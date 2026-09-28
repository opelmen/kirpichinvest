"""Сборка статического сайта kirpichinvest.ru.
Данные лотов: https://check.kirpichinvest.ru/public/lots.json (снимок в data/lots.json).
Запуск: python _src/build.py  → результат в _site/"""
import json
import re
import shutil
import statistics
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import markdown
from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

SRC = Path(__file__).parent
ROOT = SRC.parent
OUT = ROOT / "_site"

cfg = SimpleNamespace(
    SITE_NAME="КирпичИнвест", SITE_URL="https://kirpichinvest.ru", SITE_PHONE="+7 995 595-54-00",
    SITE_EMAIL="fond178@gmail.com", SITE_OWNER="ИП Смирнов Илья Александрович", SITE_INN="", SITE_OGRNIP="",
    SITE_ADDRESS="Санкт-Петербург", SITE_TELEGRAM="https://t.me/smirnoffond", METRIKA_ID="",
    PRICE_BUY="", PRICE_CHECK="", LEAD_URL="https://check.kirpichinvest.ru/public/lead",
    YANDEX_VERIFICATION="", GOOGLE_VERIFICATION="", BING_VERIFICATION="", INDEXNOW_KEY="")
cfg_file = SRC / "config.json"
if cfg_file.exists():
    for k, v in json.loads(cfg_file.read_text(encoding="utf-8")).items():
        setattr(cfg, k, v)

AUTHOR = {"name": "Илья Смирнов", "role": "брокер по недвижимости и залоговым сделкам, Санкт-Петербург"}
TODAY = date.today().isoformat()


def rub(v):
    return "—" if v in (None, "") else f"{float(v):,.0f}".replace(",", " ") + " ₽"


def ld(obj):
    return Markup('<script type="application/ld+json">' + json.dumps(obj, ensure_ascii=False).replace("</", "<\\/") + "</script>")


def faq_ld(items):
    qa = [(i["q"], i["a"]) if isinstance(i, dict) else i for i in items]
    return ld({"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in qa]})


def crumbs_ld(items):
    return ld({"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": i + 1, "name": n, "item": cfg.SITE_URL + u} for i, (n, u) in enumerate(items)]})


env = Environment(loader=FileSystemLoader(SRC / "templates"), autoescape=select_autoescape(["html"]))
env.filters["rub"] = rub
def terms_list(terms):
    return [{"@type": "DefinedTerm", "name": t, "description": d, "url": f"{cfg.SITE_URL}/slovar/#{s}"} for t, s, d in terms]


env.globals.update(terms_list=terms_list, cfg=cfg, year=date.today().year, today=date.today().strftime("%d.%m.%Y"), author=AUTHOR, ld=ld, faq_ld=faq_ld, crumbs_ld=crumbs_ld)

# ---------- статьи ----------
ARTICLES = []
for f in sorted((SRC / "content").glob("*.md")):
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", f.read_text(encoding="utf-8"), re.S)
    if not m:
        continue
    meta = {k.strip(): v.strip() for k, v in (l.split(":", 1) for l in m.group(1).splitlines() if ":" in l)}
    body, faq = m.group(2), []
    if "<!-- faq -->" in body:
        body, fq = body.split("<!-- faq -->", 1)
        faq = [{"q": q.strip(), "a": a.strip()} for q, a in re.findall(r"^### (.+?)\n(.+?)(?=\n### |\Z)", fq.strip(), re.S | re.M)]
    meta.update(slug=f.stem.split("_", 1)[-1], html=markdown.markdown(body, extensions=["tables"]), faq=faq)
    ARTICLES.append(meta)

# ---------- лоты ----------
lots_path = SRC / "data" / "lots.json"
LOTS = json.loads(lots_path.read_text(encoding="utf-8")) if lots_path.exists() else []
now = datetime.now(timezone.utc)
for d in LOTS:
    if d.get("bidd_end"):
        try:
            end = datetime.fromisoformat(str(d["bidd_end"]).replace("Z", "+00:00"))
            end = end if end.tzinfo else end.replace(tzinfo=timezone.utc)
            d["days_left"] = (end - now).total_seconds() / 86400
        except ValueError:
            d["days_left"] = None
LOTS = [d for d in LOTS if d.get("days_left") is None or d["days_left"] >= 0]

