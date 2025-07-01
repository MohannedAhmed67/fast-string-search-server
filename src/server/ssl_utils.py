"""Load/create SSL context, certificates."""

import os
import subprocess
import sys
from pathlib import Path


def generate_certificate_and_key(
    gen_path: Path,
    cert_name: str = "cert.pem",
    key_name: str = "key.pem",
) -> None:
    """Generate a self-signed SSL certificate and key using OpenSSL.

    Args:
        gen_path (Path): The directory where the certificate and key
            files will be created.
        cert_name (str, optional): The name of the certificate file.
            Defaults to "cert.pem".
        key_name (str, optional): The name of the key file.
            Defaults to "key.pem".

    """
    cert_path = gen_path / cert_name
    key_path = gen_path / key_name

    if cert_path.exists() and key_path.exists():
        print(
            f"[SSL_UTILS] SSL cert and key already exist: "
            f"{cert_path}, {key_path}",
        )
        return

    print(
        f"[SSL_UTILS] Generating self-signed SSL certificate and key in "
        f"{gen_path}...",
    )
    try:
        subprocess.run(
            ["openssl", "genrsa", "-out", str(key_path), "2048"],
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            [
                "openssl",
                "req",
                "-new",
                "-x509",
                "-key",
                str(key_path),
                "-out",
                str(cert_path),
                "-days",
                "365",
                "-nodes",
                "-subj",
                "/C=US/ST=State/L=City/O=Org/OU=Unit/CN=localhost",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        print(f"[SSL_UTILS] Successfully generated {cert_path} and {key_path}")

    except FileNotFoundError:
        print(
            "[SSL_UTILS ERROR] OpenSSL not found. Please install OpenSSL.",
            file=sys.stderr,
        )
        if cert_path.exists():
            os.remove(cert_path)
        if key_path.exists():
            os.remove(key_path)

    except subprocess.CalledProcessError as e:
        print(
            f"[SSL_UTILS ERROR] OpenSSL command failed: {e}",
            file=sys.stderr,
        )
        print(f"Stdout: {e.stdout}", file=sys.stderr)
        print(f"Stderr: {e.stderr}", file=sys.stderr)
        if cert_path.exists():
            os.remove(cert_path)
        if key_path.exists():
            os.remove(key_path)

    except Exception as e:
        print(
            "[SSL_UTILS ERROR] An unexpected error "
            f"occurred during SSL generation: {e}",
            file=sys.stderr,
        )
        if cert_path.exists():
            cert_path.unlink()
        if key_path.exists():
            key_path.unlink()
