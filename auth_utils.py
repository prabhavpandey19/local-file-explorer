from pathlib import Path

from flask import abort, request

from config import ACCESS_TOKEN, root_path


def require_token() -> None:
    token = request.args.get("token") or request.headers.get("X-Token")
    if ACCESS_TOKEN and token != ACCESS_TOKEN:
        abort(403, "Forbidden: invalid or missing token")


def safe_resolve(rel: str) -> Path:
    rel = rel.lstrip("/").replace("\\", "/")
    target = (root_path / rel).resolve()
    if root_path not in target.parents and target != root_path:
        abort(403, "Forbidden: path outside shared root")
    return target

