import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("indexnow", Path(__file__).resolve().parents[1] / "_src/indexnow.py")
indexnow = importlib.util.module_from_spec(spec)
spec.loader.exec_module(indexnow)


class IndexNowTests(unittest.TestCase):
    def test_deduplicate(self):
        url = "https://kirpichinvest.ru/"
        self.assertEqual(indexnow.validate_urls([url, url]), [url])

    def test_refuse_noncanonical_and_foreign_urls(self):
        for url in ["https://example.org/", "http://kirpichinvest.ru/",
                    "https://kirpichinvest.ru/?utm_source=test",
                    "https://kirpichinvest.ru/#form", "https://kirpichinvest.ru.evil.test/"]:
            with self.subTest(url=url), self.assertRaises(ValueError):
                indexnow.validate_urls([url])

    def test_empty_and_over_limit(self):
        for urls in [[], [f"https://kirpichinvest.ru/{i}/" for i in range(10001)]]:
            with self.assertRaises(ValueError):
                indexnow.validate_urls(urls)

    def test_sitemap(self):
        data = b'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://kirpichinvest.ru/</loc></url></urlset>'
        self.assertEqual(indexnow.sitemap_urls(data), ["https://kirpichinvest.ru/"])
        with self.assertRaises(ValueError):
            indexnow.sitemap_urls(b'<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"/>')
