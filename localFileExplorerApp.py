import os
import mimetypes
import hashlib
from io import BytesIO
from pathlib import Path
from urllib.parse import quote
import time
import subprocess
import zipfile
import tempfile

from flask import Flask, abort, request, send_file, Response, after_this_request
from typing import Optional

FFMPEG_BIN = r"C:\ffmpeg\bin\ffmpeg.exe"
FFPROBE_BIN = r"C:\ffmpeg\bin\ffprobe.exe"
# ----------------------------
# OPTIONAL: HEIC/HEIF SUPPORT
# ----------------------------
# Install:
#   pip install pillow pillow-heif
#
# If pillow-heif isn't installed, HEIC will still be listed, but previews/thumbnails
# will show a friendly message instead of crashing.
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
    Image = None
    HEIF_OK = False

# ----------------------------
# CONFIG
# ----------------------------
ROOT_DIR = r"D:\Ring ceremony photos"   # <-- change this to the folder you want to share
HOST = "0.0.0.0"
PORT = 8000
ACCESS_TOKEN = "pandey-9999"  # <-- set a strong token

# Thumbnail cache folder (on disk)
THUMB_CACHE_DIR = Path(".thumb_cache").resolve()

# ----------------------------
# APP
# ----------------------------
app = Flask(__name__)
root_path = Path(ROOT_DIR).resolve()

# Add HEIC/HEIF extensions
MEDIA_EXTS_IMG = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".heic", ".heif"}
MEDIA_EXTS_VID = {".mp4", ".webm", ".ogg", ".mov", ".m4v", ".mkv", ".avi"}  # browser support varies

# Help mimetypes recognize heic/heif
mimetypes.add_type("image/heic", ".heic")
mimetypes.add_type("image/heif", ".heif")

# View types requested:
# 1: Extra Large Icons
# 2: Large Icons
# 3: Medium Icons
# 4: Small Icons
# 5: List
# 6: Details
VIEW_SIZES = {
    1: 256,
    2: 160,
    3: 96,
    4: 64,
}
VIEW_LABELS = {
    1: "Extra Large Icons",
    2: "Large Icons",
    3: "Medium Icons",
    4: "Small Icons",
    5: "List",
    6: "Details",
}


def require_token():
    token = request.args.get("token") or request.headers.get("X-Token")
    if ACCESS_TOKEN and token != ACCESS_TOKEN:
        abort(403, "Forbidden: invalid or missing token")


def safe_resolve(rel: str) -> Path:
    rel = rel.lstrip("/").replace("\\", "/")
    target = (root_path / rel).resolve()
    if root_path not in target.parents and target != root_path:
        abort(403, "Forbidden: path outside shared root")
    return target


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


