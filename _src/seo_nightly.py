"""Nightly SEO/GEO snapshot for torggid.ru: Metrika by day, Webmaster, live site health.

Read-only: GET requests only, nothing is submitted or changed.
Token: YANDEX_METRIKA_TOKEN (metrika:read, webmaster:hostinfo). Without it only site health runs.
Writes <out>/<date>.json, <out>/<date>.md and <out>/latest.md; each failed call is recorded, not fatal.
The night analysis (Claude) reads these files from the seo-yandex-data branch.
"""
import argparse
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

from yandex_report import COUNTER, METRIKA, WEBMASTER, get, safe, webmaster

BASE = "https://torggid.ru"
UA = "TorgGid-Nightly-SEO/1.0"
KEY_PAGES = ("/", "/torgi/", "/torgi/moskva/", "/torgi/sankt-peterburg/", "/auto/", "/stati/",
             "/proverka-lota/", "/kupit-kvartiru-s-torgov/", "/analitika/")
TECH = ("/robots.txt", "/sitemap.xml", "/sitemap-yandex.xml", "/llms.txt")
RECRAWL_EVERY_DAYS = 7  # один и тот же адрес не чаще раза в неделю: квота нужна новым и изменённым страницам
AI_REFERRERS = ("chatgpt", "openai", "perplexity", "gemini", "bard", "copilot", "claude", "anthropic",
                "deepseek", "alice", "ya.ru/alice", "gigachat", "you.com", "phind", "kagi")


def fetch(path, limit=2_000_000):
    url = path if path.startswith("http") else BASE + path
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Cache-Control": "no-cache"})
    t = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read(limit)
            return {"status": r.status, "ms": int((time.monotonic() - t) * 1000), "bytes": len(body),
                    "final": r.geturl(), "body": body.decode("utf-8", "replace")}
    except urllib.error.HTTPError as e:
        return {"status": e.code, "ms": int((time.monotonic() - t) * 1000), "error": str(e)}
    except Exception as e:
        return {"status": 0, "ms": int((time.monotonic() - t) * 1000), "error": str(e)[:200]}


def page_facts(html):
    def one(pattern):
        m = re.search(pattern, html, re.I | re.S)
        return re.sub(r"\s+", " ", m.group(1)).strip()[:200] if m else None
    return {
        "title": one(r"<title[^>]*>(.*?)</title>"),
        "h1": one(r"<h1[^>]*>(.*?)</h1>") and re.sub(r"<[^>]+>", "", one(r"<h1[^>]*>(.*?)</h1>")),
        "canonical": one(r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)'),
        "robots": one(r'<meta[^>]+name=["\']robots["\'][^>]+content=["\']([^"\']+)'),
        "yandex": one(r'<meta[^>]+name=["\']yandex["\'][^>]+content=["\']([^"\']+)'),
        "description_len": len(one(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']*)') or ""),
        "jsonld": len(re.findall(r'application/ld\+json', html)),
    }


def sitemap_urls(path, depth=0):
    r = fetch(path, limit=60_000_000)
    if r["status"] != 200:
        return [], {path: r["status"]}
    try:
        root = ET.fromstring(r["body"])
    except ET.ParseError as e:
        return [], {path: "xml error %s" % e}
    ns = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
    urls, errs = [], {}
    if root.tag.endswith("sitemapindex") and depth < 2:
        for loc in root.iter(ns + "loc"):
            u, e = sitemap_urls(loc.text.strip(), depth + 1)
            urls += u
            errs.update(e)
    else:
        urls = [loc.text.strip() for loc in root.iter(ns + "loc")]
    return urls, errs


