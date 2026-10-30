"""Match school charities on the register to the Department of Education school lists.

The register has no roll numbers, so schools are matched on name within the
same county, with a bonus when the school's address towns appear in the
charity's address. Each school is matched to at most one charity.

Usage: python3 -I match_schools.py <register.xlsx> <primary.xlsx> <post-primary.xlsx> <out.csv>
"""
import re
import sys

import pandas as pd
from rapidfuzz import fuzz
from unidecode import unidecode

REG, PRI, POST, OUT = sys.argv[1:5]

# words that say "school" without naming one
GENERIC = {
    "n", "s", "ns", "sn", "national", "school", "schools", "scoil", "naisiunta", "board", "of", "management",
    "the", "and", "primary", "junior", "senior", "infant", "infants", "mxd", "mixed", "boys", "girls",
    "b", "g", "bns", "gns", "j", "jns", "sns", "clg", "company", "limited", "by", "guarantee", "ltd", "co",
    "na", "an", "ag", "a", "ar", "de", "le", "sc", "nat", "sch", "college", "secondary", "post",
    "convent", "special", "gaelscoil",
    # saints' titles are shared by hundreds of schools, so they cannot identify one
    "saint", "saints", "naomh", "naofa", "naoimh", "nais", "jnr", "snr", "jun", "sen", "bun", "bunscoil", "mhuire_",
}
BOYS, GIRLS = {"boys", "b", "bns", "buachailli"}, {"girls", "g", "gns", "cailini"}
EXPAND = {"st": "saint", "sts": "saints", "naoimh": "naomh", "mhuire": "muire", "mhichil": "michil", "phadraig": "padraig"}


def norm(s):
    s = unidecode(str(s)).lower().replace("&", " and ")
    s = re.sub(r"\b(n|s)\.\s*(s|n)\.?", " ns ", s)
    s = re.sub(r"\bc\.?\s?b\.?\s?s\b\.?", " christian brothers ", s)
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return [EXPAND.get(t, t) for t in s.split()]


def core(s):
    return " ".join(t for t in norm(s) if t not in GENERIC)


def county_key(s):
    s = unidecode(str(s)).lower()
    s = re.sub(r"^(co\.?|county)\s*", "", s.strip())
    s = re.sub(r"[^a-z ]", " ", s).split()
    return s[0] if s else ""


def charity_county(addr):
    parts = [p.strip() for p in str(addr).split(",") if p.strip()]
    if parts and parts[-1] in ("Republic of Ireland", "Ireland"):
        parts = parts[:-1]
    return county_key(parts[-1]) if parts else ""


# ---- schools ----
def load(path, sheet, cols):
    d = pd.read_excel(path, sheet_name=sheet, header=1, dtype=str)
    if cols["name"] not in d.columns:  # Special sheet has its header on the first row
        d = pd.read_excel(path, sheet_name=sheet, header=0, dtype=str)
    d = d.dropna(subset=[cols["roll"]])
    out = pd.DataFrame({
        "roll": d[cols["roll"]].str.strip(),
        "school_name": d[cols["name"]].str.strip(),
        "county": d[cols["county"]].map(county_key),
        "addr": d[[c for c in d.columns if re.match(r"address", str(c), re.I)]].fillna("").agg(" ".join, axis=1),
        "ethos": d[cols["ethos"]].str.strip().str.title(),
        "patron": d[cols["patron"]].fillna("").str.strip() if cols.get("patron") in d.columns else "",
        "level": cols["level"],
    })
    return out


pri_cols = dict(roll="Roll Number", name="Official Name", county="County Description", ethos="Ethos Description", patron="Patron", level="Primary")
schools = pd.concat([
    load(PRI, "Mainstream", pri_cols),
    load(PRI, "Special", {**pri_cols, "level": "Special"}),
    load(POST, "School Lists", dict(roll="Roll Number", name="Official School Name", county="County", ethos="Ethos", patron="Patron", level="Post-primary")),
], ignore_index=True).drop_duplicates("roll")
schools["core"] = schools["school_name"].map(core)
schools["towns"] = schools["addr"].map(lambda a: {t for t in norm(a) if len(t) > 3 and t not in GENERIC and t not in ("dublin", "road", "street", "county")})

