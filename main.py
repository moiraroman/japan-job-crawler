# -*- coding: utf-8 -*-
"""
日本招聘信息爬虫系统 - 主入口
"""
import asyncio
import argparse
import logging
from datetime import datetime
import sys

from config import CrawlerConfig, SITES, DEFAULT_KEYWORDS, DEFAULT_LOCATIONS
from scheduler import Scheduler
from storage import JobStorage

# 配置日志
def setup_logging(verbose: bool = False):
    """配置日志输出"""
    level = logging.DEBUG if verbose else logging.INFO
    
    # 创建格式化器
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(level)
    
    # 文件处理器
    file_handler = logging.FileHandler(
        'logs/crawler.log',
        encoding='utf-8',
        mode='a'
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)
    
    # 配置根日志器
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    
    # 降低第三方库日志级别
    logging.getLogger('playwright').setLevel(logging.WARNING)


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='日本招聘信息爬虫系统',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  # 爬取所有站点，默认关键词
  python main.py
  
  # 只爬取 Indeed 和 Wantedly
  python main.py --sites indeed_jp wantedly
  
  # 自定义关键词和地点
  python main.py --keywords "Python エンジニア" "機械学習" --locations "東京都" "大阪府"
  
  # 导出数据到 CSV
  python main.py --export output.csv
  
  # 查看统计信息
  python main.py --stats
        '''
    )
    
    parser.add_argument(
        '--sites',
        nargs='+',
        choices=list(SITES.keys()),
        default=list(SITES.keys()),
        help='要爬取的站点（默认全部）'
    )
    
    parser.add_argument(
        '--keywords',
        nargs='+',
        default=DEFAULT_KEYWORDS,
        help='搜索关键词'
    )
    
    parser.add_argument(
        '--locations',
        nargs='+',
        default=DEFAULT_LOCATIONS,
        help='搜索地点'
    )
    
    parser.add_argument(
        '--max-pages',
        type=int,
        default=3,
        help='每个关键词每站最多爬取页数（默认 3）'
    )
    
    parser.add_argument(
        '--headless',
        action='store_true',
        default=True,
        help='无头模式运行浏览器（默认开启）'
    )
    
    parser.add_argument(
        '--headed',
        action='store_true',
        help='有头模式运行浏览器（用于调试）'
    )
    
    parser.add_argument(
        '--export',
        type=str,
        help='导出数据到 CSV 文件'
    )
    
    parser.add_argument(
        '--export-json',
        type=str,
        help='导出数据到 JSON 文件'
    )
    
    parser.add_argument(
        '--stats',
        action='store_true',
        help='显示数据库统计信息'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='试运行模式，不保存数据'
    )
    
    parser.add_argument(
        '--schedule',
        type=int,
        help='定时执行模式，指定执行间隔（小时）'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='详细输出模式'
    )
    
    args = parser.parse_args()
    
    # 配置日志
    setup_logging(verbose=args.verbose)
    
    # 创建日志目录
    import os
    os.makedirs('logs', exist_ok=True)
    os.makedirs('data', exist_ok=True)
    
    # 只查看统计
    if args.stats:
        storage = JobStorage()
        stats = storage.get_stats()
        print("\n=== 数据库统计 ===")
        print(f"总职位数: {stats['total']}")
        print(f"今日新增: {stats['today']}")
        print("\n按站点统计:")
        for site, count in stats['by_source'].items():
            print(f"  {site}: {count}")
        return
    
    # 导出数据
    if args.export:
        storage = JobStorage()
        count = storage.export_to_csv(args.export)
        print(f"已导出 {count} 条记录到 {args.export}")
        return
    
    if args.export_json:
        storage = JobStorage()
        count = storage.export_to_json(args.export_json)
        print(f"已导出 {count} 条记录到 {args.export_json}")
        return
    
    # 创建配置
    config = CrawlerConfig(headless=not args.headed)
    
    # 创建调度器
    scheduler = Scheduler(
        config=config,
        keywords=args.keywords,
        locations=args.locations,
        sites=args.sites
    )
    
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║           日本招聘信息爬虫系统 v1.0                          ║
╠══════════════════════════════════════════════════════════════╣
║  站点: {', '.join(args.sites):<50} ║
║  关键词: {len(args.keywords)} 个{'':>43} ║
║  地点: {len(args.locations)} 个{'':>46} ║
║  最大页数: {args.max_pages} 页{'':>42} ║
║  模式: {'试运行' if args.dry_run else '正常'}{'':>48} ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    try:
        if args.schedule:
            # 定时执行模式
            await scheduler.run_with_schedule(
                interval_hours=args.schedule,
                max_pages=args.max_pages
            )
        else:
            # 单次执行
            stats = await scheduler.run(
                max_pages=args.max_pages,
                dry_run=args.dry_run
            )
            
            print(f"""
╔══════════════════════════════════════════════════════════════╗
║                      爬取完成                                ║
╠══════════════════════════════════════════════════════════════╣
║  总保存数: {stats['total_saved']:<48} ║
║  耗时: {stats['duration_seconds']:.1f} 秒{'':>48} ║
╚══════════════════════════════════════════════════════════════╝
            """)
            
            # 显示各站点统计
            for site, site_stats in stats['by_site'].items():
                print(f"  {site}: 保存 {site_stats.get('saved', 0)} 条")
                if site_stats.get('errors'):
                    for error in site_stats['errors']:
                        print(f"    错误: {error}")
    
    except KeyboardInterrupt:
        print("\n用户中断，正在退出...")
        scheduler.stop()
    
    except Exception as e:
        logging.error(f"执行异常: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
