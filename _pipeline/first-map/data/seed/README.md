# Industrial schools

`industrial_schools.csv` is the national reference list of the institutions
the Ryan Report investigated, taken from Industrial Memories' list of
institutions (https://industrialmemories.ucd.ie/ryan-report/report/institutions),
plus Passage West from its Transfer Graph 7 and other Dublin industrial
schools from Wikipedia's list. One row per institution: its order, town and
county, its Ryan Report pages, and what is known about the site today
(`current_occupier`, `sale_or_transfer`, `sale_date`, `sale_price`), each with
the source it came from. Blank means not yet researched or not found.
Every county run picks up its own rows; `church_run = no` rows (Marlborough
House, run by the State) are kept but not mapped.

The orders that ran these schools (Christian Brothers, Rosminians, Brothers of
Charity, Presentation Brothers, Oblates of Mary Immaculate, Sisters of Mercy,
Sisters of Charity, Dominican Sisters, Daughters of the Cross) are in
`entities.csv` for every county.

# History seed list

`history_sites.csv` holds other institutions named in official reports
(Magdalene laundries, mother and baby homes), one row each.
Only add what a report or peer-reviewed work states, with its reference.

- **Ryan Report:** browse by institution on [Industrial Memories](https://industrialmemories.ucd.ie/).
- **McAleese Report (Magdalen laundries):** [gov.ie](https://www.gov.ie/en/collection/a69a14-report-of-the-inter-departmental-committee-to-establish-the-facts-of).
- **Mother and Baby Homes final report:** [gov.ie](https://www.gov.ie/en/publication/d4b3d-final-report-of-the-commission-of-investigation-into-mother-and-baby-homes/).

Rows with blank `lat`/`lon` stay in the tables but are left off the map.
Fill coordinates by finding the site (NIAH, historic OS maps on GeoHive), not
by geocoding the town, so a point never lands on the wrong building.

Until then, the `anchor` column can place a row on another source's record of
the same building: it is a regular expression matched against the names of
NIAH, OpenStreetMap and protected-structure records. A row is placed only when
every match lies within 250 m of the others, and its popup says which record
it was placed on, so it can be checked. Rows that stay unplaced are listed in
`outputs/<county>_unplaced_history.csv`.

# Entity list

`entities.csv` lists the bodies whose names are worth searching in the Land
Registry Names Index, one row each, with the counties they matter for (`all`
for national trusts). These are leads, not legal names: confirm each against
the Charities Register or the CRO, and add every variant found on a folio.
The pipeline adds school patrons, OpenStreetMap operators and county charities
to it and writes `outputs/<county>_name_leads.csv`.
