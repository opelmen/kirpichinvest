"""Какие карточки лотов не отдавать в индекс поисковиков.

Яндекс на молодом домене исключает однотипные страницы пачками («малоценная или маловостребованная»)
и по ним судит о сайте целиком. Карточка без адреса, без площади и без пересказа извещения
(«Недвижимость с торгов за 214 ₽: Адрес уточняется») ничего не даёт человеку из поиска: она остаётся
на сайте и в подборках, но получает noindex и уходит из sitemap."""

MIN_PRICE = 1_000  # цена меньше тысячи рублей у недвижимости — ошибка разбора извещения, а не лот


def thin_card(d, fallback_addrs=()):
    """True, если в карточке нечего показать поиску."""
    price = d.get("price") or 0
    if 0 < price < MIN_PRICE:
        return True
    addr = (d.get("caddr") or "").strip()
    no_addr = not addr or addr == "Адрес уточняется" or addr in fallback_addrs
    return no_addr and not d.get("excerpt") and not d.get("area")


YANDEX_MIN_PRICE = 300_000
YANDEX_MIN_EXCERPT = 200  # знаков пересказа извещения: короче — карточка для Яндекса неотличима от соседней
# 07.11.2026: после #55 Яндексу открывалось 8 976 карточек, из них квартир лишь 1 475; остальное — дома, земля,
# коммерция. Квартиры открываем как раньше, остальное — только с фото, пересказом и ценой от 1 млн ₽
YANDEX_MIN_PRICE_OTHER = 1_000_000


def yandex_card(d, fallback_addrs=(), big_cities=()):
    """True, если карточку стоит отдавать Яндексу (остальные получают meta name="yandex" noindex, в Google остаются).

    Яндекс пересчитывает «малоценные» страницы по каждой и судит о сайте по их доле. Пока домен молодой и
    в Вебмастере не загружен, ему отдаём только карточки, где есть что показать: адрес, площадь, цена
    от 300 тыс. ₽, дата окончания приёма заявок и фото или пересказ извещения от 200 знаков (квартиры);
    дома, земля и коммерция — только с фото, пересказом и ценой от 1 млн ₽. Послабление
    для 16 миллионников (06.11.2026: 12 394 открытых карточки при плане 2–4 тысячи) снято; `big_cities`
    оставлен в сигнатуре, чтобы вернуть его, когда страниц в поиске Яндекса станет больше."""
    if thin_card(d, fallback_addrs):
        return False
    addr = (d.get("caddr") or "").strip()
    if not addr or addr == "Адрес уточняется" or addr in fallback_addrs:
        return False
    if not d.get("area") or (d.get("price") or 0) < YANDEX_MIN_PRICE:
        return False
    if not d.get("bidd_end"):
        return False
    photo = bool(d.get("photo"))
    long_excerpt = len((d.get("excerpt") or "").strip()) >= YANDEX_MIN_EXCERPT
    if (d.get("category") or "flat") == "flat":
        return photo or long_excerpt
    return photo and long_excerpt and (d.get("price") or 0) >= YANDEX_MIN_PRICE_OTHER
