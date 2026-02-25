import mimetypes
from io import BytesIO
from pathlib import Path
from urllib.parse import quote

from flask import Response, abort, send_file

from auth_utils import require_token, safe_resolve
from config import ACCESS_TOKEN, HEIF_OK, Image, app, root_path
from media_utils import format_size, is_image, is_media, is_video
from view_utils import VIEW_LABELS, VIEW_SIZES, get_view_type, html_page, view_link


@app.route("/")
def index():
    require_token()
    return browse("")


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
            entries.append(
                {
                    "kind": "dir",
                    "name": name,
                    "link": link,
                    "type": "Folder",
                    "size": "",
                    "rel": rel_child,
                    "path": p,
                }
            )
        else:
            mt, _ = mimetypes.guess_type(str(p))
            mt = mt or "application/octet-stream"
            entries.append(
                {
                    "kind": "file",
                    "name": name,
                    "link": link,
                    "type": mt,
                    "size": format_size(stat.st_size),
                    "rel": rel_child,
                    "path": p,
                }
            )

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
                check = (
                    f"<input class='check filecheck' type='checkbox' name='files' value='{e['rel']}'>"
                )
                p = e["path"]

                if is_image(p) and Image is not None:
                    tlink = f"/thumb/{quote(e['rel'])}?token={quote(ACCESS_TOKEN)}&s={thumb}"
                    thumb_html = (
                        f"<div class='thumb' style='height:{thumb}px'>"
                        f"<img loading='lazy' src='{tlink}' alt='thumb'></div>"
                    )
                elif is_video(p):
                    vt = f"/vthumb/{quote(e['rel'])}?token={quote(ACCESS_TOKEN)}&s={thumb}"
                    thumb_html = (
                        f"<div class='thumb' style='height:{thumb}px'>"
                        f"<img loading='lazy' src='{vt}' alt='video thumb'></div>"
                    )
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
                check = (
                    f"<input class='check filecheck' type='checkbox' name='files' value='{e['rel']}'>"
                )
                p = e["path"]
                if is_image(p) and Image is not None:
                    tlink = f"/thumb/{quote(e['rel'])}?token={quote(ACCESS_TOKEN)}&s=64"
                    mini = (
                        f"<div class='mini'><img loading='lazy' src='{tlink}' alt='thumb'></div>"
                    )
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
    prev_link = (
        f"/browse/{quote(prev_rel)}?token={quote(ACCESS_TOKEN)}&view={view}"
        if prev_rel
        else None
    )
    next_link = (
        f"/browse/{quote(next_rel)}?token={quote(ACCESS_TOKEN)}&view={view}"
        if next_rel
        else None
    )

    nav_buttons = "<div>"
    nav_buttons += (
        f"<a class='btn' href='{prev_link}'>⬅ Prev</a> "
        if prev_link
        else "<span class='muted'>⬅ Prev</span> "
    )
    nav_buttons += (
        f"<a class='btn' href='{next_link}'>Next ➡</a>"
        if next_link
        else "<span class='muted'>Next ➡</span>"
    )
    nav_buttons += "</div>"

    size = format_size(fpath.stat().st_size)
    mt, _ = mimetypes.guess_type(str(fpath))
    mt = mt or "application/octet-stream"

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
        with Image.open(fpath) as im:  # type: ignore[call-arg]
            if im.mode != "RGB":
                im = im.convert("RGB")
            buf = BytesIO()
            im.save(buf, format="JPEG", quality=90, optimize=True)
            buf.seek(0)
            return send_file(
                buf,
                mimetype="image/jpeg",
                as_attachment=False,
                download_name=fpath.stem + ".jpg",
            )

    return send_file(fpath, as_attachment=False)

