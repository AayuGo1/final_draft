"""Workbook download and loading for the Engineering Monitoring Dashboard.

This module is responsible ONLY for retrieving the Excel workbook from
GitHub and loading it into a ``pandas.ExcelFile``. It performs no parsing,
no header discovery, no KPI calculation, and no chart or dashboard logic.
"""

from __future__ import annotations

from io import BytesIO

import pandas as pd
import requests
import streamlit as st

from config import CACHE_TTL_SECONDS, WORKBOOK_RAW_URL

REQUEST_TIMEOUT_SECONDS: int = 30
"""Maximum time, in seconds, to wait for the GitHub download to complete."""


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner="Downloading workbook...")
def download_workbook(url: str = WORKBOOK_RAW_URL) -> bytes:
    """Download the Excel workbook from GitHub into memory.

    Args:
        url: Raw GitHub URL of the workbook to download. Defaults to the
            URL built from ``config.py``.

    Returns:
        The raw workbook bytes.

    Raises:
        ConnectionError: If GitHub cannot be reached due to a network
            issue.
        TimeoutError: If the request exceeds the configured timeout.
        FileNotFoundError: If the workbook does not exist at the given
            URL (HTTP 404).
        RuntimeError: If GitHub responds with any other non-success
            status code.
    """
    try:
        response = requests.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
    except requests.exceptions.Timeout as exc:
        raise TimeoutError(
            f"Timed out after {REQUEST_TIMEOUT_SECONDS}s while downloading "
            f"the workbook from '{url}'."
        ) from exc
    except requests.exceptions.ConnectionError as exc:
        raise ConnectionError(
            f"Unable to reach GitHub at '{url}'. Check your network "
            "connection or GitHub's availability."
        ) from exc
    except requests.exceptions.RequestException as exc:
        raise RuntimeError(
            f"Unexpected error while downloading the workbook from "
            f"'{url}': {exc}"
        ) from exc

    if response.status_code == 404:
        raise FileNotFoundError(
            f"Workbook not found at '{url}'. Verify the GitHub owner, "
            "repository, branch, and filename in config.py."
        )

    if response.status_code != 200:
        raise RuntimeError(
            f"GitHub returned status code {response.status_code} while "
            f"downloading the workbook from '{url}'."
        )

    return response.content


def load_excel(url: str = WORKBOOK_RAW_URL) -> pd.ExcelFile:
    """Load the downloaded workbook into a ``pandas.ExcelFile``.

    NOT cached. The expensive, shareable step — the network download — is
    cached upstream in ``download_workbook`` (its immutable ``bytes`` result is
    safe to share across sessions). This function instead wraps a FRESH
    ``BytesIO`` in a NEW ``pd.ExcelFile`` on every call, so each Streamlit rerun
    (and each thread) gets its own file handle.

    This is deliberate. A ``pd.ExcelFile`` holds an open, non-thread-safe native
    handle (an ``openpyxl`` zipfile over a ``BytesIO``; it even carries a
    ``_thread.RLock``, which is why it cannot be pickled and therefore cannot be
    cached with ``st.cache_data``). Caching it with ``st.cache_resource`` instead
    would share that single handle across every session and thread; concurrent
    ``.parse()`` calls on one shared zipfile handle corrupt its internal C state
    and crash the process with a native segmentation fault and no Python
    traceback. Building a fresh handle per call removes that shared mutable
    state. Parsed output is byte-for-byte identical either way.

    Args:
        url: Raw GitHub URL of the workbook to download and load.
            Defaults to the URL built from ``config.py``.

    Returns:
        A ``pandas.ExcelFile`` object wrapping the in-memory workbook,
        ready for sheet inspection or reading elsewhere.

    Raises:
        ValueError: If the downloaded content is not a valid Excel file.
        ConnectionError: If GitHub cannot be reached due to a network
            issue.
        TimeoutError: If the download request exceeds the configured
            timeout.
        FileNotFoundError: If the workbook does not exist at the given
            URL.
        RuntimeError: If GitHub responds with any other non-success
            status code.
    """
    workbook_bytes = download_workbook(url)

    try:
        return pd.ExcelFile(BytesIO(workbook_bytes))
    except ValueError as exc:
        raise ValueError(
            f"The file downloaded from '{url}' is not a valid Excel "
            f"workbook: {exc}"
        ) from exc
    except Exception as exc:
        raise ValueError(
            f"Failed to parse the downloaded content from '{url}' as an "
            f"Excel workbook: {exc}"
        ) from exc


def get_sheet_names(url: str = WORKBOOK_RAW_URL) -> list[str]:
    """Get the list of sheet names available in the workbook.

    Args:
        url: Raw GitHub URL of the workbook to download and load.
            Defaults to the URL built from ``config.py``.

    Returns:
        A list of sheet names present in the workbook, in workbook order.

    Raises:
        ValueError: If the downloaded content is not a valid Excel file.
        ConnectionError: If GitHub cannot be reached due to a network
            issue.
        TimeoutError: If the download request exceeds the configured
            timeout.
        FileNotFoundError: If the workbook does not exist at the given
            URL.
        RuntimeError: If GitHub responds with any other non-success
            status code.
    """
    excel_file = load_excel(url)
    return list(excel_file.sheet_names)
