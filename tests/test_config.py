from pathlib import Path

import pytest

from src.server.config import (
    ConfigBoolParsingError,
    ConfigNotFoundError,
    ServerConfig,
    load_config_file,
    parse_bool,
)

# Test data for valid configurations
VALID_CONFIG = """
# Server configuration
linuxpath = {linux_path}
reread_on_query = true
port = 8888
use_ssl = yes
"""

MISSING_KEY_CONFIG = """
linuxpath = {linux_path}
port = 8888
use_ssl = false
"""

INVALID_BOOL_CONFIG = """
linuxpath = {linux_path}
reread_on_query = maybe
port = 8888
use_ssl = false
"""

INVALID_PORT_CONFIG = """
linuxpath = {linux_path}
reread_on_query = true
port = abc
use_ssl = false
"""


# Test parse_bool function
@pytest.mark.parametrize(
    "value, expected",
    [
        ("true", True),
        ("True", True),
        ("TRUE", True),
        ("1", True),
        ("yes", True),
        ("false", False),
        ("False", False),
        ("FALSE", False),
        ("0", False),
        ("no", False),
    ],
)
def test_parse_bool_valid(value, expected):
    """Test valid boolean values."""
    assert parse_bool("test_key", value) == expected


@pytest.mark.parametrize("value", ["maybe", "2", "yess", "tru", "invalid"])
def test_parse_bool_invalid(value):
    """Test invalid boolean values."""
    with pytest.raises(ConfigBoolParsingError) as excinfo:
        parse_bool("test_key", value)
    assert "Invalid boolean value for key 'test_key'" in str(excinfo.value)


# Test ServerConfig class
def test_server_config_initialization(tmp_path):
    """Test ServerConfig initialization and properties."""
    test_file = tmp_path / "test.txt"
    test_file.touch()

    config = ServerConfig(
        linux_path=test_file,
        reread_on_query=True,
        port=8888,
        use_ssl=False,
    )

    assert config.linux_path == test_file
    assert config.reread_on_query is True
    assert config.port == 8888
    assert config.use_ssl is False


def test_server_config_repr(tmp_path):
    """Test the string representation of ServerConfig."""
    test_file = tmp_path / "test.txt"
    test_file.touch()

    config = ServerConfig(
        linux_path=test_file,
        reread_on_query=True,
        port=8888,
        use_ssl=False,
    )

    repr_str = repr(config)
    assert "Server configuration settings" in repr_str
    assert str(test_file) in repr_str
    assert "Re-read on query: YES" in repr_str
    assert "SSL enabled: NO" in repr_str
    assert "Used port number: 8888" in repr_str


# Test load_config_file function
def test_load_valid_config(tmp_path):
    """Test loading a valid configuration file."""
    # Create test file that linuxpath will point to
    test_file = tmp_path / "data.txt"
    test_file.touch()

    # Create config file
    config_path = tmp_path / "config.txt"
    config_content = VALID_CONFIG.format(linux_path=test_file)
    config_path.write_text(config_content)

    config = load_config_file(config_path)

    assert config.linux_path == test_file
    assert config.reread_on_query is True
    assert config.port == 8888
    assert config.use_ssl is True


def test_load_config_missing_file():
    """Test loading a configuration from a non-existent file."""
    with pytest.raises(FileNotFoundError) as excinfo:
        load_config_file(Path("/non/existent/path"))
    assert "Missing required configuration file" in str(excinfo.value)


def test_load_config_missing_key(tmp_path):
    """Test configuration with a missing required key."""
    # Create test file that linuxpath will point to
    test_file = tmp_path / "data.txt"
    test_file.touch()

    # Create config file
    config_path = tmp_path / "config.txt"
    config_content = MISSING_KEY_CONFIG.format(linux_path=test_file)
    config_path.write_text(config_content)

    with pytest.raises(ConfigNotFoundError) as excinfo:
        load_config_file(config_path)
    assert (
        "Missing required configuration: "
        "'reread_on_query'" in str(excinfo.value)
    )


