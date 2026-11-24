# chameleon-accel — optional Rust kernels for the BS.1770 meter

`bs1770_loudness.py` is pure standard-library Python by design (CHARTER.md
§1: the zero-dependency core is the product's differentiator). Its cost is
the sample loops: K-weighting's two biquad passes, the overlapping-block
energy sums, and the 4x-oversampled true-peak scan are all per-sample
Python, which puts a 3-minute mono file's integrated-loudness measurement
in the multi-second range.

This crate re-implements exactly those four primitives in Rust, behind
`accel.py`'s guarded dispatch:

- the native module is **optional** — a normal install never builds or
  ships it, and the pure-Python path is the default and the fallback;
- `CHAMELEON_ACCEL=0` disables it even when built;
- any failure inside a native call degrades to the Python result;
- the kernels are bit-identical to the Python ones (same operand order;
  Neumaier summation matching CPython's float `sum()`; true-peak phases
  are built by Python and passed in as data), so which path ran is
  invisible in the numbers — only in the timing.

## Building

```sh
rust/chameleon-accel/build.sh   # cargo build --release, copies the .so
                                # to the repository root (git-ignored)
```

Requires a Rust toolchain and network access to crates.io for PyO3.
The release artifact is **not** part of the distributed package.
