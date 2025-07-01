"""Usage of the fastset.c in python."""

import ctypes
import subprocess
from pathlib import Path


class FastSet:
    """This is a class that allows to use the fastset.c in python."""

    def __init__(self) -> None:
        """Initialize the FastSet object.

        Set up file paths and preprocessing resources. It's also
        loading the associated shared library,
        and defining argument and return types for the C functions used.

        Attributes:
            so_file (Path): Path to the shared object (.so) file.
            c_file (Path): Path to the C source file.
            lib (ctypes.CDLL): Loaded shared library object.

        """
        self.so_file = self.c_file = Path()

        self.preprocess()

        self.lib = ctypes.CDLL(str(self.so_file))

        # Define arg types
        self.lib.load_file.argtypes = [ctypes.c_char_p]
        self.lib.exists.argtypes = [ctypes.c_char_p]
        self.lib.exists.restype = ctypes.c_int

    def load_file(self, path: Path) -> None:
        """Load the contents of a file into the underlying data structure.

        Args:
            path (Path): The path to the file to be loaded.

        Note:
            The file is expected to be in a format
            compatible with the underlying C library.

        """
        self.lib.load_file(str(path).encode("utf-8"))

    def exists(self, query: str) -> bool:
        """Check if a given query string exists in the underlying
        data structure.

        Args:
            query (str): The string to search for.

        Returns:
            bool: True if the query string exists, False otherwise.

        Raises:
            Any exception raised by the underlying library call.

        Note:
            The query string is encoded as UTF-8 before
            being passed to the underlying library.

        """
        return bool(self.lib.exists(query.encode("utf-8")))

    def preprocess(self) -> None:
        """Compiles the 'fastset.c' C source file into a shared object (.so)
        file for use with this module.

        Raises:
            subprocess.CalledProcessError:
            If the GCC compilation process fails.
            FileNotFoundError: If the GCC compiler is not found.
            OSError: If the compilation fails for other reasons.

        """
        base_dir = Path(__file__).parent
        self.c_file = base_dir / "fastset.c"
        self.so_file = base_dir / "libfastset.so"

        try:
            subprocess.run(
                [
                    "gcc",
                    "-fPIC",
                    "-shared",
                    "-o",
                    str(self.so_file),
                    str(self.c_file),
                ],
                check=True,
                capture_output=True,
                text=True,
                cwd=base_dir,
            )

        except subprocess.CalledProcessError as e:
            print("Compilation failed!")
            print("STDOUT:", e.stdout)
            print("STDERR:", e.stderr)
            raise
