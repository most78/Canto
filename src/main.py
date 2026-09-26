import sys

from PySide6.QtWidgets import QApplication
from ui.main_window import MainWindow


STYLE = """
QWidget { background: #111b21; color: #eaf1ef; font-family: 'Segoe UI'; font-size: 14px; }
QLabel#eyebrow { color: #8bd8bc; font-size: 13px; font-weight: 600; }
QLabel#heading { font-size: 34px; font-weight: 700; }
QLabel#note { font-size: 60px; font-weight: 600; color: #77e2b1; }
QLabel#muted { color: #94aaa9; font-size: 12px; }
QPushButton, QComboBox { background: #23363c; border: 1px solid #385057; border-radius: 8px; padding: 10px; }
QPushButton:hover { background: #33534f; }
QPushButton:disabled, QCheckBox:disabled { color: #778486; }
QSlider::groove:horizontal { height: 6px; background: #314349; border-radius: 3px; }
QSlider::handle:horizontal { background: #8bd8bc; width: 16px; margin: -5px 0; border-radius: 8px; }
QProgressBar { border: 1px solid #385057; border-radius: 5px; text-align: center; min-height: 18px; }
QProgressBar::chunk { background: #467e70; }
QTabWidget::pane { border: 1px solid #385057; border-radius: 8px; }
QTabBar::tab { background: #23363c; padding: 12px 24px; margin-right: 4px; }
QTabBar::tab:selected { background: #385b50; color: #bdf4d8; }
"""


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
