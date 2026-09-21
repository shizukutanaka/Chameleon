"""BatchProcessor pre-flight must match the contract of the ops it gates.

The batch gate accepted `target_peak=0.0` and `threshold` of 0.0 or 1.0,
then every per-file call failed in normalize()/trim_silence() — the run
"validated" and then produced N identical per-file errors. The gate now
uses the ops' own ranges: (0, 1.0] for target_peak, (0, 1.0) for
threshold — matching the CLI and the API validator.
"""

import core
from tests._helpers import write_sine_wave


def test_batch_rejects_zero_target_peak(tmp_path):
    write_sine_wave(tmp_path / "in.wav", duration=0.05)

    results = core.BatchProcessor().process_directory(
        str(tmp_path), "normalize", target_peak=0.0)

    # Gate rejection is one result naming the parameter, not N per-file
    # "Invalid target peak" echoes.
    assert len(results) == 1
    assert "target_peak" in results[0].message


def test_batch_rejects_threshold_bounds(tmp_path):
    write_sine_wave(tmp_path / "in.wav", duration=0.05)

    for bad in (0.0, 1.0):
        results = core.BatchProcessor().process_directory(
            str(tmp_path), "trim", threshold=bad)

        assert len(results) == 1, f"threshold={bad} leaked past the gate"
        assert "threshold" in results[0].message
