# -*- coding: utf-8 -*-
"""
Parser 模块 - 数据解析层
使用 lxml + BeautifulSoup 解析 HTML
"""
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict
from lxml import etree
from bs4 import BeautifulSoup
import re
import logging

logger = logging.getLogger(__name__)


@dataclass
class JobInfo:
    """职位信息数据结构"""
    title: str = ""
    company: str = ""
    location: str = ""
    salary: str = ""
    employment_type: str = ""  # 雇佣形态（正社員、契約社員等）
    description: str = ""
    requirements: str = ""
    url: str = ""
    source: str = ""  # 来源网站
    posted_date: str = ""
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return asdict(self)
    
    def is_valid(self) -> bool:
        """检查是否有效（至少有标题和公司名）"""
        return bool(self.title and self.company)


class BaseParser:
    """
    解析器基类
    提供通用的 HTML 解析工具方法
    """
    
    @staticmethod
    def parse_html(html: str, parser: str = "lxml") -> BeautifulSoup:
        """解析 HTML 字符串"""
        return BeautifulSoup(html, parser)
    
    @staticmethod
    def get_text(element) -> str:
        """安全获取元素文本"""
        if element is None:
            return ""
        return element.get_text(strip=True)
    
    @staticmethod
    def clean_text(text: str) -> str:
        """清理文本（去除多余空白、换行）"""
        if not text:
            return ""
        # 替换多种空白字符为单个空格
        text = re.sub(r'[\s\u3000]+', ' ', text)
        return text.strip()
    
    @staticmethod
    def extract_salary(text: str) -> str:
        """提取薪资信息"""
        if not text:
            return ""
        
        # 匹配日式薪资格式
        patterns = [
            r'月給\s*[\d,万]+円?',
            r'年収\s*[\d,万]+円?',
            r'時給\s*[\d,]+円?',
            r'日給\s*[\d,万]+円?',
            r'[\d,万]+\s*円',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group()
        
        return text
    
    @staticmethod
    def extract_location(text: str) -> str:
        """提取地点信息"""
        if not text:
            return ""
        
        # 日本都道府县列表
        prefectures = [
            "北海道", "青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県",
            "茨城県", "栃木県", "群馬県", "埼玉県", "千葉県", "東京都", "神奈川県",
            "新潟県", "富山県", "石川県", "福井県", "山梨県", "長野県", "岐阜県",
            "静岡県", "愛知県", "三重県", "滋賀県", "京都府", "大阪府", "兵庫県",
            "奈良県", "和歌山県", "鳥取県", "島根県", "岡山県", "広島県", "山口県",
            "徳島県", "香川県", "愛媛県", "高知県", "福岡県", "佐賀県", "長崎県",
            "熊本県", "大分県", "宮崎県", "鹿児島県", "沖縄県"
        ]
        
        for pref in prefectures:
            if pref in text:
                # 提取包含都道府县的完整地址
                match = re.search(rf'{pref}[^\s]*', text)
                if match:
                    return match.group()
        
        return text


class IndeedJapanParser(BaseParser):
    """
    Indeed Japan 解析器
    
    解析 indeed.jp 的职位列表和详情页
    """
    
    def parse_list_page(self, html: str) -> List[str]:
        """解析列表页，提取职位详情 URL"""
        soup = self.parse_html(html)
        urls = []
        seen = set()
        
        # 方法1: 专用选择器
        for sel in ['a.jcs-job-link', 'div[data-jk] a', 'h2.jobTitle a', 
                    '.jobsearch-JobListTable a[href*="clk?"]', 'a[data-jobid]']:
            for tag in soup.select(sel):
                href = tag.get('href', '')
                if href and '/clk?' in href and href not in seen:
                    seen.add(href)
                    if href.startswith('/'):
                        href = f"https://jp.indeed.com{href}"
                    urls.append(href)
        
        # 方法2: 通用兜底 - 所有包含 /clk? 的链接
        if not urls:
            for tag in soup.find_all('a', href=True):
                href = tag['href']
                if '/clk?' in href and href not in seen:
                    seen.add(href)
                    if href.startswith('/'):
                        href = f"https://jp.indeed.com{href}"
                    urls.append(href)
        
        logger.info(f"Indeed: 提取到 {len(urls)} 个职位链接")
        return urls
    
    def parse_detail_page(self, html: str, url: str) -> Optional[JobInfo]:
        """解析职位详情页 - 多选择器兜底"""
        soup = self.parse_html(html)
        job = JobInfo(source="Indeed Japan", url=url)
        
        try:
            # 标题
            title_elem = (
                soup.select_one('h1.jobsearch-JobInfoHeader-title') or
                soup.select_one('h1') or
                soup.select_one('[class*="title"]')
            )
            if title_elem:
                job.title = self.clean_text(title_elem.get_text())
            
            # 公司名称
            company_elem = (
                soup.select_one('.jobsearch-InlineCompanyRating a') or
                soup.select_one('[class*="company"] a') or
                soup.select_one('.companyName')
            )
            if company_elem:
                job.company = self.clean_text(company_elem.get_text())
            
            # 地点
            location_elem = (
                soup.select_one('.jobsearch-JobInfoHeader-subtitleLocation') or
                soup.select_one('[class*="location"]') or
                soup.select_one('.location')
            )
            if location_elem:
                job.location = self.extract_location(self.clean_text(location_elem.get_text()))
            
            # 薪资
            for elem in soup.find_all(class_=lambda x: x and 'salary' in x.lower() if x else False):
                text = self.clean_text(elem.get_text())
                if '円' in text or '万' in text or '年薪' in text:
                    job.salary = self.extract_salary(text)
                    break
            
            # 职位描述
            desc_elem = (
                soup.select_one('#jobDescriptionText') or
                soup.select_one('[id*="desc"]') or
                soup.select_one('[class*="description"]')
            )
            if desc_elem:
                job.description = self.clean_text(desc_elem.get_text())[:3000]
            
            if job.is_valid():
                return job
            else:
                logger.warning(f"Indeed: 职位信息不完整 - {url}")
                return None

        except Exception as e:
            logger.error(f"Indeed 解析错误: {e}")
            return None
            
            # 雇佣形态
            type_elem = soup.select_one('.jobsearch-JobMetadataHeader-item')
            if type_elem:
                text = self.clean_text(type_elem.get_text())
                if any(t in text for t in ["正社員", "契約社員", "派遣社員", "パート", "アルバイト"]):
                    job.employment_type = text
            
            if job.is_valid():
                return job
            else:
                logger.warning(f"Indeed: 职位信息不完整 - {url}")
                return None
                
        except Exception as e:
            logger.error(f"Indeed 解析错误: {e}")
            return None


class WantedlyParser(BaseParser):
    """
    Wantedly 解析器
    """
    
    def parse_list_page(self, html: str) -> List[str]:
        """解析列表页"""
        soup = self.parse_html(html)
        urls = []
        
        # Wantedly 项目卡片
        cards = soup.select('a[href*="/projects/"], div.project-card a')
        
        for card in cards:
            href = card.get('href', '')
            if href and '/projects/' in href:
                if not href.startswith('http'):
                    href = f"https://www.wantedly.com{href}"
                urls.append(href)
        
        logger.info(f"Wantedly: 提取到 {len(urls)} 个职位链接")
        return urls
    
    def parse_detail_page(self, html: str, url: str) -> Optional[JobInfo]:
        """解析详情页 - 基于实际 Wantedly HTML 结构"""
        soup = self.parse_html(html)
        job = JobInfo(source="Wantedly", url=url)
        full_text = soup.get_text()  # 全页文本用于兜底提取
        
        try:
            # 标题 - 实际: <h1 class="project-title">
            title_elem = soup.select_one('h1.project-title')
            if title_elem:
                job.title = self.clean_text(title_elem.get_text())
            
            # 公司名 - 实际: <p class="project-company-name"><a href="/companies/xxx">公司名</a></p>
            company_elem = soup.select_one('.project-company-name a')
            if not company_elem:
                company_elem = soup.select_one('.project-company-name')
            if company_elem:
                job.company = self.clean_text(company_elem.get_text())
            
            # 地点 - 实际: <p class="project-station">
            location_elem = soup.select_one('.project-station')
            if location_elem:
                loc = self.clean_text(location_elem.get_text())
                job.location = self.extract_location(loc) or loc
            
            # 描述 - 实际: <div class="project-body"> 或 <section class="project-top-content">
            desc_elem = (
                soup.select_one('.project-body') or
                soup.select_one('.project-top-content') or
                soup.select_one('.project-detail-content') or
                soup.select_one('[class*="description"]')
            )
            if desc_elem:
                job.description = self.clean_text(desc_elem.get_text())[:2000]
            
            # 薪资（部分职位有）
            salary_elem = soup.select_one('.project-salary, .salary-info')
            if salary_elem:
                job.salary = self.clean_text(salary_elem.get_text())
            
            # 如果标题/公司都没提取到，尝试从页面文本正则匹配
            if not job.title:
                import re
                m = re.search(r'<h1[^>]*class="[^"]*project[^"]*title[^"]*"[^>]*>([^<]+)', html)
                if m:
                    job.title = self.clean_text(m.group(1))
            
            if not job.company:
                import re
                m = re.search(r'class="project-company-name"[^>]*>.*?<a[^>]*>([^<]+)', html)
                if not m:
                    m = re.search(r'class="project-company-name"[^>]*>([^<]+)', html)
                if m:
                    job.company = self.clean_text(m.group(1))
            
            if job.is_valid():
                return job
            else:
                logger.warning(f"Wantedly: 职位信息不完整 - {url}")
                return None
                
        except Exception as e:
            logger.error(f"Wantedly 解析错误: {e}")
            return None


class RikunabiParser(BaseParser):
    """
    リクナビNEXT 解析器
    """
    
    def parse_list_page(self, html: str) -> List[str]:
        """解析列表页"""
        soup = self.parse_html(html)
        urls = []
        
        # リクナビNEXT 职位链接
        links = soup.select('a[href*="/job/"], a[href*="/company/"]')
        
        for link in links:
            href = link.get('href', '')
            if href and '/job/' in href:
                if not href.startswith('http'):
                    href = f"https://next.rikunabi.com{href}"
                urls.append(href)
        
        logger.info(f"リクナビNEXT: 提取到 {len(urls)} 个职位链接")
        return urls
    
    def parse_detail_page(self, html: str, url: str) -> Optional[JobInfo]:
        """解析详情页"""
        soup = self.parse_html(html)
        job = JobInfo(source="リクナビNEXT", url=url)
        
        try:
            # 标题
            title_elem = soup.select_one('h1.job-title, .job-detail-title')
            if title_elem:
                job.title = self.clean_text(title_elem.get_text())
            
            # 公司
            company_elem = soup.select_one('.company-name, .job-detail-company-name')
            if company_elem:
                job.company = self.clean_text(company_elem.get_text())
            
            # 地点
            location_elem = soup.select_one('.work-place, .job-detail-location')
            if location_elem:
                job.location = self.extract_location(self.clean_text(location_elem.get_text()))
            
            # 薪资
            salary_elem = soup.select_one('.salary, .job-detail-salary')
            if salary_elem:
                job.salary = self.extract_salary(self.clean_text(salary_elem.get_text()))
            
            # 描述
            desc_elem = soup.select_one('.job-description, .job-detail-description')
            if desc_elem:
                job.description = self.clean_text(desc_elem.get_text())
            
            if job.is_valid():
                return job
            else:
                logger.warning(f"リクナビNEXT: 职位信息不完整 - {url}")
                return None
                
        except Exception as e:
            logger.error(f"リクナビNEXT 解析错误: {e}")
            return None


class DodaParser(BaseParser):
    """
    doda 解析器
    """
    
    def parse_list_page(self, html: str) -> List[str]:
        """解析列表页"""
        soup = self.parse_html(html)
        urls = []
        
        links = soup.select('a[href*="/job/"], .job-list-item a')
        
        for link in links:
            href = link.get('href', '')
            if href and '/job/' in href:
                if not href.startswith('http'):
                    href = f"https://doda.jp{href}"
                urls.append(href)
        
        logger.info(f"doda: 提取到 {len(urls)} 个职位链接")
        return urls
    
    def parse_detail_page(self, html: str, url: str) -> Optional[JobInfo]:
        """解析详情页"""
        soup = self.parse_html(html)
        job = JobInfo(source="doda", url=url)
        
        try:
            # doda 页面结构较复杂，需要根据实际页面调整
            title_elem = soup.select_one('h1, .job-title')
            if title_elem:
                job.title = self.clean_text(title_elem.get_text())
            
            company_elem = soup.select_one('.company-name, .job-company-name')
            if company_elem:
                job.company = self.clean_text(company_elem.get_text())
            
            # 提取所有文本，然后解析
            all_text = soup.get_text()
            
            # 薪资提取
            job.salary = self.extract_salary(all_text)
            
            # 地点提取
            job.location = self.extract_location(all_text)
            
            # 描述
            desc_elem = soup.select_one('.job-description, .job-detail-content')
            if desc_elem:
                job.description = self.clean_text(desc_elem.get_text())
            
            if job.is_valid():
                return job
            else:
                logger.warning(f"doda: 职位信息不完整 - {url}")
                return None
                
        except Exception as e:
            logger.error(f"doda 解析错误: {e}")
            return None


class MynaviParser(BaseParser):
    """
    マイナビ転職 解析器
    """

    def parse_list_page(self, html: str) -> List[str]:
        """解析列表页"""
        soup = self.parse_html(html)
        urls = []

        links = soup.select('a[href*="/job/"], a[href*="/info/"], .cassetteRecruit a')

        for link in links:
            href = link.get('href', '')
            if href:
                if not href.startswith('http'):
                    href = f"https://tenshoku.mynavi.jp{href}"
                urls.append(href)

        logger.info(f"マイナビ転職: 提取到 {len(urls)} 个职位链接")
        return urls

    def parse_detail_page(self, html: str, url: str) -> Optional[JobInfo]:
        """解析详情页"""
        soup = self.parse_html(html)
        job = JobInfo(source="マイナビ転職", url=url)

        try:
            title_elem = soup.select_one('h1, .job-title, .heading-title')
            if title_elem:
                job.title = self.clean_text(title_elem.get_text())

            company_elem = soup.select_one('.company-name, .corp-name, .js-corpName')
            if company_elem:
                job.company = self.clean_text(company_elem.get_text())

            # マイナビ页面结构复杂，尝试多种选择器
            all_text = soup.get_text()

            job.salary = self.extract_salary(all_text)
            job.location = self.extract_location(all_text)

            desc_elem = soup.select_one('.job-description, .work-content, .js-desc')
            if desc_elem:
                job.description = self.clean_text(desc_elem.get_text())

            if job.is_valid():
                return job
            else:
                logger.warning(f"マイナビ転職: 职位信息不完整 - {url}")
                return None

        except Exception as e:
            logger.error(f"マイナビ転職 解析错误: {e}")
            return None


# 解析器注册表
PARSERS = {
    "indeed_jp": IndeedJapanParser(),
    "wantedly": WantedlyParser(),
    "rikunabi": RikunabiParser(),
    "doda": DodaParser(),
    "mynavi": MynaviParser(),
}


def get_parser(site_name: str) -> Optional[BaseParser]:
    """获取指定站点的解析器"""
    return PARSERS.get(site_name)
