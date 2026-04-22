# -*- coding: utf-8 -*-
"""
Japan Job Crawler - Web UI
FastAPI + Jinja2 驱动的可视化界面
"""
import os
import sys
import asyncio
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn

# 添加项目路径
BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))

from storage import JobStorage
from config import SITES, CrawlerConfig
from spiders import create_spider

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 初始化 FastAPI
app = FastAPI(
    title="Japan Job Crawler Web UI",
    description="Visual job search and crawler control panel",
    version="1.0.0"
)

# 静态文件和模板
STATIC_DIR = BASE_DIR / "webui_static"
TEMPLATES_DIR = BASE_DIR / "webui_templates"
STATIC_DIR.mkdir(exist_ok=True)
TEMPLATES_DIR.mkdir(exist_ok=True)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# 使用自定义 Jinja2Templates，禁用模板缓存避免 context dict 无法 hash 的问题
from jinja2 import Environment, FileSystemLoader
from starlette.templating import Jinja2Templates as _Jinja2Templates, _TemplateResponse
from starlette.responses import HTMLResponse

class _NoCacheTemplateResponse(_TemplateResponse):
    """禁用模板缓存的 TemplateResponse"""
    def __init__(self, *args, **kwargs):
        self._template_name = args[0] if args else kwargs.get('name')
        self.context = kwargs.get('context', {})
        self.status_code = kwargs.get('status_code', 200)

class Jinja2Templates(_Jinja2Templates):
    """禁用模板缓存的 Jinja2 模板引擎"""
    TemplateResponse = _NoCacheTemplateResponse
    
    def get_template(self, name: str):
        # 直接从 env 获取模板，绕过 _template_cache
        return self.env.get_template(name)

jinja_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    auto_reload=True,
)
templates = Jinja2Templates(env=jinja_env)

def render_template(request, name, context):
    """手动渲染模板并返回 HTMLResponse"""
    template = templates.env.get_template(name)
    content = template.render(request=request, **context)
    return HTMLResponse(content=content)

# 全局状态
class CrawlerState:
    """爬虫运行状态"""
    is_running: bool = False
    current_task: Optional[asyncio.Task] = None
    progress: dict = {
        "total": 0,
        "completed": 0,
        "failed": 0,
        "current_site": "",
        "current_keyword": "",
        "status": "idle"
    }

    # 创建日志目录
(BASE_DIR / "logs").mkdir(exist_ok=True)

state = CrawlerState()
config = CrawlerConfig(db_path=str(BASE_DIR / "data" / "jobs.db"))
storage = JobStorage(config.db_path)

# 确保数据目录存在
(BASE_DIR / "data").mkdir(exist_ok=True)
(BASE_DIR / "data" / "output").mkdir(exist_ok=True)

# 日志文件处理器 - 实时写入文件
log_file = BASE_DIR / "logs" / "crawler.log"
file_handler = logging.FileHandler(str(log_file), encoding='utf-8', mode='a')
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%H:%M:%S'))
file_handler.setLevel(logging.INFO)
root_logger = logging.getLogger()
root_logger.addHandler(file_handler)


# ============================================================
# 页面路由
# ============================================================

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """主页 - 职位列表"""
    site_names = {site_id: site.name for site_id, site in SITES.items()}
    return render_template(request, "index.html", {
        "sites": list(SITES.keys()),
        "site_names": site_names
    })


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """仪表盘"""
    sites_data = {
        site_id: {
            "name": site.name,
            "base_url": site.base_url,
            "rate_limit": site.rate_limit,
            "has_cloudflare": site.has_cloudflare
        }
        for site_id, site in SITES.items()
    }
    return render_template(request, "dashboard.html", {
        "stats": storage.get_stats(),
        "recent_jobs": storage.get_jobs(limit=10),
        "sites": sites_data
    })


@app.get("/crawler", response_class=HTMLResponse)
async def crawler_page(request: Request):
    """爬虫控制页"""
    sites_data = {
        site_id: {
            "name": site.name,
            "base_url": site.base_url,
            "rate_limit": site.rate_limit,
            "has_cloudflare": site.has_cloudflare
        }
        for site_id, site in SITES.items()
    }
    return render_template(request, "crawler.html", {
        "sites": sites_data,
        "state": {"is_running": state.is_running, "progress": state.progress}
    })


# ============================================================
# API 接口
# ============================================================

@app.get("/api/jobs")
async def get_jobs(
    source: Optional[str] = None,
    keyword: Optional[str] = None,
    company: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
):
    """获取职位列表"""
    jobs = storage.get_jobs(
        source=source,
        keyword=keyword,
        company=company,
        limit=limit,
        offset=offset
    )
    stats = storage.get_stats()
    return JSONResponse({
        "jobs": [dict(j) for j in jobs],
        "total": stats["total"],
        "offset": offset,
        "limit": limit
    })


@app.get("/api/stats")
async def get_stats():
    """获取统计信息"""
    return JSONResponse(storage.get_stats())


@app.get("/api/search")
async def search_jobs(q: str, limit: int = 20):
    """搜索职位"""
    jobs = storage.search(q, limit=limit)
    return JSONResponse({
        "query": q,
        "count": len(jobs),
        "jobs": [dict(j) for j in jobs]
    })


@app.get("/api/sites")
async def get_sites():
    """获取站点列表"""
    return JSONResponse({
        site_id: {
            "name": site.name,
            "base_url": site.base_url,
            "rate_limit": site.rate_limit,
            "has_cloudflare": site.has_cloudflare
        }
        for site_id, site in SITES.items()
    })


