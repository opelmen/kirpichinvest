"""Сборка статического сайта torggid.ru (до 10.2026 — kirpichinvest.ru).
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
from lot_history import merge_history
from quality import thin_card, yandex_card
from budget_collections import budget_lots, budget_summary, object_group
from market_feed import CATEGORY, REGIONS, SOURCE, SOURCE_SITE, from_market, mln
from auto_feed import FIELDS as AUTO_FIELDS, VTYPES, from_vehicles

import markdown
from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

SRC = Path(__file__).parent
ROOT = SRC.parent
OUT = ROOT / "_site"

cfg = SimpleNamespace(
    SITE_NAME="ТоргГид", SITE_URL="https://torggid.ru", SITE_PHONE="+7 995 595-54-00",  # телефон карточки Яндекс Бизнеса: только подвал, «О нас» и разметка, не на главных экранах (John, 31.10.2026)
   
    SITE_EMAIL="fond178@gmail.com", SITE_OWNER="ИП Смирнов Илья Александрович", SITE_INN="", SITE_OGRNIP="",
    SITE_ADDRESS="Санкт-Петербург", SITE_TELEGRAM="https://t.me/smirnoffond", METRIKA_ID="",
    PRICE_BUY="", PRICE_CHECK="", LEAD_URL="https://check.kirpichinvest.ru/public/lead",
    YANDEX_VERIFICATION="", GOOGLE_VERIFICATION="", BING_VERIFICATION="", INDEXNOW_KEY="",
    TG_CHANNEL="", TG_BOT="", MAX_CHANNEL="",  # канал в Max (https://max.ru/…): дубль Telegram, John 21.10.2026
    APP_URL="https://app.torggid.ru", AUTO_URL="https://app.torggid.ru/auto", REPORT_PRICE=290,
    YANDEX_MAPS_URL="", VK_URL="", DZEN_URL="", SAME_AS=[])  # карточка в Яндекс Бизнесе и соцсети: попадают в sameAs и подвал
cfg_file = SRC / "config.json"
if cfg_file.exists():
    for k, v in json.loads(cfg_file.read_text(encoding="utf-8")).items():
        setattr(cfg, k, v)

AUTHOR = {"name": "Илья Смирнов", "role": "брокер по недвижимости и залоговым сделкам, Санкт-Петербург", "path": "/avtor/ilya-smirnov/"}
HOURS = ("Пн–Пт, 10:00–19:00", ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"], "10:00", "19:00")
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


def list_ld(name, url, total, lots, offset=0, base="/torgi/lot/"):
    """ItemList для страницы каталога: поисковики и ИИ-ассистенты видят список лотов как структуру, не только как ссылки."""
    return ld({"@context": "https://schema.org", "@type": "ItemList", "name": name, "url": url, "numberOfItems": total,
               "itemListElement": [{"@type": "ListItem", "position": offset + i + 1, "url": f"{cfg.SITE_URL}{base}{d['id']}/",
                                    "name": (f"{d['label']}: " if d.get("label") else "") + (d.get("caddr") or "")[:80] if d.get("caddr") else d.get("label", "")} for i, d in enumerate(lots)]})


env = Environment(loader=FileSystemLoader(SRC / "templates"), autoescape=select_autoescape(["html"]))
env.globals["list_ld"] = list_ld
env.filters["rub"] = rub
env.filters["mln"] = lambda v: mln(v) + "\u00a0₽"
env.filters["digits"] = lambda v: int(re.sub(r"\D", "", str(v)) or 0)
env.globals["object_group"] = object_group
def terms_list(terms):
    return [{"@type": "DefinedTerm", "name": t, "description": d, "url": f"{cfg.SITE_URL}/slovar/#{s}"} for t, s, d in terms]


def same_as():
    """Профили бренда вне сайта: нейросети и Яндекс сверяют по ним, что ТоргГид — одна и та же организация."""
    return list(dict.fromkeys(u for u in [cfg.YANDEX_MAPS_URL, cfg.TG_CHANNEL, cfg.MAX_CHANNEL, cfg.VK_URL, cfg.DZEN_URL, cfg.TG_BOT, *cfg.SAME_AS] if u))


env.globals.update(terms_list=terms_list, cfg=cfg, same_as=same_as, hours=HOURS, year=date.today().year, today=date.today().strftime("%d.%m.%Y"), author=AUTHOR, ld=ld, faq_ld=faq_ld, crumbs_ld=crumbs_ld)

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
market_path = SRC / "data" / "market.json"  # выгрузка приложения: вся страна и все площадки
WIDE = market_path.exists()
GEO = "по всей России" if WIDE else "в городах-миллионниках"
OBJ = "Недвижимость" if WIDE else "Квартиры"
if WIDE:
    LOTS = from_market(json.loads(market_path.read_text(encoding="utf-8"))["lots"])
now = datetime.now(timezone.utc)
for d in LOTS:
    if d.get("bidd_end"):
        try:
            end = datetime.fromisoformat(str(d["bidd_end"]).replace("Z", "+00:00"))
            end = end if end.tzinfo else end.replace(tzinfo=timezone.utc)
            d["days_left"] = (end - now).total_seconds() / 86400
        except ValueError:
            d["days_left"] = None

LOTS.sort(key=lambda d: d.get("first_seen") or "", reverse=True)


def translit(s):
    t = dict(zip("абвгдеёжзийклмнопрстуфхцчшщъыьэюя", ["a", "b", "v", "g", "d", "e", "e", "zh", "z", "i", "y", "k", "l", "m", "n", "o", "p", "r", "s", "t", "u", "f", "h", "c", "ch", "sh", "sch", "", "y", "", "e", "yu", "ya"]))
    return re.sub(r"-+", "-", "".join(t.get(c, c if c.isalnum() else "-") for c in s.lower())).strip("-")


FIO = re.compile(r"[А-ЯЁ][а-яё]+(?:-[А-ЯЁ][а-яё]+)?\s+(?:[А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+(?:вич|вна|ична|инична|оглы|кызы)\b|[А-ЯЁ]\.\s?[А-ЯЁ]\.)\s*,?")


# Хвост извещения после адреса (как в платформе, kirpich/domain/text.py): обременения, цена, этаж, кадастр.
ADDR_NOTE = re.compile(
    r"[,;(]\s*(?:обремен|ограничен|(?:наход\w*\s+)?в\s+залоге|залог|ипотек|арест|запрет|в\s+пользу|начальн|н/ц|цена\b"
    r"|задат|собственник|должник|назначени|кадастр|к/н|к\.н\.|площад|общ\w*\s+пл|этаж|эт\.|подвал|цокол|мансард"
    r"|права?\s+аренд|аренд|срок|состоит|расположен|имеет|вид\s+права|доля\s+в\s+праве|общая\s+долевая)",
    re.I,
)
ROOM_NO = re.compile(
    r",?\s*(?<![а-яё])(?:кв\.?|квартира|комн(?:ата|\.)?|ком\.|пом(?:ещение|ещ\.|\.)?|№)\s*№?\s*"
    r"(?:\d+(?:-?[а-яa-z]{1,2}\b)?|[IVXLC]+\b)(?:\s*[-–,/]\s*(?:\d+(?:-?[а-яa-z]{1,2}\b)?|[IVXLC]+\b))*"
    r"(?![\d.,]*\s*(?:м|кв\.?\s*м))",
    re.I,
)


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
    a = re.sub(r"муниципальный округ [^,]+,\s*", "", a)
    a = re.split(r"\.\s*(?:Обремен|н/ц|Начальн|Собственник|Должник)", a, flags=re.I)[0]
    a = re.split(r",?\s*(?:общей\s+площадью|общ\.?\s*пл|площадью|кадастров|кад\.\s*№|к\.н\.|общая\s+долевая|\(?доля\s+в\s+праве|н/ц\b)", a, flags=re.I)[0]
    towns = list(re.finditer(r"(?<![а-яё])(?:г\.|город)\s*[А-ЯЁ]", a))
    m = ADDR_NOTE.search(a, towns[-1].start() if towns else 0)  # «…, обременено залогом в пользу банка» — не адрес
    if m:
        a = a[: m.start()]
    a = ROOM_NO.sub("", a)  # номер квартиры/помещения не публикуем
    a = re.sub(FIO, "", a)  # ФИО должника иногда стоит прямо в строке адреса
    a = re.sub(r"(?<![а-яё])(д|корп|стр|ул|пр-т|пер)\.(?=[\dА-ЯЁ])", r"\1. ", a, flags=re.I)
    a = re.sub(r"\s+", " ", a).strip(" ,.")
    if len(a) < 12 or a in ("Ленинградская область", "Санкт-Петербург"):
        a = CITY_NAME.get(d.get("city"), "Адрес уточняется")
    return a[:160]


NOTICE_PD = re.compile(r"должник|взыскател|принадлежащ|\bИНН\b|паспорт|СНИЛС|\bтел\.?|\+7|@|\bФИО\b|дата рождения|зарегистрирован\w* по адресу", re.I)


def notice_excerpt(text, limit=500):
    """Короткий пересказ извещения своими словами площадки: только описание объекта, без персональных данных.
    Предложения с должником, ИНН, телефонами и ФИО выбрасываем целиком; это и есть уникальный текст карточки."""
    t = re.sub(r"\s+", " ", str(text or "")).strip()
    if not t:
        return ""
    keep, total = [], 0
    for part in re.split(r"(?<=[.;!?])\s+(?=[А-ЯЁA-Z«(])", t):  # «кв. м» и «д. 5» не конец предложения
        if NOTICE_PD.search(part) or FIO.search(part):
            continue
        part = re.sub(r"\b\d{10,}\b", "", part).strip(" ,;")
        if len(part) < 20:
            continue
        keep.append(part)
        total += len(part) + 1
        if total >= limit:
            break
    out = " ".join(keep)
    if len(out) > limit:
        out = out[:limit].rsplit(" ", 1)[0].rstrip(" ,;:") + "…"
    return out


def object_label(d):
    if d.get("category") in CATEGORY:
        area = f" {d['area']:g} м²".replace(".", ",") if d.get("area") and 8 <= d["area"] <= 100_000 else ""
        return CATEGORY[d["category"]][0] + area
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


def good_deal(d):
    """«Нормальный» выгодный лот для витрины: квартира или дом целиком, понятный адрес, оценка рынка по аналогам,
    скидка 10–50% (больше — чаще ошибка оценки), без серьёзных рисков в извещении и не в последний день приёма заявок."""
    cat, area, disc, flags = d.get("category") or "flat", d.get("area"), d.get("eff_discount"), d.get("flags") or ""
    return (cat in ("flat", "house") and bool(d.get("eff_market")) and disc is not None and 10 <= disc <= 50
            and "доля" not in flags and "комната" not in flags
            and not any(r.get("level") == "high" for r in d.get("risks") or [])
            and bool(area) and (20 <= area <= 250 if cat == "flat" else 30 <= area <= 600)
            and (d.get("price") or 0) >= 300_000
            and len(d.get("caddr") or "") >= 15 and d.get("caddr") not in CITY_NAME.values()
            and (d.get("days_left") is None or d["days_left"] >= 2))


def facet_lots(f, lots):
    sel = [d for d in lots if f[2](d)]
    return by_discount(sel) if f[0] == "vygodnye" else sel


def by_discount(lots):
    return sorted(lots, key=lambda d: (-(d.get("eff_discount") or 0), d["id"]))


FACETS = [  # slug, название, фильтр, заголовок-формулировка
    ("vygodnye", "Дешевле рынка", good_deal, "Квартиры и дома с торгов дешевле рынка"),
    ("odnokomnatnye", "Однокомнатные", lambda d: d.get("rooms") == 1, "Однокомнатные квартиры с торгов"),
    ("dvuhkomnatnye", "Двухкомнатные", lambda d: d.get("rooms") == 2, "Двухкомнатные квартиры с торгов"),
    ("trehkomnatnye", "Трёхкомнатные и больше", lambda d: (d.get("rooms") or 0) >= 3, "Трёх- и многокомнатные квартиры с торгов"),
    ("komnaty", "Комнаты", lambda d: "комната" in (d.get("flags") or ""), "Комнаты с торгов"),
    ("doli", "Доли", lambda d: "доля" in (d.get("flags") or ""), "Доли в квартирах с торгов"),
    ("do-5-mln", "До 5 млн ₽", lambda d: (d.get("price") or 1e12) <= 5_000_000, "Квартиры с торгов до 5 млн рублей"),
    ("povtornye-torgi", "Повторные торги", lambda d: d.get("repeat"), "Квартиры на повторных торгах"),
    ("doma", "Дома", lambda d: d.get("category") == "house", "Дома с торгов"),
    ("zemlya", "Земля", lambda d: d.get("category") == "land", "Земельные участки с торгов"),
    ("kommercheskaya", "Коммерческая", lambda d: d.get("category") == "commercial", "Коммерческая недвижимость с торгов"),
    ("garazhi", "Гаражи", lambda d: d.get("category") == "garage", "Гаражи и машино-места с торгов"),
    ("bankrotstvo", "Банкротство", lambda d: d.get("kind") == "bankruptcy", "Недвижимость с торгов по банкротству"),
    ("arestovannoe", "Арестованное", lambda d: d.get("kind") == "arrest", "Арестованная недвижимость с торгов"),
]
# подборка сайта → те же условия в поиске платформы: кнопка «Следить за подборкой» создаёт там «Охотника»
# (посадочные под рекламу, John 21.10.2026). Ключи — параметры адресной строки каталога app.torggid.ru
APP_FACET = {
    "vygodnye": [("category", "flat"), ("category", "house"), ("discount_min", "10")],
    "odnokomnatnye": [("category", "flat"), ("rooms", "1")], "dvuhkomnatnye": [("category", "flat"), ("rooms", "2")],
    "trehkomnatnye": [("category", "flat"), ("rooms", "3"), ("rooms", "4")],
    "komnaty": [("category", "room")], "doli": [("category", "share")], "do-5-mln": [("category", "flat"), ("price_max", "5")],
    "povtornye-torgi": [("repeat", "1")], "doma": [("category", "house")], "zemlya": [("category", "land")],
    "kommercheskaya": [("category", "commercial")], "garazhi": [("category", "garage")],
    "bankrotstvo": [("kind", "bankruptcy")], "arestovannoe": [("kind", "arrest")],
}


def app_query(path):
    """/torgi/kazan/doli/ → city=kazan&category=share. Регион и район платформа пока не фильтрует: берём только подборку."""
    parts = [x for x in path.strip("/").split("/") if x][1:]
    q = []
    if parts and parts[0] in CITY_NAME:
        q.append(("city", parts.pop(0)))
    elif parts and parts[0] not in APP_FACET:
        parts.pop(0)
    if parts and parts[0] in APP_FACET:
        q += APP_FACET[parts[0]]
    return "&".join(f"{k}={v}" for k, v in q)


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
    _d["excerpt"] = notice_excerpt(_d.get("descr"))
    _d["caddr"] = clean_address(_d)
    _d["label"] = object_label(_d)
    _d["city"] = _d.get("city") or ("sankt-peterburg" if str(_d.get("region")) in ("78", "47") else None)
    _d["city_name"] = CITY_NAME.get(_d["city"], "")
    _d["district"] = lo_district(_d)
    _d["town"] = lo_town(_d)
    if _d.get("region") in REGIONS and str(_d.get("region")) not in ("77", "78"):
        _d["region_slug"], _d["region_name"] = REGIONS[_d["region"]][:2]
    _d.pop("description", None)  # в извещениях бывают ФИО должников — на сайт не выводим



# History contains only fields already rendered on public cards.
for _d in LOTS:
    _d["source_url"] = _d.get("source_url") or f"https://torgi.gov.ru/new/public/lots/lot/{_d['id']}"
history_path = SRC / "data" / "lot_history.json"
previous = json.loads(history_path.read_text(encoding="utf-8")) if history_path.exists() else []
CARDS = merge_history(LOTS, previous, now)
LOTS = sorted((d for d in CARDS if d["status"] == "active"), key=lambda d: (d.get("first_seen") or "", d["id"]), reverse=True)
ARCHIVED = sorted((d for d in CARDS if d["status"] != "active"), key=lambda d: (d["lastmod"], d["id"]), reverse=True)

# ---------- техника: раздел /auto/ ----------
# Выгрузка /api/v1/public/vehicles приложения. Без неё раздел не собирается (ссылка «Авто» ведёт на платформу).
vehicles_path = SRC / "data" / "vehicles.json"
AUTOS = from_vehicles(json.loads(vehicles_path.read_text(encoding="utf-8"))["lots"]) if vehicles_path.exists() else []
for _d in AUTOS:  # выгрузка уже без ПДн, но пересказ фильтруем и здесь: предложения с ФИО, ИНН, телефонами выбрасываются
    _d["excerpt"] = notice_excerpt(_d.get("excerpt"), 600)
auto_history_path = SRC / "data" / "auto_history.json"
_auto_prev = json.loads(auto_history_path.read_text(encoding="utf-8")) if auto_history_path.exists() else []
AUTO_CARDS = merge_history(AUTOS, _auto_prev, now, AUTO_FIELDS) if (AUTOS or _auto_prev) else []
AUTOS = sorted((d for d in AUTO_CARDS if d["status"] == "active"), key=lambda d: (d.get("first_seen") or "", d["id"]), reverse=True)
AUTO_ARCHIVED = sorted((d for d in AUTO_CARDS if d["status"] != "active"), key=lambda d: (d["lastmod"], d["id"]), reverse=True)



def median(xs):
    xs = [x for x in xs if x]
    return statistics.median(xs) if xs else None


def city_stats(lots):
    n = len(lots)
    return {"count": n, "median_price": median([d.get("price") for d in lots]),
            "median_ppm2": median([d.get("ppm2") for d in lots]),
            "share_doli": round(100 * sum(1 for d in lots if "доля" in (d.get("flags") or "")) / n) if n else None,
            "share_povt": round(100 * sum(1 for d in lots if d.get("repeat")) / n) if n else None,
            "share_reg": round(100 * sum(1 for d in lots if "зарегистрированы" in (d.get("flags") or "")) / n) if n else None,
            "min_price": min((d["price"] for d in lots if d.get("price")), default=None),
            "week_new": sum(1 for d in lots if (d.get("first_seen") or "") >= (now - timedelta(days=7)).isoformat()),
            "sources": source_counts(lots)}


def source_counts(lots):
    """Площадки, где идут торги по этим лотам: (название, официальный сайт, число лотов), по убыванию."""
    # в истории карточек хранится только source_name (lot_history.FIELDS), сайт площадки берём по названию
    site_by_name = {name: SOURCE_SITE.get(code) for code, name in SOURCE.items()}
    cnt = {}
    for d in lots:
        s = d.get("source_name") or SOURCE.get(d.get("source") or "", "") or "Другие источники"
        cnt[s] = cnt.get(s, 0) + 1
    rows = [(s, site_by_name.get(s), n) for s, n in cnt.items()]
    return sorted(rows, key=lambda r: (-r[2], r[0]))


INDEX_START = "2026-10"  # с этого месяца история каталога полная по всей стране: раньше индекс не считаем
MONTHS_RU = ("январь", "февраль", "март", "апрель", "май", "июнь", "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь")
MONTHS_PREP = ("в январе", "в феврале", "в марте", "в апреле", "в мае", "в июне", "в июле", "в августе", "в сентябре",
               "в октябре", "в ноябре", "в декабре")
MONTHS_GEN = ("января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря")


def month_bounds(ym):
    y, m = map(int, ym.split("-"))
    start = date(y, m, 1)
    end = date(y + (m == 12), m % 12 + 1, 1) - timedelta(days=1)
    return start, end


def index_months(cards, today=None):
    """Месяцы индекса: от INDEX_START до текущего, только те, где в каталоге были лоты."""
    today = today or date.today()
    out, ym = [], INDEX_START
    while ym <= today.strftime("%Y-%m"):
        if month_lots(cards, ym, today):
            out.append(ym)
        y, m = map(int, ym.split("-"))
        ym = f"{y + (m == 12)}-{m % 12 + 1:02d}"
    return out


def month_lots(cards, ym, today=None):
    """Лоты, которые были в продаже в месяце: появились до его конца и не ушли до начала (по истории карточек)."""
    today = today or date.today()
    start, end = month_bounds(ym)
    end = min(end, today)
    s, e = start.isoformat(), end.isoformat()
    res = []
    for d in cards:
        if (d.get("first_seen") or "")[:10] > e:
            continue
        if d.get("status") != "active" and (d.get("last_seen") or "") < s:
            continue
        if (d.get("bidd_end") or "9999")[:10] < s:
            continue
        res.append(d)
    return res


def month_index(cards, ym, today=None):
    """Индекс торгов ТоргГид за месяц: открытые данные каталога, только агрегаты (без адресов и сведений о должниках)."""
    today = today or date.today()
    start, end = month_bounds(ym)
    lots = month_lots(cards, ym, today)
    n = len(lots)
    if not n:
        return None
    pct = lambda k: round(100 * k / n)  # noqa: E731
    med = lambda xs: (lambda v: round(v) if v is not None else None)(median(xs))  # noqa: E731
    flats = [d for d in lots if d.get("category") == "flat"]
    valued = [d["eff_discount"] for d in flats if d.get("eff_discount") is not None]
    by_cat = []
    for key, (one, many) in CATEGORY.items():
        xs = [d for d in lots if d.get("category") == key]
        if xs:
            by_cat.append({"key": key, "name": many, "count": len(xs), "share": pct(len(xs)),
                           "median_price": med([d.get("price") for d in xs]),
                           "median_ppm2": med([d.get("ppm2") for d in xs]) if key in ("flat", "house", "room") else None})
    by_cat.sort(key=lambda r: -r["count"])
    kinds = {}
    for d in lots:
        kinds[d.get("kind_name") or "Другое"] = kinds.get(d.get("kind_name") or "Другое", 0) + 1
    srcs = {}
    for d in lots:
        srcs[d.get("source_name") or "Другое"] = srcs.get(d.get("source_name") or "Другое", 0) + 1
    regs = {}
    for d in lots:
        if d.get("region") in REGIONS:
            regs.setdefault(d["region"], []).append(d)
    by_region = []
    for code, xs in sorted(regs.items(), key=lambda kv: -len(kv[1]))[:15]:
        fl = [x for x in xs if x.get("category") == "flat"]
        by_region.append({"slug": REGIONS[code][0], "name": REGIONS[code][1], "count": len(xs), "flats": len(fl),
                          "median_flat_price": med([x.get("price") for x in fl]),
                          "median_flat_ppm2": med([x.get("ppm2") for x in fl])})
    public = sum(1 for d in lots if "публичн" in (d.get("bidd_type") or "").lower())
    repeat = sum(1 for d in lots if d.get("repeat"))
    closed = end < today
    return {
        "ym": ym, "month": MONTHS_RU[start.month - 1], "month_gen": MONTHS_GEN[start.month - 1], "month_prep": MONTHS_PREP[start.month - 1], "year": start.year,
        "start": start.isoformat(), "end": end.isoformat(), "closed": closed,
        "as_of": end.isoformat() if closed else today.isoformat(),
        "count": n, "regions": len(regs),
        "new": sum(1 for d in lots if start.isoformat() <= (d.get("first_seen") or "")[:10] <= end.isoformat()) if ym > INDEX_START else None,
        "by_cat": by_cat,
        "by_kind": sorted(kinds.items(), key=lambda kv: -kv[1]),
        "by_source": sorted(srcs.items(), key=lambda kv: -kv[1]),
        "by_region": by_region,
        "public": public, "public_share": pct(public), "repeat": repeat, "repeat_share": pct(repeat),
        "flats": len(flats), "flat_median_price": med([d.get("price") for d in flats]),
        "flat_median_ppm2": med([d.get("ppm2") for d in flats]),
        "flats_valued": len(valued), "flat_median_discount": round(statistics.median(valued)) if valued else None,
        "flats_below10": round(100 * sum(1 for v in valued if v >= 10) / len(valued)) if valued else None,
    }


def index_csv(ix):
    rows = [("показатель", "значение")]
    rows += [("месяц", ix["ym"]), ("данные на", ix["as_of"]), ("лотов в продаже", ix["count"]), ("регионов", ix["regions"])]
    if ix["new"] is not None:
        rows.append(("новых лотов за месяц", ix["new"]))
    rows += [("доля публичного предложения, %", ix["public_share"]), ("доля повторных торгов, %", ix["repeat_share"]),
             ("квартир", ix["flats"]), ("медиана начальной цены квартиры, руб", ix["flat_median_price"] or ""),
             ("медиана цены м² квартиры, руб", ix["flat_median_ppm2"] or ""),
             ("квартир с оценкой рынка", ix["flats_valued"]),
             ("медиана скидки квартиры к рынку, %", "" if ix["flat_median_discount"] is None else ix["flat_median_discount"]),
             ("доля квартир дешевле рынка на 10% и больше, %", "" if ix["flats_below10"] is None else ix["flats_below10"])]
    rows += [(f"категория: {c['name']}", c["count"]) for c in ix["by_cat"]]
    rows += [(f"процедура: {k}", v) for k, v in ix["by_kind"]]
    rows += [(f"площадка: {k}", v) for k, v in ix["by_source"]]
    rows += [(f"регион: {r['name']}", r["count"]) for r in ix["by_region"]]
    return "\n".join(";".join(str(x).replace(";", ",") for x in r) for r in rows) + "\n"


def city_faq(cname, where, cs, region=False):
    """Вопросы и ответы для страницы города или региона: цифры из каталога, обновляются с каждой сборкой."""
    if not cs["count"]:
        return []
    obj = "объектов недвижимости" if WIDE else "квартир"
    src = "ГИС Торги и площадок банкротства" if WIDE else "ГИС Торги"
    scope = "" if region else " (в радиусе 100 км от города)"
    f = []
    if cs.get("sources"):
        # самый массовый запрос по данным Search Console (25.10.2026): «торги по банкротству <регион> официальный сайт»
        plat = ", ".join(f"{name} ({n})" for name, _, n in cs["sources"][:6])
        f.append((f"Какой официальный сайт торгов по банкротству {where}?",
                  f"Единого официального сайта нет. Извещения о торгах по банкротству публикуются на ЕФРСБ (bankrot.fedresurs.ru) "
                  f"и в ГИС Торги (torgi.gov.ru), а сами торги идут на электронных площадках, у каждой свой сайт. Лоты {where} "
                  f"сейчас выставлены на площадках: {plat}. Здесь они собраны в один список с ссылкой на извещение на площадке."))
    f.append((f"Сколько {obj} продаётся с торгов {where}?",
              f"На {date.today().strftime('%d.%m.%Y')} в каталоге по данным {src} {cs['count']} активных лотов {where}{scope}, за последние 7 дней появилось {cs['week_new']}."))
    if cs["median_price"]:
        f.append((f"Сколько стоит {'недвижимость' if WIDE else 'квартира'} с торгов {where}?",
                  f"Медианная начальная цена лота — {rub(cs['median_price'])}" + (f", медиана за квадратный метр — {rub(cs['median_ppm2'])}." if cs["median_ppm2"] else ".") +
                  f" Самый дешёвый активный лот — {rub(cs['min_price'])}. Это стартовые цены: на аукционе цена может вырасти, на публичном предложении снижается по графику."))
    if cs["share_doli"] is not None:
        f.append((f"Что чаще всего продаётся на торгах {'в этом регионе' if region else 'в этом городе'}?",
                  f"Доли в квартирах составляют {cs['share_doli']}% активных лотов, повторные торги — {cs['share_povt']}%, лоты с зарегистрированными жильцами по тексту извещения — {cs['share_reg']}%. Доли и лоты с жильцами дешевле, но сложнее в продаже и освобождении."))
    f.append((f"Где смотреть документы по лоту {where}?",
              "В карточке лота есть ссылка на извещение и документы на площадке, где идут торги. До подачи заявки сверьте с извещением цену, задаток, сроки и состав лота: данные каталога собраны автоматически."))
    return f


def stats(lots):
    ppm = [d["ppm2"] for d in lots if d.get("ppm2")]
    cutoff = (now - timedelta(days=7)).isoformat()
    return {"count": len(lots), "median_ppm2": statistics.median(ppm) if ppm else None,
            "min_price": min((d["price"] for d in lots if d.get("price")), default=None),
            "week_new": sum(1 for d in lots if (d.get("first_seen") or "") >= cutoff),
            "closing": sum(1 for d in lots if d.get("days_left") is not None and 0 <= d["days_left"] <= 3)}


# ---------- запись ----------
def auto_stats(lots):
    n = len(lots)
    week = (now - timedelta(days=7)).isoformat()
    pct = lambda k: round(100 * sum(1 for d in lots if d.get(k)) / n) if n else 0
    return {"count": n, "week_new": sum(1 for d in lots if (d.get("first_seen") or "") >= week),
            "median_price": median([d.get("price") for d in lots]), "with_photo": pct("photo"), "with_vin": pct("has_vin"),
            "dropped": pct("price_drops")}


AUTO_FACETS = [  # slug, название, фильтр, заголовок
    ("bankrotstvo", "Банкротство", lambda d: d.get("kind") == "bankruptcy", "Машины с торгов по банкротству"),
    ("arestovannoe", "Арестованные", lambda d: d.get("kind") == "arrest", "Арестованные автомобили с торгов"),
    ("do-500-tys", "До 500 тыс. ₽", lambda d: (d.get("price") or 1e12) <= 500_000, "Машины с торгов до 500 тысяч рублей"),
    ("do-1-mln", "До 1 млн ₽", lambda d: (d.get("price") or 1e12) <= 1_000_000, "Машины с торгов до 1 млн рублей"),
    ("snizhennaya-cena", "Цена снижалась", lambda d: d.get("price_drops") or d.get("repeat"), "Машины с торгов со сниженной ценой"),
    ("s-vin", "С VIN", lambda d: d.get("has_vin"), "Машины с торгов с VIN в извещении"),
]
AUTO_APP = {"bankrotstvo": "?kind=bankruptcy", "arestovannoe": "?kind=arrest", "do-500-tys": "?price_max=500000",
            "do-1-mln": "?price_max=1000000", "snizhennaya-cena": "", "s-vin": "?has_vin=true"}


def auto_faq(lots, where="по России", region=False):
    st = auto_stats(lots)
    vt = {}
    for d in lots:
        vt[d["vtype_name"]] = vt.get(d["vtype_name"], 0) + 1
    top = ", ".join(f"{k.lower()} ({v})" for k, v in sorted(vt.items(), key=lambda x: -x[1])[:4])
    return [
        (f"Сколько машин продаётся с торгов {where} сейчас?",
         f"{st['count']} лотов техники на {date.today().strftime('%d.%m.%Y')}: {top}. Медиана цены {rub(st['median_price'])}. "
         f"Новых за неделю: {st['week_new']}. Список обновляется несколько раз в день по данным ГИС Торги и площадок банкротства."),
        ("Чем машина с торгов отличается от машины с Авито?",
         "Продавец — организатор торгов, а не владелец: осмотр по записи, торг только через ставки, оплата после победы в срок из извещения. "
         "Зато цена стартует ниже рынка, а на повторных торгах и публичном предложении снижается ещё. Машина часто с ограничениями приставов "
         "или в залоге: их снимают после покупки, это время и документы."),
        ("Как проверить машину с торгов до ставки?",
         f"По VIN из извещения: залог в реестре ФНП, розыск и ограничения ГИБДД — бесплатно; пробег по техосмотрам, ОСАГО, лизинг и такси — "
         f"в «Истории машины» за 99 ₽. У {st['with_vin']}% лотов {where} VIN есть в извещении, у остальных его запрашивают у организатора."),
    ]


SITEMAP = []
CITY_STATS = []


def write(path, tpl, sitemap=True, priority="0.6", lastmod=TODAY, **ctx):
    ctx.setdefault("canonical", cfg.SITE_URL + path)
    ctx.setdefault("noindex", False)
    ctx.setdefault("noindex_yandex", False)  # только для Яндекса: Google страницу индексирует
    ctx.setdefault("lastmod", lastmod)  # дата изменения страницы: в <time>, og:updated_time и разметке
    ctx.setdefault("og_image", None)  # фото лота вместо общей обложки: карточки лотов в мессенджерах и соцсетях
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
    if (SRC / "svc").exists():  # служебное: запасной прокси ГИС Торги для сервера (только на новом домене)
        shutil.copytree(SRC / "svc", OUT / "svc")
    if (ROOT / "check").exists():
        shutil.copytree(ROOT / "check", OUT / "check")
    city_counts = {c[0]: sum(1 for d in LOTS if d.get("city") == c[0]) for c in CITIES}
    env.globals["has_archive"] = bool(ARCHIVED)
    env.globals["has_auto"] = bool(AUTOS)
    env.globals["wide"] = WIDE
    env.globals["region_paths"] = {f"/torgi/{r[0]}/" for r in REGIONS.values()}
    env.globals["cities"] = [(c[0], c[1], c[2], city_counts[c[0]]) for c in CITIES]
    st = stats(LOTS)
    # на главной — самые выгодные понятные объекты: квартиры и дома целиком с оценкой рынка, не больше двух из одного города,
    # чтобы витрина не состояла из одной Москвы; если таких мало, показываем свежее жильё с правдоподобной ценой
    deals = by_discount([d for d in LOTS if good_deal(d)])
    board, per_place = [], {}
    for d in deals:
        place = d.get("city") or d.get("region")
        if per_place.get(place, 0) < 2:
            board.append(d)
            per_place[place] = per_place.get(place, 0) + 1
        if len(board) == 6:
            break
    board += [d for d in deals if d not in board][:6 - len(board)]  # городов с выгодными лотами мало — добираем без ограничения
    board_deals = len(board) >= 3
    if not board_deals:
        sane = [d for d in LOTS if d.get("price") and d["price"] < 1e9 and not (d.get("area") and d["price"] / d["area"] > 3e6)
                and d.get("category", "flat") in ("flat", "house") and "доля" not in (d.get("flags") or "")]
        board = sorted(sane, key=lambda d: d.get("first_seen") or "", reverse=True)[:6]
    write("/", "home.html", priority="1.0", lots=board, board_deals=board_deals, deals_count=len(deals), st=st, articles=ARTICLES[:6],
          title=(f"Недвижимость с торгов по всей России — {cfg.SITE_NAME}" if WIDE else f"Квартиры с торгов в 16 городах России — {cfg.SITE_NAME}"),
          description=("Каталог недвижимости с торгов по банкротству и арестованному имуществу по всей России: квартиры, дома, земля, коммерция. Цена к рынку, риски, сроки заявок и расчёт максимальной ставки."
                       if WIDE else "Каталог квартир с торгов в 16 городах-миллионниках и в радиусе 100 км: актуальные лоты, цены и сроки заявок. Проверка рисков и расчёт максимальной ставки."))


    def listing(path, lots, h1, crumbs, links, sub_links=(), priority="0.8", faq=None, cs=None, archive=False, budget=None, where=""):
        page_size = 60
        count = max(1, (len(lots) + page_size - 1) // page_size)
        pages = [(path if n == 1 else f"{path}page/{n}/", n) for n in range(1, count + 1)]
        # дата изменения списка — последнее изменение его лотов, а не дата сборки: иначе lastmod меняется
        # у всех страниц несколько раз в день и поисковики перестают ему доверять
        lastmod = max((d.get("lastmod") or "" for d in lots), default="") or TODAY
        app_q = ("&".join(f"category={c}" for c in ("flat", "room", "share", "house")) + f"&price_max={budget['million']}"
                 if budget else app_query(path))
        for url, n in pages:
            suffix = f" — страница {n}" if n > 1 else ""
            page_crumbs = crumbs + ([(f"Страница {n}", url)] if n > 1 else [])
            if archive:
                description = f"{h1}: {len(lots)} карточек. История предложений, сроки и ссылки на источники. Результат продажи не подтверждён."
            elif cs and cs.get("sources"):
                plat = ", ".join(name for name, _, _ in cs["sources"][:4])
                description = f"{h1}: {len(lots)} актуальных лотов со всех площадок ({plat}) — банкротство и арест, цены, сроки заявок, ссылки на извещения."
            else:
                description = f"{h1}: {len(lots)} актуальных лотов — цены, сроки заявок и сведения об объектах."
            tail = "архив" if archive else ("все площадки, " if cs and n == 1 else "") + "актуальные лоты " + TODAY[:4]
            # страницы 2+ не кладём в sitemap: Google и так находит их по ссылкам, а 600 таких адресов в карте
            # раздували «обнаружена, не проиндексирована». Подборки по бюджету и архив повторяют общий каталог,
            # поэтому их глубокие страницы закрыты noindex, follow (ссылки на лоты по ним передаются).
            deep_dup = n > 1 and (budget is not None or archive)
            write(url, "torgi.html", priority=priority, lastmod=lastmod, lots=lots[(n-1)*page_size:n*page_size], sitemap=n == 1,
                  st=stats(lots), h1=h1 + suffix, crumbs=page_crumbs, facet_links=links,
                  town_links=sorted(sub_links), noindex=not lots or deep_dup, faq=(faq or []) if n == 1 else [],
                  cs=cs if n == 1 else None, pagination=pages, current_page=n, archive=archive, budget=budget, app_q=app_q,
                  title=f"{h1}{suffix} — {tail}", where=where,
                  description=description + suffix)

    budgets =[dict(budget_summary(LOTS, n*1_000_000), url=f"/torgi/do-{n}-mln/", million=n) for n in (1, 2, 3)]
    budget_links = [("/byudzhet/", "Выбрать бюджет")] + [(b["url"], f"До {b['million']} млн ₽ ({b['count']})") for b in budgets if b["count"]]
    env.globals["budget_links"] = budget_links
    write("/byudzhet/", "budget.html", budgets=budgets,
          city_budgets=[(c[0], c[1], [budget_summary([d for d in LOTS if d.get("city") == c[0]], n*1_000_000)["count"] for n in (1, 2, 3)]) for c in CITIES],
          title="Что можно найти на торгах до 1, 2 и 3 млн рублей",
          description="Сравните жильё с торгов по бюджету и городам: актуальные цены, доли и комнаты, состав лотов и расходы сверх ставки.")
    for b in budgets:
        listing(b["url"], budget_lots(LOTS, b["cap"]), f"Жильё с торгов до {b['million']} млн рублей",
                [("Лоты", "/torgi/"), ("Бюджет", "/byudzhet/"), (f"До {b['million']} млн ₽", b["url"])], budget_links, budget=b)

    city_links = [("/torgi/", "Все города")] + [(f"/torgi/{c[0]}/", f"{c[1]} ({city_counts[c[0]]})") for c in CITIES if city_counts[c[0]]]
    by_region = {}
    for d in LOTS:
        if d.get("region") in REGIONS and d["region"] not in ("77", "78"):  # Москва и Петербург — страницы городов
            by_region.setdefault(d["region"], []).append(d)
    region_links = sorted(((f"/torgi/{REGIONS[c][0]}/", f"{REGIONS[c][1]} ({len(v)})") for c, v in by_region.items()), key=lambda x: x[1])
    # на общей странице каталога наверху только подборки; города и регионы — в свёрнутом списке, чтобы лоты были видны сразу
    listing("/torgi/", LOTS, f"{OBJ} с торгов {GEO}", [("Лоты", "/torgi/")],
            [(f"/torgi/{f[0]}/", f[1]) for f in FACETS if any(f[2](d) for d in LOTS)], city_links[1:] + region_links, priority="0.9")
    for code, rl in by_region.items():
        rslug, rname, rwhere = REGIONS[code]
        rfacets = [(f, facet_lots(f, rl)) for f in FACETS]
        rfacets = [(f, v) for f, v in rfacets if len(v) >= 3]
        rlinks = [(f"/torgi/{rslug}/", "Все")] + [(f"/torgi/{rslug}/{f[0]}/", f[1]) for f, v in rfacets]
        rcrumbs = [("Лоты", "/torgi/"), (rname, f"/torgi/{rslug}/")]
        rcs = city_stats(rl)
        listing(f"/torgi/{rslug}/", rl, f"Недвижимость с торгов {rwhere}", rcrumbs, rlinks, region_links, "0.8",
                faq=city_faq(rname, rwhere, rcs, region=True), cs=rcs, where=rwhere)
        for f, v in rfacets:
            listing(f"/torgi/{rslug}/{f[0]}/", v, f"{f[3]}: {rname}", rcrumbs + [(f[1], f"/torgi/{rslug}/{f[0]}/")], rlinks, region_links, "0.7")
    for slug, name, flt, h1 in FACETS:
        fl = facet_lots((slug, name, flt, h1), LOTS)
        if fl or slug == "doli":
            listing(f"/torgi/{slug}/", fl, f"{h1} {GEO}", [("Лоты", "/torgi/"), (name, f"/torgi/{slug}/")], city_links)
    for cslug, cname, where in CITIES:
        cl = [d for d in LOTS if d.get("city") == cslug]
        subs = {}
        for d in cl:
            for t in (d.get("district"), d.get("town")):
                if t:
                    subs.setdefault(t, []).append(d)
        subs = {t: v for t, v in subs.items() if len(v) >= 2 or ("район" in t or "округ" in t)}
        sub_links = [(f"/torgi/{cslug}/{translit(t)}/", f"{t} ({len(v)})") for t, v in subs.items()]
        facets_here = [(f, facet_lots(f, cl)) for f in FACETS]
        facets_here = [(f, v) for f, v in facets_here if len(v) >= 3]
        links = [(f"/torgi/{cslug}/", "Все")] + [(f"/torgi/{cslug}/{f[0]}/", f[1]) for f, v in facets_here]
        base_crumbs = [("Лоты", "/torgi/"), (cname, f"/torgi/{cslug}/")]
        cs = city_stats(cl)
        CITY_STATS.append((cslug, cname, where, cs))
        listing(f"/torgi/{cslug}/", cl, f"{OBJ} с торгов {where}", base_crumbs, links, sub_links, "0.9",
                faq=city_faq(cname, where, cs), cs=cs, where=where)
        for f, v in facets_here:
            listing(f"/torgi/{cslug}/{f[0]}/", v, f"{f[3]}: {cname}", base_crumbs + [(f[1], f"/torgi/{cslug}/{f[0]}/")], links, sub_links)
        for t, v in subs.items():
            listing(f"/torgi/{cslug}/{translit(t)}/", v, f"{OBJ} с торгов: {t}", base_crumbs + [(t, f"/torgi/{cslug}/{translit(t)}/")], links, sub_links, "0.7")

    if ARCHIVED:
        listing("/torgi/arhiv/", ARCHIVED, "Архив предложений с торгов", [("Лоты", "/torgi/"), ("Архив", "/torgi/arhiv/")], city_links, archive=True)
    # похожие — того же типа (квартира к квартире, доля к доле, участок к участку): сначала в городе, потом в регионе,
    # ближе по цене; если такого типа рядом нет, блок не показываем, чем подсовывать другое
    sim_place, sim_region = {}, {}
    for x in LOTS:
        sim_place.setdefault((x.get("city") or x.get("region"), x.get("category")), []).append(x)
        sim_region.setdefault((x.get("region"), x.get("category")), []).append(x)

    def similar_to(d):
        def closest(pool):
            p = d.get("price") or 0
            return sorted((x for x in pool if x["id"] != d["id"]), key=lambda x: abs((x.get("price") or 0) - p))
        out = closest(sim_place.get((d.get("city") or d.get("region"), d.get("category")), []))[:4]
        if len(out) < 4 and d.get("region"):
            out += [x for x in closest(sim_region.get((d.get("region"), d.get("category")), [])) if x not in out][:4 - len(out)]
        return out

    thin_n = yandex_n = 0
    for d in CARDS:
        similar = similar_to(d)
        active = d["status"] == "active"
        thin = active and thin_card(d, set(CITY_NAME.values()))
        thin_n += thin
        to_yandex = active and not thin and yandex_card(d, set(CITY_NAME.values()), CITY_NAME)
        yandex_n += to_yandex
        # карточка снятого лота остаётся для людей и ссылок, но из индекса и sitemap уходит: таких карточек
        # было около трети карты сайта, и Google тратил обход на них вместо актуальных лотов
        write(f"/torgi/lot/{d['id']}/", "lot.html", priority="0.5", lastmod=d['lastmod'], noindex=not active or thin,
              noindex_yandex=not to_yandex, d=d, active=active, similar=similar, og_image=d.get("photo") if active else None,
              # цена в заголовке различает лоты одного торга по одному адресу (машиноместа, кладовые меньше 8 м²):
              # без неё у таких карточек одинаковые title и description, и Google склеивает их как копии
              title=f"{d['label']} с торгов" + (f" за {rub(d['price'])}" if d.get("price") else "") + f": {d['caddr'][:60]}" + (" — архив" if not active else ""),
              # пересказ извещения в описании: у 20 тысяч карточек сниппет перестаёт быть одинаковым
              description=f"{d['label']} с торгов: {d['caddr']}. " + (f"Начальная цена {rub(d.get('price'))}. " + (d['excerpt'][:140].rsplit(' ', 1)[0].rstrip(' .,;:') + "… " if d.get('excerpt') else "") + "Срок подачи заявки и сведения об объекте." if active else "Архив предложения. Уточняйте статус и результат у организатора торгов."))
    print(f"пустых карточек без адреса, площади и описания (noindex): {thin_n}")
    print(f"карточек, открытых Яндексу (остальные meta yandex noindex): {yandex_n}")
    history_path.write_text(json.dumps(CARDS, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---------- раздел /auto/: техника с торгов ----------
    def auto_listing(path, lots, h1, crumbs, priority="0.7", faq=None, type_links=(), facet_links=(), make_links=(), region_links=(),
                     cs=None, archive=False, app_q=""):
        page_size = 60
        count = max(1, (len(lots) + page_size - 1) // page_size)
        pages = [(path if n == 1 else f"{path}page/{n}/", n) for n in range(1, count + 1)]
        lastmod = max((d.get("lastmod") or "" for d in lots), default="") or TODAY
        for url, n in pages:
            suffix = f" — страница {n}" if n > 1 else ""
            write(url, "auto.html", priority=priority, lastmod=lastmod, lots=lots[(n-1)*page_size:n*page_size], sitemap=n == 1,
                  st=auto_stats(lots), h1=h1 + suffix, crumbs=crumbs + ([(f"Страница {n}", url)] if n > 1 else []),
                  type_links=list(type_links), facet_links=list(facet_links), make_links=list(make_links), region_links=list(region_links),
                  noindex=not lots or (n > 1 and archive), faq=(faq or []) if n == 1 else [], cs=cs if n == 1 else None,
                  pagination=pages, current_page=n, archive=archive, app_q=app_q,
                  title=f"{h1}{suffix} — {'архив' if archive else 'актуальные лоты ' + TODAY[:4]}",
                  description=(f"{h1}: {len(lots)} карточек. История предложений, сроки и ссылки на источники. Результат продажи не подтверждён."
                               if archive else f"{h1}: {len(lots)} актуальных лотов — цены, год, пробег, сроки заявок, что проверить по VIN до ставки.") + suffix)

    if AUTOS:
        by_vt, by_reg, by_make = {}, {}, {}
        for d in AUTOS:
            by_vt.setdefault(d["vtype"], []).append(d)
            if d.get("region_slug"):
                by_reg.setdefault(d["region"], []).append(d)
            if d.get("make_slug"):
                by_make.setdefault(d["make_slug"], []).append(d)
        type_links = [("/auto/", f"Все ({len(AUTOS)})")] + [(f"/auto/{VTYPES[k][0]}/", f"{VTYPES[k][1]} ({len(v)})")
                                                           for k, v in sorted(by_vt.items(), key=lambda x: -len(x[1]))]
        facet_links = [(f"/auto/{f[0]}/", f[1]) for f in AUTO_FACETS if any(f[2](d) for d in AUTOS)]
        makes = {k: v for k, v in by_make.items() if len(v) >= 3}
        make_links = [(f"/auto/marka/{k}/", f"{v[0]['make']} ({len(v)})") for k, v in sorted(makes.items(), key=lambda x: -len(x[1]))]
        region_links = sorted(((f"/auto/{REGIONS[c][0]}/", f"{REGIONS[c][1]} ({len(v)})") for c, v in by_reg.items()), key=lambda x: x[1])
        acrumbs = [("Авто с торгов", "/auto/")]
        auto_listing("/auto/", AUTOS, "Автомобили и техника с торгов по всей России", acrumbs, "0.9", faq=auto_faq(AUTOS),
                     type_links=type_links, facet_links=facet_links, make_links=make_links, region_links=region_links, cs=auto_stats(AUTOS))
        for k, v in by_vt.items():
            vslug, vname, _ = VTYPES[k]
            vmakes = {}
            for d in v:
                if d.get("make_slug") in makes:
                    vmakes.setdefault(d["make_slug"], []).append(d)
            vfacets = [(f"/auto/{vslug}/{f[0]}/", f[1]) for f in AUTO_FACETS if sum(1 for d in v if f[2](d)) >= 3]
            auto_listing(f"/auto/{vslug}/", v, f"{vname} с торгов по всей России", acrumbs + [(vname, f"/auto/{vslug}/")], "0.8",
                         faq=auto_faq(v, f"по России ({vname.lower()})"), type_links=type_links, facet_links=vfacets,
                         make_links=[(f"/auto/marka/{mk}/", f"{mv[0]['make']} ({len(mv)})") for mk, mv in sorted(vmakes.items(), key=lambda x: -len(x[1]))],
                         region_links=sorted(((f"/auto/{REGIONS[c][0]}/{vslug}/", f"{REGIONS[c][1]} ({len(rv)})") for c, rv in by_reg.items()
                                              if sum(1 for d in rv if d["vtype"] == k) >= 3), key=lambda x: x[1]),
                         cs=auto_stats(v), app_q=f"?vtype={k}")
            for slug, name, flt, h1 in AUTO_FACETS:
                fl = [d for d in v if flt(d)]
                if len(fl) >= 3:
                    auto_listing(f"/auto/{vslug}/{slug}/", fl, f"{h1}: {vname.lower()}", acrumbs + [(vname, f"/auto/{vslug}/"), (name, f"/auto/{vslug}/{slug}/")], "0.6",
                                 type_links=type_links, facet_links=vfacets, app_q=f"?vtype={k}{AUTO_APP[slug].replace('?', '&')}")
        for slug, name, flt, h1 in AUTO_FACETS:
            fl = [d for d in AUTOS if flt(d)]
            if fl:
                auto_listing(f"/auto/{slug}/", fl, f"{h1} по всей России", acrumbs + [(name, f"/auto/{slug}/")], "0.7",
                             type_links=type_links, facet_links=facet_links, app_q=AUTO_APP[slug])
        for code, rl in by_reg.items():
            rslug, rname, rwhere = REGIONS[code]
            rcrumbs = acrumbs + [(rname, f"/auto/{rslug}/")]
            rvt = {}
            for d in rl:
                rvt.setdefault(d["vtype"], []).append(d)
            rtypes = [(f"/auto/{rslug}/", f"Все ({len(rl)})")] + [(f"/auto/{rslug}/{VTYPES[k][0]}/", f"{VTYPES[k][1]} ({len(v)})")
                                                                  for k, v in sorted(rvt.items(), key=lambda x: -len(x[1])) if len(v) >= 3]
            auto_listing(f"/auto/{rslug}/", rl, f"Автомобили и техника с торгов {rwhere}", rcrumbs, "0.8", faq=auto_faq(rl, rwhere, True),
                         type_links=rtypes, region_links=region_links, cs=auto_stats(rl), app_q=f"?region={code}")
            for k, v in rvt.items():
                if len(v) >= 3:
                    vslug, vname, _ = VTYPES[k]
                    auto_listing(f"/auto/{rslug}/{vslug}/", v, f"{vname} с торгов {rwhere}", rcrumbs + [(vname, f"/auto/{rslug}/{vslug}/")], "0.7",
                                 type_links=rtypes, region_links=region_links, cs=auto_stats(v), app_q=f"?region={code}&vtype={k}")
        for mk, mv in makes.items():
            auto_listing(f"/auto/marka/{mk}/", mv, f"{mv[0]['make']} с торгов по всей России", acrumbs + [(mv[0]["make"], f"/auto/marka/{mk}/")], "0.7",
                         type_links=type_links, make_links=make_links, cs=auto_stats(mv), app_q=f"?make={mv[0]['make']}")
        if AUTO_ARCHIVED:
            auto_listing("/auto/arhiv/", AUTO_ARCHIVED, "Архив машин с торгов", acrumbs + [("Архив", "/auto/arhiv/")], "0.3", archive=True)
        pool_rv, pool_v = {}, {}
        for x in AUTOS:
            pool_rv.setdefault((x.get("region"), x["vtype"]), []).append(x)
            pool_v.setdefault(x["vtype"], []).append(x)

        def similar_auto(d):
            def closest(pool):
                p = d.get("price") or 0
                return sorted((x for x in pool if x["id"] != d["id"]), key=lambda x: abs((x.get("price") or 0) - p))
            out = closest(pool_rv.get((d.get("region"), d["vtype"]), []))[:4]
            if len(out) < 4:
                out += [x for x in closest(pool_v.get(d["vtype"], [])) if x not in out][:4 - len(out)]
            return out

        for d in AUTO_CARDS:
            active = d["status"] == "active"
            write(f"/auto/lot/{d['id']}/", "auto_lot.html", priority="0.5", lastmod=d["lastmod"], noindex=not active,
                  d=d, active=active, similar=similar_auto(d) if active else [], og_image=d.get("photo") if active else None,
                  title=f"{d['label']} с торгов" + (f" {d['region_where']}" if d.get("region_where") else "") + (f" за {rub(d['price'])}" if d.get("price") else "") + (" — архив" if not active else ""),
                  description=(f"{d['label']} с торгов{' ' + d['region_where'] if d.get('region_where') else ''}: {rub(d.get('price'))}. "
                               + (d["excerpt"][:140].rsplit(" ", 1)[0].rstrip(" .,;:") + "… " if d.get("excerpt") else "")
                               + ("Срок заявки, что проверить по VIN до ставки." if active else "Архив предложения, результат торгов не подтверждён.")))
    if AUTO_CARDS or auto_history_path.exists():
        auto_history_path.write_text(json.dumps(AUTO_CARDS, ensure_ascii=False, indent=2), encoding="utf-8")

    pages = [("uslugi", "services.html", "Услуги на торгах недвижимостью — покупателям и кредиторам",
              "Покупка под ключ, агентское участие, помощь после покупки, коммерческий подбор. Подготовка лотов и сопровождение продажи активов для кредиторов."),
             ("kupit-kvartiru-s-torgov", "buy.html", "Купить квартиру с торгов под ключ — подбор и сопровождение",
              "Подбор и сопровождение покупки квартиры с торгов в городах-миллионниках России. Проверка рисков, расчёт ставки и участие. Осмотр объекта согласуем отдельно."),
             ("proverka-lota", "check.html", "Проверка лота перед торгами: юридическая и рыночная",
              "Проверим квартиру с торгов до подачи заявки: обременения, зарегистрированные, долги, рыночная цена и максимальная ставка."),
             ("investoram", "invest.html", "Инвесторам: недвижимость с торгов в городах России",
              "Лоты в городах-миллионниках России под перепродажу или аренду. Расчёт экономики, проверка и сопровождение покупки на ваше имя. Доход не гарантирован."),
             ("kalkulyator-stavki", "calc.html", "Калькулятор максимальной ставки на торгах по недвижимости",
              "Рассчитайте, сколько можно предложить на торгах, чтобы сделка осталась в плюсе: цена продажи, расходы, срок, налоги."),
             ("proverka-avto-po-vin", "avto_vin.html", "Проверка авто по VIN: залог и ограничения бесплатно, «История машины» за 99 ₽",
              "Проверка машины по VIN: залоги, ограничения и розыск бесплатно; лизинг, пробег по техосмотрам, ОСАГО и прошлые продажи в «Истории машины» за 99 ₽."),
             ("slovar", "glossary.html", "Словарь терминов торгов по банкротству и арестованному имуществу",
              "Короткие определения: задаток, шаг аукциона, публичное предложение, цена отсечения, ЕФРСБ, ЭТП и другие термины торгов."),
             ("proverka-lota/primer", "sample.html", "Пример отчёта по проверке лота перед торгами",
              "Как выглядит полная проверка квартиры с торгов: процедура, дело о банкротстве, история квартиры, жильцы, долги, цена и стратегия ставки."),
             ("o-nas", "about.html", "О нас и контакты", "Кто мы, как работаем, реквизиты и контакты."),
             ("kontakty", "kontakty.html", "Контакты ТоргГида: почта, Telegram, сотрудничество",
              "Как связаться с ТоргГидом: почта и Telegram для вопросов по лотам и отчётам, сотрудничество для управляющих, кредиторов и партнёров."),
             ("oplata", "oplata.html", "Оплата, получение и возврат",
              "Как оплатить отчёт ТоргГида картой или через СБП, как его получить и как вернуть деньги."),
             ("oferta", "oferta.html", "Публичная оферта на оказание информационных услуг",
              "Условия платных услуг ТоргГида: отчёты по лотам торгов, оплата, сроки, возврат, реквизиты."),
             ("politika", "privacy.html", "Политика обработки персональных данных", "Политика обработки персональных данных.")]
    for slug, tpl, title, desc in pages:
        write(f"/{slug}/", tpl, sitemap=slug not in ("politika", "oferta"), priority="0.8", title=title, description=desc, st=st)
    rp = SRC / "data" / "results.json"
    RES = json.loads(rp.read_text(encoding="utf-8")) if rp.exists() else []
    res_rows = []
    for cslug, cname, _w in CITIES:
        r = [x for x in RES if x.get("city") == cslug or (not x.get("city") and cslug == "sankt-peterburg" and str(x.get("region")) in ("78", "47"))]
        if not r:
            continue
        ok = [x for x in r if x.get("result_status") == "SUCCEED"]
        ratios = [x["result_price"] / x["price"] for x in ok if x.get("result_price") and x.get("price")]
        res_rows.append((cslug, cname, len(r), round(100 * len(ok) / len(r)), median(ratios)))
    indexes = [ix for ix in (month_index(CARDS, ym) for ym in index_months(CARDS)) if ix]
    for i, ix in enumerate(indexes):
        prev = indexes[i - 1] if i else None
        write(f"/analitika/{ix['ym']}/", "index_month.html", priority="0.8", lastmod=ix["as_of"], ix=ix, prev=prev,
              months=indexes,
              title=f"Индекс торгов ТоргГид: {ix['month']} {ix['year']} — недвижимость с торгов в России",
              description=f"{ix['count']} лотов недвижимости с торгов в {ix['regions']} регионах России {ix['month_prep']} {ix['year']}: "
                          f"медианы цен, скидка квартир к рынку, доля публичного предложения и повторных торгов. "
                          f"Данные на {date.fromisoformat(ix['as_of']).strftime('%d.%m.%Y')}, CSV для скачивания.")
        (OUT / "analitika" / ix["ym"] / "indeks.csv").write_text(index_csv(ix), encoding="utf-8-sig")
    env.globals["latest_index"] = indexes[-1] if indexes else None
    tot = city_stats(LOTS)
    write("/analitika/", "analytics.html", priority="0.8", rows=CITY_STATS, tot=tot, res_rows=res_rows,
          title=f"Статистика торгов недвижимостью по городам России, {date.today().strftime('%m.%Y')}",
          description="Сколько квартир продаётся с торгов в Москве, Петербурге и других миллионниках, медианные цены за м², доля долей и повторных торгов. Обновляется несколько раз в день.")
    write("/podpiska/", "subscribe.html", priority="0.6", title="Подборка лотов с торгов в Telegram",
          description="Пришлём новые лоты с торгов по вашему городу, бюджету и типу жилья в Telegram.")
    write("/partneram/", "partners.html", priority="0.6", title="Продвижение лотов: управляющим и залоговым кредиторам",
          description="Покажем ваш лот покупателям и инвесторам: карточка на сайте, Telegram, подготовка лота к продаже — фото, документы, проверка.")
    write("/stati/", "articles.html", priority="0.7", articles=ARTICLES, title="Статьи о покупке недвижимости с торгов",
          description="Как устроены торги по банкротству и арестованному имуществу, риски, проверка лота, расчёт ставки.")
    for a in ARTICLES:
        preferred = [slug.strip() for slug in a.get("related", "").split(",") if slug.strip()]
        candidates = {x["slug"]: x for x in ARTICLES if x["slug"] != a["slug"]}
        related = [candidates.pop(slug) for slug in dict.fromkeys(preferred) if slug in candidates]
        related.extend(candidates.values())
        write(f"/stati/{a['slug']}/", "article.html", priority="0.7", lastmod=a.get("updated") or a.get("date") or TODAY,
              a=a, related=related[:4], title=a["title"], description=a["description"])
    write(AUTHOR["path"], "author.html", priority="0.5", articles=ARTICLES,
          parts=[{"@type": "Article", "headline": a["title"], "url": f"{cfg.SITE_URL}/stati/{a['slug']}/"} for a in ARTICLES],
          updated=max((a.get("updated") or a.get("date") or TODAY for a in ARTICLES), default=TODAY),
          lastmod=max((a.get("updated") or a.get("date") or TODAY for a in ARTICLES), default=TODAY),
          title=f"{AUTHOR['name']} — автор статей о торгах недвижимостью",
          description=f"{AUTHOR['name']}, {AUTHOR['role']}. Статьи о торгах по банкротству и арестованному имуществу, проверке лотов и расчёте ставки.")
    write("/404.html", "404.html", sitemap=False, noindex=True, title="Страница не найдена", description="")

    write_sitemaps()
    (OUT / "robots.txt").write_text("\n".join([
        "User-agent: *", "Allow: /", "Disallow: /check/",
        # contentsignals.org: нейропоиску и ответам ИИ цитировать можно (нам нужны переходы), обучать модели — нет
        "Content-Signal: search=yes, ai-input=yes, ai-train=no", "",
        "User-agent: Yandex", "Allow: /", "Disallow: /check/",
        "Clean-param: utm_source&utm_medium&utm_campaign&utm_content&utm_term&yclid&ysclid /",
        f"Sitemap: {cfg.SITE_URL}/sitemap-yandex.xml", "",
        "User-agent: YandexAdditional", "Allow: /", "", "User-agent: YandexAdditionalBot", "Allow: /", "",
        "User-agent: GPTBot", "Allow: /", "", "User-agent: OAI-SearchBot", "Allow: /", "",
        "User-agent: PerplexityBot", "Allow: /", "", "User-agent: ClaudeBot", "Allow: /", "",
        "User-agent: Google-Extended", "Allow: /", "", "User-agent: Applebot-Extended", "Allow: /", "",
        f"Sitemap: {cfg.SITE_URL}/sitemap.xml", ""]), encoding="utf-8")
    arts = "\n".join(f"- [{a['title']}]({cfg.SITE_URL}/stati/{a['slug']}/): {a['description']}" for a in ARTICLES)
    regions_line = ", ".join(f"[{REGIONS[c][1]}]({cfg.SITE_URL}/torgi/{REGIONS[c][0]}/)" for c in sorted(by_region, key=lambda c: REGIONS[c][1]))
    cities_line = ", ".join(f"[{c[1]}]({cfg.SITE_URL}/torgi/{c[0]}/)" for c in CITIES if city_counts[c[0]])
    facts = [f"- Активных лотов в каталоге: {st['count']} (данные на {TODAY}), новых за 7 дней: {st['week_new']}, приём заявок закрывается в ближайшие 3 дня: {st['closing']}."]
    if tot.get("median_ppm2"):
        facts.append(f"- Медиана начальной цены за м² по всему каталогу: {rub(tot['median_ppm2'])}; доля лотов-долей: {tot['share_doli']}%, повторных торгов: {tot['share_povt']}%.")
    if indexes:
        ix = indexes[-1]
        facts.append(f"- Индекс торгов ТоргГид, {ix['month']} {ix['year']}: {ix['count']} лотов недвижимости в {ix['regions']} регионах"
                     + (f", медиана начальной цены квартиры {rub(ix['flat_median_price'])}" if ix['flat_median_price'] else "")
                     + (f", медиана скидки квартир к рынку {ix['flat_median_discount']}%" if ix['flat_median_discount'] is not None else "")
                     + f", публичное предложение {ix['public_share']}% лотов ({cfg.SITE_URL}/analitika/{ix['ym']}/).")
    if AUTOS:
        ast = auto_stats(AUTOS)
        facts.append(f"- Техника с торгов: {ast['count']} лотов (легковые, грузовые, спецтехника и другие), медиана цены {rub(ast['median_price'])}, "
                     f"у {ast['with_vin']}% VIN указан в извещении ({cfg.SITE_URL}/auto/).")
    facts += ["- Источники: ГИС Торги (torgi.gov.ru) для арестованного и государственного имущества; электронные площадки банкротства по 127-ФЗ. Данные в карточке лота сверяйте с извещением организатора.",
              "- Задаток на торгах по банкротству не больше 20% начальной цены (ст. 110 127-ФЗ); оплата в течение 30 дней после подписания договора.",
              "- Повторные торги: начальная цена ниже на 10% (банкротство) или на 15% (арестованное имущество, 229-ФЗ)."]
    (OUT / "llms.txt").write_text(f"""# {cfg.SITE_NAME}

