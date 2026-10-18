"""Лоты из приложения ТоргГид (выгрузка /api/v1/public/feed): вся страна, все площадки.

Приводим строки к полям, с которыми работает сборка сайта (как в прежней выгрузке Залог-Деска), и добавляем
своё: тип объекта, регион, риски и короткий вердикт «Рентгена» для страницы лота."""
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
KIND = {"bankruptcy": "Банкротство", "arrest": "Арестованное имущество", "pledge": "Залоговое имущество", "state": "Государственное и муниципальное имущество"}
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


def rub(v):
    return f"{round(v):,}".replace(",", "\u00a0") + "\u00a0₽"


# «Рисков не видно» звучит как чистая проверка, а мы видим только извещение: обременения и оспаривание не проверены.
NO_RISKS = ("В извещении рисков не указано, но обременения и оспаривание сделок это не исключает: "
            "их покажут свежая выписка ЕГРН и картотека арбитражных дел.")

NONRES = {"commercial": "Нежилое", "land": "Земля", "garage": "Гараж", "other": "Объект"}


def verdict(d):
    """Короткий «Рентген» для статической страницы: ярлык и вывод одной фразой. Логика как в приложении."""
    found = d.get("risks") or []
    high = [r["title"].lower() for r in found if r.get("level") == "high"]
    other = [r["title"].lower() for r in found if r.get("level") != "high"]
    disc, market, price = d.get("eff_discount"), d.get("eff_market"), d.get("price")
    if d.get("category") == "share":
        return ("mid", "Доля — только для опытных",
                "Продаётся доля, а не целый объект: с рыночной ценой не сравнить, пользоваться объектом и распоряжаться долей можно только договорившись с сособственниками.")
    if (not market or disc is None or not price) and d.get("category") in NONRES:
        tail = f"Из извещения видно: {', '.join(high + other)}." if found else NO_RISKS
        name, cp, lp = NONRES[d["category"]], d.get("comps"), d.get("ppm2")
        if not lp:
            return ("none", f"{name}: оценка вручную",
                    "Площадь в извещении не указана или указана неточно, поэтому цену за м² не сравнить с объявлениями: "
                    f"такой объект оценивают по документам и осмотру. {tail}")
        if cp and cp.get("n", 0) >= 5 and cp.get("ppm") and lp:
            r = lp / cp["ppm"]
            rel = ("заметно ниже" if r < 0.7 else "ниже" if r < 0.9 else "около" if r <= 1.1
                   else "выше" if r <= 1.4 else "заметно выше")
            return ("none", f"{name}: сравнили с объявлениями",
                    f"Цена м² лота {rub(lp)} — {rel} середины {cp['n']} похожих объявлений рядом "
                    f"({rub(cp['ppm'])} за м², {cp.get('radius') or 'рядом'}). Это ориентир, а не оценка: объекты разные, "
                    f"сверьте назначение, состояние и коммуникации. {tail}")
        if cp and cp.get("n") and cp.get("ppm") and lp:
            return ("none", f"{name}: аналогов мало",
                    f"Рядом нашлось только {cp['n']} похожих объявлений ({cp.get('radius') or 'рядом'}), сравнение грубое: "
                    f"у них около {rub(cp['ppm'])} за м², у лота {rub(lp)}. {tail}")
        if cp:
            return ("none", f"{name}: аналогов рядом нет",
                    f"Похожих объявлений рядом нет, сравнить не с чем: такой объект оценивают по документам и осмотру. {tail}")
        return ("none", f"{name}: ищем объявления",
                f"Похожие объявления рядом ещё подбираем, подборка появится в приложении. {tail}")
    if not market or disc is None or not price:
        tail = f"Из извещения видно: {', '.join(high + other)}." if found else NO_RISKS
        return ("none", "Нужна оценка рынка", f"Рыночной цены пока нет, поэтому разницу с рынком не посчитать. {tail}")
    # «Выгодно» не пишем: цена — факт, а чистоту объекта (жильцы, аресты, оспаривание) по извещению не проверить.
    # чего в извещении нет, страница лота показывает отдельной строкой «Не раскрыто», в вывод не дублируем
    # срок «до владения» не пишем: собственность покупатель получает после оплаты и регистрации,
    # а жильцов и обременения решают отдельно, на переход права они не влияют
    said = f"В извещении указано: {', '.join(high + other)}; это решают отдельно, право собственности перейдёт после оплаты и регистрации." if found else ""
    if disc >= 10 and d.get("suspect"):
        return ("mid", "Цена сильно ниже оценки — сверьте с объявлениями",
                f"Цена заметно ниже нашей оценки, но такая разница встречается редко, и оценка может ошибаться: сверьте цену с объявлениями рядом. {said}".strip())
    if disc >= 10:
        badge = ("Цена ниже рынка, но серьёзный риск" if high else
                 "Цена ниже рынка, риски устранимые" if other else "Цена ниже рынка, чистота не проверена")
        return ("bad" if high else "mid" if other else "none", badge,
                f"Цена на {round(disc)}% ниже нашей оценки рынка (≈{mln(market - price)} ₽). {said}".strip())
    if disc > -5:
        return ("mid", "Цена около рынка", "Цена почти рыночная: разницы с рынком почти нет. Имеет смысл, если торги пройдут ниже старта или нужен именно этот объект.")
    return ("bad", "Цена выше рынка", f"Стартовая цена выше рынка на {round(-disc)}%. Если торги не состоятся, на повторных цена будет ниже.")


