if __name__ == "__main__":
    from config import ACCESS_TOKEN, HOST, PORT, app, root_path
    from routes_browse import index as _  # noqa: F401  (ensure routes are registered)
    from routes_download import download as _download  # noqa: F401
    from routes_thumbs import thumb as _thumb  # noqa: F401
    from thumb_cache import ensure_thumb_cache_dir, maintain_thumb_cache

    ensure_thumb_cache_dir()
    maintain_thumb_cache(max_age_days=1, max_mb=500)

    print(f"Sharing folder: {root_path}")
    print(f"Open: http://{HOST}:{PORT}/?token={ACCESS_TOKEN}")
    app.run(host=HOST, port=PORT, debug=False)