def test_load_config_invalid_bool(tmp_path):
    """Test configuration with an invalid boolean value."""
    # Create test file that linuxpath will point to
    test_file = tmp_path / "data.txt"
    test_file.touch()

    # Create config file
    config_path = tmp_path / "config.txt"
    config_content = INVALID_BOOL_CONFIG.format(linux_path=test_file)
    config_path.write_text(config_content)

    with pytest.raises(ConfigBoolParsingError) as excinfo:
        load_config_file(config_path)
    assert (
        "Invalid boolean value for key "
        "'reread_on_query'" in str(excinfo.value)
    )


def test_load_config_invalid_port(tmp_path):
    """Test configuration with an invalid port value."""
    # Create test file that linuxpath will point to
    test_file = tmp_path / "data.txt"
    test_file.touch()

    # Create config file
    config_path = tmp_path / "config.txt"
    config_content = INVALID_PORT_CONFIG.format(linux_path=test_file)
    config_path.write_text(config_content)

    with pytest.raises(ValueError):
        load_config_file(config_path)


def test_load_config_comments_ignored(tmp_path):
    """Test that comments and empty lines are ignored."""
    # Create test file that linuxpath will point to
    test_file = tmp_path / "commented.txt"
    test_file.touch()

    config_content = f"""
    # This is a comment
    linuxpath = {test_file}
    # Another comment
    reread_on_query = no
    port = 9999
    use_ssl = 1
    """

    config_path = tmp_path / "config.txt"
    config_path.write_text(config_content)

    config = load_config_file(config_path)

    assert config.linux_path == test_file
    assert config.reread_on_query is False
    assert config.port == 9999
    assert config.use_ssl is True


def test_load_config_case_insensitivity(tmp_path):
    """Test that keys are case-insensitive."""
    # Create test file that linuxpath will point to
    test_file = tmp_path / "case_insensitive.txt"
    test_file.touch()

    config_content = f"""
    LINUXPATH = {test_file}
    REREAD_ON_QUERY = 0
    PORT = 1234
    USE_SSL = false
    """

    config_path = tmp_path / "config.txt"
    config_path.write_text(config_content)

    config = load_config_file(config_path)

    assert config.linux_path == test_file
    assert config.reread_on_query is False
    assert config.port == 1234
    assert config.use_ssl is False


def test_load_config_whitespace_handling(tmp_path):
    """Test that whitespace around keys and values is handled correctly."""
    # Create test file that linuxpath will point to
    test_file = tmp_path / "whitespace.txt"
    test_file.touch()

    config_content = f"""
    linuxpath = {test_file}
    reread_on_query = 1
    port = 5432
    use_ssl = yes
    """

    config_path = tmp_path / "config.txt"
    config_path.write_text(config_content)

    config = load_config_file(config_path)

    assert config.linux_path == test_file
    assert config.reread_on_query is True
    assert config.port == 5432
    assert config.use_ssl is True


def test_load_config_missing_linuxpath_file(tmp_path):
    """Test that FileNotFoundError is raised if linuxpath doesn't exist."""
    non_existent = tmp_path / "non_existent.txt"

    config_content = f"""
    linuxpath = {non_existent}
    reread_on_query = true
    port = 8888
    use_ssl = false
    """

    config_path = tmp_path / "config.txt"
    config_path.write_text(config_content)

    with pytest.raises(FileNotFoundError) as excinfo:
        load_config_file(config_path)
    assert (
        f"The required file {non_existent} "
        "doesn't exist" in str(excinfo.value)
    )


def test_load_config_invalid_line_format(tmp_path):
    """Test that malformed lines are ignored."""
    # Create test file that linuxpath will point to
    test_file = tmp_path / "valid.txt"
    test_file.touch()

    config_content = f"""
    linuxpath = {test_file}
    invalid_line_without_equals
    reread_on_query = true
    another_invalid line
    port = 8888
    use_ssl = false
    """

    config_path = tmp_path / "config.txt"
    config_path.write_text(config_content)

    config = load_config_file(config_path)

    assert config.linux_path == test_file
    assert config.reread_on_query is True
    assert config.port == 8888
    assert config.use_ssl is False
