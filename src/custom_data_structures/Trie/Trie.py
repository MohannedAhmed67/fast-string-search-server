"""This module represents the implementation of a Trie structure that's
used for fast checking for the existence of a string.
"""


class TrieNode:
    """Represent a node in the trie structure."""

    def __init__(self) -> None:
        """Initialize a new Trie node.

        Attributes:
            children (dict): A dictionary mapping characters to
            their corresponding child TrieNode instances.
            is_the_end_of_word (bool): Indicates whether this
            node marks the end of a valid word in the Trie.

        """
        # A dictionary to store child nodes (character: TrieNode)
        self.children: dict[str, TrieNode] = {}
        # Boolean flag to indicate if this node marks the end of a word
        self.is_the_end_of_word = False


class StringTrie:
    """Represents the string trie data structure."""

    def __init__(self) -> None:
        """Initialize the root node of the Trie."""
        self.root = TrieNode()

    def insert(self, word: str) -> None:
        """Insert a new word into the String Trie structure.

        Args:
            word (str): The word to be inserted into the Trie structure.

        """
        node = self.root
        for char in word:
            # If the character is not already a child, add a new TrieNode
            if char not in node.children:
                node.children[char] = TrieNode()
            # Move to the child node
            node = node.children[char]
        # Mark the end of the word
        node.is_the_end_of_word = True

    def search(self, word: str) -> bool:
        """Check for the existence of a given word in the String
        Trie structure.

        Args:
            word (str): The word to search for in the Trie structure.

        Returns:
            bool: True if the exact `word` is present
            in the trie as a complete word, False otherwise.

        """
        node = self.root
        for char in word:
            # If the character is not found, the word does not exist
            if char not in node.children:
                return False
            # Move to the child node
            node = node.children[char]
        # Return True only if the current node marks the end of a word
        return node.is_the_end_of_word
