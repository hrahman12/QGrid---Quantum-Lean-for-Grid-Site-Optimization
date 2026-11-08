"""Embed the vendored three.js (ui/vendor/three@0.160.0/) into ui/index.html so the page opens offline from file://.

Browsers refuse to load ES-module FILES from file:// (origin null), so the import map points every module at a
data: URL instead. Relative imports inside the addons ('./Pass.js', '../shaders/CopyShader.js') can't resolve
against a data: URL, so they are rewritten to bare 'three/addons/<path>' specifiers that the same map defines.
Idempotent: re-run after changing the vendored files. Usage: python ui/build_offline.py
"""
import base64
import json
import re
from pathlib import PurePosixPath, Path

UI = Path(__file__).resolve().parent
VENDOR = UI / "vendor" / "three@0.160.0"
INDEX = UI / "index.html"


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
    imports = {"three": data_url((VENDOR / "build" / "three.module.js").read_text(encoding="utf-8"))}
    jsm = VENDOR / "examples" / "jsm"
    for f in sorted(jsm.rglob("*.js")):
        rel = f.relative_to(jsm).as_posix()
        src = f.read_text(encoding="utf-8")

        def fix(m, base=PurePosixPath(rel).parent.as_posix()):
            return m.group(1) + "three/addons/" + norm(f"{base}/{m.group(2)}") + m.group(3)

        src = re.sub(r"""((?:from|import)\s*['"])(\.{1,2}/[^'"]+)(['"])""", fix, src)
        imports[f"three/addons/{rel}"] = data_url(src)
    block = '<script type="importmap">\n' + json.dumps({"imports": imports}) + "\n</script>"
    html = INDEX.read_text(encoding="utf-8")
    new, n = re.subn(r'<script type="importmap">.*?</script>', lambda _: block, html, count=1, flags=re.S)
    if n != 1:
        raise SystemExit("no importmap block found in ui/index.html")
    INDEX.write_text(new, encoding="utf-8")
    print(f"embedded {len(imports)} modules from {VENDOR.relative_to(UI.parent)}; index.html {len(new) // 1024} KB")


if __name__ == "__main__":
    main()