LOTS.sort(key=lambda d: d.get("first_seen") or "", reverse=True)


def translit(s):
    t = dict(zip("абвгдеёжзийклмнопрстуфхцчшщъыьэюя", ["a", "b", "v", "g", "d", "e", "e", "zh", "z", "i", "y", "k", "l", "m", "n", "o", "p", "r", "s", "t", "u", "f", "h", "c", "ch", "sh", "sch", "", "y", "", "e", "yu", "ya"]))
    return re.sub(r"-+", "-", "".join(t.get(c, c if c.isalnum() else "-") for c in s.lower())).strip("-")


def clean_address(d):
    """Адрес без персональных данных должника и служебного текста извещения."""
    a = str(d.get("address") or d.get("name") or "")
    m = re.search(r"(?:по\s+адресу|адрес)[:\s]+(.+)$", a, re.I)
    if m:
        a = m.group(1)
    elif re.search(r"должник|взыскател|принадлежащ", a, re.I):
        a = ""
    a = re.sub(r"\bСПБ\b|Санкт-Петербург г\.?", "Санкт-Петербург", a)
    a = re.sub(r"обл\.\s*Ленинградская", "Ленинградская область", a)
    a = re.sub(r"вн\.тер\.г\.\s*", "", a)
    a = re.sub(r"Российская Федерация,?\s*", "", a)
    a = re.sub(r"^(Ленинградская область|Санкт-Петербург)\s+(?=Ленинградская область|Санкт-Петербург|г\.? Санкт)", "", a)
    a = re.sub(r"^г\s+Санкт", "г. Санкт", a)
    a = re.sub(r"\s+", " ", a).strip(" ,.")
    if len(a) < 12 or a in ("Ленинградская область", "Санкт-Петербург"):
        a = ("Санкт-Петербург" if d.get("region") == "78" else "Ленинградская область") + (", адрес уточняется" if len(a) < 12 else "")
    return a[:160]


def object_label(d):
    t = str(d.get("address") or d.get("name") or "").lower()
    kind = "Доля в квартире" if re.search(r"дол[яиейю]", t) else ("Комната" if "комнат" in t and "квартир" not in t else "Квартира")
    area = f" {d['area']:g} м²".replace(".", ",") if d.get("area") and 8 <= d["area"] <= 400 else ""
    return kind + area


DISTRICT_RE = re.compile(r"(?:м\.р-н|р-н\.?|м\.о\.|г\.о\.)\s*([А-ЯЁ][а-яё]+(?:ский|цкий))|([А-ЯЁ][а-яё]+(?:ский|цкий))\s+(?:муниципальный\s+)?район")


def lo_district(d):
    if str(d.get("region")) in ("77", "78"):
        return None
    m = DISTRICT_RE.search(str(d.get("address") or d.get("name") or ""))
    if not m:
        return None
    name = m.group(1) or m.group(2)
    return name + (" городской округ" if name == "Сосновоборский" else " район")


def lo_town(d):
    if str(d.get("region")) in ("77", "78"):
        return None
    m = re.search(r"(?:(?<![а-яё.])г\.|город)\s*([А-ЯЁ][а-яё\-]+(?:\s[А-ЯЁ][а-яё]+)?)", str(d.get("address") or ""))
    t = m.group(1) if m else None
    return None if (t and t in CITY_NAME.values()) else t


