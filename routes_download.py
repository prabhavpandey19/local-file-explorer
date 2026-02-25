import os
import tempfile
import zipfile

from flask import after_this_request, abort, request, send_file

from auth_utils import require_token, safe_resolve
from config import app


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
        with zipfile.ZipFile(
            zip_path,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
            allowZip64=True,
        ) as z:
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

