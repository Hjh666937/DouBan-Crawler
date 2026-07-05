import re
from urllib.parse import quote

import scrapy

from douban_crawler.cookie_loader import load_douban_cookie
from douban_crawler.csv_store import load_existing_movies
from douban_crawler.items import MovieItem, ReviewItem


GENRES = [
    "剧情", "喜剧", "动作", "爱情", "科幻", "动画", "悬疑", "惊悚", "恐怖",
    "纪录片", "短片", "音乐", "歌舞", "家庭", "儿童", "传记", "历史", "战争",
    "西部", "奇幻", "冒险", "犯罪", "武侠", "情色", "灾难", "运动", "古装",
    "黑色电影",
]

SEARCH_API = (
    "https://movie.douban.com/j/new_search_subjects"
    "?sort=U&range=0,10&tags&start={start}&genres={genre}&countries=&year_range=,2026"
)
MOVIE_API = "https://m.douban.com/rexxar/api/v2/movie/{movie_id}"
CREDITS_API = "https://m.douban.com/rexxar/api/v2/movie/{movie_id}/credits"
COMMENTS_API = (
    "https://m.douban.com/rexxar/api/v2/movie/{movie_id}/interests"
    "?count=10&start=0&type=comment&order_by=hot"
)

MOBILE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
    ),
    "Referer": "https://m.douban.com/movie/",
}


