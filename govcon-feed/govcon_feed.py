#!/usr/bin/env python3
"""
govcon_feed.py - Prototype A: govcon discovery feed.

Surfaces story-worthy small-business federal contract wins from the free,
no-key USAspending.gov API.

What it does:
  1. Pulls recent contract awards ($1M+) carrying a small-business set-aside
     code via /api/v2/search/spending_by_award/.
  2. Approximates "first-time winner" status by counting each recipient's
     prior awards over the previous 5 years via /api/v2/search/spending_by_award_count/.
     THIS IS APPROXIMATE (name-based match, contracts only, 5-year window).
  3. Scores story-worthiness with a transparent heuristic.
  4. Writes digest-top10.md and x-thread-draft.md.

Hard constraints honored: no posting, no accounts, no keys, no payments.
Only reads public data, with polite delays between calls.
"""

import json
import time
from datetime import date, timedelta
from pathlib import Path

import requests

BASE = "https://api.usaspending.gov"
SEARCH = f"{BASE}/api/v2/search/spending_by_award/"
COUNT = f"{BASE}/api/v2/search/spending_by_award_count/"
LAST_UPDATED = f"{BASE}/api/v2/awards/last_updated/"

OUT_DIR = Path(__file__).resolve().parent
SLEEP = 0.6  # polite delay between API calls

# Small-business set-aside codes (FPDS). SBA = total small business set-aside,
# 8A/8AN = 8(a), HZC/HZS = HUBZone, WOSB/EDWOSB = woman-owned, SDVOSBC/SDVOSBS =
# service-disabled veteran-owned, LAS = local area set-aside.
SET_ASIDES = ["SBA", "8A", "8AN", "HZC", "HZS", "WOSB", "EDWOSB",
              "SDVOSBC", "SDVOSBS", "LAS"]

CONTRACT_CODES = ["A", "B", "C", "D"]  # BPA call, purchase order, delivery order, definitive contract

FIELDS = [
    "Award ID", "Recipient Name", "Award Amount", "Awarding Agency",
    "Description", "Base Obligation Date", "pop_city_name",
    "pop_state_code", "pop_country_name", "Recipient UEI",
    "generated_internal_id", "naics_description",
]
# NOTE (verified against the live API 2026-10-09): the v2 search API silently
# ignores `business_categories` and `recipient_type_names` filters, and the
# display names "Award Date"/"Award Description"/"Place of Performance City"
# are NOT valid fields or sort keys. Correct names are "Base Obligation Date",
# "Description", "pop_city_name", etc. Small-business targeting is done via
# set_aside_type_codes, which the API honors.

# Keywords that make a win more story-worthy for a general audience.
HOT_KEYWORDS = ["artificial intelligence", " ai ", "cyber", "drone", "space",
                "satellite", "quantum", "robot", "autonomous", "5g"]

# Agencies whose wins tend to read as interesting to a general audience.
INTERESTING_AGENCY_HINTS = ["NASA", "Homeland Security", "Veterans Affairs",
                            "State", "Energy", "Commerce", "Treasury"]


def post(url, payload):
    r = requests.post(url, json=payload, timeout=120)
    r.raise_for_status()
    time.sleep(SLEEP)
    return r.json()


def fetch_recent_awards(start, end, min_amount=1_000_000, pages=4, limit=100):
    """Pull recent set-aside awards, newest first."""
    awards = []
    for page in range(1, pages + 1):
        data = post(SEARCH, {
            "filters": {
                "award_type_codes": CONTRACT_CODES,
                "time_period": [{"start_date": start, "end_date": end}],
                "award_amounts": [{"lower_bound": min_amount}],
                "set_aside_type_codes": SET_ASIDES,
            },
            "fields": FIELDS,
            "sort": "Base Obligation Date",
            "order": "desc",
            "limit": limit,
            "page": page,
        })
        results = data.get("results", [])
        awards.extend(results)
        if not data.get("page_metadata", {}).get("hasNext"):
            break
    return awards


