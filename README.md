# zerocost-labs

Reverse-engineering free public data into real builds. Every project here starts from data anyone can download for $0 and ends with something you can run, demo, and post.

Built in public with AI assistance (Muse). Each prototype lands through a pull request from its own branch. Nothing merges without review.

## Projects

### 1. govcon-feed
Turns boring public federal spending records into a discovery feed: small businesses winning big federal contracts. Data: USAspending.gov API (free, no key). The wedge nobody owns is the free, public narrative layer on top of govcon data.

### 2. exoplanet-hunt
Transit-detection pipeline on NASA's public TESS telescope data. Validates by re-finding known planets, then hunts candidate signals. Data: MAST archive via lightkurve (free, no key). Every signal is labeled a candidate, never a discovery, until professional follow-up.

## Conventions

- One project per directory, one branch per prototype, one PR per merge.
- `docs/research-notes.md` holds the market and competition analysis behind each project.
- No secrets in the repo. Public data sources only.
- Prototype scope: prove the pipeline works on real data, show honest limitations, then decide on v2.
