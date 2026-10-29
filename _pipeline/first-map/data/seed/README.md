# History seed list

`history_sites.csv` holds institutions named in official reports, one row each.
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
