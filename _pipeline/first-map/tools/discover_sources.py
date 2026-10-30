"""Print where the open sources currently live, to fix moved links.

Run when a fetcher fails with 404/403: it searches data.gov.ie and the
publishers' pages for current download links. Output goes to stdout.
"""

import re

import requests

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) who-owns-the-land-research/0.1"}


def ckan_search(q):
    print(f"\n### data.gov.ie package_search q={q!r}")
    try:
        r = requests.get("https://data.gov.ie/api/3/action/package_search",
                         params={"q": q, "rows": 15}, headers=UA, timeout=60)
        print("status", r.status_code)
        for p in r.json()["result"]["results"]:
            print(f"- {p['name']} | {p['title']} | modified {p.get('metadata_modified', '')[:10]}")
            for res in p.get("resources", []):
                print(f"    {res.get('format')}: {res.get('url')}")
    except Exception as e:
        print("failed:", e)


def links(url, pattern=r"\.(xlsx|xls|csv|zip)(\?|$)"):
    print(f"\n### links on {url}")
    try:
        r = requests.get(url, headers=UA, timeout=60)
        print("status", r.status_code, "final url", r.url)
        hrefs = set(re.findall(r'href="([^"]+)"', r.text))
        for h in sorted(hrefs):
            if re.search(pattern, h, re.I):
                print("-", h)
    except Exception as e:
        print("failed:", e)


def head(url, **kw):
    try:
        r = requests.get(url, headers=UA, timeout=90, **kw)
        print(f"\n### {url}\nstatus {r.status_code}, {len(r.content):,} bytes, {r.headers.get('content-type')}")
    except Exception as e:
        print(f"\n### {url}\nfailed: {e}")


def ckan_show(dataset_id):
    print(f"\n### data.gov.ie package_show {dataset_id}")
    try:
        r = requests.get("https://data.gov.ie/api/3/action/package_show",
                         params={"id": dataset_id}, headers=UA, timeout=60)
        print("status", r.status_code)
        for res in r.json()["result"].get("resources", []):
            print(f"    {res.get('format')}: {res.get('url')}")
    except Exception as e:
        print("failed:", e)


for q in ("primary schools", "post-primary schools", "schools ethos", "charities register",
          "protected structures dublin", "planning applications dublin"):
    ckan_search(q)
for ds in ("dublin-city-record-of-protected-structures", "record-protected-structures-dcc",
           "development-plan-2023-2029-rps-record-of-protected-structures-fcc2",
           "record-of-protected-structures-south-dublin-county-development-plan-2022-to-2028-sdcc1",
           "development-plan-2022-2028-protected-structures-dlr", "national-planning-applications"):
    ckan_show(ds)
links("https://www.gov.ie/en/service/search-or-download-the-public-register-of-charities/")
links("https://www.charitiesregulator.ie/en/information-for-the-public/search-the-register-of-charities")
links("https://www.gov.ie/en/department-of-education/collections/data-on-individual-schools/")
links("https://www.gov.ie/en/department-of-education/publications/data-on-individual-schools/")
for u in ("https://assets.gov.ie/static/documents/8e1b86ab/Data_on_Individual_Schools_Mainstream..xlsx",
          "https://assets.gov.ie/static/documents/d5fbb204/Data_on_Individual_Schools_post_primary..xlsx",
          "https://www.charitiesregulator.ie/media/d52jwriz/register-of-charities.csv",
          "https://overpass-api.de/api/interpreter?data=[out:json];node(53.70,-6.40,53.72,-6.34)[amenity=place_of_worship];out;",
          "https://overpass-api.de/api/status", "https://overpass.kumi.systems/api/status",
          "https://overpass.private.coffee/api/status"):
    head(u)
