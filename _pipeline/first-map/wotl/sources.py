"""Fetchers for open data that can point to Catholic Church sites.

Every fetcher returns a DataFrame with the same columns (SITE_COLUMNS), caches
its raw download in data/raw, and returns an empty frame with a warning if the
source can't be reached, so one broken source never stops the map.

None of these sources records who owns a site. They give locations of
churches, convents, schools and so on. Ownership needs the Land Registry.
"""

import json
import re
import time
import warnings
from io import BytesIO

import pandas as pd
import requests

from . import config

SITE_COLUMNS = [
    "source", "source_id", "name", "category", "denomination",
    "lat", "lon", "address", "source_url", "raw_use",
]


def _empty():
    return pd.DataFrame(columns=SITE_COLUMNS)


def _get(url, *, params=None, data=None, timeout=180, browser=False):
    headers = config.BROWSER_HEADERS if browser else {"User-Agent": config.USER_AGENT}
    if data is not None:
        r = requests.post(url, data=data, headers=headers, timeout=timeout)
    else:
        r = requests.get(url, params=params, headers=headers, timeout=timeout)
    r.raise_for_status()
    return r


def _cached(name, fetch, refresh=False):
    """Return bytes from data/raw/<name>, downloading with fetch() if missing."""
    path = config.RAW_DIR / name
    if path.exists() and not refresh:
        return path.read_bytes()
    content = fetch()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return content


def _matches(text, patterns):
    text = text or ""
    return any(re.search(p, text, flags=re.I) for p in patterns)


def guess_denomination(*texts):
    joined = " ".join(t for t in texts if isinstance(t, str))
    if _matches(joined, config.OTHER_DENOMINATION_TERMS):
        return "other"
    if re.search(r"catholic|\bR\.?C\.?\b", joined, flags=re.I):
        return "catholic"
    return "unknown"


# --- OpenStreetMap -----------------------------------------------------------

def overpass_query(area_names):
    """Query the union of one or more administrative areas (Dublin needs four)."""
    if isinstance(area_names, str):
        area_names = [area_names]
    # Overpass uses POSIX regex inside a quoted string, so a metacharacter
    # needs a doubled backslash.
    names = "|".join(re.sub(r"([.^$*+?()\[\]{}|\\])", r"\\\\\1", n) for n in area_names)
    return f"""
[out:json][timeout:300];
area["boundary"="administrative"]["name"~"^({names})$"]->.a;
(
  nwr["amenity"="place_of_worship"]["religion"="christian"](area.a);
  nwr["amenity"="monastery"](area.a);
  nwr["building"~"^(convent|monastery|church|chapel|cathedral)$"](area.a);
  nwr["landuse"="religious"](area.a);
  nwr["amenity"="grave_yard"](area.a);
  nwr["landuse"="cemetery"](area.a);
  nwr["amenity"="school"](area.a);
);
out center tags;
"""


def _osm_category(tags):
    if tags.get("amenity") == "place_of_worship" or tags.get("building") in {"church", "chapel", "cathedral"}:
        return "church"
    if tags.get("amenity") == "monastery" or tags.get("building") in {"convent", "monastery"}:
        return "convent / monastery"
    if tags.get("amenity") == "school":
        return "school"
    if tags.get("amenity") == "grave_yard" or tags.get("landuse") == "cemetery":
        return "graveyard"
    if tags.get("landuse") == "religious":
        return "religious land"
    return "other"


