"""Лоты из приложения ТоргГид (выгрузка /api/v1/public/feed): вся страна, все площадки.

Приводим строки к полям, с которыми работает сборка сайта (как в прежней выгрузке Залог-Деска), и добавляем
своё: тип объекта, регион, риски, срок до владения и короткий вердикт «Рентгена» для страницы лота."""
import re

# Коды субъектов РФ (как в ГИС Торги) → (slug, название, «где»).
REGIONS = {
    "1": ("adygeya", "Адыгея", "в Адыгее"), "2": ("bashkortostan", "Башкортостан", "в Башкортостане"),
    "3": ("buryatiya", "Бурятия", "в Бурятии"), "4": ("respublika-altay", "Республика Алтай", "в Республике Алтай"),
    "5": ("dagestan", "Дагестан", "в Дагестане"), "6": ("ingushetiya", "Ингушетия", "в Ингушетии"),
    "7": ("kabardino-balkariya", "Кабардино-Балкария", "в Кабардино-Балкарии"), "8": ("kalmykiya", "Калмыкия", "в Калмыкии"),
    "9": ("karachaevo-cherkesiya", "Карачаево-Черкесия", "в Карачаево-Черкесии"), "10": ("kareliya", "Карелия", "в Карелии"),
    "11": ("komi", "Коми", "в Республике Коми"), "12": ("mariy-el", "Марий Эл", "в Марий Эл"),
    "13": ("mordoviya", "Мордовия", "в Мордовии"), "14": ("yakutiya", "Якутия", "в Якутии"),
    "15": ("severnaya-osetiya", "Северная Осетия", "в Северной Осетии"), "16": ("tatarstan", "Татарстан", "в Татарстане"),
    "17": ("tyva", "Тыва", "в Тыве"), "18": ("udmurtiya", "Удмуртия", "в Удмуртии"), "19": ("hakasiya", "Хакасия", "в Хакасии"),
    "20": ("chechnya", "Чечня", "в Чечне"), "21": ("chuvashiya", "Чувашия", "в Чувашии"),
    "22": ("altayskiy-kray", "Алтайский край", "в Алтайском крае"), "23": ("krasnodarskiy-kray", "Краснодарский край", "в Краснодарском крае"),
    "24": ("krasnoyarskiy-kray", "Красноярский край", "в Красноярском крае"), "25": ("primorskiy-kray", "Приморский край", "в Приморском крае"),
    "26": ("stavropolskiy-kray", "Ставропольский край", "в Ставропольском крае"), "27": ("habarovskiy-kray", "Хабаровский край", "в Хабаровском крае"),
    "28": ("amurskaya-oblast", "Амурская область", "в Амурской области"), "29": ("arhangelskaya-oblast", "Архангельская область", "в Архангельской области"),
    "30": ("astrahanskaya-oblast", "Астраханская область", "в Астраханской области"), "31": ("belgorodskaya-oblast", "Белгородская область", "в Белгородской области"),
    "32": ("bryanskaya-oblast", "Брянская область", "в Брянской области"), "33": ("vladimirskaya-oblast", "Владимирская область", "во Владимирской области"),
    "34": ("volgogradskaya-oblast", "Волгоградская область", "в Волгоградской области"), "35": ("vologodskaya-oblast", "Вологодская область", "в Вологодской области"),
    "36": ("voronezhskaya-oblast", "Воронежская область", "в Воронежской области"), "37": ("ivanovskaya-oblast", "Ивановская область", "в Ивановской области"),
    "38": ("irkutskaya-oblast", "Иркутская область", "в Иркутской области"), "39": ("kaliningradskaya-oblast", "Калининградская область", "в Калининградской области"),
    "40": ("kaluzhskaya-oblast", "Калужская область", "в Калужской области"), "41": ("kamchatskiy-kray", "Камчатский край", "на Камчатке"),
    "42": ("kemerovskaya-oblast", "Кемеровская область", "в Кемеровской области"), "43": ("kirovskaya-oblast", "Кировская область", "в Кировской области"),
    "44": ("kostromskaya-oblast", "Костромская область", "в Костромской области"), "45": ("kurganskaya-oblast", "Курганская область", "в Курганской области"),
    "46": ("kurskaya-oblast", "Курская область", "в Курской области"), "47": ("leningradskaya-oblast", "Ленинградская область", "в Ленинградской области"),
    "48": ("lipetskaya-oblast", "Липецкая область", "в Липецкой области"), "49": ("magadanskaya-oblast", "Магаданская область", "в Магаданской области"),
    "50": ("moskovskaya-oblast", "Московская область", "в Московской области"), "51": ("murmanskaya-oblast", "Мурманская область", "в Мурманской области"),
    "52": ("nizhegorodskaya-oblast", "Нижегородская область", "в Нижегородской области"), "53": ("novgorodskaya-oblast", "Новгородская область", "в Новгородской области"),
    "54": ("novosibirskaya-oblast", "Новосибирская область", "в Новосибирской области"), "55": ("omskaya-oblast", "Омская область", "в Омской области"),
    "56": ("orenburgskaya-oblast", "Оренбургская область", "в Оренбургской области"), "57": ("orlovskaya-oblast", "Орловская область", "в Орловской области"),
    "58": ("penzenskaya-oblast", "Пензенская область", "в Пензенской области"), "59": ("permskiy-kray", "Пермский край", "в Пермском крае"),
    "60": ("pskovskaya-oblast", "Псковская область", "в Псковской области"), "61": ("rostovskaya-oblast", "Ростовская область", "в Ростовской области"),
    "62": ("ryazanskaya-oblast", "Рязанская область", "в Рязанской области"), "63": ("samarskaya-oblast", "Самарская область", "в Самарской области"),
    "64": ("saratovskaya-oblast", "Саратовская область", "в Саратовской области"), "65": ("sahalinskaya-oblast", "Сахалинская область", "на Сахалине"),
    "66": ("sverdlovskaya-oblast", "Свердловская область", "в Свердловской области"), "67": ("smolenskaya-oblast", "Смоленская область", "в Смоленской области"),
    "68": ("tambovskaya-oblast", "Тамбовская область", "в Тамбовской области"), "69": ("tverskaya-oblast", "Тверская область", "в Тверской области"),
    "70": ("tomskaya-oblast", "Томская область", "в Томской области"), "71": ("tulskaya-oblast", "Тульская область", "в Тульской области"),
    "72": ("tyumenskaya-oblast", "Тюменская область", "в Тюменской области"), "73": ("ulyanovskaya-oblast", "Ульяновская область", "в Ульяновской области"),
    "74": ("chelyabinskaya-oblast", "Челябинская область", "в Челябинской области"), "75": ("zabaykalskiy-kray", "Забайкальский край", "в Забайкальском крае"),
    "76": ("yaroslavskaya-oblast", "Ярославская область", "в Ярославской области"), "77": ("gorod-moskva", "Москва", "в Москве"),
    "78": ("gorod-sankt-peterburg", "Санкт-Петербург", "в Санкт-Петербурге"), "79": ("evreyskaya-ao", "Еврейская АО", "в Еврейской АО"),
    "83": ("nenetskiy-ao", "Ненецкий АО", "в Ненецком АО"), "86": ("hmao-yugra", "ХМАО — Югра", "в ХМАО — Югре"),
    "87": ("chukotka", "Чукотка", "на Чукотке"), "89": ("yanao", "ЯНАО", "в ЯНАО"), "90": ("zaporozhskaya-oblast", "Запорожская область", "в Запорожской области"),
    "91": ("krym", "Крым", "в Крыму"), "92": ("sevastopol", "Севастополь", "в Севастополе"), "93": ("dnr", "ДНР", "в ДНР"),
    "94": ("lnr", "ЛНР", "в ЛНР"), "95": ("hersonskaya-oblast", "Херсонская область", "в Херсонской области"),
}

