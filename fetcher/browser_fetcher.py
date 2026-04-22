# -*- coding: utf-8 -*-
"""
Fetcher 模块 - 浏览器自动化层
基于 Playwright 实现，支持反爬行为模拟
"""
import asyncio
import random
from typing import Optional, List, Dict, Any
from playwright.async_api import async_playwright, Page, Browser, BrowserContext
import logging

logger = logging.getLogger(__name__)


class Fetcher:
    """
    浏览器自动化 Fetcher
    
    核心功能：
    1. 模拟人类行为（随机延迟、鼠标移动、滚动）
    2. 反检测（隐藏 webdriver 特征）
    3. 代理支持
    4. Cookie 持久化
    """
    
    def __init__(
        self,
        headless: bool = True,
        user_agent: Optional[str] = None,
        proxy: Optional[Dict[str, str]] = None,
        cookies_dir: str = "data/cookies"
    ):
        self.headless = headless
        self.user_agent = user_agent or self._default_user_agent()
        self.proxy = proxy
        self.cookies_dir = cookies_dir
        
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
    
    @staticmethod
    def _default_user_agent() -> str:
        """随机选择 User-Agent"""
        agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
        ]
        return random.choice(agents)
    
    async def start(self):
        """启动浏览器"""
        self._playwright = await async_playwright().start()
        
        # 浏览器启动参数
        launch_args = [
            "--disable-blink-features=AutomationControlled",  # 隐藏自动化特征
            "--disable-dev-shm-usage",
            "--no-sandbox",
            "--disable-setuid-sandbox",
        ]
        
        # 代理配置
        if self.proxy:
            launch_args.append(f"--proxy-server={self.proxy.get('server')}")
        
        self._browser = await self._playwright.chromium.launch(
            headless=self.headless,
            args=launch_args
        )
        
        # 创建上下文（隔离的浏览器环境）
        self._context = await self._browser.new_context(
            user_agent=self.user_agent,
            viewport={"width": 1920, "height": 1080},
            locale="ja-JP",
            timezone_id="Asia/Tokyo",
        )
        
        # 注入反检测脚本
        await self._inject_stealth_scripts()
        
        # 创建页面
        self._page = await self._context.new_page()
        
        logger.info("浏览器启动成功")
    
    async def _inject_stealth_scripts(self):
        """注入反检测 JavaScript"""
        # 隐藏 webdriver 属性
        await self._context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            
            // 隐藏 Chrome 自动化标志
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            
            // 添加 Chrome 对象
            window.chrome = {
                runtime: {}
            };
            
            // 覆盖 permissions 查询
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
        """)
    
    async def close(self):
        """关闭浏览器"""
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        logger.info("浏览器已关闭")
    
    async def open_page(self, url: str, wait_until: str = "networkidle") -> str:
        """
        打开页面
        
        Args:
            url: 目标 URL
            wait_until: 等待策略 (load, domcontentloaded, networkidle)
        
        Returns:
            最终 URL（处理重定向）
        """
        logger.info(f"正在打开: {url}")
        
        try:
            response = await self._page.goto(url, wait_until=wait_until, timeout=30000)
            
            # 模拟人类行为
            await self._simulate_human_behavior()
            
            final_url = self._page.url
            logger.info(f"页面加载完成: {final_url}")
            
            return final_url
            
        except Exception as e:
            logger.error(f"打开页面失败: {e}")
            raise
    
    async def _simulate_human_behavior(self):
        """模拟人类浏览行为"""
        # 随机等待
        await self._page.wait_for_timeout(random.randint(1000, 3000))
        
        # 随机滚动
        scroll_times = random.randint(1, 3)
        for _ in range(scroll_times):
            delta = random.randint(300, 800)
            await self._page.mouse.wheel(0, delta)
            await self._page.wait_for_timeout(random.randint(500, 1500))
        
        # 随机移动鼠标
        x = random.randint(100, 1800)
        y = random.randint(100, 900)
        await self._page.mouse.move(x, y)
    
    async def get_content(self) -> str:
        """获取页面 HTML 内容"""
        return await self._page.content()
    
    async def get_text(self, selector: str) -> str:
        """获取元素文本"""
        element = await self._page.query_selector(selector)
        if element:
            return await element.text_content() or ""
        return ""
    
    async def get_full_text(self) -> str:
        """获取页面完整文本（用于提取动态渲染内容）"""
        try:
            return await self._page.inner_text('body')
        except Exception:
            return ""
    
    async def get_inner_html(self, selector: str = 'body') -> str:
        """获取元素内部 HTML（支持动态内容）"""
        try:
            elem = await self._page.query_selector(selector)
            if elem:
                return await elem.inner_html()
        except Exception:
            pass
        return ""
    
    async def click(self, selector: str, delay: float = 0.1):
        """点击元素（带随机延迟）"""
        await self._page.click(selector, delay=delay * 1000)
        await self._page.wait_for_timeout(random.randint(500, 1500))
    
    async def fill(self, selector: str, text: str, delay: float = 0.05):
        """填写表单（模拟逐字输入）"""
        await self._page.click(selector)
        await self._page.fill(selector, text)
        await self._page.wait_for_timeout(random.randint(500, 1000))
    
    async def wait_for_selector(self, selector: str, timeout: int = 10000):
        """等待元素出现"""
        await self._page.wait_for_selector(selector, timeout=timeout)
    
    async def wait_for_navigation(self, timeout: int = 30000):
        """等待页面导航完成"""
        await self._page.wait_for_load_state("networkidle", timeout=timeout)
    
    async def screenshot(self, path: str):
        """截图"""
        await self._page.screenshot(path=path)
        logger.info(f"截图已保存: {path}")
    
    async def evaluate(self, script: str) -> Any:
        """执行 JavaScript"""
        return await self._page.evaluate(script)
    
    async def query_selector_all(self, selector: str) -> List[Any]:
        """查询所有匹配元素"""
        return await self._page.query_selector_all(selector)
    
    async def save_cookies(self, site_name: str):
        """保存 Cookie"""
        import json
        import os
        
        os.makedirs(self.cookies_dir, exist_ok=True)
        cookies = await self._context.cookies()
        
        path = os.path.join(self.cookies_dir, f"{site_name}_cookies.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cookies, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Cookie 已保存: {path}")
    
    async def load_cookies(self, site_name: str) -> bool:
        """加载 Cookie"""
        import json
        import os
        
        path = os.path.join(self.cookies_dir, f"{site_name}_cookies.json")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                cookies = json.load(f)
            await self._context.add_cookies(cookies)
            logger.info(f"Cookie 已加载: {path}")
            return True
        return False
    
    @property
    def page(self) -> Page:
        """获取当前页面对象"""
        return self._page


class FetcherManager:
    """
    Fetcher 管理器
    负责管理多个 Fetcher 实例，支持并发控制
    """
    
    def __init__(self, max_concurrent: int = 3):
        self.max_concurrent = max_concurrent
        self._fetchers: List[Fetcher] = []
    
    async def acquire(self) -> Fetcher:
        """获取一个 Fetcher 实例"""
        if len(self._fetchers) < self.max_concurrent:
            fetcher = Fetcher()
            await fetcher.start()
            self._fetchers.append(fetcher)
            return fetcher
        else:
            # 等待空闲 Fetcher
            raise RuntimeError("达到最大并发数限制")
    
    async def release(self, fetcher: Fetcher):
        """释放 Fetcher"""
        await fetcher.close()
        if fetcher in self._fetchers:
            self._fetchers.remove(fetcher)
    
    async def close_all(self):
        """关闭所有 Fetcher"""
        for fetcher in self._fetchers:
            await fetcher.close()
        self._fetchers.clear()
