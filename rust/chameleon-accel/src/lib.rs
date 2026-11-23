//! Optional Rust kernels for Chameleon's BS.1770 loudness meter.
//!
//! These functions re-implement the sample-loop primitives of
//! `bs1770_loudness.py` operation-for-operation, so the results are
//! bit-identical to the pure-Python path:
//!
//! * the biquad recurrence is evaluated in the same operand order
//!   (IEEE-754 double arithmetic is deterministic given the order);
//! * block energies use Neumaier compensated summation, the exact
//!   algorithm CPython 3.12's built-in `sum()` applies to floats, so a
//!   Rust block sum rounds identically to the Python one;
//! * the true-peak phases are *built by Python* (its libm `sin`/`cos`
//!   may differ from Rust's in the last ulp) and passed in as data --
//!   this code only multiplies and accumulates them in Python's order.
//!
//! All gating, percentile and log-conversion semantics stay in Python.
//! Nothing here is reachable unless `accel.py` found this module and
//! the caller kept the result; any failure degrades to the Python path.

use pyo3::prelude::*;

/// Neumaier (improved Kahan) summation, mirroring CPython's float `sum()`.
fn neumaier_sum_of_squares(values: &[f64]) -> f64 {
    let mut result = 0.0f64;
    let mut comp = 0.0f64;
    for &s in values {
        let x = s * s;
        let t = result + x;
        if result.abs() >= x.abs() {
            comp += (result - t) + x;
        } else {
            comp += (x - t) + result;
        }
        result = t;
    }
    result + comp
}

fn apply_biquad(samples: &[f64], coeffs: (f64, f64, f64, f64, f64), out: &mut [f64]) {
    let (b0, b1, b2, a1, a2) = coeffs;
    let mut x1 = 0.0f64;
    let mut x2 = 0.0f64;
    let mut y1 = 0.0f64;
    let mut y2 = 0.0f64;
    for (i, &x0) in samples.iter().enumerate() {
        let y0 = b0 * x0 + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2;
        out[i] = y0;
        x2 = x1;
        x1 = x0;
        y2 = y1;
        y1 = y0;
    }
}

/// Two-stage K-weighting: stage 1 then stage 2, both direct-form-1
/// biquads with coefficients computed by Python (BS.1770-4 Annex 1).
#[pyfunction]
fn k_weight(
    samples: Vec<f64>,
    stage1: (f64, f64, f64, f64, f64),
    stage2: (f64, f64, f64, f64, f64),
) -> Vec<f64> {
    let mut first = vec![0.0f64; samples.len()];
    apply_biquad(&samples, stage1, &mut first);
    let mut second = vec![0.0f64; samples.len()];
    apply_biquad(&first, stage2, &mut second);
    second
}

/// Mean-square energy per overlapping block (Python `_block_mean_squares`).
#[pyfunction]
fn block_mean_squares(weighted: Vec<f64>, block_size: usize, hop: usize) -> Vec<f64> {
    if weighted.len() < block_size || block_size == 0 || hop == 0 {
        return Vec::new();
    }
    let mut blocks = Vec::new();
    let mut start = 0usize;
    while start + block_size <= weighted.len() {
        let block = &weighted[start..start + block_size];
        blocks.push(neumaier_sum_of_squares(block) / block_size as f64);
        start += hop;
    }
    blocks
}

/// Per-block energy summed across channels (Python
/// `_block_summed_mean_squares` with explicit weights).
#[pyfunction]
fn block_summed_mean_squares(
    channels: Vec<Vec<f64>>,
    weights: Vec<f64>,
    block_size: usize,
    hop: usize,
) -> Vec<f64> {
    if channels.is_empty() || block_size == 0 || hop == 0 {
        return Vec::new();
    }
    let length = channels.iter().map(|c| c.len()).min().unwrap_or(0);
    if length < block_size {
        return Vec::new();
    }
    let mut blocks = Vec::new();
    let mut start = 0usize;
    while start + block_size <= length {
        let mut total = 0.0f64;
        for (weight, channel) in weights.iter().zip(channels.iter()) {
            if *weight == 0.0 {
                continue;
            }
            let block = &channel[start..start + block_size];
            // Python evaluates `weight * sum / block_size` left-to-right:
            // (weight * sum) / block_size. Keep that exact order.
            total += weight * neumaier_sum_of_squares(block) / block_size as f64;
        }
        blocks.push(total);
        start += hop;
    }
    blocks
}

/// Maximum absolute value of the oversampled reconstruction (Python
/// `_oversampled_abs_peak`). `phases` are the (offset, coefficient)
/// pairs built by Python's `_build_polyphase_sinc`, passed as data.
#[pyfunction]
fn oversampled_abs_peak(samples: Vec<f64>, phases: Vec<Vec<(i64, f64)>>) -> f64 {
    let n = samples.len();
    if n == 0 {
        return 0.0;
    }
    let mut peak = 0.0f64;
    for i in 0..n as i64 {
        for phase in &phases {
            let mut acc = 0.0f64;
            for &(k, c) in phase {
                let j = i + k;
                if j >= 0 && (j as usize) < n {
                    acc += samples[j as usize] * c;
                }
            }
            let a = if acc >= 0.0 { acc } else { -acc };
            if a > peak {
                peak = a;
            }
        }
    }
    peak
}

#[pymodule]
fn _chameleon_accel(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(k_weight, m)?)?;
    m.add_function(wrap_pyfunction!(block_mean_squares, m)?)?;
    m.add_function(wrap_pyfunction!(block_summed_mean_squares, m)?)?;
    m.add_function(wrap_pyfunction!(oversampled_abs_peak, m)?)?;
    Ok(())
}
