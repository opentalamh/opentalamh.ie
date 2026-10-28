"""Settings for the first-attempt map. Change COUNTY to run another county."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"          # cached downloads, safe to delete
SEED_DIR = ROOT / "data" / "seed"        # hand-curated inputs (history sites)
OUT_DIR = ROOT / "outputs"

COUNTY = "Louth"

# OpenStreetMap: Irish counties are admin_level 6, named "County <Name>".
OSM_AREA_NAME = f"County {COUNTY}"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# National Inventory of Architectural Heritage (ArcGIS feature service, layer 0).
NIAH_QUERY_URL = (
    "https://services-eu1.arcgis.com/HyjXgkV6KGMSF3jt/ArcGIS/rest/services/"
    "NIAHBuildingsOpenData/FeatureServer/0/query"
)

# data.gov.ie CKAN API, used to find the current download link for a dataset.
CKAN_API = "https://data.gov.ie/api/3/action"
SCHOOL_DATASETS = ["primary-schools", "post-primary-schools"]

# Charities Regulator public register (XLSX). The link has moved before;
# if it fails, download the register by hand from charitiesregulator.ie
# and save it as data/raw/public-register-of-charities.xlsx.
CHARITIES_XLSX_URL = (
    "https://www.charitiesregulator.ie/media/5rrnldzg/public-register-of-charities.xlsx"
)

# Tailte Éireann valuation API. Experimental: the filter parameter names are
# not documented publicly, so results are filtered again on our side.
VALUATION_API = "https://opendata.tailte.ie/api/Property/GetProperties"
VALUATION_LOCAL_AUTHORITY = f"{COUNTY.upper()} COUNTY COUNCIL"

USER_AGENT = "who-owns-the-land-research/0.1 (first-attempt map)"

# Points from different sources closer than this are treated as one site.
MERGE_RADIUS_M = 100

# Words that mark a building or body as plausibly Catholic. Deliberately broad:
# every hit is a lead (grade D), never a finding.
CATHOLIC_TERMS = [
    r"\bcatholic\b", r"\bR\.?C\.?\b", r"\bdiocese\b", r"\bdiocesan\b",
    r"\barchdiocese\b", r"\bparish\b", r"\bparochial\b", r"\bpresbytery\b",
    r"\bconvent\b", r"\bmonastery\b", r"\bfriary\b", r"\babbey\b",
    r"\bsisters?\b", r"\bbrothers\b", r"\bfathers\b", r"\bcongregation\b",
    r"\bmercy\b", r"\bpresentation\b", r"\bloreto\b", r"\bbrigidine\b",
    r"\bursuline\b", r"\bdominican\b", r"\bfranciscan\b", r"\bjesuit\b",
    r"\bredemptorist\b", r"\bmarist\b", r"\bde la salle\b", r"\bchristian brothers\b",
    r"\bedmund rice\b", r"\bgood shepherd\b", r"\bour lady\b", r"\bst\.? ",
    r"\bsaint\b", r"\bholy\b", r"\bsacred heart\b", r"\bceist\b", r"\btrustees?\b",
]

# Words that mark a building as another denomination, so it can be dropped.
OTHER_DENOMINATION_TERMS = [
    r"church of ireland", r"presbyterian", r"methodist", r"quaker",
    r"society of friends", r"baptist", r"unitarian", r"synagogue", r"mosque",
]

# NIAH "Original Use" / "In Use As" values that matter for Church property.
NIAH_RELEVANT_USES = [
    "church", "chapel", "convent", "nunnery", "presbytery", "parochial house",
    "monastery", "friary", "abbey", "school", "seminary", "college", "orphanage",
    "industrial school", "reformatory", "laundry", "hospital", "workhouse",
    "graveyard", "cemetery", "mortuary chapel", "religious house", "hall",
]