def parse_overpass(payload, other_only=False):
    """Catholic or unmarked sites; with other_only, only those marked as another denomination."""
    rows = []
    for el in payload.get("elements", []):
        tags = el.get("tags", {})
        lat = el.get("lat", (el.get("center") or {}).get("lat"))
        lon = el.get("lon", (el.get("center") or {}).get("lon"))
        if lat is None or lon is None:
            continue
        name = tags.get("name", "")
        denom_tag = tags.get("denomination", "")
        if "catholic" in denom_tag:
            denom = "catholic"
        elif denom_tag:
            denom = "other"
        else:
            denom = guess_denomination(name, tags.get("operator", ""))
        category = _osm_category(tags)
        # Schools and graveyards only count when something marks them Catholic;
        # untagged ones are too many and mostly unrelated.
        if category in {"school", "graveyard"} and denom != "catholic" and not _matches(
            name, config.CATHOLIC_TERMS
        ):
            continue
        if (denom == "other") != other_only:
            continue
        rows.append({
            "source": "OpenStreetMap",
            "source_id": f"{el['type']}/{el['id']}",
            "name": name,
            "category": category,
            "denomination": denom,
            "lat": lat,
            "lon": lon,
            "address": ", ".join(
                tags[k] for k in ("addr:street", "addr:city") if tags.get(k)
            ),
            "source_url": f"https://www.openstreetmap.org/{el['type']}/{el['id']}",
            "raw_use": json.dumps(
                {k: v for k, v in tags.items() if k in ("amenity", "building", "landuse", "religion", "denomination", "operator")}
            ),
        })
    return pd.DataFrame(rows, columns=SITE_COLUMNS)


def _overpass(query):
    errors = []
    for url in config.OVERPASS_MIRRORS:
        for attempt in range(2):
            try:
                return _get(url, data={"data": query}, timeout=330).content
            except Exception as e:
                errors.append(f"{url}: {e}")
                time.sleep(30 * (attempt + 1))
    raise RuntimeError("; ".join(errors))


def fetch_osm(refresh=False, other_only=False):
    try:
        raw = _cached(
            f"osm_{config.COUNTY.lower()}.json",
            lambda: _overpass(overpass_query(config.OSM_AREA_NAMES)),
            refresh,
        )
        return parse_overpass(json.loads(raw), other_only=other_only)
    except Exception as e:  # network, rate limit, bad area name
        if not other_only:
            warnings.warn(f"OpenStreetMap skipped: {e}")
        return _empty()


# --- National Inventory of Architectural Heritage ----------------------------

def _niah_pages(terms):
    features, offset = [], 0
    where = " OR ".join(f"UPPER(COUNTY) LIKE '%{t.upper()}%'" for t in terms)
    while True:
        params = {
            "where": where,
            "outFields": "*",
            "outSR": 4326,
            "f": "geojson",
            "resultOffset": offset,
            "resultRecordCount": 2000,
        }
        page = _get(config.NIAH_QUERY_URL, params=params).json()
        batch = page.get("features", [])
        features.extend(batch)
        if len(batch) < 2000:
            break
        offset += len(batch)
    return json.dumps({"type": "FeatureCollection", "features": features}).encode()


def parse_niah(geojson):
    rows = []
    for f in geojson.get("features", []):
        p = f.get("properties", {})
        uses = f"{p.get('ORIGINAL_TYPE') or ''} / {p.get('IN_USE_AS_TYPE') or ''}"
        if not _matches(uses, [re.escape(u) for u in config.NIAH_RELEVANT_USES]):
            continue
        denom = guess_denomination(p.get("NAME"), p.get("DESCRIPTION"), p.get("APPRAISAL"))
        if denom == "other":
            continue
        # A school or hall is only a lead when the record itself suggests a Catholic link.
        if re.search(r"school|hall|hospital|workhouse|college", uses, re.I) and denom != "catholic" and not _matches(
            f"{p.get('NAME')} {p.get('DESCRIPTION')}", config.CATHOLIC_TERMS
        ):
            continue
        lat, lon = p.get("LATITUDE"), p.get("LONGITUDE")
        if (lat is None or lon is None) and f.get("geometry"):
            lon, lat = f["geometry"]["coordinates"][:2]
        rows.append({
            "source": "NIAH",
            "source_id": str(p.get("REG_NO")),
            "name": p.get("NAME") or "",
            "category": (p.get("ORIGINAL_TYPE") or "").lower(),
            "denomination": denom,
            "lat": lat,
            "lon": lon,
            "address": ", ".join(str(p[k]) for k in ("STREET1", "TOWN", "TOWNLAND") if p.get(k)),
            "source_url": p.get("WEBSITE_LINK") or "https://www.buildingsofireland.ie/",
            "raw_use": uses,
        })
    return pd.DataFrame(rows, columns=SITE_COLUMNS)


