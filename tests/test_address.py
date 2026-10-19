import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / '_src'))
from build import clean_address


class AddressTests(unittest.TestCase):
    def test_notice_tail_and_room_number_leave_header(self):
        # John 19.10.2026: в шапке лота только объект, площадь и адрес — без «обременено залогом в пользу…»
        raw = 'г. Москва, ул. Кутузова, д.11, корпус 2, помещение 35Ц, обременено залогом в пользу АО «ТБанк»'
        self.assertEqual(clean_address({'address': raw}), 'г. Москва, ул. Кутузова, д. 11, корпус 2')
        self.assertEqual(clean_address({'address': 'г. Санкт-Петербург, ул. 6-я Советская, д. 5, литера А, пом. 3-Н'}),
                         'г. Санкт-Петербург, ул. 6-я Советская, д. 5, литера А')
        self.assertEqual(clean_address({'address': 'г. Москва, ул. 1905 года, д. 7'}), 'г. Москва, ул. 1905 года, д. 7')


if __name__ == '__main__':
    unittest.main()
