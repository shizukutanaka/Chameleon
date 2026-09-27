"""The gui/ tree must carry the CRA tsconfig or `npm run build` cannot
resolve any .tsx import at all — verified empirically: without it the
build dies at `Module not found: Can't resolve './App'` before reaching a
single type check. The file was simply never committed; CRA only
auto-generates it for `npm start`, not for `npm run build`.
"""

import json
from pathlib import Path

GUI_DIR = Path(__file__).resolve().parent.parent / "gui"


def test_gui_tsconfig_exists():
    tsconfig = GUI_DIR / "tsconfig.json"
    assert tsconfig.is_file(), (
        "gui/tsconfig.json is missing — react-scripts build cannot resolve "
        ".tsx modules without it (fails on `import App from './App'`)"
    )


def test_gui_tsconfig_is_cra_compatible():
    opts = json.loads((GUI_DIR / "tsconfig.json").read_text())["compilerOptions"]
    # CRA's webpack/babel needs exactly these to compile src/*.tsx.
    assert opts["jsx"] == "react-jsx"
    assert opts["isolatedModules"] is True
    assert opts["noEmit"] is True
    assert "src" in json.loads((GUI_DIR / "tsconfig.json").read_text())["include"]
