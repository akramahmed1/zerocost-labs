# Exoplanet Hunt, Prototype B: Run Summary

Date: 2026-10-09
Data: NASA TESS 2-minute cadence PDCSAP light curves, MAST archive (free, no key)
Stack: Python 3.12, lightkurve 2.6.0, astropy 8.0.1 (Box Least Squares)

## What this is

A prototype transit-detection pipeline: download TESS light curves, detrend
with a Savitzky-Golay filter, and search for periodic dips with Box Least
Squares (BLS). Two scripts:

- `validate_toi700.py`: validation on the known planet host TOI 700
- `candidate_scan.py`: same pipeline over 8 TOI targets, ranked shortlist

Setup: `python3 -m venv venv && ./venv/bin/pip install lightkurve astropy matplotlib numpy`
Run: `./venv/bin/python validate_toi700.py`, then `./venv/bin/python candidate_scan.py`

Note: MAST sits behind a flaky egress proxy in this environment, so both
scripts retry searches and downloads with exponential backoff.

## Step 1: validation on TOI 700 (known planets)

Downloaded 4 TESS sectors (62,074 cadences). BLS over periods 1 to 40 days
returned its strongest signal at:

- Recovered: P = 16.0509 d, depth 2356 ppm
- Published TOI 700 c: P = 16.051 d
- Period error: 0.001 percent. Recovered cleanly.

The BLS periodogram shows one dominant spike at 16.05 d and the folded light
curve shows a clear transit dip at phase 0 (see `toi700_validation_fold.png`).
The pipeline works: it finds real transits in real TESS data.

## Step 2: batch scan of 8 TOI targets (2 sectors each)

| Rank | Target | Recovered P (d) | Depth (ppm) | SNR | Readout |
|------|--------|-----------------|-------------|-----|---------|
| 1 | TOI 1338 | 14.6022 | 2518 | 30.4 | Matches the host stars' 14.6 d eclipsing-binary period, NOT the planet (TOI 1338 b is ~95 d). Correctly found the strongest signal; it is stellar. |
| 2 | TOI 270 | 5.6605 | 3474 | 38.5 | Matches published TOI 270 c (5.66 d). Clean recovery. |
| 3 | TOI 216 | 24.2421 | 10662 | 23.3 | Unexplained. Known planets are at 17.16 d and 34.56 d. Possible aliasing between the two, or a false positive. V-shaped dip suggests binary contamination. |
| 4 | TOI 776 | 3.6912 | 1336 | 39.7 | Unexplained. Known planets are near 8.25 d and 15.7 d. Could be a harmonic or a false positive. |
| 5 | TOI 700 | 16.0503 | 2501 | 16.3 | TOI 700 c again, consistent with the validation run. |
| 6 | TOI 125 | 4.6549 | 773 | 20.9 | Matches published TOI 125 b (4.65 d). Clean recovery. |
| 7 | TOI 849 | 0.7926 | 385 | 4.2 | Near published TOI 849 b (0.765 d) but 3.5 percent off and very weak. Marginal at best. |
| 8 | TOI 178 | 16.2887 | 630 | 1.5 | Weak, likely noise. No known planet at this period. |

Full numbers: `candidate_shortlist.csv`. Folded plots for the top 3:
`top1_TIC_260128333_fold.png`, `top2_TIC_259377017_fold.png`,
`top3_TIC_55652896_fold.png`.

Published periods above are from the literature and should be re-verified
against the NASA Exoplanet Archive before any external use.

## The required honesty block

Nothing here is a planet discovery. Every unexplained signal above is a
CANDIDATE SIGNAL that needs professional follow-up (ground-based photometry,
spectroscopy, vetting). Most BLS detections in real survey data are false
positives. This prototype does no vetting at all.

## Limitations

1. False positives dominate. BLS cannot tell a planet from an eclipsing
   binary, a background blended binary, starspot modulation, or instrument
   systematics. TOI 1338 is the textbook case: the strongest signal is the
   stars eclipsing each other.
2. Only the strongest signal per target is reported. Real systems are
   multi-planet; this pipeline is blind to everything after the first hit.
3. Only 2 sectors per target were scanned (validation used 4). Longer
   baselines find longer periods and beat down noise.
4. No vetting tests: no odd/even transit depth comparison, no secondary
   eclipse search, no centroid shift check, no transit shape fitting.
5. BLS is a box model. Real transits are limb-darkened U shapes; the
   Transit Least Squares (TLS) algorithm is more sensitive, especially for
   small planets.
6. This does not beat NASA's ExoMiner++. ExoMiner++ is a deep-learning
   classifier trained on Kepler plus TESS data that triaged 7,000 candidates
   in one run, with false-positive rejection built in. This prototype is a
   single classical algorithm with no learned vetting. Its value is as an
   independent, explainable check, not as a competitor.
7. MAST access from this network is flaky (proxy drops); the retry wrapper
   papers over it but a production run would want a stable connection.

## What v2 would need

- Cross-match every signal against the NASA Exoplanet Archive and the
  ExoMiner++ candidate list before calling anything interesting.
- Add vetting: odd/even depth test, secondary eclipse search, transit shape
  (V vs U), centroid offsets, and a check against known eclipsing-binary
  catalogs.
- Swap BLS for TLS for small-planet sensitivity.
- Stitch all available sectors per target instead of 2.
- Cross-check ambiguous signals on Planet Hunters TESS, where human eyes
  still beat algorithms on long-period and odd-shaped transits.
- Interesting survivors get submitted to ExoFOP (the community follow-up
  portal), never announced as discoveries.
- For the build-in-public angle: wrap the whole thing in a one-command CLI
  plus a weekly "candidate of the week" thread template, with the
  candidate-signal labeling baked into every output.
