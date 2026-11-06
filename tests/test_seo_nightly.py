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


class RecrawlQueueTests(unittest.TestCase):
    def test_queue_file_reads_in_order_without_comments_and_duplicates(self):
        import tempfile
        from datetime import date
        import seo_nightly as sn
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("# очередь\n/torgi/\n\n/torgi/moskva/\n/torgi/\nhttps://torggid.ru/auto/\n")
        q = sn.read_queue(f.name)
        self.assertEqual(q, ["https://torggid.ru/torgi/", "https://torggid.ru/torgi/moskva/", "https://torggid.ru/auto/"])
        # недавно отправленные пропускаются, лимит соблюдается
        state = {"https://torggid.ru/torgi/": "2026-11-05"}
        self.assertEqual(sn.pick_recrawl(q, state, date(2026, 11, 6), 5), q[1:])
        self.assertEqual(sn.pick_recrawl(q, {"https://torggid.ru/torgi/": "2026-10-20"}, date(2026, 11, 6), 1), q[:1])

    def test_repo_queue_is_valid(self):
        from pathlib import Path
        import seo_nightly as sn
        q = sn.read_queue(Path(__file__).resolve().parents[1] / "_src" / "data" / "recrawl_queue.txt")
        self.assertGreater(len(q), 30)
        self.assertTrue(all(u.startswith("https://torggid.ru/") and u.endswith("/") for u in q))

    def test_act_section_in_report(self):
        import seo_nightly as sn
        md = sn.to_md({"date": "2026-11-06", "act": {"sitemap": "добавлен", "sent": ["https://torggid.ru/torgi/"],
                                                     "quota": {"daily": 150, "left": 150}, "errors": {}}})
        self.assertIn("sitemap-yandex.xml: добавлен", md)
        self.assertIn("отправлено 1", md)
        self.assertIn("  - /torgi/", md)
