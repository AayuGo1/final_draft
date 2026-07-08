"""Main Entry Point for the Engineering Monitoring Dashboard.

This module serves as the production presentation and UI/UX orchestration layer
for the Engineering Monitoring Dashboard. It interfaces directly with validated
domain logic services to render an enterprise dark SCADA interface.
"""

from __future__ import annotations

import datetime as dt
from typing import Any, Final

import pandas as pd
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
import services.chart_service as chart_service
from services.dashboard_loader import load_dashboard_safe
from dashboard_data import select_representative_meter

st.set_page_config(
    page_title=PAGE_CONFIG.get("page_title", APP_NAME),
    page_icon=PAGE_CONFIG.get("page_icon", "⚙️"),
    layout="wide",
    initial_sidebar_state="collapsed",
)

CRITICAL_SYSTEMS = [
    "NPCL", "DG", "GG", "Air compressor", "Traywasher",
    "Freon Refrigeration", "Ammonia Refrigeration",
]

# ------------------------------------------------------------------
# Color system — grouped by engineering discipline, applied
# consistently across cards, panel strips, and badges.
# ------------------------------------------------------------------
COLOR_ELECTRICAL = "#3B82F6"      # blue
COLOR_COMPRESSED_AIR = "#06B6D4"  # cyan
COLOR_COOLING = "#8B5CF6"         # purple
COLOR_FUEL = "#F59E0B"            # orange
COLOR_WATER = "#14B8A6"           # teal
COLOR_PRODUCTION = "#10B981"      # green

# accent = tile/border/panel-strip color, category = equipment class label
DEPT_CONFIGS = {
    "NPCL": {"accent": COLOR_ELECTRICAL, "category": "Electrical / Incoming Power"},
    "DG": {"accent": COLOR_FUEL, "category": "Fuel / Diesel Generation"},
    "GG": {"accent": COLOR_FUEL, "category": "Fuel / Gas Generation"},
    "Air compressor": {"accent": COLOR_COMPRESSED_AIR, "category": "Compressed Air"},
    "Freon Refrigeration": {"accent": COLOR_COOLING, "category": "Cooling System"},
    "Ammonia Refrigeration": {"accent": COLOR_COOLING, "category": "Cooling System"},
    "Traywasher": {"accent": COLOR_WATER, "category": "Sanitation / Water"},
    "Dough": {"accent": COLOR_PRODUCTION, "category": "Processing"},
    "Bread": {"accent": COLOR_PRODUCTION, "category": "Baking"},
    "Donut": {"accent": COLOR_PRODUCTION, "category": "Production"},
    "CLC": {"accent": COLOR_ELECTRICAL, "category": "Control Logic"},
    "Warehouse": {"accent": COLOR_ELECTRICAL, "category": "Storage / Utility"},
    "Transport": {"accent": COLOR_COMPRESSED_AIR, "category": "Logistics"},
    "Engineering": {"accent": COLOR_PRODUCTION, "category": "Workshop"},
    "Utility": {"accent": COLOR_WATER, "category": "Utilities"},
}
DEFAULT_CONFIG = {"accent": COLOR_COOLING, "category": "Engineering System"}


# ==================================================================
# Data access (untouched logic, only cached in session_state)
# ==================================================================

def get_dashboard() -> tuple[dict[str, Any] | None, str | None]:
    if "dashboard_data" not in st.session_state:
        dashboard, error = load_dashboard_safe()
        st.session_state["dashboard_data"] = dashboard
        st.session_state["dashboard_error"] = error
        st.session_state["last_refresh"] = dt.datetime.now()
    return st.session_state.get("dashboard_data"), st.session_state.get("dashboard_error")


def refresh_dashboard() -> None:
    st.cache_data.clear()
    st.cache_resource.clear()
    for key in ("dashboard_data", "dashboard_error", "last_refresh"):
        st.session_state.pop(key, None)


def get_gauge_max(df_block: pd.DataFrame, rep_m: str, dept_obj: dict[str, Any]) -> float:
    if rep_m and rep_m in df_block.columns:
        numeric_series = pd.to_numeric(df_block[rep_m], errors="coerce").dropna()
        if len(numeric_series) >= 5:
            return float(numeric_series.quantile(0.95)) * 1.15
        elif not numeric_series.empty:
            return float(numeric_series.max()) * 1.15

    total_val = dept_obj.get("total_values", {}).get(rep_m, 500.0) or 500.0
    avg_val = dept_obj.get("average_values", {}).get(rep_m, 100.0) or 100.0
    latest_val = dept_obj.get("latest_values", {}).get(rep_m, 0.0) or 0.0

    for potential_max in (total_val, avg_val, latest_val):
        if isinstance(potential_max, (int, float)) and potential_max > 0:
            return float(potential_max) * 1.15
    return 100.0


def compute_trend_chip(df_block: pd.DataFrame, rep_m: str | None) -> tuple[str, str] | None:
    """Pure display computation: % change of the representative meter's last
    two numeric observations in its already-extracted dataframe. Does not
    touch representative-meter selection, gauge scaling, or KPI calc logic —
    it only reads the same column those functions already read.
    Returns (arrow_symbol, formatted_pct) or None if not computable.
    """
    if not rep_m or not isinstance(df_block, pd.DataFrame) or rep_m not in df_block.columns:
        return None
    series = pd.to_numeric(df_block[rep_m], errors="coerce").dropna()
    if len(series) < 2:
        return None
    prev, curr = series.iloc[-2], series.iloc[-1]
    if prev == 0:
        return None
    pct = ((curr - prev) / abs(prev)) * 100
    arrow = "▲" if pct > 0 else ("▼" if pct < 0 else "▬")
    return arrow, f"{abs(pct):.1f}%"


# ==================================================================
# Styles — industrial SCADA theme, 8px grid
# ==================================================================