CATEGORY = {  # категория приложения → (название в карточке, во множественном числе для заголовков)
    "flat": ("Квартира", "Квартиры"), "room": ("Комната", "Комнаты"), "share": ("Доля", "Доли"),
    "house": ("Дом", "Дома"), "land": ("Земельный участок", "Земельные участки"),
    "commercial": ("Нежилое помещение", "Коммерческая недвижимость"), "garage": ("Гараж или машино-место", "Гаражи и машино-места"),
    "other": ("Недвижимость", "Прочая недвижимость"),
}
KIND = {"bankruptcy": "Банкротство", "arrest": "Арестованное имущество", "pledge": "Залоговое имущество"}
SOURCE = {"gistorgi": "ГИС Торги", "mets": "МЭТС", "nis": "НИС", "centerr": "ЦентрЕР", "utpl": "УТПЛ", "gpb": "ЭТП ГПБ",
          "fabrikant": "Фабрикант", "rad": "РАД", "cdt": "ЦДТ"}


def region_code(v):
    v = str(v or "").strip()
    return str(int(v)) if v.isdigit() else None


def site_id(market_id: str) -> str:
    """ГИС Торги — прежний id без префикса (адреса страниц не меняются), остальные площадки — «источник-id»."""
    src, _, sid = str(market_id).partition(":")
    if src == "gistorgi":
        return re.sub(r"[^A-Za-z0-9_-]", "_", sid)
    return re.sub(r"[^A-Za-z0-9_-]", "_", f"{src}-{sid}")[:80]


def mln(v):
    return f"{v / 1e6:.1f}".replace(".", ",") + " млн"


