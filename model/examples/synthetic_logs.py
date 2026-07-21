"""Synthetic Nginx-style access logs: normal baseline traffic + injected attacks."""
import random

NORMAL_PATHS = ["/", "/index.html", "/api/products", "/api/products/42", "/static/app.js",
                "/api/users/17/profile", "/favicon.ico", "/api/cart", "/health"]

USER_AGENTS = ["Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"]

SQLI_PAYLOADS = ["' OR '1'='1", "1; DROP TABLE users--", "' UNION SELECT username, password FROM users--"]
TRAVERSAL_PAYLOADS = ["../../../../etc/passwd", "..\\..\\..\\windows\\win.ini", "/%2e%2e/%2e%2e/etc/passwd"]
XSS_PAYLOADS = ["<script>alert(1)</script>", "\"><img src=x onerror=alert(1)>", "<svg/onload=alert(document.cookie)>"]


def _line(ip: str, path: str, status: int = 200) -> str:
    return f'{ip} - - [21/Jul/2026:10:{random.randint(0,59):02d}:{random.randint(0,59):02d} +0000] "GET {path} HTTP/1.1" {status} {random.randint(200,5000)} "-" "{random.choice(USER_AGENTS)}"'


def generate_normal_traffic(n: int = 200) -> list[str]:
    return [_line(f"10.0.0.{random.randint(2,250)}", random.choice(NORMAL_PATHS)) for _ in range(n)]


def generate_sqli_attack(n: int = 5, ip: str = "203.0.113.7") -> list[str]:
    return [_line(ip, f"/api/products?id={random.choice(SQLI_PAYLOADS)}", status=500) for _ in range(n)]


def generate_traversal_attack(n: int = 5, ip: str = "203.0.113.8") -> list[str]:
    return [_line(ip, f"/download?file={random.choice(TRAVERSAL_PAYLOADS)}", status=404) for _ in range(n)]


def generate_xss_attack(n: int = 5, ip: str = "203.0.113.9") -> list[str]:
    return [_line(ip, f"/search?q={random.choice(XSS_PAYLOADS)}", status=200) for _ in range(n)]


def generate_dataset() -> dict[str, list[str]]:
    return {
        "baseline": generate_normal_traffic(200),
        "normal_eval": generate_normal_traffic(30),
        "sqli": generate_sqli_attack(),
        "traversal": generate_traversal_attack(),
        "xss": generate_xss_attack(),
    }
