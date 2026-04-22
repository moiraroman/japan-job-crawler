# -*- coding: utf-8 -*-
"""
Spider 模块 - 站点爬虫
每个网站一个独立的 Spider 类
"""
import asyncio
import random
from typing import List, Optional, Dict, Generator
from abc import ABC, abstractmethod
import logging

from fetcher import Fetcher
from parser import JobInfo, get_parser
from storage import JobStorage
from config import CrawlerConfig, SiteConfig

logger = logging.getLogger(__name__)


class BaseSpider(ABC):
    """
    爬虫基类
    定义爬虫的标准接口
    """
    
    def __init__(
        self,
        config: CrawlerConfig,
        site_config: SiteConfig,
        storage: JobStorage,
        fetcher: Optional[Fetcher] = None
    ):
        self.config = config
        self.site_config = site_config
        self.storage = storage
        self.fetcher = fetcher or Fetcher(headless=config.headless)
        
        # 优先使用 parser_name，否则尝试从 name 推断
        parser_key = site_config.parser_name or site_config.name.lower().replace(" ", "_").replace("-", "_")
        self.parser = get_parser(parser_key)
        
        if not self.parser:
            raise ValueError(f"Parser not found for {site_config.name}")
    
    async def start(self):
        """启动爬虫（如果 Fetcher 未启动）"""
        if not self.fetcher.page:
            await self.fetcher.start()
    
    async def close(self):
        """关闭爬虫"""
        if self.fetcher:
            await self.fetcher.close()
    
    @abstractmethod
    async def crawl_list(self, keyword: str, location: str = "", page: int = 1) -> List[str]:
        """
        爬取列表页
        
        Args:
            keyword: 搜索关键词
            location: 地点
            page: 页码
        
        Returns:
            职位详情页 URL 列表
        """
        pass
    
    @abstractmethod
    async def crawl_detail(self, url: str) -> Optional[JobInfo]:
        """
        爬取详情页
        
        Args:
            url: 职位详情页 URL
        
        Returns:
            JobInfo 对象
        """
        pass
    
    async def crawl(
        self,
        keywords: List[str],
        locations: List[str] = None,
        max_pages: int = 3
    ) -> int:
        """
        执行爬取任务
        
        Args:
            keywords: 关键词列表
            locations: 地点列表
            max_pages: 每个关键词最多爬取页数
        
        Returns:
            成功保存的职位数量
        """
        await self.start()
        saved_count = 0
        
        try:
            for keyword in keywords:
                for location in (locations or [""]):
                    for page in range(1, max_pages + 1):
                        try:
                            # 爬取列表页
                            urls = await self.crawl_list(keyword, location, page)
                            
                            if not urls:
                                logger.info(f"{self.site_config.name}: 第 {page} 页无更多结果")
                                break
                            
                            # 爬取详情页
                            for url in urls:
                                try:
                                    job = await self.crawl_detail(url)
                                    if job and job.is_valid():
                                        if self.storage.save_job(job.to_dict()):
                                            saved_count += 1
                                    
                                    # 随机延迟
                                    delay = random.uniform(
                                        self.config.min_delay,
                                        self.config.max_delay
                                    )
                                    await asyncio.sleep(delay)
                                    
                                except Exception as e:
                                    logger.error(f"爬取详情页失败 {url}: {e}")
                                    continue
                            
                            # 页间延迟
                            await asyncio.sleep(self.site_config.rate_limit)
                            
                        except Exception as e:
                            logger.error(f"爬取列表页失败 {keyword} {location} page {page}: {e}")
                            continue
        finally:
            # 不关闭 fetcher，让调用者决定是否关闭
            pass
        
        return saved_count


