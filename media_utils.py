import mimetypes
import subprocess
from io import BytesIO
from pathlib import Path
from typing import Optional, Tuple

from config import (
    FFMPEG_BIN,
    FFPROBE_BIN,
    HEIF_OK,
    Image,
    MEDIA_EXTS_IMG,
    MEDIA_EXTS_VID,
)


def is_video(p: Path) -> bool:
    ext = p.suffix.lower()
    if ext in MEDIA_EXTS_VID:
        return True
    mt, _ = mimetypes.guess_type(str(p))
    return (mt or "").startswith("video/")


def is_image(p: Path) -> bool:
    # treat heic/heif as image even if mimetypes is weird
    if p.suffix.lower() in {".heic", ".heif"}:
        return True
    mt, _ = mimetypes.guess_type(str(p))
    return (mt or "").startswith("image/")


def is_media(p: Path) -> bool:
    ext = p.suffix.lower()
    return ext in MEDIA_EXTS_IMG or ext in MEDIA_EXTS_VID or is_image(p) or is_video(p)


def format_size(num: int) -> str:
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if num < 1024:
            return f"{num:.0f} {unit}" if unit == "B" else f"{num:.1f} {unit}"
        num /= 1024
    return f"{num:.1f} PB"


def ffmpeg_exists() -> bool:
    try:
        subprocess.run(
            [FFMPEG_BIN, "-version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return True
    except Exception:
        return False


def ffprobe_duration_seconds(fpath: Path) -> Optional[float]:
    try:
        p = subprocess.run(
            [
                FFPROBE_BIN,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(fpath),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if p.returncode != 0:
            return None
        s = p.stdout.decode("utf-8", "ignore").strip()
        return float(s) if s else None
    except Exception:
        return None


def _ffmpeg_grab_frame_jpeg_fastseek(fpath: Path, size: int, seek_seconds: float) -> bytes:
    vf = f"scale={size}:{size}:force_original_aspect_ratio=increase,crop={size}:{size}"
    cmd = [
        FFMPEG_BIN,
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        f"{seek_seconds:.3f}",  # FAST seek (may fail for some)
        "-i",
        str(fpath),
        "-frames:v",
        "1",
        "-vf",
        vf,
        "-f",
        "image2pipe",
        "-vcodec",
        "mjpeg",
        "pipe:1",
    ]
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if p.returncode != 0 or not p.stdout:
        raise RuntimeError(p.stderr.decode("utf-8", "ignore")[:500])
    return p.stdout


def _ffmpeg_grab_frame_jpeg_slowseek(fpath: Path, size: int, seek_seconds: float) -> bytes:
    vf = f"scale={size}:{size}:force_original_aspect_ratio=increase,crop={size}:{size}"
    cmd = [
        FFMPEG_BIN,
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(fpath),
        "-ss",
        f"{seek_seconds:.3f}",  # SLOW/accurate seek (more compatible)
        "-frames:v",
        "1",
        "-vf",
        vf,
        "-f",
        "image2pipe",
        "-vcodec",
        "mjpeg",
        "pipe:1",
    ]
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if p.returncode != 0 or not p.stdout:
        raise RuntimeError(p.stderr.decode("utf-8", "ignore")[:500])
    return p.stdout


def generate_thumb_bytes(fpath: Path, size: int) -> Tuple[bytes, str]:
    """
    Returns (bytes, mimetype). Generates JPEG thumbnails for images.
    """
    if Image is None:
        raise RuntimeError("Pillow not installed")

    # HEIC needs pillow-heif
    if fpath.suffix.lower() in {".heic", ".heif"} and not HEIF_OK:
        raise RuntimeError("HEIC/HEIF support not installed (pillow-heif)")

    with Image.open(fpath) as im:  # type: ignore[call-arg]
        if im.mode not in ("RGB", "L"):
            im = im.convert("RGB")
        else:
            im = im.convert("RGB")
        im.thumbnail((size, size))
        buf = BytesIO()
        im.save(buf, format="JPEG", quality=82, optimize=True)
        return buf.getvalue(), "image/jpeg"


def generate_video_thumb_bytes(fpath: Path, size: int) -> Tuple[bytes, str]:
    if not ffmpeg_exists():
        raise RuntimeError("ffmpeg not installed or not reachable (PATH/FFMPEG_BIN)")

    dur = ffprobe_duration_seconds(fpath)

    # Explorer-ish selection: ~10% in, clamp
    if dur and dur > 0:
        t = max(1.0, min(30.0, dur * 0.10))
        candidates = [t, min(t + 1.0, max(1.0, dur - 0.2)), max(1.0, dur * 0.25)]
    else:
        candidates = [1.0, 2.0, 3.0]

    last_err: Optional[Exception] = None
    for seek in candidates:
        # Try fast seek first, then fallback
        try:
            jpg = _ffmpeg_grab_frame_jpeg_fastseek(fpath, size, seek)
            return jpg, "image/jpeg"
        except Exception as e:
            last_err = e
        try:
            jpg = _ffmpeg_grab_frame_jpeg_slowseek(fpath, size, seek)
            return jpg, "image/jpeg"
        except Exception as e:
            last_err = e

    raise RuntimeError(f"ffmpeg frame extraction failed: {last_err}")

