from pathlib import Path

CERTS_DIR = Path(__file__).resolve().parent / "certs"
SERVER_CRT = CERTS_DIR / "cert.pem"
SERVER_KEY = CERTS_DIR / "key.pem"
