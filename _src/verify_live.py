"""Compare published bytes with this build; no submissions or lead generation."""
import concurrent.futures
import hashlib
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / '_site'
BASE = 'https://torggid.ru'
STAMP = os.environ.get('GITHUB_RUN_ID', str(int(time.time())))

def check(path):
    relative = path.relative_to(ROOT).as_posix()
    url_path = '/' + relative
    if url_path.endswith('/index.html'):
        url_path = url_path[:-10]
    for attempt in range(3):
        try:
            req = urllib.request.Request(BASE + url_path + '?seo_verify=' + STAMP, headers={'User-Agent':'TorgGid-Release-Check/1.0','Cache-Control':'no-cache'})
            with urllib.request.urlopen(req, timeout=25) as r:
                body = r.read()
                if r.status == 200 and hashlib.sha256(body).digest() == hashlib.sha256(path.read_bytes()).digest():
                    return None
            error = 'content mismatch'
        except Exception as e:
            error = str(e)
        time.sleep(attempt + 1)
    return {'path':url_path, 'error':error}

if __name__ == '__main__':
    files = list(ROOT.rglob('*.html')) + [p for p in (ROOT/'static').rglob('*') if p.is_file()] + [ROOT/n for n in ('sitemap.xml','robots.txt','llms.txt')]
    assert files and (ROOT/'index.html').exists()
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        errors = [e for e in pool.map(check, files) if e]
    try:
        urllib.request.urlopen(BASE+'/seo-release-missing-page-check/', timeout=25)
        errors.append({'path':'missing-page','error':'expected 404'})
    except urllib.error.HTTPError as e:
        if e.code != 404: errors.append({'path':'missing-page','error':str(e.code)})
    print(f'Live verification: {len(files)} files, {len(errors)} errors')
    for error in errors: print(error)
    raise SystemExit(bool(errors))
