# -*- coding: utf-8 -*-
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Movie:
    movie_id: str
    name: str = ""
    poster_url: str = ""
    plot: str = ""
    director: str = ""
    screenwriter: str = ""
    actors: str = ""
    genre: str = ""
    country: str = ""
    language: str = ""
    release_date: str = ""
    runtime: str = ""
    imdb_link: str = ""
    also_known_as: str = ""
    douban_rating: float = 0.0
    rating_count: int = 0
    short_comment_count: int = 0
    crawl_time: Optional[datetime] = None
    is_crawled: bool = True


@dataclass
class ShortComment:
    movie_id: str
    nickname: str = ""
    comment_time: str = ""
    content: str = ""
    helpful_votes: int = 0
    crawl_time: Optional[datetime] = None
