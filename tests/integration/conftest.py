"""
Integration test configuration.

Set these environment variables before running:

  INTEGRATION_BASE_URL  Full URL of the deployed app, e.g. https://sh4r3d.com
  INTEGRATION_TOKEN     Invite token (required only if beta_mode is enabled)

Run:
  pytest tests/integration/ -v
"""
import os

import httpx
import pytest

_BASE_URL = os.environ.get("INTEGRATION_BASE_URL", "").rstrip("/")
_TOKEN = os.environ.get("INTEGRATION_TOKEN", "")


@pytest.fixture(scope="session")
def base_url() -> str:
    if not _BASE_URL:
        pytest.skip("INTEGRATION_BASE_URL not set — skipping integration tests")
    return _BASE_URL


@pytest.fixture(scope="session")
def api_client(base_url: str) -> httpx.Client:
    """
    A persistent HTTP client for the duration of the test session.
    Cookies are maintained across requests (session auth).
    Redirects are NOT followed — tests inspect the 302 Location header directly.
    """
    with httpx.Client(base_url=base_url, follow_redirects=False, timeout=30) as client:
        if _TOKEN:
            r = client.post("/api/auth", json={"token": _TOKEN})
            if r.status_code != 200:
                pytest.fail(
                    f"Integration auth failed ({r.status_code}): {r.text}\n"
                    f"Check that INTEGRATION_TOKEN is valid for {base_url}"
                )
        yield client
