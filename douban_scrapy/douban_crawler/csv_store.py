# -*- coding: utf-8 -*-
"""CSV 持久化读写，支持多次爬取增量合并。"""

import csv
import os

MOVIE_FIELDS = [
    "movie_id", "name", "poster", "summary", "director", "screenwriter",
    "actors", "genre", "country", "language", "release_date", "runtime",
    "imdb_link", "aka", "rating", "rating_count", "short_review_count",
]
REVIEW_FIELDS = [
    "movie_id", "movie_name", "reviewer", "review_time", "content", "votes",
]


def movies_csv_path(output_dir: str) -> str:
    return os.path.join(output_dir, "movies.csv")


def reviews_csv_path(output_dir: str) -> str:
    return os.path.join(output_dir, "reviews.csv")


def _normalize_row(row: dict, fields: list) -> dict:
    return {field: (row.get(field, "") or "") for field in fields}


def load_existing_movies(output_dir: str) -> dict:
    """返回 {movie_id: row_dict}。"""
    path = movies_csv_path(output_dir)
    movies = {}
    if not os.path.isfile(path):
        return movies
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            movie_id = str(row.get("movie_id", "")).strip()
            if movie_id:
                movies[movie_id] = _normalize_row(row, MOVIE_FIELDS)
    return movies


def review_dedup_key(row: dict) -> tuple:
    return (
        str(row.get("movie_id", "")).strip(),
        str(row.get("reviewer", "")).strip(),
        str(row.get("review_time", "")).strip(),
        str(row.get("content", "")).strip(),
    )


def load_existing_reviews(output_dir: str) -> tuple[list, set]:
    """返回 (reviews_list, dedup_keys)。"""
    path = reviews_csv_path(output_dir)
    reviews = []
    keys = set()
    if not os.path.isfile(path):
        return reviews, keys
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            normalized = _normalize_row(row, REVIEW_FIELDS)
            if not normalized.get("movie_id"):
                continue
            key = review_dedup_key(normalized)
            if key in keys:
                continue
            keys.add(key)
            reviews.append(normalized)
    return reviews, keys


def write_movies_csv(output_dir: str, movies_buffer: dict) -> None:
    os.makedirs(output_dir, exist_ok=True)
    path = movies_csv_path(output_dir)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=MOVIE_FIELDS)
        writer.writeheader()
        for row in movies_buffer.values():
            writer.writerow(row)


def write_reviews_csv(output_dir: str, reviews: list) -> None:
    os.makedirs(output_dir, exist_ok=True)
    path = reviews_csv_path(output_dir)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=REVIEW_FIELDS)
        writer.writeheader()
        for row in reviews:
            writer.writerow(row)
