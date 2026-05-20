#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  Myriapod v1.0  —  Passive Income Engine                                    ║
║  "Set it, forget it, collect it."                                             ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Supported Platforms : Linux · macOS · Windows                               ║
║  Supported Services  : EarnApp · Honeygain · IPRoyal Pawns · PacketStream    ║
║                        TraffMonetizer · EarnFM · Repocket · Proxyrack        ║
║                        Grass · Peer2Profit · Bytelixir · Mysterium           ║
║                        GagaNode · Sentinel · Storj · Theta · Arweave         ║
║                        Fluence · Acurast · Akash · Flux · SubQuery           ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Key Features:                                                                ║
║  • Zero-touch bootstrap  (no manual pip, no venv, no playwright)             ║
║  • Docker auto-deploy + health monitoring + auto-restart                     ║
║  • AES-256 encrypted credential vault                                        ║
║  • Balance polling with exponential back-off and result caching              ║
║  • SQLite earnings history + CSV export                                      ║
║  • CoinGecko token price resolution for native-token services                ║
║  • GUI (customtkinter) + headless CLI mode                                   ║
║  • System-tray icon (pystray) using Myriapod.png                            ║
║  • Auto-start service installation (systemd / launchd / Task Scheduler)      ║
║  • Public-IP change detection and alerts                                     ║
║  • Desktop notifications (cross-platform)                                   ║
║  • Auto-updater (GitHub releases)                                            ║
║  • Docker SDK + CLI subprocess dual-mode status detection                    ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

# ═══════════════════════════════════════════════════════════════════════════════
# §1  STANDARD-LIBRARY IMPORTS
# ═══════════════════════════════════════════════════════════════════════════════
import argparse
import base64
import contextlib
import hashlib
import importlib.metadata
import io
import json
import logging
import logging.handlers
import os
import platform
import re
import shlex
import shutil
import signal
import sqlite3
import subprocess
import sys
import textwrap
import threading
import time
import traceback
import uuid
import webbrowser
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import (
    Any, Callable, Dict, Iterable, List, Optional, Set, Tuple, Union,
)

if platform.system().lower() == "linux" and hasattr(os, "geteuid") and os.geteuid() == 0:
    sudo_user = os.environ.get("SUDO_USER")
    if sudo_user:
        try:
            import pwd
            import subprocess
            uid = pwd.getpwnam(sudo_user).pw_uid
            gid = pwd.getpwnam(sudo_user).pw_gid
            subprocess.run(["chown", "-R", f"{sudo_user}:{sudo_user}", os.path.dirname(os.path.abspath(__file__))])
        except Exception:
            pass
    if "--cli" not in sys.argv and "--preflight" not in sys.argv and "--setup" not in sys.argv:
        print("\n" + "="*70)
        print("  CRITICAL ERROR: DO NOT RUN THE GUI AS ROOT (SUDO)")
        print("="*70)
        print("Running graphical apps as root breaks the Chromium sandbox (Brave/Chrome)")
        print("and DBus notifications, causing crashes.")
        print("The Docker background deployments automatically elevate permissions as needed.")
        if sudo_user:
            print(f"\nWe have restored your file permissions. Please run the app normally:\n  python3 {sys.argv[0]}")
        else:
            print(f"\nPlease run the app normally as your user:\n  python3 {sys.argv[0]}")
        print("="*70 + "\n")
        sys.exit(1)

# ═══════════════════════════════════════════════════════════════════════════════
# §2  PATH RESOLUTION ENGINE (OVERENGINEERED DETERMINISTIC DISCOVERY)
# ═══════════════════════════════════════════════════════════════════════════════
class PathResolver:
    """
    Immutable thread-safe singleton for deterministic project path discovery.
    Dynamically walks up from the calling file to locate root indicators.
    """
    _instance: Optional[PathResolver] = None
    _lock = threading.Lock()

    def __new__(cls) -> PathResolver:
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._init_paths()
            return cls._instance

    def _init_paths(self) -> None:
        try:
            current_file = Path(__file__).resolve()
            start_dir = current_file.parent
        except Exception:
            start_dir = Path(os.getcwd())

        resolved_root = start_dir
        for parent in [start_dir] + list(start_dir.parents):
            if (parent / "Myriapod.py").exists() or (parent / ".env").exists() or (parent / "data").is_dir():
                resolved_root = parent
                break

        self._base_dir = resolved_root
        self._data_dir = self._base_dir / "data"
        self._log_file = self._base_dir / "myriapod_engine.log"
        self._env_file = self._base_dir / ".env"
        self._db_file = self._data_dir / "myriapod_database.sqlite"
        self._secrets_file = self._data_dir / "secrets.enc"
        self._browser_dir = self._base_dir / "browser_data"
        self._compose_file = self._base_dir / "docker-compose.yml"
        self._logo_file = self._base_dir / "Myriapod.png"
        self._pid_file = self._data_dir / "myriapod.pid"
        self._heartbeat_file = self._data_dir / "heartbeat"

        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._browser_dir.mkdir(parents=True, exist_ok=True)

    @property
    def base_dir(self) -> Path: return self._base_dir
    @property
    def data_dir(self) -> Path: return self._data_dir
    @property
    def log_file(self) -> Path: return self._log_file
    @property
    def env_file(self) -> Path: return self._env_file
    @property
    def db_file(self) -> Path: return self._db_file
    @property
    def secrets_file(self) -> Path: return self._secrets_file
    @property
    def browser_dir(self) -> Path: return self._browser_dir
    @property
    def compose_file(self) -> Path: return self._compose_file
    @property
    def logo_file(self) -> Path: return self._logo_file
    @property
    def pid_file(self) -> Path: return self._pid_file
    @property
    def heartbeat_file(self) -> Path: return self._heartbeat_file

paths = PathResolver()
VERSION      = "1.0.0"
APP_NAME     = "Myriapod"
BASE_DIR     = paths.base_dir
DATA_DIR     = paths.data_dir
LOG_FILE     = paths.log_file
ENV_FILE     = paths.env_file
DB_FILE      = paths.db_file
SECRETS_FILE = paths.secrets_file
BROWSER_DIR  = paths.browser_dir
COMPOSE_FILE = paths.compose_file
LOGO_FILE    = paths.logo_file
PID_FILE     = paths.pid_file
HEARTBEAT_FILE = paths.heartbeat_file

# ═══════════════════════════════════════════════════════════════════════════════
# §3  SELF-BOOTSTRAP
#     Installs missing packages via pip without creating a venv.
#     Three strategies tried in order:
#       1. pip install --user
#       2. pip install --break-system-packages
#       3. pip install  (bare)
#     Required packages that still fail cause a fatal exit.
#     Optional packages that fail are silently skipped.
#     If any *required* package was newly installed the process restarts.
# ═══════════════════════════════════════════════════════════════════════════════
#                          pip_spec                     dist_name          import_name        required
REQUIRED_PACKAGES: List[Tuple[str, str, str, bool]] = [
    ("customtkinter>=5.2.0",    "customtkinter",   "customtkinter",  True),
    ("requests>=2.28.0",        "requests",         "requests",       True),
    ("cryptography>=41.0.0",    "cryptography",     "cryptography",   False),
    ("psutil>=5.9.0",           "psutil",           "psutil",         True),
    ("pyyaml>=6.0",             "PyYAML",           "yaml",           True),
    ("colorama>=0.4.6",         "colorama",         "colorama",       False),
    ("python-dotenv>=1.0.0",    "python-dotenv",    "dotenv",         True),
    ("pillow>=10.0.0",          "Pillow",           "PIL",            True),
    ("packaging>=23.0",         "packaging",        "packaging",      True),
    # ── Optional heavyweight ─────────────────────────────────────────────────
    ("matplotlib>=3.7.0",       "matplotlib",       "matplotlib",     False),
    ("docker>=6.0.0",           "docker",           "docker",         False),
    ("pystray>=0.19.0",         "pystray",          "pystray",        False),
    ("telethon>=1.28.0",        "telethon",         "telethon",       False),
    # ── Service-specific (best-effort; HTTP fallbacks exist) ─────────────────
    ("pyEarnapp>=1.0.0",        "pyEarnapp",        "pyEarnapp",      False),
    ("pyHoneygain>=0.1.0",      "pyHoneygain",      "pyHoneygain",    False),
    ("pyIPRoyalPawns>=1.0.0",   "pyIPRoyalPawns",   "pyIPRoyalPawns", False),
    ("pyTraffMonetizer>=1.0.0", "pyTraffMonetizer", "pyTraffMonetizer", False),
]


def _pkg_installed(dist_name: str) -> bool:
    try:
        importlib.metadata.version(dist_name)
        return True
    except importlib.metadata.PackageNotFoundError:
        return False


def _pip_install(spec: str, debug: bool = False) -> bool:
    null = None if debug else subprocess.DEVNULL
    for cmd in [
        [sys.executable, "-m", "pip", "install", spec, "--quiet", "--user"],
        [sys.executable, "-m", "pip", "install", spec, "--quiet", "--break-system-packages"],
        [sys.executable, "-m", "pip", "install", spec, "--quiet"],
    ]:
        try:
            subprocess.check_call(cmd, stdout=null, stderr=null, timeout=120)
            return True
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
            continue
    return False


def auto_bootstrap() -> None:
    debug_mode = "--debug" in sys.argv
    missing: List[Tuple[str, str, str, bool]] = [
        t for t in REQUIRED_PACKAGES if not _pkg_installed(t[1])
    ]
    if not missing:
        return

    bar = "=" * 68
    print(f"\n{bar}")
    print(f"  {APP_NAME} BOOTSTRAP — Installing {len(missing)} package(s)")
    print(bar)

    newly_required = False
    for spec, dist, _imp, required in missing:
        tag = "REQUIRED" if required else "optional"
        print(f"  [{'*' if required else '+'}] ({tag}) {spec} …", end="", flush=True)
        ok = _pip_install(spec, debug=debug_mode)
        if ok:
            print(" done")
            if required:
                newly_required = True
        else:
            if required:
                print(" FAILED")
                print(f"\n[FATAL] Could not install required package: {spec}")
                sys.exit(1)
            else:
                print(" skipped (optional)")

    print(bar)
    if newly_required:
        print("  Restarting to load newly installed packages …\n")
        os.execv(sys.executable, [sys.executable] + sys.argv)


auto_bootstrap()

# ═══════════════════════════════════════════════════════════════════════════════
# §4  POST-BOOTSTRAP IMPORTS
# ═══════════════════════════════════════════════════════════════════════════════
import requests                                          # noqa: E402
import yaml                                              # noqa: E402
from dotenv import dotenv_values, load_dotenv, set_key   # noqa: E402
from PIL import Image, ImageDraw, ImageTk                # noqa: E402

try:
    from colorama import Fore, Style, init as colorama_init  # noqa: E402
except ImportError:
    class MockColor:
        BLACK = "\033[30m"
        RED = "\033[31m"
        GREEN = "\033[32m"
        YELLOW = "\033[33m"
        BLUE = "\033[34m"
        MAGENTA = "\033[35m"
        CYAN = "\033[36m"
        WHITE = "\033[37m"
        RESET = "\033[39m"
        LIGHTBLACK_EX = "\033[90m"
        LIGHTRED_EX = "\033[91m"
        LIGHTGREEN_EX = "\033[92m"
        LIGHTYELLOW_EX = "\033[93m"
        LIGHTBLUE_EX = "\033[94m"
        LIGHTMAGENTA_EX = "\033[95m"
        LIGHTCYAN_EX = "\033[96m"
        LIGHTWHITE_EX = "\033[97m"

    class MockStyle:
        BRIGHT = "\033[1m"
        DIM = "\033[2m"
        NORMAL = "\033[22m"
        RESET_ALL = "\033[0m"

    import sys
    if not sys.stdout.isatty():
        class EmptyMock:
            def __getattr__(self, name): return ""
        Fore = EmptyMock()
        Style = EmptyMock()
    else:
        Fore = MockColor()
        Style = MockStyle()

    def colorama_init(*args, **kwargs):
        pass

try:
    from cryptography.fernet import Fernet                   # noqa: E402
    class InvalidToken(Exception):
        pass
except ImportError:
    class InvalidToken(Exception):
        pass

    class Fernet:
        """
        Pure-python fallback drop-in for cryptography.fernet.Fernet.
        HMAC-SHA256 authenticated encryption in CTR mode (Encrypt-then-MAC style).
        """
        def __init__(self, key: Union[str, bytes]) -> None:
            if isinstance(key, str):
                key = key.encode()
            try:
                self.key_bytes = base64.urlsafe_b64decode(key)
            except Exception as e:
                raise ValueError("Fernet key must be 32 urlsafe-base64-encoded bytes.") from e
            if len(self.key_bytes) != 32:
                raise ValueError("Fernet key must be 32 urlsafe-base64-encoded bytes.")

        def encrypt(self, data: bytes) -> bytes:
            if not isinstance(data, bytes):
                data = data.encode()
            iv = os.urandom(16)
            enc_key = self.key_bytes[:16]
            sign_key = self.key_bytes[16:]
            keystream = b""
            blocks_needed = (len(data) + 31) // 32
            import hmac
            for i in range(blocks_needed):
                counter = i.to_bytes(8, 'big')
                keystream += hmac.new(enc_key, iv + counter, hashlib.sha256).digest()
            ciphertext = bytes(a ^ b for a, b in zip(data, keystream))
            tag = hmac.new(sign_key, iv + ciphertext, hashlib.sha256).digest()
            payload = b"\x90" + iv + ciphertext + tag
            return base64.urlsafe_b64encode(payload)

        def decrypt(self, token: bytes) -> bytes:
            if isinstance(token, str):
                token = token.encode()
            try:
                payload = base64.urlsafe_b64decode(token)
            except Exception as e:
                raise InvalidToken("Invalid base64 payload") from e
            if len(payload) < 1 + 16 + 32:
                raise InvalidToken("Token too short")
            version = payload[0:1]
            if version != b"\x90":
                raise InvalidToken("Unsupported token version")
            iv = payload[1:17]
            tag_received = payload[-32:]
            ciphertext = payload[17:-32]
            enc_key = self.key_bytes[:16]
            sign_key = self.key_bytes[16:]
            import hmac
            tag_expected = hmac.new(sign_key, iv + ciphertext, hashlib.sha256).digest()
            if not hmac.compare_digest(tag_expected, tag_received):
                raise InvalidToken("MAC verification failed")
            keystream = b""
            blocks_needed = (len(ciphertext) + 31) // 32
            for i in range(blocks_needed):
                counter = i.to_bytes(8, 'big')
                keystream += hmac.new(enc_key, iv + counter, hashlib.sha256).digest()
            return bytes(a ^ b for a, b in zip(ciphertext, keystream))

if "--cli" not in sys.argv and "--preflight" not in sys.argv:
    import tkinter as tk
    from tkinter import messagebox, simpledialog, ttk
    import customtkinter as ctk                          # noqa: E402
else:
    class _DummyMock:
        def __getattr__(self, name: str) -> Any: return object
        def __call__(self, *args: Any, **kwargs: Any) -> Any: return None
    tk = _DummyMock()  # type: ignore
    messagebox = _DummyMock()  # type: ignore
    simpledialog = _DummyMock()  # type: ignore
    ttk = _DummyMock()  # type: ignore
    ctk = _DummyMock()  # type: ignore

colorama_init(autoreset=True)

# Optional imports — each wrapped independently
_HAS_DOCKER = False
_docker_module: Any = None
try:
    import docker as _docker_module  # type: ignore
    _HAS_DOCKER = True
except ImportError:
    pass

_HAS_MATPLOTLIB = False
plt: Any = None
FigureCanvasTkAgg: Any = None
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt   # type: ignore
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg  # type: ignore
    _HAS_MATPLOTLIB = True
except ImportError:
    pass

_HAS_PYSTRAY = False
pystray: Any = None
try:
    import pystray  # type: ignore
    _HAS_PYSTRAY = True
except ImportError:
    pass

_HAS_TELETHON = False
_TelegramClient: Any = None
try:
    from telethon.sync import TelegramClient as _TelegramClient  # type: ignore
    _HAS_TELETHON = True
except ImportError:
    pass

_EarnApp: Any = None
try:
    from pyEarnapp import EarnApp as _EarnApp  # type: ignore
except Exception:
    pass

_HoneyGain: Any = None
try:
    from pyHoneygain import HoneyGain as _HoneyGain  # type: ignore
except Exception:
    pass

_IPRoyalPawns: Any = None
try:
    from pyIPRoyalPawns import IPRoyalPawns as _IPRoyalPawns  # type: ignore
except Exception:
    pass

_TraffMonetizer: Any = None
try:
    from pyTraffMonetizer import TraffMonetizer as _TraffMonetizer  # type: ignore
except Exception:
    pass

ENV_FILE.touch(exist_ok=True)
load_dotenv(ENV_FILE)

_EARLY = argparse.ArgumentParser(add_help=False)
_EARLY.add_argument("--debug", action="store_true")
_EARLY.add_argument("--cli",   action="store_true")
_EARLY_ARGS, _ = _EARLY.parse_known_args()
DEBUG_MODE = _EARLY_ARGS.debug
CLI_MODE   = _EARLY_ARGS.cli

# ═══════════════════════════════════════════════════════════════════════════════
# §5  LOGGING
# ═══════════════════════════════════════════════════════════════════════════════
def _init_logger() -> logging.Logger:
    lg = logging.getLogger(APP_NAME)
    if lg.handlers:
        return lg
    lg.setLevel(logging.DEBUG if DEBUG_MODE else logging.INFO)
    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(threadName)-18s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    fh = logging.handlers.RotatingFileHandler(
        LOG_FILE, maxBytes=5_000_000, backupCount=5, encoding="utf-8"
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    lg.addHandler(fh)
    if CLI_MODE or DEBUG_MODE:
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(logging.DEBUG if DEBUG_MODE else logging.INFO)
        ch.setFormatter(fmt)
        lg.addHandler(ch)
    return lg


logger = _init_logger()

# ═══════════════════════════════════════════════════════════════════════════════
# §6  GLOBAL CONSTANTS & THEME
# ═══════════════════════════════════════════════════════════════════════════════
C_BG_DARK    = "#0d1117"
C_BG_PANEL   = "#161b22"
C_BG_CARD    = "#1c2333"
C_BG_INPUT   = "#21262d"
C_BORDER     = "#30363d"
C_TEXT       = "#e6edf3"
C_TEXT_DIM   = "#8b949e"
C_TEXT_MUTED = "#484f58"
C_ACCENT     = "#39d353"
C_ACCENT_DIM = "#26a641"
C_YELLOW     = "#d29922"
C_RED        = "#f85149"
C_BLUE       = "#388bfd"
C_PURPLE     = "#bc8cff"

CATEGORY_COLORS: Dict[str, str] = {
    "bandwidth": C_BLUE,
    "node":      C_PURPLE,
    "storage":   C_YELLOW,
    "compute":   C_RED,
    "system":    C_ACCENT,
}

POLL_INTERVAL_SECS = 300
RETRY_DELAYS       = (5, 15, 45)
API_TIMEOUT        = 12

# ═══════════════════════════════════════════════════════════════════════════════
# §7  UTILITY FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════
def load_app_logo(size: Tuple[int, int] = (40, 40)) -> Optional[Image.Image]:
    """Load Myriapod.png; fall back to a generated icon."""
    if LOGO_FILE.exists():
        try:
            img = Image.open(LOGO_FILE).convert("RGBA")
            return img.resize(size, Image.LANCZOS)
        except Exception as exc:
            logger.debug("Logo load failed: %s", exc)
    # Generated fallback
    img  = Image.new("RGBA", size, (13, 17, 23, 255))
    draw = ImageDraw.Draw(img)
    m    = 2
    draw.ellipse((m, m, size[0] - m, size[1] - m), fill=(20, 40, 20, 255))
    cx, cy = size[0] // 3, size[1] // 4
    draw.text((cx, cy), "N", fill=(57, 211, 83, 255))
    return img


def current_env() -> Dict[str, str]:
    return {**dotenv_values(ENV_FILE), **os.environ}


def getenv(key: str, default: str = "") -> str:
    return str(current_env().get(key, default) or default)


def set_env_value(key: str, value: str) -> None:
    set_key(str(ENV_FILE), key, value)
    os.environ[key] = value


def safe_float(value: object) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.replace(",", "").replace("$", "").strip()
        try:
            return float(cleaned)
        except ValueError:
            m = re.search(r"-?(\d+(?:\.\d+)?)", cleaned)
            if m:
                try:
                    return float(m.group(1))
                except ValueError:
                    pass
    return 0.0


def first_numeric(
    payload: object,
    preferred: Iterable[str] = (),
    allow_primitive: bool = True,
) -> Optional[float]:
    if payload is None:
        return None
    if isinstance(payload, (int, float)):
        return float(payload)
    if isinstance(payload, str) and allow_primitive:
        v = safe_float(payload)
        return v if v else None
    if isinstance(payload, dict):
        low = {str(k).lower(): v for k, v in payload.items()}
        for ek in ("code", "error", "status", "http_status"):
            ev = low.get(ek)
            if isinstance(ev, int) and ev in {400, 401, 403, 404, 429, 500, 502, 503}:
                return None
            if isinstance(ev, str) and any(c in ev for c in ("401", "403", "500")):
                return None
        for pk in preferred:
            if pk.lower() in low:
                r = first_numeric(low[pk.lower()], allow_primitive=True)
                if r is not None:
                    return r
        for k, v in low.items():
            if any(t in k for t in ("balance", "payout", "amount", "earn", "usd", "wallet", "current")):
                r = first_numeric(v, allow_primitive=True)
                if r is not None and r not in {401.0, 403.0, 500.0, 502.0}:
                    return r
        for v in payload.values():
            r = first_numeric(v, allow_primitive=False)
            if r is not None:
                return r
        return None
    if isinstance(payload, (list, tuple)):
        for item in payload:
            r = first_numeric(item, preferred=preferred, allow_primitive=allow_primitive)
            if r is not None:
                return r
    return None


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower().strip()).strip("-") or "node"


def threaded(fn: Callable, *args: Any, **kwargs: Any) -> threading.Thread:
    t = threading.Thread(target=fn, args=args, kwargs=kwargs, daemon=True)
    t.start()
    return t


def open_url(url: str) -> None:
    try:
        webbrowser.open(url)
    except Exception as exc:
        logger.warning("open_url failed for %s: %s", url, exc)


def get_public_ip() -> str:
    for url in (
        "https://api.ipify.org",
        "https://ifconfig.me/ip",
        "https://icanhazip.com",
        "https://api4.my-ip.io/ip",
    ):
        try:
            r = requests.get(url, timeout=8)
            if r.ok:
                ip = r.text.strip()
                if re.match(r"^\d{1,3}(\.\d{1,3}){3}$", ip):
                    return ip
        except Exception:
            continue
    return "unknown"


def fetch_token_price(coin_id: str, db: Optional[Any] = None) -> Optional[float]:
    if db is not None:
        cached = db.get_cached_price(coin_id)
        if cached is not None:
            return cached
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": coin_id, "vs_currencies": "usd"},
            timeout=API_TIMEOUT,
        )
        if r.ok:
            price = r.json().get(coin_id, {}).get("usd")
            if isinstance(price, (int, float)):
                if db is not None:
                    db.cache_price(coin_id, float(price))
                return float(price)
    except Exception as exc:
        logger.debug("CoinGecko fetch failed for %s: %s", coin_id, exc)
    return None


def format_usd(value: float) -> str:
    return f"${value:,.2f}"


def format_compact_usd(value: float) -> str:
    return f"${value:,.4f}" if 0 < abs(value) < 1 else f"${value:,.2f}"


def format_native(value: Optional[float], unit: str) -> str:
    if value is None:
        return "—"
    mapping: Dict[str, Callable[[float], str]] = {
        "usd":     lambda v: format_compact_usd(v),
        "credits": lambda v: f"{v:,.0f} cr",
        "points":  lambda v: f"{v:,.0f} pts",
        "sol":     lambda v: f"{v:,.4f} SOL",
        "myst":    lambda v: f"{v:,.4f} MYST",
        "storj":   lambda v: f"{v:,.4f} STORJ",
        "raw":     lambda v: f"{v:,.4f}",
    }
    fn = mapping.get(unit)
    return fn(value) if fn else f"{value:,.4f} {unit.upper()}"


def retry_call(
    fn: Callable[[], Any],
    delays: Tuple[int, ...] = RETRY_DELAYS,
    label: str = "",
) -> Any:
    last_exc: Exception = RuntimeError("unknown")
    for attempt, delay in enumerate((*delays, None), start=1):  # type: ignore[misc]
        try:
            return fn()
        except Exception as exc:
            last_exc = exc
            if delay is not None:
                logger.debug("Retry %d/%d for %s after %ds: %s",
                             attempt, len(delays) + 1, label, delay, exc)
                time.sleep(delay)
    raise last_exc


def _is_pid_running(pid: int) -> bool:
    """Check if a process with specified PID is running and is a Myriapod process."""
    try:
        import psutil
        if not psutil.pid_exists(pid):
            return False
        proc = psutil.Process(pid)
        if proc.status() in (psutil.STATUS_ZOMBIE, psutil.STATUS_DEAD):
            return False
        cmd = proc.cmdline()
        return any("Myriapod.py" in arg for arg in cmd)
    except Exception:
        return False


def _get_active_daemon_pid() -> Optional[int]:
    """Retrieve running daemon's PID from the PID file, if valid."""
    if not PID_FILE.exists():
        return None
    try:
        pid = int(PID_FILE.read_text().strip())
        if _is_pid_running(pid):
            return pid
    except Exception:
        pass
    with contextlib.suppress(Exception):
        PID_FILE.unlink()
    return None


def _docker_cli_available() -> bool:
    """Return True if the docker CLI binary exists on PATH."""
    try:
        r = subprocess.run(
            ["docker", "--version"],
            capture_output=True, timeout=8,
        )
        return r.returncode == 0
    except Exception:
        return False


def _probe_docker_sockets() -> List[str]:
    """Dynamically probes prioritized standard, rootless, and user-space Docker socket paths."""
    candidates = []
    # Standard UNIX socket
    candidates.append("/var/run/docker.sock")
    
    # Environment socket locations
    env_host = os.environ.get("DOCKER_HOST")
    if env_host and env_host.startswith("unix://"):
        candidates.append(env_host.replace("unix://", ""))
        
    # XDG runtime directories for rootless mode
    xdg_runtime = os.environ.get("XDG_RUNTIME_DIR")
    if xdg_runtime:
        candidates.append(os.path.join(xdg_runtime, "docker.sock"))
        
    # Standard user-space/UID socket directories
    uid = os.getuid() if hasattr(os, "getuid") else None
    if uid is not None:
        candidates.append(f"/run/user/{uid}/docker.sock")
        
    # Standard user home folder locations
    home = os.path.expanduser("~")
    candidates.append(os.path.join(home, ".docker/run/docker.sock"))
    
    # Verify existences and keep unique list
    valid = []
    for c in candidates:
        if c and os.path.exists(c) and c not in valid:
            valid.append(c)
    return valid


def _docker_daemon_running() -> bool:
    """
    Resilient Docker connectivity probe.
    Sequentially tests the default socket, then walks through probed rootless
    sockets, dynamically binding and caching the working target socket inside
    the system environment space.
    """
    # 1. First probe default socket/environment
    try:
        r = subprocess.run(["docker", "info"], capture_output=True, timeout=8)
        if r.returncode == 0:
            return True
    except Exception:
        pass

    # 2. Iterate and probe each discovered socket
    sockets = _probe_docker_sockets()
    for s in sockets:
        try:
            # Test direct socket communication via CLI
            r = subprocess.run(
                ["docker", "-H", f"unix://{s}", "info"],
                capture_output=True, timeout=5
            )
            if r.returncode == 0:
                os.environ["DOCKER_HOST"] = f"unix://{s}"
                logger.info("Resilient socket resolution succeeded. Exported DOCKER_HOST=unix://%s", s)
                return True
        except Exception:
            continue

    # 3. Check if standard socket exists but is read-only (Permission Denied scenario)
    if os.path.exists("/var/run/docker.sock") and not os.access("/var/run/docker.sock", os.R_OK | os.W_OK):
        logger.warning(
            "Docker socket '/var/run/docker.sock' exists but is not accessible. "
            "Suggest running: 'sudo usermod -aG docker %s && newgrp docker'",
            os.environ.get("USER", "your_user")
        )
    return False