@app.get("/api/crawler/status")
async def crawler_status():
    """获取爬虫状态"""
    return JSONResponse({
        "is_running": state.is_running,
        "progress": state.progress
    })


@app.post("/api/crawler/start")
async def start_crawler(
    sites: list[str],
    keywords: list[str],
    max_pages: int = 3,
    background_tasks: BackgroundTasks = None
):
    """启动爬虫"""
    if state.is_running:
        raise HTTPException(status_code=400, detail="爬虫正在运行中")

    async def run_crawler():
        import logging
        log = logging.getLogger("crawler_run")
        state.is_running = True
        state.progress = {
            "total": len(sites) * len(keywords) * max_pages,
            "completed": 0,
            "failed": 0,
            "saved": 0,
            "current_site": "",
            "current_keyword": "",
            "current_page": 0,
            "status": "running",
            "logs": []
        }
        
        def add_log(msg):
            """添加日志到 progress"""
            ts = datetime.now().strftime("%H:%M:%S")
            entry = f"[{ts}] {msg}"
            state.progress["logs"].append(entry)
            # 只保留最近 100 条
            if len(state.progress["logs"]) > 100:
                state.progress["logs"] = state.progress["logs"][-100:]
            log.info(msg)

        try:
            add_log(f"=== 爬虫启动: 站点={sites}, 关键词={keywords}, 每站={max_pages}页 ===")
            
            for site_id in sites:
                site_config = SITES.get(site_id)
                if not site_config:
                    add_log(f"[跳过] 未找到站点配置: {site_id}")
                    continue

                spider = create_spider(site_id, config, storage)
                if not spider:
                    add_log(f"[跳过] 无法创建爬虫: {site_id}")
                    continue

                try:
                    await spider.start()  # 启动浏览器
                    add_log(f"[启动] {site_config.name} 浏览器已启动")

                    for keyword in keywords:
                        for page in range(1, max_pages + 1):
                            state.progress["current_site"] = site_config.name
                            state.progress["current_keyword"] = keyword
                            state.progress["current_page"] = page

                            try:
                                add_log(f"[列表] {site_config.name} | 关键词={keyword} | 第{page}页")
                                
                                # 爬取列表页，获取职位 URL 列表
                                urls = await spider.crawl_list(keyword, page=page)
                                
                                if not urls:
                                    add_log(f"[空页] {site_config.name} 第{page}页无结果")
                                else:
                                    add_log(f"[发现] {site_config.name} 第{page}页找到 {len(urls)} 个职位")
                                    
                                    # 爬取每个职位的详情
                                    for url in urls:
                                        try:
                                            job = await spider.crawl_detail(url)
                                            if job and job.is_valid():
                                                job_dict = job.to_dict()
                                                job_dict["source"] = site_id
                                                job_dict["keyword"] = keyword
                                                if storage.save_job(job_dict):
                                                    state.progress["saved"] += 1
                                                    add_log(f"[保存] {job.title} @ {job.company}")
                                                else:
                                                    add_log(f"[去重] {job.title} (已存在)")
                                            else:
                                                add_log(f"[无效] 跳过: {url}")
                                        except Exception as e:
                                            state.progress["failed"] += 1
                                            add_log(f"[错误] 详情页: {e}")

                            except Exception as e:
                                state.progress["failed"] += 1
                                add_log(f"[失败] {site_config.name} 第{page}页: {e}")

                            state.progress["completed"] += 1
                            
                            # 页面间延迟
                            await asyncio.sleep(site_config.rate_limit)

                    add_log(f"[完成] {site_config.name} 爬取完毕")

                finally:
                    await spider.close()  # 关闭浏览器

        except Exception as e:
            add_log(f"[致命] 爬虫异常: {e}")
        finally:
            state.is_running = False
            state.progress["status"] = "completed"
            add_log(f"=== 爬虫结束: 保存={state.progress['saved']} 失败={state.progress['failed']} ===")

    background_tasks.add_task(run_crawler)
    return JSONResponse({"message": "爬虫已启动", "status": "started"})


@app.post("/api/crawler/stop")
async def stop_crawler():
    """停止爬虫"""
    if state.current_task:
        state.current_task.cancel()
    state.is_running = False
    state.progress["status"] = "stopped"
    return JSONResponse({"message": "爬虫已停止", "status": "stopped"})


@app.get("/api/export/{fmt}")
async def export_data(fmt: str, source: Optional[str] = None):
    """导出数据"""
    if fmt not in ["csv", "json"]:
        raise HTTPException(status_code=400, detail="仅支持 CSV/JSON 格式")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"jobs_export_{timestamp}.{fmt}"
    filepath = BASE_DIR / "data" / "output" / filename

    if fmt == "csv":
        count = storage.export_to_csv(str(filepath), source=source)
    else:
        count = storage.export_to_json(str(filepath), source=source)

    return JSONResponse({
        "message": "导出成功",
        "filename": filename,
        "count": count,
        "path": f"/static/downloads/{filename}"
    })


@app.get("/api/jobs/{job_id}")
async def get_job_detail(job_id: int):
    """获取职位详情"""
    jobs = storage.get_jobs(limit=1)
    for job in jobs:
        if job["id"] == job_id:
            return JSONResponse(dict(job))
    raise HTTPException(status_code=404, detail="职位不存在")


# ============================================================
# 启动
# ============================================================

def run(host: str = "0.0.0.0", port: int = 8080):
    """启动 Web UI"""
    logger.info(f"Starting Japan Job Crawler Web UI on http://{host}:{port}")
    logger.info(f"Database: {config.db_path}")
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",
        reload=False
    )


if __name__ == "__main__":
    run()
