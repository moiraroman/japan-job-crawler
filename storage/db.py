# -*- coding: utf-8 -*-
"""
Storage 模块 - 数据存储层
支持 SQLite 数据库和 CSV 导出
"""
import sqlite3
import json
import csv
import os
from typing import List, Optional, Dict
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class JobStorage:
    """
    职位数据存储
    
    功能：
    1. SQLite 数据库存储
    2. 去重（基于 URL）
    3. CSV 导出
    4. 查询和统计
    """
    
    def __init__(self, db_path: str = "data/jobs.db"):
        self.db_path = db_path
        self._ensure_db_dir()
        self._init_db()
    
    def _ensure_db_dir(self):
        """确保数据库目录存在"""
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
    
    def _init_db(self):
        """初始化数据库表"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 创建职位表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    company TEXT NOT NULL,
                    location TEXT,
                    salary TEXT,
                    employment_type TEXT,
                    description TEXT,
                    requirements TEXT,
                    url TEXT UNIQUE NOT NULL,
                    source TEXT,
                    posted_date TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 创建索引
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_jobs_source ON jobs(source)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_jobs_company ON jobs(company)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_jobs_created ON jobs(created_at)
            ''')
            
            conn.commit()
            logger.info(f"数据库初始化完成: {self.db_path}")
    
    def save_job(self, job_data: Dict) -> bool:
        """
        保存职位数据
        
        Args:
            job_data: 职位信息字典
        
        Returns:
            是否成功保存（重复返回 False）
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT INTO jobs 
                    (title, company, location, salary, employment_type, description, requirements, url, source, posted_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    job_data.get('title', ''),
                    job_data.get('company', ''),
                    job_data.get('location', ''),
                    job_data.get('salary', ''),
                    job_data.get('employment_type', ''),
                    job_data.get('description', ''),
                    job_data.get('requirements', ''),
                    job_data.get('url', ''),
                    job_data.get('source', ''),
                    job_data.get('posted_date', '')
                ))
                
                conn.commit()
                logger.info(f"保存成功: {job_data.get('title', '')} - {job_data.get('company', '')}")
                return True
                
        except sqlite3.IntegrityError:
            # URL 重复
            logger.debug(f"职位已存在，跳过: {job_data.get('url', '')}")
            return False
        except Exception as e:
            logger.error(f"保存职位失败: {e}")
            return False
    
    def save_jobs_batch(self, jobs: List[Dict]) -> int:
        """
        批量保存职位
        
        Returns:
            成功保存的数量
        """
        saved_count = 0
        for job in jobs:
            if self.save_job(job):
                saved_count += 1
        return saved_count
    
    def get_jobs(
        self,
        source: Optional[str] = None,
        keyword: Optional[str] = None,
        company: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict]:
        """
        查询职位数据
        """
        query = "SELECT * FROM jobs WHERE 1=1"
        params = []
        
        if source:
            query += " AND source = ?"
            params.append(source)
        
        if keyword:
            query += " AND (title LIKE ? OR company LIKE ? OR description LIKE ?)"
            params.extend([f"%{keyword}%", f"%{keyword}%", f"%{keyword}%"])
        
        if company:
            query += " AND company LIKE ?"
            params.append(f"%{company}%")
        
        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(query, params)
            
            return [dict(row) for row in cursor.fetchall()]
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 总数
            cursor.execute("SELECT COUNT(*) FROM jobs")
            total = cursor.fetchone()[0]
            
            # 按来源统计
            cursor.execute("SELECT source, COUNT(*) FROM jobs GROUP BY source")
            by_source = dict(cursor.fetchall())
            
            # 今日新增
            cursor.execute("""
                SELECT COUNT(*) FROM jobs 
                WHERE date(created_at) = date('now')
            """)
            today = cursor.fetchone()[0]
            
            return {
                "total": total,
                "by_source": by_source,
                "today": today
            }
    
    def search(self, keyword: str, limit: int = 20) -> List[Dict]:
        """全文搜索职位"""
        query = """
            SELECT * FROM jobs 
            WHERE title LIKE ? OR company LIKE ? OR location LIKE ? 
                OR description LIKE ? OR requirements LIKE ?
            ORDER BY created_at DESC LIMIT ?
        """
        like_kw = f"%{keyword}%"
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(query, [like_kw, like_kw, like_kw, like_kw, like_kw, limit])
            return [dict(row) for row in cursor.fetchall()]

    def export_to_csv(
        self,
        output_path: str,
        source: Optional[str] = None,
        include_description: bool = True
    ) -> int:
        """
        导出到 CSV 文件
        
        Args:
            output_path: 输出文件路径
            source: 筛选来源（可选）
            include_description: 是否包含职位描述
        
        Returns:
            导出的记录数
        """
        jobs = self.get_jobs(source=source, limit=10000)
        
        if not jobs:
            logger.warning("没有数据可导出")
            return 0
        
        # 确保输出目录存在
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        
        # 选择要导出的字段
        if include_description:
            fieldnames = ['title', 'company', 'location', 'salary', 'employment_type', 
                         'description', 'url', 'source', 'posted_date']
        else:
            fieldnames = ['title', 'company', 'location', 'salary', 'employment_type',
                         'url', 'source', 'posted_date']
        
        with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(jobs)
        
        logger.info(f"导出完成: {output_path} ({len(jobs)} 条记录)")
        return len(jobs)
    
    def export_to_json(self, output_path: str, source: Optional[str] = None) -> int:
        """导出到 JSON 文件"""
        jobs = self.get_jobs(source=source, limit=10000)
        
        if not jobs:
            logger.warning("没有数据可导出")
            return 0
        
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(jobs, f, ensure_ascii=False, indent=2)
        
        logger.info(f"导出完成: {output_path} ({len(jobs)} 条记录)")
        return len(jobs)
    
    def clear_old_data(self, days: int = 30):
        """清理旧数据"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(f"""
                DELETE FROM jobs 
                WHERE date(created_at) < date('now', '-{days} days')
            """)
            deleted = cursor.rowcount
            conn.commit()
            logger.info(f"已清理 {deleted} 条旧数据")
            return deleted


class SearchHistory:
    """
    搜索历史记录
    用于去重和避免重复爬取
    """
    
    def __init__(self, db_path: str = "data/jobs.db"):
        self.db_path = db_path
        self._init_table()
    
    def _init_table(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS search_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    site TEXT NOT NULL,
                    keyword TEXT NOT NULL,
                    location TEXT,
                    page INTEGER DEFAULT 1,
                    searched_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(site, keyword, location, page)
                )
            ''')
            conn.commit()
    
    def is_searched(self, site: str, keyword: str, location: str = "", page: int = 1) -> bool:
        """检查是否已搜索过"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT 1 FROM search_history 
                WHERE site = ? AND keyword = ? AND location = ? AND page = ?
            ''', (site, keyword, location, page))
            return cursor.fetchone() is not None
    
    def mark_searched(self, site: str, keyword: str, location: str = "", page: int = 1):
        """标记为已搜索"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR IGNORE INTO search_history (site, keyword, location, page)
                VALUES (?, ?, ?, ?)
            ''', (site, keyword, location, page))
            conn.commit()
    
    def clear_history(self):
        """清空搜索历史"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM search_history")
            conn.commit()
            logger.info("搜索历史已清空")
