"""Build the first-attempt map for one county from open data.

    python run_pilot.py                     # Dublin (or $WOTL_COUNTY), cached downloads
    python run_pilot.py --county Louth      # another county from config.COUNTIES
    python run_pilot.py --refresh           # downloads everything again

Outputs go to outputs/: the map (HTML), every point, the merged candidate
sites (with blank folio and owner columns for the pilot), name leads for the
Land Registry search, and a seed list of Catholic-sounding charity names.
"""

import argparse
import time
import warnings

import pandas as pd

from wotl import build, config, names, sources


def _timed(label, fetch, refresh):
    """Run one fetcher and log how long it took, so a slow source shows in the log."""
    start = time.time()
    print(f"[{time.strftime('%H:%M:%S')}] {label}...", flush=True)
    out = fetch(refresh)
    print(f"[{time.strftime('%H:%M:%S')}] {label}: {len(out)} rows in {time.time() - start:.0f}s", flush=True)
    return out


def run(refresh=False):
    config.OUT_DIR.mkdir(parents=True, exist_ok=True)
    county = config.COUNTY.lower()
    fetchers = {
        "OpenStreetMap": sources.fetch_osm,
        "NIAH": sources.fetch_niah,
        "Protected structures": sources.fetch_rps,
        "School lists": sources.fetch_schools,
        "Valuation list": sources.fetch_valuation,
    }
    if not config.RPS_DATASETS:
        del fetchers["Protected structures"]
    if not config.VALUATION_LOCAL_AUTHORITIES:
        del fetchers["Valuation list"]
    frames = {label: _timed(label, fetch, refresh) for label, fetch in fetchers.items()}
    found = [v for v in frames.values() if not v.empty]
    points = pd.concat(found, ignore_index=True) if found else sources._empty()
    # An area name can also match a place abroad (there is a Fingal in Tasmania).
    south, west, north, east = config.BBOX
    inside = points["lat"].astype(float).between(south, north) & points["lon"].astype(float).between(west, east)
    if (~inside).any():
        print(f"Dropped {int((~inside).sum())} points outside the county's bounding box: "
              f"{points.loc[~inside, 'source'].value_counts().to_dict()}", flush=True)
    points = points[inside].reset_index(drop=True)

    hiqa = _timed("HIQA registers", sources.fetch_hiqa_centres, refresh)
    unplaced = []
    for label, seed in (("HIQA registered centres", sources.hiqa_church_centres(hiqa)),
                        ("Industrial schools (Ryan Report)", sources.load_industrial_schools()),
                        ("History seed list", sources.load_history_sites()),
                        ("Redress transfers (former holdings)", sources.load_redress_transfers())):
        placed, missing = sources.place_history_sites(seed, points)
        frames[label] = placed
        unplaced.append(missing)
    for label in ("HIQA registered centres", "Industrial schools (Ryan Report)", "History seed list",
                  "Redress transfers (former holdings)"):
        if not frames[label].empty:
            points = pd.concat([points, frames[label]], ignore_index=True)
    unplaced = pd.concat(unplaced, ignore_index=True)
    unplaced.to_csv(config.OUT_DIR / f"{county}_unplaced_history.csv", index=False)

    summary = pd.DataFrame(
        [{"source": k, "points": len(v), "with_coordinates": int(v[["lat", "lon"]].notna().all(axis=1).sum())}
         for k, v in frames.items()]
    )
    other = sources.fetch_osm(refresh, other_only=True)
    points, dropped = build.drop_near_other(points, other)
    points, sites = build.merge_sites(points)
    points.to_csv(config.OUT_DIR / f"{county}_points.csv", index=False)
    sites.to_csv(config.OUT_DIR / f"{county}_candidate_sites.csv", index=False)
    build.draw_map(points, sites, config.OUT_DIR / f"{county}_first_map.html")

    charities = _timed("Charities register", sources.fetch_charity_names, refresh)
    if not charities.empty:
        charities.to_csv(config.OUT_DIR / "charity_name_leads.csv", index=False)
    leads = names.name_leads(frames["School lists"], frames["OpenStreetMap"], charities, hiqa)
    leads.to_csv(config.OUT_DIR / f"{county}_name_leads.csv", index=False)

    summary.loc[len(summary)] = {"source": "Charities register (names only)", "points": len(charities), "with_coordinates": 0}
    summary.to_csv(config.OUT_DIR / f"{county}_source_summary.csv", index=False)
    stats = {"dropped_other_denomination": dropped, "unplaced_history": len(unplaced), "name_leads": len(leads)}
    return summary, points, sites, leads, stats


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--county", help=f"one of {', '.join(config.COUNTIES)} (default {config.COUNTY})")
    ap.add_argument("--refresh", action="store_true", help="download every source again")
    args = ap.parse_args()
    if args.county:
        config.set_county(args.county)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        summary, points, sites, leads, stats = run(args.refresh)
    print(f"County {config.COUNTY}\n")
    print(summary.to_string(index=False))
    print(f"\n{len(sites)} candidate sites; {int((sites['n_sources'] > 1).sum())} found by 2+ sources.")
    if len(sites):
        print(f"Largest site groups {points['site_id'].value_counts().head(3).to_dict()} (merge radius {config.MERGE_RADIUS_M} m).")
    print(f"{stats['dropped_other_denomination']} unmarked points dropped as sitting on another denomination's church.")
    print(f"{stats['unplaced_history']} history sites not yet placed; {stats['name_leads']} name leads.")
    for w in caught:
        print("WARNING:", w.message)
    print(f"\nOutputs in {config.OUT_DIR}")
