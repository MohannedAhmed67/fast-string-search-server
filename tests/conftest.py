import pytest

from src.server.ssl_utils import generate_certificate_and_key
from tests.ssl_constants import CERTS_DIR, SERVER_CRT, SERVER_KEY


@pytest.fixture(scope="session", autouse=True)
def generate_test_certs() -> None:
    """Generates SSL certificates for testing if they don't already exist.
    This fixture runs automatically once per test session.
    """
    if SERVER_CRT.exists() and SERVER_KEY.exists():
        print(
            "\nSSL certificates already exist in "
            f"{CERTS_DIR}. Skipping generation.",
        )
        return

    print(
        f"\nSSL certificates not found in {CERTS_DIR}. Generating them now...",
    )
    CERTS_DIR.mkdir(parents=True, exist_ok=True)

    generate_certificate_and_key(CERTS_DIR)