> {cfg.SITE_NAME} (torggid.ru) — {"каталог недвижимости с торгов по банкротству и арестованному имуществу по всей России: квартиры, дома, земля, коммерция с ГИС Торги и электронных площадок банкротства" if WIDE else "каталог жилья с торгов в 16 городах-миллионниках России и в радиусе 100 км"}. По каждому лоту: цена к рынку, риски со статусом «подтверждено / заявлено / нет данных», срок заявки и расчёт максимальной ставки. {cfg.SITE_OWNER}. Не организатор торгов; задаток и оплата объекта идут организатору торгов и продавцу.

## Факты для цитирования
{chr(10).join(facts)}
- При цитировании указывайте «ТоргГид (torggid.ru)» и дату данных. Статистика обновляется несколько раз в день.

## География
{"Все регионы России. " if WIDE else ""}Страницы городов: {cities_line or ", ".join(c[1] for c in CITIES)}.{(" Страницы регионов: " + regions_line + ".") if regions_line else ""} Пустая подборка означает, что активных лотов по условию сейчас нет, а не отсутствие предложений на рынке.

## Разделы
- [Актуальные лоты]({cfg.SITE_URL}/torgi/): обновляются несколько раз в день по данным {"ГИС Торги и площадок банкротства (МЭТС, ЦентрЕР, УТПЛ, НИС, РАД, ЦДТ, ЭТП ГПБ, Фабрикант)" if WIDE else "ГИС Торги"}
- [Подборки по бюджету]({cfg.SITE_URL}/byudzhet/): что продаётся до 1, 2 и 3 млн ₽
- [Авто и спецтехника с торгов]({cfg.SITE_URL + "/auto/" if AUTOS else cfg.AUTO_URL}){": " + str(len(AUTOS)) + " лотов, страницы по типам техники, регионам и маркам; карта и фильтры: " + cfg.AUTO_URL if AUTOS else ""}
- [Проверка авто по VIN]({cfg.SITE_URL}/proverka-avto-po-vin/): залоги, ограничения, розыск бесплатно; лизинг, пробег, ОСАГО в «Истории машины» за 99 ₽
- [Покупка квартиры с торгов под ключ]({cfg.SITE_URL}/kupit-kvartiru-s-torgov/)
- [Проверка лота перед торгами]({cfg.SITE_URL}/proverka-lota/)
- [Инвесторам]({cfg.SITE_URL}/investoram/)
- [Калькулятор максимальной ставки]({cfg.SITE_URL}/kalkulyator-stavki/)
- [Словарь терминов торгов]({cfg.SITE_URL}/slovar/)
- [Статистика торгов по городам]({cfg.SITE_URL}/analitika/)
{f"- [Индекс торгов ТоргГид: {indexes[-1]['month']} {indexes[-1]['year']}]({cfg.SITE_URL}/analitika/{indexes[-1]['ym']}/): ежемесячные открытые данные по всей России, CSV" + chr(10) if indexes else ""}- [Карта и фильтры каталога]({cfg.APP_URL}/)

