"""
Prototype B, step 1: VALIDATION on a known planet host (TOI 700 = TIC 150428135).

Pipeline: download TESS PDCSAP light curves from MAST -> stitch -> remove
outliers -> flatten (detrend) -> Box Least Squares period search (astropy).

Goal: recover one of TOI 700's known transiting planets and compare the
recovered period against the published period. This validates the pipeline
before it is pointed at anything unknown.

Known TOI 700 planets (published values, for comparison only):
  b: P = 9.977 d | c: P = 16.051 d | d: P = 37.424 d | e: P = 27.81 d

Everything produced here is labeled as a recovered known signal or a
candidate signal needing professional follow-up. No new discovery is claimed.
"""

import numpy as np
import time

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from lightkurve import search_lightcurve
from astropy.timeseries import BoxLeastSquares

TARGET = "TIC 150428135"  # TOI 700
KNOWN_PERIODS = {"b": 9.977, "c": 16.051, "d": 37.424, "e": 27.81}
OUT_PLOT = "toi700_validation_fold.png"


def robust_search(*args, **kwargs):
    """MAST goes through a flaky egress proxy; retry with backoff."""
    last = None
    for attempt in range(1, 7):
        try:
            return search_lightcurve(*args, **kwargs)
        except Exception as exc:
            last = exc
            print(f"MAST search attempt {attempt} failed "
                  f"({type(exc).__name__}), retrying...")
            time.sleep(8 * attempt)
    raise last


def main():
    print("Searching MAST for TESS light curves of", TARGET)
    sr = robust_search(TARGET, mission="TESS", author="SPOC")
    print(sr)
    if len(sr) == 0:
        raise SystemExit("No TESS light curves found for target.")

    # Keep runtime sane: first 4 sectors is plenty to recover a transit.
    sectors = sr[:4]
    lcs = None
    for attempt in range(1, 6):
        try:
            lcs = sectors.download_all()
            break
        except Exception as exc:
            print(f"download attempt {attempt} failed "
                  f"({type(exc).__name__}), retrying...")
            time.sleep(8 * attempt)
    if lcs is None:
        raise SystemExit("Light curve downloads failed.")
    lc = lcs.stitch().remove_nans()
    lc = lc.remove_outliers(sigma=5)
    print(f"Stitched light curve: {len(lc)} cadences, "
          f"time span {lc.time.value.min():.1f} to {lc.time.value.max():.1f} (BTJD)")

    flat, trend = lc.flatten(window_length=1001, return_trend=True)

    print("Running Box Least Squares...")
    bls = BoxLeastSquares(flat.time.value, flat.flux.value)
    periods = np.linspace(1.0, 40.0, 20000)
    durations = np.linspace(0.05, 0.5, 10)
    res = bls.power(periods, durations, oversample=10)

    best = int(np.argmax(res.power))
    p_best = float(res.period[best])
    d_best = float(res.duration[best])
    t0_best = float(res.transit_time[best])
    depth_best = float(res.depth[best])
    power_best = float(res.power[best])
    print(f"Best BLS signal: P={p_best:.4f} d, duration={d_best:.3f} d, "
          f"depth={depth_best*1e6:.0f} ppm, power={power_best:.3f}")

    # Match against known planets (allow 1 percent tolerance, plus harmonics).
    match = None
    for name, p_true in KNOWN_PERIODS.items():
        for ratio in (1.0, 0.5, 2.0):
            if abs(p_best - p_true * ratio) / (p_true * ratio) < 0.01:
                match = (name, p_true, ratio)
                break
        if match:
            break

    if match:
        name, p_true, ratio = match
        err_pct = abs(p_best - p_true * ratio) / (p_true * ratio) * 100
        print(f"RECOVERED: matches TOI 700 {name} (P_true={p_true} d, "
              f"harmonic ratio {ratio}), period error {err_pct:.3f} percent")
    else:
        print("No match to a known TOI 700 planet within 1 percent "
              "(check harmonics manually).")

    # Folded light-curve plot.
    fold = flat.fold(period=p_best, epoch_time=t0_best)
    binned = fold.bin(time_bin_size=0.02)

    fig, axes = plt.subplots(2, 1, figsize=(10, 7),
                             gridspec_kw={"height_ratios": [3, 1]})
    axes[0].scatter(fold.time.value, fold.flux.value, s=2, alpha=0.25,
                    color="steelblue", label="detrended flux")
    axes[0].scatter(binned.time.value, binned.flux.value, s=14,
                    color="darkred", label="binned")
    axes[0].set_xlim(-0.5 * p_best, 0.5 * p_best)
    axes[0].set_xlabel("phase (days)")
    axes[0].set_ylabel("normalized flux")
    axes[0].set_title(
        f"TOI 700: folded light curve at recovered P={p_best:.4f} d "
        f"(candidate signal, needs professional follow-up)")
    axes[0].legend(loc="best", fontsize=9)
    axes[0].grid(alpha=0.3)

    axes[1].plot(res.period, res.power, color="black", lw=0.7)
    axes[1].axvline(p_best, color="darkred", ls="--", lw=1)
    axes[1].set_xlabel("period (days)")
    axes[1].set_ylabel("BLS power")
    axes[1].set_xlim(1, 40)
    axes[1].grid(alpha=0.3)

    fig.tight_layout()
    fig.savefig(OUT_PLOT, dpi=150)
    print("Saved", OUT_PLOT)


if __name__ == "__main__":
    main()
