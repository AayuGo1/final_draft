"""Central configuration for the Engineering Monitoring Dashboard."""
from __future__ import annotations

# ==================================================
# APPLICATION IDENTITY
# ==================================================
APP_NAME: str = "Engineering Monitoring Dashboard"
APP_ICON: str = "⚙️"
APP_VERSION: str = "1.0.0"

# ==================================================
# GITHUB SOURCE CONFIGURATION
# ==================================================
GITHUB_OWNER: str = "aayugo1"
GITHUB_REPO: str = "final_draft"
GITHUB_BRANCH: str = "main"
WORKBOOK_FILENAME: str = "Daily energy Monitoring.xlsx"

def build_raw_github_url(
    owner: str = GITHUB_OWNER,
    repo: str = GITHUB_REPO,
    branch: str = GITHUB_BRANCH,
    filename: str = WORKBOOK_FILENAME,
) -> str:
    encoded_filename = filename.replace(" ", "%20")
    return (
        f"https://raw.githubusercontent.com/"
        f"{owner}/{repo}/{branch}/{encoded_filename}"
    )

WORKBOOK_RAW_URL: str = build_raw_github_url()

# ==================================================
# CACHING
# ==================================================
CACHE_TTL_SECONDS: int = 3600

# ==================================================
# THEME CONSTANTS (Jubilant FoodWorks Light Theme)
# ==================================================
THEME_PRIMARY_COLOR: str = "#005DAA"
THEME_SECONDARY_COLOR: str = "#E31E24"
THEME_SUCCESS_COLOR: str = "#22C55E"
THEME_WARNING_COLOR: str = "#F59E0B"
THEME_DANGER_COLOR: str = "#E31E24"

THEME_BACKGROUND_COLOR: str = "#F9FAFB"
THEME_SECONDARY_BACKGROUND_COLOR: str = "#FFFFFF"
THEME_TEXT_COLOR: str = "#111827"
THEME_FONT: str = "Inter, sans-serif"

THEME_CHART_PALETTE: list[str] = [
    "#005DAA", "#E31E24", "#22C55E", "#F59E0B", "#8B5CF6", "#06B6D4", "#EC4899", "#84CC16"
]

# ==================================================
# STREAMLIT PAGE CONFIGURATION
# ==================================================
PAGE_CONFIG: dict[str, object] = {
    "page_title": APP_NAME,
    "page_icon": APP_ICON,
    "layout": "wide",
    "initial_sidebar_state": "expanded",
}