## Услуги и цены
- Отчёт по лоту (Рентген): {cfg.REPORT_PRICE} ₽, в приложении {cfg.APP_URL}/
{f"- Полная проверка лота перед торгами: {cfg.PRICE_CHECK}, {cfg.SITE_URL}/proverka-lota/" + chr(10) if cfg.PRICE_CHECK else ""}- Покупка квартиры с торгов под ключ: 10 000 ₽ при заказе + 2% от цены покупки при победе, но не меньше 45 000 ₽, {cfg.SITE_URL}/kupit-kvartiru-s-torgov/
- Работаем дистанционно по всей России: торги проходят на электронных площадках.

## Контакты
- {f"Телефон: {cfg.SITE_PHONE}, " if cfg.SITE_PHONE else ""}{f"Telegram-бот: {cfg.TG_BOT}, " if cfg.TG_BOT else ""}почта: {cfg.SITE_EMAIL}, часы работы: {HOURS[0]} по Москве
- {cfg.SITE_OWNER}{f", ИНН {cfg.SITE_INN}" if cfg.SITE_INN else ""}, {cfg.SITE_ADDRESS}
- Автор статей: [{AUTHOR['name']}]({cfg.SITE_URL}{AUTHOR['path']}), {AUTHOR['role']}
{"".join(f"- Профиль: {u}" + chr(10) for u in same_as())}
## Статьи
{arts}
""", encoding="utf-8")
    (OUT / ".htaccess").write_text("""AddDefaultCharset UTF-8