FACETS = [  # slug, название, фильтр, заголовок-формулировка
    ("odnokomnatnye", "Однокомнатные", lambda d: d.get("rooms") == 1, "Однокомнатные квартиры с торгов"),
    ("dvuhkomnatnye", "Двухкомнатные", lambda d: d.get("rooms") == 2, "Двухкомнатные квартиры с торгов"),
    ("trehkomnatnye", "Трёхкомнатные и больше", lambda d: (d.get("rooms") or 0) >= 3, "Трёх- и многокомнатные квартиры с торгов"),
    ("komnaty", "Комнаты", lambda d: "комната" in (d.get("flags") or ""), "Комнаты с торгов"),
    ("doli", "Доли", lambda d: "доля" in (d.get("flags") or ""), "Доли в квартирах с торгов"),
    ("do-5-mln", "До 5 млн ₽", lambda d: (d.get("price") or 1e12) <= 5_000_000, "Квартиры с торгов до 5 млн рублей"),
    ("povtornye-torgi", "Повторные торги", lambda d: "повторные" in (d.get("flags") or ""), "Квартиры на повторных торгах"),
]
CITIES = [  # slug, название, «где», субъекты
    ("moskva", "Москва", "в Москве и Подмосковье"), ("sankt-peterburg", "Санкт-Петербург", "в Санкт-Петербурге и Ленобласти"),
    ("novosibirsk", "Новосибирск", "в Новосибирске и области"), ("ekaterinburg", "Екатеринбург", "в Екатеринбурге и области"),
    ("kazan", "Казань", "в Казани и пригородах"), ("krasnoyarsk", "Красноярск", "в Красноярске и пригородах"),
    ("nizhniy-novgorod", "Нижний Новгород", "в Нижнем Новгороде и области"), ("chelyabinsk", "Челябинск", "в Челябинске и области"),
    ("ufa", "Уфа", "в Уфе и пригородах"), ("krasnodar", "Краснодар", "в Краснодаре и пригородах"),
    ("samara", "Самара", "в Самаре, Тольятти и области"), ("rostov-na-donu", "Ростов-на-Дону", "в Ростове-на-Дону и области"),
    ("omsk", "Омск", "в Омске и пригородах"), ("voronezh", "Воронеж", "в Воронеже и области"),
    ("perm", "Пермь", "в Перми и пригородах"), ("volgograd", "Волгоград", "в Волгограде и Волжском"),
]
CITY_NAME = {c[0]: c[1] for c in CITIES}

for _d in LOTS:
    _d["caddr"] = clean_address(_d)
    _d["label"] = object_label(_d)
    _d["city"] = _d.get("city") or ("sankt-peterburg" if str(_d.get("region")) in ("78", "47") else None)
    _d["city_name"] = CITY_NAME.get(_d["city"], "")
    _d.pop("description", None)  # в извещениях бывают ФИО должников — на сайт не выводим




def median(xs):
    xs = [x for x in xs if x]
    return statistics.median(xs) if xs else None


def city_stats(lots):
    n = len(lots)
    return {"count": n, "median_price": median([d.get("price") for d in lots]),
            "median_ppm2": median([d.get("ppm2") for d in lots]),
            "share_doli": round(100 * sum(1 for d in lots if "доля" in (d.get("flags") or "")) / n) if n else None,
            "share_povt": round(100 * sum(1 for d in lots if "повторные" in (d.get("flags") or "")) / n) if n else None,
            "share_reg": round(100 * sum(1 for d in lots if "зарегистрированы" in (d.get("flags") or "")) / n) if n else None,
            "min_price": min((d["price"] for d in lots if d.get("price")), default=None),
            "week_new": sum(1 for d in lots if (d.get("first_seen") or "") >= (now - timedelta(days=7)).isoformat())}


def city_faq(cname, where, cs):
    if not cs["count"]:
        return []
    f = [(f"Сколько квартир продаётся с торгов {where}?",
          f"На {date.today().strftime('%d.%m.%Y')} в открытом реестре ГИС Торги {cs['count']} активных лотов жилья {where} (в радиусе 100 км от города), за последние 7 дней появилось {cs['week_new']}.")]
    if cs["median_price"]:
        f.append((f"Сколько стоит квартира с торгов {where}?",
                  f"Медианная начальная цена лота — {rub(cs['median_price'])}" + (f", медиана за квадратный метр — {rub(cs['median_ppm2'])}." if cs["median_ppm2"] else ".") +
                  f" Самый дешёвый активный лот — {rub(cs['min_price'])}. Это стартовые цены: на аукционе цена может вырасти."))
    if cs["share_doli"] is not None:
        f.append(("Что чаще всего продаётся на торгах в этом городе?",
                  f"Доли в квартирах составляют {cs['share_doli']}% активных лотов, повторные торги — {cs['share_povt']}%, лоты с зарегистрированными жильцами по тексту извещения — {cs['share_reg']}%. Доли и лоты с жильцами дешевле, но сложнее в продаже и освобождении."))
    return f


def stats(lots):
    ppm = [d["ppm2"] for d in lots if d.get("ppm2")]
    cutoff = (now - timedelta(days=7)).isoformat()
    return {"count": len(lots), "median_ppm2": statistics.median(ppm) if ppm else None,
            "min_price": min((d["price"] for d in lots if d.get("price")), default=None),
            "week_new": sum(1 for d in lots if (d.get("first_seen") or "") >= cutoff)}


