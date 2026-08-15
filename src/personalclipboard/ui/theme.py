"""Shared HUD colors and control chrome for overlay, settings, and history."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget

ACCENT = "#d2d2d6"
TEXT = "#f0f0f2"
MUTED = "#a8a8ae"
MIC_OFF = "#c4453c"
MIC_WAIT = "#9a9aa0"
MIC_LIVE = "#2faf5a"


def pointing(*widgets: QWidget) -> None:
    for widget in widgets:
        widget.setCursor(Qt.CursorShape.PointingHandCursor)


def control_chrome() -> str:
    """Buttons, fields, sliders, and scrollbars. Safe to apply on overlay or dialog."""
    return f"""
            QToolTip {{
                color: {TEXT};
                background: #242428;
                border: 1px solid rgba(255, 255, 255, 28);
                padding: 7px 10px;
                font-size: 12px;
            }}
            QLabel {{ background: transparent; color: {MUTED}; font-size: 13px; }}
            QLabel#brand {{ color: {TEXT}; font-size: 15px; font-weight: 600; }}
            QLabel#sectionTitle {{ color: {ACCENT}; font-size: 12px; font-weight: 600; }}
            QLabel#fieldLabel {{ color: {ACCENT}; font-size: 13px; }}
            QLabel#opacityValue {{
                color: {TEXT}; font-size: 13px; font-weight: 600;
            }}
            QLabel#historyStamp {{ color: {MUTED}; font-size: 11px; font-weight: 600; }}
            QLabel#historyBody {{ color: {TEXT}; font-size: 14px; }}
            QLabel#historyEmpty {{ color: {MUTED}; font-size: 14px; padding: 24px 8px; }}
            QLabel#kindBadge {{
                color: #e8f8ee; font-size: 11px; font-weight: 700;
                padding: 3px 8px; border-radius: 999px;
                background: rgba(47, 175, 90, 55);
                border: 1px solid rgba(95, 220, 134, 90);
            }}
            QLabel#kindBadge[kind="playback"] {{
                color: #dce8f8;
                background: rgba(56, 96, 160, 70);
                border: 1px solid rgba(120, 160, 220, 100);
            }}
            QFrame#panel, QFrame#voicePanel, QFrame#typePanel {{
                background: rgba(20, 20, 22, 92);
                border: 1px solid rgba(255, 255, 255, 18);
                border-radius: 12px;
            }}
            QFrame#voicePanel {{
                background: rgba(16, 22, 30, 100);
                border: 1px solid rgba(120, 160, 200, 32);
            }}
            QFrame#typePanel {{
                background: rgba(24, 20, 16, 100);
                border: 1px solid rgba(210, 186, 140, 28);
            }}
            QFrame#panel[active="true"], QFrame#voicePanel[active="true"],
            QFrame#typePanel[active="true"] {{
                background: rgba(24, 26, 28, 110);
                border: 1px solid rgba(210, 210, 214, 55);
            }}
            QFrame#voicePanel[active="true"] {{
                background: rgba(18, 28, 38, 120);
                border: 1px solid rgba(140, 180, 220, 70);
            }}
            QFrame#typePanel[active="true"] {{
                background: rgba(32, 26, 18, 120);
                border: 1px solid rgba(220, 196, 150, 70);
            }}
            QFrame#sectionRule {{
                background: transparent;
                border: none;
                border-top: 1px solid rgba(255, 255, 255, 20);
                margin: 2px 8px 0 8px;
            }}
            QLabel#roleTag {{
                color: #c4d4e8;
                font-size: 10px;
                font-weight: 700;
                letter-spacing: 0.4px;
                padding: 2px 8px;
                border-radius: 999px;
                background: rgba(56, 96, 140, 70);
                border: 1px solid rgba(120, 160, 210, 90);
            }}
            QFrame#settingsDock {{
                background: transparent;
                border: none;
            }}
            QFrame#actions {{
                background: transparent;
                border: none;
            }}
            QFrame#historySection {{
                background: rgba(28, 28, 32, 230);
                border: 1px solid rgba(255, 255, 255, 22);
                border-radius: 12px;
            }}
            QFrame#historySection:hover {{
                border: 1px solid rgba(210, 210, 214, 70);
                background: rgba(36, 36, 40, 240);
            }}
            QCheckBox, QPushButton#ghost, QPushButton#primary, QPushButton#danger,
            QPushButton#quiet, QLineEdit, QPlainTextEdit, QComboBox {{
                background: rgba(12, 12, 14, 120);
                color: {TEXT};
                border: 1px solid rgba(255, 255, 255, 22);
                padding: 6px 14px;
                border-radius: 9px;
                min-height: 24px;
                font-size: 13px;
                font-weight: 600;
            }}
            QCheckBox {{ font-size: 13px; padding: 6px 12px; }}
            QCheckBox::indicator {{
                width: 16px; height: 16px; border-radius: 8px;
                border: 1px solid {ACCENT}; background: rgba(18, 18, 20, 180);
            }}
            QCheckBox::indicator:checked {{ background: {ACCENT}; }}
            QCheckBox#micToggle {{
                font-size: 13px; font-weight: 600; padding: 6px 14px;
                min-height: 24px; min-width: 72px; spacing: 0;
            }}
            QCheckBox#micToggle::indicator {{
                width: 0; height: 0; margin: 0; padding: 0;
                border: none; background: transparent;
            }}
            QCheckBox#micToggle:checked {{
                background: rgba(47, 175, 90, 48);
                border: 1px solid rgba(95, 220, 134, 110);
                color: #e8f8ee;
            }}
            QRadioButton#modeRadio {{
                background: transparent;
                color: {MUTED};
                border: 1px solid transparent;
                padding: 2px 4px;
                min-height: 22px;
                min-width: 0;
                font-size: 14px;
                font-weight: 600;
                spacing: 4px;
            }}
            QRadioButton#modeRadio::indicator {{
                width: 12px; height: 12px; border-radius: 6px;
                border: 1px solid {ACCENT};
                background: rgba(18, 18, 20, 180);
            }}
            QRadioButton#modeRadio::indicator:checked {{
                background: {ACCENT};
                border: 1px solid {TEXT};
            }}
            QRadioButton#modeRadio:checked {{ color: {TEXT}; }}
            QRadioButton#modeRadio:hover {{
                color: {TEXT};
                border-color: rgba(210, 210, 214, 50);
                background: rgba(40, 40, 44, 90);
            }}
            QPushButton#ghost {{ min-width: 72px; }}
            QPushButton#quiet {{
                background: transparent; border: 1px solid rgba(255, 255, 255, 16);
                color: {MUTED}; min-width: 64px; font-weight: 600;
            }}
            QPushButton#primary {{
                background: rgba(47, 175, 90, 48);
                border: 1px solid rgba(95, 220, 134, 110);
                color: #e8f8ee; min-width: 72px;
            }}
            QPushButton#danger {{
                background: rgba(196, 69, 60, 55);
                border: 1px solid rgba(232, 106, 98, 120);
                color: #ffe4e1; min-width: 72px;
            }}
            QPushButton#ghost:hover, QCheckBox:hover, QLineEdit:hover, QPlainTextEdit:hover,
            QComboBox:hover {{
                border-color: rgba(210, 210, 214, 90);
                background: rgba(40, 40, 44, 140);
            }}
            QPushButton#quiet:hover {{
                border-color: rgba(255, 255, 255, 28);
                color: {TEXT}; background: rgba(40, 40, 44, 90);
            }}
            QPushButton#primary:hover {{
                background: rgba(47, 175, 90, 70);
            }}
            QPushButton#danger:hover {{
                background: rgba(196, 69, 60, 78);
            }}
            QPushButton#ghost:pressed, QPushButton#primary:pressed, QPushButton#danger:pressed,
            QPushButton#quiet:pressed {{
                background: rgba(8, 8, 10, 160);
            }}
            QPushButton:disabled, QCheckBox:disabled, QToolButton#iconBtn:disabled {{
                color: #6e6e74; border-color: rgba(255, 255, 255, 10);
                background: rgba(12, 12, 14, 60);
            }}
            QToolButton#iconBtn {{
                background: rgba(12, 12, 14, 90);
                color: {TEXT};
                border: 1px solid rgba(255, 255, 255, 22);
                border-radius: 8px;
                font-size: 15px;
                font-weight: 600;
                min-width: 28px;
                min-height: 28px;
                padding: 0;
            }}
            QToolButton#iconBtn:hover {{
                border-color: rgba(210, 210, 214, 90);
                background: rgba(40, 40, 44, 140);
                color: {TEXT};
            }}
            QLineEdit QToolButton#iconBtn {{
                background: transparent;
                border: 1px solid transparent;
                min-width: 24px;
                min-height: 24px;
                font-size: 13px;
                color: {MUTED};
            }}
            QLineEdit QToolButton#iconBtn:hover {{
                background: rgba(40, 40, 44, 140);
                border-color: rgba(255, 255, 255, 22);
                color: {TEXT};
            }}
            QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QPushButton:focus,
            QCheckBox:focus, QSlider:focus, QToolButton#iconBtn:focus {{
                border: 1px solid {ACCENT};
            }}
            QComboBox {{ font-size: 13px; min-height: 24px; padding: 4px 10px; font-weight: 500; }}
            QComboBox QAbstractItemView {{
                background: #1c1c1e; color: {TEXT};
                selection-background-color: #3a3a40; selection-color: {TEXT};
                border: 1px solid rgba(255, 255, 255, 22); outline: none;
            }}
            QComboBox::drop-down {{ border: none; width: 22px; }}
            QMenu {{
                background: #1c1c1e; color: {TEXT};
                border: 1px solid rgba(255, 255, 255, 22);
                padding: 6px; border-radius: 10px;
            }}
            QMenu::item {{
                padding: 8px 16px; border-radius: 8px; font-size: 13px; font-weight: 600;
            }}
            QMenu::item:selected {{
                background: rgba(47, 175, 90, 48);
            }}
            QScrollArea#settingsScroll, QScrollArea#historyScroll {{
                background: transparent; border: none;
            }}
            QScrollBar:vertical {{
                width: 10px; background: transparent; margin: 2px;
            }}
            QScrollBar::handle:vertical {{
                background: rgba(200, 200, 204, 120); border-radius: 5px; min-height: 28px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: rgba(220, 220, 224, 160);
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0; width: 0;
            }}
            QSlider::groove:horizontal {{
                height: 6px; background: rgba(80,80,84,110); border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                width: 16px; height: 16px; margin: -5px 0; border-radius: 8px;
                background: {TEXT};
            }}
            QSlider::handle:horizontal:hover {{
                background: #ffffff;
            }}
            QLineEdit, QPlainTextEdit {{
                font-size: 14px; min-height: 30px; padding: 8px 12px;
                font-weight: 500;
                selection-background-color: #4a4a52; selection-color: {TEXT};
            }}
            QPlainTextEdit {{
                font-size: 13px; min-height: 72px;
            }}
            QPlainTextEdit#recordBody {{
                background: rgba(12, 12, 14, 160);
                border: 1px solid rgba(255, 255, 255, 18);
                border-radius: 10px;
            }}
            """
