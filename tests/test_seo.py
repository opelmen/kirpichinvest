import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '_src'))
from lot_history import merge_history

class LifecycleTests(unittest.TestCase):
    def test_missing_is_not_sold_and_reappearance_restores_active(self):
        now = datetime(2026, 10, 3, tzinfo=timezone.utc)
        row = dict(id='one_1', bidd_end='2027-01-01T00:00:00Z', label='Flat', description='PRIVATE', name='PRIVATE')
        first = merge_history([row], [], now)
        absent = merge_history([], first, now)
        self.assertEqual(absent[0]['status'], 'unavailable')
        self.assertNotIn('description', absent[0])
        self.assertNotIn('name', absent[0])
        self.assertEqual(merge_history([row], absent, now)[0]['status'], 'active')

    def test_expiry_and_meaningful_lastmod(self):
        now = datetime(2026, 10, 3, tzinfo=timezone.utc)
        row = dict(id='two', price=10, bidd_end='2026-10-04T00:00:00Z')
        first = merge_history([row], [], now)
        unchanged = merge_history([row], first, datetime(2026, 10, 3, 12, tzinfo=timezone.utc))
        self.assertEqual(first[0]['lastmod'], unchanged[0]['lastmod'])
        ended = merge_history([], first, datetime(2026, 10, 5, tzinfo=timezone.utc))
        self.assertEqual(ended[0]['status'], 'ended')
        self.assertEqual(ended[0]['lastmod'], '2026-10-05')
        changed = merge_history([dict(row, price=20)], first, datetime(2026, 10, 4, tzinfo=timezone.utc))
        self.assertEqual(changed[0]['lastmod'], '2026-10-04')

    def test_invalid_id_fails(self):
        with self.assertRaises(ValueError):
            merge_history([{'id':'../escape'}], [], datetime.now(timezone.utc))

class BuildTests(unittest.TestCase):
    def test_paginated_catalog_and_retained_card(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            shutil.copytree(ROOT / '_src', base / '_src')
            (base / '_src/data/market.json').unlink(missing_ok=True)  # тест прежнего фида Залог-Деска
            rows = [dict(id=f'test_{i}', city='moskva', region='77', address='Москва, Тестовая улица, дом 1', price=1000000, area=40, bidd_end='2099-01-01T00:00:00Z') for i in range(65)]
            rows[1]['bidd_type'] = 'Реализация имущества должников'
            data = base / '_src/data'
            rows[0].update(city='sankt-peterburg', region='47', address='Ленинградская область, Гатчинский район, г. Гатчина, Тестовая улица, дом 1')
            (data/'lot_history.json').write_text('[]')
            (data/'lots.json').write_text(json.dumps(rows))
            def build():
                subprocess.run([sys.executable, str(base/'_src/build.py')], check=True, capture_output=True)
            build()
            site = base/'_site'
            self.assertIn('noindex', (site/'torgi/doli/index.html').read_text())
            self.assertNotIn('https://torggid.ru/torgi/doli/', (site/'sitemap.xml').read_text())
            self.assertIn('Состав права нужно проверить', (site/'torgi/do-1-mln/index.html').read_text())
            self.assertIn('/byudzhet/', (site/'index.html').read_text())
            self.assertTrue((site/'torgi/sankt-peterburg/gatchinskiy-rayon/index.html').exists())
            self.assertTrue((site/'torgi/page/2/index.html').exists())
            page2 = (site/'torgi/page/2/index.html').read_text()
            self.assertIn('rel="canonical" href="https://torggid.ru/torgi/page/2/"', page2)
            self.assertEqual(page2.count('class="lot"'), 5)
            self.assertIn('/torgi/page/2/', (site/'torgi/index.html').read_text())
            rows[1]['status'] = 'ignored'  # Build derives lifecycle from source/deadline.
            rows[1]['bidd_type'] = 'Аренда'
            (data/'lots.json').write_text(json.dumps(rows[1:]))
            build()
            self.assertIn('noindex', (site/'torgi/do-1-mln/index.html').read_text())
            self.assertNotIn('https://torggid.ru/torgi/do-1-mln/', (site/'sitemap.xml').read_text())
            card = (site/'torgi/lot/test_0/index.html').read_text()
            self.assertIn('Результат торгов и факт продажи не подтверждены', card)
            self.assertNotIn('Получить отчёт', card)
            self.assertIn('/torgi/arhiv/', (site/'torgi/index.html').read_text())
            self.assertEqual(len(list((site/'torgi/lot').glob('*/index.html'))),65)

    def test_market_feed_whole_country(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            shutil.copytree(ROOT / '_src', base / '_src')
            data = base / '_src/data'
            (data/'lot_history.json').write_text('[]')
            row = dict(source='mets', source_url='https://m-ets.ru/x', kind='bankruptcy', stage='repeat', procedure='Публичное предложение',
                       category='flat', title='Квартира', address='Республика Татарстан, г. Альметьевск, ул. Ленина, д. 5', city=None, region='16',
                       area=40.5, rooms=1, price=2_000_000, price_start=2_500_000, market_price=3_000_000, market_conf='medium', discount_pct=33.3,
                       risks=[dict(key='minors', title='Несовершеннолетние', level='high')], own_time='4–11 мес.',
                       bidd_end='2099-01-01T00:00:00+00:00', first_seen='2026-10-09T00:00:00+00:00')
            rows = [dict(row, id='gistorgi:21000000000000000001_1', source='gistorgi', kind='arrest', category='land', city='kazan')]
            rows += [dict(row, id=f'mets:{i}') for i in range(3)]
            rows.append(dict(row, id='mets:9', discount_pct=55.0, suspect=True))
            (data/'market.json').write_text(json.dumps({'lots': rows}, ensure_ascii=False))
            subprocess.run([sys.executable, str(base/'_src/build.py')], check=True, capture_output=True)
            site = base/'_site'
            self.assertIn('по всей России', (site/'torgi/index.html').read_text())
            region = (site/'torgi/tatarstan/index.html').read_text()
            self.assertIn('Недвижимость с торгов в Татарстане', region)
            card = (site/'torgi/lot/mets-0/index.html').read_text()
            self.assertIn('Выгодно, но с рисками', card)
            self.assertIn('Извещение и документы на МЭТС', card)
            self.assertIn('/lot/mets%3A0', card)
            self.assertIn('RealEstateListing', card)
            self.assertIn('проверьте оценку', (site/'torgi/lot/mets-9/index.html').read_text())
            self.assertTrue((site/'torgi/lot/21000000000000000001_1/index.html').exists())  # адреса ГИС Торги прежние
            self.assertIn('Земельный участок', (site/'torgi/zemlya/index.html').read_text())
            land = (site/'torgi/lot/21000000000000000001_1/index.html').read_text()
            self.assertIn('Земля: оценка вручную', land)  # оценка по квартирам к земле не применяется
            self.assertNotIn('Выгодно', land)
            self.assertIn('?buy=1', card)  # отчёт ведёт сразу к покупке в приложении

if __name__ == '__main__':
    unittest.main()
