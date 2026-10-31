"""Weekly Yandex numbers for torggid.ru: Metrika visits by search engine and Webmaster indexing.

Read-only: only GET requests (no move, sitemap or recrawl changes).
Token comes from YANDEX_METRIKA_TOKEN (OAuth, scopes metrika:read and webmaster:hostinfo).
Writes <out>/<date>.json and <out>/<date>.md; each failed call is recorded, not fatal.
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

COUNTER = "113591344"
HOSTS = ("torggid.ru", "kirpichinvest.ru")
METRIKA = "https://api-metrika.yandex.net/stat/v1/data"
WEBMASTER = "https://api.webmaster.yandex.net/v4"


def get(url, token, params=None):
    if params:
        url += "?" + urllib.parse.urlencode(params, doseq=True)
    req = urllib.request.Request(url, headers={"Authorization": "OAuth " + token})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:300]
        raise RuntimeError("HTTP %s %s" % (e.code, body)) from None


def safe(result, key, fn):
    try:
        result[key] = fn()
    except Exception as e:  # keep going: one scope missing must not hide the rest
        result.setdefault("errors", {})[key] = str(e)


def metrika_visits(token, date1, date2):
    data = get(METRIKA, token, {
        "ids": COUNTER,
        "metrics": "ym:s:visits,ym:s:bounceRate,ym:s:pageDepth",
        "dimensions": "ym:s:searchEngineRoot",
        "filters": "ym:s:trafficSource=='organic'",
        "date1": date1, "date2": date2, "limit": 20,
    })
    rows = {}
    for r in data.get("data", []):
        name = r["dimensions"][0].get("name") or "?"
        visits, bounce, depth = r["metrics"]
        rows[name] = {"visits": int(visits), "bounce": round(bounce, 1), "depth": round(depth, 2)}
    return rows


def metrika_total(token, date1, date2):
    data = get(METRIKA, token, {
        "ids": COUNTER, "metrics": "ym:s:visits", "dimensions": "ym:s:trafficSource",
        "date1": date1, "date2": date2, "limit": 20,
    })
    return {r["dimensions"][0].get("name") or "?": int(r["metrics"][0]) for r in data.get("data", [])}


GOAL_WORDS = ("signup", "login", "hunt", "watch", "регистр", "lead", "заявк")


def metrika_goals(token):
    data = get("https://api-metrika.yandex.net/management/v1/counter/%s/goals" % COUNTER, token)
    goals = [(g["id"], g.get("name", "")) for g in data.get("goals", [])]
    return [g for g in goals if any(w in g[1].lower() for w in GOAL_WORDS)][:8]


def metrika_ads(token, date1, date2):
    """Рекламные визиты: по меткам UTM, устройствам и страницам входа, с целями."""
    goals = metrika_goals(token)
    gm = ["ym:s:goal%sreaches" % gid for gid, _ in goals]
    base = ["ym:s:visits", "ym:s:bounceRate", "ym:s:pageDepth", "ym:s:avgVisitDurationSeconds"]

    def rows(dims, filters, limit=60):
        data = get(METRIKA, token, {"ids": COUNTER, "metrics": ",".join(base + gm), "dimensions": dims,
                                    "filters": filters, "date1": date1, "date2": date2, "limit": limit,
                                    "sort": "-ym:s:visits"})
        out = []
        for r in data.get("data", []):
            m = r["metrics"]
            out.append({"dims": [d.get("name") or "–" for d in r["dimensions"]], "visits": int(m[0]),
                        "bounce": round(m[1], 1), "depth": round(m[2], 2), "sec": round(m[3]),
                        "goals": [int(x) for x in m[4:]]})
        return out

    ad = "ym:s:trafficSource=='ad' OR ym:s:UTMSource!=''"
    return {"period": [date1, date2], "goals": [n for _, n in goals],
            "utm": rows("ym:s:UTMSource,ym:s:UTMCampaign,ym:s:UTMContent", ad),
            "device": rows("ym:s:UTMSource,ym:s:deviceCategory", ad, 30),
            "landing": rows("ym:s:UTMSource,ym:s:startURLPath", ad, 30)}


def ads_md(a):
    head = "| Визиты | Отказы, % | Глубина | Сек. | " + " | ".join(a["goals"]) + " |"
    sep = "---|" * (4 + len(a["goals"]))
    lines = ["## Реклама: визиты по меткам (%s – %s)" % tuple(a["period"]), "",
             "Отказ = визит короче 15 секунд с одной страницей (accurateTrackBounce).", ""]
    for key, cols in (("utm", "Источник | Кампания | Объявление"), ("device", "Источник | Устройство"),
                      ("landing", "Источник | Страница входа")):
        n = cols.count("|") + 1
        lines += ["| " + cols + " " + head, "|" + "---|" * n + sep]
        for r in a[key]:
            lines.append("| " + " | ".join(r["dims"]) + " | %s | %s | %s | %s | " % (r["visits"], r["bounce"], r["depth"], r["sec"])
                         + " | ".join(str(g) for g in r["goals"]) + " |")
        lines.append("")
    return lines


def webmaster(token):
    uid = get(WEBMASTER + "/user", token)["user_id"]
    hosts = get("%s/user/%s/hosts" % (WEBMASTER, uid), token).get("hosts", [])
    out = {}
    for name in HOSTS:
        # the account can hold http:, https: and www variants; take the https one with data
        found = [h for h in hosts if (h.get("ascii_host_url") or "").rstrip("/").endswith("//" + name)]
        found.sort(key=lambda h: (not h["host_id"].startswith("https:"), not h.get("verified")))
        host = found[0] if found else None
        if not host:
            out[name] = {"errors": {"host": "not in Webmaster account"}}
            continue
        base = "%s/user/%s/hosts/%s" % (WEBMASTER, uid, urllib.parse.quote(host["host_id"], safe=""))
        h = {"host_id": host["host_id"], "verified": host.get("verified"),
             "variants": [x["host_id"] for x in found]}
        safe(h, "summary", lambda: get(base + "/summary", token))
        safe(h, "info", lambda: get(base, token))
        safe(h, "excluded_samples", lambda: get(base + "/search-urls/events/samples", token, {"limit": 100}))
        safe(h, "in_search_samples", lambda: get(base + "/search-urls/in-search/samples", token, {"limit": 100}))
        safe(h, "indexing_samples", lambda: get(base + "/indexing/samples", token, {"limit": 100}))
        safe(h, "sitemaps", lambda: get(base + "/sitemaps", token))
        safe(h, "diagnostics", lambda: get(base + "/diagnostics", token))
        if name == "torggid.ru":
            safe(h, "queries", lambda: get(base + "/search-queries/popular", token, {
                "order_by": "TOTAL_SHOWS", "limit": 30,
                "query_indicator": ["TOTAL_SHOWS", "TOTAL_CLICKS", "AVG_SHOW_POSITION"],
            }))
            safe(h, "recrawl_quota", lambda: get(base + "/recrawl/quota", token))
        out[name] = h
    return out


def to_md(r):
    lines = ["# Яндекс: цифры за %s – %s" % (r["week"][0], r["week"][1]), ""]
    m, p = r.get("metrika_week"), r.get("metrika_prev")
    if m is not None:
        lines += ["## Поисковые визиты (Метрика, %s)" % COUNTER, "", "| Поисковик | Визиты | Неделей раньше | Отказы, % | Глубина |", "|---|---|---|---|---|"]
        for name in sorted(set(m) | set(p or {}), key=lambda n: -m.get(n, {}).get("visits", 0)):
            cur = m.get(name, {})
            lines.append("| %s | %s | %s | %s | %s |" % (name, cur.get("visits", 0), (p or {}).get(name, {}).get("visits", 0),
                                                       cur.get("bounce", "–"), cur.get("depth", "–")))
        lines.append("")
    if r.get("metrika_sources"):
        lines += ["Все визиты по источникам: " + ", ".join("%s %s" % kv for kv in r["metrika_sources"].items()), ""]
    if r.get("metrika_ads"):
        lines += ads_md(r["metrika_ads"])
    for name, h in (r.get("webmaster") or {}).items():
        lines += ["## Вебмастер: " + name, ""]
        s = h.get("summary") or {}
        for key in ("searchable_pages_count", "excluded_pages_count", "sqi", "site_problems"):
            if key in s:
                lines.append("- %s: %s" % (key, s[key]))
        info = h.get("info") or {}
        if info.get("main_mirror"):
            lines.append("- main_mirror: %s" % info["main_mirror"].get("ascii_host_url"))
        ex = (h.get("excluded_samples") or {}).get("samples", [])
        if ex:
            reasons = {}
            for e in ex:
                if e.get("event") == "REMOVED_FROM_SEARCH":
                    reasons[e.get("excluded_url_status", "?")] = reasons.get(e.get("excluded_url_status", "?"), 0) + 1
            if reasons:
                lines.append("- исключения в выборке (до 100): " + ", ".join("%s %s" % kv for kv in sorted(reasons.items(), key=lambda kv: -kv[1])))
        q = (h.get("queries") or {}).get("queries", [])
        if q:
            lines += ["", "| Запрос | Показы | Клики | Позиция |", "|---|---|---|---|"]
            for x in q[:15]:
                ind = x.get("indicators", {})
                lines.append("| %s | %s | %s | %s |" % (x.get("query_text"), ind.get("TOTAL_SHOWS", 0), ind.get("TOTAL_CLICKS", 0),
                                                       round(ind.get("AVG_SHOW_POSITION") or 0, 1)))
        quota = h.get("recrawl_quota")
        if quota:
            lines.append("- переобход: квота %s, осталось %s" % (quota.get("daily_quota"), quota.get("quota_remainder")))
        for k, v in (h.get("errors") or {}).items():
            lines.append("- ошибка %s: %s" % (k, v))
        lines.append("")
    for k, v in (r.get("errors") or {}).items():
        lines.append("- ошибка %s: %s" % (k, v))
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="_project/seo/yandex-api")
    ap.add_argument("--ads-days", type=int, default=14, help="за сколько дней смотреть рекламные визиты")
    args = ap.parse_args()
    token = os.environ.get("YANDEX_METRIKA_TOKEN")
    if not token:
        sys.exit("YANDEX_METRIKA_TOKEN is not set")
    today = datetime.now(timezone.utc).date()
    d2, d1 = today - timedelta(days=1), today - timedelta(days=7)
    p2, p1 = d1 - timedelta(days=1), d1 - timedelta(days=7)
    r = {"generated": datetime.now(timezone.utc).isoformat(timespec="seconds"), "week": [str(d1), str(d2)]}
    safe(r, "metrika_week", lambda: metrika_visits(token, str(d1), str(d2)))
    safe(r, "metrika_prev", lambda: metrika_visits(token, str(p1), str(p2)))
    safe(r, "metrika_sources", lambda: metrika_total(token, str(d1), str(d2)))
    safe(r, "metrika_ads", lambda: metrika_ads(token, str(today - timedelta(days=args.ads_days)), str(today)))
    safe(r, "webmaster", lambda: webmaster(token))
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / ("%s.json" % today)).write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
    md = to_md(r)
    (out / ("%s.md" % today)).write_text(md, encoding="utf-8")
    (out / "latest.md").write_text(md, encoding="utf-8")
    print(md)


if __name__ == "__main__":
    main()
