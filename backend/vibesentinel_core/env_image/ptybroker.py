"""In-container PTY broker.

The host can't allocate a Unix PTY (it may be Windows), so we allocate it here,
inside the Linux environment container, and just pipe raw bytes over the
`docker exec` stdio the host holds. The host bridges those bytes to an xterm.js
websocket; from the shell's point of view it's a normal interactive terminal
(colors, line editing, job control).

Control protocol: the host may prepend a resize request as a line on stdin of
the form `\x1b_RESIZE:<cols>:<rows>\x1b\\` (an APC string, never emitted by a
real keyboard) which we intercept and turn into a TIOCSWINSZ ioctl instead of
forwarding to the shell.
"""
import fcntl
import os
import pty
import select
import signal
import struct
import sys
import termios

RESIZE_PREFIX = b"\x1b_RESIZE:"
RESIZE_SUFFIX = b"\x1b\\"


def _set_winsize(fd: int, cols: int, rows: int) -> None:
    winsize = struct.pack("HHHH", rows, cols, 0, 0)
    fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)


def _handle_control(fd: int, buf: bytes) -> bytes:
    """Pull out any complete RESIZE control frames from `buf`, apply them, and
    return the remaining bytes destined for the shell."""
    while True:
        start = buf.find(RESIZE_PREFIX)
        if start == -1:
            return buf
        end = buf.find(RESIZE_SUFFIX, start)
        if end == -1:
            return buf  # frame split across reads — wait for the rest
        payload = buf[start + len(RESIZE_PREFIX):end]
        try:
            cols, rows = (int(x) for x in payload.split(b":"))
            _set_winsize(fd, cols, rows)
        except (ValueError, OSError):
            pass
        buf = buf[:start] + buf[end + len(RESIZE_SUFFIX):]


def main() -> None:
    shell = sys.argv[1] if len(sys.argv) > 1 else "/bin/bash"
    pid, fd = pty.fork()
    if pid == 0:
        os.environ.setdefault("TERM", "xterm-256color")
        os.execvp(shell, [shell, "-i"])
        os._exit(127)

    _set_winsize(fd, 120, 32)
    pending = b""
    try:
        while True:
            rlist, _, _ = select.select([fd, 0], [], [])
            if fd in rlist:
                try:
                    data = os.read(fd, 65536)
                except OSError:
                    break
                if not data:
                    break
                os.write(1, data)
            if 0 in rlist:
                data = os.read(0, 65536)
                if not data:
                    break
                pending = _handle_control(fd, pending + data)
                if pending and RESIZE_PREFIX not in pending:
                    os.write(fd, pending)
                    pending = b""
    finally:
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass


if __name__ == "__main__":
    main()
