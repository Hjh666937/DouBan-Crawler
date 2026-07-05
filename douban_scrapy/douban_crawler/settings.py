# Scrapy settings for douban_crawler project

import os

BOT_NAME = "douban_crawler"

SPIDER_MODULES = ["douban_crawler.spiders"]
NEWSPIDER_MODULE = "douban_crawler.spiders"

ADDONS = {}

ROBOTSTXT_OBEY = False

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

DEFAULT_REQUEST_HEADERS = {
    "Accept": "application/json, text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Referer": "https://movie.douban.com/",
    "Connection": "keep-alive",
}

# ========== 保守限速（降低 403 概率）==========
CONCURRENT_REQUESTS = 1
CONCURRENT_REQUESTS_PER_DOMAIN = 1
DOWNLOAD_DELAY = 4
RANDOMIZE_DOWNLOAD_DELAY = True          # 实际间隔约 2~6 秒
DOWNLOAD_TIMEOUT = 30

AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 5
AUTOTHROTTLE_MAX_DELAY = 30
AUTOTHROTTLE_TARGET_CONCURRENCY = 0.5

RETRY_ENABLED = True
RETRY_TIMES = 5
RETRY_HTTP_CODES = [500, 502, 503, 504, 408, 429, 403]

ITEM_PIPELINES = {
    "douban_crawler.pipelines.CsvExportPipeline": 300,
}

CSV_OUTPUT_DIR = "output"
FEED_EXPORT_ENCODING = "utf-8"
LOG_LEVEL = "INFO"


def _load_douban_cookie() -> str:
    from douban_crawler.cookie_loader import load_douban_cookie
    return load_douban_cookie()


DOUBAN_COOKIE = _load_douban_cookie()

if DOUBAN_COOKIE:
    DEFAULT_REQUEST_HEADERS["Cookie"] = DOUBAN_COOKIE