def fetch_niah(refresh=False):
    try:
        raw = _cached(f"niah_{config.COUNTY.lower()}.geojson", lambda: _niah_pages(config.NIAH_COUNTY_TERMS), refresh)
        return parse_niah(json.loads(raw))
    except Exception as e:
        warnings.warn(f"NIAH skipped: {e}")
        return _empty()


# --- Council Records of Protected Structures ---------------------------------

# A use word followed by a street word is an address ("Church Street"), not a use.
_STREET_NAME = re.compile(
    r"\b(church|chapel|abbey|convent|friary|cathedral|presbytery|school|college|hospital|hall|"
    r"monastery|seminary|priory)\s+(street|st|road|rd|avenue|ave|lane|terrace|place|park|square|"
    r"row|quay|hill|gardens|close|drive|green|parade|court|view|grove|walk|way|villas)\b",
    re.I,
)


def _geometry_centre(geom):
    """A representative point for a GeoJSON geometry: the mean of its vertices."""
    if not geom:
        return None, None
    coords = []

    def walk(c):
        if c and isinstance(c[0], (int, float)):
            coords.append(c[:2])
        else:
            for x in c or []:
                walk(x)

    walk(geom.get("coordinates"))
    if not coords:
        return None, None
    return sum(c[0] for c in coords) / len(coords), sum(c[1] for c in coords) / len(coords)


def _to_wgs84(x, y):
    """Return (lon, lat), projecting from ITM when the numbers are metres."""
    x, y = pd.to_numeric(pd.Series(x), errors="coerce"), pd.to_numeric(pd.Series(y), errors="coerce")
    if x.dropna().abs().median() > 1000:
        from pyproj import Transformer
        crs = "EPSG:2157" if x.dropna().median() > 400000 else "EPSG:29902"
        t = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
        lon, lat = t.transform(x.values, y.values)
        return pd.Series(lon), pd.Series(lat)
    return x, y


def parse_rps(df, label, source_url):
    """Protected structures whose name or description reads as a Catholic site.

    Council records describe a building (\"Church of St Agatha\", \"former convent
    and chapel\"), so the same filter as NIAH applies: a relevant use, no other
    denomination, and a Catholic marker for schools, halls and the like.
    df needs `_lon` and `_lat` columns (WGS84) alongside the council's own.
    """
    name = _find_col(df, r"^(structure.?)?name$", r"structure.?name", r"^name", r"title", r"building")
    desc = [c for c in df.columns if re.search(r"desc|use|type", str(c), re.I) and c not in ("_lon", "_lat")]
    num = _find_col(df, r"rps.?(no|num|ref|id)", r"^rps$", r"ref.?(no|num)", r"^(no|number|objectid)$")
    addr = [c for c in df.columns if re.search(r"address|location|street|townland", str(c), re.I)]
    text_cols = [c for c in [name, *desc] if c]
    if not text_cols:
        warnings.warn(f"{label}: no name or description column; columns are {list(df.columns)}")
        return _empty()
    text = _join_cols(df, text_cols).fillna("")
    use_text = text.str.replace(_STREET_NAME, " ", regex=True)
    uses = [rf"\b{u}" for u in config.RPS_RELEVANT_USES]
    rows = []
    for i, t in use_text.items():
        if not _matches(t, uses):
            continue
        denom = guess_denomination(t)
        if denom == "other":
            continue
        if re.search(r"school|college|hall|hospital", t, re.I) and not re.search(
            r"church|chapel|convent|presbytery|monastery|friary|seminary", t, re.I
        ) and denom != "catholic" and not _matches(t, config.CATHOLIC_TERMS):
            continue
        lon, lat = df.at[i, "_lon"], df.at[i, "_lat"]
        if pd.isna(lat) or pd.isna(lon):
            continue
        rows.append({
            "source": label,
            "source_id": str(df.at[i, num]) if num else str(i),
            "name": str(df.at[i, name]) if name and pd.notna(df.at[i, name]) else text[i][:80],
            "category": (re.search("|".join(uses), t, re.I).group(0).lower()),
            "denomination": denom,
            "lat": lat,
            "lon": lon,
            "address": _join_cols(df.loc[[i]], addr).iloc[0] if addr else "",
            "source_url": source_url,
            "raw_use": text[i][:300],
        })
    return pd.DataFrame(rows, columns=SITE_COLUMNS)


