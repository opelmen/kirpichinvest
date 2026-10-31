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


YANDEX_MIN_PRICE = 100_000


def yandex_card(d, fallback_addrs=(), big_cities=()):
    """True, если карточку стоит отдавать Яндексу (остальные получают meta name="yandex" noindex, в Google остаются).

    Яндекс пересчитывает «малоценные» страницы по каждой и судит о сайте по их доле, поэтому ему отдаём
    только карточки, где есть что показать: адрес, площадь, цена от 100 тыс. ₽ и пересказ извещения или фото
    с датой торгов. В 16 городах-миллионниках, где есть спрос по запросам, хватает адреса, площади и цены."""
    if thin_card(d, fallback_addrs):
        return False
    addr = (d.get("caddr") or "").strip()
    if not addr or addr == "Адрес уточняется" or addr in fallback_addrs:
        return False
    if not d.get("area") or (d.get("price") or 0) < YANDEX_MIN_PRICE:
        return False
    if d.get("city") in big_cities:
        return True
    return bool(d.get("bidd_end")) and bool(d.get("photo") or d.get("excerpt"))