def next_step(schedule, now=None):
    """Публичное предложение: следующий шаг снижения цены (дата, цена) по графику из извещения."""
    from datetime import datetime, timezone
    now = now or datetime.now(timezone.utc)
    for st in schedule or []:
        try:
            t = datetime.fromisoformat(str(st.get("start")).replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            continue
        if (t if t.tzinfo else t.replace(tzinfo=timezone.utc)) > now and st.get("price"):
            return [t.strftime("%d.%m.%Y"), st["price"]]
    return None


def land_text(x):
    """Продают ли участок под зданием (поле land выгрузки) — одна строка для страницы лота."""
    if not x:
        return None
    p = ", ".join(v for v in (f"КН {x['cad']}" if x.get("cad") else None,
                              f"{x['area']:,.0f} м²".replace(",", " ") if x.get("area") else None) if v)
    p = f" ({p})" if p else ""
    return {
        "with": f"продают вместе со зданием{p}",
        "with_extra": f"переходит вместе со зданием, цену платят отдельно{p}",
        "lease": f"не продают, участок в аренде{p}: аренда переходит к покупателю здания",
        "not_sold": f"в лот не входит{p}: выкуп или аренду земли оформлять отдельно",
        "public": f"государственный, собственность не разграничена{p}: выкуп или аренда без торгов",
        "mkd": "помещение в многоквартирном доме: участок общий, доля переходит вместе с помещением",
        "premise": "продаётся помещение: участок отдельно не продают, земля общая у собственников помещений",
        "on_plot": f"здание стоит на участке{p}, продают ли его, в извещении не сказано: смотрите проект договора",
    }.get(x.get("status"), "о земле под зданием в извещении ни слова: смотрите проект договора")


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
        if "residents" in keys:
            flags.append("зарегистрированы жильцы")
        # оценка по аналогам-квартирам: у нежилого её не показываем, даже если пришла из старой выгрузки
        rough = r.get("market_conf") == "low" or cat in NONRES
        area, ppm2 = r.get("area"), r.get("ppm2")
        if cat == "land" and area and area < 100:
            area = ppm2 = None  # у земли «35,7 м²» — почти всегда сотки или гектары из извещения: лучше не показать, чем соврать
        d = {
            "id": site_id(r["id"]), "app_id": r["id"], "source": r.get("source"),
            "source_name": SOURCE.get(r.get("source"), r.get("source")),
            "source_url": r.get("source_url"), "kind": r.get("kind"), "kind_name": KIND.get(r.get("kind")),
            "category": cat, "name": r.get("title"), "address": r.get("address"),
            "city": r.get("city"), "region": region_code(r.get("region")),
            "price": r.get("price"), "price_start": r.get("price_start"), "area": area, "ppm2": ppm2,
            "rooms": r.get("rooms"), "floor": r.get("floor"), "cadastral": r.get("cadastral"),
            "bidd_type": r.get("procedure"), "bidd_end": r.get("bidd_end"), "first_seen": r.get("first_seen"),
            "eff_market": None if rough else r.get("market_price"),
            "eff_discount": None if rough or cat == "share" else r.get("discount_pct"),
            "liq": None if rough else r.get("liq_price"),
            "flags": ", ".join(dict.fromkeys(flags)), "own_time": r.get("own_time"),
            # повторные торги — плюс (цена уже снижена), не риск: показываем отдельной зелёной меткой
            "risks": [x for x in r.get("risks") or [] if x.get("key") != "repeat"],
            "repeat": r.get("stage") == "repeat" or "repeat" in keys,
            "market_basis": r.get("market_basis"), "next_step": next_step(r.get("price_schedule")),
            "price_drops": r.get("price_drops") or 0, "price_was": r.get("price_was"),
            "photo": r.get("photo"), "status": "active", "suspect": bool(r.get("suspect")),
            "comps": r.get("comps") if cat in NONRES and ppm2 else None,
            "land_text": land_text(r.get("land")),
        }
        if (r.get("land") or {}).get("status") == "not_sold":
            d["flags"] = ", ".join(x for x in (d["flags"], "участок в лот не входит") if x)
        if r.get("market_conf") == "low" and cat not in NONRES and cat != "share" and r.get("market_price"):
            d["city_market"] = r["market_price"]  # грубый ориентир по городу: показываем суммой, без процента
        tone, badge, text = verdict(d)
        d["verdict"] = [tone, badge, text.replace("..", ".")]
        if d["suspect"]:
            d["eff_discount"] = None  # скидка больше 50%: процент не выносим, вывод Рентгена объясняет почему
        out.append(d)
    return out
