# -*- coding: utf-8 -*-
"""
API 服务层 - 提供查询、统计、导出接口
基于 FastAPI 实现 RESTful API
"""
from typing import List, Optional
from datetime import datetime
import json

from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from storage import JobStorage

# 创建 FastAPI 应用
app = FastAPI(
    title="日本招聘信息 API",
    description="提供职位查询、统计、导出等功能",
    version="1.0.0"
)

# 存储实例
storage = JobStorage()


# ==================== 数据模型 ====================

class JobResponse(BaseModel):
    """职位响应模型"""
    id: int
    title: str
    company: str
    location: Optional[str]
    salary: Optional[str]
    employment_type: Optional[str]
    description: Optional[str]
    url: str
    source: str
    posted_date: Optional[str]
    created_at: str


class StatsResponse(BaseModel):
    """统计响应模型"""
    total: int
    by_source: dict
    today: int


class SearchParams(BaseModel):
    """搜索参数"""
    keyword: Optional[str] = None
    company: Optional[str] = None
    source: Optional[str] = None
    limit: int = 20
    offset: int = 0


# ==================== API 路由 ====================

@app.get("/", tags=["Root"])
async def root():
    """API 根路径"""
    return {
        "name": "日本招聘信息 API",
        "version": "1.0.0",
        "endpoints": {
            "jobs": "/jobs",
            "stats": "/stats",
            "export": "/export/{format}",
            "search": "/search"
        }
    }


@app.get("/jobs", response_model=List[JobResponse], tags=["Jobs"])
async def list_jobs(
    source: Optional[str] = Query(None, description="来源站点"),
    company: Optional[str] = Query(None, description="公司名称（模糊匹配）"),
    limit: int = Query(20, ge=1, le=100, description="返回数量"),
    offset: int = Query(0, ge=0, description="偏移量")
):
    """
    查询职位列表
    
    - **source**: 筛选来源站点（Indeed Japan, Wantedly 等）
    - **company**: 模糊匹配公司名称
    - **limit**: 返回数量（1-100）
    - **offset**: 分页偏移
    """
    jobs = storage.get_jobs(source=source, company=company, limit=limit, offset=offset)
    return jobs


@app.get("/jobs/{job_id}", response_model=JobResponse, tags=["Jobs"])
async def get_job(job_id: int):
    """
    查询单个职位详情
    
    - **job_id**: 职位 ID
    """
    jobs = storage.get_jobs(limit=1, offset=0)
    # 简化实现，实际应该按 ID 查询
    if not jobs or jobs[0]["id"] != job_id:
        raise HTTPException(status_code=404, detail="Job not found")
    return jobs[0]


@app.get("/stats", response_model=StatsResponse, tags=["Stats"])
async def get_stats():
    """
    获取统计信息
    
    返回总职位数、各站点数量、今日新增等统计数据
    """
    return storage.get_stats()


@app.get("/search", response_model=List[JobResponse], tags=["Search"])
async def search_jobs(
    keyword: str = Query(..., description="搜索关键词"),
    source: Optional[str] = Query(None, description="来源站点"),
    limit: int = Query(20, ge=1, le=100, description="返回数量"),
    offset: int = Query(0, ge=0, description="偏移量")
):
    """
    搜索职位
    
    - **keyword**: 搜索关键词（匹配标题、公司、描述）
    - **source**: 筛选来源站点
    - **limit**: 返回数量
    - **offset**: 分页偏移
    """
    # 简化实现，实际应该用全文搜索
    all_jobs = storage.get_jobs(source=source, limit=10000)
    
    # 简单的关键词匹配
    filtered = []
    for job in all_jobs:
        if keyword.lower() in job.get("title", "").lower():
            filtered.append(job)
        elif keyword.lower() in job.get("company", "").lower():
            filtered.append(job)
        elif keyword.lower() in job.get("description", "").lower():
            filtered.append(job)
    
    return filtered[offset:offset+limit]


@app.get("/export/csv", tags=["Export"])
async def export_csv(source: Optional[str] = Query(None, description="来源站点")):
    """
    导出为 CSV
    
    - **source**: 筛选来源站点（可选）
    """
    import tempfile
    import os
    
    # 创建临时文件
    temp_dir = tempfile.gettempdir()
    filename = f"jobs_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    filepath = os.path.join(temp_dir, filename)
    
    # 导出
    count = storage.export_to_csv(filepath, source=source)
    
    if count == 0:
        raise HTTPException(status_code=404, detail="No data to export")
    
    # 返回文件
    def iterfile():
        with open(filepath, mode="rb") as f:
            yield from f
        os.remove(filepath)  # 清理临时文件
    
    return StreamingResponse(
        iterfile(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@app.get("/export/json", tags=["Export"])
async def export_json(source: Optional[str] = Query(None, description="来源站点")):
    """
    导出为 JSON
    
    - **source**: 筛选来源站点（可选）
    """
    jobs = storage.get_jobs(source=source, limit=10000)
    
    if not jobs:
        raise HTTPException(status_code=404, detail="No data to export")
    
    return JSONResponse(
        content={"count": len(jobs), "jobs": jobs},
        headers={"Content-Disposition": f"attachment; filename=jobs_export.json"}
    )


@app.get("/sources", tags=["Meta"])
async def list_sources():
    """
    获取所有来源站点列表
    """
    stats = storage.get_stats()
    sources = []
    
    for source, count in stats["by_source"].items():
        sources.append({
            "name": source,
            "count": count
        })
    
    return {"sources": sources}


# ==================== 启动命令 ====================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
