import os
import mimetypes
from pathlib import Path

from flask import Flask
from dotenv import load_dotenv

load_dotenv()

# ----------------------------
# FFMPEG / FFPROBE BINARIES
# ----------------------------
FFMPEG_BIN = r"C:\ffmpeg\bin\ffmpeg.exe"
FFPROBE_BIN = r"C:\ffmpeg\bin\ffprobe.exe"

# ----------------------------
# OPTIONAL: HEIC/HEIF SUPPORT
# ----------------------------
HEIF_OK = False
try:
    from PIL import Image

    try:
        import pillow_heif  # noqa: F401

        pillow_heif.register_heif_opener()
        HEIF_OK = True
    except Exception:
        HEIF_OK = False
except Exception:
    Image = None  # type: ignore[assignment]
    HEIF_OK = False

# ----------------------------
# CONFIG (from environment, with defaults)
# ----------------------------
FFMPEG_BIN = os.getenv("FFMPEG_BIN")
FFPROBE_BIN = os.getenv("FFPROBE_BIN")

ROOT_DIR = os.getenv("ROOT_DIR")  # folder to share
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")  # set a strong token

# Thumbnail cache folder (on disk)
THUMB_CACHE_DIR = Path(".thumb_cache").resolve()

# Media extensions
MEDIA_EXTS_IMG = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".heic", ".heif"}
MEDIA_EXTS_VID = {".mp4", ".webm", ".ogg", ".mov", ".m4v", ".mkv", ".avi"}  # browser support varies

# Help mimetypes recognize heic/heif
mimetypes.add_type("image/heic", ".heic")
mimetypes.add_type("image/heif", ".heif")

# ----------------------------
# FLASK APP
# ----------------------------
app = Flask(__name__)
root_path = Path(ROOT_DIR).resolve()

