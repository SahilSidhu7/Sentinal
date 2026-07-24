"""A throwaway HTTP server for demoing live monitoring.

Run it in the *server* terminal. It logs one nginx-combined access line per
request to stdout — exactly the format the shipped `nginx` anomaly model was
trained on — so the monitor tapping this terminal has real traffic to score.
Hit it from the *tests* terminal:

    curl 'localhost:8080/'                 # normal -> no alert
    curl "localhost:8080/?q=' OR 1=1--"    # SQLi payload -> signature alert
    curl 'localhost:8080/?x=<script>alert(1)</script>'  # XSS -> alert
"""
import datetime
import http.server


class Handler(http.server.BaseHTTPRequestHandler):
    def _access_log(self) -> None:
        now = datetime.datetime.now().strftime("%d/%b/%Y:%H:%M:%S +0000")
        ua = self.headers.get("User-Agent", "-")
        line = (
            f'{self.client_address[0]} - - [{now}] '
            f'"{self.command} {self.path} HTTP/1.1" 200 512 "-" "{ua}"'
        )
        print(line, flush=True)

    def do_GET(self) -> None:
        self._access_log()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"ok\n")

    def log_message(self, *args) -> None:  # silence the default stderr logger
        pass


if __name__ == "__main__":
    print("demo server on :8080 — logging nginx-combined access lines", flush=True)
    http.server.HTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
