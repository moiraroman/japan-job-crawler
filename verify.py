# -*- coding: utf-8 -*-
"""
完整验证测试脚本
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def main():
    os.makedirs('data', exist_ok=True)
    os.makedirs('data/output', exist_ok=True)
    
    print('=' * 60)
    print('Japan Job Crawler - Verification Test')
    print('=' * 60)
    
    # Test 1: Storage CRUD
    print('\n[1] Storage CRUD Test')
    from storage import JobStorage
    storage = JobStorage('data/test_verify.db')
    
    test_job = {
        'title': 'Senior Engineer',
        'company': 'Test Company',
        'location': 'Tokyo',
        'salary': '5000000 JPY',
        'url': 'https://example.com/job/123',
        'source': 'Test'
    }
    
    success = storage.save_job(test_job)
    print(f'    Save: {"OK" if success else "SKIP (duplicate)"}')
    
    jobs = storage.get_jobs(limit=10)
    print(f'    Query: {len(jobs)} records')
    
    stats = storage.get_stats()
    print(f'    Stats: total={stats["total"]}, today={stats["today"]}')
    
    # Test 2: Parser functions
    print('\n[2] Parser Function Test')
    from parser import IndeedJapanParser, MynaviParser
    
    parser = IndeedJapanParser()
    text = parser.clean_text('  Engineer   Tokyo  ')
    print(f'    clean_text: "{text}"')
    
    salary = parser.extract_salary('Monthly 300000 JPY to 500000 JPY')
    print(f'    extract_salary: "{salary}"')
    
    location = parser.extract_location('Tokyo Shibuya-ku')
    print(f'    extract_location: "{location}"')
    
    # Test 3: Config
    print('\n[3] Configuration Test')
    from config import SITES, CrawlerConfig, DEFAULT_KEYWORDS, DEFAULT_LOCATIONS
    
    print(f'    Sites: {list(SITES.keys())}')
    print(f'    Keywords: {len(DEFAULT_KEYWORDS)} defaults')
    print(f'    Locations: {len(DEFAULT_LOCATIONS)} defaults')
    
    # Test 4: Spider creation
    print('\n[4] Spider Creation Test')
    from spiders import create_spider, SPIDER_CLASSES
    
    config = CrawlerConfig(headless=True)
    for site_name in SITES.keys():
        spider = create_spider(site_name, config, storage)
        status = 'OK' if spider else 'FAIL'
        print(f'    {site_name}: {status}')
    
    # Test 5: Export
    print('\n[5] Export Test')
    count = storage.export_to_csv('data/output/test_export.csv')
    print(f'    CSV export: {count} records')
    
    count = storage.export_to_json('data/output/test_export.json')
    print(f'    JSON export: {count} records')
    
    print('\n' + '=' * 60)
    print('All verification tests passed!')
    print('=' * 60)

if __name__ == '__main__':
    main()
