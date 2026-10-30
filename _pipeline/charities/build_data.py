"""Build layout + compact JSON for the charities landscape graphic.

Usage: python3 -I build_data.py <register.xlsx> <school_matches.csv> <out.json>

school_matches.csv comes from match_schools.py and links school charities to
the Department of Education school lists (ethos and patron).
"""
import json
import re
import math
import sys
from collections import Counter
from itertools import combinations

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

SRC, MATCHES, OUT = sys.argv[1:4]
SCHOOLS_AS_OF = "2025/26 school year (Department of Education, final data as of 26 June 2026)"

SHORT = {
    "Advancement of religion": "Religion",
    "Promotion of religious or racial harmony and harmonious community relations": "Religious & racial harmony",
    "Advancement of education": "Education",
    "Advancement of the arts, culture, heritage or sciences": "Arts, culture & heritage",
    "Promotion of civic responsibility or voluntary work": "Civic responsibility & volunteering",
    "Advancement of community development, including rural or urban regeneration": "Community development",
    "Advancement of community welfare including the relief of those in need by reason of youth, age, ill-health, or disability": "Community welfare",
    "Integration of those who are disadvantaged, and the promotion of their full participation, in society": "Social inclusion",
    "Relief of poverty or economic hardship": "Relief of poverty",
    "Promotion of health, including the prevention or relief of sickness, disease or human suffering": "Health",
    "Advancement of conflict resolution or reconciliation": "Conflict resolution",
    "Advancement of the efficient and effective use of the property of charitable organisations": "Use of charity property",
    "Prevention or relief of suffering of animals": "Animal welfare",
    "Protection of the natural environment": "Natural environment",
    "Advancement of environmental sustainability": "Environmental sustainability",
}

raw = pd.read_excel(SRC, sheet_name="Public Register", header=None, nrows=1)
effective = raw.iloc[0, 1].date().isoformat()
df = pd.read_excel(SRC, sheet_name="Public Register", header=1, dtype=str)
df = df.dropna(subset=["Registered Charity Number"])
total_all = len(df)
df = df[df["Status"] == "Registered"].copy()
registered = len(df)

def purposes(s):
    if not isinstance(s, str):
        return []
    out = [x.strip() for x in s.split(";") if x.strip()]
    return list(dict.fromkeys(p for p in out if p in SHORT))

df["P"] = df["Charitable Purpose"].apply(purposes)
no_purpose = int((df["P"].str.len() == 0).sum())
df = df[df["P"].str.len() > 0].copy()

count = Counter(p for ps in df["P"] for p in ps)
co = Counter()
for ps in df["P"]:
    for a, b in combinations(sorted(ps), 2):
        co[(a, b)] += 1

# Hub order: start at religion, greedily walk to the purpose it shares most charities with
# (normalised by size), so purposes that often appear together sit side by side.
def affinity(a, b):
    k = tuple(sorted((a, b)))
    return co[k] / math.sqrt(count[a] * count[b])

order = ["Advancement of religion"]
left = set(SHORT) - set(order)
while left:
    nxt = max(left, key=lambda p: affinity(order[-1], p))
    order.append(nxt)
    left.remove(nxt)
# the greedy walk strands Animal welfare at the end; park it beside the other environment purposes
order.remove("Prevention or relief of suffering of animals")
order.insert(order.index("Protection of the natural environment"), "Prevention or relief of suffering of animals")
idx = {p: i for i, p in enumerate(order)}

S = 4.0  # spacing between dot centres
single = Counter(ps[0] for ps in df["P"] if len(ps) == 1)
disc_r = {p: math.sqrt(single[p] * S * S / math.pi) * 1.05 + 6 for p in order}

# angular share per hub proportional to its outer disc diameter (+ margin), religion centred at top
weights = np.array([2 * disc_r[p] + 40 for p in order])
spans = weights / weights.sum() * 2 * math.pi
starts = np.concatenate([[0], np.cumsum(spans)[:-1]])
angles = starts + spans / 2 - spans[0] / 2 - math.pi / 2  # religion at 12 o'clock
R_IN = 230
hub_xy = {p: (R_IN * math.cos(a), R_IN * math.sin(a)) for p, a in zip(order, angles)}
disc_xy = {}
for p, a in zip(order, angles):
    d = R_IN + 30 + disc_r[p]
    disc_xy[p] = (d * math.cos(a), d * math.sin(a))

GOLD = math.pi * (3 - math.sqrt(5))

def sunflower(n, cx, cy, spacing):
    pts = []
    for k in range(n):
        r = spacing * math.sqrt(k + 0.5) * 0.53
        t = k * GOLD
        pts.append((cx + r * math.cos(t), cy + r * math.sin(t)))
    return pts

# sort so the same purpose combination is contiguous; inside a group, larger objects text first (arbitrary but stable)
m = pd.read_csv(MATCHES, dtype=str).set_index("charity_number")
df["ethos"] = df["Registered Charity Number"].map(m["ethos"]).fillna("")
df["patron"] = df["Registered Charity Number"].map(m["patron"]).fillna("")
df["school"] = df["Registered Charity Number"].map(m["school_name"]).fillna("")
df["catholic"] = df["ethos"].eq("Catholic")
# Community and comprehensive schools often have an ETB and a Catholic bishop or order as joint patrons,
# with an inter-denominational ethos. Church of Ireland bishops are marked "COI" in the patron field.
ORDERS = (r"sisters|brothers|congregation|society of jesus|jesuit|mercy|presentation|carmelite|edmund rice|ceist|erst|loreto|"
          r"le ch[eé]ile|spiritan|des places|marist|salesian|ursuline|dominican|vincentian|franciscan|capuchin|patrician|"
          r"de la salle|catholic|st louis|holy child|holy faith|friars|redemptorist")
