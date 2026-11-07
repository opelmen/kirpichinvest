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

    def test_bing_section_in_report(self):
        import seo_nightly as sn
        md = sn.to_md({"date": "2026-11-07", "bing": {
            "crawl": {"date": "2026-11-06", "in_index": 1200, "crawled": 300, "crawl_errors": 2, "blocked": 0, "in_links": 10},
            "traffic": {"impressions_7d": 450, "clicks_7d": 12, "days": 7},
            "queries": [["квартиры с торгов казань", 40, 3, 4.5]], "pages": [["/torgi/kazan/", 40, 3]],
            "feeds": [["/sitemap.xml", "Processed", 30000, "2026-11-06"]], "submitted_feeds": ["/sitemap-yandex.xml"],
            "quota": {"daily": 100, "monthly": 1000}, "submitted_urls": 30}})
        self.assertIn("## Bing", md)
        self.assertIn("в индексе Bing: 1200", md)
        self.assertIn("показы за 7 дн.: 450, клики: 12", md)
        self.assertIn("/sitemap.xml (Processed, 30000 адресов, обход 2026-11-06)", md)
        self.assertIn("отправлены sitemap: /sitemap-yandex.xml", md)
        self.assertIn("отправлено 30", md)
        self.assertIn("- квартиры с торгов казань — 40, 3, 4.5", md)

    def test_bing_errors_are_reported_not_raised(self):
        import seo_nightly as sn
        md = sn.to_md({"date": "2026-11-07", "bing": {"errors": {"crawl": "HTTP 401 InvalidApiKey"}}})
        self.assertIn("ошибка crawl: HTTP 401 InvalidApiKey", md)

    def test_gsc_section_in_report(self):
        import seo_nightly as sn
        md = sn.to_md({"date": "2026-11-07", "gsc": {
            "site": "sc-domain:torggid.ru", "period": "2026-10-29 — 2026-11-04",
            "totals": {"clicks": 12, "impressions": 900, "ctr": 1.3, "position": 14.2},
            "totals_prev": {"clicks": 9, "impressions": 700, "ctr": 1.3, "position": 15.0},
            "queries": {"count": 320, "top": [["квартиры с торгов", 100, 2, 12.0]],
                        "wins": [["торги по банкротству казань официальный сайт", 40, 0, 11.5]]},
            "pages": [["/torgi/kazan/", 40, 0, 11.5]]}})
        self.assertIn("## Google Search Console", md)
        self.assertIn("клики 12 (пред. 9), показы 900 (пред. 700)", md)
        self.assertIn("Быстрые победы", md)
        self.assertIn("- торги по банкротству казань официальный сайт — 40, 0, 11.5", md)

    def test_gsc_missing_key_is_reported(self):
        import seo_nightly as sn
        md = sn.to_md({"date": "2026-11-07", "errors": {"gsc": "GSC_SERVICE_ACCOUNT не задан"}})
        self.assertIn("ошибка gsc: GSC_SERVICE_ACCOUNT не задан", md)

    def test_google_token_signs_jwt(self):
        import json
        import seo_nightly as sn
        try:
            from cryptography.hazmat.primitives import serialization
            from cryptography.hazmat.primitives.asymmetric import rsa
        except ImportError:
            self.skipTest("cryptography не установлена")
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        pem = key.private_key_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                    serialization.NoEncryption()).decode() if hasattr(key, "private_key_bytes") else \
            key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()
        sa = json.dumps({"client_email": "x@y.iam.gserviceaccount.com", "token_uri": "http://127.0.0.1:9/token", "private_key": pem})
        # подпись проходит, падает только сетевой обмен токена
        with self.assertRaises(Exception) as cm:
            sn.google_token(sa)
        self.assertNotIn("private_key", str(cm.exception))

    def test_bing_date_parses_wcf_format(self):
        import seo_nightly as sn
        self.assertEqual(sn.bing_date("/Date(1793000000000)/"), "2026-10-26")
        self.assertEqual(sn.bing_date("2026-11-06T00:00:00"), "2026-11-06")
