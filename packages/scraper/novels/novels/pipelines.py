from novels.items import NovelsItem, ChapterItem
from itemadapter import ItemAdapter
from functools import singledispatch
import psycopg2


@singledispatch
def handle_item(item, pipeline, spider):
    spider.logger.warning(f"Unhandled item type: {type(item)}")
    return item


@handle_item.register
def _(item: NovelsItem, pipeline, spider):
    cur = pipeline.conn.cursor()
    try:
        authorIds = [pipeline.getOrCreate(cur, "authors", a) for a in item.get("authors") or []]
        eventIds = [pipeline.getOrCreate(cur, "events", e) for e in item.get("events") or []]
        genreIds = [pipeline.getOrCreate(cur, "genres", g) for g in item.get("genres") or []]
        publisherIds = [pipeline.getOrCreate(cur, "publishers", p) for p in item.get("publishers") or []]

        cur.execute(
            """
            INSERT INTO novels
                ("externalId", slug, title, description, status, language,
                 "totalChapters", year, "coverUrl", "firstChapterUrl")
            VALUES
                (%(externalId)s, %(slug)s, %(title)s, %(description)s, %(status)s,
                 %(language)s, %(chapters)s, %(publishYear)s, %(coverUrl)s, %(firstChapterUrl)s)
            ON CONFLICT ("externalId") DO UPDATE SET
                slug = EXCLUDED.slug,
                title = EXCLUDED.title,
                description = EXCLUDED.description,
                status = EXCLUDED.status,
                language = EXCLUDED.language,
                "totalChapters" = EXCLUDED."totalChapters",
                year = EXCLUDED.year,
                "coverUrl" = EXCLUDED."coverUrl",
                "firstChapterUrl" = EXCLUDED."firstChapterUrl",
                "scrapedAt" = NOW()
            RETURNING id
            """,
            dict(item)
        )
        novelId = cur.fetchone()[0]

        pipeline.linkMany(cur, "novelauthors", "authorid", novelId, authorIds)
        pipeline.linkMany(cur, "novelevents", "eventid", novelId, eventIds)
        pipeline.linkMany(cur, "novelgenres", "genreid", novelId, genreIds)
        pipeline.linkMany(cur, "novelpublishers", "publisherid", novelId, publisherIds)

        pipeline.ensureScraperJob(cur, novelId, item.get("firstChapterUrl"), item.get("chapters"))

        pipeline.conn.commit()
    except Exception:
        pipeline.conn.rollback()
        raise
    finally:
        cur.close()

    return item


@handle_item.register
def _(item: ChapterItem, pipeline, spider):
    spider.logger.info(f"Processing ChapterItem: {item}")
    # lógica de upsert para chapters
    return item


class NovelsPipeline:

    def open_spider(self, spider):
        self.conn = psycopg2.connect(spider.settings.get("DATABASE_URL"))
        self.conn.autocommit = False

    def close_spider(self, spider):
        self.conn.close()

    def getOrCreate(self, cur, table, name):
        cur.execute(
            f"""
            INSERT INTO {table} (name) VALUES (%s)
            ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name
            RETURNING id
            """,
            (name,)
        )
        return cur.fetchone()[0]

    def linkMany(self, cur, junctionTable, entityCol, novelId, entityIds):
        for entityId in entityIds:
            cur.execute(
                f"""
                INSERT INTO {junctionTable} (novelid, {entityCol})
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING
                """,
                (novelId, entityId)
            )

    def ensureScraperJob(self, cur, novelId, firstChapterUrl, totalChapters):
        cur.execute(
            'SELECT id FROM "scraperJobs" '
            'WHERE "novelId" = %s AND status IN (\'pending\', \'running\')',
            (novelId,)
        )
        if cur.fetchone():
            return

        cur.execute(
            'SELECT COUNT(*), MAX(number) FROM chapters WHERE "novelId" = %s',
            (novelId,)
        )
        scrapedCount, lastNumber = cur.fetchone()

        if scrapedCount >= totalChapters:
            return

        if scrapedCount == 0:
            targetUrl = firstChapterUrl
        else:
            cur.execute(
                'SELECT url FROM chapters WHERE "novelId" = %s ORDER BY number DESC LIMIT 1',
                (novelId,)
            )
            targetUrl = cur.fetchone()[0]

        cur.execute(
            'INSERT INTO "scraperJobs" ("novelId", status, "targetUrl") '
            "VALUES (%s, 'pending', %s)",
            (novelId, targetUrl)
        )

    def process_item(self, item, spider):
        return handle_item(item, self, spider)