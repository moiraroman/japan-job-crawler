# Japan Job Crawler

日本招聘信息聚合爬虫——自动化抓取 Indeed Japan、Wantedly、りくナビNEXT、doda、みんなの、就職等主流日本招聘网站的职位信息，支持 SQLite 持久化、CSV/JSON 导出，以及 Web UI 可视化操作。

> ⚠️ **免责声明**：本工具仅供个人求职研究和学习使用。请遵守各网站的服务条款和 robots.txt，勿用于商业爬取或高频请求。

---

## 主要特性

| 特性 | 说明 |
|------|------|
| 🌐 多站点支持 | Indeed、Wantaddy、りくナビNEXT、doda 等（插件式扩展） |
| 🧠 Playwright 渲染 | 真实浏览器抓取，应对 JS 动态渲染和 Cloudflare |
| 🤖 人类行为模拟 | 随机延迟、鼠标滚动、随机点击，降低被封概率 |
| 📊 统一数据模型 | 所有站点统一 `JobInfo` 数据结构 |
| 🔄 去重 & 持久化 | SQLite 本地存储，基于 URL 自动去重 |
| 📤 导出 | 支持 CSV（Excel 兼容）和 JSON 导出 |
| 🖥️ Web UI | 启动本地 Web 界面，可视化配置爬虫任务 |
| ⏰ 定时任务 | 支持设置定时爬取间隔 |
| 🔌 REST API | FastAPI 提供查询/统计/导出接口 |

---

## 架构

```
┌─────────────────────────────────────────────┐
│          main.py / webui.py / api.py        │
│        (CLI · Web UI · REST API)            │
└──────────────────────┬──────────────────────┘
                       │
┌──────────────────────▼──────────────────────┐
│              Scheduler                       │
│         频率控制 · 任务队列 · 重试             │
└──────────────────────┬──────────────────────┘
                       │
┌──────────────────────▼──────────────────────┐
│         Spider Layer (站点适配)               │
│  IndeedSpider · WantedlySpider · RikunabiSpider …
└──────┬───────────────────┬───────────────────┘
       │                   │
┌──────▼──────┐   ┌────────▼────────┐
│  Fetcher    │   │     Parser       │
│ (Playwright)│   │ (lxml + BS4)     │
└──────┬──────┘   └────────┬────────┘
       │                   │
       └────────┬──────────┘
                │
       ┌────────▼────────┐
       │     Storage      │
       │    (SQLite)      │
       └──────────────────┘
```

---

## 支持的站点

| 站点 | 反爬难度 | 数据质量 | 备注 |
|------|----------|----------|------|
| Indeed Japan | ★★★☆☆ | ★★☆☆☆ | 数据量最大 |
| Wantedly | ★★☆☆☆ | ★★★★☆ | IT/Startup 公司为主 |
| りくナビNEXT | ★★★★☆ | ★★★★☆ | 高质量企业直招 |
| doda | ★★★☆☆ | ★★★★☆ | 职位详情丰富 |
| みんなの就職 | ★★★☆☆ | ★★★☆☆ | 传统企业为主 |

---

## 安装

### 环境要求

- Python 3.11+
- Windows / macOS / Linux

### 步骤

```bash
# 1. 克隆仓库
git clone https://github.com/moiraroman/japan-job-crawler.git
cd japan-job-crawler

# 2. 创建虚拟环境（推荐）
python -m venv venv
# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 安装 Playwright 浏览器
playwright install chromium
```

---

## 快速开始

### CLI 爬取

```bash
# 爬取所有站点（默认关键词）
python main.py

# 指定站点
python main.py --sites indeed_jp wantedly

# 自定义关键词和地点
python main.py --keywords "Python エンジニア" "Web エンジニア" --locations "東京都" "大阪府"

# 限制页数
python main.py --max-pages 3

# 显示浏览器（调试用）
python main.py --headed

# 试运行（不保存数据）
python main.py --dry-run
```

### Web UI

```bash
python webui.py
# 浏览器打开 http://localhost:8080
```

### API 服务

```bash
python api.py
# 启动后访问 http://localhost:8000/docs 查看接口文档
```

### 定时爬取

```bash
# 每 6 小时执行一次
python main.py --schedule --interval 6
```

### 导出数据

```bash
# CSV 导出
python main.py --export-csv output/jobs.csv

# JSON 导出
python main.py --export-json output/jobs.json

# 按来源筛选
python main.py --export-csv output/wantedly.csv --sites wantedly
```

---

## 项目结构

```
japan-job-crawler/
├── main.py                    # CLI 入口
├── webui.py                   # Web UI 入口 (端口 8080)
├── api.py                     # FastAPI 服务 (端口 8000)
├── scheduler.py               # 任务调度器
├── test_crawler.py            # 集成测试
├── verify.py                  # 配置验证
├── requirements.txt           # 依赖清单
├── .gitignore
├── README.md
├── DESIGN.md                  # 产品设计文档
├── config/
│   ├── settings.py            # 站点配置 & 全局参数
│   └── __init__.py
├── fetcher/
│   ├── browser_fetcher.py     # Playwright 封装
│   └── __init__.py
├── parser/
│   ├── html_parser.py         # HTML 解析器（各站点适配）
│   └── __init__.py
├── spiders/
│   ├── base_spider.py         # Spider 基类
│   ├── mynavi_spider.py       # みんなの就職 Spider
│   └── __init__.py
├── storage/
│   ├── db.py                  # SQLite 操作
│   └── __init__.py
├── webui_templates/           # Jinja2 模板
├── webui_static/              # CSS / JS
└── data/                      # 数据库 & 导出目录
```

---

## 数据模型

```python
@dataclass
class JobInfo:
    title: str           # 职位名称
    company: str         # 公司名称
    location: str        # 工作地点
    salary: str          # 薪资
    employment_type: str # 雇佣形态（正社員 / 契約社員 等）
    description: str    # 职位描述
    requirements: str   # 要求条件
    url: str             # 详情页 URL（唯一标识，去重依据）
    source: str          # 来源站点
    posted_date: str     # 发布日期
```

---

## 添加新站点

1. 在 `config/settings.py` 添加站点配置
2. 在 `parser/html_parser.py` 添加解析器
3. 在 `spiders/base_spider.py` 添加 Spider 类

详细步骤见 `DESIGN.md`。

---

## License

MIT License - 仅供学习和个人使用，禁止商业用途。
