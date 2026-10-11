"""Notify IndexNow about published changes. Dry run unless --submit is supplied."""
import argparse
import json
import re
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

HOST = "torggid.ru"
BASE = "https://" + HOST
ENDPOINTS = ("https://yandex.com/indexnow", "https://api.indexnow.org/indexnow")


def validate_urls(urls):
    result = list(dict.fromkeys(urls))
    if not 1 <= len(result) <= 10000:
        raise ValueError("Expected 1–10000 URLs")
    for url in result:
        p = urlsplit(url)
        if (p.scheme != "https" or p.netloc != HOST or p.query or p.fragment
                or any(c.isspace() for c in url)):
            raise ValueError("Only canonical HTTPS URLs on " + HOST + " are allowed")
    return result


def fetch(url):
    with urllib.request.urlopen(url, timeout=30) as response:
        return response.read()


def sitemap_urls(data, fetch=fetch):
    """Адреса страниц из карты сайта. Индекс карт (sitemapindex) раскрывается: каждая вложенная карта
    должна лежать на нашем домене, иначе её не читаем."""
    root = ET.fromstring(data)
    ns = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
    if root.tag == ns + "sitemapindex":
        children = validate_urls([e.text or "" for e in root.findall(ns + "sitemap/" + ns + "loc")])
        urls = []
        for child in children:
            urls.extend(sitemap_urls(fetch(child), fetch))
        return validate_urls(urls)
    if root.tag != ns + "urlset":
        raise ValueError("Expected urlset sitemap")
    return validate_urls([e.text or "" for e in root.findall(ns + "url/" + ns + "loc")])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("urls", nargs="*")
    parser.add_argument("--sitemap", action="store_true", help="Use all URLs from the live sitemap")
    parser.add_argument("--submit", action="store_true", help="Actually send notifications")
    args = parser.parse_args()
    if args.sitemap == bool(args.urls):
        parser.error("Choose --sitemap OR one or more explicit URLs")
    urls = args.urls
    if args.sitemap:
        urls = sitemap_urls(fetch(BASE + "/sitemap.xml"))
    urls = validate_urls(urls)
    result = {"at": datetime.now(timezone.utc).isoformat(), "count": len(urls),
              "submitted": args.submit, "urls": urls, "responses": []}
    if args.submit:
        key = json.loads(Path(__file__).with_name("config.json").read_text())["INDEXNOW_KEY"]
        if not re.fullmatch(r"[a-zA-Z0-9-]{8,128}", key):
            raise ValueError("Invalid IndexNow key")
        key_url = BASE + "/" + key + ".txt"
        with urllib.request.urlopen(key_url, timeout=30) as response:
            if response.read().decode("utf-8").strip() != key:
                raise ValueError("Live key verification failed; nothing submitted")
        body = json.dumps({"host": HOST, "key": key, "keyLocation": key_url,
                           "urlList": urls}).encode()
        for endpoint in ENDPOINTS:
            request = urllib.request.Request(endpoint, data=body,
                headers={"Content-Type": "application/json; charset=utf-8"})
            try:
                with urllib.request.urlopen(request, timeout=45) as response:
                    status = response.status
            except urllib.error.HTTPError as error:
                status = error.code
            except (urllib.error.URLError, TimeoutError):
                status = "network_error"
            result["responses"].append({"endpoint": endpoint, "status": status})
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return int(any(r["status"] not in (200, 202) for r in result["responses"]))


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, OSError, ET.ParseError) as error:
        sys.exit("IndexNow stopped: " + type(error).__name__)
