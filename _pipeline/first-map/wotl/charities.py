"""Pick Catholic bodies out of the Charities Regulator's public register.

The register has no "denomination" field. Two columns help:

- `Charitable Purpose` says whether a charity exists for the advancement of
  religion (or education, and so on), but every faith shares that purpose.
- The name, `Also Known As` and `Charitable Objects` text often say which
  Church, diocese or order a charity belongs to.

So each charity gets a `catholic_match`:

- `explicit`: the text says Catholic, R.C., diocese, canon law or the like.
- `order or devotion`: the purpose includes religion and the text names a
  Catholic order or devotion (Jesuits, Presentation Sisters, Fatima...) without
  saying "Catholic". Most orders' registrations never use the word.
- `named body`: the name is a known Catholic lay body, diocesan agency or an
  order's service company (St Vincent de Paul, Pioneers, Brothers of Charity
  Services...), whatever its purpose. These register for poverty relief, health
  or education, so the religion test misses them.

Charities whose text names another denomination are left out. Every match is
a lead for the name list, not a finding. Trustee names are not copied: Open
Talamh maps organisations, not private individuals.
"""

import re

import pandas as pd

EXPLICIT = [
    r"\bcatholic\b", r"\bR\.\s?C\.", r"\bRC\b", r"\barchdiocese\b", r"\bdiocese of\b", r"\bdiocesan\b",
    r"\bcanon law\b", r"\bholy see\b", r"\bapostolic\b", r"\bpontifical\b", r"\bvatican\b",
]

ORDERS_AND_DEVOTIONS = [
    r"\bsisters? of\b", r"\bbrothers of\b", r"\bfathers\b", r"\bcongregation of\b", r"\bconvent\b",
    r"\bmonastery\b", r"\babbey\b", r"\bfriary\b", r"\bpriory\b", r"\bnovitiate\b", r"\bpresbytery\b",
    r"\bparish\b", r"\bparochial\b",
    r"\bjesuits?\b", r"\bsociety of jesus\b", r"\bmarist\b", r"\bcarmelites?\b", r"\bpresentation\b",
    r"\bmercy\b", r"\bloreto\b", r"\bdominican\b", r"\bfranciscan\b", r"\bcapuchin\b", r"\bpoor clares?\b",
    r"\bredemptorist\b", r"\bvincentian\b", r"\bspiritans?\b", r"\bholy ghost\b", r"\boblates?\b",
    r"\bpassionist\b", r"\bsalesian\b", r"\bchristian brothers\b", r"\bde la salle\b", r"\bursuline\b",
    r"\bbrigidine\b", r"\bcistercian\b", r"\bbenedictine\b", r"\baugustinian\b", r"\brosminian\b",
    r"\bcolumban\b", r"\bkiltegan\b", r"\bsma\b", r"\bsociety of african missions\b", r"\bholy child\b",
    r"\bholy faith\b", r"\bsacred heart\b", r"\bour lady\b", r"\bfatima\b", r"\bknock\b", r"\blourdes\b",
    r"\bparay.le.monial\b", r"\blegion of mary\b", r"\bopus dei\b", r"\bst\.? vincent de paul\b",
    r"\bedmund rice\b", r"\bnano nagle\b", r"\bcatherine mcauley\b",
    r"\bceist\b", r"\ble ch[eé]ile\b", r"\breligious (order|congregation|sisters|brothers|life)\b",
]

# Matched on the charity's name only, whatever its purpose.
NAMED_BODIES = [
    r"vincent de paul", r"\bozanam\b", r"pioneer total abstinence", r"legion of mary", r"legionis mariae",
    r"knights of (st\.? )?columbanus", r"\bcrosscare\b", r"\baccord\b.*marriage", r"catholic youth care",
    r"brothers of charity", r"daughters of charity", r"\bsisters of (mercy|charity|nazareth|the poor)\b",
    r"hospitaller order", r"\bst\.? john of god\b", r"\bbon secours\b", r"\bopus dei\b", r"\btr[oó]caire\b(?!.*\bscoil\b|.*\bs\.? ?n\b)",
    r"\bmater misericordiae\b", r"\bmarino institute\b", r"\bpontifical\b", r"\bparish (centre|hall|pastoral)\b",
]

