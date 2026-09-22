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


def _call_with_scipy_blocked(expr: str) -> subprocess.CompletedProcess:
    """numpy present, scipy+librosa absent: the module docstring promises a
    clear error at point of use, but the removers used to hit a raw
    NameError on `signal`/`interpolate`/`median_filter` instead."""
    code = textwrap.dedent(
        f"""
        import sys, builtins, warnings
        sys.path.insert(0, {str(REPO_ROOT)!r})
        _real_import = builtins.__import__
        def _blocked(name, *args, **kwargs):
            if name.split('.')[0] in ('scipy', 'librosa'):
                raise ImportError('blocked ' + name)
            return _real_import(name, *args, **kwargs)
        builtins.__import__ = _blocked
        warnings.simplefilter('ignore')

        import numpy as np
        import audio_restoration as m
        assert m.HAS_SCIPY is False, 'HAS_SCIPY should reflect the blocked import'

        try:
            {expr}
        except RuntimeError as exc:
            assert 'extra' in str(exc).lower() or 'requires' in str(exc).lower()
            print('OK')
        else:
            raise SystemExit('expected a RuntimeError when scipy is absent')
        """
    )
    return subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, cwd=str(REPO_ROOT)
    )


import pytest


@pytest.mark.parametrize("expr", [
    "m.ClickRemover().detect_clicks(np.zeros(64), 44100)",
    "m.ClickRemover().remove_clicks(np.zeros(64), 44100)",
    "m.CrackleRemover().remove_crackle(np.zeros(64), 44100)",
    "m.HumRemover().remove_hum(np.zeros(64), 44100)",
    "m.DeclippingProcessor().detect_clipping(np.zeros(64))",
    "m.DeclippingProcessor().restore_clipped(np.zeros(64), 44100)",
    "m.VinylRestorer().restore(np.zeros(64), 44100)",
])
def test_restoration_methods_raise_clear_error_without_scipy(expr):
    pytest.importorskip("numpy")  # needs real numpy to reach the scipy use
    result = _call_with_scipy_blocked(expr)
    assert result.returncode == 0 and "OK" in result.stdout, result.stderr