NONRES = {"commercial": "Нежилое", "land": "Земля", "garage": "Гараж", "other": "Объект"}


def verdict(d):
    """Короткий «Рентген» для статической страницы: ярлык и вывод одной фразой. Логика как в приложении."""
    found = d.get("risks") or []
    high = [r["title"].lower() for r in found if r.get("level") == "high"]
    other = [r["title"].lower() for r in found if r.get("level") != "high"]
    own = d.get("own_time") or "1–2 мес."
    disc, market, price = d.get("eff_discount"), d.get("eff_market"), d.get("price")
    if d.get("category") == "share":
        return ("mid", "Доля — только для опытных",
                "Продаётся доля, а не целый объект: с рыночной ценой не сравнить, пользоваться и продать можно только договорившись с сособственниками.")
    if (not market or disc is None or not price) and d.get("category") in NONRES:
        tail = f"Из извещения видно: {', '.join(high + other)}." if found else "Явных рисков в извещении не видно."
        return ("none", f"{NONRES[d['category']]}: оценка вручную",
                "Для помещений, земли и гаражей автоматической оценки нет: аналогов мало и они слишком разные. "
                f"Сравните цену за м² с объявлениями рядом или закажите проверку эксперта. {tail}")
    if not market or disc is None or not price:
        tail = f"Из извещения видно: {', '.join(high + other)}." if found else "Явных рисков в извещении не видно."
        return ("none", "Нужна оценка рынка", f"Рыночной цены пока нет, поэтому выгоду не посчитать. {tail}")
    if high:
        risk = f"но есть серьёзный риск ({', '.join(high)}): до полного владения {own}"
    elif other:
        risk = f"риски устранимые ({', '.join(other)}), до владения {own}"
    else:
        risk = "серьёзных рисков в извещении не нашли"
    if disc >= 10 and d.get("suspect"):
        return ("mid", "Похоже на выгоду — проверьте оценку",
                f"По оценке дешевле рынка на {round(disc)}%, но такая скидка встречается редко: сверьте цену с объявлениями вручную; {risk}.")
    if disc >= 10:
        badge = "Выгодно, но с рисками" if high else ("Выгодно, риски устранимы" if other else "Выгодно — стоит участвовать")
        return ("mid" if high else "good", badge, f"Дешевле рынка на {round(disc)}% (≈{mln(market - price)} ₽), {risk}.")
    if disc > -5:
        return ("mid", "Цена около рынка", "Цена почти рыночная: заработать на перепродаже вряд ли получится. Интересно, только если торги пройдут ниже старта или берёте для себя.")
    return ("bad", "Дороже рынка — мимо", f"Стартовая цена выше рынка на {round(-disc)}%. Ждите повторных торгов со снижением цены.")


def from_market(rows):
    out = []
    for r in rows:
        cat = r.get("category") or "other"
        keys = {x.get("key") for x in r.get("risks") or []}
        flags = [x["title"].lower() for x in r.get("risks") or [] if x.get("key") not in ("share", "room", "repeat")]
        if cat == "share":
            flags.insert(0, "доля")
        if cat == "room":
            flags.insert(0, "комната")
        if r.get("stage") == "repeat" or "repeat" in keys:
            flags.append("повторные торги")
        if "residents" in keys:
            flags.append("зарегистрированы жильцы")
        # оценка по аналогам-квартирам: у нежилого её не показываем, даже если пришла из старой выгрузки
        rough = r.get("market_conf") == "low" or cat in NONRES
        d = {
            "id": site_id(r["id"]), "app_id": r["id"], "source": r.get("source"),
            "source_name": SOURCE.get(r.get("source"), r.get("source")),
            "source_url": r.get("source_url"), "kind": r.get("kind"), "kind_name": KIND.get(r.get("kind")),
            "category": cat, "name": r.get("title"), "address": r.get("address"),
            "city": r.get("city"), "region": region_code(r.get("region")),
            "price": r.get("price"), "price_start": r.get("price_start"), "area": r.get("area"), "ppm2": r.get("ppm2"),
            "rooms": r.get("rooms"), "floor": r.get("floor"), "cadastral": r.get("cadastral"),
            "bidd_type": r.get("procedure"), "bidd_end": r.get("bidd_end"), "first_seen": r.get("first_seen"),
            "eff_market": None if rough else r.get("market_price"),
            "eff_discount": None if rough or cat == "share" else r.get("discount_pct"),
            "liq": None if rough else r.get("liq_price"),
            "flags": ", ".join(dict.fromkeys(flags)), "risks": r.get("risks") or [], "own_time": r.get("own_time"),
            "photo": r.get("photo"), "status": "active", "suspect": bool(r.get("suspect")),
        }
        tone, badge, text = verdict(d)
        d["verdict"] = [tone, badge, text.replace("..", ".")]
        out.append(d)
    return out
