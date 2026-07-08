"""Reusable Streamlit UI components for the Engineering Monitoring Dashboard."""
from __future__ import annotations

import pandas as pd
import streamlit as st

def render_page_title(title: str, subtitle: str | None = None) -> None:
    st.markdown(f"""
    <div style="margin-bottom: 24px;">
        <h1 style="font-size: 28px; font-weight: 800; color: #111827; margin: 0; letter-spacing: -0.5px;">{title}</h1>
        {f'<p style="font-size: 15px; color: #6B7280; margin-top: 8px; font-weight: 400;">{subtitle}</p>' if subtitle else ''}
    </div>
    """, unsafe_allow_html=True)

def render_success_banner(message: str) -> None:
    st.markdown(f"""
    <div style="background: rgba(34, 197, 94, 0.1); border: 1px solid #22C55E; border-radius: 12px; padding: 16px; margin-bottom: 16px; display: flex; align-items: center; gap: 12px;">
        <span style="font-size: 20px;">✅</span>
        <span style="color: #166534; font-weight: 600; font-size: 14px;">{message}</span>
    </div>
    """, unsafe_allow_html=True)

def render_error_banner(message: str) -> None:
    st.markdown(f"""
    <div style="background: rgba(227, 30, 36, 0.1); border: 1px solid #E31E24; border-radius: 12px; padding: 16px; margin-bottom: 16px; display: flex; align-items: center; gap: 12px;">
        <span style="font-size: 20px;">🚨</span>
        <span style="color: #991B1B; font-weight: 600; font-size: 14px;">{message}</span>
    </div>
    """, unsafe_allow_html=True)

def render_info_banner(message: str) -> None:
    st.markdown(f"""
    <div style="background: rgba(0, 93, 170, 0.1); border: 1px solid #005DAA; border-radius: 12px; padding: 16px; margin-bottom: 16px; display: flex; align-items: center; gap: 12px;">
        <span style="font-size: 20px;">ℹ️</span>
        <span style="color: #005DAA; font-weight: 600; font-size: 14px;">{message}</span>
    </div>
    """, unsafe_allow_html=True)

def render_kpi_cards(cards: list[dict]) -> None:
    if not cards:
        return

    st.markdown("""
    <style>
    .kpi-cards-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 20px; margin-bottom: 24px; }
    .kpi-card {
        background: #FFFFFF; border: 1px solid #E5E7EB; 
        border-left: 6px solid var(--accent, #005DAA); border-radius: 16px; padding: 24px;
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); transition: all 0.3s ease;
        height: 100%;
    }
    .kpi-card:hover { transform: translateY(-4px); box-shadow: 0 10px 15px -3px rgba(0,0,0,0.08); }
    .kpi-card-top { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
    .kpi-icon { font-size: 24px; color: var(--accent, #005DAA); }
    .kpi-title { font-size: 13px; font-weight: 600; color: #6B7280; text-transform: uppercase; letter-spacing: 0.5px; }
    .kpi-value { font-size: 32px; font-weight: 800; color: #111827; line-height: 1.2; }
    .kpi-delta { font-size: 14px; font-weight: 600; margin-top: 8px; }
    </style>
    """, unsafe_allow_html=True)

    html = '<div class="kpi-cards-grid">'
    for card in cards:
        title = card.get("title", "")
        value = card.get("value", "")
        delta = card.get("delta")
        color = card.get("color", "#005DAA")
        
        delta_html = ""
        if delta is not None:
            delta_str = str(delta)
            is_positive = "+" in delta_str or (not delta_str.startswith("-") and any(c.isdigit() for c in delta_str))
            d_color = "#22C55E" if is_positive else "#E31E24"
            arrow = "▲" if is_positive else "▼"
            delta_html = f'<div class="kpi-delta" style="color: {d_color};">{arrow} {delta_str}</div>'
            
        html += f"""
        <div class="kpi-card" style="--accent: {color};">
            <div class="kpi-card-top">
                <div class="kpi-title">{title}</div>
                <div class="kpi-icon">📊</div>
            </div>
            <div class="kpi-value">{value}</div>
            {delta_html}
        </div>
        """
    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)

def render_dataframe(dataframe: pd.DataFrame) -> None:
    st.dataframe(dataframe, use_container_width=True, hide_index=True)

def render_section(title: str) -> None:
    st.markdown(f"""
    <div class="section-title" style="font-size: 18px; font-weight: 700; color: #111827; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 20px; margin-top: 40px; display: flex; align-items: center; gap: 12px;">
        <span style="width: 4px; height: 24px; background: #005DAA; border-radius: 2px;"></span>
        {title}
    </div>
    """, unsafe_allow_html=True)

def render_divider() -> None:
    st.markdown('<hr style="border: 0; border-top: 1px solid #E5E7EB; margin: 24px 0;">', unsafe_allow_html=True)