def inject_global_styles() -> None:
    st.markdown(
        f"""
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;600;700&display=swap');

            #MainMenu {{visibility: hidden;}}
            footer {{visibility: hidden;}}
            header[data-testid="stHeader"] {{background: transparent;}}
            .stApp {{ background: #0A0C10 !important; font-family: 'Inter', -apple-system, sans-serif; }}
            .block-container {{ padding-top: 8px; padding-bottom: 16px; max-width: 1680px; }}

            * {{ box-sizing: border-box; }}
            .tnum {{ font-family: 'JetBrains Mono', 'Inter', monospace; font-variant-numeric: tabular-nums; }}

            /* ---------- Header ---------- */
            .scada-header {{
                display: flex; justify-content: space-between; align-items: center;
                background: linear-gradient(180deg, #12151C 0%, #0F1218 100%);
                border: 1px solid #1C212B;
                padding: 9px 16px; margin-bottom: 10px; border-radius: 3px;
                box-shadow: 0 1px 0 rgba(255,255,255,0.02) inset;
            }}
            .header-left {{ display: flex; align-items: center; gap: 11px; }}
            .app-logo {{
                width: 27px; height: 27px; background: #171B24; border: 1px solid #2A3140;
                border-radius: 3px; display: flex; align-items: center; justify-content: center; font-size: 13px;
            }}
            .app-title {{ font-size: 13.5px; font-weight: 800; color: #E5E9F0; letter-spacing: 0.9px; text-transform: uppercase; }}
            .app-version {{ font-size: 9px; color: #4B5563; font-weight: 700; margin-left: 7px; }}

            .header-status-group {{ display: flex; align-items: stretch; gap: 0; border-left: 1px solid #1C212B; }}
            .header-stat {{
                display: flex; flex-direction: column; align-items: flex-start; justify-content: center; gap: 2px;
                padding: 2px 16px; border-right: 1px solid #1C212B;
            }}
            .header-stat:last-child {{ border-right: none; }}
            .header-stat-label {{ font-size: 8px; font-weight: 700; color: #4B5563; text-transform: uppercase; letter-spacing: 1px; }}
            .header-stat-value {{ display: flex; align-items: center; gap: 5px; font-size: 11px; font-weight: 600; color: #D1D5DB; font-variant-numeric: tabular-nums; }}
            .status-dot {{ width: 6px; height: 6px; border-radius: 1px; flex-shrink: 0; box-shadow: 0 0 4px currentColor; }}

            /* ---------- Section headers ---------- */
            .section-title {{
                font-size: 10px; font-weight: 800; color: #566072; text-transform: uppercase;
                letter-spacing: 1.4px; margin-bottom: 9px; margin-top: 20px;
                display: flex; align-items: center; gap: 8px;
            }}
            .section-title::before {{ content: ""; width: 3px; height: 10px; background: #3B82F6; border-radius: 1px; }}
            .section-title::after {{ content: ""; flex: 1; height: 1px; background: #1C212B; }}

            .subsection-label {{
                font-size: 9px; font-weight: 800; color: #4B5563; text-transform: uppercase;
                letter-spacing: 1px; margin: 14px 2px 7px 2px;
                display: flex; align-items: center; gap: 6px;
            }}
            .subsection-label::before {{ content: ""; width: 2px; height: 8px; background: #333B4A; border-radius: 1px; }}

            /* ---------- Executive tiles (premium KPI cards) ---------- */
            .exec-grid {{ display: grid; grid-template-columns: repeat(7, 1fr); gap: 7px; }}
            .exec-tile {{
                background: linear-gradient(180deg, #12151C 0%, #0E1015 100%);
                border: 1px solid #1C212B; border-top: 2px solid var(--accent, #3B82F6);
                border-radius: 4px; padding: 10px 11px 9px 11px; min-height: 78px;
                display: flex; flex-direction: column; justify-content: space-between;
                transition: transform 0.15s ease, border-color 0.15s ease, box-shadow 0.15s ease;
            }}
            .exec-tile:hover {{
                transform: translateY(-2px);
                box-shadow: 0 6px 16px rgba(0,0,0,0.4);
                border-color: var(--accent, #3B82F6);
            }}
            .exec-tile-top {{ display: flex; justify-content: space-between; align-items: flex-start; }}
            .exec-name {{ font-size: 10px; font-weight: 800; color: #D1D5DB; text-transform: uppercase; letter-spacing: 0.5px; }}
            .exec-label {{ font-size: 8px; color: #566072; font-weight: 700; text-transform: uppercase; letter-spacing: 0.7px; margin-top: 2px; }}
            .exec-value-row {{ display: flex; align-items: baseline; justify-content: space-between; margin-top: 6px; }}
            .exec-value {{ font-size: 17px; font-weight: 700; color: #F3F4F6; font-variant-numeric: tabular-nums; font-family: 'JetBrains Mono', monospace; }}
            .exec-unit {{ font-size: 9px; color: #6B7280; font-weight: 500; margin-left: 3px; font-family: 'Inter', sans-serif; }}
            .exec-bottom-row {{ display: flex; align-items: center; justify-content: space-between; margin-top: 6px; padding-top: 6px; border-top: 1px solid #171B24; }}
            .exec-status {{ font-size: 8px; font-weight: 800; text-transform: uppercase; letter-spacing: 0.7px; }}
            .status-online {{ color: #10B981; }}
            .status-offline {{ color: #EF4444; }}
            .trend-chip {{ font-size: 9px; font-weight: 700; padding: 1px 6px; border-radius: 8px; font-family: 'JetBrains Mono', monospace; }}
            .trend-up {{ color: #10B981; background: rgba(16,185,129,0.1); }}
            .trend-down {{ color: #EF4444; background: rgba(239,68,68,0.1); }}
            .trend-flat {{ color: #6B7280; background: rgba(107,114,128,0.1); }}

            /* ---------- Operations console (row-based) ---------- */
            .ops-console {{
                background: #10131A; border: 1px solid #1C212B; border-radius: 4px; overflow: hidden;
            }}
            .console-row {{
                display: grid; grid-template-columns: 1.6fr 1fr 1fr 1fr 0.9fr;
                align-items: center; padding: 5px 15px; border-bottom: 1px solid #15181F;
                transition: background 0.12s ease;
            }}
            .console-row:last-child {{ border-bottom: none; }}
            .console-row-head {{ background: #14171F; padding: 8px 15px; }}
            .console-row-head .console-col {{
                font-size: 8.5px; font-weight: 800; color: #566072; text-transform: uppercase; letter-spacing: 0.7px;
            }}
            .console-row-alt {{ background: #0D0F14; }}
            .console-row:not(.console-row-head):hover {{ background: #1A1F29; }}
            .console-col-name {{ font-size: 11px; font-weight: 700; color: #F3F4F6; letter-spacing: 0.2px; }}
            .console-col-num {{ font-size: 10.5px; font-variant-numeric: tabular-nums; font-family: 'JetBrains Mono', monospace; }}
            .console-col-status {{ font-size: 9.5px; font-weight: 800; letter-spacing: 0.4px; }}
            .ops-val {{ color: #F3F4F6; font-weight: 700; }}
            .ops-unit {{ color: #566072; font-size: 9px; margin-left: 2px; font-family: 'Inter', sans-serif; }}

            /* ---------- Alarm ribbon ---------- */
            .alarm-ribbon {{
                display: flex; align-items: center; gap: 8px;
                background: linear-gradient(90deg, rgba(255,255,255,0.015), transparent);
                border: 1px solid #1C212B; border-left: 3px solid var(--alarm-color, #10B981);
                border-radius: 3px; padding: 8px 15px; margin-bottom: 11px;
                font-size: 10.5px; font-weight: 600; color: #D1D5DB; letter-spacing: 0.2px;
            }}
            .alarm-dot {{ width: 7px; height: 7px; border-radius: 50%; background: var(--alarm-color, #10B981); flex-shrink: 0; box-shadow: 0 0 6px var(--alarm-color, #10B981); }}
            .alarm-label {{ font-size: 8px; font-weight: 800; color: #566072; text-transform: uppercase; letter-spacing: 1px; margin-right: 4px; }}

            /* ---------- Process selector: clickable equipment cards ---------- */
            div[data-testid="column"] {{ transition: transform 0.15s ease; }}
            div[data-testid="column"]:has(button[kind="secondary"]):hover {{ transform: translateY(-2px); cursor: pointer; }}
            div[data-testid="column"]:has(button[kind="secondary"]):hover .equip-card {{
                border-color: var(--accent, #8B5CF6);
                box-shadow: 0 6px 16px rgba(0,0,0,0.45), 0 0 0 1px var(--accent, #8B5CF6) inset;
            }}

            .equip-card {{
                background: linear-gradient(180deg, #12151C 0%, #0E1015 100%);
                border: 1px solid #1C212B; border-radius: 4px;
                padding: 12px 14px 10px 14px; border-top: 2px solid var(--accent, #8B5CF6);
                transition: border-color 0.15s ease, box-shadow 0.15s ease, transform 0.15s ease;
                position: relative;
            }}
            .equip-card.active {{
                background: #14171F; border-color: var(--accent, #8B5CF6);
                box-shadow: 0 0 0 1px var(--accent, #8B5CF6) inset, 0 4px 14px rgba(0,0,0,0.4);
                animation: cardSelectPulse 0.35s ease;
            }}
            @keyframes cardSelectPulse {{
                0% {{ transform: scale(0.97); }}
                60% {{ transform: scale(1.01); }}
                100% {{ transform: scale(1); }}
            }}
            .equip-header {{ display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px; }}
            .equip-name {{ font-size: 12px; font-weight: 800; color: #F3F4F6; letter-spacing: 0.1px; }}
            .equip-category {{ font-size: 8.5px; color: #566072; text-transform: uppercase; letter-spacing: 0.5px; margin-top: 2px; }}
            .equip-live-dot {{ width: 6px; height: 6px; border-radius: 50%; margin-top: 3px; }}
            .equip-metrics {{ display: flex; flex-direction: column; gap: 4px; margin: 8px 0 9px 0; padding-top: 8px; border-top: 1px solid #171B24; }}
            .equip-metric-row {{ display: flex; justify-content: space-between; font-size: 9.5px; color: #8B93A3; }}
            .equip-metric-row span:last-child {{ color: #D1D5DB; font-weight: 700; font-variant-numeric: tabular-nums; font-family: 'JetBrains Mono', monospace; }}
            .equip-activate {{
                display: flex; justify-content: space-between; align-items: center;
                font-size: 8.5px; font-weight: 800; letter-spacing: 0.8px; text-transform: uppercase;
                color: var(--accent, #8B5CF6); padding-top: 7px; margin-top: 2px; border-top: 1px dashed #1C212B;
            }}

            div[data-testid="stButton"] {{ margin-top: -34px; position: relative; z-index: 5; }}
            div[data-testid="stButton"] > button {{
                background: transparent !important; border: none !important; padding: 0 !important;
                width: 100%; height: 30px; text-align: left; color: transparent !important;
                box-shadow: none !important;
            }}
            div[data-testid="stButton"] > button:focus {{ box-shadow: none !important; }}

            /* ---------- KPI strip (workspace) ---------- */
            .kpi-strip {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 7px; margin-bottom: 10px; }}
            .kpi-cell {{
                background: #0D0F14; border: 1px solid #171B24; border-left: 2px solid var(--accent, #3B82F6);
                border-radius: 3px; padding: 9px 13px;
            }}
            .kpi-cell-label {{ font-size: 8px; font-weight: 800; color: #566072; text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 5px; }}
            .kpi-cell-value {{ font-size: 18px; font-weight: 700; color: #F3F4F6; font-family: 'JetBrains Mono', monospace; }}
            .kpi-cell-unit {{ font-size: 9.5px; color: #6B7280; margin-left: 3px; font-family: 'Inter', sans-serif; }}

            /* ---------- Workspace / control room ---------- */
            .workspace {{
                background: #10131A; border: 1px solid #1C212B; border-radius: 4px; padding: 13px;
                border-top: 2px solid var(--accent, #3B82F6); margin-bottom: 11px;
            }}
            .workspace-header {{ display: flex; justify-content: space-between; align-items: baseline; padding: 4px 6px 11px 6px; border-bottom: 1px solid #171B24; margin-bottom: 11px; }}
            .workspace-title {{ font-size: 15px; font-weight: 800; color: #F3F4F6; margin: 0; letter-spacing: 0.3px; }}
            .workspace-label {{ font-size: 9px; color: #6B7280; text-transform: uppercase; letter-spacing: 0.7px; font-weight: 700; }}

            /* ---------- Professional chart panels ---------- */
            .chart-panel {{
                background: #0A0C10; border: 1px solid #171B24; border-left: 2px solid var(--accent, #3B82F6);
                border-radius: 4px; padding: 10px 11px; margin-bottom: 7px;
                transition: box-shadow 0.15s ease, border-color 0.15s ease;
            }}
            .chart-panel:hover {{ border-color: #262C38; box-shadow: 0 5px 16px rgba(0,0,0,0.38); }}
            .chart-panel-head {{ display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 5px; }}
            .chart-panel-title {{ font-size: 9.5px; font-weight: 800; color: #C6CBD3; text-transform: uppercase; letter-spacing: 0.7px; }}
            .chart-panel-subtitle {{ font-size: 8.5px; color: #566072; font-weight: 500; margin-top: 2px; }}
            .chart-panel-time {{ font-size: 8px; color: #3A4150; font-weight: 600; font-family: 'JetBrains Mono', monospace; white-space: nowrap; }}

            /* ---------- Tabs ---------- */
            div[data-testid="stTabs"] button[data-baseweb="tab"] {{
                font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.6px;
                color: #6B7280; padding: 6px 14px;
            }}
            div[data-testid="stTabs"] button[aria-selected="true"] {{ color: #F3F4F6 !important; }}
            div[data-testid="stTabs"] {{ margin-bottom: 4px; }}

            /* ---------- DataFrames (registers) ---------- */
            div[data-testid="stDataFrame"] {{
                border: 1px solid #1C212B !important; border-radius: 4px !important; overflow: hidden !important;
            }}
            div[data-testid="stDataFrame"] th {{
                background: #14171F !important; color: #566072 !important; font-weight: 800 !important;
                text-transform: uppercase !important; font-size: 9px !important; letter-spacing: 0.7px !important;
                border-bottom: 1px solid #262C38 !important; padding: 5px 8px !important;
            }}
            div[data-testid="stDataFrame"] td {{
                background: #10131A !important; color: #C6CBD3 !important; border-bottom: 1px solid #171B24 !important;
                padding: 4px 8px !important; font-size: 10.5px !important; font-variant-numeric: tabular-nums;
                font-family: 'JetBrains Mono', monospace !important;
            }}
            div[data-testid="stDataFrame"] tr:hover td {{ background: #1A1F29 !important; }}

            /* ---------- Footer ---------- */
            .app-footer {{
                margin-top: 20px; padding: 8px 16px; border-radius: 3px; background: #10131A;
                border: 1px solid #1C212B; font-size: 9px; color: #4B5563; text-align: center;
                letter-spacing: 0.4px; font-family: 'JetBrains Mono', monospace;
            }}

            ::-webkit-scrollbar {{ width: 6px; height: 6px; }}
            ::-webkit-scrollbar-track {{ background: #0A0C10; }}
            ::-webkit-scrollbar-thumb {{ background: #262C38; border-radius: 3px; }}
        </style>""",
        unsafe_allow_html=True,
    )


