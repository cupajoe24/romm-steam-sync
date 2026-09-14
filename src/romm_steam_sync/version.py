"""Application version information following Semantic Versioning (SemVer)."""

from typing import NamedTuple


class VersionInfo(NamedTuple):
    """Structured three-digit version representation.

    Attributes:
        major: Major release digit (breaking changes).
        minor: Minor release digit (new features / capabilities).
        bugfix: Bugfix release digit (patches / bug fixes).
    """

    major: int
    minor: int
    bugfix: int

    @property
    def patch(self) -> int:
        """Alias for bugfix release digit conforming to SemVer terminology."""
        return self.bugfix

    @property
    def version_string(self) -> str:
        """Return the formatted three-digit semantic version string (e.g. '0.1.0')."""
        return f"{self.major}.{self.minor}.{self.bugfix}"

    @property
    def display_version(self) -> str:
        """Return the version formatted with a 'v' prefix (e.g. 'v0.1.0')."""
        return f"v{self.version_string}"

    def __str__(self) -> str:
        """Return semantic version string."""
        return self.version_string


VERSION_INFO = VersionInfo(major=0, minor=1, bugfix=7)
__version__ = VERSION_INFO.version_string


def get_version() -> str:
    """Return the current application version string."""
    return __version__


def get_version_info() -> VersionInfo:
    """Return the structured VersionInfo tuple."""
    return VERSION_INFO
