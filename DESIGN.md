# 日本招聘信息爬虫系统 - 产品设计文档

## 1. 产品概述

### 1.1 目标
自动化抓取日本主流招聘网站的职位信息，为求职者提供统一的职位搜索、筛选、导出功能。

### 1.2 目标用户
- 在日求职者（外国人/日本人）
- 招聘中介
- 人力资源研究机构

### 1.3 核心价值
- **一站式聚合**：统一访问 Indeed、リクナビNEXT、doda、Wantedly、マイナビ転職
- **数据去重**：基于 URL 去重，避免重复信息
- **多维度筛选**：按关键词、地点、公司、薪资等筛选
- **导出支持**：CSV/JSON 导出，支持 Excel 打开

---

## 2. 技术架构

```
┌─────────────────────────────────────────────────────────────┐
│                        CLI / API                            │
│   main.py (CLI)          │          api.py (FastAPI)       │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                      Scheduler                              │
│   任务编排、频率控制、并发管理                              │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                      Spider Layer                           │
│   IndeedSpider │ RikunabiSpider │ DodaSpider │ ...         │
└─────────────────────────────────────────────────────────────┘
                              │
┌───────────────┬───────────────────────────┬────────────────┐
│    Fetcher    │         Parser            │    Storage     │
│  (Playwright) │  (lxml + BeautifulSoup)   │   (SQLite)     │
└───────────────┴───────────────────────────┴────────────────┘
```

### 2.1 模块职责

| 模块 | 职责 | 技术选型 |
|------|------|----------|
| Fetcher | 浏览器自动化、反爬行为模拟 | Playwright |
| Parser | HTML 解析、数据提取 | lxml + BeautifulSoup |
| Spider | 站点适配、爬取流程编排 | - |
| Storage | 数据持久化、去重、导出 | SQLite |
| Scheduler | 任务调度、频率控制 | asyncio |
| API | REST 接口 | FastAPI |

---

## 3. 数据模型

### 3.1 职位信息 (JobInfo)

```python
@dataclass
class JobInfo:
    title: str           # 职位标题
    company: str         # 公司名称
    location: str        # 工作地点
    salary: str          # 薪资范围
    employment_type: str # 雇佣形态（正社員、契約社員等）
    description: str     # 职位描述
    requirements: str    # 要求条件
    url: str             # 详情页 URL（唯一标识）
    source: str          # 来源网站
    posted_date: str     # 发布日期
```

### 3.2 数据库表结构

```sql
CREATE TABLE jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    company TEXT NOT NULL,
    location TEXT,
    salary TEXT,
    employment_type TEXT,
    description TEXT,
    requirements TEXT,
    url TEXT UNIQUE NOT NULL,  -- 去重依据
    source TEXT,
    posted_date TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

---

## 4. 支持的站点

| 站点 | 特点 | 反爬难度 | 数据质量 |
|------|------|----------|----------|
| Indeed Japan | 数据量大、覆盖广 | ★★★☆☆ | ★★☆☆☆ |
| リクナビNEXT | 高质量、企业直招 | ★★★★☆ | ★★★★☆ |
| doda | 职位详情丰富 | ★★★★☆ | ★★★★☆ |
| Wantedly | IT/创业公司为主 | ★★☆☆☆ | ★★★★☆ |
| マイナビ転職 | 传统企业多 | ★★★★☆ | ★★★☆☆ |

---

## 5. 反爬策略

### 5.1 行为模拟
- 随机延迟：2-6 秒
- 鼠标滚动：模拟人类浏览
- 页面等待：等待 JS 渲染完成

### 5.2 请求控制
- 每站点独立限速
- 站点间间隔 5-10 秒
- 失败重试 3 次

### 5.3 Cloudflare 应对
- 使用真实浏览器（Playwright）
- 等待 JS Challenge 完成
- 保持 Cookie/Session

---

## 6. API 接口

### 6.1 查询职位
```
GET /jobs?source=Indeed Japan&company=Google&limit=20&offset=0
```

### 6.2 搜索职位
```
GET /search?keyword=エンジニア&limit=20
```

### 6.3 统计信息
```
GET /stats
Response: { "total": 1234, "by_source": {...}, "today": 56 }
```

### 6.4 导出数据
```
GET /export/csv?source=Indeed Japan
GET /export/json
```

---

## 7. CLI 命令

```bash
# 基础爬取
python main.py --sites indeed_jp wantedly --keywords エンジニア --max-pages 3

# 导出数据
python main.py --export csv --output jobs.csv

# 启动 API 服务
python api.py

# 定时爬取
python main.py --schedule --interval 6
```

---

## 8. 项目结构

```
japan-job-crawler/
├── main.py              # CLI 入口
├── scheduler.py         # 任务调度器
├── api.py               # FastAPI 服务
├── test_crawler.py      # 测试脚本
├── requirements.txt     # 依赖清单
├── README.md            # 使用文档
├── DESIGN.md            # 本文档
├── config/
│   ├── settings.py      # 配置定义
│   └── __init__.py
├── fetcher/
│   ├── browser_fetcher.py  # Playwright 封装
│   └── __init__.py
├── parser/
│   ├── html_parser.py      # 解析器 + 站点适配
│   └── __init__.py
├── spiders/
│   ├── base_spider.py      # Spider 基类
│   ├── mynavi_spider.py    # マイナビ転職 Spider
│   └── __init__.py
├── storage/
│   ├── db.py               # SQLite 存储
│   └── __init__.py
└── data/                   # 数据目录
    ├── jobs.db             # SQLite 数据库
    └── output/             # 导出文件
```

---

## 9. 未来扩展

### 9.1 短期
- [ ] 添加更多站点（Green、Type 等）
- [ ] 支持登录态保持
- [ ] 邮件/消息推送

### 9.2 中期
- [ ] Web UI 界面
- [ ] 全文搜索（FTS5）
- [ ] 薪资标准化解析

### 9.3 长期
- [ ] 机器学习推荐
- [ ] 多语言支持
- [ ] 分布式爬取

---

## 10. 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| 1.0.0 | 2026-04-22 | 初始版本，支持 5 个站点 |
