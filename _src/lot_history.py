"""Persist only already-public card fields, never raw notices or debtor details."""
import hashlib
import json
import re
from datetime import datetime, timezone

FIELDS = ('id', 'city', 'city_name', 'region', 'caddr', 'label', 'price', 'area',
          'ppm2', 'rooms', 'floor', 'bidd_type', 'bidd_end', 'flags',
          'eff_market', 'eff_discount', 'liq', 'source_url', 'first_seen', 'cadastral', 'district', 'town',
          'app_id', 'source_name', 'kind', 'kind_name', 'category', 'risks', 'own_time', 'verdict',
          'region_slug', 'region_name', 'price_start', 'city_market')


def merge_history(current, previous, now):
    """Missing from a successful feed is not proof of a sale or completed auction."""
    today = now.date().isoformat()
    old = {str(d['id']): d for d in previous}
    incoming = {str(d['id']): d for d in current}
    result = []
    for lot_id in sorted(old.keys() | incoming.keys()):
        if not re.fullmatch(r'[A-Za-z0-9_-]+', lot_id):
            raise ValueError('Invalid public lot ID')
        d = {k: (incoming.get(lot_id) or old[lot_id]).get(k) for k in FIELDS}
        deadline = d.get('bidd_end')
        end = None
        if deadline:
            try:
                end = datetime.fromisoformat(str(deadline).replace('Z', '+00:00'))
                end = end if end.tzinfo else end.replace(tzinfo=timezone.utc)
            except ValueError:
                pass
        d['status'] = 'ended' if end and end < now else ('active' if lot_id in incoming else 'unavailable')
        d['days_left'] = (end - now).total_seconds() / 86400 if end else None
        # The crawl timestamp does not falsely change the content's lastmod.
        fingerprint = hashlib.sha256(json.dumps({k: v for k, v in d.items() if k != 'days_left'}, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        prior = old.get(lot_id, {})
        d['lastmod'] = prior.get('lastmod', today) if prior.get('fingerprint') == fingerprint else today
        d['fingerprint'] = fingerprint
        d['last_seen'] = today if lot_id in incoming else prior.get('last_seen', today)
        result.append(d)
    return result