class IndeedJapanSpider(BaseSpider):
    """
    Indeed Japan 爬虫
    """
    
    async def crawl_list(self, keyword: str, location: str = "", page: int = 1) -> List[str]:
        """爬取列表页"""
        start = (page - 1) * 10
        url = f"{self.site_config.list_url}?q={keyword}&l={location}&start={start}"
        
        logger.info(f"Indeed Japan: 正在爬取第 {page} 页 - {keyword} {location}")
        
        try:
            await self.fetcher.open_page(url)
            
            # 等待页面基本加载
            await asyncio.sleep(random.uniform(2, 4))
            
            # 尝试多个选择器
            for selector in ['.jobsearch-ResultsList', '.mosaic-provider-jobcards', 'ul.jobsearch-ResultsList', '[data-jk]', '#resultsContainer']:
                try:
                    await self.fetcher.wait_for_selector(selector, timeout=5000)
                    break
                except Exception:
                    continue
            
            html = await self.fetcher.get_content()
            urls = self.parser.parse_list_page(html)
            
            if urls:
                logger.info(f"Indeed 第 {page} 页找到 {len(urls)} 个职位")
            return urls
            
        except Exception as e:
            logger.error(f"Indeed Japan 列表页爬取失败: {e}")
            return []
    
    async def crawl_detail(self, url: str) -> Optional[JobInfo]:
        """爬取详情页"""
        logger.info(f"Indeed Japan: 正在爬取详情页 - {url}")
        
        try:
            await self.fetcher.open_page(url)
            await asyncio.sleep(random.uniform(1, 3))  # 等待页面加载
            
            html = await self.fetcher.get_content()
            job = self.parser.parse_detail_page(html, url)
            
            return job
            
        except Exception as e:
            logger.error(f"Indeed Japan 详情页爬取失败 {url}: {e}")
            return None


