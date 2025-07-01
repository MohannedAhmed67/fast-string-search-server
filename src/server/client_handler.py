"""Handle client's request of searching about a query string."""

import logging
import os
import time
from pathlib import Path
from typing import Any, Callable, Union

from src.custom_data_structures.custom_chash.fastset import FastSet
from src.custom_data_structures.Trie.Trie import StringTrie

BufferType = Union[FastSet, set[Any], StringTrie]

SEARCH_FILE_PATH_GLOBAL = ""
GLOBAL_BUFFER: Any


def initialize_worker_process(data_path_str: str, shared_buffer: Any) -> None:
    """Initialize each worker process in the ProcessPoolExecutor.

    Args:
        data_path_str (str): The path to the search file.
        shared_buffer (Any): The shared buffer.

    """
    global SEARCH_FILE_PATH_GLOBAL, GLOBAL_BUFFER
    SEARCH_FILE_PATH_GLOBAL = data_path_str
    GLOBAL_BUFFER = shared_buffer
    logging.info(
        f"Worker process {os.getpid()} initialized with data_path: "
        f"{SEARCH_FILE_PATH_GLOBAL}",
    )


def check_buffer_sync(query: str) -> bool:
    """Check if a query string exists in the provided buffer.

    Args:
        query (str): The query string to check.

    Returns:
        bool: True if the query string exists in the buffer, False otherwise.

    """
    try:
        return query in GLOBAL_BUFFER.keys()
    except NameError:
        logging.exception("GLOBAL_BUFFER not initialized in worker process")
        return False


def perform_file_search_sync(
    search_file: Callable[[Path, str], bool],
    data_path: Path,
    query: str,
) -> str:
    """Perform a search for `query` in the file specified by
    `SEARCH_FILE_PATH_GLOBAL`.

    Args:
        search_file (Callable): The search function.
        data_path (Path): The path to the search file.
        query (str): The query string to check.

    Returns:
        str: The response string.

    """
    pid = os.getpid()
    logging.info(
        f"Process {pid}: Starting file search for '{query}' in "
        f"'{SEARCH_FILE_PATH_GLOBAL}'...",
    )

    start_time = time.perf_counter()
    found = False
    try:
        if not SEARCH_FILE_PATH_GLOBAL:
            logging.error(f"Process {pid}: Search file path not configured.")
            return "ERROR: Server file path not configured in worker."

        response = "STRING NOT FOUND"
        if search_file(data_path, query):
            response = "STIRNG EXISTS"

        end_time = time.perf_counter()
        duration = (end_time - start_time) * 1000  # in milliseconds
        logging.info(
            f"Process {pid}: Finished search for '{query}' in "
            f"{duration:.2f} ms. Found: {found}",
        )
        return response

    except FileNotFoundError:
        logging.exception(
            f"Process {pid}: File '{SEARCH_FILE_PATH_GLOBAL}' not found.",
        )
        return f"ERROR: Search file '{SEARCH_FILE_PATH_GLOBAL}' not found."

    except Exception as e:
        logging.critical(
            f"Process {pid}: Search failed due to unexpected error: {e}",
            exc_info=True,
        )
        return f"ERROR: Search failed due to an unexpected error: {e}"
