import hashlib
import time
from pathlib import Path

from config import THUMB_CACHE_DIR


def cache_key_for_thumb(fpath: Path, size: int) -> str:
    st = fpath.stat()
    raw = f"{str(fpath.resolve())}|{st.st_mtime_ns}|{st.st_size}|{size}".encode(
        "utf-8",
        "ignore",
    )
    return hashlib.sha256(raw).hexdigest()


def cache_key_for_vthumb(fpath: Path, size: int) -> str:
    st = fpath.stat()
    raw = f"VID|{str(fpath.resolve())}|{st.st_mtime_ns}|{st.st_size}|{size}".encode(
        "utf-8",
        "ignore",
    )
    return hashlib.sha256(raw).hexdigest()


def ensure_thumb_cache_dir() -> None:
    THUMB_CACHE_DIR.mkdir(parents=True, exist_ok=True)


def cleanup_thumb_cache_age(max_age_days: int = 1) -> None:
    """
    Delete cached thumbnails older than max_age_days (based on file mtime).
    """
    if not THUMB_CACHE_DIR.exists():
        return

    cutoff = time.time() - (max_age_days * 86400)

    for f in THUMB_CACHE_DIR.glob("*.jpg"):
        try:
            if f.stat().st_mtime < cutoff:
                f.unlink()
        except OSError:
            pass


def enforce_thumb_cache_size_limit(max_mb: int = 500) -> None:
    """
    Ensure cache total size <= max_mb by deleting oldest files first until under limit.
    """
    if not THUMB_CACHE_DIR.exists():
        return

    max_bytes = max_mb * 1024 * 1024

    files = []
    total = 0

    for f in THUMB_CACHE_DIR.glob("*.jpg"):
        try:
            st = f.stat()
            files.append((f, st.st_mtime, st.st_size))
            total += st.st_size
        except OSError:
            pass

    if total <= max_bytes:
        return

    files.sort(key=lambda x: x[1])  # oldest first
    for f, _mtime, sz in files:
        if total <= max_bytes:
            break
        try:
            f.unlink()
            total -= sz
        except OSError:
            pass


def maintain_thumb_cache(max_age_days: int = 1, max_mb: int = 500) -> None:
    cleanup_thumb_cache_age(max_age_days=max_age_days)
    enforce_thumb_cache_size_limit(max_mb=max_mb)