def _ckan_meta(dataset_id):
    return _get(f"{config.CKAN_API}/package_show", params={"id": dataset_id}).json()["result"]


def _arcgis_layer_geojson(url):
    """Every feature of an ArcGIS feature or map service layer, as WGS84 GeoJSON."""
    base = re.sub(r"/query.*$", "", url.split("?")[0].rstrip("/"))
    if re.search(r"/(Feature|Map)Server$", base):
        base += "/0"
    features, offset, seen = [], 0, set()
    for _ in range(100):  # 100,000 features at most; a guard against servers that ignore offsets
        page = _get(f"{base}/query", params={
            "where": "1=1", "outFields": "*", "outSR": 4326, "f": "geojson",
            "resultOffset": offset, "resultRecordCount": 1000,
        }, timeout=120).json()
        batch = page.get("features", [])
        first = json.dumps(batch[0], sort_keys=True) if batch else None
        if first in seen:
            break
        seen.add(first)
        features.extend(batch)
        if len(batch) < 1000 and not page.get("properties", {}).get("exceededTransferLimit"):
            break
        offset += len(batch)
    return json.dumps({"type": "FeatureCollection", "features": features}).encode()


def _rps_download(dataset_id):
    """Fetch a council RPS from data.gov.ie, preferring formats with coordinates."""
    resources = _ckan_meta(dataset_id).get("resources", [])

    def kind(res):
        fmt, url = (res.get("format") or "").lower(), res.get("url") or ""
        if "geojson" in fmt or url.lower().endswith(".geojson") or "f=geojson" in url.lower():
            return "geojson"
        if re.search(r"(feature|map)server", url, re.I) or "esri" in fmt or "arcgis" in fmt:
            return "arcgis"
        if fmt == "csv" or url.lower().endswith(".csv"):
            return "csv"
        return None

    ranked = sorted((r for r in resources if kind(r)), key=lambda r: ["geojson", "arcgis", "csv"].index(kind(r)))
    errors = []
    for res in ranked:
        try:
            if kind(res) == "arcgis":
                return "geojson", _arcgis_layer_geojson(res["url"])
            return kind(res), _get(res["url"], browser=True).content
        except Exception as e:
            errors.append(f"{res.get('url')}: {e}")
    raise ValueError(f"no usable resource in {dataset_id}: {'; '.join(errors) or [r.get('format') for r in resources]}")


def _rps_frame(fmt, content):
    if fmt == "geojson":
        feats = json.loads(content).get("features", [])
        df = pd.DataFrame([f.get("properties") or {} for f in feats])
        centres = [_geometry_centre(f.get("geometry")) for f in feats]
        df["_lon"], df["_lat"] = _to_wgs84([c[0] for c in centres], [c[1] for c in centres])
        return df
    df = _read_table(content, "CSV")
    lat, lon = _find_col(df, r"^lat", r"latitude"), _find_col(df, r"^lon", r"^long", r"longitude")
    x = _find_col(df, r"easting", r"^x$", r"itm.?e", r"x.?coord", r"^x_")
    y = _find_col(df, r"northing", r"^y$", r"itm.?n", r"y.?coord", r"^y_")
    if lat and lon:
        df["_lon"], df["_lat"] = _to_wgs84(df[lon].values, df[lat].values)
    elif x and y:
        df["_lon"], df["_lat"] = _to_wgs84(df[x].values, df[y].values)
    else:
        df["_lon"], df["_lat"] = None, None
    return df.reset_index(drop=True)


