"""aisignoff: declare and check AI generation (G0-G3), human review (H0-H3) and AI review (A0-A3) per file."""
from importlib.metadata import PackageNotFoundError, version

# The version lives only in pyproject.toml; this reads it from the installed package.
try:
    __version__ = version("aisignoff")
except PackageNotFoundError:  # running from a source checkout that isn't installed
    __version__ = "0+unknown"