# ---------- запись ----------
SITEMAP = []
CITY_STATS = []


def write(path, tpl, sitemap=True, priority="0.6", lastmod=TODAY, **ctx):
    ctx.setdefault("canonical", cfg.SITE_URL + path)
    ctx.setdefault("noindex", False)
    html = env.get_template(tpl).render(path=path, **ctx)
    target = OUT / path.strip("/") / "index.html" if path.endswith("/") else OUT / path.strip("/")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(html, encoding="utf-8")
    if sitemap and not ctx["noindex"]:
        SITEMAP.append((path, lastmod, priority))


def build():
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    shutil.copytree(SRC / "static", OUT / "static")
    if (SRC / "root").exists():  # файлы подтверждения и прочее в корень сайта
        for f in (SRC / "root").iterdir():
            shutil.copy(f, OUT / f.name)
    if (ROOT / "check").exists():
        shutil.copytree(ROOT / "check", OUT / "check")
    city_counts = {c[0]: sum(1 for d in LOTS if d.get("city") == c[0]) for c in CITIES}
    env.globals["cities"] = [(c[0], c[1], c[2], city_counts[c[0]]) for c in CITIES]
    st = stats(LOTS)
    board = [d for d in LOTS if d.get("price")][:6]
    write("/", "home.html", priority="1.0", lots=board, st=st, articles=ARTICLES[:6],
          title="Квартиры с торгов в СПб и Ленобласти: подбор, проверка, покупка под ключ",
          description="Свежие лоты с торгов по жилью в Санкт-Петербурге и Ленинградской области. Проверим лот, рассчитаем максимальную ставку и сопроводим покупку до ключей.")


    def listing(path, lots, h1, crumbs, links, sub_links=(), priority="0.8", faq=None, cs=None):
        write(path, "torgi.html", priority=priority, lots=lots[:300], st=stats(lots), h1=h1, crumbs=crumbs,
              facet_links=links, town_links=sorted(sub_links), noindex=not lots, faq=faq or [], cs=cs,
              title=f"{h1} — актуальные лоты {TODAY[:4]}",
              description=f"{h1}: {len(lots)} актуальных лотов — цена, цена за м², срок подачи заявок, риски. Обновляется несколько раз в день.")

    city_links = [("/torgi/", "Все города")] + [(f"/torgi/{c[0]}/", f"{c[1]} ({city_counts[c[0]]})") for c in CITIES if city_counts[c[0]]]
    listing("/torgi/", LOTS, "Квартиры с торгов в городах-миллионниках России", [("Лоты", "/torgi/")],
            city_links + [(f"/torgi/{f[0]}/", f[1]) for f in FACETS if any(f[2](d) for d in LOTS)], priority="0.9")
    for slug, name, flt, h1 in FACETS:
        fl = [d for d in LOTS if flt(d)]
        if fl:
            listing(f"/torgi/{slug}/", fl, f"{h1} в городах-миллионниках", [("Лоты", "/torgi/"), (name, f"/torgi/{slug}/")], city_links)
    for cslug, cname, where in CITIES:
        cl = [d for d in LOTS if d.get("city") == cslug]
        subs = {}
        for d in cl:
            for t in (lo_district(d), lo_town(d)):
                if t:
                    subs.setdefault(t, []).append(d)
        subs = {t: v for t, v in subs.items() if len(v) >= 2 or ("район" in t or "округ" in t)}
        sub_links = [(f"/torgi/{cslug}/{translit(t)}/", f"{t} ({len(v)})") for t, v in subs.items()]
        facets_here = [(f, [d for d in cl if f[2](d)]) for f in FACETS]
        facets_here = [(f, v) for f, v in facets_here if len(v) >= 3]
        links = [(f"/torgi/{cslug}/", "Все")] + [(f"/torgi/{cslug}/{f[0]}/", f[1]) for f, v in facets_here]
        base_crumbs = [("Лоты", "/torgi/"), (cname, f"/torgi/{cslug}/")]
        cs = city_stats(cl)
        CITY_STATS.append((cslug, cname, where, cs))
        listing(f"/torgi/{cslug}/", cl, f"Квартиры с торгов {where}", base_crumbs, links, sub_links, "0.9",
                faq=city_faq(cname, where, cs), cs=cs)
        for f, v in facets_here:
            listing(f"/torgi/{cslug}/{f[0]}/", v, f"{f[3]}: {cname}", base_crumbs + [(f[1], f"/torgi/{cslug}/{f[0]}/")], links, sub_links)
        for t, v in subs.items():
            listing(f"/torgi/{cslug}/{translit(t)}/", v, f"Квартиры с торгов: {t}", base_crumbs + [(t, f"/torgi/{cslug}/{translit(t)}/")], links, sub_links, "0.7")

    for d in LOTS:
        similar = [x for x in LOTS if x.get("region") == d.get("region") and x["id"] != d["id"]][:4]
        write(f"/torgi/lot/{d['id']}/", "lot.html", priority="0.5", lastmod=(d.get("first_seen") or TODAY)[:10],
              d=d, active=True, similar=similar,
              title=f"{d['label']} с торгов: {d['caddr'][:70]}",
              description=f"{d['label']} с торгов: {d['caddr']}. Начальная цена {rub(d.get('price'))}. Риски, срок приёма заявок, расчёт ставки.")

    pages = [("kupit-kvartiru-s-torgov", "buy.html", "Купить квартиру с торгов под ключ в СПб — подбор и сопровождение",
              "Подберём квартиру на торгах по банкротству и арестованному имуществу, проверим риски, подадим заявку и сопроводим до регистрации права."),
             ("proverka-lota", "check.html", "Проверка лота перед торгами: юридическая и рыночная",
              "Проверим квартиру с торгов до подачи заявки: обременения, зарегистрированные, долги, рыночная цена и максимальная ставка."),
             ("investoram", "invest.html", "Инвесторам: покупка недвижимости с торгов в СПб",
              "Подбор объектов с торгов под вашу стратегию: перепродажа или аренда. Расчёт экономики сделки, проверка и сопровождение покупки на ваше имя."),
             ("kalkulyator-stavki", "calc.html", "Калькулятор максимальной ставки на торгах по недвижимости",
              "Рассчитайте, сколько можно предложить на торгах, чтобы сделка осталась в плюсе: цена продажи, расходы, срок, налоги."),
             ("slovar", "glossary.html", "Словарь терминов торгов по банкротству и арестованному имуществу",
              "Короткие определения: задаток, шаг аукциона, публичное предложение, цена отсечения, ЕФРСБ, ЭТП и другие термины торгов."),
             ("o-nas", "about.html", "О нас и контакты", "Кто мы, как работаем, реквизиты и контакты."),
             ("politika", "privacy.html", "Политика обработки персональных данных", "Политика обработки персональных данных.")]
    for slug, tpl, title, desc in pages:
        write(f"/{slug}/", tpl, sitemap=slug != "politika", priority="0.8", title=title, description=desc, st=st)
    tot = city_stats(LOTS)
    write("/analitika/", "analytics.html", priority="0.8", rows=CITY_STATS, tot=tot,
          title=f"Статистика торгов недвижимостью по городам-миллионникам — {date.today().strftime('%m.%Y')}",
          description="Сколько квартир продаётся с торгов в Москве, Петербурге и других миллионниках, медианные цены за м², доля долей и повторных торгов. Обновляется несколько раз в день.")
    write("/podpiska/", "subscribe.html", priority="0.6", title="Подборка лотов с торгов в Telegram",
          description="Пришлём новые лоты с торгов по вашему городу, бюджету и типу жилья в Telegram.")
    write("/partneram/", "partners.html", priority="0.6", title="Арбитражным управляющим и залоговым кредиторам: продвижение лотов",
          description="Покажем ваш лот покупателям и инвесторам: карточка на сайте, Telegram, подготовка лота к продаже — фото, документы, проверка.")
    write("/stati/", "articles.html", priority="0.7", articles=ARTICLES, title="Статьи о покупке недвижимости с торгов",
          description="Как устроены торги по банкротству и арестованному имуществу, риски, проверка лота, расчёт ставки.")
    for a in ARTICLES:
        write(f"/stati/{a['slug']}/", "article.html", priority="0.7", lastmod=a.get("updated") or a.get("date") or TODAY,
              a=a, related=[x for x in ARTICLES if x["slug"] != a["slug"]][:4], title=a["title"], description=a["description"])
    write("/404.html", "404.html", sitemap=False, noindex=True, title="Страница не найдена", description="")

    body = "".join(f"<url><loc>{cfg.SITE_URL}{u}</loc><lastmod>{m}</lastmod><priority>{p}</priority></url>" for u, m, p in SITEMAP)
    (OUT / "sitemap.xml").write_text(f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{body}</urlset>', encoding="utf-8")
    (OUT / "robots.txt").write_text("\n".join([
        "User-agent: *", "Allow: /", "Disallow: /check/", "",
        "User-agent: YandexAdditional", "Allow: /", "", "User-agent: YandexAdditionalBot", "Allow: /", "",
        "User-agent: GPTBot", "Allow: /", "", "User-agent: OAI-SearchBot", "Allow: /", "",
        "User-agent: PerplexityBot", "Allow: /", "", "User-agent: ClaudeBot", "Allow: /", "",
        f"Sitemap: {cfg.SITE_URL}/sitemap.xml", ""]), encoding="utf-8")
    arts = "\n".join(f"- [{a['title']}]({cfg.SITE_URL}/stati/{a['slug']}/): {a['description']}" for a in ARTICLES)
    (OUT / "llms.txt").write_text(f"""# {cfg.SITE_NAME}

> Подбор, проверка и сопровождение покупки жилья с торгов по банкротству и реализации арестованного имущества в Санкт-Петербурге и Ленинградской области. {cfg.SITE_OWNER}. Не организатор торгов, деньги клиентов не принимаем.

## Разделы
- [Актуальные лоты]({cfg.SITE_URL}/torgi/): обновляются несколько раз в день по данным ГИС Торги
- [Покупка квартиры с торгов под ключ]({cfg.SITE_URL}/kupit-kvartiru-s-torgov/)
- [Проверка лота перед торгами]({cfg.SITE_URL}/proverka-lota/)
- [Инвесторам]({cfg.SITE_URL}/investoram/)
- [Калькулятор максимальной ставки]({cfg.SITE_URL}/kalkulyator-stavki/)
- [Словарь терминов торгов]({cfg.SITE_URL}/slovar/)

## Статьи
{arts}
""", encoding="utf-8")
    (OUT / ".htaccess").write_text("""AddDefaultCharset UTF-8
ErrorDocument 404 /404.html
Options -Indexes
RewriteEngine On
RewriteCond %{HTTPS} off [OR]
RewriteCond %{HTTP_HOST} ^www\\. [NC]
RewriteRule ^(.*)$ https://kirpichinvest.ru/$1 [R=301,L]
RewriteRule ^torgi/spb/?$ /torgi/sankt-peterburg/ [R=301,L]
RewriteRule ^torgi/lenoblast/?$ /torgi/sankt-peterburg/ [R=301,L]
RewriteRule ^torgi/lenoblast/(.+)$ /torgi/sankt-peterburg/$1 [R=301,L]
RewriteCond %{REQUEST_FILENAME} !-f
RewriteCond %{REQUEST_URI} !/$
RewriteCond %{REQUEST_URI} !\\.[a-z0-9]+$ [NC]
RewriteRule ^(.*)$ /$1/ [R=301,L]
<IfModule mod_expires.c>
ExpiresActive On
ExpiresByType font/woff2 "access plus 1 year"
ExpiresByType text/css "access plus 1 month"
ExpiresByType text/html "access plus 10 minutes"
</IfModule>
<IfModule mod_deflate.c>
AddOutputFilterByType DEFLATE text/html text/css application/javascript application/xml text/plain application/json
</IfModule>
""", encoding="utf-8")
    if getattr(cfg, "INDEXNOW_KEY", ""):
        (OUT / f"{cfg.INDEXNOW_KEY}.txt").write_text(cfg.INDEXNOW_KEY, encoding="utf-8")
    (OUT / "urls.txt").write_text("\n".join(cfg.SITE_URL + u for u, _, _ in SITEMAP), encoding="utf-8")
    print(f"OK: страниц {len(SITEMAP)} в sitemap, лотов {len(LOTS)}, статей {len(ARTICLES)}")


if __name__ == "__main__":
    build()
