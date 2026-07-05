"""
豆瓣电影爬虫启动脚本 —— 在 PyCharm 里右键此文件 → Run 即可运行。

修改下方 TARGET_COUNT 控制爬取数量。
"""
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings

from douban_crawler.spiders.douban_movie import DoubanMovieSpider

# ========== 在这里改爬取数量 ==========
TARGET_COUNT = 10
# =====================================


def main():
    settings = get_project_settings()
    process = CrawlerProcess(settings)
    process.crawl(DoubanMovieSpider, target_count=TARGET_COUNT)
    process.start()
    print(f"\n完成！请查看 output/movies.csv 和 output/reviews.csv（共 {TARGET_COUNT} 部）")


if __name__ == "__main__":
    main()