def fetch_rps(refresh=False):
    frames = []
    for council, dataset_id in config.RPS_DATASETS.items():
        try:
            meta = {}

            def download():
                fmt, content = _rps_download(dataset_id)
                meta["fmt"] = fmt
                return content

            raw = _cached(f"rps_{dataset_id}.data", download, refresh)
            fmt = meta.get("fmt") or ("geojson" if raw.lstrip()[:1] == b"{" else "csv")
            df = _rps_frame(fmt, raw)
            frames.append(parse_rps(df, f"Protected structures: {council}", f"https://data.gov.ie/dataset/{dataset_id}"))
        except Exception as e:
            warnings.warn(f"Protected structures {council} skipped: {e}")
    frames = [f for f in frames if not f.empty]
    return pd.concat(frames, ignore_index=True) if frames else _empty()


# --- Department of Education school lists ------------------------------------

def _ckan_resource_url(dataset_id, formats=("CSV", "XLSX", "XLS"), name_pattern=None):
    meta = _get(f"{config.CKAN_API}/package_show", params={"id": dataset_id}).json()["result"]
    for fmt in formats:
        for res in meta.get("resources", []):
            if (res.get("format") or "").upper() != fmt:
                continue
            if name_pattern and not re.search(name_pattern, res.get("url", ""), re.I):
                continue
            return res["url"], fmt
    raise ValueError(f"no {'/'.join(formats)} resource in {dataset_id}")


def _join_cols(d, cols):
    """Join text columns per row, skipping blanks (pandas 3 keeps NaN in astype(str))."""
    return d[cols].apply(
        lambda r: ", ".join(str(v).strip() for v in r if pd.notna(v) and str(v).strip() not in ("", "nan", "None")),
        axis=1,
    )


def _find_col(df, *patterns):
    for p in patterns:
        for c in df.columns:
            if re.search(p, str(c), flags=re.I):
                return c
    return None


def parse_schools(df, label, source_url=None, catholic_only=True):
    ethos = _find_col(df, r"ethos", r"relig", r"patron")
    patron = _find_col(df, r"^patron")
    lat = _find_col(df, r"^lat", r"latitude")
    lon = _find_col(df, r"^lon", r"^long", r"longitude")
    east = _find_col(df, r"easting", r"^x$", r"itm.?e", r"x.?coord")
    north = _find_col(df, r"northing", r"^y$", r"itm.?n", r"y.?coord")
    name = _find_col(df, r"official.?name", r"school.?name", r"^name")
    county = _find_col(df, r"county")
    roll = _find_col(df, r"roll")
    addr = [c for c in df.columns if re.search(r"address", str(c), re.I)]
    if ethos is None and catholic_only:
        warnings.warn(f"{label}: no ethos column found; columns are {list(df.columns)}")
        return _empty()
    d = df.copy()
    if county and catholic_only:
        d = d[d[county].astype(str).str.contains(config.COUNTY_PATTERN, case=False, na=False, regex=True)]
    if catholic_only:
        d = d[d[ethos].astype(str).str.contains("catholic", case=False, na=False)]
    if lat and lon:
        d["_lat"], d["_lon"] = pd.to_numeric(d[lat], errors="coerce"), pd.to_numeric(d[lon], errors="coerce")
    elif east and north:
        from pyproj import Transformer
        e, n = pd.to_numeric(d[east], errors="coerce"), pd.to_numeric(d[north], errors="coerce")
        # Older lists use Irish Grid (TM65, EPSG:29902); newer use ITM (EPSG:2157).
        crs = "EPSG:2157" if e.median() > 400000 else "EPSG:29902"
        t = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
        d["_lon"], d["_lat"] = t.transform(e.values, n.values)
    else:
        warnings.warn(f"{label}: no coordinates found; schools listed but not mapped")
        d["_lat"], d["_lon"] = None, None
    return pd.DataFrame({
        "source": label,
        "source_id": d[roll].astype(str).str.strip().str.upper() if roll else "",
        "name": d[name].astype(str) if name else "",
        "category": "school",
        "denomination": "catholic",
        "lat": d["_lat"],
        "lon": d["_lon"],
        "address": _join_cols(d, addr) if addr else "",
        "source_url": source_url or "https://data.gov.ie/dataset/" + label.split(": ")[-1],
        # The patron (usually a bishop or a religious order) is the first lead to the owner.
        "raw_use": (d[ethos].astype(str) + (" · patron: " + d[patron].astype(str) if patron and patron != ethos else "")) if ethos else "",
    }, columns=SITE_COLUMNS)


