"""Configuration parser for the server."""

from pathlib import Path
from typing import cast


class ConfigBoolParsingError(Exception):
    """Raised when the parsing of bool strings in
    the config file was not successful.
    """


class ConfigNotFoundError(Exception):
    """Raised when any of the configuration settings is not provided."""


class ServerConfig:
    """A class to save server configuration settings."""

    def __init__(
        self,
        linux_path: Path,
        reread_on_query: bool,
        port: int,
        use_ssl: bool,
    ) -> None:
        """Initialize the server configuration.

        Args:
            linux_path (Path): The path to the configuration
            file on the Linux server.
            reread_on_query (bool): Whether to re-read the file when queried.
            port (int): The port number the server will listen to.
            use_ssl (bool): Whether the server should use SSL.

        """
        self.linux_path = linux_path
        self.reread_on_query = reread_on_query
        self.port = port
        self.use_ssl = use_ssl

    def __repr__(self) -> str:
        """Return a string representation of the configuration object.

        Returns:
            str: A formatted string representing the configuration settings.

        """
        return f"""
                Server configuration settings:
                Linux path: {self.linux_path}
                Re-read on query: {"YES" if self.reread_on_query else "NO"}
                SSL enabled: {"YES" if self.use_ssl else "NO"}
                Used port number: {self.port}
            """


def parse_bool(key: str, val: str) -> bool:
    """Parse given values into boolean ones (True or False).

    Args:
        key (str): The key to parse the boolean for.
        val (str): The value to be parsed to boolean.

    Raises:
        ConfigBoolParsingError: If an error occured
        while parsing the value to boolean.

    Returns:
        bool: True or False depending on the output of the parser.

    """
    if val.strip().lower() in {"true", "1", "yes"}:
        return True
    if val.strip().lower() in {"false", "0", "no"}:
        return False

    raise ConfigBoolParsingError(
        f"Invalid boolean value for key '{key}' in the configuration file. "
        "Expected 'true', 'false', '1', '0', 'yes', or 'no' "
        "(case-insensitive).",
    )


def load_config_file(config_file_path: Path) -> ServerConfig:
    """Load and parse the configuration file.

    Args:
        config_file_path (Path): Path to the config file.

    Raises:
        ConfigNotFoundError: If required settings are missing or invalid.
        FileNotFoundError: If a file does not exist.

    Returns:
        ServerConfig: Parsed config object.

    """
    if not config_file_path.exists():
        raise FileNotFoundError(
            f"Missing required configuration file: '{config_file_path}'. "
            "Please ensure the file exists and the path is correct.",
        )

    # Initialize variables for required config values
    linux_path = reread_on_query = port = use_ssl = None

    # Open and read the configuration file line by line
    with config_file_path.open("r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()

            # Skip blank lines and comments
            if not line or line.startswith("#"):
                continue

            # Split the line into key and value
            key, sep, value = line.partition("=")
            if sep != "=":
                continue

            key = key.strip().lower()
            value = value.strip()

            # Parse and assign configuration values based on key
            if key == "linuxpath":
                linux_path = Path(value)
            elif key == "reread_on_query":
                reread_on_query = parse_bool("reread_on_query", value)
            elif key == "use_ssl":
                use_ssl = parse_bool("use_ssl", value)
            elif key == "port":
                port = int(value)

    # Collect required configuration values for validation
    required = {
        "linux_path": linux_path,
        "reread_on_query": reread_on_query,
        "port": port,
        "use_ssl": use_ssl,
    }

    # Check for missing required configuration values
    for key, val in required.items():
        if val is None:
            raise ConfigNotFoundError(
                f"Missing required configuration: '{key}'. "
                f"""Please ensure the config file includes a valid line for
                '{"linuxpath" if key == "linux_path" else key.upper()}'.""",
            )

    # Check if the linux_path file exists
    if linux_path is not None and not linux_path.exists():
        raise FileNotFoundError(
            f"The required file {linux_path} doesn't exist.",
        )

    # Return a ServerConfig object with the parsed values
    return ServerConfig(
        cast("Path", linux_path),
        cast("bool", reread_on_query),
        cast("int", port),
        cast("bool", use_ssl),
    )
