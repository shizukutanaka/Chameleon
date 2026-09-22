"""GUI-layer contract guards (audit 68).

The ``gui/`` Electron+React scaffold shipped claims and wiring that provably
did not match reality: an entry point that crashed at startup (a ``path``
const used before its ``require``, plus a ``require('electron-is-dev')``
that is not a declared dependency), a spawn target that never existed
(``production_cli.py``), a CLI invocation shape the argparse contract has
never had (``<op> --input <f> --format json``), a TLS certificate bypass,
a menu channel name that never reached the renderer, IPC methods with no
handler, and UI text asserting protections nothing implements.

These guards pin the corrected contracts so none of it quietly returns.
They are stdlib-only: they read the gui sources as text.
"""

import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
GUI = REPO_ROOT / "gui"
ELECTRON_DIR = GUI / "electron"
SRC_DIR = GUI / "src"

# Node.js builtin modules + 'electron' itself: require() targets that do not
# need to live in package.json.
NODE_BUILTINS = {
    "electron", "path", "fs", "os", "child_process", "crypto", "util",
    "events", "stream", "http", "https", "url", "assert", "buffer",
    "querystring", "zlib", "net", "tls", "dns", "dgram", "readline",
    "worker_threads", "perf_hooks", "vm", "module", "process",
}


def _read(path):
    return path.read_text(encoding="utf-8")


def _package_deps():
    pkg = json.loads(_read(GUI / "package.json"))
    deps = set()
    for section in ("dependencies", "devDependencies"):
        deps.update(pkg.get(section, {}))
    return deps


def _bare_requires(js_source):
    """Module names required in a JS file that are not relative paths."""
    names = re.findall(r"require\(\s*['\"]([^'\"]+)['\"]\s*\)", js_source)
    return {n for n in names if not n.startswith(".")}


class TestElectronEntryPoint:
    """main.js must be loadable: every require declared, every preload real."""

    def test_bare_requires_are_declared_or_builtin(self):
        declared = _package_deps()
        for js_file in sorted(ELECTRON_DIR.glob("*.js")):
            for mod in _bare_requires(_read(js_file)):
                assert mod in NODE_BUILTINS or mod in declared, (
                    f"{js_file.name} requires '{mod}' -- neither a Node "
                    f"builtin nor a declared dependency; the entry point "
                    f"crashes on startup when it is not installed"
                )

    def test_every_preload_path_exists(self):
        main = _read(ELECTRON_DIR / "main.js")
        preloads = re.findall(
            r"preload:\s*path\.join\(__dirname,\s*['\"]([^'\"]+)['\"]", main
        )
        assert preloads, "no preload wiring found in main.js"
        for name in preloads:
            assert (ELECTRON_DIR / name).is_file(), (
                f"main.js points a BrowserWindow at preload '{name}' which "
                f"does not exist -- the window renders without the bridge"
            )

    def test_spawned_python_targets_exist(self):
        main = _read(ELECTRON_DIR / "main.js")
        spawned = re.findall(
            r"path\.join\(__dirname,\s*['\"]\.\./\.\./([^'\"]+\.py)['\"]", main
        )
        assert spawned, "main.js spawns no repo script -- wiring disappeared?"
        for rel in spawned:
            assert (REPO_ROOT / rel).is_file(), (
                f"main.js spawns {rel} which does not exist in the repo -- "
                f"the operation it backs always fails"
            )

    def test_cli_invocation_uses_real_contract(self):
        """Spawned argv must match main.py's argparse surface."""
        main = _read(ELECTRON_DIR / "main.js")
        # The pre-fix shape `main.py <op> --input <f> --format json` matched
        # no subcommand or flag in the CLI.
        assert "'--input'" not in main
        assert "'--format', 'json'" not in main
        # Real operations: analyze --export, process --normalize/--convert --json
        assert "'analyze', filePath, '--export'" in main
        assert "'process', '--normalize'" in main
        assert "'process', '--convert'" in main
        assert "'--json'" in main

    def test_no_phantom_backend_references(self):
        main = _read(ELECTRON_DIR / "main.js")
        assert "production_cli.py" not in main
        # Passwords must not ride on argv where `ps` exposes them
        assert "'--password'" not in main


class TestSecurityPosture:
    """Security claims and handlers must reflect what is implemented."""

    def test_invalid_certificates_not_blanket_accepted(self):
        main = _read(ELECTRON_DIR / "main.js")
        assert "app.on('certificate-error'" not in main
        assert 'app.on("certificate-error"' not in main
        # No handler anywhere in electron code opts into bad certs
        for js_file in sorted(ELECTRON_DIR.glob("*.js")):
            assert "callback(true)" not in _read(js_file), (
                f"{js_file.name} accepts an invalid certificate"
            )

    def test_audit_log_directory_created(self):
        main = _read(ELECTRON_DIR / "main.js")
        assert "fs.mkdir(path.dirname(logFile)" in main, (
            "logAuditEvent appends to logs/gui-audit.log without creating "
            "the directory -- logs/ is gitignored, so the append always fails"
        )

    def test_version_comes_from_package_metadata(self):
        main = _read(ELECTRON_DIR / "main.js")
        assert "app.getVersion()" in main
        assert "Version: 1.0.0" not in main


