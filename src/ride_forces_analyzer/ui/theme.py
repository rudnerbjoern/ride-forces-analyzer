"""Local dark workspace styling, without changes to scientific presentation contracts."""


# cspell:words Segoe

STYLESHEET = """
QMainWindow, QDialog { background: #101720; color: #e3ebf5; }
QWidget#InspectorBody { background: #101720; }
QWidget { font-family: "Segoe UI"; font-size: 12px; color: #e3ebf5; }
QToolBar { background: #151f2b; border: 0; border-bottom: 1px solid #2b394a; spacing: 8px; padding: 4px; }
QToolBar QLabel { font-weight: 600; padding: 0 10px 0 4px; }
QPushButton, QToolButton { background: #223044; border: 1px solid #35465c; border-radius: 6px; padding: 6px 10px; }
QPushButton:hover, QToolButton:hover { background: #2d4059; border-color: #6885a8; }
QPushButton:checked, QToolButton:checked, QToolButton#Primary { background: #245fe5; border-color: #5088ff; }
QPushButton:disabled, QToolButton:disabled, QCheckBox:disabled { color: #718096; }
QLabel#recordingHeading { font-size: 23px; font-weight: 600; }
QLabel#Muted { color: #9eb0c7; }
QLabel#SectionTitle { color: #b8c9df; font-size: 11px; font-weight: 600; }
QFrame#Panel { background: #182330; border: 1px solid #2b3b4d; border-radius: 10px; }
QFrame#ValueCard { background: #111c29; border: 1px solid #2e4055; border-radius: 7px; }
QLabel#CurrentValue { font-size: 22px; font-weight: 600; }
QLabel { background: transparent; border: 0; }
QSpinBox { background: #111c29; border: 1px solid #3a4d66; border-radius: 5px; padding: 4px; }
QSpinBox:disabled { color: #718096; }
QCheckBox { spacing: 5px; }
QCheckBox::indicator { width: 15px; height: 15px; }
QCheckBox::indicator:unchecked { background: #111c29; border: 1px solid #60718b; border-radius: 3px; }
QCheckBox::indicator:checked { background: #2866df; border: 1px solid #6c9dff; border-radius: 3px; }
QSlider { background: transparent; }
QSlider::groove:horizontal { background: #36465a; height: 4px; border-radius: 2px; }
QSlider::sub-page:horizontal { background: #4383ff; border-radius: 2px; }
QSlider::handle:horizontal { background: #d6e5ff; border: 2px solid #538fff; width: 12px; margin: -5px 0; border-radius: 7px; }
QSlider::handle:horizontal:disabled { background: #748196; border-color: #748196; }
QScrollArea { background: transparent; border: 0; }
QScrollBar:vertical { background: #15202d; width: 8px; }
QScrollBar::handle:vertical { background: #40546c; min-height: 24px; border-radius: 4px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QSplitter::handle { background: #101720; }
QPlainTextEdit { background: #101a27; border: 1px solid #35465c; border-radius: 5px; padding: 6px; }
QStatusBar { background: #151f2b; color: #a9bdd5; border-top: 1px solid #2b394a; }
QProgressBar { border: 0; background: #223044; max-height: 4px; }
QProgressBar::chunk { background: #4383ff; }
QToolTip { background: #223044; color: #e3ebf5; border: 1px solid #627d9f; padding: 6px; }
"""
