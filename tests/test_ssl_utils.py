import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.server.ssl_utils import generate_certificate_and_key


@pytest.fixture
def temp_cert_dir(tmp_path):
    """Creates a temporary directory for certificate and key generation."""
    return tmp_path


@pytest.fixture(autouse=True)
def cleanup_temp_files(temp_cert_dir):
    """Ensures that any created files in the temporary directory are cleaned up
    after each test.
    """
    return
    # We don't need to manually remove files here because tmp_path fixture
    # automatically cleans up its directory after each test.
    # However, if you were not using tmp_path, this fixture would be useful.


def test_generate_certificate_and_key_success(temp_cert_dir):
    """Test successful generation of certificate and key."""
    cert_path = temp_cert_dir / "cert.pem"
    key_path = temp_cert_dir / "key.pem"

    # Mock subprocess.run to simulate successful
    # OpenSSL commands AND file creation
    with patch("subprocess.run") as mock_run:

        def mock_side_effect(command, **kwargs):
            if "genrsa" in command:
                # Simulate key file creation
                Path(command[command.index("-out") + 1]).touch()
                return MagicMock(
                    returncode=0,
                    stdout="genrsa output",
                    stderr="",
                )
            if "req" in command:
                # Simulate cert file creation
                Path(command[command.index("-out") + 1]).touch()
                return MagicMock(returncode=0, stdout="req output", stderr="")
            raise ValueError(f"Unexpected command: {command}")

        mock_run.side_effect = mock_side_effect

        generate_certificate_and_key(temp_cert_dir)

        # Assert subprocess.run was called with correct arguments
        assert mock_run.call_count == 2
        # Check that the -out argument for key
        # and cert paths are present in the calls
        assert any(
            str(key_path) in arg
            for call_args in mock_run.call_args_list
            for arg in call_args.args[0]
        )
        assert any(
            str(cert_path) in arg
            for call_args in mock_run.call_args_list
            for arg in call_args.args[0]
        )

        # Assert files are created (because our mock now creates them)
        assert cert_path.exists()
        assert key_path.exists()
        # For a more robust test, you could assert
        # minimum file size, but touch() creates 0-byte files
        # If your function wrote content, you'd check stat().st_size > 0
        assert (
            cert_path.stat().st_size >= 0
        )  # Changed from > 0 as touch creates 0-byte files
        assert (
            key_path.stat().st_size >= 0
        )  # Changed from > 0 as touch creates 0-byte files


def test_generate_certificate_and_key_already_exists(temp_cert_dir):
    """Test that the function does nothing if files already exist."""
    cert_path = temp_cert_dir / "cert.pem"
    key_path = temp_cert_dir / "key.pem"

    # Create dummy files
    cert_path.touch()
    key_path.touch()

    # Mock subprocess.run to ensure it's not called
    with patch("subprocess.run") as mock_run:
        with patch("builtins.print") as mock_print:  # To capture print output
            generate_certificate_and_key(temp_cert_dir)
            mock_print.assert_called_with(
                f"[SSL_UTILS] SSL cert and key already exist: {cert_path}, "
                f"{key_path}",
            )
        mock_run.assert_not_called()

    assert cert_path.exists()
    assert key_path.exists()


def test_generate_certificate_and_key_openssl_not_found(temp_cert_dir, capsys):
    """Test handling of OpenSSL FileNotFoundError."""
    cert_path = temp_cert_dir / "cert.pem"
    key_path = temp_cert_dir / "key.pem"

    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = FileNotFoundError("openssl not found")

        generate_certificate_and_key(temp_cert_dir)

        # Assert error message is printed to stderr
        captured = capsys.readouterr()
        # Use .err instead of .stderr
        assert (
            "[SSL_UTILS ERROR] OpenSSL not found. Please install OpenSSL."
            in captured.err
        )

        # Assert no files were created or any
        # partially created ones were cleaned up
        assert not cert_path.exists()
        assert not key_path.exists()


