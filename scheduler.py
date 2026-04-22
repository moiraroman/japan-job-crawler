# -*- coding: utf-8 -*-
"""
Scheduler 模块 - 任务调度器
控制爬虫频率、管理任务队列
"""
import asyncio
import random
from typing import List, Dict, Optional
from datetime import datetime
import logging

from config import CrawlerConfig, SITES, DEFAULT_KEYWORDS, DEFAULT_LOCATIONS
from fetcher import Fetcher
from spiders import create_spider, BaseSpider
from storage import JobStorage, SearchHistory

logger = logging.getLogger(__name__)


class Scheduler:
    """
    任务调度器
    
    职责：
    1. 控制爬虫执行频率
    2. 管理任务队列
    3. 并发控制
    4. 错误处理和重试
    """
    
    def __init__(
        self,
        config: Optional[CrawlerConfig] = None,
        keywords: Optional[List[str]] = None,
        locations: Optional[List[str]] = None,
        sites: Optional[List[str]] = None
    ):
        self.config = config or CrawlerConfig()
        self.keywords = keywords or DEFAULT_KEYWORDS
        self.locations = locations or DEFAULT_LOCATIONS
        self.target_sites = sites or list(SITES.keys())
        
        self.storage = JobStorage(self.config.db_path)
        self.history = SearchHistory(self.config.db_path)
        
        self._running = False
        self._tasks: List[asyncio.Task] = []
    
    async def run(
        self,
        max_pages: int = 3,
        concurrent: int = 1,
        dry_run: bool = False
    ) -> Dict:
        """
        执行爬取任务
        
        Args:
            max_pages: 每个关键词每站最多爬取页数
            concurrent: 并发爬虫数（建议 1-2，避免被封）
            dry_run: 试运行模式，不保存数据
        
        Returns:
            执行统计信息
        """
        self._running = True
        start_time = datetime.now()
        
        stats = {
            "start_time": start_time.isoformat(),
            "total_saved": 0,
            "by_site": {},
            "errors": []
        }
        
        logger.info(f"开始爬取任务 - 站点: {self.target_sites}, 关键词: {len(self.keywords)} 个")
        
        try:
            # 顺序爬取每个站点（避免并发被封）
            for site_name in self.target_sites:
                if not self._running:
                    break
                
                site_stats = await self._crawl_site(
                    site_name,
                    max_pages=max_pages,
                    dry_run=dry_run
                )
                
                stats["by_site"][site_name] = site_stats
                stats["total_saved"] += site_stats.get("saved", 0)
                
                # 站点间延迟
                delay = random.uniform(5, 10)
                logger.info(f"等待 {delay:.1f} 秒后继续下一个站点...")
                await asyncio.sleep(delay)
        
        except Exception as e:
            logger.error(f"爬取任务异常: {e}")
            stats["errors"].append(str(e))
        
        finally:
            self._running = False
            end_time = datetime.now()
            stats["end_time"] = end_time.isoformat()
            stats["duration_seconds"] = (end_time - start_time).total_seconds()
        
        logger.info(f"爬取任务完成 - 共保存 {stats['total_saved']} 条职位")
        return stats
    
    async def _crawl_site(
        self,
        site_name: str,
        max_pages: int = 3,
        dry_run: bool = False
    ) -> Dict:
        """
        爬取单个站点
        
        Args:
            site_name: 站点名称
            max_pages: 最多爬取页数
            dry_run: 是否试运行
        
        Returns:
            站点统计信息
        """
        stats = {
            "site": site_name,
            "saved": 0,
            "errors": []
        }
        
        spider = create_spider(site_name, self.config, self.storage)
        if not spider:
            logger.error(f"无法创建 {site_name} 的爬虫")
            stats["errors"].append(f"Spider creation failed")
            return stats
        
        try:
            await spider.start()
            
            saved = await spider.crawl(
                keywords=self.keywords,
                locations=self.locations,
                max_pages=max_pages
            )
            
            stats["saved"] = saved
            
        except Exception as e:
            logger.error(f"爬取 {site_name} 失败: {e}")
            stats["errors"].append(str(e))
        
        finally:
            await spider.close()
        
        return stats
    
    def stop(self):
        """停止爬取任务"""
        self._running = False
        logger.info("正在停止爬取任务...")
    
    async def run_with_schedule(
        self,
        interval_hours: int = 6,
        max_pages: int = 3
    ):
        """
        定时执行爬取
        
        Args:
            interval_hours: 执行间隔（小时）
            max_pages: 每次最多爬取页数
        """
        logger.info(f"启动定时爬取任务，间隔 {interval_hours} 小时")
        
        while True:
            try:
                await self.run(max_pages=max_pages)
                
                # 等待下一次执行
                await asyncio.sleep(interval_hours * 3600)
                
            except KeyboardInterrupt:
                logger.info("收到停止信号，退出定时任务")
                break
            except Exception as e:
                logger.error(f"定时任务异常: {e}")
                await asyncio.sleep(300)  # 错误后等待 5 分钟重试


class TaskQueue:
    """
    任务队列（用于更精细的任务管理）
    """
    
    def __init__(self, max_concurrent: int = 2):
        self.max_concurrent = max_concurrent
        self._queue: asyncio.Queue = None
        self._workers: List[asyncio.Task] = []
    
    async def add_task(self, task: Dict):
        """添加任务到队列"""
        await self._queue.put(task)
    
    async def start_workers(self, worker_func):
        """启动工作协程"""
        self._queue = asyncio.Queue()
        
        for i in range(self.max_concurrent):
            worker = asyncio.create_task(worker_func(self._queue))
            self._workers.append(worker)
    
    async def stop_workers(self):
        """停止所有工作协程"""
        for worker in self._workers:
            worker.cancel()
        self._workers.clear()
