# -*- coding: utf-8 -*-
"""
配置模块 - 日本招聘爬虫系统
"""
import os
from dataclasses import dataclass
from typing import Dict, List


@dataclass
class CrawlerConfig:
    """爬虫配置"""
    # 请求间隔（秒）
    min_delay: float = 2.0
    max_delay: float = 6.0
    
    # 超时设置
    page_timeout: int = 30000  # 页面加载超时（毫秒）
    wait_timeout: int = 10000  # 等待元素超时
    
    # 浏览器设置
    headless: bool = True  # 无头模式
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    
    # 重试设置
    max_retries: int = 3
    retry_delay: float = 5.0
    
    # 数据库
    db_path: str = "data/jobs.db"
    
    # 输出
    output_dir: str = "data/output"


@dataclass
class SiteConfig:
    """站点配置"""
    name: str
    base_url: str
    list_url: str
    parser_name: str = ""  # 解析器名称（默认与 name 相同）
    requires_login: bool = False
    has_cloudflare: bool = False
    rate_limit: float = 3.0  # 该站点特有的请求间隔


# 站点配置列表
SITES: Dict[str, SiteConfig] = {
    "indeed_jp": SiteConfig(
        name="Indeed Japan",
        base_url="https://jp.indeed.com",
        list_url="https://jp.indeed.com/jobs",
        parser_name="indeed_jp",
        requires_login=False,
        has_cloudflare=True,
        rate_limit=4.0
    ),
    "rikunabi": SiteConfig(
        name="リクナビNEXT",
        base_url="https://next.rikunabi.com",
        list_url="https://next.rikunabi.com/search",
        parser_name="rikunabi",
        requires_login=False,
        has_cloudflare=True,
        rate_limit=5.0
    ),
    "doda": SiteConfig(
        name="doda",
        base_url="https://doda.jp",
        list_url="https://doda.jp/DodaFront/View/JobSearchList.action",
        parser_name="doda",
        requires_login=False,
        has_cloudflare=True,
        rate_limit=5.0
    ),
    "wantedly": SiteConfig(
        name="Wantedly",
        base_url="https://www.wantedly.com",
        list_url="https://www.wantedly.com/projects",
        parser_name="wantedly",
        requires_login=False,
        has_cloudflare=False,
        rate_limit=3.0
    ),
    "mynavi": SiteConfig(
        name="マイナビ転職",
        base_url="https://tenshoku.mynavi.jp",
        list_url="https://tenshoku.mynavi.jp/list",
        parser_name="mynavi",
        requires_login=False,
        has_cloudflare=True,
        rate_limit=5.0
    ),
}


# 关键词搜索配置
DEFAULT_KEYWORDS = [
    "エンジニア",  # 工程师
    "プログラマー",  # 程序员
    "Web開発",  # Web开发
    "IT",  # IT
    "システムエンジニア",  # 系统工程师
]

# 地区配置
DEFAULT_LOCATIONS = [
    "東京都",
    "神奈川県",
    "大阪府",
    "愛知県",
]