# ==================================================================
# Header
# ==================================================================

def render_header(dashboard: dict[str, Any] | None) -> None:
    now = dt.datetime.now()
    departments = (dashboard or {}).get("departments", {})
    last_refresh = st.session_state.get("last_refresh")

    plant_ok = bool(departments)
    plant_color = THEME_SUCCESS_COLOR if plant_ok else THEME_DANGER_COLOR
    plant_text = "ONLINE" if plant_ok else "OFFLINE"

    wb_ok = dashboard is not None
    wb_color = THEME_SUCCESS_COLOR if wb_ok else THEME_DANGER_COLOR
    wb_text = "LINKED" if wb_ok else "UNLINKED"

    gh_ok = dashboard is not None
    gh_color = THEME_SUCCESS_COLOR if gh_ok else THEME_DANGER_COLOR
    gh_text = "SYNCED" if gh_ok else "ERROR"

    refresh_str = last_refresh.strftime("%H:%M:%S") if last_refresh else "—"

    st.markdown(
        f"""
    <div class="scada-header">
        <div class="header-left">
            <div class="app-logo">{APP_ICON}</div>
            <div><span class="app-title">{APP_NAME}</span><span class="app-version">v{APP_VERSION}</span></div>
        </div>
        <div class="header-status-group">
            <div class="header-stat">
                <div class="header-stat-label">Plant</div>
                <div class="header-stat-value"><span class="status-dot" style="background:{plant_color};color:{plant_color};"></span>{plant_text}</div>
            </div>
            <div class="header-stat">
                <div class="header-stat-label">Workbook</div>
                <div class="header-stat-value"><span class="status-dot" style="background:{wb_color};color:{wb_color};"></span>{wb_text}</div>
            </div>
            <div class="header-stat">
                <div class="header-stat-label">GitHub</div>
                <div class="header-stat-value"><span class="status-dot" style="background:{gh_color};color:{gh_color};"></span>{gh_text}</div>
            </div>
            <div class="header-stat">
                <div class="header-stat-label">Time</div>
                <div class="header-stat-value tnum">{now.strftime("%H:%M:%S")}</div>
            </div>
            <div class="header-stat">
                <div class="header-stat-label">Last Refresh</div>
                <div class="header-stat-value tnum">{refresh_str}</div>
            </div>
        </div>
    </div>""",
        unsafe_allow_html=True,
    )