class TestIpcContract:
    """Every exposed invoke must have a handler; menu events must carry
    their channel name to the renderer."""

    def test_every_invoke_has_a_handler(self):
        handlers = set(
            re.findall(r"ipcMain\.handle\(\s*['\"]([^'\"]+)['\"]",
                       _read(ELECTRON_DIR / "main.js"))
        )
        for js_file in sorted(ELECTRON_DIR.glob("*.js")):
            for channel in re.findall(
                r"ipcRenderer\.invoke\(\s*['\"]([^'\"]+)['\"]",
                _read(js_file),
            ):
                assert channel in handlers, (
                    f"{js_file.name} invokes '{channel}' but main.js has no "
                    f"ipcMain.handle for it -- the call always rejects"
                )

    def test_menu_action_forwards_channel_name(self):
        preload = _read(ELECTRON_DIR / "preload.js")
        assert "callback(channel" in preload, (
            "onMenuAction must pass the channel name to the callback -- "
            "ipcRenderer.on delivers (event, ...args), never the channel, "
            "so without it every menu action hits the default case"
        )


class TestRendererContract:
    def test_hash_router_not_browser_router(self):
        app = _read(SRC_DIR / "App.tsx")
        assert "HashRouter" in app
        assert "BrowserRouter as Router" not in app, (
            "BrowserRouter navigates via history.pushState which throws on "
            "file:// (null origin) -- the packaged build's menu is dead"
        )

    def test_menu_actions_navigate(self):
        app = _read(SRC_DIR / "App.tsx")
        for route in ("#/processor", "#/batch", "#/audit", "#/security"):
            assert f"'{route}'" in app, (
                f"handleMenuAction does not navigate to {route} -- the "
                f"corresponding menu item does nothing"
            )

    def test_no_fantasy_operations_offered(self):
        processor = _read(
            SRC_DIR / "components" / "AudioProcessor" / "AudioProcessor.tsx"
        )
        assert 'value="enhance"' not in processor, (
            "'Audio Enhancement' maps to no CLI operation (the fantasy "
            "command was removed from main.py)"
        )
        for fmt in ('value="flac"', 'value="mp3"'):
            assert fmt not in processor, (
                "the backend writes WAV only -- offering this output format "
                "produces nothing"
            )
        for dead in ("enableSIMD", "parallelProcessing"):
            assert dead not in processor, (
                f"{dead} is a switch wired to nothing the backend reads"
            )

    def test_dropzone_accepts_only_wav(self):
        processor = _read(
            SRC_DIR / "components" / "AudioProcessor" / "AudioProcessor.tsx"
        )
        for fmt in (".mp3", ".flac", ".aiff", ".aif"):
            assert f"'{fmt}'" not in processor and f'"{fmt}"' not in processor, (
                f"the dropzone accepts {fmt} but the backend cannot read it"
            )

    def test_simulated_surfaces_are_labelled(self):
        expectations = {
            "Dashboard/Dashboard.tsx": "Simulated data",
            "Security/AuditLog.tsx": "Demo entries",
            "BatchProcessor/BatchProcessor.tsx": "UI preview",
            "System/SystemStatus.tsx": "Design preview",
            "AudioProcessor/AudioProcessor.tsx": "Simulated preview",
        }
        for rel, marker in expectations.items():
            source = _read(SRC_DIR / "components" / rel)
            assert marker in source, (
                f"{rel} shows fabricated values without the '{marker}' "
                f"disclosure -- mock data presented as live"
            )

    def test_mock_result_marked_simulated(self):
        processor = _read(
            SRC_DIR / "components" / "AudioProcessor" / "AudioProcessor.tsx"
        )
        assert "simulated: true" in processor, (
            "the browser fallback builds a fabricated result -- it must "
            "carry the simulated flag the warning banner checks"
        )

    def test_icon_imports_resolve(self):
        """Named MUI icon imports must be real exports -- the scaffold
        imported TuneIcon/AnalyticsIcon/Batch, none of which exist in
        @mui/icons-material@5.x, so the renderer could never compile."""
        processor = _read(
            SRC_DIR / "components" / "AudioProcessor" / "AudioProcessor.tsx"
        )
        layout = _read(SRC_DIR / "components" / "Layout" / "Layout.tsx")
        assert "Tune as TuneIcon" in processor
        assert "Analytics as AnalyticsIcon" in processor
        assert "Layers as BatchIcon" in layout
        for bad in ("  TuneIcon,\n", "  AnalyticsIcon,\n", "Batch as BatchIcon"):
            assert bad not in processor + layout


class TestClaimHonesty:
    """No text in the shipped UI may assert protections that do not exist."""

    FANTASY_CLAIMS = [
        "Government-Grade",
        "RESTRICTED",
        "AES-256",
        "Multi-factor",
        "Authorized Personnel",
        "Classification:",
        "GOVERNMENT USE ONLY",
    ]

    def test_no_classification_or_protection_claims(self):
        offenders = []
        for path in list(GUI.rglob("*.js")) + list(GUI.rglob("*.tsx")) \
                + list(GUI.rglob("*.ts")) + list(GUI.rglob("*.html")) \
                + [GUI / "README.md"]:
            if "node_modules" in path.parts:
                continue
            text = _read(path)
            for claim in self.FANTASY_CLAIMS:
                if claim in text:
                    offenders.append(f"{path.relative_to(GUI)}: {claim!r}")
        assert not offenders, (
            "fantasy security claims remain in the GUI:\n  " + "\n  ".join(offenders)
        )

    def test_hardcoded_status_values_removed(self):
        status = _read(SRC_DIR / "components" / "System" / "SystemStatus.tsx")
        for fake in ("Linux 6.6.87", "Python 3.11.5", '"1.0.0"', "45%", "62%", "78%"):
            assert fake not in status, (
                f"SystemStatus still presents {fake} as a live reading"
            )

    def test_docs_links_resolve_to_real_files(self):
        main = _read(ELECTRON_DIR / "main.js")
        for doc_ref in re.findall(r"\$\{DOCS_BASE_URL\}/([^'\"`]+)", main):
            assert (REPO_ROOT / "docs" / doc_ref).is_file(), (
                f"Help menu links docs/{doc_ref} which does not exist"
            )