def prior_award_count(recipient_name):
    """Approximate number of prior contract awards for a recipient over ~5 years.

    APPROXIMATE: name-based text match, contracts only, 5-year window. A count
    of 1 (just this award) suggests a new winner but is NOT proof of first-time
    status. Name collisions and UEI changes can distort it in both directions.
    """
    end = date.today().isoformat()
    start = (date.today() - timedelta(days=5 * 365)).isoformat()
    data = post(COUNT, {"filters": {
        "award_type_codes": CONTRACT_CODES,
        "time_period": [{"start_date": start, "end_date": end}],
        "recipient_search_text": [recipient_name],
    }})
    return data.get("results", {}).get("contracts", 0)


def score_award(a):
    """Transparent story-worthiness heuristic. Returns (score, reasons)."""
    reasons = []
    s = 0
    amt = a.get("Award Amount") or 0
    if a.get("approx_first_time"):
        s += 3
        reasons.append("appears to be a first-time federal winner (approximate)")
    if amt >= 10_000_000:
        s += 2
        reasons.append("unusually large at ${:,.0f}".format(amt))
    elif amt >= 5_000_000:
        s += 1
        reasons.append("sizable at ${:,.0f}".format(amt))
    desc = " " + (a.get("Description") or "").lower() + " "
    if any(k in desc for k in HOT_KEYWORDS):
        s += 1
        reasons.append("hot topic area (AI/cyber/space/robotics)")
    agency = a.get("Awarding Agency") or ""
    if any(h.lower() in agency.lower() for h in INTERESTING_AGENCY_HINTS):
        s += 1
        reasons.append("eye-catching agency: " + agency)
    return s, reasons


def fmt_money(x):
    return "${:,.0f}".format(x) if x else "n/a"


def place(a):
    city = a.get("pop_city_name") or ""
    st = a.get("pop_state_code") or ""
    cc = a.get("pop_country_name") or ""
    city_t = city.title() if city.isupper() else city
    bits = [b for b in (city_t, st) if b]
    s = ", ".join(bits)
    if cc and cc != "UNITED STATES":
        s += f" ({cc.title() if cc.isupper() else cc})"
    return s or "not listed"


