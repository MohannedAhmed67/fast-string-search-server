"""Different file-searching algorithms to be used by the server
for benchmarking purposes and responding to clients' requests.
"""

import bisect
import mmap
import os
import subprocess
from pathlib import Path

from src.custom_data_structures.Trie.Trie import StringTrie


def linear_search(data_path: Path, query_string: str) -> bool:
    """Perform linear search on a file to search for a query string.

    This function performs a simple linear search on the file
    specified to check for the existence of the query string.

    Args:
        data_path (Path): The path of the data file to search in.
        query_string (str): The string provided by the client to search for.

    Raises:
        FileNotFoundError: If the file specified by `data_path` does not exist.
        Exception: If an error occurs while performing the search.

    Returns:
        bool: True if the query string exists
        in the data path. Otherwise, False.

    """
    try:
        # Open the file for reading with UTF-8 encoding
        with data_path.open("r", encoding="utf-8") as file:
            # Iterate through each line in the file
            for line in file:
                # Check if the stripped line matches the query string
                if line.strip() == query_string:
                    return True

        # If the loop completes without finding the string, notify the client
        return False

    except FileNotFoundError as e:
        # Raise an error if the file does not exist
        raise FileNotFoundError(f"File not found: {data_path}") from e

    except Exception as e:
        # Raise a generic exception for any other errors
        raise Exception(f"An error occurred: {e!s}") from e


def hash_set(data_path: Path, query_string: str) -> bool:
    """Map file lines to a hash table for efficient lookup.

    This function checks for the existence of query string using a hash table.

    Args:
        data_path (Path): The path of the data file to search in.
        query_string (str): The string provided by the client to search for.

    Raises:
        FileNotFoundError: If the file specified by `data_path` does not exist.
        Exception: If an error occurs while performing the search.

    Returns:
        bool: True if the query string exists
        in the data path. Otherwise, False.

    """
    try:
        # Open the file for reading with UTF-8 encoding
        with data_path.open("r", encoding="utf-8") as file:
            # Read all lines, strip whitespace,
            # and store them in a set for fast lookup
            lines = {line.strip() for line in file}

            # Check if the query string exists in the set of lines
            if query_string in lines:
                return True
            return False

    except FileNotFoundError as e:
        # Raise an error if the file does not exist
        raise FileNotFoundError(f"File not found: {data_path}") from e

    except Exception as e:
        # Raise a generic exception for any other errors
        raise Exception(f"An error occurred: {e!s}") from e


def memory_mapped_search(data_path: Path, query_string: str) -> bool:
    """Use memory mapping to search for a query string.

    This function opens the specified file in binary mode,
    memory-maps it for efficient access, and iterates
    through each line to check for an exact match
    with the provided query string.

    Args:
        data_path (Path): The path of the data file to search in.
        query_string (str): The string provided by the client to search for.

    Raises:
        FileNotFoundError: If the file specified by `data_path` does not exist.
        Exception: If an error occurs while performing the search.

    Returns:
        bool: True if the query string exists
        in the data path. Otherwise, False.

    """
    try:
        with data_path.open("rb") as file:
            # Check if the file is empty BEFORE attempting to mmap it
            if os.fstat(file.fileno()).st_size == 0:
                return False  # An empty file can't contain any string

            with mmap.mmap(file.fileno(), 0, access=mmap.ACCESS_READ) as mm:
                query_bytes = query_string.encode()

                for line in iter(mm.readline, b""):
                    if line.rstrip(b"\n\r") == query_bytes:
                        return True
                return False

    except FileNotFoundError as e:
        raise FileNotFoundError(f"File not found: {data_path}") from e

    except Exception as e:
        # Catch the specific ValueError for
        # empty files if it somehow slips through,
        # or other mmap-related errors.
        if "cannot mmap an empty file" in str(e):
            return False
        raise Exception(f"An error occurred: {e!s}") from e


