from flask import Response, abort, request, send_file

from auth_utils import require_token, safe_resolve
from config import app
from media_utils import generate_thumb_bytes, generate_video_thumb_bytes, is_image, is_video
from thumb_cache import cache_key_for_thumb, cache_key_for_vthumb, ensure_thumb_cache_dir
from config import THUMB_CACHE_DIR


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