def main():
    end = date.today().isoformat()
    start = (date.today() - timedelta(days=30)).isoformat()

    try:
        freshness = requests.get(LAST_UPDATED, timeout=60).json()
    except Exception:
        freshness = {}
    last_update = freshness.get("last_updated", "unknown")

    print(f"Window: {start} to {end}; API last updated: {last_update}")
    raw = fetch_recent_awards(start, end)
    print(f"Pulled {len(raw)} raw award records")

    # Dedupe by generated internal id; drop records with no obligation date.
    seen, awards = set(), []
    for a in raw:
        gid = a.get("generated_internal_id")
        if not gid or gid in seen:
            continue
        seen.add(gid)
        if not a.get("Base Obligation Date"):
            continue
        awards.append(a)
    print(f"{len(awards)} unique awards with dates")

    # First-time approximation for the top 30 by amount (bounded API calls).
    candidates = sorted(awards, key=lambda a: a.get("Award Amount") or 0, reverse=True)[:30]
    for i, a in enumerate(candidates, 1):
        try:
            a["prior_awards_5y"] = prior_award_count(a["Recipient Name"])
        except Exception as e:
            a["prior_awards_5y"] = None
            print(f"  count failed for {a['Recipient Name']}: {e}")
        a["approx_first_time"] = (a["prior_awards_5y"] == 1)
        print(f"  [{i}/{len(candidates)}] {a['Recipient Name'][:45]:45s} prior(5y)={a['prior_awards_5y']}")
        a["score"], a["score_reasons"] = score_award(a)

    ranked = sorted(candidates, key=lambda a: (a["score"], a.get("Award Amount") or 0), reverse=True)
    top10 = ranked[:10]

    # ---- digest ----
    lines = [
        "# GovCon Discovery Feed: weekly prototype digest",
        "",
        f"Window: {start} to {end} (base obligation date).",
        f"USAspending API last updated: {last_update}.",
        f"Awards scanned: {len(awards)} unique small-business set-aside contract awards of $1M+.",
        "",
        "Method: small-business set-aside codes (SBA, 8(a), HUBZone, WOSB, SDVOSB, local area) "
        "on contract awards of $1M+, newest first. Story score weights first-time-seeming winners, "
        "large amounts, hot topic areas, and eye-catching agencies.",
        "",
        "> First-time-winner status is APPROXIMATE: it counts name-matched contract awards over the "
        "previous 5 years. A count of 1 suggests a new winner but is not proof. Award amounts are total "
        "obligated to date on the award, which can include modifications, not just the initial win.",
        "",
    ]
    for i, a in enumerate(top10, 1):
        why = "; ".join(a["score_reasons"]) if a["score_reasons"] else "made the cut on recency and size"
        desc = (a.get("Description") or "No description published.").strip()
        if len(desc) > 300:
            desc = desc[:297] + "..."
        lines += [
            f"## {i}. {a['Recipient Name']}",
            f"- Award amount (total obligated): {fmt_money(a.get('Award Amount'))}",
            f"- Awarding agency: {a.get('Awarding Agency') or 'not listed'}",
            f"- Award ID: {a.get('Award ID')}",
            f"- Award date (base obligation): {a.get('Base Obligation Date')}",
            f"- Place of performance: {place(a)}",
            f"- NAICS: {(a.get('naics_description') or 'not listed').lower()}",
            f"- Recipient UEI: {a.get('Recipient UEI') or 'not listed'}",
            f"- Prior contract awards in last 5 years (approx): {a.get('prior_awards_5y')}",
            f"- Description: {desc}",
            f"- Why it is interesting: {why}.",
            "",
        ]
    (OUT_DIR / "digest-top10.md").write_text("\n".join(lines), encoding="utf-8")
    print("Wrote digest-top10.md")

    # ---- X thread draft (top 3) ----
    top3 = top10[:3]
    t = [
        "# X thread draft (NOT POSTED, draft only)",
        "",
        "Post 1:",
        "I pulled 30 days of federal contract data and looked for small businesses "
        "winning their first big awards. Here are 3 wins worth knowing about. All data from "
        "USAspending.gov, free and public.",
        "",
    ]
    for n, a in enumerate(top3, 2):
        amt = fmt_money(a.get("Award Amount"))
        name = a["Recipient Name"].title() if a["Recipient Name"].isupper() else a["Recipient Name"]
        agency = a.get("Awarding Agency") or "a federal agency"
        city = a.get("Place of Performance City") or ""
        first = "looks like their first federal win in 5 years" if a.get("approx_first_time") else "a repeat winner going bigger"
        desc = (a.get("Description") or "").strip()
        desc_short = (desc[:110] + "...") if len(desc) > 113 else desc
        pop = a.get("pop_city_name") or ""
        pop = pop.title() if pop.isupper() else pop
        t += [
            f"Post {n}:",
            f"{name} just landed {amt} from {agency} ({pop}). {desc_short} "
            f"This {first}.",
            "",
        ]
    t += [
        f"Post {n + 1}:",
        "The pattern: set-aside contracts are how small firms break in. "
        "The data is all public. Most people just never look. I will keep posting these finds.",
        "",
        "Note: first-time status is approximate, based on 5 years of name-matched award history. "
        "Amounts are total obligated to date.",
    ]
    (OUT_DIR / "x-thread-draft.md").write_text("\n".join(t), encoding="utf-8")
    print("Wrote x-thread-draft.md")

    summary = {
        "window_start": start, "window_end": end,
        "api_last_updated": last_update,
        "awards_scanned": len(awards),
        "top10": [
            {"recipient": a["Recipient Name"], "amount": a.get("Award Amount"),
             "agency": a.get("Awarding Agency"), "date": a.get("Base Obligation Date"),
             "prior_awards_5y": a.get("prior_awards_5y"),
             "approx_first_time": a.get("approx_first_time"),
             "score": a["score"]}
            for a in top10
        ],
    }
    (OUT_DIR / "run-summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print("Wrote run-summary.json")


if __name__ == "__main__":
    main()