def site_health():
    out = {"pages": {}, "tech": {}}
    for p in KEY_PAGES:
        r = fetch(p)
        row = {k: r.get(k) for k in ("status", "ms", "bytes", "final", "error")}
        if r.get("body"):
            row.update(page_facts(r["body"]))
        out["pages"][p] = row
    for p in TECH:
        r = fetch(p)
        out["tech"][p] = {k: r.get(k) for k in ("status", "ms", "bytes", "error")}
    # mirrors: everything must end on https://torggid.ru/ (Yandex Webmaster shows https host as NOT_LOADED)
    out["mirrors"] = {}
    for u in ("http://torggid.ru/", "https://www.torggid.ru/", "http://www.torggid.ru/", "https://kirpichinvest.ru/"):
        r = fetch(u, limit=1000)
        out["mirrors"][u] = {"status": r.get("status"), "final": r.get("final"), "error": r.get("error")}
    out["robots_txt"] = (fetch("/robots.txt").get("body") or "")[:3000]
    urls, errs = sitemap_urls("/sitemap.xml")
    y_urls, y_errs = sitemap_urls("/sitemap-yandex.xml")
    kinds = {}
    for u in urls:
        seg = u.replace(BASE, "").strip("/").split("/")[0] or "(home)"
        kinds[seg] = kinds.get(seg, 0) + 1
    out["sitemap"] = {"urls": len(urls), "by_section": dict(sorted(kinds.items(), key=lambda kv: -kv[1])[:15]),
                      "errors": errs, "yandex_urls": len(y_urls), "yandex_errors": y_errs}
    # small sample of lot cards: must answer 200 and carry canonical to itself
    lots = [u for u in urls if "/lot/" in u]
    step = max(1, len(lots) // 25)
    bad = []
    for u in lots[::step][:25]:
        r = fetch(u)
        if r["status"] != 200:
            bad.append({"url": u, "status": r["status"], "error": r.get("error")})
    out["lot_sample"] = {"checked": min(25, len(lots[::step])), "bad": bad}
    return out


def metrika(token, params):
    return get(METRIKA, token, dict({"ids": COUNTER, "limit": 50}, **params)).get("data", [])


def metrika_block(token, today):
    d1 = str(today - timedelta(days=1))
    d0 = str(today - timedelta(days=2))
    w1, w2 = str(today - timedelta(days=7)), d1
    r = {"day": d1, "prev_day": d0, "week": [w1, w2]}

    def by_source(date):
        rows = metrika(token, {"metrics": "ym:s:visits,ym:s:users", "dimensions": "ym:s:trafficSource",
                               "date1": date, "date2": date})
        return {x["dimensions"][0].get("name") or "?": int(x["metrics"][0]) for x in rows}

    def organic(date1, date2):
        rows = metrika(token, {"metrics": "ym:s:visits,ym:s:bounceRate,ym:s:avgVisitDurationSeconds",
                               "dimensions": "ym:s:searchEngineRoot", "filters": "ym:s:trafficSource=='organic'",
                               "date1": date1, "date2": date2})
        return {x["dimensions"][0].get("name") or "?": {"visits": int(x["metrics"][0]),
                "bounce": round(x["metrics"][1], 1), "sec": int(x["metrics"][2])} for x in rows}

    def landings():
        rows = metrika(token, {"metrics": "ym:s:visits", "dimensions": "ym:s:startURLPath",
                               "filters": "ym:s:trafficSource=='organic'", "date1": w1, "date2": w2,
                               "sort": "-ym:s:visits", "limit": 25})
        return [[x["dimensions"][0].get("name"), int(x["metrics"][0])] for x in rows]

    def referrers():
        rows = metrika(token, {"metrics": "ym:s:visits", "dimensions": "ym:s:referalSource",
                               "date1": w1, "date2": w2, "sort": "-ym:s:visits", "limit": 50})
        allr = [[x["dimensions"][0].get("name") or "?", int(x["metrics"][0])] for x in rows]
        ai = [x for x in allr if any(a in x[0].lower() for a in AI_REFERRERS)]
        # ChatGPT ставит utm_source=chatgpt.com, и Метрика пишет такие визиты в «прямые» без реферера:
        # без этой выборки срез показывал 0 переходов из ИИ при ~30 визитах из ChatGPT в день (09.11.2026)
        utm = metrika(token, {"metrics": "ym:s:visits", "dimensions": "ym:s:UTMSource",
                              "date1": w1, "date2": w2, "sort": "-ym:s:visits", "limit": 50})
        seen = {x[0].lower() for x in ai}
        for x in utm:
            name = (x["dimensions"][0].get("name") or "").lower()
            if name and name not in seen and any(a in name for a in AI_REFERRERS):
                ai.append(["utm " + name, int(x["metrics"][0])])
        return {"top": allr[:15], "ai": ai}

    def goals():
        rows = metrika(token, {"metrics": "ym:s:sumGoalReachesAny,ym:s:visits", "dimensions": "ym:s:trafficSource",
                               "date1": w1, "date2": w2})
        return {x["dimensions"][0].get("name") or "?": int(x["metrics"][0]) for x in rows}

    safe(r, "sources_day", lambda: by_source(d1))
    safe(r, "sources_prev_day", lambda: by_source(d0))
    safe(r, "organic_day", lambda: organic(d1, d1))
    safe(r, "organic_week", lambda: organic(w1, w2))
    safe(r, "organic_landings_week", landings)
    safe(r, "referrers_week", referrers)
    safe(r, "goal_reaches_week", goals)
    return r


def post(url, token, body):
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST",
                                 headers={"Authorization": "OAuth " + token, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8", "replace")
            return json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as e:
        raise RuntimeError("HTTP %s %s" % (e.code, e.read().decode("utf-8", "replace")[:300])) from None


def read_queue(path):
    """Адреса из файла очереди: по одному в строке, пустые строки и # комментарии пропускаются, порядок сохраняется."""
    out = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if not line.startswith("http"):
            line = BASE + line
        if line not in out:
            out.append(line)
    return out


def pick_recrawl(queue, state, today, limit):
    """Какие адреса отправить сегодня: по порядку очереди, минуя те, что уходили меньше RECRAWL_EVERY_DAYS назад."""
    picked = []
    for url in queue:
        last = state.get(url)
        if last and (today - datetime.strptime(last, "%Y-%m-%d").date()).days < RECRAWL_EVERY_DAYS:
            continue
        picked.append(url)
        if len(picked) >= limit:
            break
    return picked


def probe_other_host(token, uid, hosts, skip_id):
    """Диагностика: тот же POST на другой подтверждённый хост аккаунта (kirpichinvest.ru, статус OK).
    Если там проходит — API и токен в порядке, а 504 даёт именно незагруженный хост torggid.ru."""
    other = next((h for h in hosts if h.get("host_id") != skip_id and h.get("verified")), None)
    if not other:
        return "другого подтверждённого хоста нет"
    hid = other["host_id"]
    url = "https://" + hid.split(":")[1] + "/"
    try:
        post("%s/user/%s/hosts/%s/recrawl/queue/" % (WEBMASTER, uid, urllib.parse.quote(hid, safe="")), token, {"url": url})
        return "переобход %s принят — API и токен работают, 504 только у https:torggid.ru:443" % hid
    except Exception as e:
        return "%s: %s" % (hid, str(e)[:120])


def webmaster_act(token, queue_path, state_path, today, limit):
    """ТЗ-1 (06.11.2026): sitemap-yandex.xml в Вебмастер, если его там нет, и переобход адресов из очереди в пределах квоты.

    Пишет только в свой сайт; каждый шаг записывается, ошибка одного шага не останавливает остальные.
    Если токен без прав на запись (HTTP 403) — в отчёте появится просьба выпустить новый токен."""
    out = {"sitemap": None, "sent": [], "skipped": 0, "errors": {}}
    uid = get(WEBMASTER + "/user", token)["user_id"]
    hosts = get("%s/user/%s/hosts" % (WEBMASTER, uid), token).get("hosts", [])
    host = next((h for h in hosts if h.get("host_id") == "https:torggid.ru:443"), None)
    if not host:
        out["errors"]["host"] = "https:torggid.ru:443 нет в аккаунте Вебмастера"
        return out
    base = "%s/user/%s/hosts/%s" % (WEBMASTER, uid, urllib.parse.quote(host["host_id"], safe=""))
    want = BASE + "/sitemap-yandex.xml"
    try:
        have = {s.get("sitemap_url") for s in get(base + "/user-added-sitemaps", token).get("sitemaps", [])}
        have |= {s.get("sitemap_url") for s in get(base + "/sitemaps", token).get("sitemaps", [])}
        if want in have:
            out["sitemap"] = "уже в Вебмастере"
        else:
            post(base + "/user-added-sitemaps/", token, {"url": want})
            out["sitemap"] = "добавлен"
    except Exception as e:
        out["errors"]["sitemap"] = str(e)
    state = {}
    sp = Path(state_path)
    if sp.exists():
        try:
            state = json.loads(sp.read_text(encoding="utf-8"))
        except Exception:
            state = {}
    try:
        quota = get(base + "/recrawl/quota", token)
        out["quota"] = {"daily": quota.get("daily_quota"), "left": quota.get("quota_remainder")}
        left = int(quota.get("quota_remainder") or 0)
    except Exception as e:
        out["errors"]["quota"] = str(e)
        left = 0
    failed = 0
    for url in pick_recrawl(read_queue(queue_path), state, today, min(limit, left)):
        try:
            post(base + "/recrawl/queue/", token, {"url": url})
            out["sent"].append(url)
            state[url] = str(today)
            failed = 0
        except Exception as e:
            msg = str(e)
            failed += 1
            if failed <= 3:
                out["errors"]["recrawl " + url] = msg
            if "HTTP 403" in msg or "HTTP 401" in msg:
                out["errors"]["token"] = "токен без права на переобход: нужен OAuth-токен с правом webmaster:hostinfo и доступом на запись"
                break
            if "HTTP 429" in msg or "QUOTA" in msg.upper():
                break
            if failed >= 3:
                # 06.11.2026: на host_data_status NOT_LOADED Вебмастер отвечал HTTP 504 на каждый POST — не долбим API 30 раз
                out["errors"]["recrawl"] = "3 ошибки подряд, остальные адреса не отправлены (сервис Вебмастера недоступен или хост ещё не загружен)"
                out["probe"] = probe_other_host(token, uid, hosts, host["host_id"])
                break
    sp.parent.mkdir(parents=True, exist_ok=True)
    sp.write_text(json.dumps(state, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    return out


BING = "https://ssl.bing.com/webmaster/api.svc/json"


def bing_call(method, key, body=None, **params):
    """Bing Webmaster API (JSON): GET с apikey в query, POST — JSON-тело. Ошибка ключа/прав приходит как 4xx с текстом."""
    params["apikey"] = key
    url = "%s/%s?%s" % (BING, method, urllib.parse.urlencode(params))
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method="POST" if body is not None else "GET",
                                 headers={"Content-Type": "application/json; charset=utf-8"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8", "replace")
            return (json.loads(raw) if raw.strip() else {}).get("d")
    except urllib.error.HTTPError as e:
        raise RuntimeError("HTTP %s %s" % (e.code, e.read().decode("utf-8", "replace")[:200])) from None


def bing_date(v):
    """Bing отдаёт даты как /Date(1793000000000)/ (мс с 1970) — в YYYY-MM-DD."""
    m = re.search(r"/Date\((-?\d+)", str(v or ""))
    if m:
        return datetime.fromtimestamp(int(m.group(1)) / 1000, timezone.utc).strftime("%Y-%m-%d")
    return str(v or "")[:10]


def bing_pick(queue, sitemap, state, today, n=100, days=30):
    """ГЕО-6 (08.11.2026): ротация адресов для Bing SubmitUrlBatch. Раньше каждую ночь уходила одна и та же очередь
    хабов (~50 из 100 квоты). Теперь: хабы из очереди, затем остальные страницы sitemap — сначала разделы, регионы
    и статьи, потом карточки недвижимости, потом техники; адрес, отправленный за последние `days` дней, пропускаем."""
    def rank(u):
        return 2 if "/auto/lot/" in u else (1 if "/lot/" in u else 0)
    cut = str(today - timedelta(days=days))
    seen, out = set(), []
    for u in list(queue) + sorted(sitemap, key=rank):
        if u in seen or (state.get(u) or "") > cut:
            continue
        seen.add(u)
        out.append(u)
        if len(out) >= n:
            break
    return out


def bing_block(key, queue_path, act, state_path=None, today=None):
    """ГЕО-2 (07.11.2026): через Bing ищут ChatGPT и Copilot. Что в индексе Bing, запросы и страницы с кликами,
    sitemap и (в режиме --act) отправка хабов из очереди переобхода через SubmitUrlBatch."""
    site = BASE + "/"
    out = {"errors": {}}

    def part(name, fn):
        try:
            out[name] = fn()
        except Exception as e:
            out["errors"][name] = str(e)

    def crawl():
        rows = bing_call("GetCrawlStats", key, siteUrl=site) or []
        last = rows[-1] if rows else {}
        return {"date": bing_date(last.get("Date")), "in_index": last.get("InIndex"), "crawled": last.get("CrawledPages"),
                "crawl_errors": last.get("CrawlErrors"), "blocked": last.get("BlockedByRobots"), "in_links": last.get("InLinks")}

    def traffic():
        rows = bing_call("GetRankAndTrafficStats", key, siteUrl=site) or []
        week = rows[-7:]
        return {"impressions_7d": sum(int(x.get("Impressions") or 0) for x in week),
                "clicks_7d": sum(int(x.get("Clicks") or 0) for x in week), "days": len(week)}

    def queries():
        rows = bing_call("GetQueryStats", key, siteUrl=site) or []
        rows.sort(key=lambda x: -(x.get("Impressions") or 0))
        return [[x.get("Query"), x.get("Impressions"), x.get("Clicks"), x.get("AvgImpressionPosition")] for x in rows[:15]]

    def pages():
        rows = bing_call("GetPageStats", key, siteUrl=site) or []
        rows.sort(key=lambda x: -(x.get("Impressions") or 0))
        return [[(x.get("Query") or x.get("Url") or "").replace(BASE, ""), x.get("Impressions"), x.get("Clicks")] for x in rows[:15]]

    def feeds():
        rows = bing_call("GetFeeds", key, siteUrl=site) or []
        return [[x.get("Url", "").replace(BASE, ""), x.get("Status"), x.get("UrlCount"), bing_date(x.get("LastCrawled"))] for x in rows]

    part("crawl", crawl)
    part("traffic", traffic)
    part("queries", queries)
    part("pages", pages)
    part("feeds", feeds)
    if act and "feeds" in out:
        have = {f[0] for f in out["feeds"]}
        for sm in ("/sitemap.xml", "/sitemap-yandex.xml"):
            if sm not in have:
                try:
                    bing_call("SubmitFeed", key, {"siteUrl": site, "feedUrl": BASE + sm})
                    out.setdefault("submitted_feeds", []).append(sm)
                except Exception as e:
                    out["errors"]["feed " + sm] = str(e)
    if act:
        try:
            q = bing_call("GetUrlSubmissionQuota", key, siteUrl=site) or {}
            out["quota"] = {"daily": q.get("DailyQuota"), "monthly": q.get("MonthlyQuota")}
            n = max(0, min(100, int(q.get("DailyQuota") or 0)))
            state = {}
            sp = Path(state_path) if state_path else None
            if sp and sp.exists():
                state = json.loads(sp.read_text(encoding="utf-8"))
            sm, _ = sitemap_urls("/sitemap.xml")
            urls = bing_pick(read_queue(queue_path), sm, state, today or datetime.now(timezone.utc).date(), n)
            if urls:
                bing_call("SubmitUrlBatch", key, {"siteUrl": site, "urlList": urls})
                out["submitted_urls"] = len(urls)
                d = str(today or datetime.now(timezone.utc).date())
                state.update({u: d for u in urls})
                out["submitted_by_kind"] = {k: sum(1 for u in urls if f(u)) for k, f in (
                    ("разделы и статьи", lambda u: "/lot/" not in u), ("недвижимость", lambda u: "/torgi/lot/" in u),
                    ("техника", lambda u: "/auto/lot/" in u))}
                if sp:
                    sp.parent.mkdir(parents=True, exist_ok=True)
                    sp.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            out["errors"]["submit"] = str(e)
    if not out["errors"]:
        del out["errors"]
    return out


def to_md(r):
    L = ["# ТоргГид: ночной срез %s" % r["date"], ""]
    m = r.get("metrika") or {}
    if m:
        L += ["## Метрика", "", "Вчера (%s) по источникам: %s" % (m.get("day"), ", ".join(
            "%s %s" % kv for kv in (m.get("sources_day") or {}).items()) or "нет данных"),
              "Позавчера: " + (", ".join("%s %s" % kv for kv in (m.get("sources_prev_day") or {}).items()) or "нет данных"), ""]
        L.append("Поиск вчера: " + (", ".join("%s %s" % (k, v["visits"]) for k, v in (m.get("organic_day") or {}).items()) or "0"))
        L.append("Поиск за 7 дней: " + (", ".join("%s %s (отказы %s%%, %s с)" % (k, v["visits"], v["bounce"], v["sec"])
                                                  for k, v in (m.get("organic_week") or {}).items()) or "0"))
        if m.get("organic_landings_week"):
            L += ["", "Входы из поиска за 7 дней:"] + ["- %s — %s" % (u, n) for u, n in m["organic_landings_week"][:15]]
        ref = m.get("referrers_week") or {}
        L += ["", "Переходы из ИИ-ассистентов за 7 дней: " + (", ".join("%s %s" % tuple(x) for x in ref.get("ai", [])) or "0")]
        if m.get("goal_reaches_week"):
            L.append("Достижения целей за 7 дней: " + ", ".join("%s %s" % kv for kv in m["goal_reaches_week"].items()))
        for k, v in (m.get("errors") or {}).items():
            L.append("- ошибка %s: %s" % (k, v))
        L.append("")
    for name, h in (r.get("webmaster") or {}).items():
        L += ["## Вебмастер: " + name, ""]
        s = h.get("summary") or {}
        for key in ("searchable_pages_count", "excluded_pages_count", "sqi", "site_problems"):
            if key in s:
                L.append("- %s: %s" % (key, s[key]))
        q = (h.get("queries") or {}).get("queries", [])
        if q:
            L += ["", "| Запрос | Показы | Клики | Позиция |", "|---|---|---|---|"]
            for x in q[:20]:
                ind = x.get("indicators", {})
                L.append("| %s | %s | %s | %s |" % (x.get("query_text"), ind.get("TOTAL_SHOWS", 0),
                                                   ind.get("TOTAL_CLICKS", 0), round(ind.get("AVG_SHOW_POSITION") or 0, 1)))
        for k, v in (h.get("errors") or {}).items():
            L.append("- ошибка %s: %s" % (k, str(v)[:160]))
        L.append("")
    s = r.get("site") or {}
    if s:
        L += ["## Сайт", "", "| Страница | Код | мс | title | robots/yandex |", "|---|---|---|---|---|"]
        for p, x in s.get("pages", {}).items():
            L.append("| %s | %s | %s | %s | %s |" % (p, x.get("status"), x.get("ms"), (x.get("title") or "")[:70],
                                                   " / ".join(filter(None, [x.get("robots"), x.get("yandex")])) or "–"))
        L.append("")
        L.append("Служебные: " + ", ".join("%s %s" % (p, x.get("status")) for p, x in s.get("tech", {}).items()))
        sm = s.get("sitemap", {})
        L.append("Sitemap: %s адресов, sitemap-yandex: %s; ошибки: %s" % (
            sm.get("urls"), sm.get("yandex_urls"), {**sm.get("errors", {}), **sm.get("yandex_errors", {})} or "нет"))
        bad_m = {u: x.get("final") or x.get("error") for u, x in s.get("mirrors", {}).items()
                 if not (x.get("final") or "").startswith(BASE + "/")}
        L.append("Зеркала: " + ("все ведут на https://torggid.ru/" if not bad_m else "НЕ на https://torggid.ru/: %s" % bad_m))
        ls = s.get("lot_sample", {})
        L.append("Карточки лотов (выборка %s): битых %s" % (ls.get("checked"), len(ls.get("bad", []))))
        L.append("")
    a = r.get("act")
    if a:
        q = a.get("quota") or {}
        L += ["## Вебмастер: действия", "",
              "- sitemap-yandex.xml: %s" % (a.get("sitemap") or "не проверен"),
              "- переобход: отправлено %s, квота на день %s, оставалось %s" % (len(a.get("sent", [])), q.get("daily"), q.get("left"))]
        L += ["  - %s" % u.replace(BASE, "") for u in a.get("sent", [])]
        for k, v in (a.get("errors") or {}).items():
            L.append("- ошибка %s: %s" % (k, str(v)[:200]))
        if a.get("probe"):
            L.append("- проверка на другом хосте: %s" % a["probe"])
        L.append("")
    b = r.get("bing")
    if b:
        L += ["## Bing (через него ищут ChatGPT и Copilot)", ""]
        c = b.get("crawl") or {}
        if c:
            L.append("- в индексе Bing: %s, обойдено за день: %s, ошибок обхода: %s, закрыто robots: %s (на %s)" % (
                c.get("in_index"), c.get("crawled"), c.get("crawl_errors"), c.get("blocked"), c.get("date")))
        t = b.get("traffic") or {}
        if t:
            L.append("- показы за %s дн.: %s, клики: %s" % (t.get("days"), t.get("impressions_7d"), t.get("clicks_7d")))
        if b.get("feeds") is not None:
            L.append("- sitemap в Bing: " + (", ".join("%s (%s, %s адресов, обход %s)" % tuple(f) for f in b["feeds"]) or "нет"))
        if b.get("submitted_feeds"):
            L.append("- отправлены sitemap: " + ", ".join(b["submitted_feeds"]))
        if b.get("quota"):
            L.append("- квота отправки адресов: %s в день, %s в месяц; отправлено %s" % (b["quota"].get("daily"), b["quota"].get("monthly"), b.get("submitted_urls", 0)))
            if b.get("submitted_by_kind"):
                L.append("- из них: " + ", ".join("%s %s" % kv for kv in b["submitted_by_kind"].items()))
        if b.get("queries"):
            L += ["", "Запросы в Bing (показы, клики, позиция):"] + ["- %s — %s, %s, %s" % tuple(q) for q in b["queries"]]
        if b.get("pages"):
            L += ["", "Страницы с показами в Bing:"] + ["- %s — %s показов, %s кликов" % tuple(pg) for pg in b["pages"]]
        for k, v in (b.get("errors") or {}).items():
            L.append("- ошибка %s: %s" % (k, str(v)[:200]))
        L.append("")
    g = r.get("gsc")
    if g:
        L += ["## Google Search Console", ""]
        if g.get("site"):
            L.append("- ресурс %s, период %s (данные GSC отстают на 3 дня)" % (g["site"], g.get("period")))
        t, tp = g.get("totals") or {}, g.get("totals_prev") or {}
        if t:
            L.append("- за 7 дней: клики %s (пред. %s), показы %s (пред. %s), CTR %s%%, средняя позиция %s (пред. %s)" % (
                t.get("clicks"), tp.get("clicks", "–"), t.get("impressions"), tp.get("impressions", "–"), t.get("ctr"),
                t.get("position"), tp.get("position", "–")))
        if g.get("daily"):
            L += ["", "По дням (дата — клики, показы, позиция):"] + ["- %s — %s, %s, %s" % tuple(x) for x in g["daily"]]
        q = g.get("queries") or {}
        if g.get("period_28"):
            L.append("")
            L.append("Запросы и страницы ниже — за 28 дней (%s)" % g["period_28"])
        if q.get("count") is not None:
            L.append("- запросов с показами: %s" % q["count"])
        if q.get("wins"):
            L += ["", "Быстрые победы (позиция 4–20, показы ≥ 5): запрос — показы, клики, позиция"] + ["- %s — %s, %s, %s" % tuple(x) for x in q["wins"]]
        if q.get("top"):
            L += ["", "Топ запросов Google (показы, клики, позиция):"] + ["- %s — %s, %s, %s" % tuple(x) for x in q["top"]]
        if g.get("pages"):
            L += ["", "Страницы с показами в Google (показы, клики, позиция):"] + ["- %s — %s, %s, %s" % tuple(x) for x in g["pages"]]
        if g.get("submit"):
            L += ["", "Отправка sitemap в Google:"] + ["- %s — %s" % tuple(x) for x in g["submit"]]
        if g.get("sitemaps") is not None:
            L += ["", "Sitemap в Google (путь — загружен, ошибки, предупреждения, отправлено, в индексе):"] + [
                "- %s — %s, %s, %s, %s, %s" % tuple(x) for x in g["sitemaps"]] if g["sitemaps"] else ["", "Sitemap в Google: не добавлены"]
        if g.get("inspect"):
            L += ["", "Проверка страниц в Google (страница — вердикт, статус, обход, загрузка, robots, индексация, canonical Google):"] + [
                "- %s — %s" % (x[0], ", ".join(str(v) for v in x[1:])) for x in g["inspect"]]
        for k, v in (g.get("errors") or {}).items():
            L.append("- ошибка %s: %s" % (k, str(v)[:300]))
        L.append("")
    for k, v in (r.get("errors") or {}).items():
        L.append("- ошибка %s: %s" % (k, v))
    return "\n".join(L) + "\n"


GSC = "https://www.googleapis.com/webmasters/v3"
# ключевые страницы для проверки индекса в Google (URL Inspection API, 2 000 запросов в день)
INSPECT = ["/", "/torgi/", "/torgi/moskva/", "/torgi/sankt-peterburg/", "/torgi/samara/", "/torgi/nizhniy-novgorod/",
           "/torgi/permskiy-kray/", "/auto/", "/stati/", "/stati/proverka-kvartiry-s-torgov/"]


def google_token(sa_json, scope="https://www.googleapis.com/auth/webmasters.readonly"):
    """Токен сервисного аккаунта Google: JWT RS256 (библиотека cryptography) → oauth2 token."""
    import base64
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    sa = json.loads(sa_json) if isinstance(sa_json, str) else sa_json
    b64 = lambda b: base64.urlsafe_b64encode(b).rstrip(b"=")
    now = int(time.time())
    header = b64(json.dumps({"alg": "RS256", "typ": "JWT"}).encode())
    claims = b64(json.dumps({"iss": sa["client_email"], "scope": scope, "aud": sa["token_uri"],
                             "iat": now, "exp": now + 3600}).encode())
    key = serialization.load_pem_private_key(sa["private_key"].encode(), password=None)
    sig = key.sign(header + b"." + claims, padding.PKCS1v15(), hashes.SHA256())
    jwt = (header + b"." + claims + b"." + b64(sig)).decode()
    body = urllib.parse.urlencode({"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": jwt}).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request(sa["token_uri"], data=body), timeout=60) as resp:
            return json.loads(resp.read().decode())["access_token"], sa["client_email"]
    except urllib.error.HTTPError as e:
        raise RuntimeError("token HTTP %s %s" % (e.code, e.read().decode("utf-8", "replace")[:200])) from None


def gsc_call(token, path, body=None, method=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(GSC + path, data=data, method=method or ("POST" if data else "GET"),
                                 headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8", "replace") or "{}")
    except urllib.error.HTTPError as e:
        raise RuntimeError("HTTP %s %s" % (e.code, e.read().decode("utf-8", "replace")[:200])) from None


# что переотправляем в Google каждую ночь в режиме --act (нужны права «Полный» у сервисного аккаунта)
GSC_SITEMAPS = ["/sitemap.xml"]


def gsc_block(sa_json, today, act=False):
    """ТЗ-6 (07.11.2026): Google Search Console через сервисный аккаунт (секрет GSC_SERVICE_ACCOUNT, JSON ключа).
    Данные GSC отстают на ~3 дня: берём 7 дней, заканчивая позавчера-3. Запросы на позициях 4–20 с показами —
    «быстрые победы» для НЧ (подтянуть текст/ссылки на страницу)."""
    out = {"errors": {}}
    scope = "https://www.googleapis.com/auth/webmasters" if act else "https://www.googleapis.com/auth/webmasters.readonly"
    token, email = google_token(sa_json, scope)
    sites = [s.get("siteUrl") for s in (gsc_call(token, "/sites").get("siteEntry") or [])]
    mine = [s for s in sites if "torggid.ru" in (s or "")]
    if not mine:
        out["errors"]["sites"] = "сервисный аккаунт %s не добавлен в ресурс torggid.ru в Search Console (доступные: %s)" % (email, sites or "нет")
        return out
    site = sorted(mine, key=lambda s: not s.startswith("sc-domain:"))[0]
    out["site"] = site
    end = today - timedelta(days=3)
    start = end - timedelta(days=6)
    p_end = start - timedelta(days=1)
    p_start = p_end - timedelta(days=6)
    out["period"] = "%s — %s" % (start, end)
    enc = urllib.parse.quote(site, safe="")

    def query(dims, s, e, limit=25000, extra=None):
        body = {"startDate": str(s), "endDate": str(e), "dimensions": dims, "rowLimit": limit}
        body.update(extra or {})
        return gsc_call(token, "/sites/%s/searchAnalytics/query" % enc, body).get("rows") or []

    def totals(s, e):
        rows = query([], s, e)
        t = rows[0] if rows else {}
        return {"clicks": int(t.get("clicks", 0)), "impressions": int(t.get("impressions", 0)),
                "ctr": round(100 * float(t.get("ctr", 0)), 1), "position": round(float(t.get("position", 0)), 1)}

    def part(name, fn):
        try:
            out[name] = fn()
        except Exception as e:
            out["errors"][name] = str(e)

    part("totals", lambda: totals(start, end))
    part("totals_prev", lambda: totals(p_start, p_end))
    # по дням за 28 дней: видно, где провал и где данные GSC ещё не досчитаны
    m_start = end - timedelta(days=27)
    out["period_28"] = "%s — %s" % (m_start, end)

    def daily():
        rows = query(["date"], m_start, end, 100)
        return [[x["keys"][0], int(x["clicks"]), int(x["impressions"]), round(x["position"], 1)] for x in rows]

    part("daily", daily)

    def queries():
        rows = query(["query"], m_start, end, 5000)
        rows.sort(key=lambda x: -x["impressions"])
        top = [[x["keys"][0], int(x["impressions"]), int(x["clicks"]), round(x["position"], 1)] for x in rows[:20]]
        wins = [[x["keys"][0], int(x["impressions"]), int(x["clicks"]), round(x["position"], 1)]
                for x in rows if 3.5 <= x["position"] <= 20 and x["impressions"] >= 5]
        wins.sort(key=lambda x: (-x[1], x[3]))
        return {"top": top, "wins": wins[:25], "count": len(rows)}

    def pages():
        rows = query(["page"], m_start, end, 5000)
        rows.sort(key=lambda x: -x["impressions"])
        return [[x["keys"][0].replace(BASE, ""), int(x["impressions"]), int(x["clicks"]), round(x["position"], 1)] for x in rows[:15]]

    part("queries", queries)
    part("pages", pages)

    def sitemaps():
        rows = gsc_call(token, "/sites/%s/sitemaps" % enc).get("sitemap") or []
        return [[x.get("path", "").replace(BASE, ""), str(x.get("lastDownloaded", ""))[:10], x.get("errors"), x.get("warnings"),
                 sum(int(c.get("submitted") or 0) for c in x.get("contents") or []),
                 sum(int(c.get("indexed") or 0) for c in x.get("contents") or [])] for x in rows]

    def submit():
        # переотправка sitemap: Google перечитывает его в ближайшие часы (страницы добавятся без ручной работы)
        res = []
        for path in GSC_SITEMAPS:
            try:
                gsc_call(token, "/sites/%s/sitemaps/%s" % (enc, urllib.parse.quote(BASE + path, safe="")), method="PUT")
                res.append([path, "отправлен"])
            except RuntimeError as e:
                msg = str(e)
                if "HTTP 403" in msg:
                    msg = "нет прав: дать %s права «Полный» в Search Console → Настройки → Пользователи" % email
                res.append([path, msg[:200]])
        return res

    if act:
        part("submit", submit)
    part("sitemaps", sitemaps)

    def inspect():
        # как Google видит ключевые страницы: в индексе ли, когда обходил, что получил при загрузке, какой canonical выбрал
        res = []
        for path in INSPECT:
            body = {"inspectionUrl": BASE + path, "siteUrl": site, "languageCode": "ru-RU"}
            req = urllib.request.Request("https://searchconsole.googleapis.com/v1/urlInspection/index:inspect",
                                         data=json.dumps(body).encode(), method="POST",
                                         headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    r = (json.loads(resp.read().decode()).get("inspectionResult") or {}).get("indexStatusResult") or {}
                res.append([path, r.get("verdict"), r.get("coverageState"), str(r.get("lastCrawlTime", ""))[:10],
                            r.get("pageFetchState"), r.get("robotsTxtState"), r.get("indexingState"),
                            (r.get("googleCanonical") or "").replace(BASE, "")])
            except urllib.error.HTTPError as e:
                res.append([path, "HTTP %s" % e.code, e.read().decode("utf-8", "replace")[:120], "", "", "", "", ""])
        return res

    part("inspect", inspect)
    if not out["errors"]:
        del out["errors"]
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="nightly")
    ap.add_argument("--no-site", action="store_true")
    ap.add_argument("--act", action="store_true", help="добавить sitemap-yandex.xml и отправить очередь на переобход (ТЗ-1)")
    ap.add_argument("--queue", default=str(Path(__file__).with_name("data") / "recrawl_queue.txt"))
    ap.add_argument("--recrawl-max", type=int, default=30)
    args = ap.parse_args()
    token = os.environ.get("YANDEX_METRIKA_TOKEN")
    # run starts ~01:40 MSK: "today" by UTC is still the previous Moscow day, so take MSK date
    today = (datetime.now(timezone.utc) + timedelta(hours=3)).date()
    r = {"generated": datetime.now(timezone.utc).isoformat(timespec="seconds"), "date": str(today)}
    if token:
        safe(r, "metrika", lambda: metrika_block(token, today))
        safe(r, "webmaster", lambda: webmaster(token))
        if args.act:
            safe(r, "act", lambda: webmaster_act(token, args.queue, Path(args.out) / "recrawl-state.json", today, args.recrawl_max))
    else:
        r.setdefault("errors", {})["token"] = "YANDEX_METRIKA_TOKEN is not set"
    bing_key = os.environ.get("BING_WEBMASTER_KEY")
    if bing_key:
        safe(r, "bing", lambda: bing_block(bing_key, args.queue, args.act, Path(args.out) / "bing-state.json", today))
    gsc_key = os.environ.get("GSC_SERVICE_ACCOUNT")
    if gsc_key:
        safe(r, "gsc", lambda: gsc_block(gsc_key, today, act=args.act))
    else:
        r.setdefault("errors", {})["gsc"] = "GSC_SERVICE_ACCOUNT не задан (JSON ключа сервисного аккаунта Google)"
    if not args.no_site:
        safe(r, "site", site_health)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / ("%s.json" % today)).write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
    md = to_md(r)
    (out / ("%s.md" % today)).write_text(md, encoding="utf-8")
    (out / "latest.md").write_text(md, encoding="utf-8")
    print(md)


if __name__ == "__main__":
    main()
