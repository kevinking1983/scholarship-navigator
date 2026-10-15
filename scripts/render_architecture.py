"""Render deck/architecture.mmd -> deck/architecture.png using Playwright + Mermaid (CDN).
Falls back to a hand-built SVG of the same pipeline if the CDN is unreachable.
    python scripts/render_architecture.py
"""
from __future__ import annotations
import json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MMD = os.path.join(ROOT, "deck", "architecture.mmd")
OUT = os.path.join(ROOT, "deck", "architecture.png")
FALLBACK_SVG = os.path.join(ROOT, "deck", "architecture-fallback.svg")

def chromium_kwargs() -> dict:
    """Use the pre-installed Chromium when the pip Playwright version expects a different build (never run `playwright install`)."""
    for cand in (os.environ.get("CHROMIUM_PATH"), "/opt/pw-browsers/chromium",
                 "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"):
        if cand and os.path.isfile(cand) and os.access(cand, os.X_OK):
            return {"executable_path": cand}
    return {}


def main() -> int:
    from playwright.sync_api import sync_playwright
    code = open(MMD, encoding="utf-8").read()
    html = f"""<!doctype html><html><body style="margin:0;background:#fff">
    <pre class="mermaid" id="d">{code.replace('<','&lt;')}</pre>
    <script type="module">
      import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs';
      mermaid.initialize({{startOnLoad:false, theme:'base', themeVariables:{{primaryColor:'#e8efff',primaryBorderColor:'#1d4ed8',lineColor:'#475569',fontFamily:'system-ui'}}, flowchart:{{htmlLabels:true, curve:'basis', nodeSpacing:30, rankSpacing:40}}}});
      try {{ await mermaid.run({{nodes:[document.getElementById('d')]}}); window.__ok = true; }} catch(e) {{ window.__err = String(e); }}
    </script></body></html>"""
    with sync_playwright() as p:
        b = p.chromium.launch(**chromium_kwargs()); pg = b.new_page(viewport={"width": 1800, "height": 1000}, device_scale_factor=2)
        pg.set_content(html, wait_until="networkidle")
        try:
            pg.wait_for_function("window.__ok === true || window.__err", timeout=30000)
            ok = pg.evaluate("window.__ok === true")
        except Exception:
            ok = False
        if ok:
            svg = pg.locator("svg").first
            svg.screenshot(path=OUT)
            open(os.path.join(ROOT, "deck", "architecture.svg"), "w", encoding="utf-8").write(pg.evaluate("document.querySelector('svg').outerHTML"))
            print("rendered with mermaid ->", os.path.relpath(OUT, ROOT))
        else:
            print("mermaid unavailable (", pg.evaluate("window.__err || 'timeout'"), ") -> using fallback SVG")
            pg.goto("file://" + FALLBACK_SVG); pg.wait_for_timeout(300)
            pg.locator("svg").first.screenshot(path=OUT)
            print("rendered fallback ->", os.path.relpath(OUT, ROOT))
        b.close()
    return 0

if __name__ == "__main__":
    sys.exit(main())