# ==================================================================
# Alarm Ribbon
# ==================================================================

# Soft, non-authoritative thresholds used only to color the ribbon.
# These do NOT alter any engineering calculation — display hint only.
ALARM_WATCHLIST: Final[dict[str, float]] = {
    "Air compressor": 0.90,   # latest / gauge-ceiling ratio
    "DG": 0.90,
    "GG": 0.90,
}


def render_alarm_ribbon(dashboard: dict[str, Any]) -> None:
    departments = dashboard.get("departments", {})
    alarms: list[tuple[str, str]] = []  # (severity, message)

    for dept_name, threshold_ratio in ALARM_WATCHLIST.items():
        dept_obj = departments.get(dept_name)
        if not dept_obj:
            continue
        rep_m = select_representative_meter(dept_obj)
        if not rep_m:
            continue
        latest_val = dept_obj.get("latest_values", {}).get(rep_m)
        df_block = dept_obj.get("dataframe", pd.DataFrame())
        if not isinstance(latest_val, (int, float)):
            continue
        ceiling = get_gauge_max(df_block, rep_m, dept_obj)
        if ceiling <= 0:
            continue
        ratio = latest_val / ceiling
        if ratio >= 1.0:
            alarms.append(("red", f"{dept_name} {rep_m} Exceeded"))
        elif ratio >= threshold_ratio:
            alarms.append(("amber", f"{dept_name} {rep_m} High"))

    if not alarms:
        color, label, text = "#10B981", "STATUS", "No Active Alarms"
    else:
        severities = [a[0] for a in alarms]
        if "red" in severities:
            color, label = "#EF4444", "ALARM"
            text = next(msg for sev, msg in alarms if sev == "red")
        else:
            color, label = "#F59E0B", "WARNING"
            text = alarms[0][1]
        if len(alarms) > 1:
            text += f" (+{len(alarms) - 1} more)"

    st.markdown(
        f"""
    <div class="alarm-ribbon" style="--alarm-color:{color};">
        <span class="alarm-dot"></span>
        <span class="alarm-label">{label}</span>
        <span>{text}</span>
    </div>""",
        unsafe_allow_html=True,
    )