class WantedlySpider(BaseSpider):
    """
    Wantedly 爬虫
    Wantedly 使用动态加载，需要滚动触发
    """
    
    async def crawl_list(self, keyword: str, location: str = "", page: int = 1) -> List[str]:
        """爬取列表页"""
        url = f"{self.site_config.list_url}?q={keyword}&page={page}"
        if location:
            url += f"&location={location}"
        
        logger.info(f"Wantedly: 正在爬取第 {page} 页 - {keyword}")
        
        try:
            await self.fetcher.open_page(url)
            
            # Wantedly 需要滚动加载，等待网络空闲
            await asyncio.sleep(3)
            await self._scroll_to_load(scroll_times=4)
            await asyncio.sleep(2)
            
            html = await self.fetcher.get_content()
            urls = self.parser.parse_list_page(html)
            
            if urls:
                logger.info(f"Wantedly 第 {page} 页找到 {len(urls)} 个职位")
            return urls
            
        except Exception as e:
            logger.error(f"Wantedly 列表页爬取失败: {e}")
            return []
    
    async def _scroll_to_load(self, scroll_times: int = 3):
        """滚动加载更多内容"""
        for i in range(scroll_times):
            await self.fetcher.evaluate("window.scrollBy(0, window.innerHeight * 2)")
            await asyncio.sleep(random.uniform(1, 2))
            logger.debug(f"Wantedly 滚动第 {i+1}/{scroll_times} 次")
    
    async def crawl_detail(self, url: str) -> Optional[JobInfo]:
        """
        爬取详情页
        Wantedly 使用 React 动态渲染，从 Playwright 的 inner_text 直接解析
        """
        logger.info(f"Wantedly: 正在爬取详情页 - {url}")
        
        try:
            await self.fetcher.open_page(url)
            await asyncio.sleep(random.uniform(4, 6))  # 等待 React 完全渲染
            
            # 获取完整渲染文本
            full_text = await self.fetcher.get_full_text()
            
            # 从文本解析
            job = self._parse_wantedly_text(full_text, url)
            
            if job and job.is_valid():
                logger.info(f"Wantedly: 保存职位 {job.title} @ {job.company}")
                return job
            else:
                logger.warning(f"Wantedly: 文本解析失败 - {url}")
                return None
            
        except Exception as e:
            logger.error(f"Wantedly 详情页爬取失败 {url}: {e}")
            return None
    
    def _parse_wantedly_text(self, text: str, url: str) -> Optional[JobInfo]:
        """
        从 Wantedly 页面渲染文本解析职位信息
        Wantedly 页面特征文本:
        - 公司名: [company_name]のメンバー 或 直接在 正社員/中途/契約 等字样前后
        - 职位: [title] [雇用类型] 或在 h1 中
        - 地点: 东京 等
        """
        import re
        job = JobInfo(source="Wantedly", url=url)
        text_lower = text.lower()
        
        # 1. 职位标题 - h1 在页面顶部
        # 格式: "募集\n[公司名]のメンバー\n[职位类型]\n[标题]"
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        for i, line in enumerate(lines):
            if any(kw in line for kw in ['エンジニア', 'Designer', 'Developer', ' Manager', ' PG ', 'ios', 'android', 'web']):
                if 2 <= len(line) <= 80 and not line.startswith('http'):
                    job.title = line
                    break
            if i > 0 and any(kw in lines[i-1] for kw in ['メンバー', '中途', '正社員']):
                if 2 <= len(line) <= 80:
                    job.title = line
                    break
        
        if not job.title:
            # 从 URL 提取项目 ID 作为 fallback
            m = re.search(r'wantedly\.com/projects/([a-z0-9]+)', url)
            if m:
                job.title = f"Project {m.group(1)}"
        
        # 2. 公司名 - 固定格式: [公司名]のメンバー
        m = re.search(r'([\u4e00-\鿿]{2,20}(?:社|team| Inc\.| GmbH|Ltd\.|株式会社|合名会社|合資会社|合同会社))
 のメンバー', text)
        if m:
            job.company = m.group(1)
        
        if not job.company:
            # 备选: 在 "のメンバー" 前找公司名
            m = re.search(r'([\u4e00-\u9fff]{2,30}(?:社|Inc| GmbH| LTD|株式会社))\nのメンバー', text)
            if m:
                job.company = m.group(1)
        
        if not job.company:
            # 备选: 从 URL 的 company 路径
            m = re.search(r'wantedly\.com/(?:company|companies)/([^/\?]+)', url)
            if m:
                slug = m.group(1)
                # 尝试解码: company_123456 -> 取 company 前面的词
                cm = re.search(r'([\u4e00-\u9fff]{2,20}社?)', text)
                if cm:
                    job.company = cm.group(1)
        
        # 3. 地点
        prefs = ['東京都', '東京', '大阪府', '愛知県', '京都府', '神奈川県', '札幌市', '福岡市', '埼玉県', '千葉県', '兵庫県', '宮城県', '福岡県', '北海道', '静岡県', '沖縄県', '名古屋', '大阪', '京都', '横浜', '神戸', '福岡', '仙台']
        for pref in prefs:
            if pref in text:
                job.location = pref
                if pref == '東京':
                    job.location = '東京都'
                break
        
        # 4. 雇佣形态
        if '正社員' in text:
            job.employment_type = '正社員'
        elif '契約社員' in text:
            job.employment_type = '契約社員'
        elif '業務委託' in text:
            job.employment_type = '業務委託'
        elif '中途' in text:
            job.employment_type = '中途'
        
        # 5. 薪资 - Wantedly 通常不显示薪资，跳过
        
        # 6. 描述
        # 找 "こんなことやります" 或 "なにをやっているのか" 之后的内容
        start_idx = max(
 for n, l in enumerate(lines) if any(kw in l for kw in ['なにをやっているのか', 'なぜやるのか', 'こんなことやります', '得られる経験', '\/xes', 'の技術スタック']))
        if start_idx >= 0 and start_idx < len(lines):
            desc = '\n'.join(lines[start_idx:start_idx+30])
            job.description = desc[:2000]
        
        return job if (job.title or job.company) else None
    
    def _extract_from_text(self, text: str, url: str) -> Optional[JobInfo]:
        return None  # Playwright 直接提取，不需要兜底文本解析
    
    def _extract_from_dom(self, url: str) -> Optional[JobInfo]:
        return None


class RikunabiSpider(BaseSpider):
    """
    リクナビNEXT 爬虫
    """
    
    async def crawl_list(self, keyword: str, location: str = "", page: int = 1) -> List[str]:
        """爬取列表页"""
        url = f"{self.site_config.list_url}?kw={keyword}&p={page}"
        if location:
            url += f"&area={location}"
        
        logger.info(f"リクナビNEXT: 正在爬取第 {page} 页 - {keyword}")
        
        try:
            await self.fetcher.open_page(url)
            await asyncio.sleep(random.uniform(2, 4))
            await self.fetcher.evaluate("window.scrollBy(0, window.innerHeight)")
            await asyncio.sleep(1)
            
            html = await self.fetcher.get_content()
            urls = self.parser.parse_list_page(html)
            
            if urls:
                logger.info(f"リクナビNEXT 第 {page} 页找到 {len(urls)} 个职位")
            return urls
            
        except Exception as e:
            logger.error(f"リクナビNEXT 列表页爬取失败: {e}")
            return []
    
    async def crawl_detail(self, url: str) -> Optional[JobInfo]:
        """爬取详情页"""
        logger.info(f"リクナビNEXT: 正在爬取详情页 - {url}")
        
        try:
            await self.fetcher.open_page(url)
            await asyncio.sleep(random.uniform(1, 2))
            
            html = await self.fetcher.get_content()
            job = self.parser.parse_detail_page(html, url)
            
            return job
            
        except Exception as e:
            logger.error(f"リクナビNEXT 详情页爬取失败 {url}: {e}")
            return None


class DodaSpider(BaseSpider):
    """
    doda 爬虫
    """
    
    async def crawl_list(self, keyword: str, location: str = "", page: int = 1) -> List[str]:
        """爬取列表页"""
        url = f"{self.site_config.list_url}?ss=1&kw={keyword}&page={page}"
        if location:
            url += f"&pref={location}"
        
        logger.info(f"doda: 正在爬取第 {page} 页 - {keyword}")
        
        try:
            await self.fetcher.open_page(url)
            await asyncio.sleep(random.uniform(2, 4))
            await self.fetcher.evaluate("window.scrollBy(0, window.innerHeight)")
            await asyncio.sleep(1)
            
            html = await self.fetcher.get_content()
            urls = self.parser.parse_list_page(html)
            
            if urls:
                logger.info(f"doda 第 {page} 页找到 {len(urls)} 个职位")
            return urls
            
        except Exception as e:
            logger.error(f"doda 列表页爬取失败: {e}")
            return []
    
    async def crawl_detail(self, url: str) -> Optional[JobInfo]:
        """爬取详情页"""
        logger.info(f"doda: 正在爬取详情页 - {url}")
        
        try:
            await self.fetcher.open_page(url)
            await asyncio.sleep(random.uniform(1, 2))
            
            html = await self.fetcher.get_content()
            job = self.parser.parse_detail_page(html, url)
            
            return job
            
        except Exception as e:
            logger.error(f"doda 详情页爬取失败 {url}: {e}")
            return None


from spiders.mynavi_spider import MynaviSpider

# Spider 注册表
SPIDER_CLASSES = {
    "indeed_jp": IndeedJapanSpider,
    "wantedly": WantedlySpider,
    "rikunabi": RikunabiSpider,
    "doda": DodaSpider,
    "mynavi": MynaviSpider,
}


def create_spider(
    site_name: str,
    config: CrawlerConfig,
    storage: JobStorage,
    fetcher: Optional[Fetcher] = None
) -> Optional[BaseSpider]:
    """
    创建 Spider 实例
    
    Args:
        site_name: 站点名称
        config: 爬虫配置
        storage: 存储实例
        fetcher: Fetcher 实例（可选）
    
    Returns:
        Spider 实例
    """
    from config import SITES
    
    spider_class = SPIDER_CLASSES.get(site_name)
    site_config = SITES.get(site_name)
    
    if not spider_class:
        logger.error(f"未找到 {site_name} 的 Spider 类")
        return None
    
    if not site_config:
        logger.error(f"未找到 {site_name} 的站点配置")
        return None
    
    return spider_class(config, site_config, storage, fetcher)