OTHER_DENOMINATIONS = [
    r"church of ireland", r"presbyterian", r"methodist", r"quaker", r"society of friends", r"baptist",
    r"unitarian", r"lutheran", r"jewish", r"synagogue", r"islam", r"muslim", r"mosque", r"hindu",
    r"buddhis", r"sikh", r"\borthodox\b", r"evangelical", r"pentecostal", r"anglican", r"redeemed christian",
    r"jehovah", r"latter.day saints", r"salvation army", r"bah[aá]'?i",
    # "X Parish Church" is the Church of Ireland's usual naming, as are its united dioceses.
    r"parish church", r"united dioceses", r"dublin and glendalough", r"cork,? cloyne and ross",
    r"cashel.{0,40}ossory", r"limerick.{0,20}killaloe", r"meath and kildare", r"derry and raphoe",
    r"kilmore,? elphin", r"tuam,? (killala|limerick)", r"christian (assembly|fellowship|centre)",
]

COLUMNS = [
    "charity_number", "name", "also_known_as", "status", "classification", "address", "governing_form",
    "cro_number", "charitable_purpose", "charitable_objects", "catholic_match", "matched_terms",
    "purpose_religion", "purpose_education",
]


def read_register(path):
    """The 'Public Register' sheet, plus the register's effective date."""
    raw = pd.read_excel(path, sheet_name="Public Register", header=None)
    effective = None
    if str(raw.iat[0, 0]).strip().lower().startswith("effective date"):
        effective = pd.to_datetime(raw.iat[0, 1]).date().isoformat()
    header = next(i for i in range(10) if raw.iloc[i].astype(str).str.contains("Registered Charity Number").any())
    df = raw.iloc[header + 1:].copy()
    df.columns = [str(c).strip() for c in raw.iloc[header]]
    return df.reset_index(drop=True), effective


def _hits(text, patterns):
    return [m.group(0) for p in patterns for m in [re.search(p, text, re.I)] if m]


def classify(df):
    """Catholic-linked charities from the register, one row each (see module docstring)."""
    col = {c.lower(): c for c in df.columns}

    def get(name):
        c = next((col[k] for k in col if k.startswith(name)), None)
        return df[c].fillna("").astype(str) if c else pd.Series("", index=df.index)

    name, aka, objects, purpose = get("registered charity name"), get("also known as"), get("charitable objects"), get("charitable purpose")
    text = name + " | " + aka + " | " + objects
    religion = purpose.str.contains("advancement of religion", case=False)
    education = purpose.str.contains("advancement of education", case=False)
    rows = []
    for i in df.index:
        t = text[i]
        if _hits(t, OTHER_DENOMINATIONS):
            continue
        explicit = _hits(t, EXPLICIT)
        orders = _hits(t, ORDERS_AND_DEVOTIONS)
        named = _hits(name[i] + " | " + aka[i], NAMED_BODIES)
        if explicit:
            match = "explicit"
        elif orders and religion[i]:
            match = "order or devotion"
        elif named:
            match = "named body"
        else:
            continue
        rows.append({
            "charity_number": get("registered charity number")[i],
            "name": name[i],
            "also_known_as": aka[i],
            "status": get("status")[i],
            "classification": get("charity classification")[i],
            "address": get("primary address")[i],
            "governing_form": get("governing form")[i],
            "cro_number": get("cro number")[i],
            "charitable_purpose": purpose[i],
            "charitable_objects": objects[i],
            "catholic_match": match,
            "matched_terms": "; ".join(dict.fromkeys(h.lower() for h in explicit + orders + named)),
            "purpose_religion": bool(religion[i]),
            "purpose_education": bool(education[i]),
        })
    return pd.DataFrame(rows, columns=COLUMNS)
