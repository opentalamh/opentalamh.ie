"""Extract Catholic-linked charities from a hand-downloaded Charities Register.

The Charities Regulator refuses automated downloads, so the register is
downloaded by hand from https://data.gov.ie/dataset/register-of-charities-in-ireland
and passed here:

    python tools/extract_charities.py path/to/public-register-of-charities.xlsx --downloaded 2026-10-30

It writes data/seed/charities_catholic.csv: one row per Catholic-linked
charity (see wotl/charities.py for the rule), stamped with the register's
effective date and the download date. Trustee names are not copied. The
pipeline uses this file whenever the live download is refused.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from wotl import charities, config  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("register", help="the register .xlsx as downloaded")
    ap.add_argument("--downloaded", required=True, help="date the file was downloaded, YYYY-MM-DD")
    args = ap.parse_args()

    df, effective = charities.read_register(args.register)
    out = charities.classify(df)
    out.insert(0, "register_effective_date", effective or "")
    out.insert(1, "downloaded_on", args.downloaded)
    path = config.SEED_DIR / "charities_catholic.csv"
    out.to_csv(path, index=False)
    print(f"Register effective {effective}, downloaded {args.downloaded}: {len(df):,} charities, "
          f"{len(out):,} Catholic-linked -> {path}")
    print(out["catholic_match"].value_counts().to_string())


if __name__ == "__main__":
    main()
