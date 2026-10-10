"""
Prototype B, step 2: BATCH CANDIDATE SCAN.

Runs the same flatten + Box Least Squares pipeline from validate_toi700.py
over a small batch of TESS Objects of Interest (TOIs) and ranks the most
planet-like signals by BLS power, transit depth, and an SNR estimate.

Output:
  - candidate_shortlist.csv : one row per target with best-signal metrics
  - top3_<tic>_fold.png     : folded light-curve plots for the top 3 signals

IMPORTANT: every signal here is labeled a CANDIDATE SIGNAL that needs
professional follow-up. Nothing here is a planet discovery. Most BLS
detections in real data are false positives (eclipsing binaries, stellar
variability, systematics). See SUMMARY.md for limitations.
"""

import os
import time
import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from lightkurve import search_lightcurve
from astropy.timeseries import BoxLeastSquares

# A mix of confirmed-planet hosts and TOI candidates. TIC IDs are used
# because they are unambiguous in the MAST archive.
TARGETS = [
    ("TIC 150428135", "TOI 700"),    # validated in step 1
    ("TIC 259377017", "TOI 270"),
    ("TIC 251848941", "TOI 178"),
    ("TIC 183985250", "TOI 849"),
    ("TIC 260128333", "TOI 1338"),   # circumbinary system
    ("TIC 55652896",  "TOI 216"),
    ("TIC 52368076",  "TOI 125"),
    ("TIC 307210830", "TOI 776"),
]

MAX_SECTORS = 2          # keep downloads small; enough for a prototype scan
PERIOD_MIN, PERIOD_MAX = 0.5, 30.0
N_PERIODS = 12000


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


def bls_snr(time, flux, period, duration, t0):
    """Simple transit SNR: in-transit depth over out-of-transit scatter."""
    phase = ((time - t0 + 0.5 * period) % period) - 0.5 * period
    in_tr = np.abs(phase) < duration / 2.0
    if in_tr.sum() < 5 or (~in_tr).sum() < 50:
        return 0.0
    depth = np.median(flux[~in_tr]) - np.median(flux[in_tr])
    noise = np.std(flux[~in_tr])
    if noise <= 0:
        return 0.0
    return float(depth / noise * np.sqrt(in_tr.sum()))


def scan_target(tic, label):
    try:
        sr = robust_search(tic, mission="TESS", author="SPOC")
        if len(sr) == 0:
            print(f"{label}: no TESS light curves found, skipping")
            return None
        lcs = None
        last = None
        for attempt in range(1, 6):
            try:
                lcs = sr[:MAX_SECTORS].download_all()
                break
            except Exception as exc:
                last = exc
                print(f"{label}: download attempt {attempt} failed, retrying...")
                time.sleep(8 * attempt)
        if lcs is None:
            print(f"{label}: downloads failed ({last})")
            return None
        lc = lcs.stitch().remove_nans().remove_outliers(sigma=5)
        if len(lc) < 500:
            print(f"{label}: too few cadences ({len(lc)}), skipping")
            return None
        flat = lc.flatten(window_length=1001)

        bls = BoxLeastSquares(flat.time.value, flat.flux.value)
        periods = np.linspace(PERIOD_MIN, PERIOD_MAX, N_PERIODS)
        durations = np.linspace(0.05, 0.4, 8)
        res = bls.power(periods, durations, oversample=10)

        best = int(np.argmax(res.power))
        p = float(res.period[best])
        d = float(res.duration[best])
        t0 = float(res.transit_time[best])
        depth = float(res.depth[best])
        power = float(res.power[best])
        snr = bls_snr(flat.time.value, flat.flux.value, p, d, t0)

        print(f"{label}: P={p:.4f} d depth={depth*1e6:.0f} ppm "
              f"SNR={snr:.1f} power={power:.3f}")
        return {
            "target": label, "tic": tic, "period_d": p, "duration_d": d,
            "t0_btjd": t0, "depth_ppm": depth * 1e6, "snr": snr,
            "bls_power": power, "n_cadences": len(lc),
            "time": flat.time.value, "flux": flat.flux.value,
            "fold_period": p, "fold_t0": t0,
        }
    except Exception as exc:  # keep the batch alive if one target fails
        print(f"{label}: FAILED ({exc})")
        return None


def save_fold_plot(row, rank):
    t, f = row["time"], row["flux"]
    p, t0 = row["fold_period"], row["fold_t0"]
    phase = ((t - t0 + 0.5 * p) % p) - 0.5 * p
    order = np.argsort(phase)
    # simple binning in phase
    bins = np.linspace(-0.5 * p, 0.5 * p, 200)
    idx = np.digitize(phase, bins)
    bphase, bflux = [], []
    for k in range(1, len(bins)):
        m = idx == k
        if m.sum() > 3:
            bphase.append(0.5 * (bins[k - 1] + bins[k]))
            bflux.append(np.median(f[m]))

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.scatter(phase[order], f[order], s=2, alpha=0.2, color="steelblue",
               label="detrended flux")
    ax.scatter(bphase, bflux, s=16, color="darkred", label="binned")
    ax.set_xlabel("phase (days)")
    ax.set_ylabel("normalized flux")
    ax.set_title(
        f"#{rank} {row['target']}: P={row['period_d']:.4f} d, "
        f"depth={row['depth_ppm']:.0f} ppm, SNR={row['snr']:.1f} "
        f"(candidate signal, needs professional follow-up)")
    ax.legend(loc="best", fontsize=9)
    ax.grid(alpha=0.3)
    fname = f"top{rank}_{row['tic'].replace(' ', '_')}_fold.png"
    fig.tight_layout()
    fig.savefig(fname, dpi=150)
    plt.close(fig)
    print("Saved", fname)


def main():
    results = []
    for tic, label in TARGETS:
        row = scan_target(tic, label)
        if row:
            results.append(row)

    if not results:
        raise SystemExit("No targets scanned successfully.")

    # Rank: planet-like means deep enough to be real but not stellar
    # (depth < 3 percent rules out most eclipsing binaries), decent SNR.
    def score(r):
        depth_ok = 1.0 if r["depth_ppm"] < 30000 else 0.2
        return r["bls_power"] * depth_ok * min(r["snr"], 50.0)

    ranked = sorted(results, key=score, reverse=True)

    import csv
    with open("candidate_shortlist.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["rank", "target", "tic", "period_d", "duration_d",
                    "depth_ppm", "snr", "bls_power", "n_cadences", "note"])
        for i, r in enumerate(ranked, 1):
            w.writerow([i, r["target"], r["tic"],
                        f"{r['period_d']:.4f}", f"{r['duration_d']:.4f}",
                        f"{r['depth_ppm']:.0f}", f"{r['snr']:.1f}",
                        f"{r['bls_power']:.3f}", r["n_cadences"],
                        "candidate signal, needs professional follow-up"])

    print("\nShortlist written to candidate_shortlist.csv")
    for i, r in enumerate(ranked[:3], 1):
        save_fold_plot(r, i)

    print("\nTop signals:")
    for i, r in enumerate(ranked, 1):
        print(f"  #{i} {r['target']}: P={r['period_d']:.4f} d, "
              f"depth={r['depth_ppm']:.0f} ppm, SNR={r['snr']:.1f}")


if __name__ == "__main__":
    main()
