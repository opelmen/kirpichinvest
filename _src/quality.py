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


def yandex_card(d, fallback_addrs=(), big_cities=()):
    """True, если карточку стоит отдавать Яндексу (остальные получают meta name="yandex" noindex, в Google остаются).

    Яндекс пересчитывает «малоценные» страницы по каждой и судит о сайте по их доле. Пока домен молодой и
    в Вебмастере не загружен, ему отдаём только карточки, где есть что показать: адрес, площадь, цена
    от 300 тыс. ₽, дата окончания приёма заявок и фото или пересказ извещения от 200 знаков. Послабление
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
    return (
        bool(d.get("photo"))
        or len((d.get("excerpt") or "").strip()) >= YANDEX_MIN_EXCERPT
    )
