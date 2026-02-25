from urllib.parse import quote

from flask import request

from config import ACCESS_TOKEN

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

