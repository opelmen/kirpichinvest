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

    def test_gsc_daily_in_report(self):
        import seo_nightly as sn
        md = sn.to_md({"date": "2026-11-07", "gsc": {"site": "https://torggid.ru/", "period_28": "2026-10-08 — 2026-11-04",
                                                     "daily": [["2026-10-30", 1, 40, 12.5]]}})
        self.assertIn("- 2026-10-30 — 1, 40, 12.5", md)
        self.assertIn("за 28 дней", md)

    def test_gsc_inspect_and_sitemaps_in_report(self):
        import seo_nightly as sn
        md = sn.to_md({"date": "2026-11-07", "gsc": {"site": "https://torggid.ru/",
            "sitemaps": [["/sitemap.xml", "2026-11-06", 0, 0, 30000, 0]],
            "inspect": [["/torgi/", "NEUTRAL", "Crawled - currently not indexed", "2026-11-01", "SUCCESSFUL", "ALLOWED", "INDEXING_ALLOWED", "/torgi/"]]}})
        self.assertIn("- /sitemap.xml — 2026-11-06, 0, 0, 30000, 0", md)
        self.assertIn("- /torgi/ — NEUTRAL, Crawled - currently not indexed, 2026-11-01", md)

    def test_ai_visits_counted_by_utm_source(self):
        import seo_nightly as sn
        from datetime import date
        from unittest import mock

        def fake(token, params):
            dim = params.get("dimensions")
            if dim == "ym:s:referalSource":
                return [{"dimensions": [{"name": "perplexity.ai"}], "metrics": [3]}, {"dimensions": [{"name": "vk.com"}], "metrics": [9]}]
            if dim == "ym:s:UTMSource":
                return [{"dimensions": [{"name": "chatgpt.com"}], "metrics": [120]}, {"dimensions": [{"name": "avito"}], "metrics": [50]}]
            return []

        with mock.patch.object(sn, "metrika", side_effect=fake):
            m = sn.metrika_block("t", date(2026, 11, 9))
        self.assertEqual(m["referrers_week"]["ai"], [["perplexity.ai", 3], ["utm chatgpt.com", 120]])

    def test_indexnow_first_night_then_rotation(self):
        import json as _j
        import tempfile
        import seo_nightly as sn
        from datetime import date
        from pathlib import Path
        from unittest import mock
        B = "https://torggid.ru"
        key = _j.loads(Path(sn.__file__).with_name("config.json").read_text(encoding="utf-8"))["INDEXNOW_KEY"]
        hubs = [B + "/torgi/", B + "/torgi/moskva/"]
        allu = hubs + [B + "/auto/lot/1/", B + "/torgi/lot/1/", B + "/stati/a/", "https://evil.example/x/"]
        sent = []

        def fake_sm(path, depth=0):
            return (hubs, {}) if "yandex" in path else (allu, {})

        def fake_post(ep, body):
            sent.append((ep, _j.loads(body)))
            return 200
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(sn, "sitemap_urls", side_effect=fake_sm), \
                mock.patch.object(sn, "fetch", return_value={"status": 200, "body": key}), \
                mock.patch.object(sn, "indexnow_post", side_effect=fake_post):
            st = Path(d) / "indexnow-state.json"
            r1 = sn.indexnow_block(True, st, date(2026, 11, 13), first_n=4, n=2)
            self.assertEqual(r1["submitted"], 4)
            self.assertEqual(sent[0][1]["urlList"], [B + "/torgi/", B + "/torgi/moskva/", B + "/stati/a/", B + "/torgi/lot/1/"])
            self.assertEqual(sent[0][1]["host"], "torggid.ru")
            r2 = sn.indexnow_block(True, st, date(2026, 11, 14), first_n=4, n=2)
            self.assertEqual(sent[-1][1]["urlList"], [B + "/auto/lot/1/"])
            self.assertEqual(r2["picked"], 1)
            md = sn.to_md({"date": "2026-11-13", "indexnow": r1})
            self.assertIn("IndexNow", md)
            self.assertIn("принято Яндексом: 4", md)

    def test_bing_crawl_issues_summary(self):
        import seo_nightly as sn
        B = "https://torggid.ru"
        rows = [{"Url": B + "/torgi/lot/9/", "HttpCode": 404}, {"Url": B + "/auto/lot/a/", "HttpCode": 404},
                {"Url": B + "/.env", "HttpCode": 403}, {"Url": B + "/torgi/moskva/", "HttpCode": 503},
                {"Url": B + "/guides/x.html", "HttpCode": 404}]
        r = sn.bing_issues_summary(rows, [B + "/torgi/moskva/", B + "/torgi/"])
        self.assertEqual(r["total"], 5)
        self.assertEqual(dict(r["by_code"])["404"], 3)
        self.assertEqual(dict(r["by_kind"])["мусорные пути сканеров"], 1)
        self.assertEqual(dict(r["by_kind"])["старые страницы прежнего сайта"], 1)
        self.assertEqual(r["live_in_sitemap"], [["/torgi/moskva/", "503"]])
        md = sn.to_md({"date": "2026-11-14", "bing": {"issues": r}})
        self.assertIn("живые страницы из sitemap: 1", md)

    def test_bing_pick_rotates_and_skips_recent(self):
        import seo_nightly as sn
        from datetime import date
        B = "https://torggid.ru"
        queue = [B + "/torgi/"]
        sm = [B + "/auto/lot/1/", B + "/torgi/lot/1/", B + "/torgi/permskiy-kray/", B + "/torgi/", B + "/stati/a/"]
        state = {B + "/stati/a/": "2026-11-01", B + "/torgi/lot/1/": "2026-09-01"}
        got = sn.bing_pick(queue, sm, state, date(2026, 11, 8), n=3)
        self.assertEqual(got, [B + "/torgi/", B + "/torgi/permskiy-kray/", B + "/torgi/lot/1/"])

    def test_gsc_submit_sitemap_put_and_403_hint(self):
        import seo_nightly as sn
        from datetime import date
        from unittest import mock
        calls = []

        def fake_call(token, path, body=None, method=None):
            calls.append((path, method))
            if path == "/sites":
                return {"siteEntry": [{"siteUrl": "sc-domain:torggid.ru"}]}
            if method == "PUT":
                raise RuntimeError("HTTP 403 forbidden")
            return {}

        with mock.patch.object(sn, "google_token", return_value=("t", "sa@x.iam.gserviceaccount.com")) as tok, \
                mock.patch.object(sn, "gsc_call", side_effect=fake_call), \
                mock.patch.object(sn.urllib.request, "urlopen", side_effect=OSError("no net")):
            g = sn.gsc_block("{}", date(2026, 11, 7), act=True)
        self.assertTrue(tok.call_args[0][1].endswith("/webmasters"))
        self.assertIn(("/sites/sc-domain%3Atorggid.ru/sitemaps/https%3A%2F%2Ftorggid.ru%2Fsitemap.xml", "PUT"), calls)
        self.assertIn("«Полный»", g["submit"][0][1])
        self.assertIn("Отправка sitemap в Google", sn.to_md({"date": "2026-11-07", "gsc": g}))