# ---- school charities ----
df = pd.read_excel(REG, sheet_name="Public Register", header=1, dtype=str).dropna(subset=["Registered Charity Number"])
df = df[df["Status"] == "Registered"]
cls = df["Charity Classification: Primary [Secondary (Sub)]"].fillna("")
is_board = df["Governing Form"].str.contains("Board of Management", case=False, na=False) | cls.str.contains(r"Primary level|Secondary level|Special needs education", case=False)
# Many voluntary secondary schools register as a company or trust, not as a board of management.
# Education charities with a school-like name are tried too, but need a closer match.
school_word = r"college|col[aá]iste|school|scoil|secondary|academy|\bc\.?\s?b\.?\s?s\b|convent|gaelcholaiste|pobalscoil|meanscoil|ardscoil"
is_named = (df["Charitable Purpose"].fillna("").str.contains("Advancement of education")
            & df["Registered Charity Name"].fillna("").str.contains(school_word, case=False, regex=True))
is_school = is_board | is_named
ch = df[is_school].copy()
ch["strict"] = ~is_board[is_school]
ch["county"] = ch["Primary Address"].map(charity_county)
form = ch["Governing Form"].fillna("") + " " + cls[is_school]
ch["level"] = form.map(lambda f: "Post-primary" if re.search(r"post-primary|secondary", f, re.I) else "Primary" if re.search(r"primary", f, re.I) else "")
ch["addr_tokens"] = (ch["Primary Address"].fillna("") + " " + ch["Also Known As"].fillna("")).map(lambda a: set(norm(a)))
names = ch["Registered Charity Name"].fillna("") + "|" + ch["Also Known As"].fillna("")

def sex(tokens):
    t = set(tokens)
    return "b" if t & BOYS else "g" if t & GIRLS else ""


cands = []
by_county = {k: g for k, g in schools.groupby("county")}
for (i, r), nm in zip(ch.iterrows(), names):
    # an address that doesn't end in a county is tried against every school, on a strict match
    pool = by_county.get(r["county"])
    if pool is None:
        pool, r = schools, r.copy()
        r["strict"] = True
    variants = [core(v) for v in nm.split("|") if v.strip()]
    variants = [v for v in variants if v]
    csex = sex(norm(nm))
    for j, s in pool.iterrows():
        if csex and sex(norm(s["school_name"])) not in ("", csex):
            continue
        if r["level"] and (s["level"] == "Post-primary") != (r["level"] == "Post-primary"):
            continue
        name_score = max((fuzz.token_sort_ratio(v, s["core"]) for v in variants if s["core"]), default=0)
        # a charity named after its townland ("Knocklong NS") against an Irish-named school in Knocklong
        place = any(set(v.split()) and set(v.split()) <= s["towns"] for v in variants) or (
            bool(s["core"]) and set(s["core"].split()) <= r["addr_tokens"])
        town = len(s["towns"] & r["addr_tokens"]) > 0
        # one name inside the other: "Coláiste Mhuire (Baile Átha Cliath)" and "Coláiste Mhuire"
        sc = set(s["core"].split())
        subset = any(sc and (sc <= set(v.split()) or set(v.split()) <= sc) and any(len(t) > 4 for t in sc & set(v.split())) for v in variants)
        if r["strict"]:
            ok = name_score == 100 or (name_score >= 92 and town)
        else:
            ok = name_score >= 95 or (name_score >= 86 and town) or (place and town) or (subset and town)
        if subset and town:
            name_score = max(name_score, 88)
        if ok:
            score = max(name_score, 90 if place else 0) + (10 if town else 0)
            cands.append((score, name_score, town, r["Registered Charity Number"], s["roll"]))

cands.sort(reverse=True)
used_c, used_s, rows = set(), set(), []
for score, name_score, town, rcn, roll in cands:
    if rcn in used_c or roll in used_s:
        continue
    used_c.add(rcn); used_s.add(roll)
    rows.append((rcn, roll, score, name_score, town))
m = pd.DataFrame(rows, columns=["charity_number", "roll", "score", "name_score", "town_match"])
m = m.merge(schools[["roll", "school_name", "level", "ethos", "patron"]], on="roll")
m = m.merge(ch[["Registered Charity Number", "Registered Charity Name", "Primary Address"]], left_on="charity_number", right_on="Registered Charity Number").drop(columns="Registered Charity Number")
m.to_csv(OUT, index=False)
print(f"school charities {len(ch)}, schools {len(schools)}, matched {len(m)} ({len(m)/len(ch):.0%} of school charities)")
print("matched Catholic", (m.ethos == "Catholic").sum(), "of", (schools.ethos == "Catholic").sum(), "Catholic schools")
print(m.ethos.value_counts())
