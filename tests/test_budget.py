import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / '_src'))
from budget_collections import budget_lots, budget_summary, object_group


class BudgetTests(unittest.TestCase):
    def test_excludes_unknown_rights_expired_and_invalid_prices(self):
        base = dict(status='active', bidd_type='Реализация имущества должников', price=1_000_000, city='moskva')
        rows = [dict(base, id='valid'), dict(base, id='ended', status='ended'),
                dict(base, id='missing', status='unavailable'), dict(base, id='rent', bidd_type='Аренда'),
                dict(base, id='unknown', bidd_type=None)]
        rows += [dict(base, id=f'bad{i}', price=p) for i, p in enumerate([None, 0, -1, float('nan'), float('inf'), '1', True, 1_000_001])]
        self.assertEqual([d['id'] for d in budget_lots(rows, 1_000_000)], ['valid'])

    def test_mutually_exclusive_groups_and_cumulative_budgets(self):
        base = dict(status='active', bidd_type='Реализация имущества должников', city='moskva')
        rows = [dict(base, id='share', price=500_000, flags='доля, комната / коммуналка'),
                dict(base, id='room', price=1_000_000, flags='комната / коммуналка'),
                dict(base, id='unknown', price=2_000_000, flags=None)]
        s = budget_summary(rows, 2_000_000)
        self.assertEqual((s['count'], s['shares'], s['rooms'], s['other']), (3, 1, 1, 1))
        self.assertEqual(budget_summary(rows, 1_000_000)['count'], 2)
        self.assertIn('проверить', object_group(rows[-1]))
        self.assertEqual([d['id'] for d in budget_lots(list(reversed(rows)), 2_000_000)], ['share', 'room', 'unknown'])
