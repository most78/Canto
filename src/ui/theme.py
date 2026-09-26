"""Paleta, tamaños y hoja de estilos. Pensado para verse a distancia en pantalla grande.

Todas las medidas pasan por `px()`, que escala según la altura disponible de la
pantalla (1080 p ≈ 1,0). Así la tipografía crece en un televisor o monitor 4K.
"""
from PySide6.QtGui import QColor, QFont, QGuiApplication

BG = '#15112b'
BG_DEEP = '#0d0a1f'
SURFACE = '#221c44'
SURFACE_2 = '#2e2660'
LINE = '#453b80'
TEXT = '#f7f4ff'
MUTED = '#b9b0e4'
DIM = '#7d74ad'

PINK = '#ff5fa2'
VIOLET = '#9b7bff'
GOLD = '#ffd166'
GREEN = '#4ee39a'
CYAN = '#3fd8ff'      # más grave: color frío, abajo
ORANGE = '#ff9f43'    # más agudo: color cálido, arriba
INK = '#1c1438'       # texto sobre botones claros

_scale = 1.0


def init_scale():
    global _scale
    screen = QGuiApplication.primaryScreen()
    if screen is not None:
        height = screen.availableGeometry().height()
        _scale = max(.8, min(1.8, height / 1000))
    return _scale


def px(value):
    return max(1, round(value * _scale))


def color(value, alpha=None):
    c = QColor(value)
    if alpha is not None:
        c.setAlpha(alpha)
    return c


def font(size, weight=QFont.Normal):
    f = QFont('Segoe UI')
    f.setPixelSize(px(size))
    f.setWeight(weight)
    return f


def stylesheet():
    s = px
    return f"""
QWidget {{ background: transparent; color: {TEXT}; font-family: 'Segoe UI'; font-size: {s(20)}px; }}
QMainWindow, QWidget#root {{ background: {BG}; }}
QLabel#brand {{ font-size: {s(34)}px; font-weight: 800; color: {TEXT}; }}
QLabel#display {{ font-size: {s(54)}px; font-weight: 800; }}
QLabel#h1 {{ font-size: {s(40)}px; font-weight: 800; }}
QLabel#h2 {{ font-size: {s(28)}px; font-weight: 700; }}
QLabel#lead {{ font-size: {s(24)}px; color: {MUTED}; }}
QLabel#muted {{ font-size: {s(18)}px; color: {MUTED}; }}
QLabel#eyebrow {{ font-size: {s(17)}px; font-weight: 700; color: {PINK}; letter-spacing: 2px; }}
QLabel#step {{ font-size: {s(22)}px; font-weight: 800; color: {INK}; background: {GOLD};
    border-radius: {s(44) // 2 - 1}px; min-width: {s(44)}px; max-width: {s(44)}px; min-height: {s(44)}px; max-height: {s(44)}px; }}
QLabel#bignote {{ font-size: {s(72)}px; font-weight: 800; color: {GOLD}; }}
QLabel#banner {{ font-size: {s(34)}px; font-weight: 800; padding: {s(8)}px; }}
QLabel#pill {{ background: {SURFACE_2}; border-radius: {s(16)}px; padding: {s(6)}px {s(16)}px; font-size: {s(18)}px; }}
QFrame#card {{ background: {SURFACE}; border: {s(2)}px solid {LINE}; border-radius: {s(28)}px; }}
QFrame#card[active="true"] {{ border: {s(3)}px solid {GOLD}; }}
QFrame#header {{ background: {BG_DEEP}; border-bottom: {s(2)}px solid {LINE}; }}
QPushButton {{ background: {SURFACE_2}; color: {TEXT}; border: {s(2)}px solid {LINE};
    border-radius: {s(22)}px; padding: {s(12)}px {s(26)}px; font-size: {s(22)}px; font-weight: 700; min-height: {s(30)}px; }}
QPushButton:hover {{ border-color: {VIOLET}; background: #3a3178; }}
QPushButton:pressed {{ background: {LINE}; }}
QPushButton:disabled {{ color: {DIM}; border-color: {SURFACE_2}; background: {SURFACE}; }}
QPushButton#primary {{ background: {GOLD}; color: {INK}; border: none; font-size: {s(26)}px; font-weight: 800; padding: {s(16)}px {s(36)}px; }}
QPushButton#primary:hover {{ background: #ffe08f; }}
QPushButton#primary:disabled {{ background: {SURFACE_2}; color: {DIM}; }}
QPushButton#nav {{ background: transparent; border: {s(2)}px solid transparent; border-radius: {s(22)}px;
    padding: {s(10)}px {s(28)}px; font-size: {s(24)}px; color: {MUTED}; }}
QPushButton#nav:hover {{ color: {TEXT}; border-color: {LINE}; }}
QPushButton#nav:checked {{ background: {PINK}; color: {TEXT}; border-color: {PINK}; }}
QPushButton#round {{ background: {PINK}; border: none; border-radius: {s(96) // 2 - 1}px; min-width: {s(96)}px; max-width: {s(96)}px;
    min-height: {s(96)}px; max-height: {s(96)}px; padding: 0; font-size: {s(34)}px; font-family: 'Segoe MDL2 Assets'; }}
QPushButton#round:hover {{ background: #ff7db4; }}
QPushButton#chip {{ font-size: {s(18)}px; padding: {s(10)}px {s(12)}px; border-radius: {s(18)}px; }}
QPushButton#chip:checked {{ background: {VIOLET}; border-color: {GOLD}; color: {TEXT}; }}
QComboBox {{ background: {SURFACE_2}; border: {s(2)}px solid {LINE}; border-radius: {s(18)}px;
    padding: {s(10)}px {s(18)}px; font-size: {s(20)}px; min-height: {s(30)}px; }}
QComboBox QAbstractItemView {{ background: {SURFACE}; selection-background-color: {VIOLET}; font-size: {s(20)}px; }}
QComboBox::drop-down {{ border: none; width: {s(36)}px; }}
QCheckBox {{ font-size: {s(20)}px; spacing: {s(12)}px; }}
QCheckBox::indicator {{ width: {s(30)}px; height: {s(30)}px; border-radius: {s(8)}px; border: {s(2)}px solid {LINE}; background: {SURFACE_2}; }}
QCheckBox::indicator:checked {{ background: {GREEN}; border-color: {GREEN}; }}
QSlider {{ min-height: {s(34)}px; }}
QSlider::groove:horizontal {{ height: {s(12)}px; background: {SURFACE_2}; border-radius: {s(6)}px; }}
QSlider::sub-page:horizontal {{ background: {PINK}; border-radius: {s(6)}px; }}
QSlider::handle:horizontal {{ background: {TEXT}; width: {s(30)}px; margin: -{s(10)}px 0; border-radius: {s(15)}px; }}
QProgressBar {{ background: {SURFACE_2}; border: none; border-radius: {s(10)}px; min-height: {s(20)}px; max-height: {s(20)}px; color: transparent; }}
QProgressBar::chunk {{ background: {GOLD}; border-radius: {s(10)}px; }}
QScrollArea {{ border: none; background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: {s(12)}px; }}
QScrollBar::handle:vertical {{ background: {LINE}; border-radius: {s(6)}px; min-height: {s(40)}px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QToolTip {{ background: {SURFACE}; color: {TEXT}; border: 1px solid {LINE}; font-size: {s(18)}px; }}
"""
