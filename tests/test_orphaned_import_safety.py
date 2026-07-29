"""Import-safety for the orphaned numpy/scipy modules (PRODUCT_ANALYSIS.md P1).

`spectral_editor` and `audio_restoration` are not wired into the CLI, but they
are packaged, so `import`ing them must not break the stdlib-only default
install. They previously did unconditional top-level `import numpy` /
`from scipy import ...`, which raised ModuleNotFoundError on an interpreter
without those extras. The imports are now guarded; these tests prove it by
blocking numpy/scipy in a subprocess (so they hold whether or not the test
environment happens to have numpy installed).
"""

import subprocess
import sys
import textwrap
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _import_with_numpy_scipy_blocked(module: str, ctor: str) -> subprocess.CompletedProcess:
    code = textwrap.dedent(
        f"""
        import sys, builtins, warnings
        sys.path.insert(0, {str(REPO_ROOT)!r})
        _real_import = builtins.__import__
        def _blocked(name, *args, **kwargs):
            if name.split('.')[0] in ('numpy', 'scipy'):
                raise ImportError('blocked ' + name)
            return _real_import(name, *args, **kwargs)
        builtins.__import__ = _blocked
        warnings.simplefilter('ignore')

        import {module} as m                # must NOT raise despite blocked deps
        assert m.HAS_NUMPY is False, 'HAS_NUMPY should reflect the blocked import'

        try:
            m.{ctor}()                       # numpy-dependent entry point
        except RuntimeError as exc:          # clear, actionable error (not NameError)
            assert 'install' in str(exc).lower() or 'extra' in str(exc).lower()
            print('OK')
        else:
            raise SystemExit('expected a RuntimeError when numpy/scipy are absent')
        """
    )
    return subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, cwd=str(REPO_ROOT)
    )


def test_spectral_editor_imports_without_numpy():
    result = _import_with_numpy_scipy_blocked("spectral_editor", "SpectralEditor")
    assert result.returncode == 0 and "OK" in result.stdout, result.stderr


def test_audio_restoration_imports_without_numpy_scipy():
    result = _import_with_numpy_scipy_blocked("audio_restoration", "AudioRestorer")
    assert result.returncode == 0 and "OK" in result.stdout, result.stderr


def test_modules_import_cleanly_in_this_environment():
    # A plain import must succeed here too (deps present or not).
    import audio_restoration  # noqa: F401
    import spectral_editor  # noqa: F401
