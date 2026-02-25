import os
import mimetypes
from pathlib import Path
from urllib.parse import quote

from flask import Flask, abort, request, send_file, Response

# ----------------------------
# CONFIG
# ----------------------------
ROOT_DIR = r"D:\Ring ceremony photos"   # <-- change this to the folder you want to share
HOST = "0.0.0.0"         # use 0.0.0.0 to allow other devices on your LAN
PORT = 8000
ACCESS_TOKEN = "pandey-9999" # <-- set a strong token

# ----------------------------
# APP
# ----------------------------
app = Flask(__name__)
root_path = Path(ROOT_DIR).resolve()

MEDIA_EXTS_IMG = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}
MEDIA_EXTS_VID = {".mp4", ".webm", ".ogg", ".mov", ".m4v", ".mkv", ".avi"}  # browser support varies

def is_media(p: Path) -> bool:
    ext = p.suffix.lower()
    return ext in MEDIA_EXTS_IMG or ext in MEDIA_EXTS_VID or is_image(p) or is_video(p)

def get_prev_next(rel_file: str):
    """
    Given a file relative path, return (prev_rel, next_rel) among media files in same folder.
    """
    rel_norm = rel_file.strip("/").replace("\\", "/")
    fpath = safe_resolve(rel_norm)
    folder = fpath.parent

    # collect media files in this folder
    media_files = []
    for p in folder.iterdir():
        if p.is_file() and is_media(p):
            media_files.append(p)

    # stable ordering
    media_files.sort(key=lambda x: x.name.lower())

    # find index
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


def require_token():
    # Token via query param ?token=... or header X-Token: ...
    token = request.args.get("token") or request.headers.get("X-Token")
    if ACCESS_TOKEN and token != ACCESS_TOKEN:
        abort(403, "Forbidden: invalid or missing token")

def safe_resolve(rel: str) -> Path:
    """
    Resolve a user-provided relative path safely within ROOT_DIR
    (prevents ../ traversal).
    """
    rel = rel.lstrip("/").replace("\\", "/")
    target = (root_path / rel).resolve()
    if root_path not in target.parents and target != root_path:
        abort(403, "Forbidden: path outside shared root")
    return target

def is_video(p: Path) -> bool:
    mt, _ = mimetypes.guess_type(str(p))
    return (mt or "").startswith("video/")

def is_image(p: Path) -> bool:
    mt, _ = mimetypes.guess_type(str(p))
    return (mt or "").startswith("image/")

