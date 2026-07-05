import scrapy


class MovieItem(scrapy.Item):
    movie_id = scrapy.Field()
    name = scrapy.Field()
    poster = scrapy.Field()
    summary = scrapy.Field()
    director = scrapy.Field()
    screenwriter = scrapy.Field()
    actors = scrapy.Field()
    genre = scrapy.Field()
    country = scrapy.Field()
    language = scrapy.Field()
    release_date = scrapy.Field()
    runtime = scrapy.Field()
    imdb_link = scrapy.Field()
    aka = scrapy.Field()
    rating = scrapy.Field()
    rating_count = scrapy.Field()
    short_review_count = scrapy.Field()


class ReviewItem(scrapy.Item):
    movie_id = scrapy.Field()
    movie_name = scrapy.Field()
    reviewer = scrapy.Field()
    review_time = scrapy.Field()
    content = scrapy.Field()
    votes = scrapy.Field()
