"""Central configuration for the Engineering Monitoring Dashboard.

This module is the single source of truth for application-wide constants:
identity, GitHub source location, caching behavior, theme values, and
Streamlit page configuration. No business logic, data loading, or parsing
should live here.
"""

from __future__ import annotations

# ==================================================
# APPLICATION IDENTITY
# ==================================================

APP_NAME: str = "Engineering Monitoring Dashboard"
"""Human-readable name of the application, used in page titles and headers."""

APP_ICON: str = "⚙️"
"""Emoji or icon used as the Streamlit page favicon."""

APP_VERSION: str = "1.0.0"
"""Current version of the dashboard application."""


# ==================================================
# GITHUB SOURCE CONFIGURATION
# ==================================================

GITHUB_OWNER: str = "aayugo1"
"""GitHub account or organization that owns the data repository."""

GITHUB_REPO: str = "final_draft"
"""Name of the GitHub repository containing the workbook."""

GITHUB_BRANCH: str = "main"
"""Branch of the repository to pull the workbook from."""

WORKBOOK_FILENAME: str = "Daily energy Monitoring.xlsx"
"""Filename of the Excel workbook, replaced monthly with new data."""


def build_raw_github_url(
    owner: str = GITHUB_OWNER,
    repo: str = GITHUB_REPO,
    branch: str = GITHUB_BRANCH,
    filename: str = WORKBOOK_FILENAME,
) -> str:
    """Build the raw GitHub content URL for the workbook.

    Args:
        owner: GitHub account or organization name.
        repo: Repository name.
        branch: Branch name to read the file from.
        filename: Name of the file within the repository.

    Returns:
        The fully qualified raw.githubusercontent.com URL for the file,
        with spaces percent-encoded for safe HTTP usage.
    """
    encoded_filename = filename.replace(" ", "%20")
    return (
        f"https://raw.githubusercontent.com/"
        f"{owner}/{repo}/{branch}/{encoded_filename}"
    )


WORKBOOK_RAW_URL: str = build_raw_github_url()
"""Precomputed raw GitHub URL for the default workbook configuration."""


# ==================================================
# CACHING
# ==================================================

CACHE_TTL_SECONDS: int = 3600
"""Time-to-live, in seconds, for cached workbook downloads and parsed data."""


# ==================================================
# THEME CONSTANTS
# ==================================================

THEME_PRIMARY_COLOR: str = "#6C63FF"
"""Primary accent color used across charts and UI highlights."""

THEME_BACKGROUND_COLOR: str = "#0E1117"
"""Main background color for the dashboard, supporting a dark theme."""

THEME_SECONDARY_BACKGROUND_COLOR: str = "#161A25"
"""Background color for cards, panels, and containers."""

THEME_TEXT_COLOR: str = "#FAFAFA"
"""Primary text color used throughout the dashboard."""

THEME_FONT: str = "sans serif"
"""Base font family for Streamlit-rendered text."""

THEME_SUCCESS_COLOR: str = "#2ECC71"
"""Color used to indicate positive or on-target KPI states."""

THEME_WARNING_COLOR: str = "#F5A623"
"""Color used to indicate cautionary or near-threshold KPI states."""

THEME_DANGER_COLOR: str = "#E74C3C"
"""Color used to indicate negative or off-target KPI states."""

THEME_CHART_PALETTE: list[str] = [
    "#6C63FF",
    "#2ECC71",
    "#F5A623",
    "#E74C3C",
    "#00BCD4",
    "#9B59B6",
    "#F39C12",
    "#1ABC9C",
]
"""Ordered color palette applied to multi-series charts for consistency."""


# ==================================================
# STREAMLIT PAGE CONFIGURATION
# ==================================================

PAGE_CONFIG: dict[str, object] = {
    "page_title": APP_NAME,
    "page_icon": APP_ICON,
    "layout": "wide",
    "initial_sidebar_state": "expanded",
}
"""Keyword arguments passed directly to ``st.set_page_config``."""