def binary_search(data_path: Path, query_string: str) -> bool:
    """Perform a binary search on the list of the file lines after sorting it.

    This function sorts the lines of the file and then performs a binary search
    on the sorted list to check for the existence of the query string.

    Args:
        data_path (Path): The path of the data file to search in.
        query_string (str): The string provided by the client to search for.

    Raises:
        FileNotFoundError: If the file specified by `data_path` does not exist.
        Exception: If an error occurs while performing the search.

    Returns:
        bool: True if the query string exists
        in the data path. Otherwise, False.

    """
    try:
        # Open the file for reading with UTF-8 encoding
        with data_path.open("r", encoding="utf-8") as file:
            # Read all lines, strip whitespace, and sort them for binary search
            sorted_list_of_lines = sorted([line.strip() for line in file])
            # Use bisect_left to find the insertion point for the query string
            index = bisect.bisect_left(sorted_list_of_lines, query_string)

            # Check if the query string exists at the found index
            if (
                index < len(sorted_list_of_lines)
                and sorted_list_of_lines[index] == query_string
            ):
                return True
            return False

    except FileNotFoundError as e:
        # Raise an error if the file does not exist
        raise FileNotFoundError(f"File not found: {data_path}") from e

    except Exception as e:
        # Raise a generic exception for any other errors
        raise Exception(f"An error occurred: {e!s}") from e


