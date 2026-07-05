# -*- coding: utf-8 -*-
"""
SQL Server 数据库连接与 CSV 导入模块。
参考 douban_crawler/database/database.py 实现，适配 Scrapy 导出的 CSV 字段。
"""

import csv
import json
import os
from datetime import datetime
from typing import List, Optional

import pymssql

from .models import Movie, ShortComment


class Database:
    """SQL Server 数据库操作类"""

    def __init__(self, config_path: Optional[str] = None):
        if config_path is None:
            config_path = os.path.join(os.path.dirname(__file__), "db_config.json")
        self.config = self._load_config(config_path)
        self.conn = None
        self.cursor = None

    def _load_config(self, config_path: str) -> dict:
        default_config = {
            "server": "localhost",
            "port": 1433,
            "database": "DoubanMovies",
            "user": "sa",
            "password": "123456",
            "use_windows_auth": False,
        }
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                return {**default_config, **json.load(f)}
        return default_config

    def _connect_kwargs(self, database: str) -> dict:
        kwargs = {
            "server": self.config["server"],
            "port": self.config["port"],
            "database": database,
            "charset": "utf8",
        }
        if not self.config.get("use_windows_auth", False):
            kwargs["user"] = self.config["user"]
            kwargs["password"] = self.config["password"]
        return kwargs

    def connect(self, retry_count: int = 0) -> bool:
        try:
            self.conn = pymssql.connect(**self._connect_kwargs(self.config["database"]))
            self.cursor = self.conn.cursor(as_dict=True)
            print("[数据库] 连接成功")
            return True
        except Exception as exc:
            print(f"[数据库] 连接失败: {exc}")
            if retry_count < 1 and self._create_database():
                return self.connect(retry_count + 1)
            return False

    def _create_database(self) -> bool:
        try:
            master_conn = pymssql.connect(**self._connect_kwargs("master"))
            master_conn.autocommit(True)
            cursor = master_conn.cursor()
            db_name = self.config["database"]
            cursor.execute(
                f"""
                IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = %s)
                BEGIN
                    CREATE DATABASE [{db_name}]
                END
                """,
                (db_name,),
            )
            cursor.close()
            master_conn.close()
            print(f"[数据库] 数据库 '{db_name}' 已就绪")
            return True
        except Exception as exc:
            print(f"[数据库] 创建数据库失败: {exc}")
            return False

    def disconnect(self):
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
            print("[数据库] 连接已关闭")

    def tables_ready(self) -> bool:
        try:
            self.cursor.execute("""
                SELECT COUNT(*) AS cnt FROM INFORMATION_SCHEMA.TABLES
                WHERE TABLE_NAME IN ('Movies', 'ShortComments')
            """)
            row = self.cursor.fetchone()
            return row and row.get("cnt", 0) >= 2
        except Exception:
            return False

    def ensure_tables(self) -> bool:
        """表已存在则跳过建表，避免重复执行脚本报错。"""
        if not self.conn and not self.connect():
            return False
        if self.tables_ready():
            print("[数据库] 数据表已存在，跳过建表")
            return True
        return self.init_database()

    def init_database(self) -> bool:
        if not self.conn and not self.connect():
            return False

        sql_path = os.path.join(os.path.dirname(__file__), "create_tables.sql")
        try:
            with open(sql_path, "r", encoding="utf-8") as f:
                script = f.read()

            for batch in script.split("GO"):
                batch = batch.strip()
                if not batch or batch.startswith("--"):
                    continue
                self.cursor.execute(batch)
            self.conn.commit()
            print("[数据库] 表结构初始化完成")
            return True
        except Exception as exc:
            print(f"[数据库] 初始化表结构失败: {exc}")
            self.conn.rollback()
            if self.tables_ready():
                print("[数据库] 表已存在，继续导入")
                return True
            return False

    @staticmethod
    def _convert(value, target_type):
        if value is None or str(value).strip() == "":
            if target_type is float:
                return 0.0
            if target_type is int:
                return 0
            return ""
        value = str(value).strip()
        try:
            if target_type is float:
                return float(value)
            if target_type is int:
                return int(float(value))
        except ValueError:
            return 0.0 if target_type is float else 0
        return value

    def batch_save_movies(self, movies: List[Movie]) -> bool:
        if not self.conn or not movies:
            return False

        sql = """
            MERGE INTO Movies AS target
            USING (SELECT %s AS movie_id) AS source
            ON target.movie_id = source.movie_id
            WHEN MATCHED THEN
                UPDATE SET
                    name = %s, poster_url = %s, plot = %s, director = %s,
                    screenwriter = %s, actors = %s, genre = %s, country = %s,
                    language = %s, release_date = %s, runtime = %s,
                    imdb_link = %s, also_known_as = %s, douban_rating = %s,
                    rating_count = %s, short_comment_count = %s,
                    crawl_time = %s, is_crawled = %s
            WHEN NOT MATCHED THEN
                INSERT (
                    movie_id, name, poster_url, plot, director, screenwriter,
                    actors, genre, country, language, release_date, runtime,
                    imdb_link, also_known_as, douban_rating, rating_count,
                    short_comment_count, crawl_time, is_crawled
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
        """
        try:
            for movie in movies:
                params = (
                    movie.movie_id, movie.name, movie.poster_url, movie.plot,
                    movie.director, movie.screenwriter, movie.actors, movie.genre,
                    movie.country, movie.language, movie.release_date, movie.runtime,
                    movie.imdb_link, movie.also_known_as, movie.douban_rating,
                    movie.rating_count, movie.short_comment_count,
                    movie.crawl_time or datetime.now(), movie.is_crawled,
                    movie.movie_id, movie.name, movie.poster_url, movie.plot,
                    movie.director, movie.screenwriter, movie.actors, movie.genre,
                    movie.country, movie.language, movie.release_date, movie.runtime,
                    movie.imdb_link, movie.also_known_as, movie.douban_rating,
                    movie.rating_count, movie.short_comment_count,
                    movie.crawl_time or datetime.now(), movie.is_crawled,
                )
                self.cursor.execute(sql, params)
            self.conn.commit()
            return True
        except Exception as exc:
            print(f"[数据库] 保存电影失败: {exc}")
            self.conn.rollback()
            return False

    def import_movies_csv(self, csv_path: str) -> dict:
        """从 movies.csv 导入电影数据。"""
        if not self.conn:
            return {"error": "数据库未连接"}

        column_aliases = {
            "movie_id": ["movie_id", "电影id", "id"],
            "name": ["name", "电影名", "电影名称"],
            "poster_url": ["poster_url", "poster", "海报", "海报链接"],
            "plot": ["plot", "summary", "剧情简介", "简介"],
            "director": ["director", "导演"],
            "screenwriter": ["screenwriter", "编剧"],
            "actors": ["actors", "主演", "演员"],
            "genre": ["genre", "类型"],
            "country": ["country", "制片国家", "国家", "制片国家/地区"],
            "language": ["language", "语言"],
            "release_date": ["release_date", "上映时间", "上映日期"],
            "runtime": ["runtime", "片长"],
            "imdb_link": ["imdb_link", "imdb", "imdb链接"],
            "also_known_as": ["also_known_as", "aka", "又名"],
            "douban_rating": ["douban_rating", "rating", "豆瓣评分", "评分"],
            "rating_count": ["rating_count", "评价人数", "评分人数"],
            "short_comment_count": ["short_comment_count", "short_review_count", "短评数"],
        }
        field_types = {
            "movie_id": str, "name": str, "poster_url": str, "plot": str,
            "director": str, "screenwriter": str, "actors": str, "genre": str,
            "country": str, "language": str, "release_date": str, "runtime": str,
            "imdb_link": str, "also_known_as": str, "douban_rating": float,
            "rating_count": int, "short_comment_count": int,
        }

        movies = []
        failed = 0
        try:
            with open(csv_path, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                headers = [h.strip() for h in (reader.fieldnames or [])]
                mapping = {}
                for db_field, aliases in column_aliases.items():
                    for header in headers:
                        if header.lower() in [a.lower() for a in aliases]:
                            mapping[db_field] = header
                            break

                for row in reader:
                    try:
                        data = {
                            field: self._convert(row.get(header, ""), field_types[field])
                            for field, header in mapping.items()
                        }
                        if not str(data.get("movie_id", "")).strip():
                            continue
                        movies.append(Movie(
                            movie_id=str(data["movie_id"]),
                            name=str(data.get("name", "")),
                            poster_url=str(data.get("poster_url", "")),
                            plot=str(data.get("plot", "")),
                            director=str(data.get("director", "")),
                            screenwriter=str(data.get("screenwriter", "")),
                            actors=str(data.get("actors", "")),
                            genre=str(data.get("genre", "")),
                            country=str(data.get("country", "")),
                            language=str(data.get("language", "")),
                            release_date=str(data.get("release_date", "")),
                            runtime=str(data.get("runtime", "")),
                            imdb_link=str(data.get("imdb_link", "")),
                            also_known_as=str(data.get("also_known_as", "")),
                            douban_rating=float(data.get("douban_rating", 0.0)),
                            rating_count=int(data.get("rating_count", 0)),
                            short_comment_count=int(data.get("short_comment_count", 0)),
                            crawl_time=datetime.now(),
                            is_crawled=True,
                        ))
                    except Exception as exc:
                        print(f"[数据库] 解析电影行失败: {exc}")
                        failed += 1
        except Exception as exc:
            return {"error": str(exc)}

        success = 0
        batch_size = 100
        for i in range(0, len(movies), batch_size):
            batch = movies[i:i + batch_size]
            if self.batch_save_movies(batch):
                success += len(batch)
            else:
                failed += len(batch)

        return {"total": len(movies), "success": success, "failed": failed}

    def import_reviews_csv(self, csv_path: str) -> dict:
        """从 reviews.csv 导入短评数据。"""
        if not self.conn:
            return {"error": "数据库未连接"}

        column_aliases = {
            "movie_id": ["movie_id", "电影id"],
            "nickname": ["nickname", "reviewer", "昵称", "短评者昵称"],
            "comment_time": ["comment_time", "review_time", "短评时间", "评论时间"],
            "content": ["content", "短评内容", "内容"],
            "helpful_votes": ["helpful_votes", "votes", "有用人数", "认为该短评有用人数"],
        }
        field_types = {
            "movie_id": str, "nickname": str, "comment_time": str,
            "content": str, "helpful_votes": int,
        }

        comments_by_movie = {}
        failed = 0
        total = 0

        try:
            with open(csv_path, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                headers = [h.strip() for h in (reader.fieldnames or [])]
                mapping = {}
                for db_field, aliases in column_aliases.items():
                    for header in headers:
                        if header.lower() in [a.lower() for a in aliases]:
                            mapping[db_field] = header
                            break

                for row in reader:
                    try:
                        data = {
                            field: self._convert(row.get(header, ""), field_types[field])
                            for field, header in mapping.items()
                        }
                        movie_id = str(data.get("movie_id", "")).strip()
                        if not movie_id:
                            continue
                        comment = ShortComment(
                            movie_id=movie_id,
                            nickname=str(data.get("nickname", "")),
                            comment_time=str(data.get("comment_time", "")),
                            content=str(data.get("content", "")),
                            helpful_votes=int(data.get("helpful_votes", 0)),
                            crawl_time=datetime.now(),
                        )
                        comments_by_movie.setdefault(movie_id, []).append(comment)
                        total += 1
                    except Exception as exc:
                        print(f"[数据库] 解析短评行失败: {exc}")
                        failed += 1
        except Exception as exc:
            return {"error": str(exc)}

        insert_sql = """
            INSERT INTO ShortComments
                (movie_id, nickname, comment_time, content, helpful_votes, crawl_time)
            VALUES (%s, %s, %s, %s, %s, %s);
        """
        success = 0
        try:
            for movie_id, comments in comments_by_movie.items():
                self.cursor.execute("DELETE FROM ShortComments WHERE movie_id = %s", (movie_id,))
                for comment in comments:
                    self.cursor.execute(insert_sql, (
                        comment.movie_id, comment.nickname, comment.comment_time,
                        comment.content, comment.helpful_votes, comment.crawl_time,
                    ))
                success += len(comments)
            self.conn.commit()
        except Exception as exc:
            print(f"[数据库] 导入短评失败: {exc}")
            self.conn.rollback()
            failed += total - success
            return {"error": str(exc), "total": total, "success": success, "failed": failed}

        return {"total": total, "success": success, "failed": failed}
