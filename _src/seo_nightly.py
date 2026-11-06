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
                break
    sp.parent.mkdir(parents=True, exist_ok=True)
    sp.write_text(json.dumps(state, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
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
        L.append("")
    for k, v in (r.get("errors") or {}).items():
        L.append("- ошибка %s: %s" % (k, v))
    return "\n".join(L) + "\n"


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
