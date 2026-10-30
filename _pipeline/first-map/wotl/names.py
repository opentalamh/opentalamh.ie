"""Name leads for Land Registry searches: who might hold title in a county.

A Names Index search returns every folio registered to one exact name in one
county, so the unit of work is name x county (see the Method page). This
module gathers candidate names from what the open sources already say:

- the hand-curated entity list (data/seed/entities.csv),
- school patrons in the Department of Education lists,
- `operator` tags on OpenStreetMap sites,
- Catholic-sounding charities with an address in the county.

None of these is a legal owner's name yet. Each is a lead to confirm against
the Charities Register, the CRO or a folio before it goes on the search list.
"""

import json
import re

import pandas as pd

from . import config

NAME_COLUMNS = ["name", "entity_class", "found_in", "count", "note", "status"]


def seed_entities():
    path = config.SEED_DIR / "entities.csv"
    if not path.exists():
        return pd.DataFrame(columns=NAME_COLUMNS)
    e = pd.read_csv(path).fillna("")
    scope = e["counties"].astype(str).str.lower()
    e = e[scope.eq("all") | scope.str.contains(rf"\b{config.COUNTY.lower()}\b", regex=True)]
    return pd.DataFrame({
        "name": e["name"],
        "entity_class": e["entity_class"],
        "found_in": "entity list",
        "count": "",
        "note": (e["variants"].where(e["variants"] == "", "search also: " + e["variants"]) + " " + e["why"]).str.strip(),
        "status": e["status"],
    }, columns=NAME_COLUMNS)


def school_patrons(schools):
    """Patrons of Catholic-ethos schools, with how many schools each holds."""
    if schools.empty:
        return pd.DataFrame(columns=NAME_COLUMNS)
    patron = schools["raw_use"].astype(str).str.extract(r"patron:\s*(.+)$", expand=False).str.strip()
    patron = patron[patron.notna() & ~patron.str.lower().isin(["", "nan", "none"])]
    counts = patron.str.title().value_counts()
    return pd.DataFrame({
        "name": counts.index,
        "entity_class": "school patron",
        "found_in": "Dept of Education school lists",
        "count": counts.values,
        "note": "schools in the county with this patron; the patron is not always the landowner",
        "status": "lead",
    }, columns=NAME_COLUMNS)


def osm_operators(osm):
    """`operator` tags on Catholic or unmarked OpenStreetMap sites."""
    ops = []
    for raw in osm.get("raw_use", pd.Series(dtype=str)):
        try:
            op = json.loads(raw).get("operator")
        except (TypeError, ValueError):
            continue
        if op:
            ops.append(op.strip())
    if not ops:
        return pd.DataFrame(columns=NAME_COLUMNS)
    counts = pd.Series(ops).value_counts()
    return pd.DataFrame({
        "name": counts.index,
        "entity_class": "operator",
        "found_in": "OpenStreetMap operator tag",
        "count": counts.values,
        "note": "volunteer-entered; often the parish or order that runs the site",
        "status": "lead",
    }, columns=NAME_COLUMNS)


def county_charities(charities):
    if charities.empty or "in_county" not in charities:
        return pd.DataFrame(columns=NAME_COLUMNS)
    c = charities[charities["in_county"]]
    return pd.DataFrame({
        "name": c["name"],
        "entity_class": "charity",
        "found_in": "Charities Regulator register",
        "count": "",
        "note": "registered charity number " + c.get("charity_number", pd.Series("", index=c.index)).astype(str)
                + "; match: " + c.get("catholic_match", pd.Series("", index=c.index)).astype(str)
                + " (" + c.get("matched_terms", pd.Series("", index=c.index)).astype(str) + ")",
        "status": "lead",
    }, columns=NAME_COLUMNS)


def name_leads(schools, osm, charities):
    frames = [seed_entities(), school_patrons(schools), osm_operators(osm), county_charities(charities)]
    leads = pd.concat([f for f in frames if not f.empty], ignore_index=True) \
        if any(not f.empty for f in frames) else pd.DataFrame(columns=NAME_COLUMNS)
    # One row per name: keep the first (seed entries come first) and carry
    # over a count and source found for the same name elsewhere.
    key = leads["name"].astype(str).str.lower().map(lambda s: re.sub(r"[^a-z0-9]+", " ", s).strip())
    out = []
    for _, g in leads.groupby(key, sort=False):
        row = g.iloc[0].copy()
        counts = g["count"][g["count"].astype(str) != ""]
        if len(counts):
            row["count"] = counts.iloc[0]
        row["found_in"] = "; ".join(dict.fromkeys(g["found_in"]))
        out.append(row)
    return pd.DataFrame(out, columns=NAME_COLUMNS).reset_index(drop=True)
