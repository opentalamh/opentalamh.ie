# First-attempt map: County Louth

A first pass at the map from data that is already open. It puts every likely
Catholic Church site in one county on one map, from five sources, and merges
points that sit within 100 m of each other into candidate sites.

**Every point is a grade D lead (location only).** No open dataset says who owns
a parcel. Ownership comes later, from Land Registry folios.

## Run it

You need Python 3.10+ and an internet connection.

```
pip install -r requirements.txt
jupyter notebook first_map.ipynb      # step by step, with explanations
python run_pilot.py                    # or all at once
```

Outputs land in `outputs/`:

| File | What it is |
| --- | --- |
| `louth_first_map.html` | The map. Open it in a browser and toggle layers per source. |
| `louth_candidate_sites.csv` | One row per candidate site, with blank `folio_number` and `registered_owner` columns to fill during the pilot. |
| `louth_points.csv` | Every point from every source, with its source record link. |
| `charity_name_leads.csv` | Catholic-sounding charity names, a seed for the name list. |
| `louth_source_summary.csv` | Points per source. |

To run another county, change `COUNTY` in `wotl/config.py`.

## Files

- `wotl/config.py`: county, source URLs, keyword lists.
- `wotl/sources.py`: one fetcher per source (OpenStreetMap, NIAH, school lists, valuation list, charities register, history seed list).
- `wotl/build.py`: merging points into sites, and drawing the map.
- `data/seed/history_sites.csv`: institutions from the official reports, entered by hand with references.
- `tests/test_offline.py`: checks the parsing and merging on made-up records (`python -m pytest tests`).

## Status

The code was tested on made-up records only. It has not yet run against the
live sources, because the environment it was written in couldn't reach them.
Expect to adjust a column name or two on the first real run, especially for
the school lists and the valuation API, whose formats change between years.
If a source fails, the run carries on without it and prints a warning.
