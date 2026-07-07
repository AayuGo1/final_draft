"""Main Streamlit entry point for the Engineering Monitoring Dashboard.

Single-page industrial SCADA / Power BI style application: a horizontal
header, a global filter bar, a global KPI strip, a department tile grid
(primary navigation), the active department's content rendered directly
below the grid, and a minimal footer. The sidebar is limited to cache /
settings / about / debug controls.

No data discovery, parsing, or KPI calculation happens here. Everything
is sourced from ``dashboard_loader.load_dashboard_safe`` and the
dashboard dictionary built by ``dashboard_data.py``. No departments,
meters, or worksheet names are ever hardcoded.
"""

from __future__ import annotations

import datetime as dt

import streamlit as st

from config import (
    APP_ICON,
    APP_NAME,
    APP_VERSION,
    GITHUB_BRANCH,
    GITHUB_OWNER,
    GITHUB_REPO,
    PAGE_CONFIG,
    THEME_DANGER_COLOR,
    THEME_PRIMARY_COLOR,
    THEME_SUCCESS_COLOR,
)
from services.dashboard_loader import load_dashboard_safe
from pages import (
    home,
    engineering,
    utility,
    air_compressor,
    freon_refrigeration,
    ammonia_refrigeration,
)

DEPARTMENT_ICONS: tuple[str, ...] = (
    "🏭", "⚙️", "🧊", "❄️", "⚡", "🛠", "🔥", "💧", "🌞", "📦",
)
"""Cycled, generic icon set applied to discovered department tiles.

Purely decorative — never used to identify or hardcode a department.
"""

DEPARTMENT_NAME_TO_PAGE: dict[str, object] = {
    "utility": utility,
    "air compressor": air_compressor,
    "air": air_compressor,
    "compressor": air_compressor,
    "freon": freon_refrigeration,
    "freon refrigeration": freon_refrigeration,
    "ammonia": ammonia_refrigeration,
    "ammonia refrigeration": ammonia_refrigeration,
}
"""Best-effort keyword mapping from a discovered department label to its
page module. Anything unmatched falls back to the generic Engineering
page, which can filter itself by the selected department."""


def get_dashboard() -> tuple[dict | None, str | None]:
    """Load (once per session) and return the cached dashboard data.

    Returns:
        A tuple of ``(dashboard, error_message)``; exactly one is
        ``None``.
    """
    if "dashboard_data" not in st.session_state:
        dashboard, error = load_dashboard_safe()
        st.session_state["dashboard_data"] = dashboard
        st.session_state["dashboard_error"] = error
        st.session_state["last_refresh"] = dt.datetime.now()

    return st.session_state["dashboard_data"], st.session_state["dashboard_error"]


def refresh_dashboard() -> None:
    """Clear cached dashboard data so it is reloaded on next access."""
    for key in ("dashboard_data", "dashboard_error", "last_refresh"):
        st.session_state.pop(key, None)


def resolve_page_for_department(department_name: str) -> object:
    """Resolve the page module to render for a selected department.

    Args:
        department_name: The department label the user selected.

    Returns:
        The page module whose ``render()`` should populate the content
        area. Falls back to the generic Engineering page when no
        keyword matches.
    """
    normalized = department_name.strip().lower()

    for keyword, page_module in DEPARTMENT_NAME_TO_PAGE.items():
        if keyword in normalized:
            return page_module

    return engineering