def _promote_header(df, pattern=r"roll|charity.?name"):
    """Spreadsheets often open with a title block; use the first row that looks like a header."""
    if any(re.search(pattern, str(c), re.I) for c in df.columns):
        return df
    for i in range(min(len(df), 20)):
        row = df.iloc[i].astype(str)
        if row.str.contains(pattern, case=False, regex=True).any():
            out = df.iloc[i + 1:].copy()
            out.columns = [str(c).strip() for c in df.iloc[i]]
            return out.reset_index(drop=True)
    return df


def _read_table(content, fmt):
    if fmt == "CSV":
        for enc in ("utf-8", "cp1252", "latin-1"):
            try:
                return _promote_header(pd.read_csv(BytesIO(content), encoding=enc))
            except UnicodeDecodeError:
                continue
    sheets = pd.read_excel(BytesIO(content), sheet_name=None)
    return _promote_header(max(sheets.values(), key=len))


def _school_locations(refresh):
    """Roll number -> (lat, lon) from the older lists that carry coordinates."""
    frames = []
    for ds in config.SCHOOL_LOCATION_DATASETS:
        try:
            url, fmt = _ckan_resource_url(ds)
            raw = _cached(f"{ds}.{fmt.lower()}", lambda: _get(url, browser=True).content, refresh)
            df = _read_table(raw, fmt)
            parsed = parse_schools(df, "locations", catholic_only=False)
            frames.append(parsed[["source_id", "lat", "lon"]].dropna())
        except Exception as e:
            warnings.warn(f"School locations {ds} skipped: {e}")
    if not frames:
        return pd.DataFrame(columns=["source_id", "lat", "lon"])
    return pd.concat(frames).drop_duplicates("source_id").set_index("source_id")


def fetch_schools(refresh=False):
    frames, locations = [], None
    for ds, (url, page) in config.SCHOOL_LISTS.items():
        try:
            fmt = "CSV" if url.lower().endswith(".csv") else "XLSX"
            raw = _cached(f"{ds}.{fmt.lower()}", lambda: _get(url, browser=True).content, refresh)
            d = parse_schools(_read_table(raw, fmt), f"Dept of Education: {ds}", source_url=page)
            missing = d["lat"].isna()
            if missing.any():
                if locations is None:
                    locations = _school_locations(refresh)
                key = d.loc[missing, "source_id"].str.strip().str.upper()
                d.loc[missing, "lat"] = key.map(locations["lat"]).values
                d.loc[missing, "lon"] = key.map(locations["lon"]).values
                still = int(d["lat"].isna().sum())
                if still:
                    warnings.warn(f"School list {ds}: {still} of {len(d)} Catholic schools have no coordinates (not mapped)")
            frames.append(d)
        except Exception as e:
            warnings.warn(f"School list {ds} skipped: {e}")
    return pd.concat(frames, ignore_index=True) if frames else _empty()


# --- Tailte Éireann valuation list (experimental) ----------------------------

# Schools and halls are left out: the list has no names to tell a parish hall
# from a dance hall. Most Church property is exempt from rates and so is absent.
VALUATION_USE_PATTERN = r"church|chapel|convent|presbytery|parochial|monastery|friary|religious|seminary"


