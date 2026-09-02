"""Real tests for app/notify.py's timeout, retry, and circuit-breaker
behavior -- Defects #2 and #7. No mocking of urllib: a real local
HTTP server runs in a background thread and is made to behave badly
on purpose (hang, or fail N times then succeed), so these tests prove
actual socket-level behavior, not just that a mock was called.
"""
import http.server
import threading
import time

import pytest

from app import notify


@pytest.fixture(autouse=True)
def reset_circuit_breaker():
    """Each test starts with a closed circuit and a clean failure count."""
    notify._consecutive_failures = 0
    notify._circuit_open_until = 0.0
    yield
    notify._consecutive_failures = 0
    notify._circuit_open_until = 0.0


class _HangingHandler(http.server.BaseHTTPRequestHandler):
    """Accepts the connection, then never responds -- simulates a
    half-dead downstream receiver."""

    def do_POST(self):
        time.sleep(5)  # long enough that "no timeout" (Defect #2) takes 15s across 3 retries

    def log_message(self, *args):
        pass


class _FlakyHandler(http.server.BaseHTTPRequestHandler):
    """Fails with a 500 for the first N requests (class-level counter,
    reset per test), then succeeds."""

    fail_count = 0
    calls = 0

    def do_POST(self):
        _FlakyHandler.calls += 1
        length = int(self.headers.get("Content-Length", 0))
        self.rfile.read(length)
        if _FlakyHandler.calls <= _FlakyHandler.fail_count:
            self.send_response(500)
            self.end_headers()
        else:
            self.send_response(200)
            self.end_headers()

    def log_message(self, *args):
        pass


class _AlwaysFailHandler(http.server.BaseHTTPRequestHandler):
    calls = 0

    def do_POST(self):
        _AlwaysFailHandler.calls += 1
        length = int(self.headers.get("Content-Length", 0))
        self.rfile.read(length)
        self.send_response(500)
        self.end_headers()

    def log_message(self, *args):
        pass


def _run_server(handler_cls):
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, port


def test_send_webhook_times_out_instead_of_hanging_forever():
    server, port = _run_server(_HangingHandler)
    try:
        start = time.monotonic()
        with pytest.raises((TimeoutError, Exception)):
            notify.send_webhook(f"http://127.0.0.1:{port}/webhook", {"x": 1}, timeout=0.5)
        elapsed = time.monotonic() - start
        assert elapsed < 5, (
            f"send_webhook took {elapsed:.1f}s against a hanging server -- "
            "Defect #2: no timeout is actually being applied"
        )
    finally:
        server.shutdown()


def test_send_webhook_retries_and_succeeds_after_transient_failures():
    _FlakyHandler.calls = 0
    _FlakyHandler.fail_count = 2  # fails twice, succeeds on the 3rd attempt
    server, port = _run_server(_FlakyHandler)
    try:
        status = notify.send_webhook(f"http://127.0.0.1:{port}/webhook", {"x": 1})
        assert status == 200
        assert _FlakyHandler.calls == 3, "expected exactly 3 attempts (2 failures + 1 success)"
    finally:
        server.shutdown()


def test_send_webhook_gives_up_after_max_attempts():
    _AlwaysFailHandler.calls = 0
    server, port = _run_server(_AlwaysFailHandler)
    try:
        with pytest.raises(RuntimeError, match="failed after"):
            notify.send_webhook(f"http://127.0.0.1:{port}/webhook", {"x": 1})
        assert _AlwaysFailHandler.calls == notify.MAX_ATTEMPTS
    finally:
        server.shutdown()


def test_circuit_breaker_opens_after_repeated_consecutive_failures():
    _AlwaysFailHandler.calls = 0
    server, port = _run_server(_AlwaysFailHandler)
    try:
        url = f"http://127.0.0.1:{port}/webhook"
        for _ in range(notify._FAILURE_THRESHOLD):
            with pytest.raises(RuntimeError):
                notify.send_webhook(url, {"x": 1})

        calls_before_open = _AlwaysFailHandler.calls
        start = time.monotonic()
        with pytest.raises(notify.CircuitOpenError):
            notify.send_webhook(url, {"x": 1})
        elapsed = time.monotonic() - start

        assert elapsed < 0.5, "circuit breaker should fail fast, not attempt the network"
        assert _AlwaysFailHandler.calls == calls_before_open, (
            "a call was made to the server even though the circuit should be open"
        )
    finally:
        server.shutdown()
