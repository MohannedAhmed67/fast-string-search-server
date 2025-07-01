"""Initialize the server's cache."""

import multiprocessing
from typing import Any

_global_manager: Any = None
# These will hold the *proxies* to the shared objects
_search_results_cache: Any


def setup_cache_manager() -> None:
    """Setup the global multiprocessing Manager and shared cache."""
    global _global_manager
    global _search_results_cache
    if _global_manager is None:  # Only initialize if not already initialized
        _global_manager = multiprocessing.Manager()
        _search_results_cache = _global_manager.dict()


def get_search_results_cache() -> Any:  # Using Any for value type
    """Get the shared search results cache (a Manager proxy)."""
    try:
        return _search_results_cache
    except NameError as e:
        raise RuntimeError(
            "Shared search results cache not initialized in this process.",
        ) from e


def clear_cache() -> None:
    """Clear all entries from the shared search results cache."""
    try:
        if _search_results_cache is not None:
            _search_results_cache.clear()
            print("Shared search results cache has been cleared.")
        else:
            print("Cache manager not set up, nothing to clear.")
    except NameError:
        print("Cache manager not set up, nothing to clear.")


def shutdown_cache_manager() -> None:
    """Shutdown the multiprocessing Manager."""
    global _global_manager
    if _global_manager is not None:
        _global_manager.shutdown()
        _global_manager = None
