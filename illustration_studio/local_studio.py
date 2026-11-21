"""Mac-side SVG studio. The model stays on Vast behind the SSH tunnel."""
import http.client
import json
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
UPSTREAM_PORT = int(os.environ.get("ATELIER_UPSTREAM_PORT", "8090"))
PORT = 8765


class Studio(BaseHTTPRequestHandler):
    def reply(self, code, mime, data):
        self.send_response(code)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'self'; script-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        assets = {"/": ("studio.html", "text/html; charset=utf-8"),
                  "/studio.css": ("studio.css", "text/css"),
                  "/studio.js": ("studio.js", "text/javascript")}
        if self.path in assets:
            name, mime = assets[self.path]
            self.reply(200, mime, (ROOT / name).read_bytes())
        elif self.path == "/health":
            conn = http.client.HTTPConnection("127.0.0.1", UPSTREAM_PORT, timeout=5)
            try:
                conn.request("GET", "/health")
                response = conn.getresponse()
                ready = response.status == 200 and response.read(100) == b"ready"
            except (OSError, http.client.HTTPException):
                ready = False
            finally:
                conn.close()
            self.reply(200, "application/json", json.dumps({"ready": ready}).encode())
        elif self.path == "/sample":
            for name in ("step-0625", "base"):
                folder = ROOT / "results" / name
                meta = folder / "00.json"
                if meta.exists():
                    row = json.loads(meta.read_text())
                    if row.get("valid"):
                        svg = re.search(r"<svg\b.*?</svg>", (folder / "00.txt").read_text(), re.S)
                        if svg:
                            self.reply(200, "application/json", json.dumps(dict(prompt=row["description"], model=name, svg=svg.group())).encode())
                            return
            self.reply(200, "application/json", b"null")
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path != "/generate":
            self.send_error(404)
            return
        origin = self.headers.get("Origin")
        if origin and origin not in {f"http://127.0.0.1:{PORT}", f"http://localhost:{PORT}"}:
            self.send_error(403)
            return
        if self.headers.get_content_type() != "application/json":
            self.send_error(415)
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            if not 0 < length <= 12000:
                raise ValueError
        except ValueError:
            self.send_error(400)
            return
        conn = http.client.HTTPConnection("127.0.0.1", UPSTREAM_PORT, timeout=600)
        sent = False
        try:
            conn.request("POST", "/generate", self.rfile.read(length), {"Content-Type": "application/json"})
            response = conn.getresponse()
            if response.status != 200:
                self.send_error(response.status)
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            sent = True
            while line := response.readline():
                self.wfile.write(line)
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            if not sent:
                self.send_error(502)
        except (OSError, http.client.HTTPException):
            if not sent:
                self.send_error(502, "Model connection unavailable")
        finally:
            conn.close()


if __name__ == "__main__":
    print(f"Le Chat Atelier listening at http://127.0.0.1:{PORT}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", PORT), Studio).serve_forever()
