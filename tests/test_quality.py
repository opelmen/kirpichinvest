import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / '_src'))
from quality import thin_card


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


if __name__ == '__main__':
    unittest.main()
