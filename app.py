def inject_global_styles() -> None:
    """Inject customized production glassmorphism responsive layout rules."""
    st.markdown(
        f"""
        <style>
            #MainMenu {{visibility: hidden;}}
            footer {{visibility: hidden;}}
            header[data-testid="stHeader"] {{background: transparent;}}

            .block-container {{
                padding-top: 1.0rem;
                padding-bottom: 2.0rem;
                max-width: 1550px;
            }}

            .scada-header {{
                background: linear-gradient(135deg, rgba(108, 99, 255, 0.12), rgba(22, 26, 37, 0.95));
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 12px;
                padding: 16px 20px;
                margin-bottom: 16px;
            }}

            .scada-title-block {{
                display: flex;
                align-items: center;
                gap: 14px;
            }}

            .scada-logo {{
                width: 44px;
                height: 44px;
                border-radius: 8px;
                background: linear-gradient(135deg, {THEME_PRIMARY_COLOR}, #3a34a1);
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 22px;
                box-shadow: 0 4px 12px rgba(108, 99, 255, 0.3);
            }}

            .scada-main-title {{
                font-size: 1.25rem;
                font-weight: 700;
                color: #FAFAFA;
                margin: 0;
            }}

            .status-pill {{
                display: inline-flex;
                align-items: center;
                gap: 6px;
                padding: 3px 10px;
                border-radius: 12px;
                background: rgba(255, 255, 255, 0.03);
                border: 1px solid rgba(255, 255, 255, 0.06);
                font-size: 0.72rem;
                color: #CBD5E1;
            }}

            .status-dot {{
                width: 7px;
                height: 7px;
                border-radius: 50%;
                display: inline-block;
            }}

            .metric-card-container {{
                background: linear-gradient(145deg, rgba(30, 41, 59, 0.35), rgba(15, 23, 42, 0.75));
                border: 1px solid rgba(255, 255, 255, 0.05);
                border-radius: 10px;
                padding: 14px 18px;
                box-shadow: 0 4px 16px rgba(0, 0, 0, 0.25);
            }}

            .metric-card-title {{
                font-size: 0.75rem;
                color: #94A3B8;
                font-weight: 600;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                margin: 0 0 4px 0;
            }}

            .metric-card-value {{
                font-size: 1.5rem;
                font-weight: 700;
                color: #F8FAFC;
                margin: 0;
            }}

            .metric-card-footer {{
                font-size: 0.7rem;
                color: #64748B;
                margin-top: 4px;
            }}

            .section-panel-title {{
                font-size: 0.9rem;
                font-weight: 700;
                color: #F1F5F9;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                margin: 16px 0 10px 2px;
            }}

            .scada-asset-card {{
                background: linear-gradient(145deg, rgba(30, 41, 59, 0.45), rgba(15, 23, 42, 0.85));
                border: 1px solid rgba(255, 255, 255, 0.06);
                border-radius: 12px;
                padding: 18px;
                box-shadow: 0 6px 20px rgba(0, 0, 0, 0.3);
                transition: transform 0.2s ease-in-out, box-shadow 0.2s ease-in-out;
                min-height: 250px;
                display: flex;
                flex-direction: column;
                justify-content: space-between;
                box-sizing: border-box;
                margin-bottom: 16px;
            }}

            .scada-asset-card:hover {{
                transform: translateY(-2px);
                box-shadow: 0 10px 24px rgba(108, 99, 255, 0.15);
                border-color: {THEME_PRIMARY_COLOR}55;
            }}

            .scada-asset-title {{
                font-size: 1.05rem;
                font-weight: 700;
                color: #FAFAFA;
                margin: 0 0 12px 0;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
            }}

            .scada-asset-data-row {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin: 4px 0;
                font-size: 0.82rem;
            }}

            .scada-asset-label {{
                color: #94A3B8;
                font-weight: 500;
            }}

            .scada-asset-value {{
                color: #F8FAFC;
                font-weight: 700;
                text-align: right;
                white-space: nowrap;
            }}

            .scada-asset-status {{
                display: flex;
                align-items: center;
                gap: 6px;
                font-size: 0.75rem;
                color: #CBD5E1;
                margin-top: 10px;
                margin-bottom: 12px;
            }}

            div[data-testid="stButton"] > button {{
                width: 100%;
                border-radius: 8px !important;
                border: 1px solid rgba(255, 255, 255, 0.05) !important;
                background: linear-gradient(145deg, rgba(30, 41, 59, 0.3), rgba(15, 23, 42, 0.7)) !important;
                padding: 10px 12px !important;
                text-align: left !important;
                transition: all 0.15s ease-in-out !important;
            }}

            div[data-testid="stButton"] > button:hover {{
                transform: translateY(-1px);
                border-color: {THEME_PRIMARY_COLOR}66 !important;
                box-shadow: 0 4px 12px rgba(108, 99, 255, 0.12) !important;
            }}

            .tile-active > div[data-testid="stButton"] > button {{
                border-color: {THEME_PRIMARY_COLOR} !important;
                background: linear-gradient(145deg, rgba(108, 99, 255, 0.15), rgba(15, 23, 42, 0.85)) !important;
                box-shadow: 0 4px 12px rgba(108, 99, 255, 0.18) !important;
            }}

            .scada-action-btn > div[data-testid="stButton"] > button {{
                text-align: center !important;
                background: linear-gradient(145deg, {THEME_PRIMARY_COLOR}22, rgba(15, 23, 42, 0.8)) !important;
                border: 1px solid rgba(108, 99, 255, 0.2) !important;
                font-weight: 600 !important;
                color: #E2E8F0 !important;
            }}

            .scada-action-btn > div[data-testid="stButton"] > button:hover {{
                background: linear-gradient(145deg, {THEME_PRIMARY_COLOR}44, rgba(15, 23, 42, 0.9)) !important;
                border-color: {THEME_PRIMARY_COLOR} !important;
                color: #FAFAFA !important;
            }}

            .tile-dept-name {{
                font-size: 0.82rem;
                font-weight: 700;
                color: #F8FAFC;
                margin: 0 0 4px 0;
            }}

            .tile-meta-row {{
                display: flex;
                justify-content: space-between;
                font-size: 0.7rem;
                color: #94A3B8;
                margin-top: 2px;
            }}

            .panel-container {{
                background: rgba(22, 26, 37, 0.45);
                border: 1px solid rgba(255, 255, 255, 0.04);
                border-radius: 12px;
                padding: 24px;
                margin-top: 14px;
            }}

            /* ========================================================= */
            /* POLISHED WORKSPACE STYLES                                 */
            /* ========================================================= */
            
            .workspace-header {{
                background: linear-gradient(135deg, rgba(15, 23, 42, 0.85) 0%, rgba(30, 41, 59, 0.5) 100%);
                border-left: 5px solid {THEME_PRIMARY_COLOR};
                border-top: 1px solid rgba(255, 255, 255, 0.06);
                border-right: 1px solid rgba(255, 255, 255, 0.06);
                border-bottom: 1px solid rgba(255, 255, 255, 0.06);
                border-radius: 12px;
                padding: 24px 28px;
                margin-bottom: 28px;
                box-shadow: 0 8px 32px rgba(0, 0, 0, 0.15);
                backdrop-filter: blur(8px);
            }}

            .workspace-title {{
                font-size: 1.6rem;
                font-weight: 700;
                color: #FFFFFF;
                margin: 0 0 16px 0;
                letter-spacing: 0.02em;
            }}

            .workspace-kpi-card {{
                background: linear-gradient(145deg, rgba(30, 41, 59, 0.4), rgba(15, 23, 42, 0.8));
                border: 1px solid rgba(255, 255, 255, 0.05);
                border-radius: 12px;
                padding: 22px;
                text-align: left;
                box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15);
                transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
                display: flex;
                flex-direction: column;
                justify-content: center;
                height: 100%;
            }}

            .workspace-kpi-card:hover {{
                transform: translateY(-2px);
                box-shadow: 0 8px 24px rgba(108, 99, 255, 0.12);
                border-color: rgba(108, 99, 255, 0.3);
            }}
            
            .workspace-kpi-label {{
                font-size: 0.8rem;
                color: #94A3B8;
                font-weight: 600;
                text-transform: uppercase;
                letter-spacing: 0.05em;
                margin-bottom: 8px;
            }}
            
            .workspace-kpi-value {{
                font-size: 1.8rem;
                font-weight: 700;
                color: #F8FAFC;
                line-height: 1.1;
            }}

            .workspace-section-header {{
                font-size: 1.05rem;
                font-weight: 600;
                color: #E2E8F0;
                margin: 32px 0 16px 0;
                padding-bottom: 10px;
                border-bottom: 1px solid rgba(255, 255, 255, 0.06);
                display: flex;
                align-items: center;
                gap: 10px;
                letter-spacing: 0.03em;
            }}

            .scada-footer {{
                margin-top: 36px;
                padding: 16px;
                border-radius: 10px;
                background: rgba(255, 255, 255, 0.015);
                border: 1px solid rgba(255, 255, 255, 0.03);
                font-size: 0.75rem;
                color: #475569;
                text-align: center;
            }}
        </style>
        """,
        unsafe_allow_html=True,
    )
