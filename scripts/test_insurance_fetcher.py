"""Tests for scripts/insurance_fetcher.py.

Uses httpx.MockTransport (part of httpx itself, no extra test dependency)
instead of hitting real network -- deterministic, and this project already
depends on httpx everywhere in scripts/sources/ib_disclosure/*.

Run: python scripts/test_insurance_fetcher.py
"""

from __future__ import annotations

import ssl
import sys
import unittest
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))

from insurance_fetcher import (  # noqa: E402
    InsuranceFetcher,
    _classify_exception,
    is_retryable_error,
)


class FakeClock:
    """Deterministic, manually-advanced clock -- avoids real sleeps in tests."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


def _fetcher(handler, **kwargs) -> InsuranceFetcher:
    clock = FakeClock()
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return InsuranceFetcher(client=client, clock=clock, sleep=clock.sleep, delay_seconds=1.0, **kwargs)


class TestExceptionClassification(unittest.TestCase):
    def test_connect_timeout(self):
        self.assertEqual(_classify_exception(httpx.ConnectTimeout("x")), "FETCH_CONNECT_TIMEOUT")

    def test_read_timeout(self):
        self.assertEqual(_classify_exception(httpx.ReadTimeout("x")), "FETCH_READ_TIMEOUT")

    def test_too_many_redirects(self):
        self.assertEqual(_classify_exception(httpx.TooManyRedirects("x")), "FETCH_REDIRECT_LIMIT")

    def test_connect_error(self):
        self.assertEqual(_classify_exception(httpx.ConnectError("x")), "FETCH_CONNECTION_ERROR")

    def test_tls_error_via_cause_chain(self):
        ssl_error = ssl.SSLError("certificate verify failed")
        wrapped = httpx.ConnectError("tls broke")
        wrapped.__cause__ = ssl_error
        self.assertEqual(_classify_exception(wrapped), "FETCH_TLS_ERROR")

    def test_generic_request_error(self):
        self.assertEqual(_classify_exception(httpx.RequestError("x")), "FETCH_REQUEST_ERROR")

    def test_is_retryable(self):
        self.assertTrue(is_retryable_error("HTTP_429"))
        self.assertTrue(is_retryable_error("HTTP_5XX"))
        self.assertTrue(is_retryable_error("FETCH_CONNECT_TIMEOUT"))
        self.assertFalse(is_retryable_error("BODY_TOO_LARGE"))
        self.assertFalse(is_retryable_error(None))


class TestInsuranceFetcher(unittest.TestCase):
    def test_successful_fetch_and_content_type(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, headers={"content-type": "text/html; charset=utf-8"}, content=b"<html>ok</html>")

        fetcher = _fetcher(handler)
        response = fetcher.get("https://example.gov.tw/page")
        self.assertIsNone(response.error_code)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content_type, "text/html")
        self.assertTrue(response.ok)
        self.assertEqual(response.body, b"<html>ok</html>")

    def test_body_too_large(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=b"x" * 1000)

        fetcher = _fetcher(handler, max_body_bytes=10)
        response = fetcher.get("https://example.gov.tw/big")
        self.assertEqual(response.error_code, "BODY_TOO_LARGE")

    def test_429_with_retry_after_updates_host_delay(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(429, headers={"retry-after": "5"}, content=b"slow down")

        fetcher = _fetcher(handler)
        host = "example.gov.tw"
        self.assertEqual(fetcher._delay_for(host), 1.0)
        response = fetcher.get("https://example.gov.tw/limited")
        self.assertEqual(response.error_code, "HTTP_429")
        self.assertEqual(fetcher.host_delay[host], 5.0)  # Retry-After wins over current*2 (2.0)

    def test_successful_fetch_relaxes_host_delay(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=b"ok")

        fetcher = _fetcher(handler)
        host = "example.gov.tw"
        fetcher.host_delay[host] = 10.0
        fetcher.get("https://example.gov.tw/ok")
        self.assertAlmostEqual(fetcher.host_delay[host], 9.0)  # relaxed by 10%, still above floor

    def test_server_error_classified_as_http_5xx(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(503, content=b"down")

        fetcher = _fetcher(handler)
        response = fetcher.get("https://example.gov.tw/down")
        self.assertEqual(response.error_code, "HTTP_5XX")

    def test_transport_exception_becomes_stable_code(self):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectTimeout("timed out", request=request)

        fetcher = _fetcher(handler)
        response = fetcher.get("https://example.gov.tw/timeout")
        self.assertEqual(response.error_code, "FETCH_CONNECT_TIMEOUT")
        self.assertEqual(response.status_code, 0)


if __name__ == "__main__":
    unittest.main()
