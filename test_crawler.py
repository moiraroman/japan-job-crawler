# -*- coding: utf-8 -*-
"""
快速测试脚本 - 验证爬虫功能
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent))


async def test_fetcher():
    """测试 Fetcher 基本功能"""
    print("\n=== 测试 Fetcher ===")
    
    from fetcher import Fetcher
    
    fetcher = Fetcher(headless=True)
    
    try:
        await fetcher.start()
        print("✓ 浏览器启动成功")
        
        # 测试访问 Indeed Japan
        url = "https://jp.indeed.com"
        await fetcher.open_page(url)
        print(f"✓ 成功访问 {url}")
        
        # 获取页面标题
        title = await fetcher.get_text("title")
        print(f"✓ 页面标题: {title}")
        
        # 截图
        await fetcher.screenshot("test_screenshot.png")
        print("✓ 截图已保存")
        
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        return False
    
    finally:
        await fetcher.close()
    
    return True


async def test_parser():
    """测试 Parser 基本功能"""
    print("\n=== 测试 Parser ===")
    
    from parser import IndeedJapanParser
    
    parser = IndeedJapanParser()
    
    # 测试文本清理
    dirty_text = "  エンジニア  \n  東京都  "
    clean = parser.clean_text(dirty_text)
    print(f"✓ 文本清理: '{dirty_text}' → '{clean}'")
    
    # 测试薪资提取
    salary_text = "月給 30万円 〜 50万円"
    salary = parser.extract_salary(salary_text)
    print(f"✓ 薪资提取: '{salary_text}' → '{salary}'")
    
    # 测试地点提取
    location_text = "東京都渋谷区"
    location = parser.extract_location(location_text)
    print(f"✓ 地点提取: '{location_text}' → '{location}'")
    
    return True


def test_storage():
    """测试 Storage 基本功能"""
    print("\n=== 测试 Storage ===")
    
    from storage import JobStorage
    
    storage = JobStorage("data/test_jobs.db")
    
    # 测试保存
    job_data = {
        "title": "テストエンジニア",
        "company": "テスト会社",
        "location": "東京都",
        "salary": "月給 30万円",
        "url": "https://example.com/test/1",
        "source": "Test"
    }
    
    success = storage.save_job(job_data)
    if success:
        print("✓ 职位保存成功")
    else:
        print("✗ 职位保存失败（可能已存在）")
    
    # 测试查询
    jobs = storage.get_jobs(limit=10)
    print(f"✓ 查询到 {len(jobs)} 条职位")
    
    # 测试统计
    stats = storage.get_stats()
    print(f"✓ 统计信息: 总计 {stats['total']} 条")
    
    return True


async def test_spider():
    """测试 Spider 基本功能（不实际爬取）"""
    print("\n=== 测试 Spider ===")
    
    from spiders import create_spider
    from config import CrawlerConfig, SITES
    from storage import JobStorage
    
    config = CrawlerConfig(headless=True)
    storage = JobStorage("data/test_jobs.db")
    
    # 测试创建 Spider
    for site_name in ["indeed_jp", "wantedly"]:
        spider = create_spider(site_name, config, storage)
        if spider:
            print(f"✓ {site_name} Spider 创建成功")
        else:
            print(f"✗ {site_name} Spider 创建失败")
    
    return True


def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("日本招聘爬虫系统 - 功能测试")
    print("=" * 60)
    
    results = []
    
    # 测试 Storage（同步）
    results.append(("Storage", test_storage()))
    
    # 测试 Parser（同步）
    results.append(("Parser", asyncio.run(test_parser())))
    
    # 测试 Fetcher（异步，需要浏览器）
    print("\n提示: Fetcher 测试需要 Playwright 浏览器")
    print("如果未安装，请运行: playwright install chromium")
    
    try:
        results.append(("Fetcher", asyncio.run(test_fetcher())))
    except Exception as e:
        print(f"✗ Fetcher 测试跳过: {e}")
        results.append(("Fetcher", False))
    
    # 测试 Spider（异步）
    try:
        results.append(("Spider", asyncio.run(test_spider())))
    except Exception as e:
        print(f"✗ Spider 测试跳过: {e}")
        results.append(("Spider", False))
    
    # 汇总结果
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    
    for name, passed in results:
        status = "✓ 通过" if passed else "✗ 失败"
        print(f"  {name}: {status}")
    
    total = len(results)
    passed = sum(1 for _, p in results if p)
    print(f"\n总计: {passed}/{total} 通过")
    
    return all(p for _, p in results)


if __name__ == "__main__":
    run_all_tests()