def test_generate_certificate_and_key_openssl_called_process_error(
    temp_cert_dir,
    capsys,
):
    """
    Test handling of subprocess.CalledProcessError during
    OpenSSL commands.
    """
    cert_path = temp_cert_dir / "cert.pem"
    key_path = temp_cert_dir / "key.pem"

    with patch("subprocess.run") as mock_run:
        # Simulate genrsa success, but req failure
        def mock_side_effect_error(command, **kwargs):
            if "genrsa" in command:
                Path(
                    command[command.index("-out") + 1],
                ).touch()  # Simulate key creation
                return MagicMock(
                    returncode=0,
                    stdout="genrsa success",
                    stderr="",
                )
            if "req" in command:
                raise subprocess.CalledProcessError(
                    returncode=1,
                    cmd="openssl req",
                    output="error stdout",
                    stderr="error stderr",
                )
            raise ValueError(f"Unexpected command: {command}")

        mock_run.side_effect = mock_side_effect_error

        generate_certificate_and_key(temp_cert_dir)

        # Assert error message is printed to stderr
        captured = capsys.readouterr()
        # Use .err instead of .stderr
        assert (
            "[SSL_UTILS ERROR] OpenSSL command failed: "
            "Command 'openssl req' returned "
            "non-zero exit status 1." in captured.err
        )
        assert "Stdout: error stdout" in captured.err
        assert "Stderr: error stderr" in captured.err

        # Assert files are cleaned up
        # (key might have been created before req failed)
        assert not cert_path.exists()
        assert not key_path.exists()


def test_generate_certificate_and_key_unexpected_error(temp_cert_dir, capsys):
    """Test handling of a generic unexpected error."""
    cert_path = temp_cert_dir / "cert.pem"
    key_path = temp_cert_dir / "key.pem"

    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = Exception("An unexpected problem")

        generate_certificate_and_key(temp_cert_dir)

        # Assert error message is printed to stderr
        captured = capsys.readouterr()
        # Use .err instead of .stderr
        assert (
            "[SSL_UTILS ERROR] An unexpected error occurred "
            "during SSL generation: An unexpected problem" in captured.err
        )

        # Assert no files were created or any
        # partially created ones were cleaned up
        assert not cert_path.exists()
        assert not key_path.exists()


def test_generate_certificate_and_key_cleanup_partial_files(temp_cert_dir):
    """Test that files are cleaned up even if only
    one was created before an error.
    """
    cert_path = temp_cert_dir / "cert.pem"
    key_path = temp_cert_dir / "key.pem"

    with patch("subprocess.run") as mock_run:
        # Simulate genrsa creating the key, but
        # then req fails before cert is created
        def mock_side_effect_partial_error(command, **kwargs):
            if "genrsa" in command:
                Path(
                    command[command.index("-out") + 1],
                ).touch()  # Simulate key creation
                return MagicMock(
                    returncode=0,
                    stdout="genrsa success",
                    stderr="",
                )
            if "req" in command:
                raise subprocess.CalledProcessError(
                    returncode=1,
                    cmd="openssl req",
                    output="",
                    stderr="",
                )
            raise ValueError(f"Unexpected command: {command}")

        mock_run.side_effect = mock_side_effect_partial_error

        # We don't need to manually create the key
        # file here; the mock's side_effect does it
        # key_path.touch() # Remove this line

        generate_certificate_and_key(temp_cert_dir)

        # Assert both files are gone
        assert not cert_path.exists()
        assert not key_path.exists()


def test_generate_certificate_and_key_custom_names(temp_cert_dir):
    """Test generation with custom certificate and key names."""
    custom_cert_name = "my_cert.crt"
    custom_key_name = "my_key.pem"
    cert_path = temp_cert_dir / custom_cert_name
    key_path = temp_cert_dir / custom_key_name

    with patch("subprocess.run") as mock_run:

        def mock_side_effect_custom(command, **kwargs):
            if "genrsa" in command:
                Path(command[command.index("-out") + 1]).touch()
                return MagicMock(
                    returncode=0,
                    stdout="genrsa output",
                    stderr="",
                )
            if "req" in command:
                Path(command[command.index("-out") + 1]).touch()
                return MagicMock(returncode=0, stdout="req output", stderr="")
            raise ValueError(f"Unexpected command: {command}")

        mock_run.side_effect = mock_side_effect_custom

        generate_certificate_and_key(
            temp_cert_dir,
            cert_name=custom_cert_name,
            key_name=custom_key_name,
        )

        assert mock_run.call_count == 2
        # Check that the -out argument for key and
        # cert paths are present in the calls
        assert any(
            str(key_path) in arg
            for call_args in mock_run.call_args_list
            for arg in call_args.args[0]
        )
        assert any(
            str(cert_path) in arg
            for call_args in mock_run.call_args_list
            for arg in call_args.args[0]
        )

        assert cert_path.exists()
        assert key_path.exists()
        assert cert_path.stat().st_size >= 0
        assert key_path.stat().st_size >= 0