# ==================================================================
# Section 1 — Executive Summary
# ==================================================================

def render_executive_summary(dashboard: dict[str, Any]) -> None:
    departments = dashboard.get("departments", {})
    tiles_html = ""

    for sys_name in CRITICAL_SYSTEMS:
        if sys_name not in departments:
            continue

        dept_obj = departments[sys_name]
        rep_m = select_representative_meter(dept_obj)
        latest_val = dept_obj.get("latest_values", {}).get(rep_m)
        unit = dept_obj.get("units", {}).get(rep_m, "")
        accent = DEPT_CONFIGS.get(sys_name, DEFAULT_CONFIG)["accent"]
        df_block = dept_obj.get("dataframe", pd.DataFrame())

        if isinstance(latest_val, (int, float)):
            val_str = f"{latest_val:,.0f}"
            status_class, status_text = "status-online", "ONLINE"
        else:
            val_str = "—"
            status_class, status_text = "status-offline", "OFFLINE"

        unit_str = str(unit).strip() if unit else ""
        # engineering metric label, not the raw meter name
        metric_label = DEPT_CONFIGS.get(sys_name, DEFAULT_CONFIG).get("category", "Metric").split(" / ")[0]

        trend = compute_trend_chip(df_block, rep_m)
        if trend:
            arrow, pct = trend
            trend_class = "trend-up" if arrow == "▲" else ("trend-down" if arrow == "▼" else "trend-flat")
            trend_html = f'<span class="trend-chip {trend_class}">{arrow} {pct}</span>'
        else:
            trend_html = ""

        tiles_html += f"""
        <div class="exec-tile" style="--accent:{accent};">
            <div class="exec-tile-top">
                <div class="exec-name">{sys_name}</div>
            </div>
            <div class="exec-label">{metric_label}</div>
            <div class="exec-value-row">
                <div class="exec-value">{val_str}<span class="exec-unit">{unit_str}</span></div>
            </div>
            <div class="exec-bottom-row">
                <div class="exec-status {status_class}">{status_text}</div>
                {trend_html}
            </div>
        </div>"""

    if tiles_html:
        st.markdown(f'<div class="exec-grid">{tiles_html}</div>', unsafe_allow_html=True)


# ==================================================================
# Section 2 — Operations Overview
# ==================================================================

OPS_CONSOLE_PROCESSES: Final[list[str]] = [
    "NPCL",
    "Overall PNG",
    "Dough",
    "Traywasher",
    "Freon Refrigeration",
    "Ammonia Refrigeration",
    "Bread",
    "Donut",
]


def render_operations_overview(dashboard: dict[str, Any]) -> None:
    departments = dashboard.get("departments", {})
    rows_html = ""

    header_html = """
    <div class="console-row console-row-head">
        <div class="console-col console-col-name">Process</div>
        <div class="console-col console-col-num">Total</div>
        <div class="console-col console-col-num">Average</div>
        <div class="console-col console-col-num">Latest</div>
        <div class="console-col console-col-status">Status</div>
    </div>"""

    for idx, dept_name in enumerate(OPS_CONSOLE_PROCESSES):
        if dept_name not in departments:
            continue
        dept_obj = departments[dept_name]
        rep_m = select_representative_meter(dept_obj)
        total_val = dept_obj.get("total_values", {}).get(rep_m)
        avg_val = dept_obj.get("average_values", {}).get(rep_m)
        latest_val = dept_obj.get("latest_values", {}).get(rep_m)
        unit = dept_obj.get("units", {}).get(rep_m, "")
        unit_str = str(unit).strip() if unit else ""

        total_str = f"{total_val:,.0f}" if isinstance(total_val, (int, float)) else "—"
        avg_str = f"{avg_val:,.1f}" if isinstance(avg_val, (int, float)) else "—"
        latest_str = f"{latest_val:,.0f}" if isinstance(latest_val, (int, float)) else "—"

        is_online = isinstance(latest_val, (int, float))
        status_html = (
            '<span class="status-online">● ONLINE</span>' if is_online
            else '<span class="status-offline">○ OFFLINE</span>'
        )
        row_shade = "console-row-alt" if idx % 2 else ""

        rows_html += f"""
        <div class="console-row {row_shade}">
            <div class="console-col console-col-name">{dept_name}</div>
            <div class="console-col console-col-num"><span class="ops-val">{total_str}</span><span class="ops-unit">{unit_str}</span></div>
            <div class="console-col console-col-num"><span class="ops-val">{avg_str}</span><span class="ops-unit">{unit_str}</span></div>
            <div class="console-col console-col-num"><span class="ops-val">{latest_str}</span><span class="ops-unit">{unit_str}</span></div>
            <div class="console-col console-col-status">{status_html}</div>
        </div>"""

    if rows_html:
        st.markdown(f'<div class="ops-console">{header_html}{rows_html}</div>', unsafe_allow_html=True)


