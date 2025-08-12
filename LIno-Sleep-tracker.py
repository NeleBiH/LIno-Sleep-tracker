# SleepyPenguin — Sleep Tracker (PyQt6)
# Created by Nele using ChatGPT
# License: GPL-3.0-only
#
# Features:
# - Start/Stop microphone monitoring
# - Auto-record to ./recordings when level crosses threshold (pre-roll & hang time + hysteresis)
# - Live microphone meter (dB and percentage)
# - Per-clip list with Play/Stop and Delete
# - Themed UI (System/Indigo Night/Neon Black/Nord/Solarized/Light Minimal/Purple Waves)
# - Language switcher (EN/HR/DE) with instant relabeling
# - Sleep session history (Day/Start/End/Sleep Duration)
# - System theme detection (incl. KDE)
#
# Setup helper:
# - Run:  python "Sleep tracker.py" --setup
#   Detects your Linux distro and installs system packages for PortAudio/ALSA (needs sudo),
#   then pip-installs PyQt6, numpy, sounddevice, soundfile.
#   Sudo je potreban jer se instaliraju **sistemske** biblioteke (PortAudio).

import sys, os, json, queue, datetime, collections, configparser, typing, weakref, subprocess
import numpy as np
from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
import sounddevice as sd


# ===================== setup helper =====================
def detect_distro() -> str:
    try:
        with open("/etc/os-release", "r", encoding="utf-8") as f:
            data = f.read().lower()

        def val(k):
            for line in data.splitlines():
                if line.startswith(k + "="):
                    return line.split("=", 1)[1].strip().strip('"')
            return ""

        blob = (val("id") + " " + val("id_like"))
        if any(x in blob for x in ["ubuntu", "debian", "linuxmint", "elementary"]): return "debian"
        if any(x in blob for x in ["fedora", "rhel", "centos"]): return "fedora"
        if "arch" in blob: return "arch"
        if any(x in blob for x in ["opensuse", "suse", "sle"]): return "opensuse"
        return val("id") or ""
    except Exception:
        return ""


def system_install_cmd(distro: str) -> str:
    if distro == "debian":
        return ("sudo apt update && sudo apt install -y "
                "libportaudio2 portaudio19-dev python3-dev libsndfile1 "
                "gstreamer1.0-plugins-base gstreamer1.0-plugins-good "
                "gstreamer1.0-plugins-bad gstreamer1.0-plugins-ugly")
    if distro == "fedora":
        return ("sudo dnf install -y portaudio portaudio-devel python3-devel libsndfile "
                "gstreamer1-plugins-base gstreamer1-plugins-good "
                "gstreamer1-plugins-bad-free gstreamer1-plugins-ugly")
    if distro == "arch":
        return ("sudo pacman -S --noconfirm portaudio libsndfile gstreamer "
                "gst-plugins-base gst-plugins-good gst-plugins-bad gst-plugins-ugly")
    if distro == "opensuse":
        return ("sudo zypper install -y portaudio-devel libsndfile1 "
                "gstreamer-plugins-base gstreamer-plugins-good "
                "gstreamer-plugins-bad gstreamer-plugins-ugly")
    return "echo 'Install PortAudio + GStreamer (base/good/bad/ugly) + libsndfile on your distro'"


def pip_install_cmd() -> str:
    py = sys.executable
    return f"{py} -m pip install -U pip && {py} -m pip install 'PyQt6>=6.5' numpy sounddevice soundfile"


if "--setup" in sys.argv:
    d = detect_distro()
    print(f"[setup] distro: {d or 'unknown'}")
    print("[setup] will run:\n ", system_install_cmd(d), "\n ", pip_install_cmd())
    ok = input("[setup] proceed (needs sudo)? [y/N]: ").strip().lower() == "y"
    if not ok:
        sys.exit(0)
    subprocess.call(system_install_cmd(d), shell=True)
    subprocess.call(pip_install_cmd(), shell=True)
    print("[setup] done. Re-run the app.")
    sys.exit(0)

# ===================== THEMES/QSS =====================
THEME_PALETTES = {
    "Indigo Night": dict(
        bg1="#0B1220", bg2="#0B1A36", fg="#E5E7EB",
        card="rgba(17,25,40,0.55)", border="rgba(255,255,255,0.12)",
        accent="#6366F1", accent2="#4F46E5", muted="#94a3b8"
    ),
    "Neon Black": dict(
        bg1="#0a0f1c", bg2="#0f172a", fg="#E6F7FF",
        card="rgba(10,15,28,0.55)", border="rgba(0,255,255,0.25)",
        accent="#22d3ee", accent2="#a78bfa", muted="#9bd9ff"
    ),
    "Nord": dict(
        bg1="#2E3440", bg2="#2E3440", fg="#ECEFF4",
        card="rgba(59,66,82,0.55)", border="#434C5E",
        accent="#88C0D0", accent2="#8FBCBB", muted="#D8DEE9"
    ),
    "Solarized Dark": dict(
        bg1="#002b36", bg2="#002b36", fg="#EEE8D5",
        card="rgba(7,54,66,0.55)", border="#0b3945",
        accent="#2aa198", accent2="#b58900", muted="#93a1a1"
    ),
    "Light Minimal": dict(
        bg1="#f5f7fb", bg2="#f5f7fb", fg="#111827",
        card="rgba(255,255,255,0.80)", border="#e5e7eb",
        accent="#4F46E5", accent2="#6366F1", muted="#6b7280"
    ),
    "Purple Waves": dict(
        bg1="#1b1033", bg2="#24123a", fg="#F3E8FF",
        card="rgba(255,255,255,0.06)", border="rgba(163,53,238,0.35)",
        accent="#a78bfa", accent2="#f0abfc", muted="#c6b5ff"
    ),
}


