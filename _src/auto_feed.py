"""Техника с торгов из приложения ТоргГид (выгрузка /api/v1/public/vehicles) для раздела torggid.ru/auto/.

Строки выгрузки приводим к карточке сайта: без VIN и госномера (их нет и в выгрузке), описание — пересказ
извещения без персональных данных. Страницы: все машины, по типу техники, по региону, по марке и подборки."""
import re

from market_feed import KIND, REGIONS, SOURCE, region_code, site_id

# vtype приложения → (slug раздела, название во множественном числе, в единственном для заголовка карточки)
VTYPES = {
    "car": ("legkovye", "Легковые автомобили", "Легковой автомобиль"),
    "truck": ("gruzovye", "Грузовые автомобили", "Грузовой автомобиль"),
    "special": ("spectehnika", "Спецтехника", "Спецтехника"),
    "bus": ("avtobusy", "Автобусы", "Автобус"),
    "trailer": ("pricepy", "Прицепы и полуприцепы", "Прицеп"),
    "moto": ("mototehnika", "Мототехника", "Мототехника"),
    "agri": ("selhoztehnika", "Сельхозтехника", "Сельхозтехника"),
    "water": ("vodnyy-transport", "Катера, лодки и суда", "Водный транспорт"),
    "air": ("aviatehnika", "Авиатехника", "Авиатехника"),
    "other": ("drugaya-tehnika", "Другая техника", "Техника"),
}
VTYPE_BY_SLUG = {v[0]: k for k, v in VTYPES.items()}

# Поля карточки, которые храним между сборками (история: lastmod и статус, когда лот ушёл из выгрузки).
# Описаний извещений и VIN здесь нет: наружу уходит только то, что уже показано на странице.
FIELDS = ("id", "app_id", "source", "source_name", "source_url", "kind", "kind_name", "bidd_type", "repeat",
          "vtype", "vtype_slug", "vtype_name", "make", "model", "make_slug", "year", "mileage", "hours", "purpose",
          "pledge", "has_vin", "region", "region_slug", "region_name", "region_where", "price", "price_start",
          "price_was", "price_drops", "bidd_end", "first_seen", "photo", "photos", "photos_count", "excerpt", "label")


def slug(s):
    """Марка в адрес страницы: латиница как есть, кириллица транслитом (ГАЗ → gaz, Лада → lada)."""
    t = dict(zip("абвгдеёжзийклмнопрстуфхцчшщъыьэюя",
                 ["a", "b", "v", "g", "d", "e", "e", "zh", "z", "i", "y", "k", "l", "m", "n", "o", "p", "r", "s", "t", "u",
                  "f", "h", "c", "ch", "sh", "sch", "", "y", "", "e", "yu", "ya"]))
    out = "".join(t.get(c, c if c.isalnum() else "-") for c in str(s or "").lower())
    return re.sub(r"-+", "-", out).strip("-")


def label(r):
    """Короткое название: «Renault Logan Stepway, 2020» или «Экскаватор-погрузчик JCB, 2014»; без марки — тип."""
    make, model, year = (r.get("make") or "").strip(), (r.get("model") or "").strip(), r.get("year")
    name = " ".join(x for x in (make, model) if x) or VTYPES.get(r.get("vtype") or "other", VTYPES["other"])[2]
    if make and r.get("vtype") in ("special", "agri", "truck", "bus", "trailer", "water"):
        name = f"{VTYPES[r['vtype']][2]} {name}"
    return f"{name}, {year}" if year else name


def from_vehicles(rows):
    out = []
    for r in rows:
        vt = r.get("vtype") if r.get("vtype") in VTYPES else "other"
        code = region_code(r.get("region"))
        reg = REGIONS.get(code or "")
        photos = [p for p in r.get("photos") or [] if isinstance(p, str) and p.startswith("http")]
        photo = r.get("photo") if str(r.get("photo") or "").startswith("http") else (photos[0] if photos else None)
        d = {
            "id": site_id(r["id"]), "app_id": r["id"], "source": r.get("source"),
            "source_name": SOURCE.get(r.get("source"), r.get("source")), "source_url": r.get("source_url"),
            "kind": r.get("kind"), "kind_name": KIND.get(r.get("kind")), "bidd_type": r.get("procedure"),
            "repeat": r.get("stage") == "repeat",
            "vtype": vt, "vtype_slug": VTYPES[vt][0], "vtype_name": VTYPES[vt][1],
            "make": r.get("make"), "model": r.get("model"), "make_slug": slug(r.get("make")) or None,
            "year": r.get("year"), "mileage": r.get("mileage_km"), "hours": r.get("hours"), "purpose": r.get("purpose"),
            "pledge": bool(r.get("pledge_mentioned")), "has_vin": bool(r.get("has_vin")),
            "region": code, "region_slug": reg[0] if reg else None, "region_name": reg[1] if reg else None,
            "region_where": reg[2] if reg else None,
            "price": r.get("price"), "price_start": r.get("price_start"),
            "price_was": r.get("price_was"), "price_drops": r.get("price_drops") or 0,
            "bidd_end": r.get("bidd_end"), "first_seen": r.get("first_seen"),
            "photo": photo, "photos": photos[:4] or ([photo] if photo else []), "photos_count": r.get("photos_count") or len(photos),
            "excerpt": re.sub(r"\s+", " ", str(r.get("descr") or "")).strip()[:600],
            "status": "active",
        }
        d["label"] = label(d)
        out.append(d)
    return out