class DoubanMovieSpider(scrapy.Spider):
    name = "douban_movie"
    allowed_domains = ["movie.douban.com", "m.douban.com"]

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 4,
        "RANDOMIZE_DOWNLOAD_DELAY": True,
    }

    def __init__(self, target_count=10000, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.target_count = int(target_count)
        self.collected_ids = set()
        self._existing_count = 0

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super().from_crawler(crawler, *args, **kwargs)
        output_dir = crawler.settings.get("CSV_OUTPUT_DIR", "output")
        existing = load_existing_movies(output_dir)
        spider.collected_ids.update(existing.keys())
        spider._existing_count = len(existing)
        spider._log_cookie_status()
        if spider._existing_count:
            need = max(spider.target_count - spider._existing_count, 0)
            spider.logger.info(
                "CSV 中已有 %d 部电影，目标总数 %d，本次还需采集 %d 部",
                spider._existing_count,
                spider.target_count,
                need,
            )
        return spider

    def _log_cookie_status(self):
        cookie = load_douban_cookie()
        if cookie:
            self.logger.info("已加载豆瓣 Cookie（每次请求自动读取 cookie.txt）")
        else:
            self.logger.warning(
                "未配置 Cookie，长时间爬取可能触发 403。"
                "请将 Cookie 粘贴到 douban_crawler/cookie.txt"
            )

    def closed(self, reason):
        self.logger.info("爬虫已停止，原因: %s", reason)

    async def start(self):
        yield self._search_request(GENRES[0], 0)

    def _build_headers(self, mobile=False):
        headers = dict(MOBILE_HEADERS if mobile else {})
        if not mobile:
            headers.setdefault(
                "User-Agent",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            )
            headers.setdefault("Referer", "https://movie.douban.com/")
        headers.setdefault("Accept", "application/json, text/plain, */*")
        headers.setdefault("Accept-Language", "zh-CN,zh;q=0.9,en;q=0.8")
        cookie = load_douban_cookie()
        if cookie:
            headers["Cookie"] = cookie
        return headers

    def _search_request(self, genre, start):
        return scrapy.Request(
            SEARCH_API.format(start=start, genre=quote(genre)),
            callback=self.parse_search,
            headers=self._build_headers(mobile=False),
            meta={"genre": genre, "start": start},
            dont_filter=True,
        )

    def _mobile_request(self, url, callback, **meta):
        return scrapy.Request(
            url,
            callback=callback,
            headers=self._build_headers(mobile=True),
            meta=meta,
        )

    def parse_search(self, response):
        genre = response.meta["genre"]
        start = response.meta["start"]

        try:
            data = response.json()
        except Exception:
            self.logger.warning("搜索 API 解析失败: %s", response.url)
            yield from self._next_genre(genre)
            return

        for item in data.get("data", []):
            if len(self.collected_ids) >= self.target_count:
                break
            movie_id = str(item.get("id", ""))
            if movie_id and movie_id not in self.collected_ids:
                self.collected_ids.add(movie_id)
                yield self._mobile_request(
                    MOVIE_API.format(movie_id=movie_id),
                    self.parse_movie,
                    movie_id=movie_id,
                )

        self.logger.info(
            "分类 [%s] start=%d，已收集 %d/%d 部电影 ID（含历史 %d 部）",
            genre, start, len(self.collected_ids), self.target_count, self._existing_count,
        )

        if len(self.collected_ids) >= self.target_count:
            return

        if data.get("data"):
            yield self._search_request(genre, start + 20)
        else:
            yield from self._next_genre(genre)

    def _next_genre(self, genre):
        if len(self.collected_ids) >= self.target_count:
            return
        try:
            idx = GENRES.index(genre) + 1
        except ValueError:
            idx = 0
        if idx < len(GENRES):
            yield self._search_request(GENRES[idx], 0)
        else:
            self.logger.info("所有分类已遍历完毕，共收集 %d 部电影 ID", len(self.collected_ids))

    def parse_movie(self, response):
        movie_id = response.meta["movie_id"]

        try:
            data = response.json()
        except Exception:
            self.logger.warning("电影 API 解析失败: %s", response.url)
            return

        rating = data.get("rating") or {}
        poster = data.get("cover_url") or ""
        if not poster and data.get("pic"):
            poster = data["pic"].get("large") or data["pic"].get("normal") or ""

        item = MovieItem(
            movie_id=movie_id,
            name=data.get("title", ""),
            poster=poster,
            summary=self._clean_text(data.get("intro", "")),
            director=self._join_names(data.get("directors", [])),
            screenwriter="",
            actors=self._join_names(data.get("actors", [])),
            genre=" / ".join(data.get("genres", [])),
            country=" / ".join(data.get("countries", [])),
            language=" / ".join(data.get("languages", [])),
            release_date=" / ".join(data.get("pubdate", [])),
            runtime=" / ".join(data.get("durations", [])),
            imdb_link="",
            aka=" / ".join(data.get("aka", [])),
            rating=str(rating.get("value", "")),
            rating_count=str(rating.get("count", "")),
            short_review_count=str(data.get("comment_count", "")),
        )
        yield item

        yield self._mobile_request(
            CREDITS_API.format(movie_id=movie_id),
            self.parse_credits,
            movie_id=movie_id,
        )
        yield self._mobile_request(
            COMMENTS_API.format(movie_id=movie_id),
            self.parse_comments,
            movie_id=movie_id,
            movie_name=item["name"],
        )

    def parse_credits(self, response):
        movie_id = response.meta["movie_id"]
        try:
            data = response.json()
        except Exception:
            return

        writers = [
            person["name"]
            for person in data.get("items", [])
            if person.get("category") == "编剧" and person.get("name")
        ]
        if writers:
            yield MovieItem(
                movie_id=movie_id,
                screenwriter=" / ".join(dict.fromkeys(writers)),
            )

    def parse_comments(self, response):
        movie_id = response.meta["movie_id"]
        movie_name = response.meta["movie_name"]

        try:
            data = response.json()
        except Exception:
            self.logger.warning("短评 API 解析失败: %s", response.url)
            return

        total = data.get("total")
        if total is not None:
            yield MovieItem(
                movie_id=movie_id,
                short_review_count=str(total),
            )

        for interest in data.get("interests", [])[:10]:
            user = interest.get("user") or {}
            yield ReviewItem(
                movie_id=movie_id,
                movie_name=movie_name,
                reviewer=user.get("name", ""),
                review_time=interest.get("create_time", ""),
                content=self._clean_text(interest.get("comment", "")),
                votes=str(interest.get("vote_count", 0)),
            )

    @staticmethod
    def _join_names(people):
        return " / ".join(
            person.get("name", "")
            for person in people
            if person.get("name")
        )

    @staticmethod
    def _clean_text(text):
        if not text:
            return ""
        return re.sub(r"\s+", " ", str(text)).strip()