def qss_for(p: dict) -> str:
    btn_fg = "#000" if p['accent2'].lower() in ("#ffffff", "#fff") else p['fg']
    sel_fg = "#000" if p['accent2'].lower() in ("#ffffff", "#fff") else "#fff"
    return f"""
* {{ font-family: Inter, "Segoe UI", Roboto, Arial; color: {p['fg']}; }}
QWidget#root {{
  background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 {p['bg1']}, stop:1 {p['bg2']});
}}

/* Cards */
QFrame.card {{
  background: {p['card']};
  border: 1px solid {p['border']};
  border-radius: 16px;
}}

/* Badges */
QLabel.badge {{
  background: rgba(255,255,255,0.10);
  border-radius: 12px;
  padding: 4px 10px;
  font-size: 12px;
}}

/* Buttons */
QPushButton {{
  background: {p['accent2']};
  color: {btn_fg};
  padding: 10px 16px;
  border-radius: 14px;
  border: 1px solid rgba(0,0,0,0.0);
}}
QPushButton:hover {{ background: {p['accent']}; }}
QPushButton[variant="ghost"] {{ background: rgba(255,255,255,0.08); }}
QPushButton[variant="pill"] {{
  background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {p['accent']}, stop:1 {p['accent2']});
  color: {"#001018" if p['fg'] == "#E6F7FF" else "#fff"};
  border-radius: 22px; padding: 14px 22px; font-weight:600;
}}

/* Tabs */
QTabWidget::pane {{ border:0; margin-top:6px; }}
QTabBar::tab {{
  background: rgba(255,255,255,0.06); padding: 6px 12px;
  border-radius: 10px; margin-right: 6px;
}}
QTabBar::tab:selected {{ background: rgba(255,255,255,0.14); }}

/* Progress */
QProgressBar {{
  background: rgba(255,255,255,0.10);
  border: 1px solid {p['border']};
  border-radius: 8px; height: 16px; text-align:center;
}}
QProgressBar::chunk {{ background: {p['accent']}; border-radius: 8px; }}

/* Slider */
QSlider::groove:horizontal {{ height: 6px; background: rgba(255,255,255,0.20); border-radius: 3px; }}
QSlider::handle:horizontal {{ width: 18px; height: 18px; margin: -6px 0; background: {p['accent']}; border: 1px solid {p['border']}; border-radius: 9px; }}

/* ComboBox */
QComboBox {{ background: {p['card']}; border: 1px solid {p['border']}; padding: 8px 12px; border-radius: 10px; }}
QComboBox::drop-down {{ width: 22px; border: 0; }}
QComboBox QAbstractItemView {{
  background: {p['card']}; color: {p['fg']}; border: 1px solid {p['border']};
  selection-background-color: {p['accent']};
  selection-color: {sel_fg};
}}

/* Table card wrapper */
QFrame.tableCard {{
  background: {p['card']};
  border: 1px solid {p['border']};
  border-radius: 16px;
}}

/* Tables */
QTableWidget, QTableView {{
  background: transparent;
  border: none;
  gridline-color: {p['border']};
  selection-background-color: {p['accent']};
  selection-color: {sel_fg};
  alternate-background-color: rgba(255,255,255,0.03);
}}
QTableView::item {{ padding: 6px 8px; }}
QHeaderView::section {{
  background: rgba(255,255,255,0.08);
  color: {p['fg']};
  border: 0;
  border-bottom: 1px solid {p['border']};
  padding: 8px 10px;
}}
QTableCornerButton::section {{
  background: rgba(255,255,255,0.08);
  border: 0;
  border-bottom: 1px solid {p['border']};
}}

QScrollBar:vertical {{ background: transparent; width: 10px; }}
QScrollBar::handle:vertical {{ background: rgba(255,255,255,0.18); border-radius: 5px; }}
"""


# ===================== icons =====================
def icon_play(size=20, color="#ffffff") -> QtGui.QIcon:
    pix = QtGui.QPixmap(size, size)
    pix.fill(QtCore.Qt.GlobalColor.transparent)
    p = QtGui.QPainter(pix)
    p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
    p.setBrush(QtGui.QColor(color))
    p.setPen(QtCore.Qt.PenStyle.NoPen)
    path = QtGui.QPainterPath()
    path.moveTo(size * 0.32, size * 0.24)
    path.lineTo(size * 0.32, size * 0.76)
    path.lineTo(size * 0.78, size * 0.5)
    path.closeSubpath()
    p.drawPath(path)
    p.end()
    return QtGui.QIcon(pix)


def icon_stop(size=20, color="#ffffff") -> QtGui.QIcon:
    pix = QtGui.QPixmap(size, size)
    pix.fill(QtCore.Qt.GlobalColor.transparent)
    p = QtGui.QPainter(pix)
    p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
    p.setBrush(QtGui.QColor(color))
    p.setPen(QtCore.Qt.PenStyle.NoPen)
    r = QtCore.QRectF(size * 0.28, size * 0.28, size * 0.44, size * 0.44)
    p.drawRoundedRect(r, 4, 4)
    p.end()
    return QtGui.QIcon(pix)


def icon_trash(size=18, color="#ffffff") -> QtGui.QIcon:
    pix = QtGui.QPixmap(size, size)
    pix.fill(QtCore.Qt.GlobalColor.transparent)
    p = QtGui.QPainter(pix)
    p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
    pen = QtGui.QPen(QtGui.QColor(color))
    pen.setWidth(2)
    p.setPen(pen)
    p.setBrush(QtCore.Qt.BrushStyle.NoBrush)
    p.drawRect(QtCore.QRectF(size * 0.28, size * 0.35, size * 0.44, size * 0.46))
    p.drawLine(QtCore.QPointF(size * 0.24, size * 0.35), QtCore.QPointF(size * 0.76, size * 0.35))
    p.drawLine(QtCore.QPointF(size * 0.36, size * 0.46), QtCore.QPointF(size * 0.36, size * 0.74))
    p.drawLine(QtCore.QPointF(size * 0.5, size * 0.46), QtCore.QPointF(size * 0.5, size * 0.74))
    p.drawLine(QtCore.QPointF(size * 0.64, size * 0.46), QtCore.QPointF(size * 0.64, size * 0.74))
    p.drawLine(QtCore.QPointF(size * 0.34, size * 0.30), QtCore.QPointF(size * 0.66, size * 0.30))
    p.drawLine(QtCore.QPointF(size * 0.40, size * 0.26), QtCore.QPointF(size * 0.60, size * 0.26))
    p.end()
    return QtGui.QIcon(pix)


