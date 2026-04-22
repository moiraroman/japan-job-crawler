# -*- coding: utf-8 -*-
"""
マイナビ転職 Spider
"""
import asyncio
import random
from typing import List, Optional

from spiders.base_spider import BaseSpider
from parser.html_parser import JobInfo
from config import CrawlerConfig, SiteConfig
from storage import JobStorage
from fetcher import Fetcher
import logging

logger = logging.getLogger(__name__)


class MynaviSpider(BaseSpider):
    """
    マイナビ転職 爬虫

    特点：
    - Cloudflare 防护较强
    - 强 JS 渲染
    - URL 结构：https://tenshoku.mynavi.jp/list/?kw=XXX
    """

    async def crawl_list(self, keyword: str, location: str = "", page: int = 1) -> List[str]:
        """爬取列表页"""
        url = f"{self.site_config.list_url}/?kw={keyword}&page={page}"

        if location:
            url += f"&area={location}"

        logger.info(f"マイナビ転職: 正在爬取第 {page} 页 - {keyword}")

        try:
            await self.fetcher.open_page(url)

            # マイナビ需要较长等待
            await asyncio.sleep(random.uniform(3, 5))
            await self.fetcher.wait_for_selector(
                '.js-searchResultList, .cassetteRecruit, .searchResultList',
                timeout=15000
            )

            # 滚动加载
            for _ in range(3):
                await self.fetcher.evaluate("window.scrollBy(0, window.innerHeight)")
                await asyncio.sleep(random.uniform(0.8, 1.5))

            html = await self.fetcher.get_content()
            urls = self.parser.parse_list_page(html)

            return urls

        except Exception as e:
            logger.error(f"マイナビ転職 列表页爬取失败: {e}")
            return []

    async def crawl_detail(self, url: str) -> Optional[JobInfo]:
        """爬取详情页"""
        logger.info(f"マイナビ転職: 正在爬取详情页 - {url}")

        try:
            await self.fetcher.open_page(url)
            await asyncio.sleep(random.uniform(2, 4))

            html = await self.fetcher.get_content()
            job = self.parser.parse_detail_page(html, url)

            return job

        except Exception as e:
            logger.error(f"マイナビ転職 详情页爬取失败 {url}: {e}")
            return None