def html_page(title: str, body: str) -> str:
    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>{title}</title>
  <style>
    body {{ font-family: system-ui, Arial, sans-serif; margin: 16px; }}
    a {{ text-decoration: none; }}
    .path {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ padding: 10px; border-bottom: 1px solid #eee; text-align: left; }}
    .muted {{ color: #666; }}
    .preview {{ margin-top: 16px; }}
    img {{ max-width: 100%; height: auto; border: 1px solid #eee; border-radius: 8px; }}
    video {{ max-width: 100%; border: 1px solid #eee; border-radius: 8px; }}
    .btn {{ display:inline-block; padding:8px 12px; border:1px solid #ddd; border-radius:10px; }}
  </style>
</head>
<body>
  {body}
</body>
</html>"""

def format_size(num: int) -> str:
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if num < 1024:
            return f"{num:.0f} {unit}" if unit == "B" else f"{num:.1f} {unit}"
        num /= 1024
    return f"{num:.1f} PB"

@app.route("/")
def index():
    require_token()
    return browse("")

@app.route("/browse/<path:rel>")
def browse(rel):
    require_token()
    folder = safe_resolve(rel)

    if not folder.exists():
        abort(404, "Not found")
    if folder.is_file():
        return file_view(rel)

    # list directory
    items = []
    for p in sorted(folder.iterdir(), key=lambda x: (x.is_file(), x.name.lower())):
        try:
            stat = p.stat()
        except OSError:
            continue

        name = p.name
        rel_child = str(p.relative_to(root_path)).replace("\\", "/")
        url_rel = quote(rel_child)

        if p.is_dir():
            link = f"/browse/{url_rel}?token={quote(ACCESS_TOKEN)}"
            items.append((f"📁 {name}", link, "Folder", ""))
        else:
            link = f"/browse/{url_rel}?token={quote(ACCESS_TOKEN)}"
            mt, _ = mimetypes.guess_type(str(p))
            mt = mt or "application/octet-stream"
            items.append((f"📄 {name}", link, mt, format_size(stat.st_size)))

    # parent link
    rel_norm = rel.strip("/")
    if rel_norm:
        parent = str(Path(rel_norm).parent).replace("\\", "/")
        parent_link = f"/browse/{quote(parent)}?token={quote(ACCESS_TOKEN)}" if parent != "." else f"/?token={quote(ACCESS_TOKEN)}"
        up = f'<p><a class="btn" href="{parent_link}">⬅ Up</a></p>'
    else:
        up = ""

    rows = "\n".join(
        f"<tr><td><a href='{link}'>{name}</a></td><td class='muted'>{typ}</td><td class='muted'>{size}</td></tr>"
        for name, link, typ, size in items
    )

    body = f"""
    <h2>Local File Browser</h2>
    <p class="muted">Root: <span class="path">{root_path}</span></p>
    <p class="muted">Current: <span class="path">/{rel_norm}</span></p>
    {up}
    <table>
      <thead><tr><th>Name</th><th>Type</th><th>Size</th></tr></thead>
      <tbody>{rows}</tbody>
    </table>
    """
    return Response(html_page("Browse", body), mimetype="text/html")

def file_view(rel):
    require_token()
    fpath = safe_resolve(rel)
    if not fpath.exists() or not fpath.is_file():
        abort(404, "Not found")

    rel_norm = rel.strip("/").replace("\\", "/")
    parent = str(Path(rel_norm).parent).replace("\\", "/")
    parent_link = f"/browse/{quote(parent)}?token={quote(ACCESS_TOKEN)}" if parent != "." else f"/?token={quote(ACCESS_TOKEN)}"

    download_link = f"/download/{quote(rel_norm)}?token={quote(ACCESS_TOKEN)}"
    raw_link = f"/raw/{quote(rel_norm)}?token={quote(ACCESS_TOKEN)}"

    # NEXT / PREV among media in same folder
    prev_rel, next_rel = get_prev_next(rel_norm)
    prev_link = f"/browse/{quote(prev_rel)}?token={quote(ACCESS_TOKEN)}" if prev_rel else None
    next_link = f"/browse/{quote(next_rel)}?token={quote(ACCESS_TOKEN)}" if next_rel else None

    nav_buttons = "<div>"
    if prev_link:
        nav_buttons += f"<a class='btn' href='{prev_link}'>⬅ Prev</a> "
    else:
        nav_buttons += "<span class='muted'>⬅ Prev</span> "

    if next_link:
        nav_buttons += f"<a class='btn' href='{next_link}'>Next ➡</a>"
    else:
        nav_buttons += "<span class='muted'>Next ➡</span>"
    nav_buttons += "</div>"

    preview_html = ""
    if is_image(fpath):
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
        preview_html = f"""
        <div class="preview">
          <p class="muted">No preview available for this file type.</p>
        </div>
        """

    size = format_size(fpath.stat().st_size)
    mt, _ = mimetypes.guess_type(str(fpath))
    mt = mt or "application/octet-stream"

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

@app.route("/download/<path:rel>")
def download(rel):
    require_token()
    fpath = safe_resolve(rel)
    if not fpath.exists() or not fpath.is_file():
        abort(404, "Not found")
    return send_file(fpath, as_attachment=True, download_name=fpath.name)

@app.route("/raw/<path:rel>")
def raw(rel):
    require_token()
    fpath = safe_resolve(rel)
    if not fpath.exists() or not fpath.is_file():
        abort(404, "Not found")
    # For previews / inline viewing
    return send_file(fpath, as_attachment=False)

if __name__ == "__main__":
    print(f"Sharing folder: {root_path}")
    print(f"Open: http://{HOST}:{PORT}/?token={ACCESS_TOKEN}")
    app.run(host=HOST, port=PORT, debug=False)