def icon_mic(size=18, color="#ffffff") -> QtGui.QIcon:
    pix = QtGui.QPixmap(size, size)
    pix.fill(QtCore.Qt.GlobalColor.transparent)
    p = QtGui.QPainter(pix)
    p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
    p.setPen(QtCore.Qt.PenStyle.NoPen)
    p.setBrush(QtGui.QColor(color))
    p.drawRoundedRect(QtCore.QRectF(size * 0.38, size * 0.18, size * 0.24, size * 0.44), 6, 6)
    p.drawRect(QtCore.QRectF(size * 0.33, size * 0.40, size * 0.34, size * 0.20))
    p.drawRoundedRect(QtCore.QRectF(size * 0.26, size * 0.40, size * 0.48, size * 0.18), 9, 9)
    p.drawRect(QtCore.QRectF(size * 0.47, size * 0.62, size * 0.06, size * 0.18))
    p.drawRoundedRect(QtCore.QRectF(size * 0.38, size * 0.78, size * 0.24, size * 0.05), 2, 2)
    p.end()
    return QtGui.QIcon(pix)


def icon_app(size=64) -> QtGui.QIcon:
    """Crescent-moon app icon in purple."""
    pix = QtGui.QPixmap(size, size)
    pix.fill(QtCore.Qt.GlobalColor.transparent)
    p = QtGui.QPainter(pix)
    p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
    # background rounded square
    bg = QtGui.QColor(60, 65, 80)
    p.setBrush(bg)
    p.setPen(QtCore.Qt.PenStyle.NoPen)
    p.drawRoundedRect(QtCore.QRectF(0, 0, size, size), size * 0.12, size * 0.12)
    # purple moon ring
    ring = QtGui.QColor(167, 139, 250)  # a78bfa
    p.setBrush(ring)
    cx = cy = size * 0.5
    r = size * 0.32
    p.drawEllipse(QtCore.QPointF(cx, cy), r, r)
    # dark crescent cutout
    cut = QtGui.QColor(10, 16, 28)
    p.setBrush(cut)
    p.drawEllipse(QtCore.QPointF(cx + r * 0.35, cy), r * 0.92, r * 0.92)
    p.end()
    return QtGui.QIcon(pix)


# ===================== translations =====================
T = {
    "en": {"title": "Sleep Tracker", "tab_home": "Home", "tab_hist": "History",
           "start": "Start", "stop": "Stop", "time": "Time", "length": "Length",
           "playstop": "Play/Stop", "delete": "Delete",
           "sensitivity": "Microphone Sensitivity", "minlen": "Minimum clip length",
           "language": "Language", "theme": "Theme", "help": "Help", "about": "About", "license": "License", "day": "Day", "maxlen": "Max clip length",
           "sleep_duration": "Sleep Duration", "days": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
           "help_text": "HOW TO USE:\n1) Start = arm mic. Speak/clap to test.\n2) Auto-record saves clips only while level is above sensitivity.\n3) Sliders:\n   • Microphone Sensitivity: right = more sensitive, left = less.\n   • Minimum clip length: throw away tiny blips.\n   • Max clip length: hard stop clip at this time (0 = unlimited).\n4) List below: Play/Stop to preview, Delete to remove.\n5) History shows past sleep sessions."},
    "hr": {"title": "Sleep Tracker", "tab_home": "Home", "tab_hist": "Povijest",
           "start": "Start", "stop": "Stop", "time": "Vrijeme", "length": "Dužina",
           "playstop": "Play/Stop", "delete": "Obriši",
           "sensitivity": "Osjetljivost mikrofona", "minlen": "Minimalna dužina klipa",
           "language": "Jezik", "theme": "Tema", "help": "Pomoć", "about": "O aplikaciji", "license": "Licenca", "day": "Dan", "maxlen": "Maksimalna dužina klipa",
           "sleep_duration": "Trajanje sna", "days": ["Pon", "Uto", "Sri", "Čet", "Pet", "Sub", "Ned"]},
    "de": {"title": "Schlaf-Tracker", "tab_home": "Home", "tab_hist": "Verlauf",
           "start": "Start", "stop": "Stop", "time": "Zeit", "length": "Länge",
           "playstop": "Play/Stop", "delete": "Löschen",
           "sensitivity": "Mikrofon-Empfindlichkeit", "minlen": "Mindestlänge",
           "language": "Sprache", "theme": "Thema", "help": "Hilfe", "about": "Über", "license": "Lizenz", "day": "Tag", "maxlen": "Maximale Clip-Länge",
           "sleep_duration": "Schlafdauer", "days": ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]},
}


# ===================== main window =====================

