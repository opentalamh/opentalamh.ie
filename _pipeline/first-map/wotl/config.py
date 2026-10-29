"""Settings for the first-attempt map.

Each county has an entry in COUNTIES. Pick one with `python run_pilot.py
--county Dublin`, the WOTL_COUNTY environment variable, or set_county() in a
notebook. Everything county-specific below is set from that entry.
"""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"          # cached downloads, safe to delete
SEED_DIR = ROOT / "data" / "seed"        # hand-curated inputs (history sites)
OUT_DIR = ROOT / "outputs"

# Per-county settings. Dublin is split into four local authorities (Dublin
# City, Fingal, South Dublin, Dún Laoghaire-Rathdown), and several sources
# file records under the local authority rather than the county, so each
# setting is a list of the names a source might use.
COUNTIES = {
    "Louth": {
        # OpenStreetMap administrative areas whose union is the county.
        "osm_areas": ["County Louth"],
        # Values to look for in NIAH's COUNTY field.
        "niah_terms": ["LOUTH"],
        # Matches the county in school, charity and address columns.
        "county_pattern": r"louth",
        # Tailte Éireann valuation list, one download per local authority.
        "valuation_authorities": ["LOUTH COUNTY COUNCIL"],
        # Council Records of Protected Structures on data.gov.ie (dataset ids).
        "rps_datasets": {},
        "merge_radius_m": 100,
        "site_prefix": "LO",
        # (south, west, north, east): points outside are dropped, since an
        # area name can also match a place abroad.
        "bbox": (53.70, -6.75, 54.15, -6.00),
    },
    "Dublin": {
        "osm_areas": [
            "County Dublin", "Dublin City", "Fingal", "South Dublin",
            "Dún Laoghaire-Rathdown", "Dún Laoghaire–Rathdown",
        ],
        "niah_terms": ["DUBLIN", "FINGAL", "RATHDOWN"],
        "county_pattern": r"dublin|fingal|rathdown|d[uú]n laoghaire",
        # Skipped: the Louth run found no religious uses among 4,477 rated
        # properties (Church property is mostly exempt), and the four Dublin
        # lists are far larger. Add the authority names here to try anyway.
        "valuation_authorities": [],
        "rps_datasets": {
            # The older "dublin-city-record-of-protected-structures" entry links only to a web page.
            "Dublin City Council": "record-protected-structures-dcc",
            "Fingal County Council": "development-plan-2023-2029-rps-record-of-protected-structures-fcc2",
            "South Dublin County Council": "record-of-protected-structures-south-dublin-county-development-plan-2022-to-2028-sdcc1",
            "Dún Laoghaire-Rathdown County Council": "development-plan-2022-2028-protected-structures-dlr",
        },
        # Dense city streets: a smaller radius stops neighbouring sites chaining together.
        "merge_radius_m": 50,
        "site_prefix": "DU",
        "bbox": (53.15, -6.55, 53.65, -5.95),
    },
}

COUNTY = None  # set by set_county() at the bottom of this file


def set_county(name):
    """Point every county-specific setting at one entry of COUNTIES."""
    global COUNTY, OSM_AREA_NAMES, NIAH_COUNTY_TERMS, COUNTY_PATTERN
    global VALUATION_LOCAL_AUTHORITIES, RPS_DATASETS, MERGE_RADIUS_M, SITE_PREFIX, BBOX
    key = next((k for k in COUNTIES if k.lower() == name.strip().lower()), None)
    if key is None:
        raise ValueError(f"unknown county {name!r}; add it to COUNTIES (have {', '.join(COUNTIES)})")
    c = COUNTIES[key]
    COUNTY = key
    OSM_AREA_NAMES = c["osm_areas"]
    NIAH_COUNTY_TERMS = c["niah_terms"]
    COUNTY_PATTERN = c["county_pattern"]
    VALUATION_LOCAL_AUTHORITIES = c["valuation_authorities"]
    RPS_DATASETS = c["rps_datasets"]
    MERGE_RADIUS_M = c["merge_radius_m"]
    SITE_PREFIX = c["site_prefix"]
    BBOX = c["bbox"]
    return COUNTY


OVERPASS_URL = "https://overpass-api.de/api/interpreter"
# Tried in order when the main server is busy (it often answers 502/504).
OVERPASS_MIRRORS = [
    OVERPASS_URL,
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]

# National Inventory of Architectural Heritage (ArcGIS feature service, layer 0).
NIAH_QUERY_URL = (
    "https://services-eu1.arcgis.com/HyjXgkV6KGMSF3jt/ArcGIS/rest/services/"
    "NIAHBuildingsOpenData/FeatureServer/0/query"
)

# data.gov.ie CKAN API, used to find the current download link for a dataset.
CKAN_API = "https://data.gov.ie/api/3/action"

# Department of Education "Data on individual schools" (gov.ie), the current
# lists with ethos. New links appear each school year on the collection pages.
SCHOOL_LISTS = {
    "primary-schools": (
        "https://assets.gov.ie/static/documents/8e1b86ab/Data_on_Individual_Schools_Mainstream..xlsx",
        "https://www.gov.ie/en/department-of-education/collections/primary-schools-enrolment-figures/",
    ),
    "post-primary-schools": (
        "https://assets.gov.ie/static/documents/d5fbb204/Data_on_Individual_Schools_post_primary..xlsx",
        "https://www.gov.ie/en/department-of-education/collections/post-primary-schools-enrolment-figures/",
    ),
}
# Older lists (2016/17) on data.gov.ie that carry coordinates, joined on roll
# number when the current list has none.
SCHOOL_LOCATION_DATASETS = ["list-of-primary-schools", "post-primary-schools-list-2017"]

# Charities Regulator public register. The file name changes with each
# release, so the current link is looked up on data.gov.ie. If the download is
# refused, save the register by hand as data/raw/public-register-of-charities.xlsx.
CHARITIES_DATASET = "register-of-charities-in-ireland"

# Tailte Éireann valuation API. Experimental: the filter parameter names are
# not documented publicly, so results are filtered again on our side.
VALUATION_API = "https://opendata.tailte.ie/api/Property/GetProperties"

USER_AGENT = "who-owns-the-land-research/0.1 (first-attempt map)"
# Some publishers refuse requests that do not look like a browser.
BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0",
    "Accept": "text/html,application/xhtml+xml,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,*/*;q=0.8",
    "Accept-Language": "en-IE,en;q=0.8",
}

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

# Uses in a Record of Protected Structures description that matter for Church
# property. Schools, halls and similar only count with a Catholic marker.
RPS_RELEVANT_USES = [
    r"church", r"chapel", r"cathedral", r"pro-cathedral", r"convent", r"presbytery",
    r"parochial", r"monastery", r"friary", r"abbey", r"seminary", r"oratory",
    r"novitiate", r"religious", r"orphanage", r"industrial school", r"magdalen",
    r"laundry", r"school", r"college", r"hospital", r"hall", r"graveyard", r"cemetery",
]

set_county(os.environ.get("WOTL_COUNTY", "Dublin"))
