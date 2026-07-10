"""spelunk-bench: a benchmark for code-retrieval tools.

Measures how well retrieval tools answer natural-language "where is X
implemented?" queries against real repositories, scored against hand-labeled
ground truth. See docs/DESIGN.md for the full design.
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("spelunk-bench")
except PackageNotFoundError:  # pragma: no cover - source checkout without install
    __version__ = "0.0.0+unknown"

__all__ = ["__version__"]