def joint_catholic(ethos, patron):
    if ethos in ("", "Catholic", "Church Of Ireland", "Presbyterian", "Methodist", "Quaker", "Jewish", "Muslim"):
        return False
    p = patron.lower()
    return bool(re.search(ORDERS, p)) or p.count("bishop") > p.count("coi")
df["joint"] = [joint_catholic(e, p) for e, p in zip(df["ethos"], df["patron"])]
# inside each cluster, Catholic-patron schools fill the centre so they read as one core
df["key"] = df["P"].apply(lambda ps: tuple(sorted(ps, key=idx.get)))
df["school_rank"] = np.where(df["catholic"], 0, np.where(df["joint"], 1, 2))
df = df.sort_values(["key", "school_rank", "Registered Charity Name"]).reset_index(drop=True)

pos = np.zeros((len(df), 2))
target = np.zeros((len(df), 2))
fixed = np.zeros(len(df), bool)
for key, g in df.groupby("key", sort=False):
    if len(key) == 1:
        cx, cy = disc_xy[key[0]]
        fixed[g.index] = True
    else:
        xs = np.array([hub_xy[p] for p in key])
        cx, cy = xs.mean(0) * 0.92
    pts = sunflower(len(g), cx, cy, S)
    pos[g.index] = pts
    target[g.index] = (cx, cy)

# relax the interior (multi-purpose) dots so none overlap
movable = ~fixed
for it in range(160):
    tree = cKDTree(pos)
    pairs = tree.query_pairs(S * 0.9, output_type="ndarray")
    pairs = pairs[movable[pairs[:, 0]] | movable[pairs[:, 1]]]
    if len(pairs) == 0:
        break
    d = pos[pairs[:, 1]] - pos[pairs[:, 0]]
    dist = np.linalg.norm(d, axis=1)
    dist[dist == 0] = 1e-3
    push = ((S - dist) / dist / 2)[:, None] * d * 0.6
    delta = np.zeros_like(pos)
    np.add.at(delta, pairs[:, 0], -push)
    np.add.at(delta, pairs[:, 1], push)
    delta[fixed] = 0
    pos += delta
    pos[movable] += (target[movable] - pos[movable]) * 0.01
print("relax iterations", it, "remaining overlaps", len(pairs))

def county(addr):
    if not isinstance(addr, str):
        return ""
    parts = [x.strip() for x in addr.split(",") if x.strip()]
    if len(parts) >= 2 and parts[-1] in ("Republic of Ireland", "Ireland", "Northern Ireland"):
        return parts[-2]
    return parts[-1] if parts else ""

def trim(s, n=420):
    if not isinstance(s, str):
        return ""
    s = " ".join(s.replace("\x7f", " ").split())
    return s if len(s) <= n else s[: n].rsplit(" ", 1)[0].rstrip(",;:.-") + "…"

rel = "Advancement of religion"
bm = df["Governing Form"].str.contains("Board of Management", case=False, na=False)
is_rel = df["P"].apply(lambda ps: rel in ps)
stats = {
    "effective": effective,
    "downloaded": "2026-10-30",
    "rows_in_file": int(total_all),
    "registered": int(registered),
    "no_purpose": no_purpose,
    "shown": int(len(df)),
    "religion": int(is_rel.sum()),
    "religion_only": int((is_rel & (df["P"].str.len() == 1)).sum()),
    "religion_and_education": int(df["P"].apply(lambda ps: rel in ps and "Advancement of education" in ps).sum()),
    "school_boards": int(bm.sum()),
    "school_boards_religion": int((bm & is_rel).sum()),
    "schools_as_of": SCHOOLS_AS_OF,
    "school_charities": int(len(m)),
    "catholic_schools": int(df["catholic"].sum()),
    "catholic_schools_religion": int((df["catholic"] & is_rel).sum()),
    "joint_catholic_schools": int(df["joint"].sum()),
    "catholic_schools_education_only": int((df["catholic"] & df["P"].apply(lambda ps: ps == ["Advancement of education"])).sum()),
    "education": int(df["P"].apply(lambda ps: "Advancement of education" in ps).sum()),
}
print(stats)

hubs = [
    {"id": i, "full": p, "short": SHORT[p], "n": count[p], "single": single[p],
     "hx": round(hub_xy[p][0], 1), "hy": round(hub_xy[p][1], 1),
     "dx": round(disc_xy[p][0], 1), "dy": round(disc_xy[p][1], 1), "dr": round(disc_r[p], 1)}
    for i, p in enumerate(order)
]
patrons = sorted(set(df["patron"]) - {""})
pidx = {p: i for i, p in enumerate(patrons)}
ethos_codes = sorted(set(df["ethos"]) - {""})
eidx = {e: i for i, e in enumerate(ethos_codes)}
recs = []
for i, r in df.iterrows():
    mask = sum(1 << idx[p] for p in r["P"])
    recs.append([
        round(float(pos[i, 0]), 1), round(float(pos[i, 1]), 1), mask,
        r["Registered Charity Name"], r["Registered Charity Number"], county(r["Primary Address"]),
        r["Governing Form"] if isinstance(r["Governing Form"], str) else "",
        trim(r["Charitable Objects"]),
        # school ethos and patron from the Department of Education list (-1 = not a matched school)
        eidx.get(r["ethos"], -1), pidx.get(r["patron"], -1), r["school"].title() if r["school"] else "",
        1 if r["catholic"] else 2 if r["joint"] else 0,  # 1 Catholic ethos, 2 joint Catholic patronage
    ])
with open(OUT, "w") as f:
    json.dump({"stats": stats, "hubs": hubs, "ethos": ethos_codes, "patrons": patrons, "c": recs}, f, ensure_ascii=False, separators=(",", ":"))
print("wrote", OUT, len(recs))
