# exoplanet-hunt

Hunting exoplanet transits in NASA's public TESS telescope data.

## Data source
MAST archive via the `lightkurve` Python package. Free, no key required. All TESS and Kepler data is public.

## Prototype goal
1. Validate the pipeline by recovering a known planet transit (TOI 700) with Box Least Squares.
2. Run the same search on a batch of TESS candidate light curves and shortlist the most planet-like signals.

## Rules
- Every signal is a *candidate*, never a discovery, until professional telescope follow-up.
- Do not try to beat NASA's ExoMiner++ (open source, 7,000 TESS candidates flagged Jan 2026). The value here is the pipeline, the learning, and the build-in-public story.

## Honest limitations (to verify in the prototype)
- False positives: eclipsing binaries, stellar activity, background interference.
- Real discovery is a lottery ticket and needs telescope time we don't control.
