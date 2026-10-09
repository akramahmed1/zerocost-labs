# govcon-feed

Small businesses winning big federal contracts, surfaced from free public data.

## Data source
USAspending.gov API (`https://api.usaspending.gov`). Free, no API key required.

## Prototype goal
Query recent contract awards of $1M+ to small businesses, rank the most story-worthy (unusually large for the recipient, first-time-seeming winners, interesting agencies), and output a digest plus a draft X thread.

## Honest limitations (to verify in the prototype)
- "First-time winner" detection is approximate; recipient history lookups are the weak point.
- Data freshness depends on agency reporting lags.
- This is the most crowded lane (GovWin, GovSpend, Bloomberg Government, HigherGov, GovTribe, plus AI entrants). The wedge is the free public narrative layer, not another paid dashboard.
