import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("indexnow", Path(__file__).resolve().parents[1] / "_src/indexnow.py")
indexnow = importlib.util.module_from_spec(spec)
spec.loader.exec_module(indexnow)


class IndexNowTests(unittest.TestCase):
    def test_deduplicate(self):
        url = "https://torggid.ru/"
        self.assertEqual(indexnow.validate_urls([url, url]), [url])

    def test_refuse_noncanonical_and_foreign_urls(self):
        for url in ["https://example.org/", "http://torggid.ru/",
                    "https://torggid.ru/?utm_source=test",
                    "https://torggid.ru/#form", "https://torggid.ru.evil.test/"]:
            with self.subTest(url=url), self.assertRaises(ValueError):
                indexnow.validate_urls([url])

    def test_empty_and_over_limit(self):
        for urls in [[], [f"https://torggid.ru/{i}/" for i in range(10001)]]:
            with self.assertRaises(ValueError):
                indexnow.validate_urls(urls)

    def test_sitemap(self):
        data = b'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://torggid.ru/</loc></url></urlset>'
        self.assertEqual(indexnow.sitemap_urls(data), ["https://torggid.ru/"])
        with self.assertRaises(ValueError):
            indexnow.sitemap_urls(b'<rss/>')

    def test_sitemap_index_is_expanded(self):
        index = (b'<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                 b'<sitemap><loc>https://torggid.ru/sitemap-pages.xml</loc></sitemap>'
                 b'<sitemap><loc>https://torggid.ru/sitemap-lots-1.xml</loc></sitemap></sitemapindex>')
        parts = {"https://torggid.ru/sitemap-pages.xml": b'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://torggid.ru/</loc></url></urlset>',
                 "https://torggid.ru/sitemap-lots-1.xml": b'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://torggid.ru/torgi/lot/a/</loc></url></urlset>'}
        self.assertEqual(indexnow.sitemap_urls(index, fetch=parts.__getitem__), ["https://torggid.ru/", "https://torggid.ru/torgi/lot/a/"])
        foreign = b'<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><sitemap><loc>https://evil.test/s.xml</loc></sitemap></sitemapindex>'
        with self.assertRaises(ValueError):
            indexnow.sitemap_urls(foreign, fetch=lambda u: b"")
