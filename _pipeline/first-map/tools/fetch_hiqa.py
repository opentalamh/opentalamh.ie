"""Save the HIQA registers of designated centres for one county.

    python tools/fetch_hiqa.py --county Dublin

Reads every older persons' and disability centre in HIQA's Find a Centre
listing, and the registered provider from each centre's latest inspection
report, two seconds apart because HIQA refuses rapid requests. Writes
data/cache/hiqa_<county>.csv, which the map build reads. Run by the "Fetch
HIQA register" workflow; it takes about half an hour for Dublin.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from wotl import config, sources  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--county", default=config.COUNTY)
    args = ap.parse_args()
    config.set_county(args.county)
    df = sources.fetch_hiqa_centres()
    missing = int((df["provider"] == "").sum())
    path = sources.hiqa_cache_path()
    old = sources.load_hiqa_centres() if path.exists() else df.iloc[0:0]
    # Don't replace a fuller saved copy with a run HIQA cut short.
    if len(df) < 0.9 * len(old):
        sys.exit(f"Only {len(df)} centres read against {len(old)} saved; keeping the saved copy.")
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    print(f"{config.COUNTY}: {len(df)} centres, {missing} without a provider -> {path}")
    print(df["type"].value_counts().to_string())


if __name__ == "__main__":
    main()
