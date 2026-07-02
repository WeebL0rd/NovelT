# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy


class NovelsItem(scrapy.Item):
    externalId = scrapy.Field()
    slug = scrapy.Field()
    title = scrapy.Field() 
    description = scrapy.Field()
    status = scrapy.Field()
    chapters = scrapy.Field()
    publishYear = scrapy.Field()
    language = scrapy.Field()
    authors = scrapy.Field()
    publishers = scrapy.Field()
    genres = scrapy.Field()
    events = scrapy.Field()
    coverUrl = scrapy.Field()
    firstChapterUrl = scrapy.Field()