def parse_valuation(records):
    df = pd.json_normalize(records)
    if df.empty:
        return _empty()
    use_cols = [c for c in df.columns if re.search(r"use|category", c, re.I)]
    text = _join_cols(df, use_cols).str.replace(",", "") if use_cols else pd.Series("", index=df.index)
    d = df[text.str.contains(VALUATION_USE_PATTERN, case=False, na=False)].copy()
    if d.empty:
        return _empty()
    x, y = _find_col(d, r"x.?itm", r"^x"), _find_col(d, r"y.?itm", r"^y")
    from pyproj import Transformer
    t = Transformer.from_crs("EPSG:2157", "EPSG:4326", always_xy=True)
    lon, lat = t.transform(pd.to_numeric(d[x], errors="coerce").values, pd.to_numeric(d[y], errors="coerce").values)
    pn = _find_col(d, r"property.?number")
    addr = sorted(c for c in d.columns if re.search(r"address", c, re.I))
    return pd.DataFrame({
        "source": "Tailte Éireann valuation list",
        "source_id": d[pn].astype(str) if pn else "",
        "name": d[addr[0]].astype(str) if addr else "",
        "category": text.loc[d.index].str.lower().str.extract(f"({VALUATION_USE_PATTERN})", expand=False),
        "denomination": "unknown",
        "lat": lat,
        "lon": lon,
        "address": _join_cols(d, addr) if addr else "",
        "source_url": "https://tailte.ie/en/valuation/open-data/open-data-information",
        "raw_use": text.loc[d.index],
    }, columns=SITE_COLUMNS)


def fetch_valuation(refresh=False):
    frames = []
    for authority in config.VALUATION_LOCAL_AUTHORITIES:
        try:
            params = {
                "Fields": "*",
                "LocalAuthority": authority,
                "Format": "json",
                "Download": "false",
            }
            slug = re.sub(r"\W+", "_", authority.lower()).strip("_")
            raw = _cached(
                f"valuation_{slug}.json",
                lambda: _get(config.VALUATION_API, params=params, timeout=300).content,
                refresh,
            )
            frames.append(parse_valuation(json.loads(raw)))
        except Exception as e:
            warnings.warn(f"Valuation list {authority} skipped: {e}")
    frames = [f for f in frames if not f.empty]
    return pd.concat(frames, ignore_index=True) if frames else _empty()


# --- Hand-curated history sites ----------------------------------------------

def load_history_sites():
    """Institutions from the Ryan, McAleese and Mother and Baby Homes reports.

    Filled in by hand from the reports (see data/seed/README). Rows without
    coordinates are kept in the table but left off the map.
    """
    path = config.SEED_DIR / "history_sites.csv"
    if not path.exists():
        return _empty()
    h = pd.read_csv(path)
    h = h[h["county"].astype(str).str.fullmatch(config.COUNTY, case=False, na=False)]
    return pd.DataFrame({
        "source": "History seed list",
        "source_id": h["source_ref"].astype(str),
        "name": h["institution"],
        "category": h["type"],
        "denomination": "catholic",
        "lat": pd.to_numeric(h["lat"], errors="coerce"),
        "lon": pd.to_numeric(h["lon"], errors="coerce"),
        "address": h["town"].astype(str),
        "source_url": h["source_url"],
        "raw_use": h["operator"].astype(str),
        "anchor": h["anchor"] if "anchor" in h else "",
    }, columns=SITE_COLUMNS + ["anchor"])


def load_industrial_schools():
    """Industrial and residential schools from the Ryan Report, for every county.

    data/seed/industrial_schools.csv is the national reference list: each
    school's order, location, Ryan Report pages, and what is known of who
    occupies the site now and any sale or transfer. State-run institutions
    (church_run = no) stay in the file but are left off the map.
    """
    path = config.SEED_DIR / "industrial_schools.csv"
    if not path.exists():
        return _empty()
    s = pd.read_csv(path, dtype=str).fillna("")
    s = s[s["county"].str.fullmatch(config.COUNTY, case=False) & (s["church_run"] != "no")]

    def detail(r):
        parts = [r["order"] or "order to confirm", r["type"], f"{r['opened']}–{r['closed']}".strip("–")]
        if r["current_occupier"]:
            parts.append(f"now: {r['current_occupier']}")
        if r["sale_or_transfer"]:
            parts.append(f"sale/transfer: {r['sale_or_transfer']}")
        return " · ".join(p for p in parts if p)

    return pd.DataFrame({
        "source": "Industrial schools (Ryan Report)",
        "source_id": s["ryan_report_name"].where(s["ryan_report_name"] != "", s["institution"]),
        "name": s["institution"],
        "category": s["type"].where(s["type"] != "", "industrial school"),
        "denomination": "catholic",
        "lat": pd.to_numeric(s["lat"], errors="coerce"),
        "lon": pd.to_numeric(s["lon"], errors="coerce"),
        "address": s["town"],
        "source_url": s["ryan_report_url"].where(s["ryan_report_url"] != "", "https://industrialmemories.ucd.ie/"),
        "raw_use": s.apply(detail, axis=1),
        "anchor": s["anchor"],
    }, columns=SITE_COLUMNS + ["anchor"])


