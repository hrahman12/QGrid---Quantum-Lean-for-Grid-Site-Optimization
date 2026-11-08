"""Write ui/index.offline.html: the same page, openable by double-click (file://) with no server and no network.

ui/index.html's import map points at ./vendor/*.js. That works over http (python -m http.server), but browsers
refuse to load ES-module FILES from file:// (origin null). This copies index.html and points the import map at
data: URLs built from the vendored three.js in ui/vendor/ instead. Relative imports inside the addons
('./Pass.js', '../shaders/CopyShader.js') can't resolve against a data: URL, so they are rewritten to bare
'three/addons/<path>' specifiers defined by the same map. Data comes from the inline copy in the page.
Re-run after rebuilding index.html or the vendored files:  python ui/build_offline.py
"""
import base64
import json
import re
from pathlib import Path, PurePosixPath

UI = Path(__file__).resolve().parent
VENDOR = UI / "vendor"
SRC, OUT = UI / "index.html", UI / "index.offline.html"


def norm(p):
    out = []
    for seg in p.split("/"):
        if seg == "..":
            out.pop()
        elif seg not in (".", ""):
            out.append(seg)
    return "/".join(out)


def data_url(src):
    return "data:text/javascript;base64," + base64.b64encode(src.encode("utf-8")).decode("ascii")


def main():
    imports = {"three": data_url((VENDOR / "three.module.js").read_text(encoding="utf-8"))}
    jsm = VENDOR / "jsm"
    for f in sorted(jsm.rglob("*.js")):
        rel = f.relative_to(jsm).as_posix()
        base = PurePosixPath(rel).parent.as_posix()
        src = re.sub(r"""((?:from|import)\s*['"])(\.{1,2}/[^'"]+)(['"])""",
                     lambda m: m.group(1) + "three/addons/" + norm(f"{base}/{m.group(2)}") + m.group(3),
                     f.read_text(encoding="utf-8"))
        imports[f"three/addons/{rel}"] = data_url(src)
    block = '<script type="importmap">\n' + json.dumps({"imports": imports}) + "\n</script>"
    html = SRC.read_text(encoding="utf-8")
    new, n = re.subn(r'<script type="importmap">.*?</script>', lambda _: block, html, count=1, flags=re.S)
    if n != 1:
        raise SystemExit("no importmap block found in ui/index.html")
    OUT.write_text(new, encoding="utf-8")
    print(f"wrote {OUT.relative_to(UI.parent)}: {len(imports)} modules embedded, {len(new) // 1024} KB")


if __name__ == "__main__":
    main()
