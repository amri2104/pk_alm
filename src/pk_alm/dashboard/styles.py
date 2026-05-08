"""Minimal CSS for the Streamlit dashboard."""

from __future__ import annotations


def dashboard_css() -> str:
    return """
    <style>
    .pk-alm-subtitle {
        color: #4b5563;
        font-size: 1.02rem;
        margin-bottom: 1.2rem;
    }
    .pk-alm-section {
        margin-top: 0.6rem;
    }
    </style>
    """

