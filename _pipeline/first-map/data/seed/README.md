# History seed list

`history_sites.csv` holds institutions named in official reports, one row each.
Only add what a report or peer-reviewed work states, with its reference.

- **Ryan Report:** browse by institution on [Industrial Memories](https://industrialmemories.ucd.ie/).
- **McAleese Report (Magdalen laundries):** [gov.ie](https://www.gov.ie/en/collection/a69a14-report-of-the-inter-departmental-committee-to-establish-the-facts-of).
- **Mother and Baby Homes final report:** [gov.ie](https://www.gov.ie/en/publication/d4b3d-final-report-of-the-commission-of-investigation-into-mother-and-baby-homes/).

Rows with blank `lat`/`lon` stay in the tables but are left off the map.
Fill coordinates by finding the site (NIAH, historic OS maps on GeoHive), not
by geocoding the town, so a point never lands on the wrong building.
