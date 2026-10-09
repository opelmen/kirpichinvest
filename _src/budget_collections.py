"""Small, data-backed collections; missing flags never prove a whole apartment."""
import math

SALE_TYPES = {
    'Реализация имущества должников',
    'Продажа (приватизация) государственного и муниципального имущества',
}


def budget_lots(lots, cap):
    selected = []
    for row in lots:
        price = row.get('price')
        if (row.get('status') == 'active' and (row.get('bidd_type') in SALE_TYPES or row.get('kind') in ('arrest', 'bankruptcy'))
                and isinstance(price, (int, float)) and not isinstance(price, bool)
                and math.isfinite(price) and 0 < price <= cap):
            selected.append(row)
    return sorted(selected, key=lambda d: (d['price'], d['id']))


def object_group(row):
    flags = (row.get('flags') or '').lower()
    if 'доля' in flags:
        return 'Доля по данным источника'
    if 'комната' in flags:
        return 'Комната / коммунальная квартира по данным источника'
    return 'Состав права нужно проверить по документам'


def budget_summary(lots, cap):
    rows = budget_lots(lots, cap)
    shares = sum('доля' in (d.get('flags') or '').lower() for d in rows)
    rooms = sum('доля' not in (d.get('flags') or '').lower() and 'комната' in (d.get('flags') or '').lower() for d in rows)
    return dict(cap=cap, count=len(rows), shares=shares, rooms=rooms,
                other=len(rows)-shares-rooms, cities=len({d.get('city') for d in rows if d.get('city')}))
