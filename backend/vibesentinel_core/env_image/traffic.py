"""Fake traffic + attack generator for demoing live detection.

Run it in the *tests* terminal while `demo_server.py` runs in the *server*
terminal. It fires mostly-normal requests with periodic real attack payloads
mixed in — the monitor tapping the server terminal should raise an `attack`
alert for each malicious one and stay quiet on the normal ones (after warmup).

    python3 /opt/traffic.py            # runs ~40 requests then stops
    python3 /opt/traffic.py --forever  # continuous, Ctrl+C to stop
"""
import random
import sys
import time
import urllib.parse
import urllib.request

BASE = "http://127.0.0.1:8080"

NORMAL = [
    "/", "/index.html", "/about", "/products?page=2", "/search?q=laptop",
    "/api/v1/users/42", "/static/app.css", "/login", "/cart?item=17",
    "/blog/2026/summer-sale", "/health", "/favicon.ico",
]

# (label, raw path) — payloads a signature should catch (see model signatures.py)
ATTACKS = [
    ("sqli", "/items?q=" + urllib.parse.quote("1' OR 1=1--")),
    ("sqli", "/user?id=" + urllib.parse.quote("1 UNION SELECT password FROM users")),
    ("xss", "/search?q=" + urllib.parse.quote("<script>alert(document.cookie)</script>")),
    ("xss", "/c?m=" + urllib.parse.quote("<img src=x onerror=alert(1)>")),
    ("traversal", "/file?p=" + urllib.parse.quote("../../../../etc/passwd")),
    ("cmdi", "/ping?host=" + urllib.parse.quote("127.0.0.1; cat /etc/shadow")),
    ("recon_probe", "/wp-login.php"),
    ("recon_probe", "/.env"),
]


def fire(path: str) -> None:
    try:
        urllib.request.urlopen(BASE + path, timeout=2).read()
    except Exception as exc:  # noqa: BLE001 — server may 404/close, we only care it logged
        print(f"  (request error, ignored: {exc})", flush=True)


def main() -> None:
    forever = "--forever" in sys.argv
    count = 0
    print("traffic generator -> " + BASE + (" (forever)" if forever else " (~40 requests)"), flush=True)
    while forever or count < 40:
        # ~1 in 5 requests is an attack
        if random.random() < 0.2:
            label, path = random.choice(ATTACKS)
            print(f"[attack:{label}] {path}", flush=True)
        else:
            path = random.choice(NORMAL)
            print(f"[normal] {path}", flush=True)
        fire(path)
        count += 1
        time.sleep(0.4)
    print(f"done — sent {count} requests", flush=True)


if __name__ == "__main__":
    main()