class SleepTracker(QtWidgets.QWidget):
    RATE = 44100
    CH = 1
    EPS = 1e-8
    ARM_MS = 120
    HANG_MS = 400
    PREROLL_MS = 250
    BLOCK = 1024
    EMA_ALPHA = 0.4

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("root")
        self.lang = "en"
        self.theme_palette: typing.Optional[dict] = None
        self.theme_name: typing.Optional[str] = None

        # audio state
        self.stream: typing.Optional[sd.InputStream] = None
        self.q: "queue.Queue[np.ndarray]" = queue.Queue()
        self.monitoring: bool = False
        self.threshold_db: int = -45
        self.min_len_s: int = 1
        self.max_len_s: int = 30  # seconds (0 = unlimited)
        self.capture_samples: int = 0
        self.smooth_db: float = -90.0

        # segmentation
        self.capturing: bool = False
        self.capture_frames: list[np.ndarray] = []
        self.above_ms: float = 0.0
        self.below_ms: float = 0.0
        self.preroll = collections.deque(maxlen=int(self.PREROLL_MS / 1000 * self.RATE / self.BLOCK + 4))

        # storage
        self.out_dir = os.path.join(os.getcwd(), "recordings")
        os.makedirs(self.out_dir, exist_ok=True)
        cfg_dir = os.path.join(os.path.expanduser("~"), ".config", "SleepyPenguin")
        os.makedirs(cfg_dir, exist_ok=True)
        self.sessions_file = os.path.join(cfg_dir, "sessions.json")
        legacy = os.path.join(os.getcwd(), "sessions.json")
        try:
            if os.path.exists(legacy) and not os.path.exists(self.sessions_file):
                import shutil as _sh
                _sh.copy2(legacy, self.sessions_file)
        except Exception:
            pass
        self.sessions = self._load_sessions()
        self.session_start: typing.Optional[QtCore.QDateTime] = None

        # playback state
        self.current_play: typing.Optional[tuple] = None  # (weakref(btn), path)
        self.player = QMediaPlayer(self)
        self.audio_out = QAudioOutput(self)
        self.player.setAudioOutput(self.audio_out)
        self.audio_out.setVolume(1.0)
        self.player.playbackStateChanged.connect(self._on_player_state)

        # ui
        self._build_ui()
        self.setWindowIcon(icon_app(64))

        self.apply_system_theme()
        self._wire_timers()

        # System tray icon
        self.tray = QtWidgets.QSystemTrayIcon(icon_app(32), self)
        menu = QtWidgets.QMenu()
        actShow = menu.addAction("Show App")
        actExit = menu.addAction("Exit")
        actShow.triggered.connect(self._tray_show)
        actExit.triggered.connect(self._tray_exit)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(
            lambda reason: self._tray_show()
            if reason in (
                QtWidgets.QSystemTrayIcon.ActivationReason.Trigger,
                QtWidgets.QSystemTrayIcon.ActivationReason.DoubleClick,
            )
            else None
        )
        self.tray.setToolTip("SleepyPenguin — Sleep Tracker")
        self.tray.show()

    # ---- UI ----
    def _build_ui(self) -> None:
        self.setWindowTitle(T[self.lang]["title"])
        self.resize(980, 640)
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(10)

        header = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel(T[self.lang]["title"])
        title.setStyleSheet("font-size:20px; font-weight:600;")
        header.addWidget(title)
        header.addStretch(1)
        self.themeCombo = QtWidgets.QComboBox()
        self.themeCombo.addItems(["Tema sustava (Standard)"] + list(THEME_PALETTES.keys()))
        self.themeCombo.currentTextChanged.connect(self._theme_changed)
        header.addWidget(QtWidgets.QLabel(T[self.lang]["theme"] + ":"))
        header.addWidget(self.themeCombo)
        self.langCombo = QtWidgets.QComboBox()
        self.langCombo.addItems(["English", "Hrvatski", "Deutsch"])
        self.langCombo.currentIndexChanged.connect(self._lang_changed)
        header.addWidget(QtWidgets.QLabel(T[self.lang]["language"] + ":"))
        header.addWidget(self.langCombo)
        outer.addLayout(header)

        self.tabs = QtWidgets.QTabWidget()
        self.tabs.currentChanged.connect(self._on_tab_changed)
        outer.addWidget(self.tabs)

        # footer: About + License + (History) Help
        footer = QtWidgets.QHBoxLayout()
        footer.addStretch(1)
        self.btnAbout = QtWidgets.QPushButton(T[self.lang]["about"])
        self.btnAbout.setProperty("variant", "ghost")
        self.btnAbout.clicked.connect(self._show_about)
        footer.addWidget(self.btnAbout)
        self.btnLicense = QtWidgets.QPushButton(T[self.lang]["license"])
        self.btnLicense.setProperty("variant", "ghost")
        self.btnLicense.clicked.connect(self._show_license)
        footer.addWidget(self.btnLicense)
        self.btnHistHelp = QtWidgets.QPushButton(T[self.lang]["help"])
        self.btnHistHelp.setProperty("variant", "ghost")
        self.btnHistHelp.clicked.connect(lambda: self._show_help_context("history"))
        footer.addWidget(self.btnHistHelp)
        outer.addLayout(footer)

        # -- Home tab --
        home = QtWidgets.QWidget()
        g = QtWidgets.QGridLayout(home)
        g.setContentsMargins(0, 0, 0, 0)
        g.setVerticalSpacing(10)

        self.card = QtWidgets.QFrame()
        self.card.setObjectName("card")
        self.card.setProperty("class", "card")
        cg = QtWidgets.QGridLayout(self.card)
        cg.setContentsMargins(16, 16, 16, 16)
        cg.setVerticalSpacing(10)

        self.btnStart = QtWidgets.QPushButton(T[self.lang]["start"])
        self.btnStart.setProperty("variant", "pill")
        self.btnStart.setIcon(icon_play(22))
        self.btnStart.setIconSize(QtCore.QSize(22, 22))
        self.btnStart.clicked.connect(self._toggle_monitor)
        cg.addWidget(self.btnStart, 0, 0, 1, 2)

        micRow = QtWidgets.QHBoxLayout()
        micIcon = QtWidgets.QLabel()
        micIcon.setPixmap(icon_mic(18).pixmap(18, 18))
        micRow.addWidget(micIcon)
        self.levelBar = QtWidgets.QProgressBar()
        self.levelBar.setFormat("%p%")
        self.lblDb = QtWidgets.QLabel("-inf dB")
        self.lblDb.setProperty("class", "badge")
        micRow.addWidget(self.levelBar, 1)
        micRow.addWidget(self.lblDb)
        cg.addLayout(micRow, 1, 0, 1, 2)

        settingsBox = QtWidgets.QFrame()
        settingsBox.setObjectName("card")
        settingsBox.setProperty("class", "card")
        s = QtWidgets.QGridLayout(settingsBox)
        s.setContentsMargins(12, 12, 12, 12)

        self.lblSens = QtWidgets.QLabel(f"{T[self.lang]['sensitivity']} ({self.threshold_db} dB)")
        self.sens = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.sens.setRange(-60, 0)
        self.sens.setValue(self.threshold_db)
        self.sens.setToolTip("Lower = less sensitive; Higher = more sensitive")
        self.sens.valueChanged.connect(self._sens_changed)
        s.addWidget(self.lblSens, 0, 0)
        s.addWidget(self.sens, 0, 1)

        self.lblMin = QtWidgets.QLabel(f"{T[self.lang]['minlen']} ({self.min_len_s} s)")
        self.minlen = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.minlen.setRange(1, 5)
        self.minlen.setValue(self.min_len_s)
        self.minlen.setToolTip("Discard clips shorter than this")
        self.minlen.valueChanged.connect(self._minlen_changed)
        s.addWidget(self.lblMin, 1, 0)
        s.addWidget(self.minlen, 1, 1)

        # Max clip length slider 0–60 s
        self.lblMax = QtWidgets.QLabel(f"{T[self.lang]['maxlen']} ({self.max_len_s} s)")
        self.maxlen = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.maxlen.setRange(0, 60)
        self.maxlen.setValue(self.max_len_s)
        self.maxlen.setToolTip("0 = unlimited")
        self.maxlen.valueChanged.connect(self._maxlen_changed)
        s.addWidget(self.lblMax, 2, 0)
        s.addWidget(self.maxlen, 2, 1)

        self.btnHelp = QtWidgets.QPushButton(T[self.lang]["help"])
        self.btnHelp.setProperty("variant", "ghost")
        self.btnHelp.clicked.connect(self._show_help)
        s.addWidget(self.btnHelp, 0, 2, 3, 1)

        cg.addWidget(settingsBox, 2, 0, 1, 2)

        # recordings table in card
        self.recCard = QtWidgets.QFrame()
        self.recCard.setObjectName("tableCard")
        rv = QtWidgets.QVBoxLayout(self.recCard)
        rv.setContentsMargins(8, 8, 8, 8)
        rv.setSpacing(6)
        self.table = QtWidgets.QTableWidget(0, 4)
        self.table.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.table.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.table.setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.table.setHorizontalScrollMode(QtWidgets.QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setHorizontalHeaderLabels(
            [T[self.lang]["time"], T[self.lang]["length"], T[self.lang]["playstop"], T[self.lang]["delete"]]
        )
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        rv.addWidget(self.table)
        cg.addWidget(self.recCard, 3, 0, 1, 2)

        g.addWidget(self.card, 0, 0, 1, 1)
        g.addWidget(self.recCard, 1, 0, 1, 1)
        self.tabs.addTab(home, T[self.lang]["tab_home"])

        # -- History tab --
        hist = QtWidgets.QWidget()
        hv = QtWidgets.QVBoxLayout(hist)
        hv.setSpacing(10)
        self.histCard = QtWidgets.QFrame()
        self.histCard.setObjectName("tableCard")
        hv2 = QtWidgets.QVBoxLayout(self.histCard)
        hv2.setContentsMargins(8, 8, 8, 8)
        hv2.setSpacing(6)
        self.sessionTable = QtWidgets.QTableWidget(0, 5)
        self.sessionTable.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.sessionTable.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.sessionTable.setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.sessionTable.setHorizontalScrollMode(QtWidgets.QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.sessionTable.setAlternatingRowColors(True)
        self.sessionTable.setShowGrid(False)
        self.sessionTable.setHorizontalHeaderLabels(
            [T[self.lang]["day"], T[self.lang]["time"], "Start", "End", T[self.lang]["sleep_duration"]]
        )
        self.sessionTable.horizontalHeader().setStretchLastSection(True)
        self.sessionTable.verticalHeader().setVisible(False)
        self.sessionTable.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.sessionTable.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        hv2.addWidget(self.sessionTable)
        hv.addWidget(self.histCard)
        self.tabs.addTab(hist, T[self.lang]["tab_hist"])

        self._apply_header_styles()
        self._refresh_history()
        self.btnHistHelp.setVisible(False)  # vidljiv samo na History tabu

    # ---- i18n/theme ----
    def _on_tab_changed(self, idx: int) -> None:
        self.btnHistHelp.setVisible(idx == 1)

    def _lang_changed(self, idx: int) -> None:
        self.lang = ["en", "hr", "de"][idx]
        self.setWindowTitle(T[self.lang]["title"])
        self.tabs.setTabText(0, T[self.lang]["tab_home"])
        self.tabs.setTabText(1, T[self.lang]["tab_hist"])
        self.btnStart.setText(T[self.lang]["stop"] if self.monitoring else T[self.lang]["start"])
        self.lblSens.setText(f"{T[self.lang]['sensitivity']} ({self.threshold_db} dB)")
        self.lblMin.setText(f"{T[self.lang]['minlen']} ({self.min_len_s} s)")
        self.btnHelp.setText(T[self.lang]["help"])
        self.btnHistHelp.setText(T[self.lang]["help"])
        self.btnAbout.setText(T[self.lang]["about"])
        self.btnLicense.setText(T[self.lang]["license"])
        self.lblMax.setText(f"{T[self.lang]['maxlen']} ({self.max_len_s if self.max_len_s > 0 else '∞'} s)")
        self.table.setHorizontalHeaderLabels(
            [T[self.lang]["time"], T[self.lang]["length"], T[self.lang]["playstop"], T[self.lang]["delete"]]
        )
        self.sessionTable.setHorizontalHeaderLabels(
            [T[self.lang]["day"], T[self.lang]["time"], "Start", "End", T[self.lang]["sleep_duration"]]
        )
        self._apply_header_styles()
        self._refresh_history()

    def _kde_dark_hint(self) -> typing.Optional[bool]:
        try:
            cfg = configparser.ConfigParser()
            p = os.path.expanduser("~/.config/kdeglobals")
            if not os.path.exists(p):
                return None
            cfg.read(p)
            sch = cfg.get("General", "ColorScheme", fallback="")
            return ("dark" in sch.lower()) if sch else None
        except Exception:
            return None

    def system_is_dark(self) -> bool:
        try:
            cs = QtGui.QGuiApplication.instance().styleHints().colorScheme()
            if cs == QtCore.Qt.ColorScheme.Dark:
                return True
            if cs == QtCore.Qt.ColorScheme.Light:
                return False
        except Exception:
            pass
        kde = self._kde_dark_hint()
        if kde is not None:
            return kde
        pal = self.palette()
        return pal.color(QtGui.QPalette.ColorRole.Window).lightness() < 120

    def apply_system_theme(self) -> None:
        name = "Indigo Night" if self.system_is_dark() else "Light Minimal"
        self.theme_name = name
        self.theme_palette = THEME_PALETTES[name]
        # koristimo class-metodu da PyCharm ne gunđa
        QtWidgets.QApplication.setStyle("Fusion")
        app = QtWidgets.QApplication.instance()
        if app:
            app.setStyleSheet(qss_for(self.theme_palette))
        self._refresh_icons()
        self._apply_header_styles()

    def _theme_changed(self, name: str) -> None:
        if name.startswith("Tema sustava"):
            self.apply_system_theme()
            return
        self.theme_name = name
        self.theme_palette = THEME_PALETTES[name]
        QtWidgets.QApplication.setStyle("Fusion")
        app = QtWidgets.QApplication.instance()
        if app:
            app.setStyleSheet(qss_for(self.theme_palette))
        self._refresh_icons()
        self._apply_header_styles()

    def _refresh_icons(self) -> None:
        col = self.theme_palette["fg"] if self.theme_palette else "#fff"
        self.btnStart.setIcon(icon_stop(22, col) if self.monitoring else icon_play(22, col))

    def _apply_header_styles(self) -> None:
        if not self.theme_palette:
            return
        pal = self.theme_palette
        header_style = (
            f"QHeaderView::section {{"
            f"background: rgba(255,255,255,0.08);"
            f"color: {pal['fg']};"
            f"border: 0;"
            f"border-bottom: 1px solid {pal['border']};"
            f"padding: 8px 10px; }}"
        )
        for t in (self.table, self.sessionTable):
            try:
                t.horizontalHeader().setStyleSheet(header_style)
            except Exception:
                pass

    def _on_player_state(self, state) -> None:
        try:
            if state == QMediaPlayer.PlaybackState.StoppedState and self.current_play:
                btn_ref, _path = self.current_play
                btn = btn_ref() if callable(btn_ref) else None
                if btn:
                    btn.setIcon(icon_play(18, self.theme_palette['fg'] if self.theme_palette else '#fff'))
                    setattr(btn, "_is_playing", False)
                self.current_play = None
        except Exception:
            pass

    # ---- settings ----
    def _sens_changed(self, v: int) -> None:
        self.threshold_db = v
        self.lblSens.setText(f"{T[self.lang]['sensitivity']} ({v} dB)")

    def _minlen_changed(self, v: int) -> None:
        self.min_len_s = v
        self.lblMin.setText(f"{T[self.lang]['minlen']} ({v} s)")

    def _maxlen_changed(self, v: int) -> None:
        self.max_len_s = v
        if v <= 0:
            self.lblMax.setText(f"{T[self.lang]['maxlen']} (∞)")
        else:
            self.lblMax.setText(f"{T[self.lang]['maxlen']} ({v} s)")

    def _show_help(self) -> None:
        QtWidgets.QMessageBox.information(self, T[self.lang]["help"], T[self.lang].get("help_text", ""))

    def _show_help_context(self, ctx: str) -> None:
        base = T[self.lang].get("help_text", "")
        if ctx == "clips":
            extra = ("\n\nCLIPS LIST:\n- Time: date/time when clip was saved.\n- Length: duration of the clip."
                     "\n- Play/Stop: preview.\n- Delete: remove file from disk.")
        elif ctx == "history":
            extra = ("\n\nHISTORY:\n- Day: localized day name.\n- Time: recording date.\n- Start/End: session times."
                     "\n- Sleep Duration: total hours/minutes (HH:MM).")
        else:
            extra = ""
        QtWidgets.QMessageBox.information(self, T[self.lang]["help"], base + extra)

    def _show_about(self) -> None:
        QtWidgets.QMessageBox.about(
            self, T[self.lang]["about"],
            '<b>SleepyPenguin — Sleep Tracker (PyQt6)</b><br>'
            'Created by Nele using ChatGPT<br>'
            'License: GPL-3.0-only<br><br>'
            '<b>Features</b><br>'
            '• Start/Stop microphone monitoring<br>'
            '• Auto-record to ./recordings when level crosses threshold (pre-roll & hang time + hysteresis)<br>'
            '• Live microphone meter (dB and percentage)<br>'
            '• Per-clip list with Play/Stop and Delete<br>'
            '• Themed UI (System/Indigo Night/Neon Black/Nord/Solarized/Light Minimal/Purple Waves)<br>'
            '• Language switcher (EN/HR/DE) with instant relabeling<br>'
            '• Sleep session history (with Day/Start/End/Sleep Duration)<br>'
            '• System theme detection (incl. KDE)<br><br>'
            '<b>Setup helper</b><br>'
            'Run: <code>python "Sleep tracker.py" --setup</code><br>'
            'Detects your Linux distro and installs system packages for PortAudio/ALSA + GStreamer + libsndfile (needs sudo),<br>'
            'then pip-installs PyQt6, numpy, sounddevice, soundfile.<br>'
            'Sudo je potreban jer se instaliraju <i>sistemske</i> biblioteke.'
        )

    def _show_license(self) -> None:
        paths = [
            os.path.join(os.getcwd(), "LICENSE.MD"),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "LICENSE.MD"),
            os.path.join(os.getcwd(), "LICENSE"),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "LICENSE"),
        ]
        text = ""
        for path in paths:
            try:
                if os.path.exists(path):
                    with open(path, "r", encoding="utf-8", errors="ignore") as f:
                        text = f.read()
                        break
            except Exception:
                pass
        if not text:
            text = ("SleepyPenguin — Sleep Tracker\n"
                    "GPL-3.0-only. See https://www.gnu.org/licenses/gpl-3.0.html\n")
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle(T[self.lang]["license"])
        dlg.resize(820, 620)
        v = QtWidgets.QVBoxLayout(dlg)
        info = QtWidgets.QLabel("LICENSE.MD (read-only)")
        info.setProperty("class", "badge")
        v.addWidget(info)
        editor = QtWidgets.QPlainTextEdit()
        editor.setPlainText(text)
        editor.setReadOnly(True)
        v.addWidget(editor, 1)
        btns = QtWidgets.QHBoxLayout()
        btns.addStretch(1)
        btnCopy = QtWidgets.QPushButton("Copy")
        btnClose = QtWidgets.QPushButton("Close")
        btns.addWidget(btnCopy)
        btns.addWidget(btnClose)
        v.addLayout(btns)
        btnCopy.clicked.connect(lambda: QtWidgets.QApplication.clipboard().setText(text))
        btnClose.clicked.connect(dlg.accept)
        dlg.exec()

    # ---- timers & audio ----
    def _wire_timers(self) -> None:
        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(50)
        self.timer.timeout.connect(self._drain_audio)
        self.timer.start()

    def _toggle_monitor(self) -> None:
        if not self.monitoring:
            try:
                self.stream = sd.InputStream(
                    samplerate=self.RATE, channels=self.CH, callback=self._cb, blocksize=self.BLOCK
                )
                self.stream.start()
                self.monitoring = True
                self.session_start = QtCore.QDateTime.currentDateTime()
                self.btnStart.setText(T[self.lang]["stop"])
                self._refresh_icons()
                self.above_ms = self.below_ms = 0.0
                self.capturing = False
                self.capture_frames.clear()
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Audio error", str(e))
        else:
            if self.stream:
                self.stream.stop()
                self.stream.close()
                self.stream = None
            self.monitoring = False
            self._finalize_clip(force=True)
            self.btnStart.setText(T[self.lang]["start"])
            self._refresh_icons()
            if self.session_start:
                end = QtCore.QDateTime.currentDateTime()
                dur = int(self.session_start.msecsTo(end) / 1000)
                self._save_session(self.session_start, end, dur)
                self.session_start = None
                self._refresh_history()

    def _cb(self, indata, frames, time, status) -> None:
        if status:
            pass
        self.q.put(indata.copy())

    def _drain_audio(self) -> None:
        while not self.q.empty():
            block = self.q.get()
            block_ms = len(block) / self.RATE * 1000.0
            rms = float(np.sqrt(np.mean(np.square(block)) + self.EPS))
            inst_db = 20.0 * np.log10(rms + self.EPS)
            self.smooth_db = self.EMA_ALPHA * inst_db + (1.0 - self.EMA_ALPHA) * self.smooth_db
            self.lblDb.setText(f"{inst_db:0.1f} dB")
            self.levelBar.setValue(max(0, min(100, int((inst_db + 60) * (100.0 / 60.0)))))

            if not self.monitoring:
                continue

            start_th = self.threshold_db
            stop_th = self.threshold_db - 6.0  # hystereza
            above = self.smooth_db >= start_th
            self.preroll.append(block)

            if above:
                self.above_ms += block_ms
                self.below_ms = 0.0
            else:
                self.below_ms += block_ms
                self.above_ms = 0.0

            if not self.capturing and self.above_ms >= self.ARM_MS:
                self._start_capture()

            if self.capturing:
                self.capture_frames.append(block)
                try:
                    self.capture_samples += block.shape[0]
                except Exception:
                    pass
                hit_hysteresis = self.smooth_db < stop_th and self.below_ms >= self.HANG_MS
                hit_max = self.max_len_s > 0 and (self.capture_samples / self.RATE) >= self.max_len_s
                if hit_hysteresis or hit_max:
                    self._finalize_clip()

    def _start_capture(self) -> None:
        self.capturing = True
        self.capture_frames = list(self.preroll)
        try:
            self.capture_samples = sum(b.shape[0] for b in self.capture_frames)
        except Exception:
            self.capture_samples = 0
        self.preroll.clear()

    def _finalize_clip(self, force: bool = False) -> None:
        if not self.capturing and not force:
            return
        frames = self.capture_frames if self.capturing else []
        self.capturing = False
        self.capture_frames = []
        self.above_ms = self.below_ms = 0.0
        if not frames:
            return
        data = np.concatenate(frames, axis=0)
        dur = data.shape[0] / self.RATE
        if (not force) and (dur < self.min_len_s):
            return
        # Prefer OGG Vorbis (smaller). Fallback to WAV ako nema soundfile.
        try:
            import soundfile as sf
            fname = datetime.datetime.now().strftime("%Y%m%d_%H%M%S") + ".ogg"
            path = os.path.join(self.out_dir, fname)
            sf.write(path, data.astype("float32"), self.RATE, format="OGG", subtype="VORBIS")
        except Exception:
            import wave as _w
            data16 = np.clip(data, -1.0, 1.0)
            data16 = (data16 * 32767.0).astype(np.int16)
            fname = datetime.datetime.now().strftime("%Y%m%d_%H%M%S") + ".wav"
            path = os.path.join(self.out_dir, fname)
            with _w.open(path, "wb") as wf:
                wf.setnchannels(self.CH)
                wf.setsampwidth(2)
                wf.setframerate(self.RATE)
                wf.writeframes(data16.tobytes())
        self._add_row(path, dur)
        self.capture_samples = 0

    # ---- playback helpers ----
    def _stop_current(self) -> None:
        if not self.current_play:
            try:
                self.player.stop()
            except Exception:
                pass
            return
        try:
            btn_ref, _path = self.current_play
        except Exception:
            self.current_play = None
            try:
                self.player.stop()
            except Exception:
                pass
            return
        try:
            self.player.stop()
        except Exception:
            pass
        btn = btn_ref() if callable(btn_ref) else None
        if btn:
            try:
                btn.setIcon(icon_play(18, self.theme_palette["fg"] if self.theme_palette else "#fff"))
                setattr(btn, "_is_playing", False)
            except Exception:
                pass
        self.current_play = None

    # ---- recordings table ops ----
    def _add_row(self, path: str, dur: float) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QtWidgets.QTableWidgetItem(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        self.table.setItem(row, 1, QtWidgets.QTableWidgetItem(f"{dur:.1f}s"))
        fg = self.theme_palette["fg"] if self.theme_palette else "#fff"

        btnPlay = QtWidgets.QPushButton()
        btnPlay.setIcon(icon_play(18, fg))
        btnPlay.setProperty("variant", "ghost")
        btnPlay.clicked.connect(lambda _, p=path, b=btnPlay: self._playstop(p, b))
        self.table.setCellWidget(row, 2, btnPlay)

        btnDel = QtWidgets.QPushButton()
        btnDel.setIcon(icon_trash(16, fg))
        btnDel.setProperty("variant", "ghost")
        btnDel.clicked.connect(lambda _, b=btnDel, p=path: self._delete_btn(b, p))
        self.table.setCellWidget(row, 3, btnDel)

    def _playstop(self, path: str, btn: QtWidgets.QPushButton) -> None:
        # toggle ako je isti fajl i već svira
        if getattr(btn, "_is_playing", False) and self.current_play and \
           self.current_play[1] == path and \
           self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._stop_current()
            return

        # stop bilo što što već svira
        self._stop_current()
        try:
            url = QtCore.QUrl.fromLocalFile(path)
            self.player.setSource(url)
            self.player.play()
            btn.setIcon(icon_stop(18, self.theme_palette["fg"] if self.theme_palette else "#fff"))
            btn._is_playing = True
            self.current_play = (weakref.ref(btn), path)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Play error", str(e))
            self._stop_current()

    def _delete_btn(self, btn: QtWidgets.QPushButton, path: str) -> None:
        # pronađi red gdje je ovaj gumb (red se može pomaknuti nakon brisanja)
        row = -1
        try:
            for r in range(self.table.rowCount()):
                if self.table.cellWidget(r, 3) is btn:
                    row = r
                    break
        except Exception:
            row = -1
        if row == -1:
            # fallback – bar obriši datoteku
            try:
                if os.path.exists(path):
                    os.remove(path)
            except Exception as e:
                QtWidgets.QMessageBox.warning(self, "Delete", f"Cannot delete file:\n{e}")
            return
        self._delete(path, row)

    def _delete(self, path: str, row: int) -> None:
        self._stop_current()
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Delete", f"Cannot delete file:\n{e}")
        self.table.removeRow(row)

    # ---- sessions/history ----
    def _load_sessions(self) -> list:
        if not os.path.exists(self.sessions_file):
            return []
        try:
            with open(self.sessions_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def _save_session(self, start_dt: QtCore.QDateTime, end_dt: QtCore.QDateTime, dur_s: int) -> None:
        rec = {
            "start": start_dt.toString(QtCore.Qt.DateFormat.ISODate),
            "end": end_dt.toString(QtCore.Qt.DateFormat.ISODate),
            "duration_s": dur_s,
        }
        self.sessions.append(rec)
        try:
            with open(self.sessions_file, "w", encoding="utf-8") as f:
                json.dump(self.sessions, f, ensure_ascii=False, indent=2)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Save session", f"Cannot save session log:\n{e}")

    def _refresh_history(self) -> None:
        if not hasattr(self, "sessionTable"):
            return
        self.sessionTable.setRowCount(0)
        days = T[self.lang].get("days", ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])
        for rec in self.sessions:
            try:
                s = datetime.datetime.fromisoformat(rec["start"])
                e = datetime.datetime.fromisoformat(rec["end"])
            except Exception:
                continue
            dur = int(rec.get("duration_s", int((e - s).total_seconds())))
            r = self.sessionTable.rowCount()
            self.sessionTable.insertRow(r)
            day_name = days[s.weekday()] if 0 <= s.weekday() < 7 else ""
            self.sessionTable.setItem(r, 0, QtWidgets.QTableWidgetItem(day_name))
            self.sessionTable.setItem(r, 1, QtWidgets.QTableWidgetItem(s.strftime("%Y-%m-%d")))
            self.sessionTable.setItem(r, 2, QtWidgets.QTableWidgetItem(s.strftime("%H:%M")))
            self.sessionTable.setItem(r, 3, QtWidgets.QTableWidgetItem(e.strftime("%H:%M")))
            self.sessionTable.setItem(r, 4, QtWidgets.QTableWidgetItem(f"{dur // 3600:02d}:{(dur % 3600) // 60:02d}"))

    # ---- tray helpers ----
    def _tray_show(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _tray_exit(self) -> None:
        try:
            if self.stream:
                self.stream.stop()
                self.stream.close()
        except Exception:
            pass
        try:
            self.player.stop()
        except Exception:
            pass
        QtWidgets.QApplication.quit()

    def closeEvent(self, e: QtGui.QCloseEvent) -> None:
        # Hide to tray; “Exit” iz tray menija za pravo gašenje
        if hasattr(self, "tray") and self.tray.isVisible():
            e.ignore()
            self.hide()
        else:
            super().closeEvent(e)


# ===================== boot =====================
def main() -> None:
    # upozorenje ako PortAudio nije spreman
    try:
        test = sd.InputStream(samplerate=44100, channels=1, blocksize=256)
        test.close()
    except Exception:
        d = detect_distro()
        print("[audio] PortAudio missing/misconfigured. Distro:", d)
        print(system_install_cmd(d))
        print("Or run this script with --setup (needs sudo).")

    # stišaj QtMultimedia/FFmpeg log spam
    try:
        QtCore.qputenv(
            b"QT_LOGGING_RULES",
            b"qt.multimedia.ffmpeg.debug=false;qt.multimedia.ffmpeg.mediasource.debug=false;"
            b"qt.multimedia.ffmpeg.muxer.debug=false;qt.multimedia.ffmpeg.demuxer.debug=false",
        )
    except Exception:
        pass

    app = QtWidgets.QApplication(sys.argv)
    w = SleepTracker()
    w.apply_system_theme()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
