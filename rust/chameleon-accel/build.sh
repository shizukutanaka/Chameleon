#!/bin/sh
# Build the optional Rust accelerator and place it at the repository root
# as _chameleon_accel.so (git-ignored via *.so; the package works without
# it -- see accel.py). Usage: rust/chameleon-accel/build.sh
set -eu
cd "$(dirname "$0")"
cargo build --release
cp target/release/lib_chameleon_accel.so ../../_chameleon_accel.so
echo "installed: _chameleon_accel.so"