def html_page(title: str, body: str) -> str:
    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>{title}</title>
  <style>
    body {{ font-family: system-ui, Arial, sans-serif; margin: 16px; }}
    a {{ text-decoration: none; color: inherit; }}
    .path {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }}
    .muted {{ color: #666; }}
    .btn {{ display:inline-block; padding:8px 12px; border:1px solid #ddd; border-radius:10px; margin-right:8px; background:#fff; cursor:pointer; }}
    .toolbar {{ display:flex; flex-wrap: wrap; gap:8px; align-items:center; margin: 12px 0 10px; }}
    .toolbar .spacer {{ flex: 1; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ padding: 10px; border-bottom: 1px solid #eee; text-align: left; }}

    /* Multi-select bar */
    .selectbar {{
      display:flex;
      gap:8px;
      align-items:center;
      flex-wrap: wrap;
      margin: 8px 0 16px;
      padding: 10px;
      border: 1px solid #eee;
      border-radius: 14px;
      background: #fafafa;
    }}
    .selectbar .muted {{ margin:0; }}

    /* Icon/Grid view */
    .grid {{
      display: grid;
      gap: 12px;
      grid-template-columns: repeat(auto-fill, minmax(var(--cell), 1fr));
      align-items: start;
      width: 100%;
    }}
    .card {{
      border: 1px solid #eee;
      border-radius: 14px;
      padding: 10px;
      background: #fff;
      min-width: 0;
    }}
    .cardwrap {{ position: relative; }}
    .check {{
      position:absolute;
      top: 10px;
      left: 10px;
      width: 18px;
      height: 18px;
      z-index: 2;
      accent-color: #111;
    }}

    .thumb {{
      width: 100%;
      height: var(--thumb);
      border-radius: 12px;
      border: 1px solid #eee;
      overflow: hidden;
      background: #fafafa;
      display: flex;
      align-items: center;
      justify-content: center;
    }}
    .thumb img {{
      width: 100%;
      height: 100%;
      object-fit: cover;
      display:block;
    }}
    .name {{
      margin-top: 8px;
      font-size: 14px;
      word-break: break-word;
      line-height: 1.25;
    }}
    .meta {{
      margin-top: 4px;
      font-size: 12px;
      color: #666;
    }}

    /* List view */
    .list {{
      display:flex;
      flex-direction: column;
      gap: 6px;
    }}
    .list-item {{
      display:flex;
      gap: 10px;
      align-items:center;
      padding: 8px 10px;
      border: 1px solid #eee;
      border-radius: 12px;
      background:#fff;
      position: relative;
    }}
    .list-item .check {{
      position: static;
      width: 18px;
      height: 18px;
      margin-right: 2px;
    }}
    .list-item .mini {{
      width: 44px;
      height: 44px;
      border-radius: 10px;
      border: 1px solid #eee;
      overflow:hidden;
      background:#fafafa;
      display:flex;
      align-items:center;
      justify-content:center;
      flex: 0 0 44px;
    }}
    .list-item .mini img {{
      width:100%;
      height:100%;
      object-fit:cover;
    }}
    .list-item .title {{
      font-size: 14px;
      line-height: 1.25;
      word-break: break-word;
    }}
    .list-item .sub {{
      font-size: 12px;
      color: #666;
      margin-top: 2px;
    }}

    /* Preview */
    .preview {{ margin-top: 16px; }}
    .preview img {{ max-width: 100%; height: auto; border: 1px solid #eee; border-radius: 8px; }}
    .preview video {{ max-width: 100%; border: 1px solid #eee; border-radius: 8px; }}
  </style>
</head>
<body>
  {body}

  <script>
  function toggleAll(checked) {{
    document.querySelectorAll("input.filecheck").forEach(cb => {{
      if (!cb.disabled) cb.checked = checked;
    }});
    updateCount();
  }}

  function updateCount() {{
    const n = document.querySelectorAll("input.filecheck:checked").length;
    const el = document.getElementById("selCount");
    if (el) el.textContent = n;
  }}

  function getSelectedFiles() {{
    return Array.from(document.querySelectorAll("input.filecheck:checked"))
      .map(cb => cb.value);
  }}

  async function downloadSelected() {{
    const files = getSelectedFiles();
    if (!files.length) {{
      alert("No files selected");
      return;
    }}

    const modeEl = document.getElementById("dlMode");
    const mode = modeEl ? modeEl.value : "zip";

    if (mode === "zip") {{
      const form = document.getElementById("selectForm");
      if (form) form.submit();
      return;
    }}

    const token = new URLSearchParams(location.search).get("token") || "";
    for (let i = 0; i < files.length; i++) {{
      const rel = files[i];
      const url = `/download/${{encodeURIComponent(rel)}}?token=${{encodeURIComponent(token)}}`;

      const a = document.createElement("a");
      a.href = url;
      a.download = "";
      document.body.appendChild(a);
      a.click();
      a.remove();

      await new Promise(r => setTimeout(r, 400));
    }}
  }}

  // Prevent navigation when clicking checkbox sitting on top of a link/card
  document.addEventListener("click", (e) => {{
    const t = e.target;
    if (t && t.classList && t.classList.contains("filecheck")) {{
      e.stopPropagation();
      updateCount();
    }}
  }}, true);

  document.addEventListener("change", (e) => {{
    const t = e.target;
    if (t && t.classList && t.classList.contains("filecheck")) updateCount();
  }});

  document.addEventListener("DOMContentLoaded", updateCount);
</script>
</body>
</html>"""


def get_view_type() -> int:
    try:
        v = int(request.args.get("view", "6"))
    except ValueError:
        v = 6
    return v if v in VIEW_LABELS else 6


def view_link(rel: str, view: int) -> str:
    rel_q = quote(rel) if rel else ""
    base = f"/browse/{rel_q}" if rel else "/"
    return f"{base}?token={quote(ACCESS_TOKEN)}&view={view}"


def get_prev_next(rel_file: str):
    rel_norm = rel_file.strip("/").replace("\\", "/")
    fpath = safe_resolve(rel_norm)
    folder = fpath.parent

    media_files = []
    for p in folder.iterdir():
        if p.is_file() and is_media(p):
            media_files.append(p)

    media_files.sort(key=lambda x: x.name.lower())

    try:
        idx = next(i for i, p in enumerate(media_files) if p.resolve() == fpath.resolve())
    except StopIteration:
        return None, None

    prev_rel = None
    next_rel = None
    if idx > 0:
        prev_rel = str(media_files[idx - 1].relative_to(root_path)).replace("\\", "/")
    if idx < len(media_files) - 1:
        next_rel = str(media_files[idx + 1].relative_to(root_path)).replace("\\", "/")
    return prev_rel, next_rel


def cache_key_for_thumb(fpath: Path, size: int) -> str:
    st = fpath.stat()
    raw = f"{str(fpath.resolve())}|{st.st_mtime_ns}|{st.st_size}|{size}".encode("utf-8", "ignore")
    return hashlib.sha256(raw).hexdigest()


def ensure_thumb_cache_dir():
    THUMB_CACHE_DIR.mkdir(parents=True, exist_ok=True)


def generate_thumb_bytes(fpath: Path, size: int) -> tuple[bytes, str]:
    """
    Returns (bytes, mimetype). Generates JPEG thumbnails for images.
    """
    if Image is None:
        raise RuntimeError("Pillow not installed")

    # HEIC needs pillow-heif
    if fpath.suffix.lower() in {".heic", ".heif"} and not HEIF_OK:
        raise RuntimeError("HEIC/HEIF support not installed (pillow-heif)")

    with Image.open(fpath) as im:
        if im.mode not in ("RGB", "L"):
            im = im.convert("RGB")
        else:
            im = im.convert("RGB")
        im.thumbnail((size, size))
        buf = BytesIO()
        im.save(buf, format="JPEG", quality=82, optimize=True)
        return buf.getvalue(), "image/jpeg"


# ----------------------------
# VIDEO THUMBNAILS (ffmpeg)
# ----------------------------
def ffmpeg_exists() -> bool:
    try:
        subprocess.run([FFMPEG_BIN, "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        return True
    except Exception:
        return False


def cache_key_for_vthumb(fpath: Path, size: int) -> str:
    st = fpath.stat()
    raw = f"VID|{str(fpath.resolve())}|{st.st_mtime_ns}|{st.st_size}|{size}".encode("utf-8", "ignore")
    return hashlib.sha256(raw).hexdigest()


def ffprobe_duration_seconds(fpath: Path) -> Optional[float]:
    try:
        p = subprocess.run(
            [FFPROBE_BIN, "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(fpath)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False
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
        "-loglevel", "error",
        "-ss", f"{seek_seconds:.3f}",      # FAST seek (may fail for some)
        "-i", str(fpath),
        "-frames:v", "1",
        "-vf", vf,
        "-f", "image2pipe",
        "-vcodec", "mjpeg",
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
        "-loglevel", "error",
        "-i", str(fpath),
        "-ss", f"{seek_seconds:.3f}",      # SLOW/accurate seek (more compatible)
        "-frames:v", "1",
        "-vf", vf,
        "-f", "image2pipe",
        "-vcodec", "mjpeg",
        "pipe:1",
    ]
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if p.returncode != 0 or not p.stdout:
        raise RuntimeError(p.stderr.decode("utf-8", "ignore")[:500])
    return p.stdout


def generate_video_thumb_bytes(fpath: Path, size: int) -> tuple[bytes, str]:
    if not ffmpeg_exists():
        raise RuntimeError("ffmpeg not installed or not reachable (PATH/FFMPEG_BIN)")

    dur = ffprobe_duration_seconds(fpath)

    # Explorer-ish selection: ~10% in, clamp
    if dur and dur > 0:
        t = max(1.0, min(30.0, dur * 0.10))
        candidates = [t, min(t + 1.0, max(1.0, dur - 0.2)), max(1.0, dur * 0.25)]
    else:
        candidates = [1.0, 2.0, 3.0]

    last_err = None
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

@app.route("/")
def index():
    require_token()
    return browse("")


@app.route("/browse/<path:rel>")
def browse(rel):
    require_token()
    view = get_view_type()

    folder = safe_resolve(rel)
    if not folder.exists():
        abort(404, "Not found")
    if folder.is_file():
        return file_view(rel)

    rel_norm = rel.strip("/")
    title = "Local File Browser"

    # parent link
    if rel_norm:
        parent = str(Path(rel_norm).parent).replace("\\", "/")
        parent_link = view_link(parent if parent != "." else "", view)
        up = f'<a class="btn" href="{parent_link}">⬅ Up</a>'
    else:
        up = ""

    # toolbar (view switch)
    view_options = "\n".join(
        f"<option value='{view_link(rel_norm, v)}' {'selected' if v == view else ''}>"
        f"{v}: {VIEW_LABELS[v]}</option>"
        for v in [1, 2, 3, 4, 5, 6]
    )

    toolbar = f"""
    <div class="toolbar">
      {up}
      <div class="spacer"></div>
    
      <label class="muted" style="display:flex; align-items:center; gap:8px;">
        View:
        <select class="btn" style="padding:8px 10px;" onchange="location.href=this.value">
          {view_options}
        </select>
      </label>
    </div>
    """

    zip_action = f"/download-zip?token={quote(ACCESS_TOKEN)}"
    selectbar_open = f"""
    <form class="selectbar" id="selectForm" method="POST" action="{zip_action}">
      <span class="muted">Selected: <b id="selCount">0</b></span>
    
      <button class="btn" type="button" onclick="toggleAll(true)">Select all</button>
      <button class="btn" type="button" onclick="toggleAll(false)">Clear</button>
    
      <label class="muted" style="display:flex; align-items:center; gap:8px;">
        Download option:
        <select class="btn" id="dlMode" style="padding:8px 10px;">
          <option value="zip">ZIP (single file)</option>
          <option value="single" selected>One-by-one</option>
        </select>
      </label>
    
      <button class="btn" type="button" onclick="downloadSelected()">⬇ Download selected</button>
    
      <span class="muted">Tip: browser may ask permission for multiple downloads.</span>
    """

    # list directory
    entries = []
    for p in sorted(folder.iterdir(), key=lambda x: (x.is_file(), x.name.lower())):
        try:
            stat = p.stat()
        except OSError:
            continue

        name = p.name
        rel_child = str(p.relative_to(root_path)).replace("\\", "/")
        url_rel = quote(rel_child)
        link = f"/browse/{url_rel}?token={quote(ACCESS_TOKEN)}&view={view}"

        if p.is_dir():
            entries.append({
                "kind": "dir",
                "name": name,
                "link": link,
                "type": "Folder",
                "size": "",
                "rel": rel_child,
                "path": p,
            })
        else:
            mt, _ = mimetypes.guess_type(str(p))
            mt = mt or "application/octet-stream"
            entries.append({
                "kind": "file",
                "name": name,
                "link": link,
                "type": mt,
                "size": format_size(stat.st_size),
                "rel": rel_child,
                "path": p,
            })

    header = f"""
    <h2>{title}</h2>
    <p class="muted">Root: <span class="path">{root_path}</span></p>
    <p class="muted">Current: <span class="path">/{rel_norm}</span></p>
    """

    # View rendering
    if view in (1, 2, 3, 4):
        cell = {1: 260, 2: 190, 3: 140, 4: 120}[view]
        thumb = VIEW_SIZES[view]

        cards = []
        for e in entries:
            if e["kind"] == "dir":
                check = ""
                thumb_html = f"<div class='thumb' style='height:{thumb}px'>📁</div>"
                meta = "Folder"
            else:
                check = f"<input class='check filecheck' type='checkbox' name='files' value='{e['rel']}'>"
                p = e["path"]

                if is_image(p) and Image is not None:
                    tlink = f"/thumb/{quote(e['rel'])}?token={quote(ACCESS_TOKEN)}&s={thumb}"
                    thumb_html = f"<div class='thumb' style='height:{thumb}px'><img loading='lazy' src='{tlink}' alt='thumb'></div>"
                elif is_video(p):
                    vt = f"/vthumb/{quote(e['rel'])}?token={quote(ACCESS_TOKEN)}&s={thumb}"
                    thumb_html = f"<div class='thumb' style='height:{thumb}px'><img loading='lazy' src='{vt}' alt='video thumb'></div>"
                else:
                    thumb_html = f"<div class='thumb' style='height:{thumb}px'>📄</div>"

                meta = f"{e['type']} • {e['size']}"

            cards.append(
                f"""
                <div class="card cardwrap">
                  {check}
                  <a href="{e['link']}" style="display:block">
                    {thumb_html}
                    <div class="name">{'📁 ' if e['kind']=='dir' else ''}{e['name']}</div>
                    <div class="meta">{meta}</div>
                  </a>
                </div>
                """
            )

        body = f"""
        {header}
        {toolbar}
        {selectbar_open}
        <div class="grid" style="--cell:{cell}px; --thumb:{thumb}px;">
          {''.join(cards)}
        </div>
        </form>
        """

    elif view == 5:
        # List view
        items_html = []
        for e in entries:
            if e["kind"] == "dir":
                check = ""
                mini = "<div class='mini'>📁</div>"
                sub = "Folder"
            else:
                check = f"<input class='check filecheck' type='checkbox' name='files' value='{e['rel']}'>"
                p = e["path"]
                if is_image(p) and Image is not None:
                    tlink = f"/thumb/{quote(e['rel'])}?token={quote(ACCESS_TOKEN)}&s=64"
                    mini = f"<div class='mini'><img loading='lazy' src='{tlink}' alt='thumb'></div>"
                elif is_video(p):
                    vt = f"/vthumb/{quote(e['rel'])}?token={quote(ACCESS_TOKEN)}&s=64"
                    mini = f"<div class='mini'><img loading='lazy' src='{vt}' alt='video thumb'></div>"
                else:
                    mini = "<div class='mini'>📄</div>"
                sub = f"{e['type']} • {e['size']}"

            items_html.append(
                f"""
                <div class="list-item">
                  {check}
                  <a style="display:flex; gap:10px; align-items:center; flex:1" href="{e['link']}">
                    {mini}
                    <div>
                      <div class="title">{'📁 ' if e['kind']=='dir' else ''}{e['name']}</div>
                      <div class="sub">{sub}</div>
                    </div>
                  </a>
                </div>
                """
            )

        body = f"""
        {header}
        {toolbar}
        {selectbar_open}
        <div class="list">
          {''.join(items_html)}
        </div>
        </form>
        """

    else:
        # Details view (table)
        row_parts = []
        for e in entries:
            checkbox_html = ""
            icon = "📁 " if e["kind"] == "dir" else "📄 "

            if e["kind"] != "dir":
                checkbox_html = (
                    f"<input class='filecheck' type='checkbox' name='files' value='{e['rel']}'>"
                )

            row_parts.append(
                "<tr>"
                f"<td>{checkbox_html}</td>"
                f"<td><a href='{e['link']}'>{icon}{e['name']}</a></td>"
                f"<td class='muted'>{e['type']}</td>"
                f"<td class='muted'>{e['size']}</td>"
                "</tr>"
            )

        rows = "\n".join(row_parts)

        body = f"""
        {header}
        {toolbar}
        {selectbar_open}
        <table>
          <thead><tr><th></th><th>Name</th><th>Type</th><th>Size</th></tr></thead>
          <tbody>{rows}</tbody>
        </table>
        </form>
        """

    return Response(html_page("Browse", body), mimetype="text/html")


def file_view(rel):
    require_token()
    view = get_view_type()

    fpath = safe_resolve(rel)
    if not fpath.exists() or not fpath.is_file():
        abort(404, "Not found")

    rel_norm = rel.strip("/").replace("\\", "/")
    parent = str(Path(rel_norm).parent).replace("\\", "/")
    parent_link = view_link(parent if parent != "." else "", view)

    download_link = f"/download/{quote(rel_norm)}?token={quote(ACCESS_TOKEN)}"
    raw_link = f"/raw/{quote(rel_norm)}?token={quote(ACCESS_TOKEN)}"

    prev_rel, next_rel = get_prev_next(rel_norm)
    prev_link = f"/browse/{quote(prev_rel)}?token={quote(ACCESS_TOKEN)}&view={view}" if prev_rel else None
    next_link = f"/browse/{quote(next_rel)}?token={quote(ACCESS_TOKEN)}&view={view}" if next_rel else None

    nav_buttons = "<div>"
    nav_buttons += f"<a class='btn' href='{prev_link}'>⬅ Prev</a> " if prev_link else "<span class='muted'>⬅ Prev</span> "
    nav_buttons += f"<a class='btn' href='{next_link}'>Next ➡</a>" if next_link else "<span class='muted'>Next ➡</span>"
    nav_buttons += "</div>"

    size = format_size(fpath.stat().st_size)
    mt, _ = mimetypes.guess_type(str(fpath))
    mt = mt or "application/octet-stream"

    preview_html = ""
    if is_image(fpath):
        if fpath.suffix.lower() in {".heic", ".heif"} and not HEIF_OK:
            preview_html = """
            <div class="preview">
              <h3>Preview (Image)</h3>
              <p class="muted">HEIC/HEIF preview needs: <span class="path">pip install pillow pillow-heif</span></p>
            </div>
            """
        else:
            preview_html = f"""
            <div class="preview">
              <h3>Preview (Image)</h3>
              {nav_buttons}
              <div style="height:10px"></div>
              <img src="{raw_link}" alt="image preview" />
            </div>
            """
    elif is_video(fpath):
        preview_html = f"""
        <div class="preview">
          <h3>Preview (Video)</h3>
          {nav_buttons}
          <div style="height:10px"></div>
          <video controls preload="metadata" src="{raw_link}"></video>
          <p class="muted">If the browser can’t play this format, download it instead.</p>
        </div>
        """
    else:
        preview_html = """
        <div class="preview">
          <p class="muted">No preview available for this file type.</p>
        </div>
        """

    body = f"""
    <p><a class="btn" href="{parent_link}">⬅ Back</a></p>
    <h2>📄 {fpath.name}</h2>
    <p class="muted">Path: <span class="path">/{rel_norm}</span></p>
    <p class="muted">Type: {mt} • Size: {size}</p>

    <p>
      <a class="btn" href="{download_link}">⬇ Download</a>
      <a class="btn" href="{raw_link}" target="_blank">🧾 Open raw</a>
    </p>

    {preview_html}
    """
    return Response(html_page(fpath.name, body), mimetype="text/html")


@app.route("/thumb/<path:rel>")
def thumb(rel):
    """
    Image thumbnail endpoint used by icon/list views.
    Generates a JPEG thumbnail (cached on disk).
    """
    require_token()
    fpath = safe_resolve(rel)
    if not fpath.exists() or not fpath.is_file():
        abort(404, "Not found")

    if not is_image(fpath):
        abort(415, "Not an image")

    try:
        size = int(request.args.get("s", "160"))
    except ValueError:
        size = 160
    size = max(32, min(size, 512))

    ensure_thumb_cache_dir()
    key = cache_key_for_thumb(fpath, size)
    cached = THUMB_CACHE_DIR / f"{key}.jpg"

    if cached.exists():
        return send_file(cached, mimetype="image/jpeg", as_attachment=False)

    try:
        data, mt = generate_thumb_bytes(fpath, size)
    except Exception:
        svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}">
  <rect width="100%" height="100%" fill="#f3f4f6"/>
  <text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" fill="#6b7280"
        font-family="system-ui, Arial" font-size="{max(10, size//10)}">No thumb</text>
</svg>"""
        return Response(svg, mimetype="image/svg+xml")

    try:
        cached.write_bytes(data)
    except Exception:
        pass

    return Response(data, mimetype=mt)


@app.route("/vthumb/<path:rel>")
def vthumb(rel):
    """
    Video thumbnail endpoint (cached on disk).
    """
    require_token()
    fpath = safe_resolve(rel)
    if not fpath.exists() or not fpath.is_file():
        abort(404, "Not found")

    if not is_video(fpath):
        abort(415, "Not a video")

    try:
        size = int(request.args.get("s", "160"))
    except ValueError:
        size = 160
    size = max(32, min(size, 512))

    ensure_thumb_cache_dir()
    key = cache_key_for_vthumb(fpath, size)
    cached = THUMB_CACHE_DIR / f"{key}.jpg"

    if cached.exists():
        return send_file(cached, mimetype="image/jpeg", as_attachment=False)

    try:
        data, mt = generate_video_thumb_bytes(fpath, size)
    except Exception:
        svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}">
  <rect width="100%" height="100%" fill="#f3f4f6"/>
  <text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" fill="#6b7280"
        font-family="system-ui, Arial" font-size="{max(10, size//10)}">No vthumb</text>
</svg>"""
        return Response(svg, mimetype="image/svg+xml")

    try:
        cached.write_bytes(data)
    except Exception:
        pass

    return Response(data, mimetype=mt)


@app.route("/download-zip", methods=["POST"])
def download_zip():
    """
    Disk-backed ZIP (safe for large selections).
    Creates the zip on disk (temp file) and deletes it after the response is sent.
    """
    require_token()

    rels = request.form.getlist("files")
    if not rels:
        abort(400, "No files selected")

    # Create a temp zip file on disk (important for large selections)
    fd, zip_path = tempfile.mkstemp(prefix="selected_", suffix=".zip")
    os.close(fd)  # close the OS handle; ZipFile will open it

    try:
        with zipfile.ZipFile(zip_path, mode="w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as z:
            for rel in rels:
                rel_norm = rel.strip("/").replace("\\", "/")
                fpath = safe_resolve(rel_norm)
                if not fpath.exists() or not fpath.is_file():
                    continue
                z.write(fpath, arcname=rel_norm)
    except Exception:
        # Cleanup if zip creation fails
        try:
            os.remove(zip_path)
        except OSError:
            pass
        raise

    @after_this_request
    def _cleanup(response):
        try:
            os.remove(zip_path)
        except OSError:
            pass
        return response

    return send_file(
        zip_path,
        as_attachment=True,
        download_name="selected_files.zip",
        mimetype="application/zip",
        conditional=True,  # lets Flask support range requests on some setups
    )


@app.route("/download/<path:rel>")
def download(rel):
    require_token()
    fpath = safe_resolve(rel)
    if not fpath.exists() or not fpath.is_file():
        abort(404, "Not found")
    return send_file(fpath, as_attachment=True, download_name=fpath.name)


@app.route("/raw/<path:rel>")
def raw(rel):
    """
    Raw inline viewing.
    If HEIC/HEIF and pillow-heif is available, converts to JPEG for browser viewing.
    Download still returns original via /download.
    """
    require_token()
    fpath = safe_resolve(rel)
    if not fpath.exists() or not fpath.is_file():
        abort(404, "Not found")

    ext = fpath.suffix.lower()
    if ext in {".heic", ".heif"}:
        if not HEIF_OK or Image is None:
            abort(415, "HEIC/HEIF preview requires: pip install pillow pillow-heif")
        with Image.open(fpath) as im:
            if im.mode != "RGB":
                im = im.convert("RGB")
            buf = BytesIO()
            im.save(buf, format="JPEG", quality=90, optimize=True)
            buf.seek(0)
            return send_file(buf, mimetype="image/jpeg", as_attachment=False, download_name=fpath.stem + ".jpg")

    return send_file(fpath, as_attachment=False)


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


if __name__ == "__main__":
    ensure_thumb_cache_dir()
    maintain_thumb_cache(max_age_days=1, max_mb=500)

    print(f"Sharing folder: {root_path}")
    print(f"Open: http://{HOST}:{PORT}/?token={ACCESS_TOKEN}")
    app.run(host=HOST, port=PORT, debug=False)