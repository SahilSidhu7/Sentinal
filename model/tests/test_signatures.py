from vibesentinel_model import signatures


def test_sqli_detected():
    m = signatures.match("GET /product?id=1 OR 1=1")
    assert m is not None and m.category == "sqli"


def test_sqli_union_select_detected():
    m = signatures.match("id=1; DROP TABLE users; UNION SELECT * FROM secrets")
    assert m is not None and m.category == "sqli"


def test_xss_script_tag_detected():
    m = signatures.match('q=<script>alert(document.cookie)</script>')
    assert m is not None and m.category == "xss"


def test_xss_event_handler_detected():
    m = signatures.match('name="><img src=x onerror=alert(1)>')
    assert m is not None and m.category == "xss"


def test_traversal_detected():
    m = signatures.match("file=../../../../etc/passwd")
    assert m is not None and m.category == "traversal"


def test_cmdi_detected():
    m = signatures.match("host=127.0.0.1; whoami")
    assert m is not None and m.category == "cmdi"


def test_normal_request_no_match():
    assert signatures.match("GET /tienda1/publico/anadir.jsp?nombre=Jamon+Iberico&precio=85") is None


def test_normal_syslog_line_no_match():
    assert signatures.match("Jun  9 06:06:20 combo kernel: klogd 1.4.1 started") is None


def test_url_encoded_sqli_detected():
    m = signatures.match("cantidad=%27%3B+DROP+TABLE+usuarios%3B+SELECT+*+FROM+datos")
    assert m is not None and m.category == "sqli"


def test_url_encoded_xss_detected():
    m = signatures.match("login=bob%40%3CSCRipt%3Ealert%28Paros%29%3C%2FscrIPT%3E")
    assert m is not None and m.category == "xss"


def test_double_url_encoded_xss_detected():
    m = signatures.match("modo=registro%253CSCRIPT%253Ealert%2528%2522Paros%2522%2529%253B%253C%252FSCRIPT%253E")
    assert m is not None and m.category == "xss"


def test_recon_probe_detected():
    m = signatures.match('103.163.220.8 - - [19/Apr/2026] "GET /wp-admin/css/colors/coffee/index.php HTTP/1.1" 404')
    assert m is not None and m.category == "recon_probe"


def test_overflow_probe_detected():
    m = signatures.match("name=" + "A" * 200)
    assert m is not None and m.category == "overflow"


def test_crlf_injection_detected():
    m = signatures.match("redirect=%0d%0aSet-Cookie:%20session=hijacked")
    assert m is not None and m.category == "crlf"