# ==================================================================
# Section 3 — Equipment / Process Selector
# ==================================================================

def _top_metrics_for(dept_obj: dict[str, Any], meters: list[str], n: int = 3) -> list[tuple[str, str]]:
    """Pull up to n (meter_name, formatted latest value + unit) pairs for a card."""
    latest_vals = dept_obj.get("latest_values", {})
    units = dept_obj.get("units", {})
    out: list[tuple[str, str]] = []
    for m in meters[:n]:
        v = latest_vals.get(m)
        u = str(units.get(m, "") or "").strip()
        v_str = f"{v:,.1f}" if isinstance(v, (int, float)) else "—"
        out.append((m, f"{v_str} {u}".strip()))
    return out


def render_process_selector(dashboard: dict[str, Any]) -> str | None:
    departments = dashboard.get("departments", {})

    if "selected_process" not in st.session_state:
        st.session_state["selected_process"] = None

    selected = st.session_state["selected_process"]
    dept_names = sorted(departments.keys())
    cols = st.columns(4)

    for idx, dept_name in enumerate(dept_names):
        dept_obj = departments[dept_name]
        config = DEPT_CONFIGS.get(dept_name, DEFAULT_CONFIG)
        meters = dept_obj.get("meters", [])
        is_active = (dept_name == selected)
        metrics = _top_metrics_for(dept_obj, meters, n=3)
        is_online = any(dept_obj.get("latest_values", {}).get(m) is not None for m in meters)
        status_class = "status-online" if is_online else "status-offline"
        status_text = "ONLINE" if is_online else "OFFLINE"
        live_color = "#10B981" if is_online else "#EF4444"

        metrics_html = "".join(
            f'<div class="equip-metric-row"><span>{name}</span><span>{val}</span></div>'
            for name, val in metrics
        )

        card_html = f"""
        <div class="equip-card{' active' if is_active else ''}" style="--accent:{config['accent']};">
            <div class="equip-header">
                <div>
                    <div class="equip-name">{dept_name}</div>
                    <div class="equip-category">{config['category']}</div>
                </div>
                <div class="equip-live-dot" style="background:{live_color};box-shadow:0 0 5px {live_color};"></div>
            </div>
            <div class="equip-metrics">{metrics_html}</div>
            <div class="equip-activate">
                <span>{'ACTIVE ●' if is_active else 'ACTIVATE'}</span>
                <span class="exec-status {status_class}">{status_text}</span>
            </div>
        </div>"""

        with cols[idx % 4]:
            st.markdown(card_html, unsafe_allow_html=True)
            st.button(" ", key=f"proc_{dept_name}", use_container_width=True)
            if st.session_state.get(f"proc_{dept_name}"):
                st.session_state["selected_process"] = dept_name
                st.rerun()

    return st.session_state["selected_process"]


# ==================================================================
# Section 4 — Workspace / control room, per-department layouts
# ==================================================================

def _chart_panel(label: str, fig, accent: str, subtitle: str = "") -> None:
    """Consistent professional chart panel: accent strip, title, subtitle,
    timestamp — same visual language across every chart in the workspace."""
    ts = dt.datetime.now().strftime("%H:%M:%S")
    sub_html = f'<div class="chart-panel-subtitle">{subtitle}</div>' if subtitle else ""
    st.markdown(
        f"""<div class="chart-panel" style="--accent:{accent};">
            <div class="chart-panel-head">
                <div>
                    <div class="chart-panel-title">{label}</div>
                    {sub_html}
                </div>
                <div class="chart-panel-time">{ts}</div>
            </div>""",
        unsafe_allow_html=True,
    )
    if fig:
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    st.markdown("</div>", unsafe_allow_html=True)


def _render_kpi_strip(dept_obj: dict[str, Any], meters: list[str], rep_m: str | None, accent: str) -> None:
    """Dense top-of-workspace KPI row: representative meter + up to 3 more."""
    latest_vals = dept_obj.get("latest_values", {})
    units = dept_obj.get("units", {})

    strip_meters: list[str] = []
    if rep_m:
        strip_meters.append(rep_m)
    for m in meters:
        if m not in strip_meters:
            strip_meters.append(m)
        if len(strip_meters) >= 4:
            break

    cells_html = ""
    for m in strip_meters:
        unit_str = str(units.get(m, "") or "").strip()
        v = latest_vals.get(m)
        v_str = f"{v:,.1f}" if isinstance(v, (int, float)) else "—"
        cells_html += f"""
        <div class="kpi-cell" style="--accent:{accent};">
            <div class="kpi-cell-label">{m}</div>
            <div class="kpi-cell-value">{v_str}<span class="kpi-cell-unit">{unit_str}</span></div>
        </div>"""

    if cells_html:
        st.markdown(f'<div class="kpi-strip">{cells_html}</div>', unsafe_allow_html=True)


