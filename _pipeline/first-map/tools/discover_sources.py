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


for q in ("primary schools", "post-primary schools", "schools ethos", "charities register"):
    ckan_search(q)
links("https://www.gov.ie/en/service/search-or-download-the-public-register-of-charities/")
links("https://www.charitiesregulator.ie/en/information-for-the-public/search-the-register-of-charities")
links("https://www.gov.ie/en/department-of-education/collections/data-on-individual-schools/")
links("https://www.gov.ie/en/department-of-education/publications/data-on-individual-schools/")
for u in ("https://overpass-api.de/api/status", "https://overpass.kumi.systems/api/status",
          "https://overpass.private.coffee/api/status"):
    head(u)
