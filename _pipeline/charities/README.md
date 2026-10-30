# Charities landscape graphic

Builds `maps/charities_landscape.html`, shown at the bottom of the [Map page](../../map.qmd): every registered charity as a dot, clustered by charitable purpose, with religion and Catholic-patron schools highlighted.

## Sources

- Charities Regulator, Public Register of Charitable Organisations. Effective date 26 October 2026, downloaded by hand on 30 October 2026 (the Regulator refuses automated downloads). About 37 MB, not kept in this repo.
- Department of Education, Data on Individual Schools: primary (mainstream and special) and post-primary, 2025/26 school year, final data as of 26 June 2026. These give each school's ethos and patron. The same files the first-map pipeline downloads into `first-map/data/raw/`.

## Build

    pip install pandas openpyxl numpy scipy rapidfuzz unidecode
    python3 -I match_schools.py register.xlsx primary-schools.xlsx post-primary-schools.xlsx outputs/school_matches.csv
    python3 -I build_data.py register.xlsx outputs/school_matches.csv data.json
    python3 -I assemble.py template.html data.json ../../maps/charities_landscape.html

When you rebuild from a newer download, update the `downloaded` date and `SCHOOLS_AS_OF` in `build_data.py`.

## School matching

The register has no roll numbers, so `match_schools.py` matches school charities to the school lists by name within the same county. It tries boards of management and charities classed as primary, secondary or special-needs education, plus education charities with a school-like name (many voluntary secondary schools register as a company or trust), which need a closer match. It takes a weaker name match only when the school's address towns appear in the charity's address, never pairs a boys' and a girls' school or a primary and a post-primary one, and matches each school once.

On the 26 Oct 2026 register it matched 3,241 of 4,129 school charities: 2,762 to a Catholic-ethos school (291 of the 337 Catholic secondary schools), and 83 to a school with a Catholic bishop or order as joint patron, mostly community schools with an ETB. A spot check found most of the weaker matches correct, but some will be wrong: check `outputs/school_matches.csv` (the `name_score` and `town_match` columns) before quoting a single school.
