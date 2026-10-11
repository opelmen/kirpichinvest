"""Запасной прокси ГИС Торги (_src/svc/gt.php): тот же протокол, что у функции Яндекс Облака в zalog-desk."""
import base64
import hashlib
import http.server
import os
import re
import shutil
import socket
import subprocess
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "_src" / "svc" / "gt.php"
DATA = bytes(range(256)) * 4


class Upstream(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/new/file-store/v1/"):
            a, b = map(int, self.headers["Range"].split("=")[1].split("-"))
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {a}-{b}/{len(DATA)}")
            self.send_header("Content-Disposition", 'attachment; filename="lot.pdf"')
            self.end_headers()
            self.wfile.write(DATA[a:b + 1])
            return
        self.send_response(404 if "missing" in self.path else 200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(self.path.encode())

    def log_message(self, *a):
        pass


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@unittest.skipUnless(shutil.which("php"), "нет php")
class TorgiProxyTest(unittest.TestCase):
    KEY = "test-key"

    @classmethod
    def setUpClass(cls):
        up = http.server.HTTPServer(("127.0.0.1", 0), Upstream)
        threading.Thread(target=up.serve_forever, daemon=True).start()
        cls.up = up
        cls.dir = tempfile.mkdtemp()
        code = re.sub(r"const KEY_SHA256 = '[0-9a-f]{64}'",
                      f"const KEY_SHA256 = '{hashlib.sha256(cls.KEY.encode()).hexdigest()}'", SRC.read_text())
        Path(cls.dir, "gt.php").write_text(code)
        port = free_port()
        env = {k: v for k, v in os.environ.items() if "proxy" not in k.lower()}
        env["TORGI_BASE"] = f"http://127.0.0.1:{up.server_port}"
        cls.php = subprocess.Popen(["php", "-S", f"127.0.0.1:{port}"], cwd=cls.dir, env=env,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        cls.url = f"http://127.0.0.1:{port}/gt.php"
        cls.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        for _ in range(50):
            try:
                socket.create_connection(("127.0.0.1", port), 0.2).close()
                break
            except OSError:
                time.sleep(0.1)

    @classmethod
    def tearDownClass(cls):
        cls.php.terminate()
        cls.up.shutdown()
        shutil.rmtree(cls.dir)

    def get(self, params):
        try:
            r = self.opener.open(self.url + "?" + urllib.parse.urlencode(params), timeout=10)
            return r.status, r.headers, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.headers, e.read()

    def test_real_key_hash_is_set(self):
        self.assertRegex(SRC.read_text(), r"const KEY_SHA256 = '[0-9a-f]{64}'")

    def test_wrong_key(self):
        self.assertEqual(self.get([("key", "x"), ("path", "/new/api/public/lotcards/search")])[0], 403)

    def test_only_public_paths(self):
        for path in ("/etc/passwd", "/new/api/private/x", "/new/api/public/../../x", "https://evil/new/api/public/"):
            self.assertEqual(self.get([("key", self.KEY), ("path", path)])[0], 400, path)

    def test_search_keeps_repeated_params(self):
        code, _, body = self.get([("key", self.KEY), ("path", "/new/api/public/lotcards/search"),
                                  ("dynSubjRF", "77"), ("dynSubjRF", "78"), ("text", "кв 1")])
        self.assertEqual(code, 200)
        self.assertEqual(body.decode(), "/new/api/public/lotcards/search?dynSubjRF=77&dynSubjRF=78&text=%D0%BA%D0%B2%201")

    def test_upstream_status_passed_through(self):
        self.assertEqual(self.get([("key", self.KEY), ("path", "/new/api/public/missing")])[0], 404)

    def test_file_chunk_as_base64(self):
        code, h, body = self.get([("key", self.KEY), ("path", "/new/file-store/v1/6a85a18c"), ("range", "10-19")])
        self.assertEqual(code, 200)
        self.assertEqual(base64.b64decode(body), DATA[10:20])
        self.assertEqual(h["X-Total"], "1024")
        self.assertIn("lot.pdf", urllib.parse.unquote(h["X-Name"]))


if __name__ == "__main__":
    unittest.main()
