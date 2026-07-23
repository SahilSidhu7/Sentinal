"""Unit tests for vibesentinel_core's pure logic (no Docker / no model needed)."""
from vibesentinel_core import ids
from vibesentinel_core.monitor import _clean, _is_noise


def test_new_id_shape():
    i = ids.new_id()
    assert len(i) == 6
    assert all(c in "0123456789ABCDEFGHJKMNPQRSTVWXYZ" for c in i)  # no ambiguous I/L/O/U


def test_slugify_normalizes_and_falls_back():
    assert ids.slugify("My Cool App!") == "my-cool-app"
    assert ids.slugify("  spaced  ") == "spaced"
    # nothing usable -> a generated id, not an empty string
    assert len(ids.slugify("!!!")) == 6


def test_clean_strips_ansi_and_cr():
    assert _clean("\x1b[32mhello\x1b[0m\r\n") == "hello\n"


def test_is_noise_filters_prompts_and_short_lines():
    # shell prompt + command echo is not a log record
    assert _is_noise("root@abc123:~# python3 /opt/demo_server.py")
    # too short to be a real log line
    assert _is_noise("ok")
    # a real nginx access line is NOT noise
    assert not _is_noise('127.0.0.1 - - [23/Jul/2026:19:55:44 +0000] "GET / HTTP/1.1" 200 512 "-" "curl"')