def shell_grep(data_path: Path, query_string: str) -> bool:
    """Use the grep command with some defined flags.

    This function uses the grep command with some defined flags to check for
    the existence of a query string in the given data path.

    Args:
        data_path (Path): The path of the data file to search in.
        query_string (str): The string provided by the client to search for.

    Raises:
        FileNotFoundError: If the file specified by `data_path` does not exist.
        Exception: If an error occurs while performing the search.

    Returns:
        bool: True if the query string exists
        in the data path. Otherwise, False.

    """
    if not data_path.exists():
        raise FileNotFoundError(f"File not found: {data_path}")

    try:
        temp_query = query_string.rstrip("\n")

        if not temp_query and query_string:
            return False

        result = subprocess.run(
            ["grep", "-Fxq", temp_query, data_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )

        if query_string.endswith("\n") and result.returncode == 0:
            return False

        return result.returncode == 0

    except FileNotFoundError as e:
        raise FileNotFoundError(f"File not found: {data_path}") from e

    except Exception as e:
        raise Exception(f"An error occurred: {e!s}") from e


def trie_search(data_path: Path, query_string: str) -> bool:
    """Insert all the lines of the data file into a trie structure.

    This function inserts all the lines of the data file into a trie structure
    and then checks for the existence of the query string in the trie.

    Args:
        data_path (Path): The path of the data file to search in.
        query_string (str): The string provided by the client to search for.

    Raises:
        FileNotFoundError: If the file specified by `data_path` does not exist.
        Exception: If an error occurs while performing the search.

    Returns:
        bool: True if the query string exists in
        the data path. Otherwise, False.

    """
    # Initialize the trie structure
    data_trie = StringTrie()
    try:
        # Open the file for reading with UTF-8 encoding
        with data_path.open("r", encoding="utf-8") as file:
            # Iterate through each line in the file
            for line in file:
                # Insert each stripped line into the trie structure
                data_trie.insert(line.strip())

        # Check for the existence of the query string in the trie
        if data_trie.search(query_string):
            return True
        return False

    except FileNotFoundError as e:
        # Raise an error if the file does not exist
        raise FileNotFoundError(f"File not found: {data_path}") from e

    except Exception as e:
        # Raise a generic exception for any other errors
        raise Exception(f"An error occurred: {e!s}") from e


def kmp_search(data_path: Path, query_string: str) -> bool:
    """Perform a Knuth-Morris-Pratt (KMP) string search for whole lines.

    This function performs a Knuth-Morris-Pratt string search for whole lines.

    Args:
        data_path (Path): The path of the data file to search in.
        query_string (str): The string provided by the client to search for.

    Raises:
        FileNotFoundError: If the file specified by `data_path` does not exist.
        Exception: If an error occurs while performing the search.

    Returns:
        bool: True if the query string exists in
        the data path. Otherwise, False.

    """
    try:
        with data_path.open("r", encoding="utf-8") as file:
            for line in file:
                line = line.strip()
                # Only process lines of matching length
                if len(line) != len(query_string):
                    continue

                # Apply KMP to individual line
                pattern = query_string
                text = line
                pattern_length = len(pattern)
                text_length = len(text)

                # Build prefix table
                prefix_table = [0] * pattern_length
                j = 0
                for i in range(1, pattern_length):
                    if pattern[i] == pattern[j]:
                        j += 1
                        prefix_table[i] = j
                    elif j != 0:
                        j = prefix_table[j - 1]
                        i -= 1  # Stay at same position
                    else:
                        prefix_table[i] = 0

                # Perform KMP search
                i = j = 0
                while i < text_length:
                    if pattern[j] == text[i]:
                        i += 1
                        j += 1
                    if j == pattern_length:
                        return True
                    if i < text_length and pattern[j] != text[i]:
                        if j != 0:
                            j = prefix_table[j - 1]
                        else:
                            i += 1
            return False

    except FileNotFoundError as e:
        raise FileNotFoundError(f"File not found: {data_path}") from e

    except Exception as e:
        raise Exception(f"An error occurred: {e!s}") from e


def boyer_moore_search(data_path: Path, query_string: str) -> bool:
    """Perform a Boyer-Moore string search for whole lines.

    This function performs a Boyer-Moore string search for whole lines.

    Args:
        data_path (Path): The path of the data file to search in.
        query_string (str): The string provided by the client to search for.

    Raises:
        FileNotFoundError: If the file specified by `data_path` does not exist.
        Exception: If an error occurs while performing the search.

    Returns:
        bool: True if the query string exists in
        the data path. Otherwise, False.

    """
    try:
        with data_path.open("r", encoding="utf-8") as file:
            for line in file:
                line = line.strip()
                # Only process lines of matching length
                if len(line) != len(query_string):
                    continue

                # Apply Boyer-Moore to individual line
                pattern = query_string
                text = line
                pattern_length = len(pattern)
                text_length = len(text)

                if pattern_length == 0:
                    return False

                # Build skip table
                skip_table = {}
                for i in range(pattern_length - 1):
                    skip_table[pattern[i]] = pattern_length - i - 1

                # Perform search
                i = pattern_length - 1
                while i < text_length:
                    j = pattern_length - 1
                    k = i
                    while j >= 0 and text[k] == pattern[j]:
                        j -= 1
                        k -= 1
                    if j < 0:
                        return True
                    i += skip_table.get(text[i], pattern_length)
            return False

    except FileNotFoundError as e:
        raise FileNotFoundError(f"File not found: {data_path}") from e

    except Exception as e:
        raise Exception(f"An error occurred: {e!s}") from e


def rabin_karp_search(data_path: Path, query_string: str) -> bool:
    """Perform a Rabin-Karp string search for whole lines.

    This function performs a Rabin-Karp string search for whole lines.

    Args:
        data_path (Path): The path of the data file to search in.
        query_string (str): The string provided by the client to search for.

    Raises:
        FileNotFoundError: If the file specified by `data_path` does not exist.
        Exception: If an error occurs while performing the search.

    Returns:
        bool: True if the query string exists in
        the data path. Otherwise, False.

    """
    try:
        with data_path.open("r", encoding="utf-8") as file:
            pattern = query_string
            pattern_length = len(pattern)
            pattern_hash = hash(pattern)

            for line in file:
                line = line.strip()
                # Only process lines of matching length
                if len(line) != pattern_length:
                    continue

                # Apply Rabin-Karp to individual line
                text = line
                text_hash = hash(text)

                if pattern_hash == text_hash and pattern == text:
                    return True
            return False

    except FileNotFoundError as e:
        raise FileNotFoundError(f"File not found: {data_path}") from e

    except Exception as e:
        raise Exception(f"An error occurred: {e!s}") from e
