import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / '_src'))
from quality import thin_card, yandex_card


class ThinCardTests(unittest.TestCase):
    def test_no_address_no_area_no_excerpt_is_thin(self):
        self.assertTrue(thin_card(dict(price=500_000, caddr='Адрес уточняется')))
        self.assertTrue(thin_card(dict(price=500_000, caddr='Москва'), {'Москва'}))

    def test_placeholder_price_is_thin(self):
        self.assertTrue(thin_card(dict(price=214, caddr='г. Пермь, ул. Ленина, д. 5', area=40)))

    def test_any_real_content_keeps_card_indexed(self):
        self.assertFalse(thin_card(dict(price=500_000, caddr='г. Пермь, ул. Ленина, д. 5')))
        self.assertFalse(thin_card(dict(price=500_000, caddr='Адрес уточняется', area=42)))
        self.assertFalse(thin_card(dict(price=500_000, caddr='Адрес уточняется', excerpt='Квартира на 5 этаже')))
        self.assertFalse(thin_card(dict(price=None, caddr='Москва', area=30), {'Москва'}))


class YandexCardTests(unittest.TestCase):
    FULL = dict(price=2_500_000, caddr='г. Тверь, ул. Советская, д. 3', area=41, bidd_end='2099-01-01',
                excerpt='Квартира на 2 этаже пятиэтажного кирпичного дома, две комнаты, общая площадь 41 кв. м, '
                        'балкон застеклён, окна во двор. Продаётся в рамках процедуры реализации имущества, '
                        'обременений по выписке нет, зарегистрированных жильцов нет.')

    def test_full_card_outside_big_cities_is_open(self):
        self.assertTrue(yandex_card(self.FULL))

    def test_missing_date_or_description_closes_card_outside_big_cities(self):
        self.assertFalse(yandex_card(dict(self.FULL, bidd_end=None)))
        self.assertFalse(yandex_card(dict(self.FULL, excerpt=None)))
        self.assertTrue(yandex_card(dict(self.FULL, excerpt=None, photo='p.jpg')))

    def test_big_city_gets_no_shortcut(self):
        card = dict(price=2_500_000, caddr='Москва, ул. Тверская, д. 1', area=40, city='moskva')
        self.assertFalse(yandex_card(card, big_cities={'moskva'}))
        self.assertTrue(yandex_card(dict(card, bidd_end='2099-01-01', photo='p.jpg'), big_cities={'moskva'}))

    def test_house_or_land_needs_photo_excerpt_and_million(self):
        house = dict(self.FULL, category='house', photo='p.jpg')
        self.assertTrue(yandex_card(house))
        self.assertFalse(yandex_card(dict(house, photo=None)))              # без фото
        self.assertFalse(yandex_card(dict(house, excerpt='Дом, участок')))  # без пересказа
        self.assertFalse(yandex_card(dict(house, price=800_000)))           # дешевле 1 млн
        self.assertTrue(yandex_card(dict(self.FULL, category='land', photo='p.jpg', price=1_000_000)))

    def test_short_excerpt_is_not_enough(self):
        self.assertFalse(yandex_card(dict(self.FULL, excerpt='Квартира, 2 этаж')))

    def test_cheap_or_no_area_or_no_address_is_closed(self):
        self.assertFalse(yandex_card(dict(self.FULL, price=50_000)))
        self.assertFalse(yandex_card(dict(self.FULL, price=250_000)))
        self.assertFalse(yandex_card(dict(self.FULL, area=None)))
        self.assertFalse(yandex_card(dict(self.FULL, caddr='Адрес уточняется')))
        self.assertFalse(yandex_card(dict(self.FULL, caddr='Москва'), {'Москва'}))


if __name__ == '__main__':
    unittest.main()