ErrorDocument 404 /404.html
Options -Indexes
RewriteEngine On
RewriteCond %{HTTPS} off [OR]
RewriteCond %{HTTP_HOST} ^www\\. [NC]
RewriteRule ^(.*)$ """ + cfg.SITE_URL + """/$1 [R=301,L]
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
    build_old_domain()
    print(f"OK: страниц {len(SITEMAP)} в sitemap, лотов {len(LOTS)}, техники {len(AUTOS)}, статей {len(ARTICLES)}")


def write_sitemaps(chunk=5000):
    """Индекс карт сайта: страницы разделов, каталог (списки) и карточки лотов отдельными файлами.
    Поисковики обходят маленькие карты быстрее, а по индексации каждой части видно, где проблема."""
    def urlset(rows):
        body = "".join(f"<url><loc>{cfg.SITE_URL}{u}</loc><lastmod>{m}</lastmod><priority>{p}</priority></url>" for u, m, p in rows)
        return f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{body}</urlset>'
    groups = {"sitemap-pages.xml": [], "sitemap-catalog.xml": [], "sitemap-auto.xml": []}
    lots, autos = [], []
    for row in SITEMAP:
        if row[0].startswith("/torgi/lot/"):
            lots.append(row)
        elif row[0].startswith("/auto/lot/"):
            autos.append(row)
        elif row[0].startswith("/torgi/"):
            groups["sitemap-catalog.xml"].append(row)
        elif row[0].startswith("/auto/"):
            groups["sitemap-auto.xml"].append(row)
        else:
            groups["sitemap-pages.xml"].append(row)
    for i in range(0, len(lots), chunk):
        groups[f"sitemap-lots-{i // chunk + 1}.xml"] = lots[i:i + chunk]
    for i in range(0, len(autos), chunk):
        groups[f"sitemap-auto-lots-{i // chunk + 1}.xml"] = autos[i:i + chunk]
    index = []
    for name, rows in groups.items():
        if not rows:
            continue
        (OUT / name).write_text(urlset(rows), encoding="utf-8")
        index.append(f"<sitemap><loc>{cfg.SITE_URL}/{name}</loc><lastmod>{max(r[1] for r in rows)}</lastmod></sitemap>")
    (OUT / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?><sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                                     + "".join(index) + "</sitemapindex>", encoding="utf-8")
    # отдельная карта для Вебмастера Яндекса: только хабы, статьи и сервисы (без карточек и глубоких подборок
    # по районам), чтобы молодой домен обходили по сильным страницам, а не по тысячам однотипных
    facet_slugs = {f[0] for f in FACETS}

    def for_yandex(path):
        parts = path.strip("/").split("/")
        if parts[0] == "torgi":
            return len(parts) <= 2 or (len(parts) == 3 and parts[1] in CITY_NAME and parts[2] in facet_slugs)
        if parts[0] == "auto":
            return len(parts) <= 2
        return True
    yandex = [r for r in SITEMAP if for_yandex(r[0])]
    (OUT / "sitemap-yandex.xml").write_text(urlset(yandex), encoding="utf-8")
    print(f"sitemap-yandex.xml: {len(yandex)} адресов")


