# -*- coding: utf-8 -*-
"""
将 Scrapy 爬取的 CSV 导入 SQL Server。

用法（在项目根目录执行）：
    python database/import_csv.py
    python database/import_csv.py --csv-dir output
"""

import argparse
import os
import sys

# 将项目根目录加入路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from database.db_manager import Database


def main():
    parser = argparse.ArgumentParser(description="导入豆瓣 CSV 到 SQL Server")
    parser.add_argument(
        "--csv-dir",
        default=os.path.join(os.path.dirname(os.path.dirname(__file__)), "output"),
        help="CSV 文件目录，默认 output/",
    )
    parser.add_argument(
        "--config",
        default=None,
        help="数据库配置文件路径，默认 database/db_config.json",
    )
    args = parser.parse_args()

    movies_csv = os.path.join(args.csv_dir, "movies.csv")
    reviews_csv = os.path.join(args.csv_dir, "reviews.csv")

    if not os.path.isfile(movies_csv):
        print(f"[错误] 未找到 {movies_csv}，请先运行爬虫")
        sys.exit(1)

    db = Database(config_path=args.config)
    if not db.connect():
        sys.exit(1)
    if not db.ensure_tables():
        sys.exit(1)

    print(f"\n[1/2] 导入电影: {movies_csv}")
    movie_result = db.import_movies_csv(movies_csv)
    print(f"      结果: {movie_result}")

    if os.path.isfile(reviews_csv):
        print(f"\n[2/2] 导入短评: {reviews_csv}")
        review_result = db.import_reviews_csv(reviews_csv)
        print(f"      结果: {review_result}")
    else:
        print(f"\n[2/2] 跳过短评，未找到 {reviews_csv}")

    db.disconnect()
    print("\n导入完成！")


if __name__ == "__main__":
    main()