def _render_channel_register(dept_obj: dict[str, Any], meters: list[str]) -> None:
    units_map = dept_obj.get("units", {})
    latest_vals = dept_obj.get("latest_values", {})
    avg_vals = dept_obj.get("average_values", {})
    total_vals = dept_obj.get("total_values", {})

    ledger_records = []
    for m in meters:
        lbl = units_map.get(m)
        l_v = latest_vals.get(m)
        a_v = avg_vals.get(m)
        t_v = total_vals.get(m)
        ledger_records.append(
            {
                "Channel": m,
                "Unit": lbl if (lbl and str(lbl).strip()) else "N/A",
                "Latest": round(l_v, 2) if isinstance(l_v, (int, float)) else "N/A",
                "Mean": round(a_v, 2) if isinstance(a_v, (int, float)) else "N/A",
                "Total": round(t_v, 2) if isinstance(t_v, (int, float)) else "N/A",
                "Status": "Active" if l_v is not None else "Idle",
            }
        )
    if ledger_records:
        st.dataframe(pd.DataFrame(ledger_records), use_container_width=True, hide_index=True)


def _render_primary_and_secondary_charts(
    process_name: str, dept_obj: dict[str, Any], overview_df: pd.DataFrame,
    df_block: pd.DataFrame, meters: list[str], rep_m: str | None,
    unit_lbl: str, latest_val: float, max_ceiling: float, accent: str,
) -> None:
    """Primary + secondary chart section (department-specific layouts)."""
    st.markdown('<div class="subsection-label">Primary Charts</div>', unsafe_allow_html=True)

    if process_name == "NPCL":
        col1, col2 = st.columns([2, 1])
        with col1:
            fig = chart_service.build_section_trend_chart(overview_df, dept_obj)
            _chart_panel("Load Trend", fig, accent, "Representative meter, time series")
        with col2:
            fig = chart_service.create_gauge_chart(latest_val, "Demand", maximum=max_ceiling, unit=unit_lbl)
            _chart_panel("Demand Gauge", fig, accent, "Live reading vs. ceiling")

        st.markdown('<div class="subsection-label">Secondary Charts</div>', unsafe_allow_html=True)
        col3, col4 = st.columns([1, 1])
        with col3:
            if len(meters) >= 2:
                fig = chart_service.create_area_chart(df_block, x_column=df_block.columns[0] if not df_block.empty else "", y_columns=meters[:3], title="Power Factor / Load Area") if not df_block.empty else None
                if fig:
                    _chart_panel("Power Distribution", fig, accent)
        with col4:
            if len(meters) >= 2:
                vals = {m: dept_obj["total_values"].get(m, 0) or 0 for m in meters[:5]}
                bar_df = pd.DataFrame(list(vals.items()), columns=["Meter", "Value"])
                fig = chart_service.create_donut_chart(bar_df, "Meter", "Value", "Energy Distribution")
                _chart_panel("Energy Distribution", fig, accent)

    elif process_name == "Air compressor":
        col1, col2 = st.columns([1, 1])
        with col1:
            fig = chart_service.create_gauge_chart(latest_val, "Pressure", maximum=max_ceiling, unit=unit_lbl)
            _chart_panel("Pressure Gauge", fig, accent)
        with col2:
            fig = chart_service.build_section_trend_chart(overview_df, dept_obj)
            _chart_panel("Flow Trend / Stability", fig, accent)

        if len(meters) >= 2:
            st.markdown('<div class="subsection-label">Secondary Charts</div>', unsafe_allow_html=True)
            vals = {m: dept_obj["total_values"].get(m, 0) or 0 for m in meters[:5]}
            bar_df = pd.DataFrame(list(vals.items()), columns=["Meter", "Value"])
            fig = chart_service.create_horizontal_bar_chart(bar_df, "Meter", "Value", "Runtime")
            _chart_panel("Runtime", fig, accent)

        if len(meters) >= 3:
            st.markdown('<div class="subsection-label">Diagnostics</div>', unsafe_allow_html=True)
            fig = chart_service.create_radar_chart(df_block, meters[:6], "Efficiency Profile")
            _chart_panel("Efficiency", fig, accent, "Normalized channel profile")

    elif process_name in ("Freon Refrigeration", "Ammonia Refrigeration"):
        col1, col2 = st.columns([2, 1])
        with col1:
            fig = chart_service.create_heatmap(df_block, meters[: min(len(meters), 8)], "Temperature Heatmap")
            _chart_panel("Temperature Heatmap", fig, accent)
        with col2:
            fig = chart_service.create_gauge_chart(latest_val, "COP", maximum=max_ceiling, unit=unit_lbl)
            _chart_panel("COP", fig, accent)

        st.markdown('<div class="subsection-label">Secondary Charts</div>', unsafe_allow_html=True)
        col3, col4 = st.columns([2, 1])
        with col3:
            fig = chart_service.build_section_trend_chart(overview_df, dept_obj)
            _chart_panel("Cooling Trend", fig, accent)
        with col4:
            if len(meters) >= 2:
                fig = chart_service.create_histogram(df_block, meters[0], "Temperature Distribution")
                _chart_panel("Temperature Distribution", fig, accent)

    elif process_name in ("DG", "GG"):
        col1, col2 = st.columns([1, 2])
        with col1:
            target_val = dept_obj.get("average_values", {}).get(rep_m, latest_val) or latest_val
            fig = chart_service.create_bullet_chart(latest_val, target_val, "Generation vs Target", unit=unit_lbl)
            _chart_panel("Generation", fig, accent)
        with col2:
            vals = {m: dept_obj["total_values"].get(m, 0) or 0 for m in meters[:6]}
            bar_df = pd.DataFrame(list(vals.items()), columns=["Meter", "Value"])
            fig = chart_service.create_bar_chart(bar_df, "Meter", "Value", "Fuel Consumption")
            _chart_panel("Fuel Consumption", fig, accent)

        st.markdown('<div class="subsection-label">Secondary Charts</div>', unsafe_allow_html=True)
        col3, col4 = st.columns([1, 2])
        with col3:
            fig = chart_service.create_gauge_chart(latest_val, "Runtime Load", maximum=100, unit="%")
            _chart_panel("Runtime", fig, accent)
        with col4:
            fig = chart_service.build_section_trend_chart(overview_df, dept_obj)
            _chart_panel("Output Trend", fig, accent)

    elif process_name == "Traywasher":
        col1, col2 = st.columns([1, 1])
        with col1:
            vals = {m: dept_obj["total_values"].get(m, 0) or 0 for m in meters[:5]}
            bar_df = pd.DataFrame(list(vals.items()), columns=["Meter", "Value"])
            fig = chart_service.create_horizontal_bar_chart(bar_df, "Meter", "Value", "Water Usage")
            _chart_panel("Water Usage", fig, accent)
        with col2:
            fig = chart_service.build_section_trend_chart(overview_df, dept_obj)
            _chart_panel("Thermal Trend", fig, accent)

        if len(meters) >= 3:
            st.markdown('<div class="subsection-label">Diagnostics</div>', unsafe_allow_html=True)
            fig = chart_service.create_radar_chart(df_block, meters[:6], "Cycle Efficiency")
            _chart_panel("Efficiency", fig, accent)

    else:
        col1, col2 = st.columns([2, 1])
        with col1:
            fig = chart_service.build_section_trend_chart(overview_df, dept_obj)
            _chart_panel("Primary Telemetry", fig, accent)
        with col2:
            if rep_m:
                fig = chart_service.create_gauge_chart(latest_val, rep_m, maximum=max_ceiling, unit=unit_lbl)
                _chart_panel("Current Status", fig, accent)

        if len(meters) > 1:
            st.markdown('<div class="subsection-label">Secondary Charts</div>', unsafe_allow_html=True)
            fig = chart_service.create_department_multi_line_chart(
                overview_dataframe=overview_df, section=dept_obj, title="Load Profiles"
            )
            _chart_panel("Multi-Channel Analysis", fig, accent)