OLD_OUT = ROOT / "_site_old_domain"


def build_old_domain():
    """public_html старого домена kirpichinvest.ru после переезда: постраничный 301 на тот же путь нового домена.
    Файлы подтверждения Вебмастера/Search Console и ключ IndexNow отдаются как есть, чтобы не потерять права
    на старый сайт во время склейки."""
    if OLD_OUT.exists():
        shutil.rmtree(OLD_OUT)
    OLD_OUT.mkdir()
    keep = sorted(f.name for f in (SRC / "root").iterdir()) if (SRC / "root").exists() else []
    for name in keep:
        shutil.copy(SRC / "root" / name, OLD_OUT / name)
    if getattr(cfg, "INDEXNOW_KEY", ""):
        keep.append(f"{cfg.INDEXNOW_KEY}.txt")
        (OLD_OUT / keep[-1]).write_text(cfg.INDEXNOW_KEY, encoding="utf-8")
    exempt = "".join(f"RewriteCond %{{REQUEST_URI}} !^/{re.escape(n)}$\n" for n in keep)
    (OLD_OUT / ".htaccess").write_text(f"""AddDefaultCharset UTF-8
Options -Indexes
RewriteEngine On
{exempt}RewriteRule ^(.*)$ {cfg.SITE_URL}/$1 [R=301,L]
""", encoding="utf-8")


if __name__ == "__main__":
    build()
