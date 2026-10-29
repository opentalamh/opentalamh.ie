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

First live run: 28 October 2026, on GitHub Actions (`.github/workflows/build-map.yml`
in the website repo runs the pipeline and commits the outputs).

| Source | Result for Louth |
| --- | --- |
| OpenStreetMap (Overpass) | 158 points. The main server often answers 502, so the fetcher retries and falls back to mirrors. |
| NIAH | 107 of 1,347 Louth records kept (churches, convents, presbyteries, schools with a Catholic marker). |
| Dept of Education school lists, 2025/26 | 71 Catholic-ethos schools (62 primary, 9 post-primary), all with coordinates. Patron shown: mostly the Archbishop of Armagh, some Bishop of Meath, CEIST, Edmund Rice, Le Chéile, Marist. |
| Tailte Éireann valuation list | 4,477 Louth properties downloaded, none with a religious use. Most Church property is exempt from rates, so it is not on the list. |
| Charities register | Not downloaded: charitiesregulator.ie refuses automated requests (403). Download it by hand and save it as `data/raw/public-register-of-charities.xlsx`. |
| History seed list | 1 site (St Joseph's Industrial School, Dundalk), placed on the St Malachy's Convent complex. |

Result: 157 candidate sites, 68 of them found by two or more sources.
Every point is a grade D lead: location only, ownership not checked.

If a fetcher fails because a link moved, `python tools/discover_sources.py`
lists the current links on data.gov.ie and the publishers' pages.
