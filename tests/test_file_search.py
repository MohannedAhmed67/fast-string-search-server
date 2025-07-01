from pathlib import Path
from unittest.mock import patch

import pytest

from src.server.file_search import (
    binary_search,
    boyer_moore_search,
    hash_set,
    kmp_search,
    linear_search,
    memory_mapped_search,
    rabin_karp_search,
    shell_grep,
    trie_search,
)

# Test data
TEST_DATA = [
    "apple",
    "banana",
    "cherry",
    "date",
    "elderberry",
    "fig",
    "grape",
    "honeydew melon",
]


# Create a fixture for temporary file
@pytest.fixture
def test_file(tmp_path):
    file_path = tmp_path / "test_data.txt"
    with file_path.open("w") as f:
        for item in TEST_DATA:
            f.write(f"{item}\n")
    return file_path


# Test for file not found
def test_file_not_found():
    non_existent = Path("/non/existent/file.txt")
    for func in [
        linear_search,
        hash_set,
        memory_mapped_search,
        binary_search,
        shell_grep,
        trie_search,
        kmp_search,
        boyer_moore_search,
        rabin_karp_search,
    ]:
        with pytest.raises(FileNotFoundError):
            func(non_existent, "test")


# Test existing strings
@pytest.mark.parametrize("query", TEST_DATA)
def test_search_existing_string(test_file, query):
    for func in [
        linear_search,
        hash_set,
        memory_mapped_search,
        binary_search,
        shell_grep,
        trie_search,
        kmp_search,
        boyer_moore_search,
        rabin_karp_search,
    ]:
        assert func(test_file, query) is True


# Test non-existing strings
@pytest.mark.parametrize(
    "query",
    [
        "aple",
        "bannana",
        "cheery",
        "datte",
        "elderbery",
        "ffig",
        "grapes",
        "melon",
    ],
)
def test_search_non_existing_string(test_file, query):
    for func in [
        linear_search,
        hash_set,
        memory_mapped_search,
        binary_search,
        shell_grep,
        trie_search,
        kmp_search,
        boyer_moore_search,
        rabin_karp_search,
    ]:
        assert func(test_file, query) is False


# Test edge cases
@pytest.mark.parametrize(
    "query,expected",
    [
        ("", False),  # Empty string
        (" ", False),  # Whitespace
        ("\n", False),  # Newline only
        ("apple\n", False),  # String with newline
    ],
)
def test_edge_cases(test_file, query, expected):
    for func in [
        linear_search,
        hash_set,
        memory_mapped_search,
        binary_search,
        shell_grep,
        trie_search,
        kmp_search,
        boyer_moore_search,
        rabin_karp_search,
    ]:
        assert func(test_file, query) == expected


# Test empty file
def test_empty_file(tmp_path):
    empty_file = tmp_path / "empty.txt"
    empty_file.touch()

    for func in [
        linear_search,
        hash_set,
        memory_mapped_search,
        binary_search,
        shell_grep,
        trie_search,
        kmp_search,
        boyer_moore_search,
        rabin_karp_search,
    ]:
        assert func(empty_file, "test") is False


# Test with special characters
def test_special_characters(tmp_path):
    special_file = tmp_path / "special.txt"
    with special_file.open("w") as f:
        f.write("hello world\n")
        f.write("special@char.com\n")
        f.write("123!@#$%^&*()\n")
        f.write("line with spaces\n")

    test_cases = [
        ("hello world", True),
        ("special@char.com", True),
        ("123!@#$%^&*()", True),
        ("line with spaces", True),
        ("hello", False),  # Partial match
        ("char.com", False),  # Partial match
    ]

    for query, expected in test_cases:
        for func in [
            linear_search,
            hash_set,
            memory_mapped_search,
            binary_search,
            shell_grep,
            trie_search,
            kmp_search,
            boyer_moore_search,
            rabin_karp_search,
        ]:
            assert func(special_file, query) == expected


# Test shell_grep specifically
def test_shell_grep(test_file):
    # Test successful search
    assert shell_grep(test_file, "banana") is True

    # Test failed search
    assert shell_grep(test_file, "kiwi") is False

    # Test error handling
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = Exception("Mock error")
        with pytest.raises(Exception) as excinfo:
            shell_grep(test_file, "test")
        assert "Mock error" in str(excinfo.value)


# Test binary search with sorted requirement
def test_binary_search_unsorted(tmp_path):
    unsorted_file = tmp_path / "unsorted.txt"
    with unsorted_file.open("w") as f:
        f.write("zebra\n")
        f.write("apple\n")
        f.write("banana\n")

    # Should still work because binary_search sorts the list internally
    assert binary_search(unsorted_file, "apple") is True
    assert binary_search(unsorted_file, "zebra") is True
    assert binary_search(unsorted_file, "cherry") is False


# Test memory mapped search
def test_memory_mapped_search(test_file):
    assert memory_mapped_search(test_file, "cherry") is True
    assert memory_mapped_search(test_file, "mango") is False


# Test trie search
def test_trie_search(test_file):
    assert trie_search(test_file, "fig") is True
    assert trie_search(test_file, "kiwi") is False


# Test large file handling
def test_large_file(tmp_path):
    large_file = tmp_path / "large.txt"
    with large_file.open("w") as f:
        for i in range(10000):
            f.write(f"line_{i}\n")

    # Test beginning, middle, and end
    for func in [
        linear_search,
        hash_set,
        memory_mapped_search,
        binary_search,
        shell_grep,
        trie_search,
        kmp_search,
        boyer_moore_search,
        rabin_karp_search,
    ]:
        assert func(large_file, "line_0") is True
        assert func(large_file, "line_5000") is True
        assert func(large_file, "line_9999") is True
        assert func(large_file, "line_10000") is False
