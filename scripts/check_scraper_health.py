#!/usr/bin/env python3
"""Scraper health monitor for YardBird / GSIN map-refresh.

Reads the *.log files produced by map-refresh steps and the live city JSON
source counts. Emits a clear health report to stdout (for GITHUB_STEP_SUMMARY)
and writes webapp/data/scraper-health.json.

Exit codes:
  0  — healthy or degraded (soft-warn only / single primary zero)
  1  — critical (majority of primary free sources failed / zero / missing)

Primary free sources:
  - EstateSales.org
  - YardSaleSearch
  - Craigslist

Secondary (warn-only):
  - GarageSaleFinder
  - SA permits
  - EstateSales.net lightweight
  - gsalr.com
  - Express-News Marketplace
  - Wilson County News
  - yardsales.net
  - A Better Estate Sale
  - Blox classifieds (Herald-Zeitung, Seguin Gazette)
  - Event listings (AllEvents + Eventbrite)

Every discovery step in master_populate writes a per-source log, so a
missing log means the step truly did not run (not_run) — it is never
reported as a source failure. A step whose script is absent from the
repo gets a stub log and is reported as missing_script, distinct from
both. Sources that contribute listings through other pipeline paths
(submissions, community/event feeds, manual adds) have no per-run log;
they are listed under untracked_sources with their live inventory
counts so every active source has an observable state.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

CT = ZoneInfo("America/Chicago")
ROOT = Path(__file__).resolve().parents[1]
CITY_DIR = ROOT / "data" / "cities"
HEALTH_PATH = ROOT / "data" / "scraper-health.json"

LOGS = {
    "garagesalefinder": "discover.log",
    "permits": "permits.log",
    "estatesales_org": "estatesales-org.log",
    "yardsalesearch": "yardsalesearch.log",
    "gsalr": "gsalr.log",
    "craigslist": "craigslist.log",
    "estatesales_net": "estatesales.log",
    "express_news": "express-news.log",
    "wilson_county": "wilson-county.log",
    "yardsales_net": "yardsales-net.log",
    "abetterestatesale": "abetterestatesale.log",
    "blox_classifieds": "blox-classifieds.log",
    "event_listings": "event-listings.log",
}

PRIMARY = {"estatesales_org", "yardsalesearch", "craigslist"}

# These fetchers treat per-section HTTP failures as soft skips: they log a
# WARN line for the section they skipped, keep going, and print a final
# normalized= count. A WARN in their log is only a source failure when no
# usable records came out of the run; a positive count is a success even
# when some sections were skipped.
SOFT_WARN_SOURCES = {
    "express_news",
    "wilson_county",
    "yardsales_net",
    "abetterestatesale",
    "blox_classifieds",
    "event_listings",
}

# Listing "source" strings in the city JSON (lowercased) that belong to a
# tracked pipeline source. Anything else in the JSON counts is an
# inventory-only source: it contributes listings through other pipeline
# paths and has no per-run retrieval log.
SOURCE_ALIASES = {
    "garagesalefinder": "garagesalefinder",
    "yardsalesearch": "yardsalesearch",
    "craigslist": "craigslist",
    "estatesales.org": "estatesales_org",
    "estatesales.net": "estatesales_net",
    "gsalr": "gsalr",
    "express-news marketplace": "express_news",
    "wilson county news": "wilson_county",
    "yardsales.net": "yardsales_net",
    "a better estate sale": "abetterestatesale",
    "herald-zeitung": "blox_classifieds",
    "seguin gazette": "blox_classifieds",
    "allevents": "event_listings",
    "eventbrite": "event_listings",
}

# The daily pipeline runs several times a week; a tracked source whose
# last successful retrieval is older than this is flagged stale even if
# its most recent run state was recorded without an error.
STALE_AFTER_HOURS = 48

ZERO_PATTERNS = [
    re.compile(r"normalized=0\b", re.I),
    re.compile(r"0 listings?\b", re.I),
    re.compile(r"no sales? found\b", re.I),
    re.compile(r"static results=0\b", re.I),
    re.compile(r"enriched=0\b", re.I),
    re.compile(r"\b0 parsed\b", re.I),
    re.compile(r"garage/estate permits in window=0\b", re.I),
]

FAIL_PATTERNS = [
    re.compile(r"HTTP (403|429|5\d\d)\b"),
    re.compile(r"WARN: non-200", re.I),
    re.compile(r"Traceback \(most recent call last\)"),
    re.compile(r"blocked|forbidden|captcha|imperva", re.I),
    re.compile(r"ConnectionError|Timeout|URLError", re.I),
]

OK_PATTERNS = [
    re.compile(r"normalized=([1-9]\d*)\b", re.I),
    re.compile(r"garage/estate permits in window=([1-9]\d*)\b", re.I),
    re.compile(r"(?:parsed|enriched|static results)=([1-9]\d*)\b", re.I),
    re.compile(r"\b[1-9]\d* parsed\b", re.I),
    re.compile(r"merge added=([1-9]\d*)\b", re.I),
]


def read_log(name: str, log_dir: Path) -> str:
    p = log_dir / name
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8", errors="replace")


# Final discovery-stage counts, not merge-added counts or accumulated inventory.
# Sum once per requested city. Missing markers remain null, not a false zero.
RECORD_COUNT_PATTERNS = {
    "garagesalefinder": ("parsed", re.compile(r"^\s*(?:.*?→\s*)?(\d+) parsed\b", re.I | re.M)),
    "permits": ("permits_in_window", re.compile(r"garage/estate permits in window=(\d+)\b", re.I)),
    "estatesales_org": ("normalized", re.compile(r"^\s*normalized=(\d+)\b", re.I | re.M)),
    "yardsalesearch": ("normalized", re.compile(r"^\s*normalized=(\d+)\b", re.I | re.M)),
    "gsalr": ("normalized", re.compile(r"^\s*normalized=(\d+)\b", re.I | re.M)),
    "craigslist": ("enriched", re.compile(r"^\s*enriched=(\d+)\b", re.I | re.M)),
    "estatesales_net": ("normalized", re.compile(r"^\s*normalized=(\d+)\b", re.I | re.M)),
    "express_news": ("normalized", re.compile(r"^\s*normalized=(\d+)\b", re.I | re.M)),
    "wilson_county": ("normalized", re.compile(r"^\s*normalized=(\d+)\b", re.I | re.M)),
    "yardsales_net": ("normalized", re.compile(r"^\s*normalized=(\d+)\b", re.I | re.M)),
    "abetterestatesale": ("normalized", re.compile(r"^\s*normalized=(\d+)\b", re.I | re.M)),
    "blox_classifieds": ("normalized", re.compile(r"^\s*normalized=(\d+)\b", re.I | re.M)),
    "event_listings": ("normalized", re.compile(r"^\s*normalized=(\d+)\b", re.I | re.M)),
}

def extract_records_found(key: str, text: str) -> tuple[int | None, str | None]:
    spec = RECORD_COUNT_PATTERNS.get(key)
    if not spec:
        return None, None
    metric, pattern = spec
    values = [int(value) for value in pattern.findall(text)]
    if not values:
        return None, metric
    return sum(values), metric

def analyze_log(key: str, text: str) -> dict:
    primary = key in PRIMARY
    if not text.strip():
        metric = RECORD_COUNT_PATTERNS.get(key, (None, None))[0]
        return {
            "source": key, "status": "not_run",
            "detail": "no source log captured for this run", "primary": primary,
            "records_found": None, "records_found_metric": metric,
        }

    def marker(name: str) -> str | None:
        match = re.search(rf"^__CHICA_{name}=(.+)$", text, re.M)
        return match.group(1).strip() if match else None

    exit_code = marker("EXIT_CODE")
    started_at = marker("STARTED_AT")
    finished_at = marker("FINISHED_AT")
    records_found, records_metric = extract_records_found(key, text)
    result = {
        "source": key, "primary": primary,
        "last_attempt_at": started_at,
        "finished_at": finished_at,
        "exit_code": int(exit_code) if exit_code and exit_code.isdigit() else None,
        "records_found": records_found,
        "records_found_metric": records_metric,
    }

    if "SCRIPT MISSING" in text:
        result.update(
            status="missing_script",
            detail="source script missing from repo — step could not run",
        )
        return result

    if result["exit_code"] not in (None, 0):
        result.update(status="fail", detail=f"source script exited {result['exit_code']}")
        return result

    # Soft-warn fetchers log per-section WARN lines for sections they skip
    # and still finish with a real count. A positive count is a successful
    # retrieval; their WARN lines only decide the state when nothing came
    # out of the run (handled by the fail/zero checks below).
    if key in SOFT_WARN_SOURCES and records_found:
        result.update(status="ok", detail=f"normalized={records_found}")
        result["last_successful_retrieval"] = finished_at
        return result

    for pat in FAIL_PATTERNS:
        match = pat.search(text)
        if match:
            result.update(status="fail", detail=match.group(0)[:120])
            return result

    # Craigslist's static search count is only an intermediate stage. The
    # final enriched count determines whether usable sale records were found.
    if key == "craigslist" and records_found is not None:
        if records_found == 0:
            result.update(status="zero", detail="source returned zero enriched listings")
        else:
            result.update(status="ok", detail=f"enriched={records_found}")
        result["last_successful_retrieval"] = finished_at
        return result

    for pat in OK_PATTERNS:
        match = pat.search(text)
        if match:
            result.update(status="ok", detail=match.group(0)[:80])
            result["last_successful_retrieval"] = finished_at
            return result

    for pat in ZERO_PATTERNS:
        if pat.search(text):
            result.update(status="zero", detail="source returned zero listings")
            result["last_successful_retrieval"] = finished_at
            return result

    if result["exit_code"] == 0:
        result.update(
            status="completed_unverified",
            detail="script exited successfully but emitted no recognized retrieval/result marker",
        )
    else:
        result.update(status="unknown", detail="log present without run metadata or result marker")
    return result


def source_counts_from_json() -> dict[str, int]:
    counts: dict[str, int] = {}
    for path in CITY_DIR.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for item in data.get("public") or []:
            src = (item.get("source") or "unknown").strip().lower()
            counts[src] = counts.get(src, 0) + 1
    return counts


def apply_staleness(results: list[dict], now: datetime) -> list[dict]:
    """Flag sources whose last successful retrieval is older than
    STALE_AFTER_HOURS. Returns the stale subset. Sources that have never
    recorded a success keep age None and are judged by their run status."""
    stale = []
    for item in results:
        last = item.get("last_successful_retrieval")
        age_hours = None
        if last:
            try:
                parsed = datetime.fromisoformat(last)
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=CT)
                age_hours = round((now - parsed).total_seconds() / 3600, 1)
            except ValueError:
                age_hours = None
        item["last_success_age_hours"] = age_hours
        item["stale"] = age_hours is not None and age_hours > STALE_AFTER_HOURS
        if item["stale"]:
            stale.append(item)
    return stale


def split_inventory(json_counts: dict[str, int]) -> tuple[dict[str, int], list[dict]]:
    """Split live JSON source counts into counts owned by tracked pipeline
    sources and inventory-only sources with no per-run retrieval log."""
    tracked: dict[str, int] = {}
    untracked: list[dict] = []
    for name, count in json_counts.items():
        key = SOURCE_ALIASES.get(name)
        if key:
            tracked[key] = tracked.get(key, 0) + count
        else:
            untracked.append({"source": name, "listings": count})
    untracked.sort(key=lambda entry: -entry["listings"])
    return tracked, untracked


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log-dir", type=Path, default=Path.cwd())
    args = parser.parse_args()
    now = datetime.now(CT).isoformat(timespec="seconds")
    previous_success = {}
    try:
        previous = json.loads(HEALTH_PATH.read_text(encoding="utf-8"))
        previous_success = {
            item.get("source"): item.get("last_successful_retrieval")
            for item in previous.get("sources", [])
            if item.get("last_successful_retrieval")
        }
    except (OSError, json.JSONDecodeError, AttributeError):
        pass

    results = []
    for key, logname in LOGS.items():
        text = read_log(logname, args.log_dir)
        item = analyze_log(key, text)
        if not item.get("last_successful_retrieval") and key in previous_success:
            item["last_successful_retrieval"] = previous_success[key]
        results.append(item)
    stale_sources = apply_staleness(results, datetime.now(CT))

    json_counts = source_counts_from_json()
    tracked_inventory, untracked_sources = split_inventory(json_counts)

    critical_fails = [
        r for r in results if r["primary"] and r["status"] in ("fail", "missing_script")
    ]
    warns = [
        r for r in results if (not r["primary"]) and r["status"] in ("fail", "missing_script", "zero", "not_run", "unknown", "completed_unverified")
    ]
    uncertain_primary = [
        r for r in results if r["primary"] and r["status"] in ("not_run", "unknown", "completed_unverified")
    ]
    zero_sources = [r for r in results if r["status"] == "zero"]

    n_primary_problems = len(critical_fails)
    if n_primary_problems >= 2:
        overall = "critical"
    elif n_primary_problems == 1 or warns or uncertain_primary or zero_sources or stale_sources:
        overall = "degraded"
    else:
        overall = "healthy"

    report = {
        "generated_at": now,
        "overall": overall,
        "primary_failures": [r["source"] for r in critical_fails],
        "sources": results,
        "json_source_counts": json_counts,
        "tracked_inventory_counts": tracked_inventory,
        "untracked_sources": untracked_sources,
        "notes": (
            "Primary free sources: estatesales_org, yardsalesearch, craigslist. "
            "Secondary: gsalr, garagesalefinder, permits, estatesales_net, express_news, "
            "wilson_county, yardsales_net, abetterestatesale, blox_classifieds, event_listings. "
            "Only explicit source errors/nonzero exits count as failures. Missing logs are not_run, "
            "a source script absent from the repo is missing_script, zero listings are a successful "
            "empty retrieval, and unrecognized output is unverified. "
            "Two or more failed primary sources are critical. "
            f"A tracked source whose last successful retrieval is over {STALE_AFTER_HOURS}h old is stale. "
            "Source-attributed JSON counts are inventory evidence, not proof of a fresh retrieval. "
            "untracked_sources contribute listings through other pipeline paths (submissions, "
            "community/event feeds, manual adds) and have no per-run retrieval log. "
            "Apify removed 2026-08-22."
        ),
    }

    HEALTH_PATH.parent.mkdir(parents=True, exist_ok=True)
    HEALTH_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print("### Scraper health")
    print("")
    print(f"- Overall: **{overall.upper()}**")
    print(f"- Generated: {now}")
    print(f"- Confirmed primary failures: {n_primary_problems}/3")
    print(f"- Primary sources without verified retrieval evidence: {len(uncertain_primary)}")
    print(f"- Sources with zero listings: {len(zero_sources)}")
    print(f"- Sources with stale last success (>{STALE_AFTER_HOURS}h): {len(stale_sources)}")
    print("")
    print("| Source | Status | Records found | Detail |")
    print("|--------|--------|--------------:|--------|")
    for r in results:
        flag = "🔴" if r["status"] in ("fail", "missing_script") else ("🟡" if r["status"] in ("zero", "not_run", "unknown", "completed_unverified") else "🟢")
        print(f"| {r['source']} | {flag} {r['status']} | {r.get('records_found') if r.get('records_found') is not None else '—'} | {r['detail'][:60]} |")
    print("")
    if json_counts:
        print("#### Live public counts by source (from city JSON)")
        for src, n in sorted(json_counts.items(), key=lambda x: -x[1]):
            print(f"- {src}: {n}")
        print("")
    if untracked_sources:
        print("#### Inventory-only sources (no per-run retrieval log)")
        print("These contribute live listings through other pipeline paths — submissions, community/event feeds, manual adds — so they have no run status above.")
        for entry in untracked_sources:
            print(f"- {entry['source']}: {entry['listings']}")
        print("")

    if overall == "critical":
        print("#### ⚠️ Critical — two or more primary source failures confirmed")
        for r in critical_fails:
            print(f"- **{r['source']}**: {r['status']} — {r['detail']}")
        print("")
        print("An issue will be opened (or updated) if none is already open with label `scraper-failure`.")
        return 1

    if overall == "degraded":
        print("#### 🟡 Degraded — source failures, empty results, or incomplete monitoring evidence")
        for r in critical_fails:
            print(f"- **{r['source']}**: {r['status']} — {r['detail']}")
        for r in uncertain_primary:
            print(f"- **{r['source']}**: {r['status']} — {r['detail']}")
        for r in zero_sources:
            print(f"- {r['source']}: {r['status']} — {r['detail']}")
        for r in warns:
            print(f"- {r['source']}: {r['status']} — {r['detail']}")
        for r in stale_sources:
            print(f"- {r['source']}: stale — last successful retrieval {r['last_success_age_hours']}h ago")
        print("")
        print("Map remains usable. Soft-fail continues.")
        return 0

    print("All primary free sources look healthy (or soft-warn only).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
