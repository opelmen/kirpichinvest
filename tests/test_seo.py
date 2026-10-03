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
            rows = [dict(id=f'test_{i}', city='moskva', region='77', address='Москва, Тестовая улица, дом 1', price=1000000, area=40, bidd_end='2099-01-01T00:00:00Z') for i in range(65)]
            data = base / '_src/data'
            rows[0].update(city='sankt-peterburg', region='47', address='Ленинградская область, Гатчинский район, г. Гатчина, Тестовая улица, дом 1')
            (data/'lot_history.json').write_text('[]')
            (data/'lots.json').write_text(json.dumps(rows))
            def build():
                subprocess.run([sys.executable, str(base/'_src/build.py')], check=True, capture_output=True)
            build()
            site = base/'_site'
            self.assertTrue((site/'torgi/sankt-peterburg/gatchinskiy-rayon/index.html').exists())
            self.assertTrue((site/'torgi/page/2/index.html').exists())
            page2 = (site/'torgi/page/2/index.html').read_text()
            self.assertIn('rel="canonical" href="https://kirpichinvest.ru/torgi/page/2/"', page2)
            self.assertEqual(page2.count('class="lot"'), 5)
            self.assertIn('/torgi/page/2/', (site/'torgi/index.html').read_text())
            (data/'lots.json').write_text(json.dumps(rows[1:]))
            build()
            card = (site/'torgi/lot/test_0/index.html').read_text()
            self.assertIn('Результат торгов и факт продажи не подтверждены', card)
            self.assertNotIn('Получить отчёт', card)
            self.assertIn('/torgi/arhiv/', (site/'torgi/index.html').read_text())
            self.assertEqual(len(list((site/'torgi/lot').glob('*/index.html'))),65)

if __name__ == '__main__':
    unittest.main()