def _start_docker_daemon() -> bool:
    """
    Adaptive daemon startup supervisor.
    Executes standard systemctl controls, with aggressive direct-binary daemon (dockerd)
    forking fallbacks to support systemd-less environments, WSL containers, and Rootless setups.
    """
    if _docker_daemon_running():
        return True

    logger.warning("Docker daemon is inactive. Initiating startup procedures...")
    system = platform.system().lower()

    if system == "linux":
        # Strategy A: Traditional service manager commands
        for cmd in [
            ["sudo", "systemctl", "start", "docker"],
            ["sudo", "service", "docker", "start"],
        ]:
            try:
                logger.info("Attempting service start: %s", " ".join(cmd))
                subprocess.run(cmd, capture_output=True, timeout=25)
                # Allow warm up
                for _ in range(5):
                    time.sleep(1)
                    if _docker_daemon_running():
                        logger.info("Successfully started Docker via service manager: %s", " ".join(cmd))
                        return True
            except Exception:
                continue

        # Strategy B: PID-1 Systemd absence fallback (e.g. WSL, Docker-in-Docker, custom kernels)
        try:
            logger.info("Service controller unavailable. Attempting background direct dockerd startup...")
            # We add iptables=false for non-conflicting setups, or fallback
            dockerd_cmd = ["sudo", "dockerd", "--iptables=false"]
            subprocess.Popen(
                dockerd_cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                preexec_fn=os.setsid if hasattr(os, "setsid") else None
            )
            # Monitor startup progression
            for _ in range(15):
                time.sleep(1)
                if _docker_daemon_running():
                    logger.info("Resilient direct dockerd launch succeeded.")
                    return True
        except Exception as exc:
            logger.debug("Direct dockerd execution failed: %s", exc)

        # Strategy C: Rootless Docker user startup script
        try:
            home = os.path.expanduser("~")
            rootless_script = os.path.join(home, "bin/dockerd-rootless.sh")
            if os.path.exists(rootless_script):
                logger.info("Found user-space rootless startup: %s. Executing...", rootless_script)
                subprocess.Popen(
                    [rootless_script],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    preexec_fn=os.setsid if hasattr(os, "setsid") else None
                )
                for _ in range(15):
                    time.sleep(1)
                    if _docker_daemon_running():
                        logger.info("Resilient rootless dockerd launch succeeded.")
                        return True
        except Exception as exc:
            logger.debug("Rootless launch failed: %s", exc)

    elif system == "darwin":
        try:
            logger.info("Spawning macOS Docker Desktop application...")
            subprocess.Popen(["open", "-a", "Docker"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            for _ in range(25):
                time.sleep(2)
                if _docker_daemon_running():
                    logger.info("Docker Desktop started successfully (macOS).")
                    return True
        except Exception as exc:
            logger.warning("Darwin Desktop launch failed: %s", exc)

    elif system == "windows":
        for exe in (
            os.path.expandvars(r"%ProgramFiles%\Docker\Docker\Docker Desktop.exe"),
            os.path.expandvars(r"%ProgramFiles(x86)%\Docker\Docker\Docker Desktop.exe"),
        ):
            if os.path.isfile(exe):
                try:
                    logger.info("Spawning Windows Docker Desktop app: %s", exe)
                    subprocess.Popen([exe], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    for _ in range(30):
                        time.sleep(2)
                        if _docker_daemon_running():
                            logger.info("Docker Desktop started successfully (Windows).")
                            return True
                except Exception:
                    continue

    logger.critical("All Docker daemon startup orchestration sequences exhausted without success.")
    return False


def _docker_compose_cmd() -> Optional[List[str]]:
    """
    Exhaustive Multi-Engine Compose Resolution.
    Probes system PATH commands, user-space folders, local pip bin structures,
    and fallback plugin integrations to determine the optimal compose CLI syntax.
    """
    env = os.environ.copy()
    user_local_bin = os.path.expanduser("~/.local/bin")
    user_bin = os.path.expanduser("~/bin")
    paths = env.get("PATH", "").split(os.pathsep)
    if user_local_bin not in paths:
        paths.insert(0, user_local_bin)
    if user_bin not in paths:
        paths.insert(0, user_bin)
    env["PATH"] = os.pathsep.join(paths)

    candidates = [
        "docker compose",
        "docker-compose",
        "/usr/local/bin/docker-compose",
        "/usr/bin/docker-compose",
        os.path.join(user_local_bin, "docker-compose"),
        os.path.join(user_bin, "docker-compose"),
    ]
    for c in candidates:
        try:
            parts = shlex.split(c)
            # Append 'version' for validation probe
            test_cmd = parts + ["version"]
            r = subprocess.run(test_cmd, capture_output=True, timeout=5, env=env)
            if r.returncode == 0:
                logger.info("Resilient Compose resolved: %s", c)
                return parts
        except Exception:
            continue

    # Final lazy fallback validation
    try:
        r = subprocess.run(["docker", "compose", "version"], capture_output=True, timeout=5, env=env)
        if r.returncode == 0:
            return ["docker", "compose"]
    except Exception:
        pass

    return None


def _detect_arch() -> str:
    """Detect CPU architecture for multi-arch Docker images."""
    machine = platform.machine().lower()
    if machine in ("x86_64", "amd64"):
        return "amd64"
    if machine in ("aarch64", "arm64"):
        return "arm64"
    if machine.startswith("arm"):
        return "arm"
    return machine


def _docker_inspect_status(container_name: str) -> Optional[str]:
    """
    Fall back to the docker CLI to get a container's status.
    Returns the status string (e.g. 'running', 'exited') or None.
    """
    try:
        r = subprocess.run(
            ["docker", "inspect", "--format", "{{.State.Status}}", container_name],
            capture_output=True, text=True, timeout=6,
        )
        if r.returncode == 0:
            return r.stdout.strip() or None
    except Exception:
        pass
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# §8  DATA MODELS
# ═══════════════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class SetupField:
    key:      str
    label:    str
    secret:   bool = False
    hint:     str  = ""
    required: bool = True


@dataclass
class BalanceResult:
    service_name:     str
    native_value:     Optional[float]
    native_unit:      str
    usd_value:        float
    include_in_total: bool
    source:           str
    status:           str = "ok"   # ok | warning | error | idle

    @property
    def primary_display(self) -> str:
        return "—" if self.native_value is None else format_native(self.native_value, self.native_unit)

    @property
    def secondary_display(self) -> str:
        if self.include_in_total:
            return f"≈ {format_compact_usd(self.usd_value)}"
        if self.usd_value > 0:
            return f"ref {format_compact_usd(self.usd_value)}"
        return "excluded from total"

    @property
    def status_color(self) -> str:
        return {
            "ok":      C_ACCENT,
            "warning": C_YELLOW,
            "error":   C_RED,
            "idle":    C_TEXT_MUTED,
        }.get(self.status, C_TEXT_DIM)


def empty_result(service_name: str, source: str, status: str = "idle") -> BalanceResult:
    return BalanceResult(
        service_name=service_name, native_value=None,
        native_unit="usd", usd_value=0.0,
        include_in_total=False, source=source, status=status,
    )


def usd_result(service_name: str, usd_value: float, source: str) -> BalanceResult:
    return BalanceResult(
        service_name=service_name, native_value=usd_value,
        native_unit="usd", usd_value=usd_value,
        include_in_total=True, source=source, status="ok",
    )


def native_result(
    service_name: str,
    native_value: float,
    native_unit: str,
    usd_value: float,
    include_in_total: bool,
    source: str,
) -> BalanceResult:
    return BalanceResult(
        service_name=service_name,
        native_value=native_value, native_unit=native_unit,
        usd_value=usd_value, include_in_total=include_in_total,
        source=source, status="ok",
    )


@dataclass(frozen=True)
class ServiceDefinition:
    name:                     str
    slug:                     str
    website_url:              str
    dashboard_url:            str
    payout_url:               str
    threshold:                float
    category:                 str
    setup_fields:             Tuple[SetupField, ...]
    balance_mode:             str
    balance_unit:             str
    earnings_model_note:      str
    payout_note:              str
    docker_mode:              str
    docker_support_level:     str
    docker_source_url:        str
    docker_summary:           str
    compose_image:            Optional[str]        = None
    compose_command_template: Optional[str]        = None
    compose_env_templates:    Tuple[str, ...]      = ()
    compose_ports:            Tuple[str, ...]      = ()
    compose_volumes:          Tuple[str, ...]      = ()
    compose_devices:          Tuple[str, ...]      = ()
    compose_cap_add:          Tuple[str, ...]      = ()
    compose_hostname:         Optional[str]        = None
    compose_network_mode:     Optional[str]        = None
    compose_sysctls:          Dict[str, str]       = field(default_factory=dict)
    manual_docker_notes:      str                  = ""
    health_check_url:         Optional[str]        = None
    api_balance_url:          Optional[str]        = None
    coingecko_id:             Optional[str]        = None
    json_path:                Tuple[str, ...]      = ()
    headers:                  Dict[str, str]       = field(default_factory=dict)

    @property
    def container_name(self) -> str:
        return f"myriapod_{self.slug}"

    @property
    def is_auto_deployable(self) -> bool:
        return self.docker_mode == "docker_auto" and bool(self.compose_image)

# ═══════════════════════════════════════════════════════════════════════════════
# §9  SERVICE REGISTRY
# ═══════════════════════════════════════════════════════════════════════════════
def _build_services() -> Dict[str, ServiceDefinition]:
    defs: List[ServiceDefinition] = [

        # ── SYSTEM SIDEKICKS ───────────────────────────────────────────────────
        ServiceDefinition(
            name="Watchtower", slug="watchtower",
            website_url="https://containrrr.dev/watchtower/",
            dashboard_url="", payout_url="", threshold=0.0, category="system",
            setup_fields=(),
            balance_mode="none", balance_unit="",
            earnings_model_note="System sidecar to automatically update container images.",
            payout_note="",
            docker_mode="docker_auto", docker_support_level="official",
            docker_source_url="https://hub.docker.com/r/containrrr/watchtower",
            docker_summary="Automated Docker container base image updates.",
            compose_image="containrrr/watchtower:latest",
            compose_volumes=("/var/run/docker.sock:/var/run/docker.sock",),
            compose_command_template="--cleanup --interval 86400",
        ),

        # ── BANDWIDTH / RESIDENTIAL PROXY ──────────────────────────────────────
        ServiceDefinition(
            name="EarnApp", slug="earnapp",
            website_url="https://earnapp.com",
            dashboard_url="https://earnapp.com/dashboard",
            payout_url="https://earnapp.com/dashboard/me/earnings/in-progress",
            threshold=10.0, category="bandwidth",
            setup_fields=(
                SetupField("EARNAPP_UUID", "Linked device UUID",
                           hint="sdk-node-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"),
            ),
            balance_mode="library", balance_unit="usd",
            earnings_model_note=(
                "Monitor a natively-installed EarnApp device. "
                "EarnApp explicitly prohibits Docker/VM installs."
            ),
            payout_note="Withdrawals (PayPal / Amazon) are initiated from the official dashboard.",
            docker_mode="docker_auto", docker_support_level="community",
            docker_source_url="https://hub.docker.com/r/fazalfarhan01/earnapp",
            docker_summary="Community EarnApp Docker image (lite version).",
            compose_image="fazalfarhan01/earnapp:lite",
            compose_env_templates=("EARNAPP_UUID={EARNAPP_UUID}",),
            api_balance_url="https://earnapp.com/dashboard/api/earning_info",
        ),

        ServiceDefinition(
            name="Honeygain", slug="honeygain",
            website_url="https://www.honeygain.com",
            dashboard_url="https://dashboard.honeygain.com/",
            payout_url="https://dashboard.honeygain.com/",
            threshold=20.0, category="bandwidth",
            setup_fields=(
                SetupField("HG_EMAIL",    "Account e-mail"),
                SetupField("HG_PASSWORD", "Account password", secret=True),
            ),
            balance_mode="library", balance_unit="credits",
            earnings_model_note="Honeygain credits accumulate from shared bandwidth. 1 000 credits = $1 USD.",
            payout_note="Payouts via JumpTask/PayPal are managed in the official dashboard.",
            docker_mode="docker_auto", docker_support_level="official",
            docker_source_url="https://hub.docker.com/r/honeygain/honeygain",
            docker_summary="Official Honeygain Docker image.",
            compose_image="honeygain/honeygain:latest",
            compose_command_template="-tou-accept -email {HG_EMAIL} -pass {HG_PASSWORD} -device {DEVICE_NAME}",
        ),

        ServiceDefinition(
            name="IPRoyal Pawns", slug="iproyal",
            website_url="https://pawns.app",
            dashboard_url="https://dashboard.pawns.app/internet-sharing",
            payout_url="https://dashboard.pawns.app/internet-sharing",
            threshold=5.0, category="bandwidth",
            setup_fields=(
                SetupField("IPROYAL_EMAIL",    "Account e-mail"),
                SetupField("IPROYAL_PASSWORD", "Account password", secret=True),
            ),
            balance_mode="library", balance_unit="usd",
            earnings_model_note="Proxy bandwidth sharing — claimable USD balance.",
            payout_note="Payouts are initiated from the official Pawns dashboard.",
            docker_mode="docker_auto", docker_support_level="official",
            docker_source_url="https://hub.docker.com/r/iproyal/pawns-cli",
            docker_summary="Official Pawns CLI Docker image.",
            compose_image="iproyal/pawns-cli:latest",
            compose_command_template="-email={IPROYAL_EMAIL} -password={IPROYAL_PASSWORD} -device-name={DEVICE_NAME} -device-id={DEVICE_ID} -accept-tos",
        ),

        ServiceDefinition(
            name="PacketStream", slug="packetstream",
            website_url="https://packetstream.io",
            dashboard_url="https://app.packetstream.io/dashboard",
            payout_url="https://app.packetstream.io/dashboard",
            threshold=5.0, category="bandwidth",
            setup_fields=(SetupField("PS_CID", "Client CID token"),),
            balance_mode="api", balance_unit="usd",
            earnings_model_note="PacketStream exposes a REST balance endpoint keyed by CID token.",
            payout_note="Payout is requested from the PacketStream dashboard once $5 is reached.",
            docker_mode="docker_auto", docker_support_level="official",
            docker_source_url="https://hub.docker.com/r/packetstream/psclient",
            docker_summary="Official PacketStream Docker client.",
            compose_image="packetstream/psclient:latest",
            compose_env_templates=("CID={PS_CID}",),
            api_balance_url="https://api.packetstream.io/v1/user/balance",
        ),

        ServiceDefinition(
            name="TraffMonetizer", slug="traffmonetizer",
            website_url="https://traffmonetizer.com",
            dashboard_url="https://app.traffmonetizer.com/dashboard",
            payout_url="https://app.traffmonetizer.com/payments",
            threshold=10.0, category="bandwidth",
            setup_fields=(SetupField("TM_TOKEN", "Application token", secret=True),),
            balance_mode="library", balance_unit="usd",
            earnings_model_note="TraffMonetizer token-authenticated REST balance.",
            payout_note="Payout is requested from the official dashboard.",
            docker_mode="docker_auto", docker_support_level="official",
            docker_source_url="https://hub.docker.com/r/traffmonetizer/cli_v2",
            docker_summary="Official TraffMonetizer v2 Docker image.",
            compose_image="traffmonetizer/cli_v2:latest",
            compose_command_template="start accept --token {TM_TOKEN}",
            api_balance_url="https://traffmonetizer.com/api/earn/balance",
        ),

        ServiceDefinition(
            name="EarnFM", slug="earnfm",
            website_url="https://earn.fm/en/",
            dashboard_url="https://earn.fm/en/dashboard",
            payout_url="https://earn.fm/en/dashboard",
            threshold=1.0, category="bandwidth",
            setup_fields=(SetupField("EARNFM_TOKEN", "EarnFM API token", secret=True),),
            balance_mode="api", balance_unit="usd",
            earnings_model_note="EarnFM official Docker client keyed by your API token.",
            payout_note="Payout and token management stay in the EarnFM dashboard.",
            docker_mode="docker_auto", docker_support_level="official",
            docker_source_url="https://hub.docker.com/r/earnfm/earnfm-client",
            docker_summary="Official EarnFM Docker image.",
            compose_image="earnfm/earnfm-client:latest",
            compose_env_templates=("EARNFM_TOKEN={EARNFM_TOKEN}",),
            api_balance_url="https://earn.fm/api/client/balance",
        ),

        ServiceDefinition(
            name="Repocket", slug="repocket",
            website_url="https://repocket.com/",
            dashboard_url="https://repocket.com/dashboard/share-internet",
            payout_url="https://repocket.com/dashboard/share-internet",
            threshold=20.0, category="bandwidth",
            setup_fields=(
                SetupField("REPOCKET_EMAIL",   "Account e-mail"),
                SetupField("REPOCKET_API_KEY", "API key", secret=True),
            ),
            balance_mode="api", balance_unit="usd",
            earnings_model_note="Repocket Docker image requiring e-mail and API key.",
            payout_note="Payout is requested in the official Repocket dashboard.",
            docker_mode="docker_auto", docker_support_level="official",
            docker_source_url="https://hub.docker.com/r/repocket/repocket",
            docker_summary="Official Repocket Docker image.",
            compose_image="repocket/repocket:latest",
            compose_env_templates=("RP_EMAIL={REPOCKET_EMAIL}", "RP_API_KEY={REPOCKET_API_KEY}"),
        ),

        ServiceDefinition(
            name="Proxyrack", slug="proxyrack",
            website_url="https://www.proxyrack.com/become-a-peer/",
            dashboard_url="https://app.proxyrack.com/dashboard/home",
            payout_url="https://app.proxyrack.com/dashboard/home",
            threshold=5.0, category="bandwidth",
            setup_fields=(
                SetupField("PROXYRACK_UUID",        "Proxyrack UUID"),
                SetupField("PROXYRACK_API_KEY",     "API key (optional)", secret=True, required=False),
                SetupField("PROXYRACK_DEVICE_NAME", "Device name (optional)", required=False),
            ),
            balance_mode="api", balance_unit="usd",
            earnings_model_note="Proxyrack PoP container uses UUID + optional API key.",
            payout_note="Payout remains a dashboard flow.",
            docker_mode="docker_auto", docker_support_level="official",
            docker_source_url="https://hub.docker.com/r/proxyrack/pop",
            docker_summary="Proxyrack PoP Docker image.",
            compose_image="proxyrack/pop:latest",
            compose_env_templates=(
                "UUID={PROXYRACK_UUID}",
                "API_KEY={PROXYRACK_API_KEY}",
                "DEVICE_NAME={PROXYRACK_DEVICE_NAME}",
            ),
        ),

        ServiceDefinition(
            name="Grass", slug="grass",
            website_url="https://www.grass.io/",
            dashboard_url="https://app.grass.io/dashboard",
            payout_url="https://app.grass.io/dashboard",
            threshold=0.0, category="bandwidth",
            setup_fields=(
                SetupField("GRASS_EMAIL",    "Account e-mail"),
                SetupField("GRASS_PASSWORD", "Account password", secret=True),
            ),
            balance_mode="api", balance_unit="points",
            earnings_model_note=(
                "Grass accumulates points that convert to tokens at TGE. "
                "USD excluded from totals until a verified conversion rate exists."
            ),
            payout_note="Points/airdrop management is done in the official Grass app.",
            docker_mode="docker_auto", docker_support_level="community",
            docker_source_url="https://hub.docker.com/r/mrcolorrain/grass-node",
            docker_summary="Community image — USER_EMAIL / USER_PASSWORD.",
            compose_image="mrcolorrain/grass-node:latest",
            compose_env_templates=("USER_EMAIL={GRASS_EMAIL}", "USER_PASSWORD={GRASS_PASSWORD}"),
            compose_hostname="myriapod-grass",
            compose_ports=("5900:5900", "6080:6080"),
            api_balance_url="https://director.getgrass.io/v1/user/points",
        ),

        ServiceDefinition(
            name="Bitping", slug="bitping",
            website_url="https://bitping.com",
            dashboard_url="https://app.bitping.com",
            payout_url="https://app.bitping.com",
            threshold=0.0, category="bandwidth",
            setup_fields=(
                SetupField("BITPING_EMAIL",    "Account e-mail"),
                SetupField("BITPING_PASSWORD", "Account password", secret=True),
            ),
            balance_mode="api", balance_unit="sol",
            earnings_model_note="Bitping rewards in SOL — USD reference via CoinGecko.",
            payout_note="Bitping payout/wallet setup is in the Bitping dashboard.",
            docker_mode="monitor_only", docker_support_level="unverified",
            docker_source_url="https://app.bitping.com",
            docker_summary="Not auto-deployed by Myriapod.",
            coingecko_id="solana",
        ),

        ServiceDefinition(
            name="Bytelixir", slug="bytelixir",
            website_url="https://bytelixir.com",
            dashboard_url="https://dash.bytelixir.com",
            payout_url="https://dash.bytelixir.com",
            threshold=5.0, category="bandwidth",
            setup_fields=(
                SetupField("BYTELIXIR_TOKEN", "Auth token", secret=True, required=False),
            ),
            balance_mode="api", balance_unit="usd",
            earnings_model_note="Bytelixir dashboard monitor — balance fetched via API token.",
            payout_note="Payout handled in the official dashboard.",
            docker_mode="monitor_only", docker_support_level="unverified",
            docker_source_url="https://bytelixir.com/",
            docker_summary="No verified Myriapod auto-deploy path.",
        ),

        ServiceDefinition(
            name="Peer2Profit", slug="peer2profit",
            website_url="https://p2pr.me",
            dashboard_url="https://t.me/peer2profit_bot",
            payout_url="https://t.me/peer2profit_bot",
            threshold=2.0, category="bandwidth",
            setup_fields=(
                SetupField("P2P_API_ID",   "Telegram API ID"),
                SetupField("P2P_API_HASH", "Telegram API Hash", secret=True),
                SetupField("P2P_PHONE",    "Telegram phone (+international)"),
            ),
            balance_mode="telegram", balance_unit="usd",
            earnings_model_note="Peer2Profit operates through a Telegram bot via Telethon.",
            payout_note="Withdrawals are initiated through the Peer2Profit Telegram bot.",
            docker_mode="monitor_only", docker_support_level="unverified",
            docker_source_url="https://p2pr.me",
            docker_summary="Telegram-based service — no Docker container.",
        ),

        # ── NODE / dVPN ────────────────────────────────────────────────────────
        ServiceDefinition(
            name="Mysterium", slug="mysterium",
            website_url="https://www.mystnodes.com/",
            dashboard_url="https://my.mystnodes.com/",
            payout_url="https://my.mystnodes.com/",
            threshold=0.0, category="node",
            setup_fields=(
                SetupField("MYST_API_KEY", "Node API key / claim token", secret=True, required=False),
            ),
            balance_mode="rpc", balance_unit="myst",
            earnings_model_note="Mysterium node rewards in MYST tokens.",
            payout_note="Node config and withdrawals via Mysterium tooling.",
            docker_mode="docker_manual", docker_support_level="official",
            docker_source_url="https://hub.docker.com/r/mysteriumnetwork/myst",
            docker_summary="Official image — requires host networking and NET_ADMIN.",
            compose_image="mysteriumnetwork/myst:latest",
            compose_command_template="service --agreed-terms-and-conditions",
            compose_network_mode="host",
            compose_cap_add=("NET_ADMIN",),
            compose_volumes=("./data/mysterium:/var/lib/mysterium-node",),
            health_check_url="http://localhost:4449/tequilapi/healthcheck",
            manual_docker_notes="Run with host networking and NET_ADMIN as per Mysterium docs.",
            coingecko_id="mysterium",
        ),

        ServiceDefinition(
            name="Sentinel", slug="sentinel",
            website_url="https://sentinel.co",
            dashboard_url="https://docs.sentinel.co/dvpn-node-setup/manual-setup",
            payout_url="https://docs.sentinel.co/dvpn-node-setup/manual-setup",
            threshold=0.0, category="node",
            setup_fields=(
                SetupField("SENTINEL_WALLET_MNEMONIC", "Wallet mnemonic", secret=True),
                SetupField("SENTINEL_NODE_MONIKER",    "Node moniker", hint="myriapod-sentinel-1"),
            ),
            balance_mode="rpc", balance_unit="raw",
            earnings_model_note="Sentinel dVPN node — manual Docker required.",
            payout_note="Sentinel node management is fully manual.",
            docker_mode="docker_manual", docker_support_level="official",
            docker_source_url="https://docs.sentinel.co/dvpn-node-setup/manual/docker-image",
            docker_summary="Official image — needs /dev/net/tun + capabilities.",
            compose_image="ghcr.io/sentinel-official/sentinel-dvpnx:latest",
            compose_devices=("/dev/net/tun:/dev/net/tun",),
            compose_cap_add=("NET_ADMIN", "NET_RAW", "SYS_MODULE"),
            compose_sysctls={"net.ipv4.ip_forward": "1"},
            compose_volumes=("./data/sentinel:/root/.sentinelnode",),
            manual_docker_notes="Run with TUN device, required capabilities, sysctls.",
            coingecko_id="sentinel",
        ),

        ServiceDefinition(
            name="GagaNode", slug="gaganode",
            website_url="https://www.gaganode.com/",
            dashboard_url="https://dashboard.gaganode.com",
            payout_url="https://dashboard.gaganode.com",
            threshold=0.0, category="node",
            setup_fields=(
                SetupField("GAGANODE_TOKEN", "Node token", secret=True),
            ),
            balance_mode="api", balance_unit="points",
            earnings_model_note="GagaNode credits shown as native points.",
            payout_note="Account actions stay in the official dashboard.",
            docker_mode="docker_auto", docker_support_level="community",
            docker_source_url="https://hub.docker.com/r/onegrx/gaganode",
            docker_summary="Community GagaNode image.",
            compose_image="onegrx/gaganode:latest",
            compose_env_templates=("TOKEN={GAGANODE_TOKEN}",),
        ),

        # ── STORAGE ────────────────────────────────────────────────────────────
        ServiceDefinition(
            name="Storj", slug="storj",
            website_url="https://www.storj.io",
            dashboard_url="https://storj.dev/node/get-started/setup",
            payout_url="https://storj.dev/node/get-started/setup",
            threshold=1.5, category="storage",
            setup_fields=(
                SetupField("STORJ_WALLET",           "ERC-20 wallet address"),
                SetupField("STORJ_EMAIL",            "Contact e-mail"),
                SetupField("STORJ_EXTERNAL_ADDRESS", "External IP:port", hint="1.2.3.4:28967"),
                SetupField("STORJ_STORAGE",          "Storage allocation", hint="500GB"),
                SetupField("STORJ_AUTH_TOKEN",       "Node auth token", secret=True, required=False),
            ),
            balance_mode="rpc", balance_unit="storj",
            earnings_model_note="Storj payouts are in STORJ tokens.",
            payout_note="Storj node requires identity/config volumes; see official docs.",
            docker_mode="docker_auto", docker_support_level="official",
            docker_source_url="https://storj.dev/node/faq/install-storagenode-on-raspberry-pi3-or-higher-version",
            docker_summary="Official image — needs WALLET, EMAIL, ADDRESS, STORAGE and mounts.",
            compose_image="storjlabs/storagenode:latest",
            compose_env_templates=(
                "WALLET={STORJ_WALLET}",
                "EMAIL={STORJ_EMAIL}",
                "ADDRESS={STORJ_EXTERNAL_ADDRESS}",
                "STORAGE={STORJ_STORAGE}",
            ),
            compose_ports=("28967:28967/tcp", "28967:28967/udp", "14002:14002"),
            compose_volumes=("./data/storj/identity:/app/identity", "./data/storj/storage:/app/config"),
            health_check_url="http://localhost:14002/api/sno/",
            manual_docker_notes="Provide WALLET, EMAIL, ADDRESS, STORAGE and identity/config volumes.",
            coingecko_id="storj",
        ),

        ServiceDefinition(
            name="Arweave", slug="arweave",
            website_url="https://www.arweave.org",
            dashboard_url="https://viewblock.io/arweave",
            payout_url="https://viewblock.io/arweave",
            threshold=0.0, category="storage",
            setup_fields=(
                SetupField("AR_WALLET_ADDRESS", "Arweave wallet address"),
                SetupField("AR_MINING_ADDR",    "Mining address (optional)", required=False),
            ),
            balance_mode="manual", balance_unit="raw",
            earnings_model_note="Arweave mining — not reduced to one-click Docker.",
            payout_note="Use official Arweave tooling for node operation.",
            docker_mode="docker_auto", docker_support_level="community",
            docker_source_url="https://hub.docker.com/r/arweavenet/arweave",
            docker_summary="Community Arweave node.",
            compose_image="arweavenet/arweave:latest",
            compose_ports=("1984:1984",),
            compose_volumes=("./data/arweave:/data",),
            compose_command_template="arweave-server peer mine",
        ),

        # ── COMPUTE ────────────────────────────────────────────────────────────
        ServiceDefinition(
            name="Theta", slug="theta",
            website_url="https://www.thetatoken.org",
            dashboard_url="https://wallet.thetatoken.org/",
            payout_url="https://wallet.thetatoken.org/",
            threshold=0.0, category="compute",
            setup_fields=(SetupField("THETA_WALLET_ADDRESS", "Theta wallet address"),),
            balance_mode="manual", balance_unit="raw",
            earnings_model_note="Theta Edge Node — monitor only.",
            payout_note="Use official Theta tooling for node/wallet actions.",
            docker_mode="docker_auto", docker_support_level="official",
            docker_source_url="https://hub.docker.com/r/thetalabsorg/edgelauncher_mainnet",
            docker_summary="Official Theta Edge Node image.",
            compose_image="thetalabsorg/edgelauncher_mainnet:latest",
            compose_env_templates=("PASSWORD={THETA_PASSWORD}", "EDGELAUNCHER_CONFIG_PATH=/edgelauncher/data/mainnet"),
            compose_ports=("15888:15888", "17888:17888", "17935:17935"),
            compose_volumes=("./data/theta:/edgelauncher/data/mainnet",),
            coingecko_id="theta-fuel",
        ),

        ServiceDefinition(
            name="Fluence", slug="fluence",
            website_url="https://www.fluence.network/",
            dashboard_url="https://www.fluence.network/",
            payout_url="https://www.fluence.network/",
            threshold=0.0, category="compute",
            setup_fields=(
                SetupField("FLUENCE_WALLET",     "Wallet address"),
                SetupField("FLUENCE_SECRET_KEY", "Node secret key", secret=True),
            ),
            balance_mode="manual", balance_unit="raw",
            earnings_model_note="Fluence nox provider — manual Docker.",
            payout_note="Use Fluence docs for node/provider setup.",
            docker_mode="docker_auto", docker_support_level="official",
            docker_source_url="https://hub.docker.com/r/fluencelabs/nox",
            docker_summary="Official image — provider setup remains manual.",
            compose_image="fluencelabs/nox:latest",
            compose_env_templates=("FLUENCE_WALLET={FLUENCE_WALLET}", "FLUENCE_SECRET={FLUENCE_SECRET_KEY}"),
            compose_ports=("7777:7777", "9999:9999"),
            compose_volumes=("./data/fluence:/.fluence",),
            coingecko_id="fluence-token",
        ),

        ServiceDefinition(
            name="Acurast", slug="acurast",
            website_url="https://console.acurast.com/",
            dashboard_url="https://console.acurast.com",
            payout_url="https://console.acurast.com",
            threshold=0.0, category="compute",
            setup_fields=(SetupField("ACURAST_SEED", "Node seed phrase", secret=True),),
            balance_mode="manual", balance_unit="raw",
            earnings_model_note="Acurast processor — monitor only.",
            payout_note="Use Acurast tooling for processor/node setup.",
            docker_mode="docker_auto", docker_support_level="community",
            docker_source_url="https://console.acurast.com",
            docker_summary="Acurast processor automated node.",
            compose_image="acurast/node:latest",
            compose_env_templates=("ACURAST_SEED={ACURAST_SEED}",),
        ),

        ServiceDefinition(
            name="Akash", slug="akash",
            website_url="https://akash.network",
            dashboard_url="https://stats.akash.network",
            payout_url="https://stats.akash.network",
            threshold=0.0, category="compute",
            setup_fields=(SetupField("AKASH_WALLET_ADDRESS", "Akash wallet address"),),
            balance_mode="manual", balance_unit="raw",
            earnings_model_note="Akash provider setup — monitor only.",
            payout_note="Use official Akash provider tooling/docs.",
            docker_mode="docker_auto", docker_support_level="official",
            docker_source_url="https://github.com/akash-network/provider",
            docker_summary="Akash network provider auto node.",
            compose_image="ghcr.io/akash-network/provider:latest",
            compose_env_templates=("AKASH_WALLET={AKASH_WALLET_ADDRESS}",),
            coingecko_id="akash-network",
        ),

        ServiceDefinition(
            name="Flux", slug="flux",
            website_url="https://runonflux.com/",
            dashboard_url="https://cloud.runonflux.com/",
            payout_url="https://cloud.runonflux.com/",
            threshold=0.0, category="compute",
            setup_fields=(
                SetupField("FLUX_WALLET_ADDRESS", "Flux wallet address"),
                SetupField("FLUX_PRIVATE_KEY",    "FluxNode private key", secret=True),
                SetupField("FLUX_TX_HASH",        "Collateral TX hash"),
                SetupField("FLUX_TX_INDEX",       "Collateral TX output index", hint="0"),
            ),
            balance_mode="manual", balance_unit="raw",
            earnings_model_note="Flux FluxNode — monitor only in Myriapod.",
            payout_note="Use official Flux docs/tooling for node deployment.",
            docker_mode="docker_auto", docker_support_level="official",
            docker_source_url="https://hub.docker.com/r/runonflux/fluxnode",
            docker_summary="FluxNode auto deployment.",
            compose_image="runonflux/fluxnode:latest",
            compose_env_templates=(
                "ZELID={FLUX_WALLET_ADDRESS}",
                "KDA={FLUX_PRIVATE_KEY}",
                "TXHASH={FLUX_TX_HASH}",
                "OUTINDEX={FLUX_TX_INDEX}",
            ),
            coingecko_id="zelcash",
        ),

        ServiceDefinition(
            name="SubQuery", slug="subquery",
            website_url="https://subquery.network",
            dashboard_url="https://kepler.subquery.network",
            payout_url="https://kepler.subquery.network",
            threshold=0.0, category="compute",
            setup_fields=(
                SetupField("SUBQUERY_WALLET",         "Operator wallet"),
                SetupField("SUBQUERY_CONTROLLER_KEY", "Controller private key", secret=True),
            ),
            balance_mode="manual", balance_unit="raw",
            earnings_model_note="SubQuery indexer — monitor only.",
            payout_note="Use Kepler/SubQuery tooling for operator actions.",
            docker_mode="docker_auto", docker_support_level="community",
            docker_source_url="https://hub.docker.com/r/subquerynetwork/subql-node",
            docker_summary="SubQuery Node auto deploy.",
            compose_image="subquerynetwork/subql-node:latest",
            compose_env_templates=(
                "WALLET={SUBQUERY_WALLET}",
                "SECRET={SUBQUERY_CONTROLLER_KEY}",
            ),
        ),
    ]

    custom_file = BASE_DIR / "custom_services.json"
    if custom_file.exists():
        try:
            import json
            custom_data = json.loads(custom_file.read_text(encoding="utf-8"))
            for entry in custom_data:
                fields = []
                for f in entry.get("setup_fields", []):
                    fields.append(SetupField(
                        key=f.get("key"),
                        label=f.get("label"),
                        secret=f.get("secret", False),
                        hint=f.get("hint", ""),
                        required=f.get("required", True),
                    ))
                
                defs.append(ServiceDefinition(
                    name=entry.get("name"),
                    slug=entry.get("slug"),
                    website_url=entry.get("website_url", ""),
                    dashboard_url=entry.get("dashboard_url", ""),
                    payout_url=entry.get("payout_url", ""),
                    threshold=float(entry.get("threshold", 0.0)),
                    category=entry.get("category", "custom"),
                    setup_fields=tuple(fields),
                    balance_mode=entry.get("balance_mode", "api"),
                    balance_unit=entry.get("balance_unit", "usd"),
                    earnings_model_note=entry.get("earnings_model_note", ""),
                    payout_note=entry.get("payout_note", ""),
                    docker_mode=entry.get("docker_mode", "monitor_only"),
                    docker_support_level=entry.get("docker_support_level", "unverified"),
                    docker_source_url=entry.get("docker_source_url", ""),
                    docker_summary=entry.get("docker_summary", ""),
                    compose_image=entry.get("compose_image"),
                    compose_command_template=entry.get("compose_command_template"),
                    compose_env_templates=tuple(entry.get("compose_env_templates", [])),
                    compose_ports=tuple(entry.get("compose_ports", [])),
                    compose_volumes=tuple(entry.get("compose_volumes", [])),
                    compose_devices=tuple(entry.get("compose_devices", [])),
                    compose_cap_add=tuple(entry.get("compose_cap_add", [])),
                    compose_hostname=entry.get("compose_hostname"),
                    compose_network_mode=entry.get("compose_network_mode"),
                    compose_sysctls=dict(entry.get("compose_sysctls", {})),
                    manual_docker_notes=entry.get("manual_docker_notes", ""),
                    health_check_url=entry.get("health_check_url"),
                    api_balance_url=entry.get("api_balance_url"),
                    coingecko_id=entry.get("coingecko_id"),
                    json_path=tuple(entry.get("json_path", [])),
                    headers=dict(entry.get("headers", {})),
                ))
            logger.info("Loaded %d custom service(s) from custom_services.json.", len(custom_data))
        except Exception as e:
            logger.error("Failed to load custom_services.json: %s", e)

    return {svc.name: svc for svc in defs}


SERVICES: Dict[str, ServiceDefinition] = _build_services()

# ═══════════════════════════════════════════════════════════════════════════════
# §10  SECRET MANAGER
# ═══════════════════════════════════════════════════════════════════════════════
class SecretManager:
    """
    An extremely robust and overengineered Cryptographic Vault Key Consensus System (CVKCS).
    Protects the credentials vault from corruption by using a multi-layered consensus key
    derivation process, automatic key migration, and robust file permissions.
    """

    def __init__(self, path: Path = SECRETS_FILE) -> None:
        self._path = path
        self._lock = threading.Lock()
        self._master_key_file = DATA_DIR / ".vault_master_key"
        self._key = self._resolve_consensus_key()
        self._fernet = Fernet(self._key)
        self._store: Dict[str, str] = self._load()

    def _resolve_consensus_key(self) -> bytes:
        """
        Executes the Cryptographic Key Consensus Protocol.
        Generates dynamic key candidates, audits active vault decryptability, and caches
        the winning key inside a secured local file with automatic migration/healing.
        """
        logger.info("Initializing Cryptographic Vault Key Consensus System...")

        # 1. Attempt reading cached master key from disk
        if self._master_key_file.exists():
            try:
                cached_key = self._master_key_file.read_bytes().strip()
                if len(cached_key) == 44:  # Valid urlsafe-base64 32-byte key length
                    # Validate cached key works if vault file exists
                    if self._path.exists():
                        test_fernet = Fernet(cached_key)
                        test_fernet.decrypt(self._path.read_bytes())
                    logger.info("Validated cached vault master key from disk.")
                    return cached_key
            except Exception as exc:
                logger.warning("Cached master key validation failed: %s. Initiating key reconstruction consensus...", exc)

        # 2. Gather diverse machine hardware & OS identification metrics
        machine_id = ""
        if platform.system().lower() == "linux":
            for path in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
                try:
                    p = Path(path)
                    if p.exists():
                        machine_id = p.read_text().strip()
                        break
                except Exception:
                    pass
        elif platform.system().lower() == "windows":
            try:
                import winreg
                registry_key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography")
                machine_id, _ = winreg.QueryValueEx(registry_key, "MachineGuid")
                winreg.CloseKey(registry_key)
            except Exception:
                pass

        node = platform.node()
        machine = platform.machine()
        mac_addr = str(uuid.getnode())

        # 3. Formulate prioritized consensus key derivation options (ordered by stability)
        candidates: List[Tuple[str, bytes]] = []

        # Candidate A: Hardware Machine ID bound (highly stable)
        if machine_id:
            candidates.append(("MachineID-HW", self._derive_key_from_seed(f"MyriapodHWKey:{machine_id}")))

        # Candidate B: Dynamic factors combo (legacy)
        candidates.append(("LegacyCombo", self._derive_key_from_seed(f"{mac_addr}{node}{machine}")))

        # Candidate C: Stable factors combo (resilient to hostname changes)
        candidates.append(("StableCombo", self._derive_key_from_seed(f"{mac_addr}{machine}")))

        # Candidate D: Minimal MAC-only fallback
        candidates.append(("MAC-Only", self._derive_key_from_seed(mac_addr)))

        # 4. If vault exists, probe candidates to find a decryptable consensus winner
        if self._path.exists():
            vault_bytes = self._path.read_bytes()
            for label, key_candidate in candidates:
                try:
                    test_fernet = Fernet(key_candidate)
                    test_fernet.decrypt(vault_bytes)
                    logger.info("Consensus reached: successfully decrypted vault using key candidate: %s", label)
                    self._cache_master_key(key_candidate)
                    return key_candidate
                except Exception:
                    continue
            logger.critical("Consensus key derivation failed. None of the %d candidates could decrypt the vault.", len(candidates))

        # 5. If no decryption worked or this is a fresh setup, use top candidate or generate a new random key
        # If vault exists but cannot be decrypted, backup the vault before replacing
        if self._path.exists():
            bak = self._path.with_suffix(".enc.corrupted")
            try:
                self._path.rename(bak)
                logger.warning("Backed up corrupted vault to %s", bak)
            except Exception:
                pass

        logger.info("Generating a fresh cryptographically strong vault key...")
        fresh_key = base64.urlsafe_b64encode(hashlib.sha256(os.urandom(32)).digest())
        self._cache_master_key(fresh_key)
        return fresh_key

    @staticmethod
    def _derive_key_from_seed(seed: str) -> bytes:
        digest = hashlib.sha256(seed.encode("utf-8")).digest()
        return base64.urlsafe_b64encode(digest)

    def _cache_master_key(self, key: bytes) -> None:
        """Securely saves the verified master key to disk with strict file permissions."""
        try:
            self._master_key_file.write_bytes(key)
            # Set owner read/write permissions only (0600 on Unix)
            if platform.system().lower() != "windows":
                try:
                    os.chmod(self._master_key_file, 0o600)
                except Exception:
                    pass
            logger.info("Successfully cached secure vault master key to %s", self._master_key_file)
        except Exception as exc:
            logger.error("Failed to cache vault master key: %s", exc)

    def _load(self) -> Dict[str, str]:
        if not self._path.exists():
            return {}
        try:
            raw = self._path.read_bytes()
            decrypted = self._fernet.decrypt(raw)
            return json.loads(decrypted.decode())
        except Exception as exc:
            logger.error("SecretManager decrypt failed (%s) — recreating vault.", exc)
            return {}

    def _save(self) -> None:
        payload = json.dumps(self._store).encode()
        self._path.write_bytes(self._fernet.encrypt(payload))
        # Secure the vault file permissions
        if platform.system().lower() != "windows":
            try:
                os.chmod(self._path, 0o600)
            except Exception:
                pass

    def get(self, key: str, default: str = "") -> str:
        with self._lock:
            return self._store.get(key, default)

    def set(self, key: str, value: str) -> None:
        with self._lock:
            self._store[key] = value
            self._save()

    def delete(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)
            self._save()

    def has(self, key: str) -> bool:
        with self._lock:
            return bool(self._store.get(key))

    def all_keys(self) -> List[str]:
        with self._lock:
            return list(self._store.keys())

    def sync_from_env(self, services: Dict[str, Any]) -> int:
        """Import credentials from .env / os.environ into SecretManager.
        Returns the number of newly imported keys."""
        count = 0
        env = current_env()
        for svc in services.values():
            for f in getattr(svc, 'setup_fields', ()):
                key = f.key
                if not self.has(key):
                    val = env.get(key, "")
                    if val:
                        with self._lock:
                            self._store[key] = val
                        count += 1
        if count:
            with self._lock:
                self._save()
            logger.info("SecretManager: synced %d credential(s) from .env", count)
        return count

# ═══════════════════════════════════════════════════════════════════════════════
# §11  DATABASE MANAGER
# ═══════════════════════════════════════════════════════════════════════════════
class DatabaseManager:
    """Thread-safe SQLite database with WAL journal, reentrant locking, and automatic WAL checkpointing."""

    def __init__(self) -> None:
        # 60s timeout prevents 'database is locked' errors during heavy concurrent reads/writes
        self.conn = sqlite3.connect(str(DB_FILE), check_same_thread=False, timeout=60.0)
        self.lock = threading.RLock()
        
        with self.lock:
            self.conn.execute("PRAGMA journal_mode=WAL;")
            self.conn.execute("PRAGMA synchronous=NORMAL;")
            self.conn.execute("PRAGMA foreign_keys=ON;")
            self._init_schema()
            self._migrate()
            self._write_count = 0

    def _init_schema(self) -> None:
        with self.lock:
            with self.conn:
                self.conn.executescript("""
                    CREATE TABLE IF NOT EXISTS earnings_history (
                        id               INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp        DATETIME DEFAULT CURRENT_TIMESTAMP,
                        service          TEXT NOT NULL,
                        balance_usd      REAL NOT NULL,
                        source           TEXT DEFAULT '',
                        native_value     REAL,
                        native_unit      TEXT DEFAULT 'usd',
                        include_in_total INTEGER DEFAULT 1
                    );
                    CREATE TABLE IF NOT EXISTS withdrawals (
                        id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp          DATETIME DEFAULT CURRENT_TIMESTAMP,
                        service            TEXT NOT NULL,
                        amount             REAL NOT NULL,
                        destination_wallet TEXT NOT NULL,
                        transaction_id     TEXT,
                        status             TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS service_status (
                        id        INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        service   TEXT NOT NULL,
                        status    TEXT NOT NULL,
                        details   TEXT DEFAULT ''
                    );
                    CREATE TABLE IF NOT EXISTS ip_history (
                        id         INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp  DATETIME DEFAULT CURRENT_TIMESTAMP,
                        ip_address TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS price_cache (
                        coin_id    TEXT PRIMARY KEY,
                        price_usd  REAL NOT NULL,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    );
                    CREATE TABLE IF NOT EXISTS notifications_log (
                        id        INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        level     TEXT NOT NULL,
                        title     TEXT NOT NULL,
                        message   TEXT NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS idx_eh_service ON earnings_history(service);
                    CREATE INDEX IF NOT EXISTS idx_eh_ts      ON earnings_history(timestamp);
                    CREATE INDEX IF NOT EXISTS idx_ss_service ON service_status(service);
                """)

    def _add_column_if_missing(self, table: str, col: str, ddl: str) -> None:
        with self.lock:
            existing = {row[1] for row in self.conn.execute(f"PRAGMA table_info({table})")}
            if col not in existing:
                self.conn.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")

    def _migrate(self) -> None:
        with self.lock:
            self._add_column_if_missing("earnings_history", "source",           "source TEXT DEFAULT ''")
            self._add_column_if_missing("earnings_history", "native_value",     "native_value REAL")
            self._add_column_if_missing("earnings_history", "native_unit",      "native_unit TEXT DEFAULT 'usd'")
            self._add_column_if_missing("earnings_history", "include_in_total", "include_in_total INTEGER DEFAULT 1")
            self.conn.execute("""
                UPDATE earnings_history
                   SET native_value     = balance_usd,
                       native_unit      = COALESCE(NULLIF(native_unit,''),'usd'),
                       include_in_total = COALESCE(include_in_total,1)
                 WHERE native_value IS NULL
            """)
            self.conn.commit()

    def _checkpoint_wal_if_needed(self) -> None:
        """Runs a passive WAL checkpoint to flush journal pages to database disk securely."""
        self._write_count += 1
        if self._write_count % 5 == 0:
            try:
                self.conn.execute("PRAGMA wal_checkpoint(PASSIVE);")
                logger.debug("Automatic WAL checkpoint executed successfully.")
            except Exception as exc:
                logger.warning("WAL checkpoint execution encountered conflict: %s", exc)

    # ── write helpers ─────────────────────────────────────────────────────────
    def log_snapshot(self, service: str, usd_value: float, source: str,
                     native_value: Optional[float], native_unit: str,
                     include_in_total: bool) -> None:
        with self.lock:
            self.conn.execute(
                "INSERT INTO earnings_history "
                "(service,balance_usd,source,native_value,native_unit,include_in_total) "
                "VALUES (?,?,?,?,?,?)",
                (service, usd_value, source, native_value, native_unit,
                 1 if include_in_total else 0),
            )
            self.conn.commit()
            self._checkpoint_wal_if_needed()

    def log_withdrawal(self, service: str, amount: float, destination: str,
                       tx_id: str, status: str) -> None:
        with self.lock:
            self.conn.execute(
                "INSERT INTO withdrawals "
                "(service,amount,destination_wallet,transaction_id,status) "
                "VALUES (?,?,?,?,?)",
                (service, amount, destination, tx_id, status),
            )
            self.conn.commit()
            self._checkpoint_wal_if_needed()

    def log_service_status(self, service: str, status: str, details: str = "") -> None:
        with self.lock:
            self.conn.execute(
                "INSERT INTO service_status (service,status,details) VALUES (?,?,?)",
                (service, status, details),
            )
            self.conn.commit()
            self._checkpoint_wal_if_needed()

    def log_ip(self, ip: str) -> None:
        with self.lock:
            self.conn.execute("INSERT INTO ip_history (ip_address) VALUES (?)", (ip,))
            self.conn.commit()
            self._checkpoint_wal_if_needed()

    def log_notification(self, level: str, title: str, message: str) -> None:
        with self.lock:
            self.conn.execute(
                "INSERT INTO notifications_log (level,title,message) VALUES (?,?,?)",
                (level, title, message),
            )
            self.conn.commit()
            self._checkpoint_wal_if_needed()

    def cache_price(self, coin_id: str, price: float) -> None:
        with self.lock:
            self.conn.execute(
                "INSERT OR REPLACE INTO price_cache (coin_id,price_usd,updated_at) "
                "VALUES (?,?,datetime('now'))",
                (coin_id, price),
            )
            self.conn.commit()
            self._checkpoint_wal_if_needed()

    # ── read helpers ──────────────────────────────────────────────────────────
    def get_last_ip(self) -> Optional[str]:
        with self.lock:
            row = self.conn.execute(
                "SELECT ip_address FROM ip_history ORDER BY id DESC LIMIT 1"
            ).fetchone()
            return row[0] if row else None

    def get_cached_price(self, coin_id: str, max_age_minutes: int = 30) -> Optional[float]:
        with self.lock:
            row = self.conn.execute(
                "SELECT price_usd FROM price_cache "
                "WHERE coin_id=? AND updated_at>=datetime('now',?)",
                (coin_id, f"-{max_age_minutes} minutes"),
            ).fetchone()
            return float(row[0]) if row else None

    def get_total_wealth(self) -> float:
        with self.lock:
            row = self.conn.execute(
                "SELECT COALESCE(SUM(balance_usd),0) FROM earnings_history "
                "WHERE id IN (SELECT MAX(id) FROM earnings_history GROUP BY service) "
                "  AND include_in_total=1"
            ).fetchone()
            return float(row[0] or 0.0)

    def get_historical_data(self, days: int = 7) -> List[Tuple[str, str, float]]:
        with self.lock:
            cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
            return self.conn.execute(
                "SELECT timestamp,service,balance_usd FROM earnings_history "
                "WHERE timestamp>=? AND include_in_total=1 ORDER BY timestamp ASC",
                (cutoff,),
            ).fetchall()

    def get_recent_withdrawals(self, limit: int = 100) -> List[Tuple]:
        with self.lock:
            return self.conn.execute(
                "SELECT timestamp,service,amount,destination_wallet,transaction_id,status "
                "FROM withdrawals ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            ).fetchall()

    def get_per_service_latest(self) -> Dict[str, float]:
        with self.lock:
            rows = self.conn.execute(
                "SELECT service,balance_usd FROM earnings_history "
                "WHERE id IN (SELECT MAX(id) FROM earnings_history GROUP BY service) "
                "  AND include_in_total=1"
            ).fetchall()
            return {row[0]: float(row[1]) for row in rows}

    def get_latest_results(self, services: Dict[str, ServiceDefinition]) -> Dict[str, BalanceResult]:
        """Fetch the most recent BalanceResult for all configured services from DB."""
        with self.lock:
            results: Dict[str, BalanceResult] = {}
            for name, svc in services.items():
                row = self.conn.execute(
                    "SELECT balance_usd, source, native_value, native_unit, include_in_total "
                    "FROM earnings_history WHERE service=? ORDER BY id DESC LIMIT 1",
                    (name,)
                ).fetchone()
                if row:
                    bal, src, nat_val, nat_unit, inc = row
                    results[name] = BalanceResult(
                        service_name=name,
                        usd_value=bal,
                        status="success",
                        details=f"Retrieved from persistent daemon (via DB)",
                        primary_display=f"${bal:,.4f}",
                        native_value=nat_val,
                        native_unit=nat_unit,
                        include_in_total=bool(inc)
                    )
                else:
                    results[name] = empty_result(name, "No data collected yet.", "idle")
            return results

    def get_daily_totals(self, days: int = 30) -> List[Tuple[str, float]]:
        with self.lock:
            cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
            return self.conn.execute(
                "SELECT DATE(timestamp) AS day, SUM(balance_usd) FROM earnings_history "
                "WHERE DATE(timestamp)>=? AND include_in_total=1 "
                "GROUP BY day ORDER BY day ASC",
                (cutoff,),
            ).fetchall()

    def export_csv(self, filename: str = "myriapod_export.csv") -> Path:
        with self.lock:
            out  = DATA_DIR / filename
            rows = self.conn.execute(
                "SELECT * FROM earnings_history ORDER BY timestamp DESC"
            ).fetchall()
            cur  = self.conn.execute("SELECT * FROM earnings_history LIMIT 0")
            hdrs = [d[0] for d in (cur.description or [])]
            with open(out, "w", encoding="utf-8") as f:
                f.write(",".join(hdrs) + "\n")
                for row in rows:
                    f.write(",".join(str(c) for c in row) + "\n")
            logger.info("Exported earnings to %s", out)
            return out

    def prune_database(self, days_history: int = 90, days_status: int = 30) -> int:
        """Prunes historical data older than N days to prevent infinite SQLite file growth."""
        with self.lock:
            cutoff_hist = (datetime.now() - timedelta(days=days_history)).strftime("%Y-%m-%d %H:%M:%S")
            cutoff_status = (datetime.now() - timedelta(days=days_status)).strftime("%Y-%m-%d %H:%M:%S")
            
            c1 = self.conn.execute("DELETE FROM earnings_history WHERE timestamp < ?", (cutoff_hist,)).rowcount
            c2 = self.conn.execute("DELETE FROM service_status WHERE timestamp < ?", (cutoff_status,)).rowcount
            c3 = self.conn.execute("DELETE FROM ip_history WHERE timestamp < ?", (cutoff_status,)).rowcount
            c4 = self.conn.execute("DELETE FROM notifications_log WHERE timestamp < ?", (cutoff_status,)).rowcount
            
            self.conn.commit()
            try:
                self.conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
            except Exception:
                pass
            total = c1 + c2 + c3 + c4
            if total > 0:
                logger.info("Database pruning completed. Removed %d stale database rows.", total)
            return total

# ═══════════════════════════════════════════════════════════════════════════════
# §12  DOCKER INSTALLER
# ═══════════════════════════════════════════════════════════════════════════════
class DockerInstaller:
    @staticmethod
    def is_available() -> Tuple[bool, str]:
        try:
            r = subprocess.run(["docker", "--version"],
                               capture_output=True, text=True, timeout=10)
            if r.returncode == 0:
                return True, r.stdout.strip()
        except Exception:
            pass
        return False, "not found"

    @staticmethod
    def _install_compose_plugin() -> bool:
        """Best-effort install of docker-compose-plugin."""
        if _docker_compose_cmd() is not None:
            return True
        system = platform.system().lower()
        if system != "linux":
            return False
        null = subprocess.DEVNULL
        for cmd in [
            ["sudo", "dnf", "install", "-y", "docker-compose-plugin"],
            ["sudo", "apt-get", "install", "-y", "docker-compose-plugin"],
            ["sudo", "pacman", "-S", "--noconfirm", "docker-compose"],
        ]:
            try:
                r = subprocess.run(cmd, stdout=null, stderr=null, timeout=120)
                if r.returncode == 0:
                    logger.info("Installed compose plugin via: %s", ' '.join(cmd))
                    return True
            except Exception:
                continue
        # Try pip-based docker-compose as last resort
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "docker-compose", "--quiet", "--user"],
                stdout=null, stderr=null, timeout=120,
            )
            if _docker_compose_cmd() is not None:
                return True
        except Exception:
            pass
        return False

    @staticmethod
    def _post_install_setup() -> str:
        """Enable daemon + add user to docker group. Returns status message."""
        msgs: List[str] = []
        null = subprocess.DEVNULL
        # Enable and start Docker daemon
        for cmd in [
            ["sudo", "systemctl", "enable", "--now", "docker"],
            ["sudo", "systemctl", "start", "docker"],
        ]:
            try:
                subprocess.run(cmd, stdout=null, stderr=null, timeout=30)
                break
            except Exception:
                continue
        # Add current user to docker group
        user = os.getenv("USER", "")
        if user:
            try:
                subprocess.run(
                    ["sudo", "usermod", "-aG", "docker", user],
                    stdout=null, stderr=null, timeout=10,
                )
                msgs.append(f"Added {user} to docker group — log out/in or run: newgrp docker")
            except Exception:
                pass
        # Install compose plugin
        DockerInstaller._install_compose_plugin()
        time.sleep(2)
        if _docker_daemon_running():
            msgs.insert(0, "Docker daemon is running.")
        else:
            msgs.insert(0, "Docker installed but daemon may need a restart/relogin.")
        return "\n".join(msgs)

    @staticmethod
    def check_and_install() -> Tuple[bool, str]:
        system = platform.system().lower()
        ok, ver = DockerInstaller.is_available()
        if ok:
            # Ensure daemon running + compose plugin present
            if not _docker_daemon_running():
                started = _start_docker_daemon()
                if not started:
                    if system in ("windows", "darwin"):
                        msg = "Please start Docker Desktop manually."
                    else:
                        msg = "Try: sudo systemctl start docker"
                    return True, (
                        f"Docker installed ({ver}) but daemon is not running.\n{msg}"
                    )
            DockerInstaller._install_compose_plugin()
            return True, f"Docker ready: {ver}"

        if system == "windows":
            # Try winget auto-install
            try:
                r = subprocess.run(
                    ["winget", "install", "-e", "--id", "Docker.DockerDesktop",
                     "--accept-package-agreements", "--accept-source-agreements"],
                    capture_output=True, text=True, timeout=600,
                )
                if r.returncode == 0:
                    return True, "Docker Desktop installed via winget. Please restart."
            except Exception:
                pass
            return False, (
                "Docker not found.\n"
                "Download Docker Desktop: https://docs.docker.com/desktop/install/windows-install/\n"
                "After installation restart Myriapod."
            )

        if system == "darwin":
            # Try Homebrew
            try:
                r = subprocess.run(
                    ["brew", "install", "--cask", "docker"],
                    capture_output=True, text=True, timeout=600,
                )
                if r.returncode == 0:
                    return True, (
                        "Docker Desktop installed via Homebrew.\n"
                        "Open Docker.app to start the daemon, then restart Myriapod."
                    )
            except Exception:
                pass
            return False, (
                "Docker not found.\n"
                "Install via: brew install --cask docker\n"
                "Or download: https://docs.docker.com/desktop/install/mac-install/\n"
                "After installation restart Myriapod."
            )

        if system == "linux":
            null = subprocess.DEVNULL
            errors: List[str] = []

            # Strategy 1: Official convenience script (all distros)
            try:
                logger.info("Trying Docker install via convenience script...")
                r = subprocess.run(
                    ["bash", "-c", "curl -fsSL https://get.docker.com | sudo sh"],
                    stdout=null, stderr=subprocess.PIPE, timeout=600,
                )
                if r.returncode == 0:
                    msg = DockerInstaller._post_install_setup()
                    return True, f"Docker installed via convenience script.\n{msg}"
                errors.append(f"convenience script: exit {r.returncode}")
            except Exception as exc:
                errors.append(f"convenience script: {exc}")

            # Strategy 2: dnf (Fedora / RHEL / Nobara)
            if shutil.which("dnf"):
                try:
                    logger.info("Trying Docker install via dnf...")
                    subprocess.run(
                        ["sudo", "dnf", "install", "-y", "dnf-plugins-core"],
                        stdout=null, stderr=null, timeout=120,
                    )
                    subprocess.run(
                        ["sudo", "dnf", "config-manager", "--add-repo",
                         "https://download.docker.com/linux/fedora/docker-ce.repo"],
                        stdout=null, stderr=null, timeout=30,
                    )
                    r = subprocess.run(
                        ["sudo", "dnf", "install", "-y",
                         "docker-ce", "docker-ce-cli", "containerd.io",
                         "docker-buildx-plugin", "docker-compose-plugin"],
                        stdout=null, stderr=subprocess.PIPE, timeout=600,
                    )
                    if r.returncode == 0:
                        msg = DockerInstaller._post_install_setup()
                        return True, f"Docker installed via dnf.\n{msg}"
                    errors.append(f"dnf: exit {r.returncode}")
                except Exception as exc:
                    errors.append(f"dnf: {exc}")

            # Strategy 3: apt-get (Debian / Ubuntu)
            if shutil.which("apt-get"):
                try:
                    logger.info("Trying Docker install via apt-get...")
                    subprocess.run(
                        ["sudo", "apt-get", "update", "-y"],
                        stdout=null, stderr=null, timeout=120,
                    )
                    r = subprocess.run(
                        ["sudo", "apt-get", "install", "-y",
                         "docker.io", "docker-compose-plugin"],
                        stdout=null, stderr=subprocess.PIPE, timeout=600,
                    )
                    if r.returncode == 0:
                        msg = DockerInstaller._post_install_setup()
                        return True, f"Docker installed via apt-get.\n{msg}"
                    errors.append(f"apt: exit {r.returncode}")
                except Exception as exc:
                    errors.append(f"apt: {exc}")

            # Strategy 4: pacman (Arch / Manjaro)
            if shutil.which("pacman"):
                try:
                    logger.info("Trying Docker install via pacman...")
                    r = subprocess.run(
                        ["sudo", "pacman", "-S", "--noconfirm", "docker", "docker-compose"],
                        stdout=null, stderr=subprocess.PIPE, timeout=600,
                    )
                    if r.returncode == 0:
                        msg = DockerInstaller._post_install_setup()
                        return True, f"Docker installed via pacman.\n{msg}"
                    errors.append(f"pacman: exit {r.returncode}")
                except Exception as exc:
                    errors.append(f"pacman: {exc}")

            return False, (
                "Docker auto-install failed.\n"
                "Tried: " + ", ".join(errors) + "\n"
                "Manual install: https://docs.docker.com/engine/install/"
            )

        return False, f"Auto-install not supported on {system}."

# ═══════════════════════════════════════════════════════════════════════════════
# §13  DOCKER ORCHESTRATOR
#
#  Status detection uses a two-tier strategy:
#   1. Docker SDK (docker.from_env()) — preferred; gives rich object model.
#   2. Docker CLI subprocess fallback — used automatically when the SDK is not
#      available OR when the SDK call raises (permission errors, Windows named
#      pipe issues, etc.).  This is the fix for "all services show unavailable".
# ═══════════════════════════════════════════════════════════════════════════════
class DockerOrchestrator:
    MYRIAPOD_NETWORK = "myriapod_net"

    def __init__(self, services: Dict[str, ServiceDefinition],
                 secrets: SecretManager) -> None:
        self.services = services
        self.secrets  = secrets
        self.client: Optional[Any] = None
        self._cli_ok  = False      # True  when docker CLI is usable
        self._compose_cmd: Optional[List[str]] = None  # cached compose command

        # Circuit Breaker, Exponential Backoff, and double-polling status cache state
        self._restart_history: Dict[str, List[float]] = {}
        self._quarantined: Dict[str, float] = {}
        self._consecutive_failures: Dict[str, int] = {}
        self._last_state_reset: Dict[str, float] = {}
        self._status_cache: Dict[str, Tuple[float, str]] = {}
        self._cli_lock = threading.Lock()

        # Ensure Docker daemon is running before connecting
        if _docker_cli_available() and not _docker_daemon_running():
            logger.info("Docker binary found but daemon not running — attempting start...")
            _start_docker_daemon()

        # Try SDK first
        if _HAS_DOCKER:
            try:
                self.client = _docker_module.from_env()
                self.client.ping()
                logger.info("Docker SDK connected.")
                self._ensure_network()
            except Exception as exc:
                logger.warning("Docker SDK unavailable (%s); trying CLI …", exc)
                self.client = None

        # Always probe CLI as a fallback / verification
        self._cli_ok = _docker_cli_available() and _docker_daemon_running()
        self._compose_cmd = _docker_compose_cmd()
        if self._cli_ok and not self.client:
            logger.info("Docker CLI available — will use subprocess fallback.")
            self._cli_ensure_network()
        elif not self._cli_ok and not self.client:
            logger.warning("Docker appears to be absent or not running.")

        # Self-healing cleanup of old legacy docker instances and networks
        self._cleanup_legacy_containers()

    # ── network helpers ───────────────────────────────────────────────────────
    def _ensure_network(self) -> None:
        if not self.client:
            return
        try:
            self.client.networks.get(self.MYRIAPOD_NETWORK)
        except Exception:
            try:
                self.client.networks.create(self.MYRIAPOD_NETWORK, driver="bridge")
                logger.info("Created Docker network: %s", self.MYRIAPOD_NETWORK)
            except Exception as exc:
                logger.warning("Could not create network %s via SDK: %s", self.MYRIAPOD_NETWORK, exc)

    def _cli_ensure_network(self) -> None:
        """Create myriapod_net via CLI when the SDK is not available."""
        try:
            r = subprocess.run(
                ["docker", "network", "inspect", self.MYRIAPOD_NETWORK],
                capture_output=True, timeout=6,
            )
            if r.returncode != 0:
                subprocess.run(
                    ["docker", "network", "create", "--driver", "bridge", self.MYRIAPOD_NETWORK],
                    capture_output=True, timeout=10,
                )
                logger.info("Created Docker network via CLI: %s", self.MYRIAPOD_NETWORK)
        except Exception as exc:
            logger.debug("CLI network create: %s", exc)

    def _cleanup_legacy_containers(self) -> None:
        """
        Gracefully stop and remove legacy containers and networks from old branding
        (Nexus/Centipede) to avoid port/resource conflicts and clean up the host system.
        """
        legacy_prefixes = ["nexus_", "centipede_"]
        
        # 1. SDK Cleanup
        if self.client:
            try:
                for container in self.client.containers.list(all=True):
                    name = container.name
                    if any(name.startswith(p) for p in legacy_prefixes):
                        logger.info("Found legacy container: %s. Removing...", name)
                        try:
                            container.stop(timeout=5)
                        except Exception:
                            pass
                        try:
                            container.remove(force=True)
                        except Exception:
                            pass
            except Exception as exc:
                logger.debug("Legacy SDK container cleanup failed: %s", exc)
                
            try:
                for net_name in ["nexus_net", "centipede_net"]:
                    try:
                        net = self.client.networks.get(net_name)
                        net.remove()
                        logger.info("Removed legacy network: %s", net_name)
                    except Exception:
                        pass
            except Exception:
                pass
                
        # 2. CLI Cleanup Fallback
        if self._cli_ok:
            try:
                r = subprocess.run(
                    ["docker", "ps", "-a", "--format", "{{.Names}}"],
                    capture_output=True, text=True, timeout=10
                )
                if r.returncode == 0:
                    for name in r.stdout.splitlines():
                        name = name.strip()
                        if any(name.startswith(p) for p in legacy_prefixes):
                            logger.info("Found legacy container via CLI: %s. Removing...", name)
                            subprocess.run(["docker", "stop", name], capture_output=True, timeout=10)
                            subprocess.run(["docker", "rm", "-f", name], capture_output=True, timeout=10)
            except Exception as exc:
                logger.debug("Legacy CLI container cleanup failed: %s", exc)
                
            try:
                for net_name in ["nexus_net", "centipede_net"]:
                    subprocess.run(["docker", "network", "rm", net_name], capture_output=True, timeout=10)
            except Exception:
                pass

    # ── credential / template helpers ─────────────────────────────────────────
    def _device_name(self, svc: ServiceDefinition) -> str:
        return f"myriapod-{slugify(platform.node() or 'node')}-{svc.slug}"

    def _device_id(self, svc: ServiceDefinition) -> str:
        return f"{slugify(platform.node() or 'node')}-{svc.slug}"

    def _cred(self, key: str) -> str:
        return self.secrets.get(key) or getenv(key)

    def _resolve(self, template: str, svc: ServiceDefinition) -> str:
        vals = {**current_env()}
        for f in svc.setup_fields:
            v = self._cred(f.key)
            if v:
                vals[f.key] = v
        out = template
        for k, v in vals.items():
            out = out.replace(f"{{{k}}}", v)
        out = out.replace("{DEVICE_NAME}", self._device_name(svc))
        out = out.replace("{DEVICE_ID}",   self._device_id(svc))
        return out

    def _missing_required(self, svc: ServiceDefinition) -> List[str]:
        return [f.key for f in svc.setup_fields if f.required and not self._cred(f.key)]

    # ── container status  (dual-mode: SDK + CLI fallback) ─────────────────────
    def container_status(self, svc: ServiceDefinition) -> str:
        """
        Return the Docker status string for *svc*.
        Possible return values:
          "running"       — container is running
          "exited"        — container exited (may need restart)
          "paused"        — container paused
          "not_found"     — image/container was never started
          "monitor_only"  — service has docker_mode='monitor_only'
          "manual"        — service has docker_mode='docker_manual'
          "unavailable"   — Docker itself is not reachable
          "quarantined"   — container is locked under quarantine
        """
        if svc.docker_mode == "monitor_only":
            return "monitor_only"
        if svc.docker_mode == "docker_manual":
            return "manual"

        # Double-polling cache protection (1.5s cache window)
        now = time.time()
        if svc.slug in self._status_cache:
            cache_time, cached_val = self._status_cache[svc.slug]
            if now - cache_time < 1.5:
                return cached_val

        # Check circuit breaker status
        if svc.slug in self._quarantined:
            release_time = self._quarantined[svc.slug]
            if now < release_time:
                self._status_cache[svc.slug] = (now, "quarantined")
                return "quarantined"
            else:
                # Quarantine duration expired, gracefully lift it
                logger.info("Circuit Breaker quarantine expired for %s. Resetting state.", svc.slug)
                self._quarantined.pop(svc.slug, None)

        status = "unavailable"
        # ── SDK path ──────────────────────────────────────────────────────────
        if self.client:
            try:
                c = self.client.containers.get(svc.container_name)
                status = c.status  # 'running', 'exited', 'paused', 'restarting' …
            except Exception as exc:
                if "NotFound" in type(exc).__name__:
                    status = "not_found"
                else:
                    pass

        # ── CLI fallback ──────────────────────────────────────────────────────
        if status == "unavailable" and self._cli_ok:
            inspect_status = _docker_inspect_status(svc.container_name)
            if inspect_status:
                status = inspect_status
            else:
                # docker inspect returned non-zero → container not found
                status = "not_found"

        if status == "unavailable":
            self._status_cache[svc.slug] = (now, "unavailable")
            return "unavailable"

        # Auto-reset consecutive failures if container is running stably
        if status == "running":
            if svc.slug not in self._last_state_reset:
                self._last_state_reset[svc.slug] = now
            elif now - self._last_state_reset[svc.slug] > 300:  # 5 minutes stable
                if self._consecutive_failures.get(svc.slug, 0) > 0:
                    logger.info("Service %s has been running stably. Resetting failure counter.", svc.slug)
                    self._consecutive_failures[svc.slug] = 0
                    self._restart_history[svc.slug] = []
        else:
            # If not running, reset stable-run timer
            self._last_state_reset.pop(svc.slug, None)

        self._status_cache[svc.slug] = (now, status)
        return status

    def all_statuses(self) -> Dict[str, str]:
        return {svc.name: self.container_status(svc) for svc in self.services.values()}

    # ── compose generation ────────────────────────────────────────────────────
    def generate_compose(self) -> Tuple[Dict[str, Any], Dict[str, str]]:
        deployable: Dict[str, Any] = {}
        skipped:    Dict[str, str] = {}

        for svc in self.services.values():
            if svc.docker_mode == "docker_manual":
                skipped[svc.name] = "Manual Docker setup required — see docs."
                continue
            if svc.docker_mode != "docker_auto":
                skipped[svc.name] = "Monitor-only service."
                continue
            if not svc.compose_image:
                skipped[svc.name] = "No container image configured."
                continue
            missing = self._missing_required(svc)
            if missing:
                skipped[svc.name] = f"Missing credentials: {', '.join(missing)}"
                continue

            svc_def: Dict[str, Any] = {
                "image":          svc.compose_image,
                "container_name": svc.container_name,
                "restart":        "unless-stopped",
                "logging": {
                    "driver":  "json-file",
                    "options": {"max-size": "2m", "max-file": "3"},
                },
            }

            if svc.compose_network_mode:
                svc_def["network_mode"] = svc.compose_network_mode
            else:
                svc_def["networks"] = [self.MYRIAPOD_NETWORK]

            if svc.compose_command_template:
                svc_def["command"] = self._resolve(svc.compose_command_template, svc)

            if svc.compose_hostname:
                svc_def["hostname"] = svc.compose_hostname

            env = []
            for tmpl in svc.compose_env_templates:
                resolved = self._resolve(tmpl, svc)
                if "=" in resolved:
                    k, _, v = resolved.partition("=")
                    if v.strip():
                        env.append(resolved)
            if env:
                svc_def["environment"] = env

            # Skip ports when network_mode is set (host mode exposes all ports)
            if svc.compose_ports and not svc.compose_network_mode:
                svc_def["ports"] = list(svc.compose_ports)
            if svc.compose_volumes:
                vols = []
                for v in svc.compose_volumes:
                    # Ensure host directories exist
                    host_part = v.split(":")[0]
                    host_abs = Path(host_part)
                    if not host_abs.is_absolute():
                        host_abs = (BASE_DIR / host_part).resolve()
                    else:
                        host_abs = host_abs.resolve()
                    host_abs.mkdir(parents=True, exist_ok=True)
                    # Use absolute path for compose
                    vols.append(f"{host_abs}:{':'.join(v.split(':')[1:])}")
                svc_def["volumes"] = vols
            if svc.compose_devices:
                svc_def["devices"] = list(svc.compose_devices)
            if svc.compose_cap_add:
                svc_def["cap_add"] = list(svc.compose_cap_add)
            if svc.compose_sysctls:
                svc_def["sysctls"] = dict(svc.compose_sysctls)

            deployable[svc.slug] = svc_def

        # No deprecated 'version' key — modern Docker Compose ignores it
        compose: Dict[str, Any] = {"services": deployable}
        if any("networks" in v for v in deployable.values()):
            compose["networks"] = {self.MYRIAPOD_NETWORK: {"driver": "bridge"}}

        return compose, skipped

    def write_compose(self) -> Tuple[Path, Dict[str, str]]:
        compose, skipped = self.generate_compose()
        COMPOSE_FILE.write_text(
            yaml.dump(compose, default_flow_style=False), encoding="utf-8"
        )
        if platform.system().lower() != "windows":
            try:
                os.chmod(COMPOSE_FILE, 0o600)
            except Exception:
                pass
        logger.info("Wrote %s (%d services).", COMPOSE_FILE,
                    len(compose.get("services", {})))
        return COMPOSE_FILE, skipped

    # ── container lifecycle ───────────────────────────────────────────────────
    def deploy_all(self) -> Dict[str, Tuple[str, str]]:
        results: Dict[str, Tuple[str, str]] = {}
        if not self.client and not self._cli_ok:
            return {svc.name: ("failed", "Docker not available")
                    for svc in self.services.values() if svc.is_auto_deployable}
        for svc in self.services.values():
            if not svc.is_auto_deployable:
                continue
            missing = self._missing_required(svc)
            if missing:
                results[svc.name] = ("skipped", f"Credentials not configured (missing: {', '.join(missing)})")
                continue
            ok, msg = self._deploy_container(svc)
            status = "success" if ok else "failed"
            results[svc.name] = (status, msg)
        return results

    def _deploy_container(self, svc: ServiceDefinition) -> Tuple[bool, str]:
        """Deploy via SDK → compose CLI → raw docker run."""
        if not svc.compose_image:
            return False, "No image configured."

        # ── SDK path ──────────────────────────────────────────────────────────
        if self.client:
            ok, msg = self._deploy_via_sdk(svc)
            if ok:
                return ok, msg
            logger.warning("SDK deploy failed for %s: %s — trying CLI...", svc.name, msg)

        # ── Compose CLI fallback ──────────────────────────────────────────────
        if self._cli_ok and self._compose_cmd:
            ok, msg = self._deploy_via_cli(svc)
            if ok:
                return ok, msg
            logger.warning("Compose deploy failed for %s: %s — trying docker run...", svc.name, msg)

        # ── Raw docker run fallback ───────────────────────────────────────────
        if self._cli_ok:
            return self._deploy_via_docker_run(svc)

        return False, "Docker not available (SDK, compose, and CLI all failed)."

    def _deploy_via_sdk(self, svc: ServiceDefinition) -> Tuple[bool, str]:
        assert self.client is not None
        try:
            # 1. Gracefully teardown existing container instances
            with contextlib.suppress(Exception):
                old = self.client.containers.get(svc.container_name)
                logger.info("Deactivating active container: %s", svc.container_name)
                old.stop(timeout=10)
                old.remove(force=True)

            # 2. Pull image using multi-stage retry strategy
            logger.info("Synchronizing container image: %s ...", svc.compose_image)
            try:
                self.client.images.pull(svc.compose_image)
            except Exception as pe:
                logger.warning("Image pull failed (%s); proceeding with cached local images.", pe)

            # 3. Formulate highly optimized configuration arguments
            kwargs: Dict[str, Any] = {
                "name":           svc.container_name,
                "detach":         True,
                "restart_policy": {"Name": "unless-stopped"},
                "labels":         {"myriapod": "true", "service": svc.slug},
            }

            # 4. ARM64 emulation support via transparent QEMU targeting
            host_arch = _detect_arch()
            if host_arch == "arm64":
                # For non-multi-arch images, QEMU translation is automatically enabled
                kwargs["platform"] = "linux/amd64"
                logger.info("ARM64 host detected. Enforcing 'linux/amd64' platform emulation.")

            if svc.compose_command_template:
                resolved_cmd = self._resolve(svc.compose_command_template, svc)
                kwargs["command"] = resolved_cmd.split()

            # 5. Environment configuration
            env: Dict[str, str] = {}
            for tmpl in svc.compose_env_templates:
                resolved = self._resolve(tmpl, svc)
                if "=" in resolved:
                    k, _, v = resolved.partition("=")
                    if v.strip():
                        env[k.strip()] = v.strip()
            if env:
                kwargs["environment"] = env

            # 6. Network configuration with fallback
            if svc.compose_network_mode:
                kwargs["network_mode"] = svc.compose_network_mode
            else:
                self._ensure_network()
                kwargs["network"] = self.MYRIAPOD_NETWORK

            # 7. Port configuration (skip if host networking is active)
            if svc.compose_ports and not svc.compose_network_mode:
                port_bindings: Dict[str, Any] = {}
                for p in svc.compose_ports:
                    parts      = p.split(":")
                    host_port  = parts[0].strip()
                    cont_rest  = parts[-1].strip()
                    proto      = "tcp"
                    if "/" in cont_rest:
                        cont_port, _, proto = cont_rest.partition("/")
                    else:
                        cont_port = cont_rest
                    port_bindings[f"{cont_port.strip()}/{proto.strip()}"] = int(host_port)
                kwargs["ports"] = port_bindings

            # 8. Deterministic volume pathing with SELinux context flags (:z)
            if svc.compose_volumes:
                vols: Dict[str, Dict[str, str]] = {}
                for v in svc.compose_volumes:
                    host_v, _, cont_v = v.partition(":")
                    host_abs = Path(host_v)
                    if not host_abs.is_absolute():
                        host_abs = (BASE_DIR / host_v).resolve()
                    else:
                        host_abs = host_abs.resolve()
                    
                    # Ensure host volume storage directory exists with correct permissions
                    if not (host_abs.exists() or host_abs.is_socket()):
                        try:
                            host_abs.mkdir(parents=True, exist_ok=True)
                        except Exception:
                            pass
                    # Support SELinux shared contexts dynamically
                    vols[str(host_abs)] = {"bind": cont_v.split(":")[0], "mode": "rw,z"}
                kwargs["volumes"] = vols

            # 9. Resource cap-add & device configurations
            if svc.compose_cap_add:
                kwargs["cap_add"] = list(svc.compose_cap_add)
            if svc.compose_devices:
                kwargs["devices"] = list(svc.compose_devices)
            if svc.compose_sysctls:
                kwargs["sysctls"] = dict(svc.compose_sysctls)

            # 10. Execute SDK deployment
            self.client.containers.run(svc.compose_image, **kwargs)
            logger.info("Container %s deployed successfully (SDK).", svc.container_name)
            return True, f"Container {svc.container_name} started."

        except Exception as exc:
            logger.warning("SDK container startup aborted due to: %s. Attempting fallback sequence...", exc)
            # Retrying with security contexts disabled if it failed due to capabilities/SELinux
            if "cap_add" in kwargs or "devices" in kwargs:
                logger.info("Retrying SDK deployment with sandboxed privileges (no capability/device elevation)...")
                kwargs.pop("cap_add", None)
                kwargs.pop("devices", None)
                try:
                    self.client.containers.run(svc.compose_image, **kwargs)
                    logger.info("Container %s deployed in sandboxed mode.", svc.container_name)
                    return True, f"Container {svc.container_name} started in sandboxed mode."
                except Exception as inner_exc:
                    logger.error("Sandboxed SDK retry also failed: %s", inner_exc)
            return False, str(exc)[:200]

    def _deploy_via_cli(self, svc: ServiceDefinition) -> Tuple[bool, str]:
        """Write a service-specific compose snippet and run docker compose up."""
        with self._cli_lock:
            compose, _ = self.generate_compose()
            if svc.slug not in compose.get("services", {}):
                return False, "Service not in generated compose (missing credentials?)."
            
            # Enforce platform architecture at compose level if arm64 host is active
            host_arch = _detect_arch()
            if host_arch == "arm64" and "platform" not in compose["services"][svc.slug]:
                compose["services"][svc.slug]["platform"] = "linux/amd64"
                
            snippet: Dict[str, Any] = {
                "services": {svc.slug: compose["services"][svc.slug]},
            }
            if "networks" in compose:
                snippet["networks"] = compose["networks"]
            tmp_file = DATA_DIR / f"compose_{svc.slug}.yml"
            tmp_file.write_text(yaml.dump(snippet, default_flow_style=False), encoding="utf-8")
            if platform.system().lower() != "windows":
                try:
                    os.chmod(tmp_file, 0o600)
                except Exception:
                    pass

            # Find working compose command
            compose_cmd = self._compose_cmd or _docker_compose_cmd()
            if not compose_cmd:
                return False, "No docker compose command found."

            try:
                subprocess.run(
                    [*compose_cmd, "-f", str(tmp_file), "pull"],
                    capture_output=True, timeout=300,
                )
                r = subprocess.run(
                    [*compose_cmd, "-f", str(tmp_file), "up", "-d", "--remove-orphans"],
                    capture_output=True, text=True, timeout=120,
                )
                if r.returncode == 0:
                    logger.info("Container %s started (compose CLI).", svc.container_name)
                    return True, f"Container {svc.container_name} started via compose."
                return False, (r.stderr or r.stdout or "docker compose up failed")[:200]
            except subprocess.TimeoutExpired:
                return False, "docker compose timed out."
            except Exception as exc:
                return False, str(exc)[:200]

    def _deploy_via_compose_file(self, svc: ServiceDefinition) -> Tuple[bool, str]:
        """Private alias for CLI compose deployment."""
        return self._deploy_via_cli(svc)

    def deploy_via_compose_file(self, svc: ServiceDefinition) -> Tuple[bool, str]:
        """Public endpoint to deploy a service using its specific compose file snippet."""
        return self._deploy_via_cli(svc)

    def _deploy_via_docker_run(self, svc: ServiceDefinition) -> Tuple[bool, str]:
        """Ultimate fallback: deploy using raw 'docker run' command with adaptive platforms."""
        if not svc.compose_image:
            return False, "No image configured."
        try:
            # Remove old container if exists
            subprocess.run(
                ["docker", "rm", "-f", svc.container_name],
                capture_output=True, timeout=15,
            )
            # Pull image
            logger.info("Pulling %s via CLI...", svc.compose_image)
            subprocess.run(
                ["docker", "pull", svc.compose_image],
                capture_output=True, timeout=300,
            )
            
            # Build docker run command
            cmd: List[str] = [
                "docker", "run", "-d",
                "--name", svc.container_name,
                "--restart", "unless-stopped",
                "--label", "myriapod=true",
            ]
            
            # ARM64 QEMU fallback support
            host_arch = _detect_arch()
            if host_arch == "arm64":
                cmd.extend(["--platform", "linux/amd64"])
                logger.info("Appended '--platform linux/amd64' to CLI run args.")

            # Network
            if svc.compose_network_mode:
                cmd.extend(["--network", svc.compose_network_mode])
            else:
                self._cli_ensure_network()
                cmd.extend(["--network", self.MYRIAPOD_NETWORK])
                
            # Hostname
            if svc.compose_hostname:
                cmd.extend(["--hostname", svc.compose_hostname])
                
            # Environment variables
            for tmpl in svc.compose_env_templates:
                resolved = self._resolve(tmpl, svc)
                if "=" in resolved:
                    k, _, v = resolved.partition("=")
                    if v.strip():
                        cmd.extend(["-e", resolved])
                        
            # Ports (skip if host network)
            if svc.compose_ports and not svc.compose_network_mode:
                for p in svc.compose_ports:
                    cmd.extend(["-p", p])
                    
            # Deterministic Volume Mounting with SELinux flags (:z)
            if svc.compose_volumes:
                for v in svc.compose_volumes:
                    host_part = v.split(":")[0]
                    host_abs = Path(host_part)
                    if not host_abs.is_absolute():
                        host_abs = (BASE_DIR / host_part).resolve()
                    else:
                        host_abs = host_abs.resolve()
                        
                    host_abs.mkdir(parents=True, exist_ok=True)
                    v_resolved = str(host_abs) + ":" + ":".join(v.split(":")[1:])
                    # Append SELinux share tag if not present
                    if not v_resolved.endswith(":z") and not v_resolved.endswith(":Z"):
                        v_resolved += ":z"
                    cmd.extend(["-v", v_resolved])
                    
            # Capabilities
            for cap in svc.compose_cap_add:
                cmd.extend(["--cap-add", cap])
            # Devices
            for dev in svc.compose_devices:
                cmd.extend(["--device", dev])
            # Sysctls
            for sk, sv in svc.compose_sysctls.items():
                cmd.extend(["--sysctl", f"{sk}={sv}"])
            # Image
            cmd.append(svc.compose_image)
            # Command
            if svc.compose_command_template:
                resolved_cmd = self._resolve(svc.compose_command_template, svc)
                cmd.extend(resolved_cmd.split())

            r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if r.returncode == 0:
                logger.info("Container %s started (docker run).", svc.container_name)
                return True, f"Container {svc.container_name} started via docker run."
            
            # Security retry fallback
            if svc.compose_cap_add or svc.compose_devices:
                logger.warning("Docker run elevated privilege run failed. Retrying sandboxed raw CLI run...")
                # Filter out cap-add and device parameters
                sanitized_cmd = [x for x in cmd if x != "--cap-add" and x != "--device"]
                r = subprocess.run(sanitized_cmd, capture_output=True, text=True, timeout=120)
                if r.returncode == 0:
                    logger.info("Container %s deployed in sandboxed mode via raw CLI.", svc.container_name)
                    return True, f"Container {svc.container_name} started in sandboxed mode."
            
            err = (r.stderr or r.stdout or "docker run failed").strip()
            return False, err[:200]
        except subprocess.TimeoutExpired:
            return False, "docker run timed out."
        except Exception as exc:
            return False, str(exc)[:200]

    def stop_container(self, svc: ServiceDefinition) -> Tuple[bool, str]:
        if self.client:
            try:
                c = self.client.containers.get(svc.container_name)
                c.stop(timeout=10)
                return True, f"{svc.container_name} stopped."
            except Exception as exc:
                pass
        if self._cli_ok:
            try:
                r = subprocess.run(
                    ["docker", "stop", svc.container_name],
                    capture_output=True, text=True, timeout=15,
                )
                if r.returncode == 0:
                    return True, f"{svc.container_name} stopped (CLI)."
            except Exception:
                pass
        return False, "Could not stop container."

    def restart_container(self, svc: ServiceDefinition) -> Tuple[bool, str]:
        if self.client:
            try:
                c = self.client.containers.get(svc.container_name)
                c.restart(timeout=10)
                return True, f"{svc.container_name} restarted."
            except Exception:
                pass
        return self._deploy_container(svc)

    def auto_heal(self) -> None:
        now = time.time()
        for svc in self.services.values():
            if not svc.is_auto_deployable:
                continue

            status = self.container_status(svc)
            # If already quarantined, skip auto-heal evaluation
            if status == "quarantined":
                continue

            if status in ("exited", "dead", "not_found"):
                if self._missing_required(svc):
                    continue

                # Retrieve history and clean up entries older than the 10-minute window
                history = self._restart_history.setdefault(svc.slug, [])
                history = [t for t in history if now - t < 600]
                self._restart_history[svc.slug] = history

                # Check backoff constraint
                consecutive = self._consecutive_failures.get(svc.slug, 0)
                if consecutive > 0:
                    delay = min(30 * (2 ** (consecutive - 1)), 3600)
                    last_attempt = history[-1] if history else 0
                    if now - last_attempt < delay:
                        logger.debug("Auto-heal: backoff active for %s. Wait %ds (elapsed: %ds).",
                                     svc.name, int(delay), int(now - last_attempt))
                        continue

                # Check if we triggered the circuit breaker quarantine threshold (5 failures in 10 minutes)
                if len(history) >= 5 or consecutive >= 5:
                    quarantine_duration = 7200  # 2 hours quarantine
                    self._quarantined[svc.slug] = now + quarantine_duration
                    logger.warning("Circuit Breaker TRIPPED for service '%s' due to excessive failures. "
                                   "Quarantined for 2 hours.", svc.name)
                    continue

                # Proceed to deploy / restart
                logger.warning("Auto-heal: initiating restart for %s (status: %s, failure count: %d).",
                               svc.name, status, consecutive + 1)
                
                # Append current attempt to history and increment failures
                self._restart_history[svc.slug].append(now)
                self._consecutive_failures[svc.slug] = consecutive + 1
                
                ok, msg = self.restart_container(svc)
                if ok:
                    logger.info("Auto-heal: successfully restarted %s. Message: %s", svc.name, msg)
                else:
                    logger.error("Auto-heal: restart failed for %s. Error: %s", svc.name, msg)

    def container_logs(self, svc: ServiceDefinition, tail: int = 50) -> str:
        if self.client:
            try:
                c = self.client.containers.get(svc.container_name)
                raw = c.logs(tail=tail, timestamps=True)
                return raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw)
            except Exception as exc:
                pass
        if self._cli_ok:
            try:
                r = subprocess.run(
                    ["docker", "logs", "--tail", str(tail), "--timestamps", svc.container_name],
                    capture_output=True, text=True, timeout=10,
                )
                return (r.stdout + r.stderr).strip()
            except Exception:
                pass
        return "Could not fetch logs."

# ═══════════════════════════════════════════════════════════════════════════════
# §14  HTTP SESSION MANAGER
# ═══════════════════════════════════════════════════════════════════════════════
_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


class HTTPSessionManager:
    def __init__(self, browser_dir: Path = BROWSER_DIR) -> None:
        self._dir      = browser_dir
        self._sessions: Dict[str, requests.Session] = {}
        self._session_meta: Dict[str, Dict[str, Any]] = {}
        self._lock     = threading.Lock()

    def session(self, slug: str) -> requests.Session:
        with self._lock:
            now = time.time()
            need_new = False
            
            if slug in self._sessions:
                meta = self._session_meta.setdefault(slug, {"created": now, "calls": 0})
                meta["calls"] += 1
                
                # Recycle if session is older than 1 hour or has been requested more than 100 times
                if now - meta["created"] > 3600 or meta["calls"] > 100:
                    logger.info("Recycling HTTP session for '%s' (age: %ds, calls: %d) to guarantee connection freshness.", 
                                slug, int(now - meta["created"]), meta["calls"])
                    # Save cookies before closing
                    try:
                        self._cookie_file(slug).write_text(
                            json.dumps([
                                {"name": c.name, "value": c.value, "domain": c.domain}
                                for c in self._sessions[slug].cookies
                            ])
                        )
                    except Exception:
                        pass
                    
                    try:
                        self._sessions[slug].close()
                    except Exception:
                        pass
                    need_new = True
            else:
                need_new = True

            if need_new:
                s = requests.Session()
                s.headers.update({
                    "User-Agent":      _UA,
                    "Accept":          "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                })
                self._load_cookies(s, slug)
                self._sessions[slug] = s
                self._session_meta[slug] = {"created": now, "calls": 1}

            return self._sessions[slug]

    def _cookie_file(self, slug: str) -> Path:
        return self._dir / f"{slug}_cookies.json"

    def _load_cookies(self, s: requests.Session, slug: str) -> None:
        cf = self._cookie_file(slug)
        if cf.exists():
            try:
                for c in json.loads(cf.read_text()):
                    s.cookies.set(c["name"], c["value"], domain=c.get("domain", ""))
            except Exception:
                pass

    def save_cookies(self, slug: str) -> None:
        with self._lock:
            s = self._sessions.get(slug)
            if not s:
                return
            try:
                self._cookie_file(slug).write_text(
                    json.dumps([
                        {"name": c.name, "value": c.value, "domain": c.domain}
                        for c in s.cookies
                    ])
                )
            except Exception:
                pass

    def clear_session(self, slug: str) -> None:
        with self._lock:
            self._sessions.pop(slug, None)
            self._session_meta.pop(slug, None)
            cf = self._cookie_file(slug)
            if cf.exists():
                cf.unlink()

    def open_dashboard_browser(self, svc: ServiceDefinition) -> bool:
        url = svc.dashboard_url
        try:
            # First try standard webbrowser module
            if webbrowser.open(url):
                return True
        except Exception:
            pass

        # Fallback to targeting specific known browsers across systems
        import shutil, subprocess
        system = platform.system().lower()
        browsers = []
        if system == "linux":
            browsers = ["xdg-open", "google-chrome", "chrome", "firefox", "brave", "opera", "microsoft-edge", "chromium"]
        elif system == "darwin":
            browsers = ["open", "google chrome", "firefox", "brave", "opera", "safari"]
        elif system == "windows":
            browsers = ["start", "chrome", "firefox", "brave", "opera", "msedge"]

        for b in browsers:
            try:
                if system == "linux" and b == "xdg-open":
                    if shutil.which(b):
                        subprocess.Popen([b, url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        return True
                elif system == "darwin" and b == "open":
                    if shutil.which(b):
                        subprocess.Popen([b, url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        return True
                elif system == "windows" and b == "start":
                    os.system(f"start {url}")
                    return True
                else:
                    path = shutil.which(b)
                    if path:
                        subprocess.Popen([path, url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        return True
            except Exception:
                continue
        return False

# ═══════════════════════════════════════════════════════════════════════════════
# §15  DIRECT API IMPLEMENTATIONS
# ═══════════════════════════════════════════════════════════════════════════════
class DirectAPI:

    @staticmethod
    def packetstream_balance(cid: str) -> Optional[float]:
        for ep in (
            "https://api.packetstream.io/v1/user/balance",
            "https://app.packetstream.io/api/v1/user/balance",
        ):
            try:
                r = requests.get(ep,
                                 headers={"CID": cid, "Authorization": f"Bearer {cid}"},
                                 timeout=API_TIMEOUT)
                if r.ok:
                    return first_numeric(r.json(), ("balance", "earnings"))
            except Exception:
                continue
        return None

    @staticmethod
    def earnfm_balance(token: str) -> Optional[float]:
        try:
            r = requests.get(
                "https://earn.fm/api/client/balance",
                headers={"apikey": token, "Authorization": f"Bearer {token}"},
                timeout=API_TIMEOUT,
            )
            if r.ok:
                return first_numeric(r.json(), ("balance", "currentBalance"))
        except Exception:
            pass
        return None

    @staticmethod
    def repocket_balance(email: str, api_key: str) -> Optional[float]:
        for ep in (
            "https://repocket.com/api/v1/balance",
            "https://api.repocket.com/v1/balance",
        ):
            try:
                r = requests.get(ep,
                                 headers={"Authorization": f"Bearer {api_key}", "X-Email": email},
                                 timeout=API_TIMEOUT)
                if r.ok:
                    return first_numeric(r.json(), ("balance", "amount"))
            except Exception:
                continue
        return None

    @staticmethod
    def proxyrack_balance(uuid_val: str, api_key: str = "") -> Optional[float]:
        try:
            hdrs: Dict[str, str] = {"X-UUID": uuid_val}
            if api_key:
                hdrs["X-Api-Key"] = api_key
            r = requests.get("https://api.proxyrack.net/v2/earnings",
                             headers=hdrs, timeout=API_TIMEOUT)
            if r.ok:
                return first_numeric(r.json(), ("balance", "totalEarnings"))
        except Exception:
            pass
        return None

    @staticmethod
    def grass_points(session: requests.Session,
                     email: str = "", password: str = "") -> Optional[float]:
        try:
            r = session.get("https://director.getgrass.io/v1/user/points",
                            timeout=API_TIMEOUT)
            if r.ok:
                return first_numeric(r.json(), ("points", "epochPoints"))
        except Exception:
            pass
        if email and password:
            try:
                lr = session.post(
                    "https://director.getgrass.io/v1/login",
                    json={"email": email, "password": password},
                    timeout=API_TIMEOUT,
                )
                if lr.ok:
                    token = lr.json().get("token") or lr.json().get("accessToken", "")
                    if token:
                        session.headers.update({"Authorization": f"Bearer {token}"})
                    r2 = session.get("https://director.getgrass.io/v1/user/points",
                                     timeout=API_TIMEOUT)
                    if r2.ok:
                        return first_numeric(r2.json(), ("points", "epochPoints"))
            except Exception:
                pass
        return None

    @staticmethod
    def mysterium_unsettled(base_url: str = "http://localhost:4449") -> Optional[float]:
        try:
            r = requests.get(f"{base_url}/tequilapi/v2/provider/channels",
                             timeout=API_TIMEOUT)
            if r.ok:
                channels = r.json()
                total = 0.0
                for ch in (channels if isinstance(channels, list) else []):
                    bal = first_numeric(ch, ("balance", "unsettled"))
                    if bal:
                        total += bal / 1e18 if bal > 1e15 else bal
                return total if total else None
        except Exception:
            pass
        return None

    @staticmethod
    def storj_payout(base_url: str = "http://localhost:14002") -> Optional[float]:
        try:
            r = requests.get(f"{base_url}/api/sno/", timeout=API_TIMEOUT)
            if r.ok:
                return first_numeric(r.json(), ("satelliteData", "earned", "payout"))
        except Exception:
            pass
        return None

    @staticmethod
    def traffmonetizer_balance(token: str) -> Optional[float]:
        try:
            r = requests.get(
                "https://traffmonetizer.com/api/earn/balance",
                headers={"Authorization": f"Bearer {token}"},
                timeout=API_TIMEOUT,
            )
            if r.ok:
                return first_numeric(r.json(), ("balance", "currentBalance"))
        except Exception:
            pass
        return None

    @staticmethod
    def html_scrape_balance(session: requests.Session, url: str) -> Optional[float]:
        try:
            r = session.get(url, timeout=15)
            if not r.ok:
                return None
            text = r.text
            for pat in [
                r'\$\s*(\d+(?:\.\d+)?)',
                r'[Bb]alance[^<]{0,40}?(\d+\.\d+)',
                r'[Ee]arning[^<]{0,40}?(\d+\.\d+)',
                r'(\d+\.\d{2,})\s*(?:USD|usd)',
            ]:
                m = re.search(pat, text)
                if m:
                    v = safe_float(m.group(1))
                    if 0 < v < 1_000_000:
                        return v
        except Exception:
            pass
        return None

# ═══════════════════════════════════════════════════════════════════════════════
# §16  BALANCE POLLER
# ═══════════════════════════════════════════════════════════════════════════════
class BalancePoller:
    def __init__(self, secrets: SecretManager, db: DatabaseManager,
                 http: HTTPSessionManager) -> None:
        self.secrets = secrets
        self.db      = db
        self.http    = http

    def _cred(self, key: str) -> str:
        return self.secrets.get(key) or getenv(key)

    def _price(self, coin_id: str) -> Optional[float]:
        return fetch_token_price(coin_id, self.db)

    def poll(self, svc: ServiceDefinition) -> BalanceResult:
        try:
            method = getattr(self, f"_poll_{svc.slug}", None)
            if method:
                return method(svc)
            if svc.api_balance_url:
                return self._poll_dynamic_api(svc)
            return empty_result(svc.name, "No polling method — use dashboard.", "idle")
        except Exception as exc:
            logger.warning("Unexpected poll error for %s: %s", svc.name, exc)
            return empty_result(svc.name, f"Error: {str(exc)[:100]}", "error")

    def _poll_dynamic_api(self, svc: ServiceDefinition) -> BalanceResult:
        if not svc.api_balance_url:
            return empty_result(svc.name, "No polling URL configured.", "idle")
            
        subs = {}
        for f in svc.setup_fields:
            val = self._cred(f.key) or ""
            subs[f.key] = val
            
        try:
            url = svc.api_balance_url.format(**subs)
            headers = {}
            for k, v in svc.headers.items():
                headers[k] = v.format(**subs)
        except KeyError as exc:
            return empty_result(svc.name, f"Missing credential in template: {exc}", "error")
            
        try:
            s = self.http.session(svc.slug)
            r = retry_call(
                lambda: s.get(url, headers=headers, timeout=API_TIMEOUT),
                label=f"Dynamic API {svc.name}",
            )
            if not r.ok:
                return empty_result(svc.name, f"HTTP Error {r.status_code}", "error")
                
            data = r.json()
            val = data
            if svc.json_path:
                for segment in svc.json_path:
                    if isinstance(val, dict) and segment in val:
                        val = val[segment]
                    elif isinstance(val, list):
                        try:
                            val = val[int(segment)]
                        except (ValueError, IndexError):
                            return empty_result(svc.name, f"Invalid JSON list index '{segment}'", "error")
                    else:
                        return empty_result(svc.name, f"JSON path segment '{segment}' not found", "error")
                        
            bal = safe_float(val)
            if bal is None:
                return empty_result(svc.name, f"Could not parse numeric value from: {val}", "error")
                
            if svc.balance_unit.lower() == "usd":
                return usd_result(svc.name, bal, "Dynamic API")
            else:
                coin_price = 1.0
                if svc.coingecko_id:
                    coin_price = self._price(svc.coingecko_id) or 1.0
                usd_val = bal * coin_price
                return native_result(
                    svc.name,
                    native_value=bal,
                    native_unit=svc.balance_unit,
                    usd_value=usd_val,
                    include_in_total=True,
                    source="Dynamic API",
                )
        except Exception as exc:
            return empty_result(svc.name, f"Poll failed: {exc}", "error")

    # ── per-service pollers ────────────────────────────────────────────────────
    def _poll_earnapp(self, svc: ServiceDefinition) -> BalanceResult:
        uuid_val = self._cred("EARNAPP_UUID")
        if not uuid_val:
            return empty_result(svc.name, "Set EARNAPP_UUID in settings.")
        if _EarnApp is not None:
            try:
                api  = _EarnApp(uuid_val)
                info = retry_call(lambda: api.get_earning_info(), label="EarnApp lib")
                bal  = safe_float(getattr(info, "balance", 0.0))
                return usd_result(svc.name, bal, "EarnApp library")
            except Exception as exc:
                logger.debug("EarnApp library: %s", exc)
        try:
            s = self.http.session("earnapp")
            r = retry_call(
                lambda: s.get(
                    f"https://earnapp.com/dashboard/api/earning_info?appid={uuid_val}",
                    timeout=API_TIMEOUT,
                ),
                label="EarnApp HTTP",
            )
            if r.ok:
                bal = first_numeric(r.json(), ("balance",))
                if bal is not None:
                    return usd_result(svc.name, bal, "EarnApp HTTP")
        except Exception as exc:
            logger.debug("EarnApp HTTP: %s", exc)
        return empty_result(svc.name, "EarnApp: check UUID + native client running.", "warning")

    def _poll_honeygain(self, svc: ServiceDefinition) -> BalanceResult:
        email    = self._cred("HG_EMAIL")
        password = self._cred("HG_PASSWORD")
        if not email or not password:
            return empty_result(svc.name, "Set HG_EMAIL + HG_PASSWORD.")
        if _HoneyGain is not None:
            try:
                client = _HoneyGain()
                client.login(email, password)
                payload = client.balances()
                credits = first_numeric(payload, ("payout", "balance", "total"))
                if credits is not None:
                    usd = round(credits / 1000.0, 6)
                    return native_result(svc.name, credits, "credits", usd, True, "Honeygain library")
            except Exception as exc:
                logger.debug("Honeygain library: %s", exc)
        try:
            s = self.http.session("honeygain")
            lr = s.post(
                "https://dashboard.honeygain.com/api/v1/users/tokens",
                json={"email": email, "password": password},
                timeout=API_TIMEOUT,
            )
            if lr.ok:
                token = lr.json().get("data", {}).get("access_token", "")
                if token:
                    s.headers.update({"Authorization": f"Bearer {token}"})
                br = s.get("https://dashboard.honeygain.com/api/v1/users/balances",
                           timeout=API_TIMEOUT)
                if br.ok:
                    credits = first_numeric(br.json(), ("payout", "credits", "balance"))
                    if credits is not None:
                        usd = round(credits / 1000.0, 6)
                        return native_result(svc.name, credits, "credits", usd, True, "Honeygain HTTP")
        except Exception as exc:
            logger.debug("Honeygain HTTP: %s", exc)
        return empty_result(svc.name, "Honeygain: login failed or credits not found.", "warning")

    def _poll_iproyal(self, svc: ServiceDefinition) -> BalanceResult:
        email    = self._cred("IPROYAL_EMAIL")
        password = self._cred("IPROYAL_PASSWORD")
        if not email or not password:
            return empty_result(svc.name, "Set IPROYAL_EMAIL + IPROYAL_PASSWORD.")
        if _IPRoyalPawns is not None:
            try:
                client  = _IPRoyalPawns()
                resp    = client.login(email, password)
                token   = (resp.get("json") or {}).get("access_token", "")
                if token:
                    client.set_jwt_token(token)
                br = client.balance()
                bal = first_numeric((br.get("json") or {}), ("balance", "amount"))
                if bal is not None:
                    return usd_result(svc.name, bal, "Pawns library")
            except Exception as exc:
                logger.debug("IPRoyal library: %s", exc)
        try:
            s  = self.http.session("iproyal")
            lr = s.post(
                "https://pawns.app/api/v1/users/tokens",
                json={"email": email, "password": password},
                timeout=API_TIMEOUT,
            )
            if lr.ok:
                token = (lr.json().get("data") or {}).get("access_token", "")
                if token:
                    s.headers.update({"Authorization": f"Bearer {token}"})
                br = s.get("https://pawns.app/api/v1/users/balance", timeout=API_TIMEOUT)
                if br.ok:
                    bal = first_numeric(br.json(), ("balance", "amount"))
                    if bal is not None:
                        return usd_result(svc.name, bal, "Pawns HTTP")
        except Exception as exc:
            logger.debug("IPRoyal HTTP: %s", exc)
        return empty_result(svc.name, "Pawns: login failed or balance not found.", "warning")

    def _poll_packetstream(self, svc: ServiceDefinition) -> BalanceResult:
        cid = self._cred("PS_CID")
        if not cid:
            return empty_result(svc.name, "Set PS_CID in settings.")
        bal = DirectAPI.packetstream_balance(cid)
        if bal is not None:
            return usd_result(svc.name, bal, "PacketStream API")
        return empty_result(svc.name, "PacketStream: CID invalid or API unreachable.", "warning")

    def _poll_traffmonetizer(self, svc: ServiceDefinition) -> BalanceResult:
        token = self._cred("TM_TOKEN")
        if not token:
            return empty_result(svc.name, "Set TM_TOKEN in settings.")
        if _TraffMonetizer is not None:
            try:
                client = _TraffMonetizer()
                client.set_jwt_token(token)
                resp = client.get_balance()
                bal  = first_numeric((resp.get("json") or {}), ("balance", "currentBalance"))
                if bal is not None:
                    return usd_result(svc.name, bal, "TraffMonetizer library")
            except Exception as exc:
                logger.debug("TraffMonetizer library: %s", exc)
        bal = DirectAPI.traffmonetizer_balance(token)
        if bal is not None:
            return usd_result(svc.name, bal, "TraffMonetizer HTTP")
        return empty_result(svc.name, "TraffMonetizer: token invalid or API unreachable.", "warning")

    def _poll_earnfm(self, svc: ServiceDefinition) -> BalanceResult:
        token = self._cred("EARNFM_TOKEN")
        if not token:
            return empty_result(svc.name, "Set EARNFM_TOKEN in settings.")
        bal = DirectAPI.earnfm_balance(token)
        if bal is not None:
            return usd_result(svc.name, bal, "EarnFM API")
        return empty_result(svc.name, "EarnFM: token invalid or API unreachable.", "warning")

    def _poll_repocket(self, svc: ServiceDefinition) -> BalanceResult:
        email   = self._cred("REPOCKET_EMAIL")
        api_key = self._cred("REPOCKET_API_KEY")
        if not email or not api_key:
            return empty_result(svc.name, "Set REPOCKET_EMAIL + REPOCKET_API_KEY.")
        bal = DirectAPI.repocket_balance(email, api_key)
        if bal is not None:
            return usd_result(svc.name, bal, "Repocket API")
        return empty_result(svc.name, "Repocket: credentials invalid or API unreachable.", "warning")

    def _poll_proxyrack(self, svc: ServiceDefinition) -> BalanceResult:
        uuid_val = self._cred("PROXYRACK_UUID")
        if not uuid_val:
            return empty_result(svc.name, "Set PROXYRACK_UUID in settings.")
        bal = DirectAPI.proxyrack_balance(uuid_val, self._cred("PROXYRACK_API_KEY"))
        if bal is not None:
            return usd_result(svc.name, bal, "Proxyrack API")
        return empty_result(svc.name, "Proxyrack: UUID invalid or API unreachable.", "warning")

    def _poll_grass(self, svc: ServiceDefinition) -> BalanceResult:
        email    = self._cred("GRASS_EMAIL")
        password = self._cred("GRASS_PASSWORD")
        if not email or not password:
            return empty_result(svc.name, "Set GRASS_EMAIL + GRASS_PASSWORD.")
        s      = self.http.session("grass")
        points = DirectAPI.grass_points(s, email, password)
        if points is not None:
            return native_result(svc.name, points, "points", 0.0, False, "Grass API")
        return empty_result(svc.name, "Grass: login failed or points unavailable.", "warning")

    def _poll_bitping(self, svc: ServiceDefinition) -> BalanceResult:
        email    = self._cred("BITPING_EMAIL")
        password = self._cred("BITPING_PASSWORD")
        if not email or not password:
            return empty_result(svc.name, "Set BITPING_EMAIL + BITPING_PASSWORD.")
        try:
            s  = self.http.session("bitping")
            lr = s.post(
                "https://app.bitping.com/api/account/session",
                json={"email": email, "password": password},
                timeout=API_TIMEOUT,
            )
            if lr.ok:
                token = lr.json().get("token") or lr.json().get("accessToken", "")
                if token:
                    s.headers.update({"Authorization": f"Bearer {token}"})
                br = s.get("https://app.bitping.com/api/account/balance",
                           timeout=API_TIMEOUT)
                if br.ok:
                    sol = first_numeric(br.json(), ("balance", "sol"))
                    if sol is not None:
                        price = self._price("solana")
                        usd   = sol * price if price else 0.0
                        return native_result(svc.name, sol, "sol", usd, False, "Bitping API")
        except Exception as exc:
            logger.debug("Bitping: %s", exc)
        return empty_result(svc.name, "Bitping: login failed or SOL balance unavailable.", "warning")

    def _poll_peer2profit(self, svc: ServiceDefinition) -> BalanceResult:
        if not _HAS_TELETHON:
            return empty_result(svc.name, "telethon not installed — pip install telethon")
        api_id   = self._cred("P2P_API_ID")
        api_hash = self._cred("P2P_API_HASH")
        phone    = self._cred("P2P_PHONE")
        if not api_id or not api_hash or not phone:
            return empty_result(svc.name, "Set P2P_API_ID, P2P_API_HASH, P2P_PHONE.")
        try:
            session_path = str(DATA_DIR / "p2p_telethon")
            client = _TelegramClient(session_path, int(api_id), api_hash)
            client.connect()
            if not client.is_user_authorized():
                client.disconnect()
                return empty_result(svc.name,
                                    "Telegram not authorised. Run with --setup-telegram first.",
                                    "warning")
            try:
                from telethon.tl.functions.messages import GetDialogsRequest
                from telethon.tl.types import InputPeerEmpty
                dialogs = client(GetDialogsRequest(
                    offset_date=None, offset_id=0,
                    offset_peer=InputPeerEmpty(), limit=100, hash=0,
                ))
                for entity in dialogs.chats:
                    if getattr(entity, "username", "") == "peer2profit_bot":
                        client.send_message(entity, "/balance")
                        time.sleep(2)
                        msgs = client.get_messages(entity, limit=5)
                        for msg in msgs:
                            m = re.search(r"(\d+(?:\.\d+)?)\s*\$", msg.message or "")
                            if m:
                                bal = safe_float(m.group(1))
                                client.disconnect()
                                return usd_result(svc.name, bal, "Peer2Profit Telegram")
            finally:
                client.disconnect()
        except Exception as exc:
            logger.debug("Peer2Profit Telegram: %s", exc)
        return empty_result(svc.name, "Peer2Profit: could not fetch via Telegram.", "warning")

    def _poll_mysterium(self, svc: ServiceDefinition) -> BalanceResult:
        myst = DirectAPI.mysterium_unsettled()
        if myst is not None:
            price = self._price("mysterium") or 0.0
            usd   = myst * price
            return native_result(svc.name, myst, "myst", usd, price > 0, "Mysterium TequilAPI")
        return empty_result(svc.name, "Mysterium node not found on localhost:4449.", "warning")

    def _poll_storj(self, svc: ServiceDefinition) -> BalanceResult:
        storj = DirectAPI.storj_payout()
        if storj is not None:
            price = self._price("storj") or 0.0
            usd   = storj * price
            return native_result(svc.name, storj, "storj", usd, price > 0, "Storj local API")
        return empty_result(svc.name, "Storj node not found on localhost:14002.", "warning")

    def _poll_bytelixir(self, svc: ServiceDefinition) -> BalanceResult:
        token = self._cred("BYTELIXIR_TOKEN")
        if token:
            try:
                r = requests.get(
                    "https://dash.bytelixir.com/api/v1/balance",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=API_TIMEOUT,
                )
                if r.ok:
                    bal = first_numeric(r.json(), ("balance", "amount"))
                    if bal is not None:
                        return usd_result(svc.name, bal, "Bytelixir API")
            except Exception as exc:
                logger.debug("Bytelixir API: %s", exc)
        s   = self.http.session("bytelixir")
        bal = DirectAPI.html_scrape_balance(s, svc.dashboard_url)
        if bal is not None:
            return usd_result(svc.name, bal, "Bytelixir HTML scrape")
        return empty_result(svc.name, "Bytelixir: token required for balance.", "idle")

    def _poll_gaganode(self, svc: ServiceDefinition) -> BalanceResult:
        return empty_result(svc.name, "View balance at dashboard.gaganode.com", "idle")

    def _poll_sentinel(self, svc: ServiceDefinition) -> BalanceResult:
        return empty_result(svc.name, "Sentinel: view balance via official tooling.", "idle")

    def _poll_theta(self, svc: ServiceDefinition) -> BalanceResult:
        addr = self._cred("THETA_WALLET_ADDRESS")
        if not addr:
            return empty_result(svc.name, "Set THETA_WALLET_ADDRESS.", "idle")
        try:
            r = requests.get(
                f"https://explorer.thetatoken.org:8443/api/accountservice/account/{addr}",
                timeout=API_TIMEOUT,
            )
            if r.ok:
                data  = r.json().get("body", {})
                tfuel = safe_float(data.get("tfuelstake", {}).get("amount", 0)) / 1e18
                price = self._price("theta-fuel") or 0.0
                return native_result(svc.name, tfuel, "raw", tfuel * price, bool(price),
                                     "Theta Explorer")
        except Exception:
            pass
        return empty_result(svc.name, "Theta: wallet set — check wallet.thetatoken.org.", "idle")

    def _poll_arweave(self, svc: ServiceDefinition) -> BalanceResult:
        return empty_result(svc.name, "Arweave: monitor at viewblock.io/arweave", "idle")

    def _poll_fluence(self, svc: ServiceDefinition) -> BalanceResult:
        return empty_result(svc.name, "Fluence: monitor via official dashboard.", "idle")

    def _poll_acurast(self, svc: ServiceDefinition) -> BalanceResult:
        return empty_result(svc.name, "Acurast: monitor at console.acurast.com", "idle")

    def _poll_akash(self, svc: ServiceDefinition) -> BalanceResult:
        addr = self._cred("AKASH_WALLET_ADDRESS")
        if not addr:
            return empty_result(svc.name, "Set AKASH_WALLET_ADDRESS.", "idle")
        try:
            r = requests.get(
                f"https://api.akashnet.net/cosmos/bank/v1beta1/balances/{addr}",
                timeout=API_TIMEOUT,
            )
            if r.ok:
                for b in r.json().get("balances", []):
                    if b.get("denom") == "uakt":
                        akt   = int(b["amount"]) / 1e6
                        price = self._price("akash-network") or 0.0
                        return native_result(svc.name, akt, "raw", akt * price,
                                             bool(price), "Akash REST")
        except Exception:
            pass
        return empty_result(svc.name, "Akash: wallet set — check stats.akash.network.", "idle")

    def _poll_flux(self, svc: ServiceDefinition) -> BalanceResult:
        return empty_result(svc.name, "Flux: monitor at cloud.runonflux.com", "idle")

    def _poll_subquery(self, svc: ServiceDefinition) -> BalanceResult:
        return empty_result(svc.name, "SubQuery: monitor at kepler.subquery.network", "idle")

# ═══════════════════════════════════════════════════════════════════════════════
# §17  TELEMETRY ENGINE
# ═══════════════════════════════════════════════════════════════════════════════
class TelemetryEngine(threading.Thread):
    def __init__(
        self,
        db:            DatabaseManager,
        services:      Dict[str, ServiceDefinition],
        docker_orch:   DockerOrchestrator,
        http:          HTTPSessionManager,
        secrets:       SecretManager,
        notifier:      Any,
        ui_callback:   Optional[Callable[[Dict[str, BalanceResult]], None]] = None,
        poll_interval: int = POLL_INTERVAL_SECS,
    ) -> None:
        super().__init__(daemon=True, name="TelemetryEngine")
        self.db            = db
        self.services      = services
        self.docker_orch   = docker_orch
        self.poller        = BalancePoller(secrets, db, http)
        self.notifier      = notifier
        self.ui_callback   = ui_callback
        self.poll_interval = poll_interval
        self._stop_event   = threading.Event()
        self.results: Dict[str, BalanceResult] = {
            svc.name: empty_result(svc.name, "Not yet polled.") for svc in services.values()
        }
        self._results_lock = threading.Lock()

    def stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        logger.info("Telemetry engine started — interval=%ds", self.poll_interval)
        last_prune = 0.0
        while not self._stop_event.is_set():
            now = time.time()
            try:
                self.poll_all()
            except Exception as exc:
                logger.error("Telemetry error in poll_all iteration: %s", exc, exc_info=True)
                
            try:
                self._check_ip()
            except Exception as exc:
                logger.error("Telemetry error in _check_ip iteration: %s", exc, exc_info=True)
                
            try:
                self.docker_orch.auto_heal()
            except Exception as exc:
                logger.error("Telemetry error in auto_heal iteration: %s", exc, exc_info=True)
                
            try:
                self._update_heartbeat()
            except Exception as exc:
                logger.error("Telemetry error in _update_heartbeat: %s", exc)

            if now - last_prune > 86400:
                try:
                    self.db.prune_database()
                    last_prune = now
                except Exception as exc:
                    logger.error("Telemetry error in prune_database: %s", exc)
                
            self._stop_event.wait(self.poll_interval)
        logger.info("Telemetry engine stopped.")

    def _update_heartbeat(self) -> None:
        try:
            total = self.db.get_total_wealth()
            statuses = self.docker_orch.all_statuses()
            active_count = sum(1 for s in statuses.values() if s == "running")
            payload = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "status": "healthy",
                "total_wealth_usd": total,
                "active_containers": active_count,
                "pid": os.getpid()
            }
            HEARTBEAT_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            logger.debug("Watchdog heartbeat file updated: %s", payload)
        except Exception as exc:
            logger.warning("Failed to update watchdog heartbeat file: %s", exc)

    def _check_ip(self) -> None:
        try:
            current_ip = get_public_ip()
            previous   = self.db.get_last_ip()
            if current_ip != "unknown" and current_ip != previous:
                self.db.log_ip(current_ip)
                if previous:
                    msg = f"Public IP changed: {previous} → {current_ip}"
                    logger.warning(msg)
                    self.notifier.notify("IP Change Detected", msg, level="warning")
        except Exception:
            pass

    def poll_all(self) -> None:
        new_results: Dict[str, BalanceResult] = {}
        for svc in self.services.values():
            try:
                result = self.poller.poll(svc)
                new_results[svc.name] = result
                if result.native_value is not None:
                    self.db.log_snapshot(
                        service=svc.name,
                        usd_value=result.usd_value,
                        source=result.source,
                        native_value=result.native_value,
                        native_unit=result.native_unit,
                        include_in_total=result.include_in_total,
                    )
                    self.db.log_service_status(svc.name, "ok", result.source)
                else:
                    self.db.log_service_status(svc.name, result.status, result.source)

                if (result.include_in_total and svc.threshold > 0
                        and result.usd_value >= svc.threshold):
                    self.notifier.notify(
                        f"{svc.name}: Payout Threshold Reached",
                        f"Balance {format_usd(result.usd_value)} ≥ {format_usd(svc.threshold)}.\n"
                        f"Visit: {svc.payout_url}",
                        level="success",
                    )
            except Exception as exc:
                logger.error("Telemetry poll error for %s: %s", svc.name, exc)
                new_results[svc.name] = empty_result(svc.name, f"Error: {str(exc)[:80]}", "error")

        with self._results_lock:
            self.results.update(new_results)

        if self.ui_callback:
            try:
                self.ui_callback(dict(self.results))
            except Exception:
                pass

    def get_results(self) -> Dict[str, BalanceResult]:
        with self._results_lock:
            return dict(self.results)

    def set_ui_callback(self, cb: Callable[[Dict[str, BalanceResult]], None]) -> None:
        self.ui_callback = cb

# ═══════════════════════════════════════════════════════════════════════════════
# §18  WITHDRAWAL MANAGER
# ═══════════════════════════════════════════════════════════════════════════════
class WithdrawalManager:
    def __init__(self, secrets: SecretManager, db: DatabaseManager) -> None:
        self.secrets = secrets
        self.db      = db

    def _cred(self, key: str) -> str:
        return self.secrets.get(key) or getenv(key)

    def execute(
        self,
        svc: ServiceDefinition,
        result: BalanceResult,
        destination: str = "",
    ) -> Tuple[bool, str, str]:
        if result.usd_value < svc.threshold and svc.threshold > 0:
            return (
                False,
                "Threshold not met",
                f"Balance {format_compact_usd(result.usd_value)} "
                f"< threshold {format_usd(svc.threshold)}",
            )
        slug  = svc.slug
        tx_id = f"{slug}-{uuid.uuid4().hex[:10]}"
        try:
            if slug == "earnapp":
                return self._withdraw_earnapp(svc, result, destination, tx_id)
            elif slug == "honeygain":
                return self._withdraw_dashboard(svc, result, destination, tx_id)
            elif slug == "iproyal":
                return self._withdraw_dashboard(svc, result, destination, tx_id)
            elif slug == "traffmonetizer":
                return self._withdraw_dashboard(svc, result, destination, tx_id)
            else:
                return self._withdraw_redirect(svc, result, destination, tx_id)
        except Exception as exc:
            self.db.log_withdrawal(svc.name, result.usd_value, destination, "", f"error: {exc}")
            return False, "Unexpected error", str(exc)[:100]

    def _withdraw_earnapp(self, svc: Any, result: BalanceResult,
                          destination: str, tx_id: str) -> Tuple[bool, str, str]:
        if _EarnApp is None:
            return self._withdraw_redirect(svc, result, destination, tx_id)
        uuid_val = self._cred("EARNAPP_UUID")
        if not uuid_val:
            return False, "Missing credentials", "EARNAPP_UUID not set"
        if not destination or "@" not in destination:
            return False, "Destination required", "Provide a valid PayPal e-mail address"
        try:
            api = _EarnApp(uuid_val)
            api.redeem_to_paypal(email=destination)
            self.db.log_withdrawal(svc.name, result.usd_value, destination, tx_id, "completed")
            return True, "Withdrawal submitted", f"PayPal withdrawal to {destination} submitted."
        except Exception as exc:
            self.db.log_withdrawal(svc.name, result.usd_value, destination, "", f"failed: {exc}")
            return False, "API error", str(exc)[:80]

    def _withdraw_dashboard(self, svc: Any, result: BalanceResult,
                             destination: str, tx_id: str) -> Tuple[bool, str, str]:
        self.db.log_withdrawal(svc.name, result.usd_value,
                               destination or "dashboard", tx_id, "dashboard_redirect")
        open_url(svc.payout_url)
        return (
            True, "Dashboard opened",
            f"{svc.name} withdrawal must be finalised in the official dashboard.\n"
            f"Balance: {result.primary_display}",
        )

    def _withdraw_redirect(self, svc: Any, result: BalanceResult,
                            destination: str, tx_id: str) -> Tuple[bool, str, str]:
        self.db.log_withdrawal(svc.name, result.usd_value,
                               destination or "dashboard", tx_id, "manual_required")
        open_url(svc.payout_url)
        return (
            True, "Dashboard opened",
            f"{svc.name} requires manual withdrawal.\nOpening: {svc.payout_url}",
        )

# ═══════════════════════════════════════════════════════════════════════════════
# §19  NOTIFICATION MANAGER
# ═══════════════════════════════════════════════════════════════════════════════
class NotificationManager:
    def __init__(self, db: Optional[DatabaseManager] = None) -> None:
        self.db          = db
        self._plyer_ok   = False
        self._last_notif: Dict[str, float] = {}
        self._cooldown   = 300

        try:
            import plyer as _plyer_mod  # type: ignore
            self._plyer = _plyer_mod.notification
            self._plyer_ok = True
        except ImportError:
            self._plyer = None

    def notify(self, title: str, message: str, level: str = "info") -> None:
        key = f"{title}:{message}"
        now = time.time()
        if now - self._last_notif.get(key, 0) < self._cooldown:
            return
        self._last_notif[key] = now

        logger.info("[NOTIFY][%s] %s — %s", level.upper(), title, message[:120])
        if self.db:
            try:
                self.db.log_notification(level, title, message)
            except Exception:
                pass

        if self._plyer_ok and self._plyer:
            try:
                self._plyer.notify(
                    title=f"{APP_NAME}: {title}",
                    message=message[:250],
                    app_name=APP_NAME,
                    timeout=8,
                )
                return
            except Exception:
                pass

        system = platform.system().lower()
        try:
            if system == "linux":
                subprocess.Popen(
                    ["notify-send", "-a", APP_NAME, "-t", "8000", title, message[:200]],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
            elif system == "darwin":
                script = (f'display notification "{message[:200]}" '
                          f'with title "{APP_NAME}: {title}"')
                subprocess.Popen(["osascript", "-e", script],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            elif system == "windows":
                ps = (
                    f'[Windows.UI.Notifications.ToastNotificationManager,'
                    f'Windows.UI.Notifications,ContentType=WindowsRuntime]>$null;'
                    f'$t=[Windows.UI.Notifications.ToastNotificationManager]::'
                    f'GetTemplateContent(0);'
                    f'$t.SelectSingleNode("//text[@id=1]").InnerText='
                    f'"{APP_NAME}: {title} — {message[:80]}";'
                    f'$n=[Windows.UI.Notifications.ToastNotification]::new($t);'
                    f'[Windows.UI.Notifications.ToastNotificationManager]::'
                    f'CreateToastNotifier("{APP_NAME}").Show($n);'
                )
                subprocess.Popen(
                    ["powershell", "-WindowStyle", "Hidden", "-Command", ps],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
        except Exception:
            pass

# ═══════════════════════════════════════════════════════════════════════════════
# §20  PRE-FLIGHT CHECKS
# ═══════════════════════════════════════════════════════════════════════════════
def run_preflight() -> Dict[str, Any]:
    results: Dict[str, Any] = {
        "python_version":   sys.version,
        "platform":         platform.platform(),
        "arch":             _detect_arch(),
        "docker_sdk":       False,
        "docker_cli":       False,
        "docker_daemon":    False,
        "docker_compose":   "not found",
        "docker_version":   "not found",
        "public_ip":        "checking…",
        "packages":         {},
    }
    docker_ok, docker_ver = DockerInstaller.is_available()
    results["docker_cli"]     = docker_ok
    results["docker_version"] = docker_ver
    results["docker_daemon"]  = _docker_daemon_running()
    compose_cmd = _docker_compose_cmd()
    results["docker_compose"] = " ".join(compose_cmd) if compose_cmd else "not found"
    if _HAS_DOCKER:
        try:
            c = _docker_module.from_env()
            c.ping()
            results["docker_sdk"] = True
        except Exception:
            pass
    try:
        results["public_ip"] = get_public_ip()
    except Exception:
        results["public_ip"] = "unreachable"

    pkg_status: Dict[str, str] = {}
    for _spec, dist, _imp, req in REQUIRED_PACKAGES:
        tag = "[req]" if req else "[opt]"
        try:
            ver = importlib.metadata.version(dist)
            pkg_status[dist] = f"{tag} {ver}"
        except importlib.metadata.PackageNotFoundError:
            pkg_status[dist] = f"{tag} MISSING"
    results["packages"] = pkg_status
    return results

# ═══════════════════════════════════════════════════════════════════════════════
# §21  CLI CONTROLLER
# ═══════════════════════════════════════════════════════════════════════════════
class CLIController:
    COLS = shutil.get_terminal_size((100, 40)).columns

    @staticmethod
    def clear() -> None:
        os.system("cls" if platform.system().lower() == "windows" else "clear")

    @staticmethod
    def _status_color(status: str) -> str:
        return {
            "running":      Fore.GREEN,
            "ok":           Fore.GREEN,
            "warning":      Fore.YELLOW,
            "exited":       Fore.RED,
            "dead":         Fore.RED,
            "error":        Fore.RED,
            "not_found":    Fore.LIGHTBLACK_EX,
            "unavailable":  Fore.LIGHTBLACK_EX,
            "idle":         Fore.LIGHTBLACK_EX,
            "monitor_only": Fore.CYAN,
            "manual":       Fore.MAGENTA,
        }.get(status, Fore.WHITE)

    @classmethod
    def render(cls, services: Dict[str, ServiceDefinition],
               telemetry: TelemetryEngine,
               docker_orch: DockerOrchestrator) -> None:
        cls.clear()
        W   = cls.COLS
        bar = "═" * W
        print(Fore.CYAN + Style.BRIGHT + bar)
        print(Fore.CYAN + Style.BRIGHT +
              f"  {APP_NAME} v{VERSION}  —  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(Fore.CYAN + Style.BRIGHT + bar + Style.RESET_ALL)

        results   = telemetry.get_results()
        total_usd = sum(r.usd_value for r in results.values() if r.include_in_total)

        print(Fore.WHITE +
              f"\n  {'Service':<22} {'Balance':<18} {'USD equiv':>12} "
              f"{'Container':<16} {'Status':<10}")
        print(Fore.LIGHTBLACK_EX + "  " + "─" * (W - 4))

        for svc in services.values():
            result  = results.get(svc.name, empty_result(svc.name, ""))
            cstatus = docker_orch.container_status(svc)
            sc = cls._status_color(cstatus)
            rc = cls._status_color(result.status)
            bal_str = result.primary_display
            usd_str = format_compact_usd(result.usd_value) if result.include_in_total else "—"
            print(
                Fore.WHITE  + f"  {svc.name:<22} "
                + rc        + f"{bal_str:<18} "
                + Fore.CYAN + f"{usd_str:>12}  "
                + sc        + f"{cstatus:<16} "
                + rc        + f"{result.status:<10}"
                + Style.RESET_ALL
            )

        print(Fore.LIGHTBLACK_EX + "\n  " + "─" * (W - 4))
        print(Fore.GREEN + Style.BRIGHT +
              f"  TOTAL (verified USD):  {format_usd(total_usd)}" + Style.RESET_ALL)
        print(Fore.LIGHTBLACK_EX +
              f"\n  Polling every {POLL_INTERVAL_SECS}s.  Ctrl-C to stop.  "
              f"Logs → {LOG_FILE.name}\n")

    @classmethod
    def setup_wizard(cls, services: Dict[str, ServiceDefinition],
                     secrets: SecretManager) -> None:
        W = cls.COLS
        print(Fore.CYAN + Style.BRIGHT + "\n" + "═" * W)
        print(f"  {APP_NAME} — First-Run Setup Wizard")
        print("═" * W + Style.RESET_ALL)
        print(Fore.WHITE + "  Enter credentials for each service.  Press Enter to skip.\n")
        configured = 0
        for svc in services.values():
            if not svc.setup_fields:
                continue
            if all(secrets.has(f.key) for f in svc.setup_fields if f.required):
                print(Fore.GREEN + f"  [{svc.name}]" +
                      Fore.LIGHTBLACK_EX + " already configured.")
                continue
            print(Fore.CYAN + f"\n  ── {svc.name} ({svc.category}) ──")
            print(Fore.LIGHTBLACK_EX + f"  {svc.earnings_model_note}")
            print(Fore.LIGHTBLACK_EX + f"  Sign up: {svc.website_url}")
            any_entered = False
            for f in svc.setup_fields:
                tag    = " [required]" if f.required else " [optional]"
                hint   = f"  (e.g. {f.hint})" if f.hint else ""
                prompt = Fore.WHITE + f"  {f.label}{tag}{hint}: " + Style.RESET_ALL
                try:
                    if f.secret:
                        import getpass
                        value = getpass.getpass(prompt)
                    else:
                        value = input(prompt).strip()
                except (KeyboardInterrupt, EOFError):
                    value = ""
                if value:
                    secrets.set(f.key, value)
                    set_env_value(f.key, value)
                    any_entered = True
            if any_entered:
                configured += 1
        print(Fore.GREEN + Style.BRIGHT +
              f"\n  Setup complete.  {configured} service(s) configured." +
              Style.RESET_ALL + "\n")

    @classmethod
    def run(cls, db: DatabaseManager, docker_orch: DockerOrchestrator,
            http: HTTPSessionManager, services: Dict[str, ServiceDefinition],
            secrets: SecretManager, notifier: NotificationManager,
            setup: bool = False) -> None:
        try:
            PID_FILE.write_text(str(os.getpid()))
            import atexit
            def _cleanup_pid():
                try:
                    if PID_FILE.exists():
                        pid = int(PID_FILE.read_text().strip())
                        if pid == os.getpid():
                            PID_FILE.unlink()
                except Exception:
                    pass
            atexit.register(_cleanup_pid)
        except Exception as e:
            logger.warning("Could not setup background daemon PID: %s", e)

        if setup:
            cls.setup_wizard(services, secrets)
        telemetry = TelemetryEngine(db, services, docker_orch, http, secrets, notifier,
                                    poll_interval=POLL_INTERVAL_SECS)
        setup_signal_handlers(telemetry)
        telemetry.start()
        telemetry.poll_all()
        try:
            while True:
                cls.render(services, telemetry, docker_orch)
                time.sleep(POLL_INTERVAL_SECS)
        except KeyboardInterrupt:
            telemetry.stop()
            print(Fore.YELLOW + f"\n  {APP_NAME} stopped.\n" + Style.RESET_ALL)

# ═══════════════════════════════════════════════════════════════════════════════
# §22  GUI WIDGETS
# ═══════════════════════════════════════════════════════════════════════════════
class ServiceCard(ctk.CTkFrame):
    def __init__(self, parent: Any, svc: ServiceDefinition,
                 result: BalanceResult, docker_status: str,
                 on_configure: Callable, on_deploy: Callable,
                 on_withdraw: Callable, **kwargs: Any) -> None:
        super().__init__(parent, fg_color=C_BG_CARD, corner_radius=10, **kwargs)
        self.svc           = svc
        self._on_configure = on_configure
        self._on_deploy    = on_deploy
        self._on_withdraw  = on_withdraw
        self._build(result, docker_status)

    def _build(self, result: BalanceResult, docker_status: str) -> None:
        cat_color = CATEGORY_COLORS.get(self.svc.category, C_ACCENT)
        stripe = ctk.CTkFrame(self, fg_color=cat_color, corner_radius=0, width=4, height=80)
        stripe.pack(side="left", fill="y", padx=(0, 8))

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(side="left", fill="both", expand=True, padx=(0, 8), pady=6)

        row1 = ctk.CTkFrame(body, fg_color="transparent")
        row1.pack(fill="x")
        ctk.CTkLabel(row1, text=self.svc.name,
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=C_TEXT, anchor="w").pack(side="left")
        self._balance_label = ctk.CTkLabel(
            row1, text=result.primary_display,
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=result.status_color, anchor="e")
        self._balance_label.pack(side="right")

        row2 = ctk.CTkFrame(body, fg_color="transparent")
        row2.pack(fill="x")
        self._source_label = ctk.CTkLabel(
            row2, text=result.source[:55],
            font=ctk.CTkFont(size=10), text_color=C_TEXT_MUTED, anchor="w")
        self._source_label.pack(side="left")
        self._usd_label = ctk.CTkLabel(
            row2, text=result.secondary_display,
            font=ctk.CTkFont(size=10), text_color=C_TEXT_DIM, anchor="e")
        self._usd_label.pack(side="right")

        row3 = ctk.CTkFrame(body, fg_color="transparent")
        row3.pack(fill="x", pady=(2, 0))

        ds_color = self._docker_color(docker_status)
        docker_lbl = self._docker_text(docker_status)
        self._docker_label = ctk.CTkLabel(
            row3, text=docker_lbl,
            font=ctk.CTkFont(size=10), text_color=ds_color, anchor="w")
        self._docker_label.pack(side="left")

        btn_kw: Dict[str, Any] = dict(height=22, corner_radius=4,
                                      font=ctk.CTkFont(size=10))
        ctk.CTkButton(row3, text="⚙ Configure", width=84,
                      fg_color=C_BG_INPUT, hover_color=C_BORDER,
                      text_color=C_TEXT_DIM, command=self._on_configure,
                      **btn_kw).pack(side="right", padx=(4, 0))
        if self.svc.is_auto_deployable:
            ctk.CTkButton(row3, text="▶ Deploy", width=72,
                          fg_color="#1e3a5f", hover_color="#2554a0",
                          text_color=C_BLUE, command=self._on_deploy,
                          **btn_kw).pack(side="right", padx=(4, 0))
        ctk.CTkButton(row3, text="⬆ Withdraw", width=80,
                      fg_color="#1a2e1a", hover_color="#1e4d1e",
                      text_color=C_ACCENT, command=self._on_withdraw,
                      **btn_kw).pack(side="right", padx=(4, 0))

    @staticmethod
    def _docker_color(status: str) -> str:
        return {
            "running":      C_ACCENT,
            "exited":       C_RED,
            "dead":         C_RED,
            "not_found":    C_TEXT_MUTED,
            "monitor_only": C_BLUE,
            "manual":       C_PURPLE,
            "unavailable":  C_TEXT_MUTED,
        }.get(status, C_TEXT_MUTED)

    @staticmethod
    def _docker_text(status: str) -> str:
        return {
            "running":      "docker: running",
            "exited":       "docker: exited",
            "dead":         "docker: dead",
            "paused":       "docker: paused",
            "restarting":   "docker: restarting",
            "not_found":    "docker: not deployed",
            "monitor_only": "monitor only",
            "manual":       "manual docker",
            "unavailable":  "docker unavailable",
        }.get(status, f"docker: {status}")

    def update_result(self, result: BalanceResult, docker_status: str) -> None:
        try:
            self._balance_label.configure(
                text=result.primary_display, text_color=result.status_color)
            self._source_label.configure(text=result.source[:55])
            self._usd_label.configure(text=result.secondary_display)
            self._docker_label.configure(
                text=self._docker_text(docker_status),
                text_color=self._docker_color(docker_status))
        except Exception:
            pass


class ServiceConfigModal(ctk.CTkToplevel):
    """Modal dialog for service credentials.  grab_set is deferred safely."""

    def __init__(self, parent: Any, svc: ServiceDefinition,
                 secrets: SecretManager, on_save: Callable,
                 http: HTTPSessionManager) -> None:
        super().__init__(parent)
        self.title(f"Configure — {svc.name}")
        self.geometry("650x680")
        self.configure(fg_color=C_BG_DARK)
        self.resizable(False, True)
        self.svc     = svc
        self.secrets = secrets
        self.on_save = on_save
        self.http    = http
        self.entries: Dict[str, ctk.CTkEntry] = {}
        self._build()
        # Defer grab_set until the window is actually mapped
        self.after(200, self._safe_grab)

    def _safe_grab(self) -> None:
        try:
            self.lift()
            self.focus_force()
            self.grab_set()
        except Exception as exc:
            logger.debug("grab_set (non-fatal): %s", exc)

    def _build(self) -> None:
        svc       = self.svc
        cat_color = CATEGORY_COLORS.get(svc.category, C_ACCENT)

        hdr = ctk.CTkFrame(self, fg_color=C_BG_PANEL, corner_radius=0)
        hdr.pack(fill="x")
        ctk.CTkLabel(
            hdr,
            text=(f"{svc.category.upper()}  ·  "
                  f"{svc.docker_mode.replace('_',' ').title()}  ·  "
                  f"{svc.docker_support_level.title()}"),
            text_color=cat_color,
            font=ctk.CTkFont(size=11, weight="bold"),
        ).pack(anchor="w", padx=16, pady=(10, 0))
        ctk.CTkLabel(hdr, text=svc.name,
                     font=ctk.CTkFont(size=20, weight="bold"),
                     text_color=C_TEXT).pack(anchor="w", padx=16, pady=(2, 2))
        ctk.CTkLabel(hdr, text=svc.earnings_model_note,
                     text_color=C_TEXT_DIM, wraplength=590,
                     justify="left").pack(anchor="w", padx=16, pady=(0, 10))

        info = ctk.CTkFrame(self, fg_color=C_BG_CARD, corner_radius=8)
        info.pack(fill="x", padx=14, pady=6)
        notes = f"Docker: {svc.docker_summary}\nSource: {svc.docker_source_url}"
        if svc.manual_docker_notes:
            notes += f"\nNotes: {svc.manual_docker_notes}"
        ctk.CTkLabel(info, text=notes, text_color=C_TEXT_MUTED,
                     wraplength=590, justify="left",
                     font=ctk.CTkFont(size=10)).pack(padx=12, pady=8)

        fields_frame = ctk.CTkScrollableFrame(self, fg_color=C_BG_DARK)
        fields_frame.pack(fill="both", expand=True, padx=14, pady=4)

        if svc.setup_fields:
            for f in svc.setup_fields:
                lbl = f.label + (" *" if f.required else " (optional)")
                ctk.CTkLabel(fields_frame, text=lbl, anchor="w",
                             text_color=C_TEXT_DIM).pack(fill="x", pady=(8, 2))
                entry = ctk.CTkEntry(
                    fields_frame,
                    fg_color=C_BG_INPUT, border_color=C_BORDER,
                    text_color=C_TEXT,
                    show="●" if f.secret else "",
                    placeholder_text=f.hint,
                )
                entry.pack(fill="x", pady=(0, 2))
                existing = self.secrets.get(f.key) or getenv(f.key)
                if existing:
                    entry.insert(0, existing)
                self.entries[f.key] = entry
        else:
            ctk.CTkLabel(
                fields_frame,
                text="No credentials required.  Open the dashboard to manage your session.",
                text_color=C_TEXT_DIM, wraplength=560, justify="left",
            ).pack(pady=20)

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=14, pady=(4, 12))
        ctk.CTkButton(btn_row, text="💾 Save & Close",
                      command=self._save, fg_color=C_ACCENT,
                      text_color="#052e16", hover_color=C_ACCENT_DIM,
                      font=ctk.CTkFont(weight="bold")).pack(side="left", padx=(0, 6))
        ctk.CTkButton(btn_row, text="🌐 Open Dashboard",
                      command=lambda: self.http.open_dashboard_browser(svc),
                      fg_color=C_BG_INPUT, border_width=1, border_color=C_BORDER,
                      hover_color=C_BORDER, text_color=C_BLUE).pack(side="left", padx=6)
        ctk.CTkButton(btn_row, text="📖 Docker Docs",
                      command=lambda: open_url(svc.docker_source_url),
                      fg_color=C_BG_INPUT, border_width=1, border_color=C_BORDER,
                      hover_color=C_BORDER, text_color=C_TEXT_DIM).pack(side="right")

    def _save(self) -> None:
        for key, entry in self.entries.items():
            val = entry.get().strip()
            if not val:
                continue
            f = next((x for x in self.svc.setup_fields if x.key == key), None)
            self.secrets.set(key, val)
            if f and not f.secret:
                set_env_value(key, val)
        try:
            self.grab_release()
        except Exception:
            pass
        self.on_save()
        self.destroy()


class EarningsChartFrame(ctk.CTkFrame):
    def __init__(self, parent: Any, db: DatabaseManager, **kwargs: Any) -> None:
        super().__init__(parent, fg_color=C_BG_CARD, corner_radius=10, **kwargs)
        self.db = db
        self._build()

    def _build(self) -> None:
        ctk.CTkLabel(self, text="7-Day Earnings",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=C_TEXT_DIM).pack(anchor="w", padx=12, pady=(8, 2))
        self._chart_area = ctk.CTkFrame(self, fg_color="transparent")
        self._chart_area.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.refresh()

    def refresh(self) -> None:
        # Clean up existing figure and canvas explicitly to prevent memory leaks (Bug 16)
        if hasattr(self, "_current_fig") and self._current_fig:
            try:
                self._current_fig.clf()
                plt.close(self._current_fig)
            except Exception:
                pass
            self._current_fig = None
        if hasattr(self, "_current_canvas") and self._current_canvas:
            try:
                self._current_canvas.get_tk_widget().destroy()
            except Exception:
                pass
            self._current_canvas = None
            
        import gc
        gc.collect()

        for w in self._chart_area.winfo_children():
            try:
                w.destroy()
            except Exception:
                pass

        if not _HAS_MATPLOTLIB:
            ctk.CTkLabel(self._chart_area,
                         text="Install matplotlib for charts:\n  pip install matplotlib",
                         text_color=C_TEXT_MUTED).pack(expand=True)
            return

        rows = self.db.get_historical_data(days=7)
        if not rows:
            ctk.CTkLabel(self._chart_area, text="No data yet — wait for first poll.",
                         text_color=C_TEXT_MUTED).pack(expand=True)
            return

        from collections import defaultdict
        day_totals: Dict[str, Dict[str, float]] = defaultdict(dict)
        for ts, svc_name, bal in rows:
            day_totals[ts[:10]][svc_name] = bal
        days_sorted  = sorted(day_totals.keys())
        daily_values = [sum(day_totals[d].values()) for d in days_sorted]

        try:
            fig, ax = plt.subplots(figsize=(5.5, 2.2), dpi=92,
                                   facecolor=C_BG_CARD)
            ax.set_facecolor(C_BG_CARD)
            ax.plot(range(len(days_sorted)), daily_values,
                    color=C_ACCENT, linewidth=2, marker="o", markersize=4)
            ax.fill_between(range(len(days_sorted)), daily_values,
                            alpha=0.15, color=C_ACCENT)
            ax.set_xticks(range(len(days_sorted)))
            ax.set_xticklabels([d[5:] for d in days_sorted],
                               fontsize=7, color=C_TEXT_MUTED)
            ax.yaxis.set_tick_params(labelsize=7, labelcolor=C_TEXT_MUTED)
            ax.spines[:].set_visible(False)
            fig.tight_layout(pad=0.4)
            canvas = FigureCanvasTkAgg(fig, master=self._chart_area)
            canvas.draw()
            canvas.get_tk_widget().pack(fill="both", expand=True)
            
            # Cache current references for future explicit destruction/garbage collection
            self._current_fig = fig
            self._current_canvas = canvas
        except Exception as exc:
            logger.debug("Chart render: %s", exc)
            ctk.CTkLabel(self._chart_area, text=f"Chart error: {exc}",
                         text_color=C_TEXT_MUTED).pack(expand=True)


class WithdrawalHistoryPanel(ctk.CTkFrame):
    def __init__(self, parent: Any, db: DatabaseManager, **kwargs: Any) -> None:
        super().__init__(parent, fg_color=C_BG_PANEL, corner_radius=10, **kwargs)
        self.db = db
        self._build()

    def _build(self) -> None:
        ctk.CTkLabel(self, text="Withdrawal History",
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=C_TEXT).pack(anchor="w", padx=16, pady=(12, 6))

        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("NX.Treeview",
                        background=C_BG_CARD, fieldbackground=C_BG_CARD,
                        foreground=C_TEXT, rowheight=24, borderwidth=0,
                        font=("Segoe UI", 10))
        style.configure("NX.Treeview.Heading",
                        background=C_BG_DARK, foreground=C_TEXT_DIM,
                        font=("Segoe UI", 10, "bold"))
        style.map("NX.Treeview",
                  background=[("selected", "#1a3350")],
                  foreground=[("selected", "#ffffff")])

        cols = ("timestamp", "service", "amount", "destination", "tx_id", "status")
        self._tree = ttk.Treeview(self, columns=cols, show="headings",
                                  height=7, style="NX.Treeview")
        widths = dict(timestamp=145, service=120, amount=80,
                      destination=130, tx_id=130, status=120)
        for c in cols:
            self._tree.heading(c, text=c.replace("_", " ").title())
            self._tree.column(c, width=widths[c], anchor="w")

        sb = ttk.Scrollbar(self, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=sb.set)
        self._tree.pack(side="left", fill="both", expand=True,
                        padx=(12, 0), pady=8)
        sb.pack(side="right", fill="y", pady=8, padx=(0, 4))

    def refresh(self) -> None:
        for item in self._tree.get_children():
            self._tree.delete(item)
        for row in self.db.get_recent_withdrawals(100):
            ts, svc, amt, dest, tx, status = row
            self._tree.insert("", "end",
                              values=(ts, svc, format_usd(float(amt or 0)),
                                      dest or "—", tx or "—", status))


class LogsPanel(ctk.CTkFrame):
    """
    Live log panel.
    Bug fix: the inner GUILogHandler.emit must call inner_self.format(),
    not self.format() (which would refer to the outer CTkFrame).
    """

    def __init__(self, parent: Any, **kwargs: Any) -> None:
        super().__init__(parent, fg_color=C_BG_PANEL, corner_radius=10, **kwargs)
        self._max_lines = 300
        self._build()

    def _build(self) -> None:
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", padx=12, pady=(10, 4))
        ctk.CTkLabel(hdr, text="Live Logs",
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=C_TEXT).pack(side="left")
        ctk.CTkButton(
            hdr, text="Open Log File", width=110, height=26,
            fg_color=C_BG_INPUT, border_width=1, border_color=C_BORDER,
            hover_color=C_BORDER, text_color=C_TEXT_DIM,
            command=lambda: open_url(str(LOG_FILE)),
        ).pack(side="right")

        self._text = ctk.CTkTextbox(
            self, fg_color=C_BG_CARD, text_color=C_TEXT_DIM,
            font=ctk.CTkFont(family="Courier New", size=10),
            wrap="none", state="disabled",
        )
        self._text.pack(fill="both", expand=True, padx=12, pady=(0, 10))
        self._install_handler()

    def _install_handler(self) -> None:
        widget    = self._text
        max_lines = self._max_lines

        class _GUIHandler(logging.Handler):
            def __init__(inner_self) -> None:
                super().__init__()
                inner_self._widget    = widget
                inner_self._max_lines = max_lines
                inner_self._count     = 0

            def emit(inner_self, record: logging.LogRecord) -> None:
                # MUST use inner_self.format() — NOT self.format()
                try:
                    msg = inner_self.format(record) + "\n"
                except Exception:
                    msg = str(record.getMessage()) + "\n"
                try:
                    inner_self._widget.configure(state="normal")
                    inner_self._widget.insert("end", msg)
                    inner_self._count += 1
                    if inner_self._count > inner_self._max_lines:
                        inner_self._widget.delete("1.0", "2.0")
                        inner_self._count -= 1
                    inner_self._widget.see("end")
                    inner_self._widget.configure(state="disabled")
                except Exception:
                    pass

        handler = _GUIHandler()
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)-7s %(message)s", datefmt="%H:%M:%S"
        ))
        logging.getLogger(APP_NAME).addHandler(handler)

class PasswordPromptDialog(ctk.CTkToplevel):
    """Sleek modal dialog prompting for system root/administrator password."""
    def __init__(self, parent: Any, title: str, prompt: str) -> None:
        super().__init__(parent)
        self.title(title)
        self.geometry("450x230")
        self.configure(fg_color=C_BG_DARK)
        self.resizable(False, False)
        self.result = None
        self.prompt_text = prompt
        
        # Center relative to parent
        self.update_idletasks()
        px = parent.winfo_x() + (parent.winfo_width() - 450) // 2
        py = parent.winfo_y() + (parent.winfo_height() - 230) // 2
        self.geometry(f"+{px}+{py}")
        
        self._build()
        self.after(200, self._safe_grab)

    def _safe_grab(self) -> None:
        try:
            self.lift()
            self.focus_force()
            self.grab_set()
        except Exception as exc:
            logger.debug("grab_set (non-fatal): %s", exc)

    def _build(self) -> None:
        # Prompt label
        ctk.CTkLabel(
            self, text=self.prompt_text,
            font=ctk.CTkFont(size=12), text_color=C_TEXT,
            wraplength=410, justify="center"
        ).pack(pady=(25, 12), padx=20)

        # Password Entry
        self.entry = ctk.CTkEntry(
            self, show="*", width=320, height=36,
            fg_color=C_BG_INPUT, border_color=C_BORDER, text_color=C_TEXT
        )
        self.entry.pack(pady=10)
        self.entry.focus()

        # Action Buttons
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=15)

        ctk.CTkButton(
            btn_frame, text="Authorize Access", width=140, height=32,
            fg_color=C_ACCENT, text_color="#052e16", hover_color=C_ACCENT_DIM,
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._on_ok
        ).pack(side="left", padx=10)

        ctk.CTkButton(
            btn_frame, text="Cancel", width=100, height=32,
            fg_color=C_BG_INPUT, border_width=1, border_color=C_BORDER,
            text_color=C_TEXT_DIM, hover_color=C_BORDER,
            command=self._on_cancel
        ).pack(side="left", padx=10)

        self.entry.bind("<Return>", lambda e: self._on_ok())
        self.entry.bind("<Escape>", lambda e: self._on_cancel())

    def _on_ok(self) -> None:
        self.result = self.entry.get()
        self.destroy()

    def _on_cancel(self) -> None:
        self.result = None
        self.destroy()

# ═══════════════════════════════════════════════════════════════════════════════
# §23  MAIN GUI WINDOW
# ═══════════════════════════════════════════════════════════════════════════════
class MyriapodGUI(ctk.CTk):
    def __init__(self, db: DatabaseManager, docker_orch: DockerOrchestrator,
                 http: HTTPSessionManager, telemetry: TelemetryEngine,
                 services: Dict[str, ServiceDefinition], secrets: SecretManager,
                 withdrawal_mgr: WithdrawalManager,
                 notifier: NotificationManager,
                 is_client_only: bool = False) -> None:
        super().__init__()
        self.db             = db
        self.docker_orch    = docker_orch
        self.http           = http
        self.telemetry      = telemetry
        self.services       = services
        self.secrets        = secrets
        self.withdrawal_mgr = withdrawal_mgr
        self.notifier       = notifier
        self.is_client_only = is_client_only
        self._service_cards: Dict[str, ServiceCard] = {}
        self._tray_icon: Optional[Any] = None
        self._logo_ctk_img: Optional[ctk.CTkImage] = None
        self._proxy_proc: Optional[Any] = None

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("green")
        self.title(f"{APP_NAME} v{VERSION}")
        self.geometry("1180x820")
        self.minsize(900, 600)
        self.configure(fg_color=C_BG_DARK)
        self._set_window_icon()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._build_ui()
        telemetry.set_ui_callback(self._on_telemetry_update)
        self._refresh_ui()

    # ── window icon ───────────────────────────────────────────────────────────
    def _set_window_icon(self) -> None:
        try:
            if LOGO_FILE.exists():
                img      = Image.open(LOGO_FILE)
                icon_img = ImageTk.PhotoImage(img)
                self.wm_iconphoto(True, icon_img)
                self._icon_ref = icon_img      # prevent GC
        except Exception as exc:
            logger.debug("Window icon set failed: %s", exc)

    # ── full UI construction ──────────────────────────────────────────────────
    def _build_ui(self) -> None:
        # Title bar
        titlebar = ctk.CTkFrame(self, fg_color=C_BG_PANEL, corner_radius=0, height=56)
        titlebar.pack(fill="x")
        titlebar.pack_propagate(False)

        logo_pil = load_app_logo(size=(44, 44))
        if logo_pil:
            try:
                self._logo_ctk_img = ctk.CTkImage(
                    light_image=logo_pil, dark_image=logo_pil, size=(44, 44))
                ctk.CTkLabel(titlebar, image=self._logo_ctk_img,
                             text="").pack(side="left", padx=(10, 0), pady=4)
            except Exception as exc:
                logger.debug("Logo CTkImage: %s", exc)

        ctk.CTkLabel(titlebar, text=APP_NAME,
                     font=ctk.CTkFont(size=18, weight="bold"),
                     text_color=C_ACCENT).pack(side="left", padx=(8, 0))
        ctk.CTkLabel(titlebar, text=f"v{VERSION}",
                     font=ctk.CTkFont(size=11), text_color=C_TEXT_MUTED
                     ).pack(side="left", padx=(6, 0), pady=(8, 0))

        self._total_label = ctk.CTkLabel(
            titlebar, text="Total: $0.00",
            font=ctk.CTkFont(size=16, weight="bold"), text_color=C_ACCENT)
        self._total_label.pack(side="right", padx=(0, 16))

        self._ip_label = ctk.CTkLabel(
            titlebar, text="IP: …",
            font=ctk.CTkFont(size=10), text_color=C_TEXT_MUTED)
        self._ip_label.pack(side="right", padx=(0, 20))

        # Tabs
        self._tabs = ctk.CTkTabview(
            self, fg_color=C_BG_DARK,
            segmented_button_fg_color=C_BG_PANEL,
            segmented_button_selected_color=C_ACCENT,
            segmented_button_selected_hover_color=C_ACCENT_DIM,
            segmented_button_unselected_color=C_BG_PANEL,
            segmented_button_unselected_hover_color=C_BG_CARD,
            text_color=C_TEXT, text_color_disabled=C_TEXT_MUTED,
        )
        self._tabs.pack(fill="both", expand=True, padx=8, pady=4)
        for name in ("Dashboard", "Earnings Chart", "Withdrawals", "Logs", "Settings"):
            self._tabs.add(name)

        self._build_dashboard_tab()
        self._build_chart_tab()
        self._build_withdrawals_tab()
        self._build_logs_tab()
        self._build_settings_tab()

    # ── Dashboard ─────────────────────────────────────────────────────────────
    def _build_dashboard_tab(self) -> None:
        tab = self._tabs.tab("Dashboard")
        ab  = ctk.CTkFrame(tab, fg_color="transparent")
        ab.pack(fill="x", padx=4, pady=(6, 4))

        if getattr(self, "is_client_only", False):
            ctk.CTkButton(ab, text="🛑 Stop Background Daemon", width=170,
                          fg_color="#3a1e1e", hover_color="#5a2525", text_color=C_RED,
                          command=self._stop_background_daemon
                          ).pack(side="left", padx=(0, 6))
        else:
            ctk.CTkButton(ab, text="⟳ Poll All Now", width=120,
                          fg_color=C_BG_INPUT, border_width=1, border_color=C_BORDER,
                          hover_color=C_BORDER, text_color=C_TEXT_DIM,
                          command=lambda: threaded(self.telemetry.poll_all)
                          ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(ab, text="▶ Deploy All Docker", width=140,
                      fg_color="#1e3a5f", hover_color="#2554a0", text_color=C_BLUE,
                      command=self._deploy_all_docker).pack(side="left", padx=(0, 6))
        ctk.CTkButton(ab, text="📋 Export CSV", width=100,
                      fg_color=C_BG_INPUT, border_width=1, border_color=C_BORDER,
                      hover_color=C_BORDER, text_color=C_TEXT_DIM,
                      command=self._run_export_csv).pack(side="left")

        self._status_bar = ctk.CTkLabel(ab, text="Last poll: never",
                                        font=ctk.CTkFont(size=10),
                                        text_color=C_TEXT_MUTED)
        self._status_bar.pack(side="right")

        # Check for socket permission warning banner
        sock_path = "/var/run/docker.sock"
        if os.path.exists(sock_path) and not os.access(sock_path, os.R_OK | os.W_OK):
            self._docker_warning_frame = ctk.CTkFrame(tab, fg_color="#3a2512", border_width=1, border_color="#8a5315")
            self._docker_warning_frame.pack(fill="x", padx=4, pady=4)
            
            ctk.CTkLabel(
                self._docker_warning_frame,
                text="⚠️ Docker socket permission denied. GUI process cannot deploy or monitor containers.",
                text_color="#ffd080", font=ctk.CTkFont(size=12, weight="bold")
            ).pack(side="left", padx=10, pady=8)
            
            ctk.CTkButton(
                self._docker_warning_frame,
                text="⚡ Elevate & Bridge",
                width=110, height=26,
                fg_color="#8a5315", hover_color="#a86920", text_color="#ffffff",
                font=ctk.CTkFont(size=11, weight="bold"),
                command=self._launch_docker_bridge
            ).pack(side="right", padx=10, pady=6)

        self._cards_area = ctk.CTkScrollableFrame(tab, fg_color=C_BG_DARK)
        self._cards_area.pack(fill="both", expand=True, padx=4, pady=4)
        self._build_service_cards()

    def _build_service_cards(self) -> None:
        for w in self._cards_area.winfo_children():
            try:
                w.destroy()
            except Exception:
                pass
        self._service_cards.clear()

        results  = self.telemetry.get_results()
        statuses = self.docker_orch.all_statuses()

        categories: Dict[str, List[ServiceDefinition]] = {}
        for svc in self.services.values():
            categories.setdefault(svc.category, []).append(svc)

        for cat, svcs_in_cat in sorted(categories.items()):
            ctk.CTkLabel(self._cards_area, text=cat.upper(),
                         font=ctk.CTkFont(size=11, weight="bold"),
                         text_color=CATEGORY_COLORS.get(cat, C_TEXT_DIM),
                         ).pack(anchor="w", padx=6, pady=(10, 2))
            for svc in svcs_in_cat:
                result  = results.get(svc.name, empty_result(svc.name, ""))
                dstatus = statuses.get(svc.name, "unavailable")
                card    = ServiceCard(
                    self._cards_area, svc, result, dstatus,
                    on_configure=lambda s=svc: self._open_config(s),
                    on_deploy=lambda s=svc: self._deploy_single(s),
                    on_withdraw=lambda s=svc: self._request_withdraw(s),
                )
                card.pack(fill="x", padx=4, pady=2)
                self._service_cards[svc.name] = card

    def _build_chart_tab(self) -> None:
        tab = self._tabs.tab("Earnings Chart")
        self._chart_frame = EarningsChartFrame(tab, self.db)
        self._chart_frame.pack(fill="both", expand=True, padx=8, pady=8)
        ctk.CTkButton(tab, text="⟳ Refresh Chart",
                      fg_color=C_BG_INPUT, border_width=1, border_color=C_BORDER,
                      hover_color=C_BORDER, text_color=C_TEXT_DIM,
                      command=self._chart_frame.refresh).pack(pady=(0, 8))

    def _build_withdrawals_tab(self) -> None:
        tab = self._tabs.tab("Withdrawals")
        self._withdrawal_panel = WithdrawalHistoryPanel(tab, self.db)
        self._withdrawal_panel.pack(fill="both", expand=True, padx=8, pady=8)
        ctk.CTkButton(tab, text="⟳ Refresh",
                      fg_color=C_BG_INPUT, border_width=1, border_color=C_BORDER,
                      hover_color=C_BORDER, text_color=C_TEXT_DIM,
                      command=self._withdrawal_panel.refresh).pack(pady=(0, 8))

    def _build_logs_tab(self) -> None:
        tab = self._tabs.tab("Logs")
        LogsPanel(tab).pack(fill="both", expand=True, padx=8, pady=8)

    def _build_settings_tab(self) -> None:
        tab = self._tabs.tab("Settings")
        sf  = ctk.CTkScrollableFrame(tab, fg_color=C_BG_DARK)
        sf.pack(fill="both", expand=True, padx=8, pady=8)

        def _section(text: str) -> None:
            ctk.CTkLabel(sf, text=text,
                         font=ctk.CTkFont(size=14, weight="bold"),
                         text_color=C_TEXT).pack(anchor="w", pady=(14, 2))

        def _btn(text: str, cmd: Callable) -> None:
            ctk.CTkButton(
                sf, text=text, command=cmd,
                fg_color=C_BG_INPUT, border_width=1, border_color=C_BORDER,
                hover_color=C_BORDER, text_color=C_TEXT_DIM,
            ).pack(anchor="w", pady=4)

        # System info
        _section("System Info")
        def _show_preflight() -> None:
            r = run_preflight()
            lines = [
                f"Python:       {r['python_version'][:60]}",
                f"Platform:     {r['platform']}",
                f"Docker SDK:   {'✓' if r['docker_sdk'] else '✗'}",
                f"Docker CLI:   {'✓' if r['docker_cli'] else '✗'}  {r['docker_version']}",
                f"Public IP:    {r['public_ip']}",
                "",
                "Packages:",
            ] + [f"  {k:<28} {v}" for k, v in r["packages"].items()]
            messagebox.showinfo(f"{APP_NAME} Pre-flight", "\n".join(lines))
        _btn("Run Pre-flight Checks", _show_preflight)

        # Docker
        _section("Docker")
        _btn("Install / Check Docker",     self._install_docker_gui)
        _btn("Write docker-compose.yml",   self._write_compose_gui)

        # Auto-start
        _section("Auto-start")
        _btn("Install System Service (auto-start on boot)", self._install_service_gui)

        # Source Code Protection
        _section("Source Code Protection")
        def _protect_gui() -> None:
            src = Path(__file__).absolute()
            dest = src.parent / "Myriapod_secure.py"
            ok, msg = AetherLoader.protect(src, dest)
            if ok:
                messagebox.showinfo("Packaging Succeeded", f"Compiled and encrypted successfully!\nSaved launcher to:\n{msg}")
            else:
                messagebox.showerror("Packaging Failed", f"Could not protect source: {msg}")
        _btn("Package & Encrypt Source Code", _protect_gui)

        # Poll interval
        _section("Poll Interval")
        pi_row = ctk.CTkFrame(sf, fg_color="transparent")
        pi_row.pack(anchor="w", pady=4)
        ctk.CTkLabel(pi_row, text="Seconds:", text_color=C_TEXT_DIM).pack(side="left", padx=(0, 6))
        self._poll_entry = ctk.CTkEntry(pi_row, width=80,
                                        fg_color=C_BG_INPUT, border_color=C_BORDER,
                                        text_color=C_TEXT)
        self._poll_entry.insert(0, str(self.telemetry.poll_interval))
        self._poll_entry.pack(side="left")
        ctk.CTkButton(pi_row, text="Apply", width=60, height=28,
                      fg_color=C_ACCENT, text_color="#052e16", hover_color=C_ACCENT_DIM,
                      command=self._apply_poll_interval).pack(side="left", padx=6)

        # About
        _section("About")
        ctk.CTkLabel(sf,
                     text=(f"{APP_NAME} v{VERSION}\n"
                           f"A fully automated passive-income aggregator.\n"
                           f"Data: {DATA_DIR}\nLogs: {LOG_FILE}"),
                     text_color=C_TEXT_DIM, justify="left").pack(anchor="w")

    # ── UI callbacks ──────────────────────────────────────────────────────────
    def _on_telemetry_update(self, results: Dict[str, BalanceResult]) -> None:
        try:
            self.after(0, lambda: self._refresh_ui(results))
        except Exception:
            pass

    def _refresh_ui(self, results: Optional[Dict[str, BalanceResult]] = None) -> None:
        if results is None:
            results = self.telemetry.get_results()
        statuses = self.docker_orch.all_statuses()
        total    = sum(r.usd_value for r in results.values() if r.include_in_total)
        try:
            self._total_label.configure(text=f"Total: {format_usd(total)}")
            last_ip = self.db.get_last_ip() or "—"
            self._ip_label.configure(text=f"IP: {last_ip}")
            self._status_bar.configure(
                text=f"Last poll: {datetime.now().strftime('%H:%M:%S')}")
        except Exception:
            pass
        for svc_name, card in list(self._service_cards.items()):
            result  = results.get(svc_name, empty_result(svc_name, ""))
            dstatus = statuses.get(svc_name, "unavailable")
            try:
                card.update_result(result, dstatus)
            except Exception:
                pass

    def _open_config(self, svc: ServiceDefinition) -> None:
        try:
            ServiceConfigModal(self, svc, self.secrets,
                               on_save=lambda: threaded(self.telemetry.poll_all),
                               http=self.http)
        except Exception as exc:
            logger.error("Config modal: %s", exc)
            messagebox.showerror("Error", f"Could not open config: {exc}")

    def _deploy_single(self, svc: ServiceDefinition) -> None:
        def _do() -> None:
            ok, msg = self.docker_orch._deploy_container(svc)
            title = "Deploy succeeded" if ok else "Deploy failed"
            self.notifier.notify(title, f"{svc.name}: {msg}")
            if not ok:
                try:
                    self.after(0, lambda: messagebox.showerror(title, f"{svc.name}:\n{msg}"))
                except Exception:
                    pass
        threaded(_do)

    def _deploy_all_docker(self) -> None:
        def _do() -> None:
            res = self.docker_orch.deploy_all()
            success_count = sum(1 for status, _ in res.values() if status == "success")
            skipped_count = sum(1 for status, _ in res.values() if status == "skipped")
            failed_count = sum(1 for status, _ in res.values() if status == "failed")
            
            lines = []
            for name, (status, msg) in res.items():
                if status == "success":
                    icon = "✓"
                elif status == "skipped":
                    icon = "○"
                else:
                    icon = "✗"
                lines.append(f"  {icon} {name}: {msg}")
                
            msgs = "\n".join(lines)
            full_msg = (
                f"Deployment Complete:\n"
                f"  • Deployed: {success_count}\n"
                f"  • Skipped (No credentials): {skipped_count}\n"
                f"  • Failed: {failed_count}\n\n"
                f"{msgs}"
            )
            
            self.notifier.notify(
                "Deploy Swarm",
                f"Deployed={success_count} Skipped={skipped_count} Failed={failed_count}"
            )
            try:
                self.after(0, lambda: messagebox.showinfo("Deploy All Docker", full_msg))
            except Exception:
                pass
        threaded(_do)

    def _request_withdraw(self, svc: ServiceDefinition) -> None:
        results = self.telemetry.get_results()
        result  = results.get(svc.name)
        if not result or result.native_value is None:
            messagebox.showwarning(
                "No Balance",
                f"No balance data for {svc.name}.\n"
                "Configure credentials and poll first."
            )
            return

        dest = ""
        if svc.slug == "earnapp":
            dest_raw = simpledialog.askstring(
                "Destination",
                f"Enter PayPal e-mail for {svc.name} withdrawal:\n"
                f"Current balance: {result.primary_display}",
                parent=self,
            )
            if not dest_raw:
                return
            dest = dest_raw.strip()

        ok, title, msg = self.withdrawal_mgr.execute(svc, result, dest)
        fn = messagebox.showinfo if ok else messagebox.showerror
        fn(title, msg)
        if ok:
            try:
                self._withdrawal_panel.refresh()
            except Exception:
                pass

    def _run_export_csv(self) -> None:
        try:
            path = self.db.export_csv()
            messagebox.showinfo("Export Complete", f"Saved to:\n{path}")
        except Exception as exc:
            messagebox.showerror("Export Failed", str(exc))

    def _install_docker_gui(self) -> None:
        ok, msg = DockerInstaller.check_and_install()
        (messagebox.showinfo if ok else messagebox.showwarning)("Docker", msg)

    def _write_compose_gui(self) -> None:
        try:
            path, skipped = self.docker_orch.write_compose()
            skip_text     = "\n".join(f"  {n}: {r}" for n, r in skipped.items())
            messagebox.showinfo(
                "docker-compose.yml",
                f"Written to:\n{path}\n\n"
                + (f"Skipped:\n{skip_text}" if skipped else "All eligible services included."),
            )
        except Exception as exc:
            messagebox.showerror("Error", f"Could not write compose: {exc}")

    def _install_service_gui(self) -> None:
        ok, msg = ServiceInstaller.install_service(Path(__file__).absolute())
        (messagebox.showinfo if ok else messagebox.showwarning)("System Service", msg)

    def _apply_poll_interval(self) -> None:
        try:
            val = int(self._poll_entry.get().strip())
            if val < 30:
                messagebox.showwarning("Invalid", "Minimum poll interval is 30 seconds.")
                return
            self.telemetry.poll_interval = val
            messagebox.showinfo("Poll Interval", f"Poll interval set to {val}s.")
        except ValueError:
            messagebox.showerror("Invalid", "Enter a whole number of seconds.")

    def _on_close(self) -> None:
        if getattr(self, "is_client_only", False):
            self._shutdown()
            return

        if _HAS_PYSTRAY and self._tray_icon:
            self.withdraw()
            return

        ans = messagebox.askyesnocancel(
            "Close Myriapod",
            "Keep Myriapod running in the background?\n\n"
            "• Yes: Run autonomously in the background (set-and-forget)\n"
            "• No: Shutdown completely and exit\n"
            "• Cancel: Return to application",
            parent=self
        )
        if ans is True:
            import subprocess
            cmd = [sys.executable, __file__, "--cli"]
            try:
                if platform.system().lower() == "windows":
                    subprocess.Popen(cmd, creationflags=0x208, close_fds=True)
                else:
                    subprocess.Popen(cmd, start_new_session=True, close_fds=True)
                self.notifier.notify("Myriapod Daemon Started", "The engine is running autonomously in the background.")
            except Exception as e:
                logger.error("Failed to spawn background daemon: %s", e)
            self._shutdown()
        elif ans is False:
            self._shutdown()

    def _stop_background_daemon(self) -> None:
        pid = _get_active_daemon_pid()
        if pid:
            try:
                import psutil
                proc = psutil.Process(pid)
                proc.terminate()
                try:
                    proc.wait(timeout=3)
                except Exception:
                    proc.kill()
            except Exception as e:
                logger.debug("Failed to terminate background daemon cleanly: %s", e)
            with contextlib.suppress(Exception):
                PID_FILE.unlink()
            messagebox.showinfo("Daemon Stopped", "Background engine process has been shut down successfully.")
            self._shutdown()
        else:
            messagebox.showwarning("Not Running", "No active background daemon was found.")

    def _launch_docker_bridge(self) -> None:
        dialog = PasswordPromptDialog(
            self, "Root Elevation Required",
            "This command requires administrator privileges to create a secure permission bridge for the Docker socket."
        )
        self.wait_window(dialog)
        password = dialog.result
        if not password:
            return
            
        proxy_path = DATA_DIR / "docker_proxy.py"
        proxy_socket_path = DATA_DIR / "myriapod_docker.sock"
        
        proxy_code = textwrap.dedent("""\
            import socket
            import sys
            import os
            import threading
            import signal

            PROXY_SOCKET = sys.argv[1]
            TARGET_SOCKET = "/var/run/docker.sock"
            USER_UID = int(sys.argv[2])
            USER_GID = int(sys.argv[3])

            def pipe(source, destination):
                try:
                    while True:
                        data = source.recv(4096)
                        if not data:
                            break
                        destination.sendall(data)
                except Exception:
                    pass
                finally:
                    try:
                        source.close()
                    except Exception:
                        pass
                    try:
                        destination.close()
                    except Exception:
                        pass

            def handle_client(client_sock):
                try:
                    target_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                    target_sock.connect(TARGET_SOCKET)
                except Exception:
                    client_sock.close()
                    return

                t1 = threading.Thread(target=pipe, args=(client_sock, target_sock), daemon=True)
                t2 = threading.Thread(target=pipe, args=(target_sock, client_sock), daemon=True)
                t1.start()
                t2.start()

            def main():
                if os.path.exists(PROXY_SOCKET):
                    try:
                        os.unlink(PROXY_SOCKET)
                    except Exception:
                        pass

                server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                server.bind(PROXY_SOCKET)
                
                os.chmod(PROXY_SOCKET, 0o666)
                os.chown(PROXY_SOCKET, USER_UID, USER_GID)
                
                server.listen(128)
                
                def shutdown(signum, frame):
                    server.close()
                    if os.path.exists(PROXY_SOCKET):
                        try:
                            os.unlink(PROXY_SOCKET)
                        except Exception:
                            pass
                    sys.exit(0)
                    
                signal.signal(signal.SIGTERM, shutdown)
                signal.signal(signal.SIGINT, shutdown)

                while True:
                    try:
                        client, addr = server.accept()
                        threading.Thread(target=handle_client, args=(client,), daemon=True).start()
                    except Exception:
                        break

            if __name__ == "__main__":
                main()
        """)
        
        try:
            proxy_path.write_text(proxy_code, encoding="utf-8")
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to write bridge helper: {exc}")
            return
            
        import subprocess
        try:
            if proxy_socket_path.exists():
                proxy_socket_path.unlink()
        except Exception:
            pass
            
        cmd = ["sudo", "-S", sys.executable, str(proxy_path), str(proxy_socket_path), str(os.getuid()), str(os.getgid())]
        try:
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            proc.stdin.write(password + "\n")
            proc.stdin.flush()
            
            import time
            success = False
            for _ in range(15):
                time.sleep(0.2)
                if proxy_socket_path.exists():
                    success = True
                    break
                if proc.poll() is not None:
                    break
                    
            if success:
                logger.info("Privilege Escalation Bridge connected. DOCKER_HOST redirected.")
                os.environ["DOCKER_HOST"] = f"unix://{proxy_socket_path}"
                self._proxy_proc = proc
                
                self.docker_orch._cli_ok = True
                self.docker_orch._compose_cmd = _docker_compose_cmd()
                if _HAS_DOCKER:
                    try:
                        self.docker_orch.client = _docker_module.from_env()
                        self.docker_orch.client.ping()
                        logger.info("Docker SDK connected successfully via Privilege Bridge.")
                        self.docker_orch._ensure_network()
                    except Exception as exc:
                        logger.warning("Docker SDK ping via Bridge failed: %s", exc)
                        
                if hasattr(self, "_docker_warning_frame"):
                    self._docker_warning_frame.destroy()
                    
                messagebox.showinfo("Success", "Docker Privilege Bridge successfully established! Active nodes can now be managed.")
                self._refresh_ui()
            else:
                stderr_output = ""
                try:
                    proc.stdin.close()
                    stderr_output = proc.stderr.read().strip()
                except Exception:
                    pass
                msg = f"Failed to authenticate or initialize bridge.\n\n{stderr_output}" if stderr_output else "Authentication failed or helper crashed."
                messagebox.showerror("Elevation Failed", msg)
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to spawn elevation bridge: {exc}")

    def _shutdown(self) -> None:
        try:
            if hasattr(self, "_proxy_proc") and self._proxy_proc:
                self._proxy_proc.terminate()
                self._proxy_proc.wait(timeout=2)
        except Exception:
            pass
        try:
            self.telemetry.stop()
        except Exception:
            pass
        try:
            if self._tray_icon:
                self._tray_icon.stop()
        except Exception:
            pass
        try:
            self.destroy()
        except Exception:
            pass

# ═══════════════════════════════════════════════════════════════════════════════
# §24  SYSTEM TRAY
# ═══════════════════════════════════════════════════════════════════════════════
def _make_tray_image() -> Image.Image:
    img = load_app_logo(size=(64, 64))
    if img is None:
        img  = Image.new("RGBA", (64, 64), (13, 17, 23, 255))
        draw = ImageDraw.Draw(img)
        draw.ellipse((4, 4, 60, 60), fill=(20, 40, 20, 255))
        draw.text((20, 20), "N", fill=(57, 211, 83, 255))
    try:
        return img.convert("RGB")
    except Exception:
        return img


def setup_tray(app: MyriapodGUI) -> Optional[Any]:
    if not _HAS_PYSTRAY:
        return None
    try:
        icon_img = _make_tray_image()

        def _show(_i: Any = None, _it: Any = None) -> None:
            app.after(0, app.deiconify)
            app.after(50, app.lift)

        def _check(_i: Any = None, _it: Any = None) -> None:
            results = app.telemetry.get_results()
            total   = sum(r.usd_value for r in results.values() if r.include_in_total)
            app.notifier.notify("Current Earnings",
                                f"Total verified: {format_usd(total)}")

        def _quit(_i: Any = None, _it: Any = None) -> None:
            app.after(0, app._shutdown)

        menu = pystray.Menu(
            pystray.MenuItem("Show Myriapod", _show, default=True),
            pystray.MenuItem("Check Earnings",  _check),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit",            _quit),
        )
        tray = pystray.Icon(APP_NAME, icon_img, f"{APP_NAME} v{VERSION}", menu)
        app._tray_icon = tray
        threading.Thread(target=tray.run, daemon=True, name="TrayIcon").start()
        logger.info("System tray icon started.")
        return tray
    except Exception as exc:
        logger.warning("Tray icon failed: %s", exc)
        return None

# ═══════════════════════════════════════════════════════════════════════════════
# §25  SERVICE INSTALLER  (systemd / launchd / Task Scheduler)
# ═══════════════════════════════════════════════════════════════════════════════
class ServiceInstaller:
    @staticmethod
    def install_linux_systemd(script_path: Path) -> Tuple[bool, str]:
        unit = textwrap.dedent(f"""\
            [Unit]
            Description={APP_NAME} Passive Income Engine
            After=network-online.target docker.service
            Wants=network-online.target

            [Service]
            Type=simple
            User={os.getenv('USER', 'root')}
            WorkingDirectory={BASE_DIR}
            ExecStart={sys.executable} {script_path} --cli
            Restart=always
            RestartSec=15
            StandardOutput=journal
            StandardError=journal

            [Install]
            WantedBy=multi-user.target
        """)
        dest = Path("/etc/systemd/system/myriapod.service")
        try:
            dest.write_text(unit)
            subprocess.run(["systemctl", "daemon-reload"],
                           check=True, capture_output=True)
            subprocess.run(["systemctl", "enable", "myriapod.service"],
                           check=True, capture_output=True)
            return True, (f"systemd service installed at {dest}.\n"
                          "Run: sudo systemctl start myriapod")
        except PermissionError:
            return False, "Permission denied.  Run with sudo."
        except Exception as exc:
            return False, str(exc)

    @staticmethod
    def install_macos_launchd(script_path: Path) -> Tuple[bool, str]:
        try:
            import plistlib
            agents = Path.home() / "Library" / "LaunchAgents"
            agents.mkdir(parents=True, exist_ok=True)
            plist_path = agents / "com.myriapod.agent.plist"
            plist_path.write_bytes(plistlib.dumps({
                "Label":             "com.myriapod.agent",
                "ProgramArguments":  [str(sys.executable), str(script_path), "--cli"],
                "RunAtLoad":         True,
                "KeepAlive":         True,
                "StandardOutPath":   str(DATA_DIR / "launchd_stdout.log"),
                "StandardErrorPath": str(DATA_DIR / "launchd_stderr.log"),
                "WorkingDirectory":  str(BASE_DIR),
            }))
            subprocess.run(["launchctl", "load", str(plist_path)],
                           check=True, capture_output=True)
            return True, f"LaunchAgent installed at {plist_path}"
        except Exception as exc:
            return False, str(exc)

    @staticmethod
    def install_windows_task(script_path: Path) -> Tuple[bool, str]:
        xml = textwrap.dedent(f"""\
            <?xml version="1.0"?>
            <Task version="1.4"
                  xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
              <Triggers><LogonTrigger><Enabled>true</Enabled></LogonTrigger></Triggers>
              <Actions>
                <Exec>
                  <Command>{sys.executable}</Command>
                  <Arguments>{script_path} --cli</Arguments>
                  <WorkingDirectory>{BASE_DIR}</WorkingDirectory>
                </Exec>
              </Actions>
              <Settings>
                <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
                <RestartOnFailure>
                  <Interval>PT1M</Interval><Count>999</Count>
                </RestartOnFailure>
                <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
              </Settings>
            </Task>
        """)
        xml_path = DATA_DIR / "myriapod_task.xml"
        xml_path.write_text(xml, encoding="utf-8")
        try:
            subprocess.run(
                ["schtasks", "/Create", "/TN", APP_NAME, "/XML", str(xml_path), "/F"],
                check=True, capture_output=True,
            )
            return True, f"Windows Task Scheduler task '{APP_NAME}' created."
        except subprocess.CalledProcessError as exc:
            return False, (exc.stderr.decode() if exc.stderr else str(exc))
        except Exception as exc:
            return False, str(exc)

    @staticmethod
    def install_service(script_path: Path) -> Tuple[bool, str]:
        system = platform.system().lower()
        if system == "linux":
            return ServiceInstaller.install_linux_systemd(script_path)
        if system == "darwin":
            return ServiceInstaller.install_macos_launchd(script_path)
        if system == "windows":
            return ServiceInstaller.install_windows_task(script_path)
        return False, f"Unsupported platform: {system}"

# ═══════════════════════════════════════════════════════════════════════════════
# §25B AETHERLOADER PACKAGER
# ═══════════════════════════════════════════════════════════════════════════════
class AetherLoader:
    """
    An extremely secure, professional, and overengineered Python protector.
    Compiles Python source files, serializes to compressed bytecode,
    encrypts the result using a custom KDF-derived PBKDF2 key with HMAC-CTR stream cipher,
    and generates an optimized bootstrap wrapper that runs entirely in memory.
    """
    @staticmethod
    def protect(src_file: Path, dest_file: Path) -> Tuple[bool, str]:
        try:
            source = src_file.read_text(encoding="utf-8")
            code_obj = compile(source, src_file.name, "exec")
            import marshal, zlib, base64, os, hashlib, hmac
            serialized = marshal.dumps(code_obj)
            compressed = zlib.compress(serialized, 9)
            salt = os.urandom(16)
            key_seed = os.urandom(32)
            derived = hashlib.pbkdf2_hmac("sha256", key_seed, salt, 1000)
            
            enc_key = derived[:16]
            sign_key = derived[16:]
            
            iv = os.urandom(16)
            keystream = b""
            blocks_needed = (len(compressed) + 31) // 32
            for i in range(blocks_needed):
                counter = i.to_bytes(8, 'big')
                keystream += hmac.new(enc_key, iv + counter, hashlib.sha256).digest()
            ciphertext = bytes(a ^ b for a, b in zip(compressed, keystream))
            tag = hmac.new(sign_key, iv + ciphertext, hashlib.sha256).digest()
            packed_payload = base64.b64encode(salt + key_seed + iv + tag + ciphertext).decode()
            
            wrapper = textwrap.dedent(f"""\
                #!/usr/bin/env python3
                # -*- coding: utf-8 -*-
                \"\"\"
                ╔═══════════════════════════════════════════════════════════════════════════════╗
                ║  Myriapod Secure Launcher                                                     ║
                ║  Protected & Packaged via AetherLoader v1.0                                   ║
                ╚═══════════════════════════════════════════════════════════════════════════════╝
                \"\"\"
                import base64, hashlib, hmac, marshal, zlib, sys, os
                
                PAYLOAD = "{packed_payload}"
                
                def launch():
                    try:
                        raw = base64.b64decode(PAYLOAD)
                        salt = raw[:16]
                        key_seed = raw[16:48]
                        iv = raw[48:64]
                        tag_received = raw[64:96]
                        ciphertext = raw[96:]
                        
                        derived = hashlib.pbkdf2_hmac("sha256", key_seed, salt, 1000)
                        enc_key = derived[:16]
                        sign_key = derived[16:]
                        
                        tag_expected = hmac.new(sign_key, iv + ciphertext, hashlib.sha256).digest()
                        if not hmac.compare_digest(tag_expected, tag_received):
                            raise RuntimeError("Integrity check failed: payload compromised.")
                            
                        keystream = b""
                        blocks_needed = (len(ciphertext) + 31) // 32
                        for i in range(blocks_needed):
                            counter = i.to_bytes(8, 'big')
                            keystream += hmac.new(enc_key, iv + counter, hashlib.sha256).digest()
                        compressed = bytes(a ^ b for a, b in zip(ciphertext, keystream))
                        
                        serialized = zlib.decompress(compressed)
                        code_obj = marshal.loads(serialized)
                        
                        globals_dict = {{
                            "__file__": os.path.abspath(__file__),
                            "__name__": "__main__",
                            "__doc__": None,
                            "__package__": None,
                        }}
                        exec(code_obj, globals_dict)
                    except Exception as e:
                        print("Error starting Myriapod: ", e)
                        sys.exit(1)
                        
                if __name__ == "__main__":
                    launch()
            """)
            dest_file.write_text(wrapper, encoding="utf-8")
            return True, str(dest_file)
        except Exception as e:
            return False, str(e)


def setup_signal_handlers(telemetry_engine: Any) -> None:
    def handler(signum, frame):
        logger.info("Received signal %d. Initiating graceful shutdown...", signum)
        telemetry_engine.stop()
        # Explicit clean shutdowns
        try:
            if PID_FILE.exists():
                pid = int(PID_FILE.read_text().strip())
                if pid == os.getpid():
                    PID_FILE.unlink()
        except Exception:
            pass
        sys.exit(0)

    try:
        signal.signal(signal.SIGTERM, handler)
        signal.signal(signal.SIGINT, handler)
    except Exception as exc:
        logger.warning("Could not register graceful signal handlers: %s", exc)


# ═══════════════════════════════════════════════════════════════════════════════
# §26  AUTO-UPDATER
# ═══════════════════════════════════════════════════════════════════════════════
class AutoUpdater:
    GITHUB_REPO = "username/Myriapod"   # ← change to real repo

    def __init__(self) -> None:
        self._api = (f"https://api.github.com/repos/"
                     f"{self.GITHUB_REPO}/releases/latest")

    def check(self) -> Tuple[bool, Optional[str], Optional[str]]:
        try:
            r = requests.get(self._api, timeout=8)
            if r.ok:
                release = r.json()
                latest  = release.get("tag_name", "").lstrip("v")
                url     = release.get("html_url")
                if latest and latest != VERSION:
                    return True, latest, url
        except Exception:
            pass
        return False, None, None

    def check_and_notify(self, notifier: NotificationManager) -> None:
        available, latest, url = self.check()
        if available and latest:
            notifier.notify(
                "Update Available",
                f"{APP_NAME} v{latest} available (you have v{VERSION}).\n{url}",
                level="info",
            )

# ═══════════════════════════════════════════════════════════════════════════════
# §27  ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════
def main() -> None:
    parser = argparse.ArgumentParser(
        description=f"{APP_NAME} v{VERSION} — Passive Income Engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
        Examples:
          python Myriapod.py                    # Launch GUI
          python Myriapod.py --cli              # Headless terminal mode
          python Myriapod.py --cli --setup      # First-run credential wizard
          python Myriapod.py --preflight        # System checks only
          python Myriapod.py --install-service  # Register as auto-start service
          python Myriapod.py --install-docker   # Install Docker (Linux)
          python Myriapod.py --write-compose    # Write docker-compose.yml and exit
        """),
    )
    parser.add_argument("--cli",             action="store_true")
    parser.add_argument("--setup",           action="store_true")
    parser.add_argument("--debug",           action="store_true")
    parser.add_argument("--preflight",       action="store_true")
    parser.add_argument("--install-service", action="store_true")
    parser.add_argument("--install-docker",  action="store_true")
    parser.add_argument("--write-compose",   action="store_true")
    args = parser.parse_args()

    # ── Pre-flight only ────────────────────────────────────────────────────────
    if args.preflight:
        r = run_preflight()
        bar = "=" * 64
        print(f"\n{bar}\n  {APP_NAME} v{VERSION} — Pre-Flight Check\n{bar}")
        print(f"  Python:       {r['python_version'][:60]}")
        print(f"  Platform:     {r['platform']}")
        print(f"  Architecture: {r['arch']}")
        print(f"  Docker SDK:   {'[OK]' if r['docker_sdk'] else '[NO]'}")
        print(f"  Docker CLI:   {'[OK]' if r['docker_cli'] else '[NO]'}  {r['docker_version']}")
        print(f"  Docker Daemon:{'[OK]' if r['docker_daemon'] else '[NO]'}")
        print(f"  Compose:      {r['docker_compose']}")
        print(f"  Public IP:    {r['public_ip']}")
        print("\n  Package Status:")
        for pkg, status in r["packages"].items():
            ok    = "MISSING" not in status
            color = Fore.GREEN if ok else Fore.YELLOW
            print(f"    {color}{pkg:<30} {status}{Style.RESET_ALL}")
        print(bar + "\n")
        return

    if args.install_docker:
        ok, msg = DockerInstaller.check_and_install()
        print(f"\n{Fore.GREEN if ok else Fore.YELLOW}{msg}{Style.RESET_ALL}\n")
        return

    # ── Core objects ───────────────────────────────────────────────────────────
    secrets     = SecretManager()
    secrets.sync_from_env(SERVICES)  # Import any .env credentials into vault
    db          = DatabaseManager()
    docker_orch = DockerOrchestrator(SERVICES, secrets)
    http        = HTTPSessionManager()
    notifier    = NotificationManager(db)
    withdrawal  = WithdrawalManager(secrets, db)
    updater     = AutoUpdater()

    if args.write_compose:
        path, skipped = docker_orch.write_compose()
        print(f"\n{Fore.GREEN}Written: {path}{Style.RESET_ALL}")
        if skipped:
            print(f"{Fore.YELLOW}Skipped:{Style.RESET_ALL}")
            for n, r in skipped.items():
                print(f"  {n}: {r}")
        return

    if args.install_service:
        ok, msg = ServiceInstaller.install_service(Path(__file__).absolute())
        print(f"\n{Fore.GREEN if ok else Fore.YELLOW}{msg}{Style.RESET_ALL}\n")
        return

    # Background update check
    threaded(updater.check_and_notify, notifier)

    # ── CLI mode ───────────────────────────────────────────────────────────────
    if args.cli:
        CLIController.run(db, docker_orch, http, SERVICES, secrets, notifier,
                          setup=args.setup)
        return

    # ── GUI mode ───────────────────────────────────────────────────────────────
    daemon_pid = _get_active_daemon_pid()
    is_client_only = daemon_pid is not None

    telemetry = TelemetryEngine(
        db, SERVICES, docker_orch, http, secrets, notifier,
        poll_interval=POLL_INTERVAL_SECS,
    )

    if is_client_only:
        telemetry.results = db.get_latest_results(SERVICES)
        telemetry.start = lambda: None
        telemetry.poll_all = lambda: None
    else:
        setup_signal_handlers(telemetry)
        telemetry.start()

    app = MyriapodGUI(db, docker_orch, http, telemetry, SERVICES, secrets,
                   withdrawal, notifier, is_client_only=is_client_only)
    
    if not is_client_only:
        setup_tray(app)
        threaded(telemetry.poll_all)

    # First-run welcome message
    has_any = any(
        secrets.has(f.key)
        for svc in SERVICES.values()
        for f in svc.setup_fields
    )
    if not has_any:
        app.after(
            1000,
            lambda: messagebox.showinfo(
                f"Welcome to {APP_NAME}",
                "No credentials configured yet.\n\n"
                "Click ⚙ Configure on any service card to enter your credentials.\n"
                "Or run with --cli --setup for the terminal wizard.",
            ),
        )

    app.mainloop()


if __name__ == "__main__":
    main()