def inject_global_styles() -> None:
    """Inject the dark industrial glassmorphism CSS theme."""
    st.markdown(
        f"""
        <style>
            #MainMenu {{visibility: hidden;}}
            footer {{visibility: hidden;}}
            header[data-testid="stHeader"] {{background: transparent;}}

            .block-container {{
                padding-top: 1.1rem;
                padding-bottom: 1.5rem;
                max-width: 1400px;
            }}

            .scada-header {{
                display: flex;
                align-items: center;
                justify-content: space-between;
                background: linear-gradient(135deg, rgba(108,99,255,0.12), rgba(22,26,37,0.85));
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 16px;
                padding: 16px 24px;
                backdrop-filter: blur(10px);
                box-shadow: 0 8px 24px rgba(0,0,0,0.35);
                margin-bottom: 12px;
                flex-wrap: wrap;
                gap: 12px;
            }}

            .scada-header-left {{
                display: flex;
                align-items: center;
                gap: 14px;
            }}

            .scada-logo {{
                width: 46px;
                height: 46px;
                border-radius: 12px;
                background: linear-gradient(135deg, {THEME_PRIMARY_COLOR}, #3f3aa3);
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 22px;
                box-shadow: 0 4px 14px rgba(108,99,255,0.4);
            }}

            .scada-title {{
                font-size: 1.15rem;
                font-weight: 700;
                letter-spacing: 0.3px;
                margin: 0;
            }}

            .scada-subtitle {{
                font-size: 0.75rem;
                opacity: 0.6;
                margin: 0;
            }}

            .scada-status-group {{
                display: flex;
                gap: 18px;
                flex-wrap: wrap;
                align-items: center;
                font-size: 0.78rem;
            }}

            .status-pill {{
                display: flex;
                align-items: center;
                gap: 6px;
                padding: 4px 10px;
                border-radius: 999px;
                background: rgba(255,255,255,0.05);
                border: 1px solid rgba(255,255,255,0.08);
                white-space: nowrap;
            }}

            .status-dot {{
                width: 8px;
                height: 8px;
                border-radius: 50%;
                display: inline-block;
            }}

            .glass-panel {{
                background: rgba(255,255,255,0.03);
                border: 1px solid rgba(255,255,255,0.07);
                border-radius: 14px;
                padding: 14px 18px;
                backdrop-filter: blur(6px);
                margin-bottom: 12px;
            }}

            .kpi-strip {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
                gap: 14px;
                margin-bottom: 14px;
            }}

            .kpi-card {{
                position: relative;
                border-radius: 16px;
                padding: 18px 20px;
                background: linear-gradient(145deg, rgba(108,99,255,0.16), rgba(22,26,37,0.9));
                border: 1px solid rgba(255,255,255,0.08);
                box-shadow: 0 6px 18px rgba(0,0,0,0.3);
                transition: transform 0.18s ease, box-shadow 0.18s ease;
                overflow: hidden;
            }}

            .kpi-card:hover {{
                transform: translateY(-3px);
                box-shadow: 0 10px 26px rgba(108,99,255,0.25);
            }}

            .kpi-icon {{
                font-size: 1.4rem;
                opacity: 0.85;
                margin-bottom: 6px;
            }}

            .kpi-value {{
                font-size: 1.55rem;
                font-weight: 700;
                margin: 0;
                line-height: 1.1;
            }}

            .kpi-label {{
                font-size: 0.78rem;
                opacity: 0.65;
                margin-top: 2px;
            }}

            .dept-grid-title {{
                font-size: 0.95rem;
                font-weight: 700;
                opacity: 0.85;
                margin: 6px 0 10px 2px;
                letter-spacing: 0.3px;
                text-transform: uppercase;
            }}

            div[data-testid="stButton"] > button {{
                width: 100%;
                border-radius: 14px !important;
                border: 1px solid rgba(255,255,255,0.08) !important;
                background: linear-gradient(145deg, rgba(255,255,255,0.04), rgba(22,26,37,0.85)) !important;
                padding: 14px 10px !important;
                font-weight: 600 !important;
                transition: transform 0.15s ease, border-color 0.15s ease, box-shadow 0.15s ease !important;
                box-shadow: 0 4px 12px rgba(0,0,0,0.25) !important;
            }}

            div[data-testid="stButton"] > button:hover {{
                transform: translateY(-2px);
                border-color: {THEME_PRIMARY_COLOR}66 !important;
                box-shadow: 0 8px 20px rgba(108,99,255,0.25) !important;
            }}

            .dept-tile-active > button {{
                border-color: {THEME_PRIMARY_COLOR} !important;
                background: linear-gradient(145deg, rgba(108,99,255,0.25), rgba(22,26,37,0.9)) !important;
            }}

            .content-panel {{
                background: rgba(255,255,255,0.02);
                border: 1px solid rgba(255,255,255,0.06);
                border-radius: 16px;
                padding: 18px 20px;
                margin-top: 4px;
            }}

            .scada-footer {{
                margin-top: 20px;
                padding: 12px 18px;
                border-radius: 12px;
                background: rgba(255,255,255,0.02);
                border: 1px solid rgba(255,255,255,0.06);
                font-size: 0.75rem;
                opacity: 0.55;
                text-align: center;
            }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header(dashboard: dict | None) -> None:
    """Render the horizontal SCADA-style header with live status pills."""
    now = dt.datetime.now()
    summary = (dashboard or {}).get("summary", {})
    available_sections = summary.get("available_sections", [])

    plant_ok = bool(available_sections)
    plant_color = THEME_SUCCESS_COLOR if plant_ok else THEME_DANGER_COLOR
    plant_text = "Online" if plant_ok else "No Data"

    workbook_ok = dashboard is not None
    workbook_color = THEME_SUCCESS_COLOR if workbook_ok else THEME_DANGER_COLOR
    workbook_text = "Loaded" if workbook_ok else "Load Failed"

    last_refresh = st.session_state.get("last_refresh", now)

    st.markdown(
        f"""
        <div class="scada-header">
            <div class="scada-header-left">
                <div class="scada-logo">{APP_ICON}</div>
                <div>
                    <p class="scada-title">{APP_NAME}</p>
                    <p class="scada-subtitle">Plant Monitoring &amp; Control · v{APP_VERSION}</p>
                </div>
            </div>
            <div class="scada-status-group">
                <div class="status-pill">
                    <span class="status-dot" style="background:{plant_color};"></span>
                    Plant: {plant_text}
                </div>
                <div class="status-pill">
                    <span class="status-dot" style="background:{workbook_color};"></span>
                    Workbook: {workbook_text}
                </div>
                <div class="status-pill">
                    <span class="status-dot" style="background:{THEME_SUCCESS_COLOR};"></span>
                    GitHub: {GITHUB_OWNER}/{GITHUB_REPO}@{GITHUB_BRANCH}
                </div>
                <div class="status-pill">📅 {now.strftime("%d %b %Y")}</div>
                <div class="status-pill">🕒 {now.strftime("%H:%M:%S")}</div>
                <div class="status-pill">🔁 {last_refresh.strftime("%H:%M:%S")}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    control_col1, control_col2, _ = st.columns([1.2, 1, 6])
    with control_col1:
        st.toggle("Auto Refresh", key="auto_refresh_enabled", value=False)
    with control_col2:
        if st.button("🔄 Refresh", use_container_width=True):
            refresh_dashboard()
            st.rerun()


def render_filter_bar(dashboard: dict) -> None:
    """Render the month / date / department search / department filter bar."""
    filters = dashboard.get("filters", {})
    months = filters.get("months", [])
    dates = filters.get("dates", [])
    departments = filters.get("departments", [])

    st.markdown('<div class="glass-panel">', unsafe_allow_html=True)
    col_month, col_date, col_search, col_dept = st.columns([1, 1, 1.4, 1.4])

    with col_month:
        if months:
            st.selectbox("Month", options=months, key="selected_month")
        else:
            st.selectbox("Month", options=["N/A"], disabled=True)

    with col_date:
        if dates:
            st.selectbox("Date", options=dates, key="selected_date")
        else:
            st.selectbox("Date", options=["N/A"], disabled=True)

    with col_search:
        st.text_input(
            "Search Department", key="department_search", placeholder="Type to filter…"
        )

    with col_dept:
        if departments:
            st.selectbox(
                "Jump to Department",
                options=["All"] + departments,
                key="department_filter",
            )
        else:
            st.selectbox("Jump to Department", options=["All"], disabled=True)

    st.markdown("</div>", unsafe_allow_html=True)


def render_kpi_strip(dashboard: dict) -> None:
    """Render premium global KPI cards sourced from the dashboard summary.

    Only real, backend-supplied operational metrics are shown. Developer
    metrics (rows, columns, sheet counts, available-section lists) are
    never displayed. A card is omitted entirely if its underlying value
    is not available rather than showing a fabricated placeholder.
    """
    summary = dashboard.get("summary", {})

    department_count = summary.get("department_count")
    meter_count = summary.get("meter_count")
    latest_timestamp = summary.get("latest_timestamp")
    data_availability = summary.get("data_availability")

    department_latest_values = summary.get("department_latest_values", {})
    meters_reporting = sum(
        sum(1 for value in meters.values() if value is not None)
        for meters in department_latest_values.values()
    )

    cards: list[tuple[str, str, str]] = []

    if department_count is not None:
        cards.append(("🏢", str(department_count), "Departments Monitored"))
    if meter_count is not None:
        cards.append(("📟", str(meter_count), "Meters Tracked"))
    if department_latest_values:
        cards.append(("📈", str(meters_reporting), "Meters Reporting"))
    if data_availability is not None:
        cards.append(("📊", f"{data_availability * 100:.0f}%", "Data Availability"))
    if latest_timestamp and latest_timestamp != "N/A":
        cards.append(("🕒", str(latest_timestamp), "Latest Reading"))

    if not cards:
        return

    cards_html = "".join(
        f"""
        <div class="kpi-card">
            <div class="kpi-icon">{icon}</div>
            <p class="kpi-value">{value}</p>
            <p class="kpi-label">{label}</p>
        </div>
        """
        for icon, value, label in cards
    )

    st.markdown(f'<div class="kpi-strip">{cards_html}</div>', unsafe_allow_html=True)


def render_department_grid(dashboard: dict) -> None:
    """Render the responsive department tile grid (primary navigation).

    Every tile name is sourced from ``dashboard["filters"]["departments"]``.
    Selecting a tile stores ``st.session_state["selected_department"]``
    without any page rerouting.
    """
    departments = dashboard.get("filters", {}).get("departments", [])
    search_term = st.session_state.get("department_search", "").strip().lower()

    visible_departments = (
        [d for d in departments if search_term in d.lower()]
        if search_term
        else departments
    )

    st.markdown('<p class="dept-grid-title">Departments</p>', unsafe_allow_html=True)

    if not departments:
        st.info("No departments were discovered in the current workbook.")
        return

    if not visible_departments:
        st.caption("No departments match your search.")
        return

    columns_per_row = 5
    selected_department = st.session_state.get("selected_department")

    for row_start in range(0, len(visible_departments), columns_per_row):
        row_departments = visible_departments[row_start : row_start + columns_per_row]
        columns = st.columns(columns_per_row)

        for column, department_name in zip(columns, row_departments):
            icon = DEPARTMENT_ICONS[
                departments.index(department_name) % len(DEPARTMENT_ICONS)
            ]
            is_active = department_name == selected_department

            with column:
                if is_active:
                    st.markdown('<div class="dept-tile-active">', unsafe_allow_html=True)

                if st.button(
                    f"{icon}\n\n{department_name}",
                    key=f"dept_tile_{department_name}",
                    use_container_width=True,
                ):
                    st.session_state["selected_department"] = department_name

                if is_active:
                    st.markdown("</div>", unsafe_allow_html=True)


def render_active_content() -> None:
    """Render exactly one existing page's content below the tile grid.

    Falls back to the Home page when no department has been selected.
    """
    selected_department = st.session_state.get("selected_department")

    st.markdown('<div class="content-panel">', unsafe_allow_html=True)

    if not selected_department:
        home.render()
    else:
        resolve_page_for_department(selected_department).render()

    st.markdown("</div>", unsafe_allow_html=True)


def render_sidebar() -> None:
    """Render a minimal sidebar: cache refresh, settings, about, debug."""
    with st.sidebar:
        st.markdown(f"### {APP_ICON} {APP_NAME}")
        st.caption(f"v{APP_VERSION}")
        st.divider()

        if st.button("🗑 Refresh Cache", use_container_width=True):
            refresh_dashboard()
            st.rerun()

        with st.expander("⚙ Settings", expanded=False):
            st.toggle("Compact Mode", key="compact_mode", value=False)

        with st.expander("ℹ About", expanded=False):
            st.write(
                "Industrial engineering monitoring dashboard sourced from a "
                "live workbook. Data is discovered dynamically — no "
                "departments, meters, or sheets are hardcoded."
            )

        with st.expander("🐞 Debug", expanded=False):
            st.write(
                {
                    "selected_department": st.session_state.get("selected_department"),
                    "selected_month": st.session_state.get("selected_month"),
                    "selected_date": st.session_state.get("selected_date"),
                    "last_refresh": str(st.session_state.get("last_refresh")),
                }
            )


def render_footer(dashboard: dict | None) -> None:
    """Render the footer: current workbook, last refresh, dashboard version."""
    last_refresh = st.session_state.get("last_refresh")
    last_refresh_text = (
        last_refresh.strftime("%d %b %Y, %H:%M:%S") if last_refresh else "N/A"
    )

    metadata = (dashboard or {}).get("metadata", {})
    sheet_names = metadata.get("sheet_names", [])
    workbook_text = sheet_names[0] if sheet_names else "N/A"

    st.markdown(
        f"""
        <div class="scada-footer">
            Workbook: {workbook_text} · Last Refresh: {last_refresh_text} ·
            {APP_NAME} v{APP_VERSION}
        </div>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    """Configure the page and render the unified SCADA-style application."""
    st.set_page_config(**PAGE_CONFIG)
    inject_global_styles()

    render_sidebar()

    dashboard, error = get_dashboard()

    render_header(dashboard)

    if error is not None or dashboard is None:
        st.error(error or "Dashboard data could not be loaded.")
        render_footer(dashboard)
        return

    render_filter_bar(dashboard)
    render_kpi_strip(dashboard)
    render_department_grid(dashboard)
    render_active_content()
    render_footer(dashboard)


if __name__ == "__main__":
    main()
