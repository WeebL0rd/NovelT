from logging import NullHandler

import scrapy
import re
from w3lib.html import remove_tags
from novels.items import NovelsItem


class NovelsSpiderSpider(scrapy.Spider):
    name = "novels_spider"
    allowed_domains = ["ranobes.net"]
    start_urls = ["https://ranobes.net"]

    def __init__(self, novelId=None, slug=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not novelId and not slug:
            raise ValueError("novelId or slug must be provided")
        self.novelId = novelId
        self.slug = slug
        self.start_urls = [f"https://ranobes.net/novels/{self.novelId}-{self.slug}.html" ]

    def getByTitle(self, lis, keyword):
        for li in lis:
            title_attr = li.css("::attr(title)").get() or ""
            text = " ".join(li.css("::text").getall())
            if keyword in title_attr or keyword in text:
                return li
        return None

    def getDescription(self,response):
        # 1. Traé el HTML crudo del contenedor (no el texto)
        raw_html = response.css(".moreless__full").get()

        # 2. Sacá el link "Collapse" antes de seguir (no lo querés en la descripción)
        raw_html = re.sub(
        r'<a[^>]*class="[^"]*moreless__toggle[^"]*"[^>]*>.*?</a>',
        '',
        raw_html,
        flags=re.DOTALL
    )

        # 3. Reemplazá <br> (en sus variantes) por un salto de línea real
        raw_html = re.sub(r'<br\s*/?>', '\n', raw_html)

        # 4. Sacá el resto de las etiquetas HTML (el div contenedor, etc.)
        description = remove_tags(raw_html)

        # 5. Limpiá espacios sobrantes en cada línea, pero conservá los \n
        description = "\n".join(line.strip() for line in description.split("\n")).strip()
        return description

    def parse(self, response):
        title = response.css('h1.title::text').get()
        title = title.strip() if title else None

        description = self.getDescription(response)

        items = response.css("div.r-fullstory-spec ul:nth-of-type(1) li")
        

        statusLi = self.getByTitle(items, "Status in COO")
        status = statusLi.css("span.grey a::text").get() if statusLi else None
        
        # Capítulos disponibles (no confundir con "Total written")
        chaptersLi = self.getByTitle(items, "Available")
        if chaptersLi:
            chapters_text = chaptersLi.css("span.grey::text").get()
            match = re.match(r"(\d+)", chapters_text) if chapters_text else None
            totalChapters = int(match.group(1)) if match else None
        else:
            totalChapters = None

        publishYearLi = self.getByTitle(items, "Year of publishing")
        publishYear = int(publishYearLi.css("a::text").get()) if publishYearLi else None
                
        languageLi = self.getByTitle(items, "Language")
        language = languageLi.css("a::text").get() if languageLi else None
        
        authorsLi = self.getByTitle(items, "Authors")
        authors = authorsLi.css("span.tag_list a::text").getall() if authorsLi else []
        authors = [author.strip() for author in authors] if authors else []

        publishersLi = self.getByTitle(items, "Publishers")
        publishers = publishersLi.css("span.publishers_list a::text").getall() if publishersLi else []
        publishers = [publisher.strip() for publisher in publishers] if publishers else []

        genresEvents = response.css("div.r-fullstory-s2 div.mcollapse-cont")

        genres = genresEvents[0].css("div.links a::text").getall()
        genres = [genre.strip() for genre in genres] if genres else []

        events = genresEvents[1].css("a::text").getall()
        events = [event.strip() for event in events] if events else []

        coverUrl = response.css(".poster a::attr(href)").get()

        firstChapterLi = self.getByTitle(response.css(".r-fullstory-chapters-foot a"), "First")
        relativeChapterUrl = firstChapterLi.css("::attr(href)").get() if firstChapterLi else None
        firstChapterUrl = response.urljoin(relativeChapterUrl) if relativeChapterUrl else None


        novel = {
            "externalId": self.novelId,
            "slug": self.slug,
            "title": title,
            "description": description,
            "status": status,
            "chapters": totalChapters,
            "publishYear": publishYear,
            "language": language,
            "authors": authors,
            "publishers": publishers,
            "genres": genres,
            "events": events,

            "coverUrl": coverUrl,
            "firstChapterUrl": firstChapterUrl
        }
        novel = NovelsItem(**novel) 

        yield novel

