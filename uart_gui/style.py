"""Shared desktop palette and widget styling."""

COLORS = ["#007f87", "#db8351", "#7166bb", "#378ccd", "#c75d86",
          "#659445", "#c5a230", "#428e80", "#ac6b42", "#626acb",
          "#c34854", "#6794a1", "#956aa4", "#87953d", "#5080aa"]

STYLESHEET = """
QMainWindow, QDialog { background: #f4f6f8; }
QWidget { color: #202e40; font-family: 'Inter', 'Segoe UI', sans-serif; font-size: 13px; }
QFrame#sidebar { background: #152837; border: none; }
QLabel#brand { color: #f4ffff; font-size: 23px; font-weight: 700; }
QLabel#brandSub { color: #91a8b5; font-size: 11px; }
QLabel#sideLabel { color: #7e9aa9; font-size: 10px; font-weight: 700; }
QLabel#sideNote { color: #a9bdc8; font-size: 11px; }
QListWidget#navigation { background: transparent; border: none; outline: none; color: #b6c8d1; }
QListWidget#navigation::item { padding: 13px 12px; border-radius: 7px; margin: 3px 0; }
QListWidget#navigation::item:selected { background: #284957; color: #dcfffc; border-left: 3px solid #60d8c8; }
QListWidget#navigation::item:hover { background: #203b4a; }
QLabel#title { font-size: 26px; font-weight: 700; color: #162d3b; }
QLabel#muted { color: #708292; font-size: 12px; }
QLabel#cardTitle { font-size: 16px; font-weight: 650; }
QLabel#eyebrow { color: #66818a; font-size: 10px; font-weight: 700; }
QLabel#pill { background: #e9eef2; border-radius: 10px; padding: 5px 12px; color: #697e8b; font-weight: 600; }
QFrame#card { background: white; border: 1px solid #dfe7eb; border-radius: 10px; }
QPushButton { background: #fff; border: 1px solid #d6e0e5; border-radius: 6px; padding: 8px 12px; font-weight: 550; }
QPushButton:hover { background: #eef7f7; border-color: #8cb9bb; }
QPushButton:pressed { background: #dcefed; }
QPushButton:disabled { color: #9daab2; background: #f5f7f8; border-color: #e4eaed; }
QPushButton#primary { background: #007f87; color: white; border-color: #007f87; }
QPushButton#primary:hover { background: #006970; }
QPushButton#stop { background: #fcf0ef; color: #b64238; border-color: #e8c1bc; font-weight: 700; }
QPushButton#stop:hover { background: #f8deda; }
QPushButton#write { padding: 5px 8px; font-size: 11px; color: #007f87; background: #f2fafa; border-color: #c9e4e3; }
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox { background: white; border: 1px solid #d8e2e7; border-radius: 5px; padding: 7px; selection-background-color: #b7e2df; }
QLineEdit:focus, QComboBox:focus { border-color: #238e93; }
QLineEdit[invalid="true"] { border-color: #d46255; background: #fff4f2; }
QLineEdit[dirty="true"] { border-color: #d3b272; background: #fffdf5; }
QTableWidget { background: white; alternate-background-color: #f8fafb; border: none; gridline-color: #eff3f5; selection-background-color: #edf7f7; selection-color: #203843; }
QTableWidget::item { padding: 6px; }
QHeaderView::section { background: #f5f8fa; color: #728491; font-size: 10px; font-weight: 650; border: none; border-bottom: 1px solid #e4ebef; padding: 11px 6px; }
QCheckBox { spacing: 8px; }
QCheckBox::indicator { width: 15px; height: 15px; border: 1px solid #b5c6ce; border-radius: 4px; background: white; }
QCheckBox::indicator:checked { background: #158c92; border-color: #158c92; }
QTabWidget::pane { border: none; background: white; }
QTabBar::tab { background: white; color: #81909a; padding: 11px 14px; border-bottom: 2px solid #eaf0f3; }
QTabBar::tab:selected { color: #007f87; border-bottom: 2px solid #007f87; font-weight: 600; }
QPlainTextEdit { background: #f8fafb; color: #60717e; border: 1px solid #e2e9ed; border-radius: 6px; padding: 5px; font-family: monospace; font-size: 11px; }
QSplitter::handle { background: #f4f6f8; width: 12px; }
QStatusBar { background: #eaf0f3; color: #6f818d; font-size: 11px; }
QToolTip { background: #172f3d; color: white; padding: 5px; border: none; }
QScrollBar:vertical { background: #f5f7f9; width: 9px; }
QScrollBar::handle:vertical { background: #cad8de; border-radius: 4px; min-height: 25px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
"""
