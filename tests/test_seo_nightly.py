import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_src"))
import seo_nightly  # noqa: E402


class PageFacts(unittest.TestCase):
    def test_reads_head_tags(self):
        html = ('<html><head><title> Торги  в Москве </title>'
                '<link rel="canonical" href="https://torggid.ru/torgi/moskva/">'
                '<meta name="robots" content="index, follow"><meta name="yandex" content="noindex, follow">'
                '<meta name="description" content="Лоты">'
                '<script type="application/ld+json">{}</script></head><body><h1>Лоты <b>Москвы</b></h1></body></html>')
        f = seo_nightly.page_facts(html)
        self.assertEqual(f["title"], "Торги в Москве")
        self.assertEqual(f["h1"], "Лоты Москвы")
        self.assertEqual(f["canonical"], "https://torggid.ru/torgi/moskva/")
        self.assertEqual(f["yandex"], "noindex, follow")
        self.assertEqual(f["description_len"], 4)
        self.assertEqual(f["jsonld"], 1)

    def test_report_without_data(self):
        md = seo_nightly.to_md({"date": "2026-11-04", "errors": {"token": "нет"}})
        self.assertIn("ночной срез 2026-11-04", md)


if __name__ == "__main__":
    unittest.main()