def render_workspace(dashboard: dict[str, Any], process_name: str) -> None:
    departments = dashboard.get("departments", {})
    dept_obj = departments.get(process_name, {})
    overview_df = dashboard.get("overview", pd.DataFrame())

    if not dept_obj:
        return

    config = DEPT_CONFIGS.get(process_name, DEFAULT_CONFIG)
    accent = config["accent"]
    meters = dept_obj.get("meters", [])
    df_block = dept_obj.get("dataframe", pd.DataFrame())
    rep_m = select_representative_meter(dept_obj)
    unit_lbl = dept_obj.get("units", {}).get(rep_m, "") if rep_m else ""
    latest_val = dept_obj.get("latest_values", {}).get(rep_m, 0.0) or 0.0 if rep_m else 0.0
    max_ceiling = get_gauge_max(df_block, rep_m, dept_obj) if rep_m else 100.0

    st.markdown(
        f"""
    <div class="workspace" style="--accent:{accent};">
        <div class="workspace-header">
            <h2 class="workspace-title">{process_name}</h2>
            <div class="workspace-label">{config['category']}</div>
        </div>
    </div>""",
        unsafe_allow_html=True,
    )

    # ---------------- Large KPIs (always first, outside tabs) ----------------
    _render_kpi_strip(dept_obj, meters, rep_m, accent)

    # Departments with many diagnostics get compact tabs to cut scrolling.
    use_tabs = len(meters) >= 3

    if use_tabs:
        tab_overview, tab_diag, tab_channels = st.tabs(["Overview", "Diagnostics", "Channels"])
        with tab_overview:
            _render_primary_and_secondary_charts(
                process_name, dept_obj, overview_df, df_block, meters, rep_m,
                unit_lbl, latest_val, max_ceiling, accent,
            )
        with tab_diag:
            if len(meters) >= 3:
                fig = chart_service.create_radar_chart(df_block, meters[:6], "Channel Profile")
                _chart_panel("Diagnostic Profile", fig, accent, "Normalized against channel peak")
                fig = chart_service.create_histogram(df_block, rep_m, "Value Distribution") if rep_m else None
                if fig:
                    _chart_panel("Value Distribution", fig, accent)
            else:
                st.caption("Not enough channels for a diagnostic profile.")
        with tab_channels:
            st.markdown('<div class="subsection-label">Channel Register</div>', unsafe_allow_html=True)
            _render_channel_register(dept_obj, meters)
    else:
        _render_primary_and_secondary_charts(
            process_name, dept_obj, overview_df, df_block, meters, rep_m,
            unit_lbl, latest_val, max_ceiling, accent,
        )
        st.markdown('<div class="subsection-label">Channel Register</div>', unsafe_allow_html=True)
        _render_channel_register(dept_obj, meters)


# ==================================================================
# Footer
# ==================================================================

def render_footer(dashboard: dict[str, Any] | None) -> None:
    last_refresh = st.session_state.get("last_refresh")
    refresh_text = last_refresh.strftime("%d %b %Y, %H:%M:%S") if last_refresh else "N/A"
    meta = (dashboard or {}).get("metadata", {})
    sheet_names = meta.get("sheet_names", ["Data Source Unlinked"])
    active_workbook = sheet_names[0] if sheet_names else "N/A"
    st.markdown(
        f"""<div class="app-footer">WORKBOOK: {active_workbook} &nbsp;·&nbsp; REFRESHED: {refresh_text} &nbsp;·&nbsp; v{APP_VERSION}</div>""",
        unsafe_allow_html=True,
    )


# ==================================================================
# Main
# ==================================================================

def main() -> None:
    inject_global_styles()
    dashboard, error_msg = get_dashboard()

    render_header(dashboard)

    if error_msg is not None or dashboard is None:
        st.error(error_msg or "Critical Infrastructure Alert: Analytical context dictionary failed initialization.")
        render_footer(dashboard)
        return

    render_alarm_ribbon(dashboard)

    st.markdown('<div class="section-title">Executive Summary</div>', unsafe_allow_html=True)
    render_executive_summary(dashboard)

    st.markdown('<div class="section-title">Plant Operations Overview</div>', unsafe_allow_html=True)
    render_operations_overview(dashboard)

    st.markdown('<div class="section-title">Process Selection</div>', unsafe_allow_html=True)
    selected_process = render_process_selector(dashboard)

    if selected_process:
        st.markdown('<div class="section-title">Engineering Workspace</div>', unsafe_allow_html=True)
        render_workspace(dashboard, selected_process)

    render_footer(dashboard)


if __name__ == "__main__":
    main()
