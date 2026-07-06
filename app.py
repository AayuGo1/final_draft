"""Main Streamlit entry point for the Engineering Monitoring Dashboard.

This module is responsible ONLY for configuring the page, loading the
workbook, and displaying basic workbook accessibility information (source,
status, sheet count, and sheet names). It performs no parsing, no KPI
calculation, no charting, and no sidebar navigation.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from config import APP_NAME, PAGE_CONFIG, WORKBOOK_RAW_URL
from data_loader import load_excel


def render_header() -> None:
    """Render the application title and workbook source information."""
    st.title(APP_NAME)
    with st.container(border=True):
        st.caption("Workbook source")
        st.code(WORKBOOK_RAW_URL, language="text")


def render_workbook_summary(excel_file: pd.ExcelFile) -> None:
    """Render the workbook status, sheet count, and sheet names.

    Args:
        excel_file: A successfully loaded ``pandas.ExcelFile`` instance.
    """
    sheet_names = list(excel_file.sheet_names)

    with st.container(border=True):
        col1, col2 = st.columns(2)
        with col1:
            st.metric(label="Workbook status", value="Loaded")
        with col2:
            st.metric(label="Number of sheets", value=len(sheet_names))

    with st.container(border=True):
        st.caption("Sheet names")
        for name in sheet_names:
            st.write(f"- {name}")


def render_error(message: str) -> None:
    """Render a descriptive error message for a failed workbook load.

    Args:
        message: Human-readable description of what went wrong.
    """
    with st.container(border=True):
        st.error(message)


def load_workbook_safely() -> pd.ExcelFile | None:
    """Load the workbook while handling all expected failure modes.

    Returns:
        A ``pandas.ExcelFile`` instance if loading succeeds, otherwise
        ``None`` after an appropriate error message has been displayed.
    """
    try:
        with st.spinner("Connecting to workbook source..."):
            excel_file = load_excel()
    except TimeoutError as exc:
        render_error(f"The workbook source timed out: {exc}")
        return None
    except ConnectionError as exc:
        render_error(f"Could not connect to the workbook source: {exc}")
        return None
    except FileNotFoundError as exc:
        render_error(f"Workbook not found: {exc}")
        return None
    except ValueError as exc:
        render_error(f"The workbook file is invalid: {exc}")
        return None
    except RuntimeError as exc:
        render_error(f"An error occurred while loading the workbook: {exc}")
        return None

    st.success("Workbook loaded successfully.")
    return excel_file


def main() -> None:
    """Configure the page and orchestrate the workbook loading display."""
    st.set_page_config(**PAGE_CONFIG)

    render_header()
    excel_file = load_workbook_safely()

    if excel_file is not None:
        render_workbook_summary(excel_file)


if __name__ == "__main__":
    main()
