import logging
import os

from itemadapter import ItemAdapter

from douban_crawler.csv_store import (
    MOVIE_FIELDS,
    REVIEW_FIELDS,
    load_existing_movies,
    load_existing_reviews,
    review_dedup_key,
    write_movies_csv,
    write_reviews_csv,
)
from douban_crawler.items import MovieItem, ReviewItem


class CsvExportPipeline:
    """将电影信息与短评分别写入 CSV 文件（增量合并，不覆盖历史数据）。"""

    def __init__(self, output_dir):
        self.output_dir = output_dir
        self.movies_buffer = {}
        self.reviews_buffer = []
        self.review_keys = set()
        self._existing_movie_count = 0
        self._existing_review_count = 0

    @classmethod
    def from_crawler(cls, crawler):
        output_dir = crawler.settings.get("CSV_OUTPUT_DIR", "output")
        return cls(output_dir)

    def open_spider(self, spider):
        os.makedirs(self.output_dir, exist_ok=True)
        self.movies_buffer = load_existing_movies(self.output_dir)
        self.reviews_buffer, self.review_keys = load_existing_reviews(self.output_dir)
        self._existing_movie_count = len(self.movies_buffer)
        self._existing_review_count = len(self.reviews_buffer)
        if self._existing_movie_count or self._existing_review_count:
            logging.getLogger(__name__).info(
                "已加载历史 CSV：%d 部电影，%d 条短评（新数据将追加合并）",
                self._existing_movie_count,
                self._existing_review_count,
            )

    def close_spider(self, spider):
        self._flush_movies()
        self._flush_reviews()
        new_movies = len(self.movies_buffer) - self._existing_movie_count
        new_reviews = len(self.reviews_buffer) - self._existing_review_count
        logging.getLogger(__name__).info(
            "CSV 已保存至 %s：共 %d 部电影（本次新增 %d），%d 条短评（本次新增 %d）",
            self.output_dir,
            len(self.movies_buffer),
            max(new_movies, 0),
            len(self.reviews_buffer),
            max(new_reviews, 0),
        )

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        if isinstance(item, MovieItem):
            movie_id = adapter.get("movie_id")
            if not movie_id:
                return item
            movie_id = str(movie_id).strip()
            if movie_id not in self.movies_buffer:
                self.movies_buffer[movie_id] = {
                    field: "" for field in MOVIE_FIELDS
                }
            for key, value in adapter.items():
                if value is not None and value != "":
                    self.movies_buffer[movie_id][key] = value
            self._flush_movies()
        elif isinstance(item, ReviewItem):
            row = {field: adapter.get(field, "") or "" for field in REVIEW_FIELDS}
            key = review_dedup_key(row)
            if key in self.review_keys:
                return item
            self.review_keys.add(key)
            self.reviews_buffer.append(row)
            self._flush_reviews()
        return item

    def _flush_movies(self):
        write_movies_csv(self.output_dir, self.movies_buffer)

    def _flush_reviews(self):
        write_reviews_csv(self.output_dir, self.reviews_buffer)