def place_history_sites(history, points, max_spread_m=250):
    """Give unplaced history sites the location of the record their `anchor` names.

    `anchor` is a regular expression for the name of the same building in
    another source (an NIAH, OSM or protected-structure record). A site is
    placed only when every matching record sits within max_spread_m of the
    others; otherwise it stays unplaced for a hand check. Returns (placed or
    already placed rows, unplaced rows).
    """
    from .build import _metres

    h = history.copy()
    named = points[points["name"].fillna("").astype(str).str.strip() != ""].dropna(subset=["lat", "lon"])
    for i, row in h.iterrows():
        if pd.notna(row["lat"]) or not isinstance(row.get("anchor"), str) or not row["anchor"].strip():
            continue
        hits = named[named["name"].str.contains(row["anchor"], case=False, regex=True, na=False)]
        if hits.empty:
            continue
        lat, lon = hits["lat"].astype(float), hits["lon"].astype(float)
        spread = max(_metres(lat.iloc[0], lon.iloc[0], a, b) for a, b in zip(lat, lon))
        if spread > max_spread_m:
            continue
        best = hits.iloc[0]
        h.at[i, "lat"], h.at[i, "lon"] = lat.mean(), lon.mean()
        h.at[i, "raw_use"] = (
            f"{row['raw_use']} · placed by name on {best['source']} record {best['source_id']} "
            f"(\"{best['name']}\"): check the exact building"
        )
    placed = h["lat"].notna() & h["lon"].notna()
    return h[placed].drop(columns="anchor"), h[~placed].drop(columns="anchor")


# --- Charities Regulator register: names, not places ---------------------------

def parse_charities(df):
    name = _find_col(df, r"registered.?charity.?name", r"charity.?name", r"^name")
    aka = _find_col(df, r"also.?known")
    addr = _find_col(df, r"primary.?address", r"address")
    number = _find_col(df, r"registered.?charity.?number", r"charity.?number", r"rcn")
    form = _find_col(df, r"governing.?form", r"legal.?form", r"form")
    if name is None:
        warnings.warn(f"Charities register: no name column; columns are {list(df.columns)}")
        return pd.DataFrame()
    text = df[name].astype(str) + " " + (df[aka].astype(str) if aka else "")
    hits = df[text.apply(lambda t: _matches(t, config.CATHOLIC_TERMS))].copy()
    if addr:
        hits["in_county"] = hits[addr].astype(str).str.contains(config.COUNTY_PATTERN, case=False, na=False, regex=True)
    keep = [c for c in (number, name, aka, form, addr) if c] + (["in_county"] if addr else [])
    return hits[keep].rename(columns={number: "charity_number", name: "name", aka: "also_known_as", form: "governing_form", addr: "address"})


def fetch_charity_names(refresh=False):
    try:
        def download():
            url, _ = _ckan_resource_url(config.CHARITIES_DATASET, formats=("XLSX",), name_pattern=r"public-register")
            return _get(url, browser=True).content

        raw = _cached("public-register-of-charities.xlsx", download, refresh)
        xl = pd.read_excel(BytesIO(raw), sheet_name=None)
        # The register has a header block on some sheets; pick the sheet with most rows.
        df = max(xl.values(), key=len)
        if not any(re.search(r"name", str(c), re.I) for c in df.columns):
            hdr = df.index[df.apply(lambda r: r.astype(str).str.contains("Charity Name", case=False).any(), axis=1)]
            if len(hdr):
                df.columns = df.loc[hdr[0]].astype(str)
                df = df.loc[hdr[0] + 1:]
        return parse_charities(df)
    except Exception as e:
        warnings.warn(f"Charities register skipped: {e}")
        return pd.DataFrame()
