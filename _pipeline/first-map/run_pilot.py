"""Build the first-attempt map for one county from open data.

    python run_pilot.py            # uses cached downloads where present
    python run_pilot.py --refresh  # downloads everything again

Outputs go to outputs/: the map (HTML), every point, the merged candidate
sites (with blank folio and owner columns for the pilot), and a seed list of
Catholic-sounding charity names.
"""

import argparse
import warnings

import pandas as pd

from wotl import build, config, sources


def run(refresh=False):
    config.OUT_DIR.mkdir(parents=True, exist_ok=True)
    county = config.COUNTY.lower()
    frames = {
        "OpenStreetMap": sources.fetch_osm(refresh),
        "NIAH": sources.fetch_niah(refresh),
        "School lists": sources.fetch_schools(refresh),
        "Valuation list": sources.fetch_valuation(refresh),
        "History seed list": sources.load_history_sites(),
    }
    summary = pd.DataFrame(
        [{"source": k, "points": len(v), "with_coordinates": int(v[["lat", "lon"]].notna().all(axis=1).sum())}
         for k, v in frames.items()]
    )
    points = pd.concat([v for v in frames.values() if not v.empty], ignore_index=True) \
        if any(not v.empty for v in frames.values()) else sources._empty()
    points, sites = build.merge_sites(points)
    points.to_csv(config.OUT_DIR / f"{county}_points.csv", index=False)
    sites.to_csv(config.OUT_DIR / f"{county}_candidate_sites.csv", index=False)
    build.draw_map(points, sites, config.OUT_DIR / f"{county}_first_map.html")

    names = sources.fetch_charity_names(refresh)
    if not names.empty:
        names.to_csv(config.OUT_DIR / f"charity_name_leads.csv", index=False)
    summary.loc[len(summary)] = {"source": "Charities register (names only)", "points": len(names), "with_coordinates": 0}
    summary.to_csv(config.OUT_DIR / f"{county}_source_summary.csv", index=False)
    return summary, points, sites, names


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true", help="download every source again")
    args = ap.parse_args()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        summary, points, sites, names = run(args.refresh)
    print(summary.to_string(index=False))
    print(f"\n{len(sites)} candidate sites; {int((sites['n_sources'] > 1).sum())} found by 2+ sources.")
    for w in caught:
        print("WARNING:", w.message)
    print(f"\nOutputs in {config.OUT_DIR}")
