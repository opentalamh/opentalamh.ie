# First-attempt maps: County Louth and County Dublin

A first pass at the map from data that is already open. It puts every likely
Catholic Church site in one county on one map, from several open sources, and
merges points that sit close together (100 m in Louth, 50 m in Dublin's denser
streets) into candidate sites. The same code runs any county set up in
`wotl/config.py`.

**Every point is a grade D lead (location only).** No open dataset says who owns
a parcel. Ownership comes later, from Land Registry folios.

## Run it

You need Python 3.10+ and an internet connection.

```
pip install -r requirements.txt
jupyter notebook first_map.ipynb      # step by step, with explanations
python run_pilot.py                    # or all at once (Dublin by default)
python run_pilot.py --county Louth     # any county in wotl/config.py
```

Outputs land in `outputs/`:

| File | What it is |
| --- | --- |
| `<county>_first_map.html` | The map. Open it in a browser and toggle layers per source. |
| `<county>_candidate_sites.csv` | One row per candidate site, with blank `folio_number` and `registered_owner` columns to fill during the pilot. |
| `<county>_points.csv` | Every point from every source, with its source record link. |
| `<county>_name_leads.csv` | Names to search in the Land Registry Names Index: the entity list, school patrons, OpenStreetMap operators and county charities, each with where it was found. |
| `<county>_unplaced_history.csv` | Report institutions not yet placed on the map. |
| `<county>_source_summary.csv` | Points per source. |
| `charity_name_leads.csv` | Catholic-sounding charity names nationally, when the register can be downloaded. |

To add a county, add an entry to `COUNTIES` in `wotl/config.py`: its
OpenStreetMap area names, the names NIAH files it under, a pattern that
matches it in addresses, and any council Records of Protected Structures on
data.gov.ie. Then run `python run_pilot.py --county <Name>`.

## Files

- `wotl/config.py`: per-county settings, source URLs, keyword lists.
- `wotl/sources.py`: one fetcher per source (OpenStreetMap, NIAH, council protected structures, school lists, valuation list, charities register, history seed list).
- `wotl/build.py`: merging points into sites, and drawing the map.
- `wotl/names.py`: name leads for the Land Registry search.
- `data/seed/history_sites.csv`: institutions from the official reports, entered by hand with references.
- `data/seed/entities.csv`: dioceses, congregations and school trusts to search for, per county.
- `tests/test_offline.py`: checks the parsing and merging on made-up records (`python -m pytest tests`).

## Status

The pipeline runs on GitHub Actions (`.github/workflows/build-map.yml` in the
website repo runs every county and commits the outputs and maps).

### Louth (first live run 28 October 2026)

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
