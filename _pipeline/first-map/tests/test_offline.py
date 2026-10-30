"""Offline checks of the parsing and merging logic, using made-up fixture records.

The fixtures are invented test data, not real sites. Run: python -m pytest tests
"""

import json

import pandas as pd

from wotl import build, config, sources

# The first fixtures are Louth records.
config.set_county("Louth")

OSM = {"elements": [
    {"type": "node", "id": 1, "lat": 54.0, "lon": -6.4,
     "tags": {"amenity": "place_of_worship", "religion": "christian", "denomination": "roman_catholic", "name": "Test Church A"}},
    {"type": "way", "id": 2, "center": {"lat": 54.0004, "lon": -6.4003},
     "tags": {"landuse": "religious", "name": "Test Church A grounds"}},
    {"type": "node", "id": 3, "lat": 54.1, "lon": -6.3,
     "tags": {"amenity": "place_of_worship", "religion": "christian", "denomination": "anglican", "name": "Test Parish Church"}},
    {"type": "node", "id": 4, "lat": 54.2, "lon": -6.2, "tags": {"amenity": "school", "name": "Test Community College"}},
    {"type": "node", "id": 5, "lat": 54.3, "lon": -6.1, "tags": {"amenity": "school", "name": "Test St Mary's NS"}},
]}

NIAH = {"features": [
    {"properties": {"REG_NO": 1, "ORIGINAL_TYPE": "church/chapel", "IN_USE_AS_TYPE": "church/chapel",
                    "NAME": "Test Church A", "DESCRIPTION": "Catholic church, built 1850", "LATITUDE": 54.0002, "LONGITUDE": -6.4001}},
    {"properties": {"REG_NO": 2, "ORIGINAL_TYPE": "church/chapel", "IN_USE_AS_TYPE": "church/chapel",
                    "NAME": "Test Church", "DESCRIPTION": "Church of Ireland church", "LATITUDE": 54.1, "LONGITUDE": -6.3}},
    {"properties": {"REG_NO": 3, "ORIGINAL_TYPE": "house", "IN_USE_AS_TYPE": "house", "NAME": "Test House",
                    "LATITUDE": 54.4, "LONGITUDE": -6.0}},
]}

SCHOOLS = pd.DataFrame({
    "Roll Number": ["00001A", "00002B", "00003C"],
    "Official Name": ["Test NS", "Test Educate Together", "Elsewhere NS"],
    "County": ["Louth", "Louth", "Meath"],
    "Ethos": ["CATHOLIC", "MULTI DENOMINATIONAL", "CATHOLIC"],
    "Easting (ITM)": [705000, 706000, 700000],
    "Northing (ITM)": [805000, 806000, 760000],
})


def test_osm_keeps_catholic_and_drops_other():
    df = sources.parse_overpass(OSM)
    assert set(df["name"]) == {"Test Church A", "Test Church A grounds", "Test St Mary's NS"}


def test_niah_drops_other_denominations_and_irrelevant_uses():
    df = sources.parse_niah(NIAH)
    assert list(df["source_id"]) == ["1"]


def test_schools_filters_county_and_ethos_and_projects_itm():
    df = sources.parse_schools(SCHOOLS, "Dept of Education: test")
    assert list(df["source_id"]) == ["00001A"]
    assert 53 < df["lat"].iloc[0] < 55 and -7 < df["lon"].iloc[0] < -6


def test_merge_groups_nearby_points_across_sources(tmp_path):
    pts = pd.concat([sources.parse_overpass(OSM), sources.parse_niah(NIAH)], ignore_index=True)
    pts, sites = build.merge_sites(pts, radius_m=100)
    church = sites[sites["all_names"].str.contains("Test Church A")]
    assert len(church) == 1 and church["n_sources"].iloc[0] == 2
    build.draw_map(pts, sites, tmp_path / "map.html")
    assert (tmp_path / "map.html").stat().st_size > 1000


def test_charities_name_filter():
    df = pd.DataFrame({
        "Registered Charity Number": [1, 2, 3, 4, 5],
        "Registered Charity Name": ["Test Diocesan Trust", "Test Sports Club", "Sisters of Test",
                                    "Test Parish Church", "Test Presbyterian Congregation"],
        "Primary Address": ["Dundalk, Co. Louth", "Drogheda, Co. Louth", "Cork", "Louth", "Louth"],
        "Charitable Purpose": ["Advancement of religion", "Other", "Advancement of religion",
                               "Advancement of religion", "Advancement of religion"],
    })
    out = sources.parse_charities(df)
    assert list(out["name"]) == ["Test Diocesan Trust", "Sisters of Test"]
    assert list(out["catholic_match"]) == ["explicit", "order or devotion"]
    assert list(out["in_county"]) == [True, False]


def test_charities_named_bodies_match_whatever_their_purpose():
    df = pd.DataFrame({
        "Registered Charity Number": [1, 2],
        "Registered Charity Name": ["Testtown Vincent De Paul", "Testtown Parish Council"],
        "Primary Address": ["Dublin", "Dublin"],
        "Charitable Purpose": ["Relief of poverty or economic hardship", "Advancement of community welfare"],
    })
    out = sources.parse_charities(df)
    assert list(out["name"]) == ["Testtown Vincent De Paul"] and out["catholic_match"].iloc[0] == "named body"


# --- County switching and the Dublin sources ---------------------------------

import pytest

from wotl import config, names


@pytest.fixture
def dublin():
    config.set_county("Dublin")
    yield
    config.set_county("Louth")


def test_set_county_switches_every_setting(dublin):
    assert config.COUNTY == "Dublin" and config.SITE_PREFIX == "DU"
    assert "Fingal" in config.OSM_AREA_NAMES and config.RPS_DATASETS
    q = sources.overpass_query(config.OSM_AREA_NAMES)
    assert "^(County Dublin|Dublin City|Fingal|South Dublin|" in q
    with pytest.raises(ValueError):
        config.set_county("Atlantis")


def test_schools_match_dublin_postal_districts(dublin):
    df = SCHOOLS.assign(County=["Dublin 7", "Dublin", "Co. Fingal"])
    out = sources.parse_schools(df, "Dept of Education: test")
    assert list(out["source_id"]) == ["00001A", "00003C"]


RPS = pd.DataFrame({
    "RPS_No": [1, 2, 3, 4, 5, 6],
    "Name": ["Church of the Test", "Test House", "Test Parish Church", "Former Test Convent", "Test Hall", "Test Shop"],
    "Description": ["Catholic church", "Georgian house", "Church of Ireland church", "convent and chapel",
                    "parish hall", "Shopfront"],
    "Address": ["Main Street", "Church Street", "Church Road", "Convent Lane", "Main Street", "Church Street"],
    "_lon": [-6.26, -6.27, -6.28, -6.29, -6.30, -6.31],
    "_lat": [53.35] * 6,
})


def test_rps_keeps_catholic_uses_and_skips_addresses_and_other_denominations(dublin):
    out = sources.parse_rps(RPS, "Protected structures: Test Council", "https://example.org")
    assert list(out["source_id"]) == ["1", "4", "5"]
    assert out.loc[out["source_id"] == "1", "denomination"].iloc[0] == "catholic"


def test_rps_street_name_is_not_a_use(dublin):
    df = pd.DataFrame({"Name": ["No. 3 Church Street"], "_lon": [-6.2], "_lat": [53.3]})
    assert sources.parse_rps(df, "Protected structures: Test", "x").empty


def test_rps_frame_reads_geojson_polygons_in_itm():
    gj = {"features": [{"properties": {"Name": "Test Church"},
                        "geometry": {"type": "Polygon", "coordinates": [[[715000, 734000], [715010, 734000], [715010, 734010]]]}}]}
    df = sources._rps_frame("geojson", json.dumps(gj).encode())
    assert 53.2 < df["_lat"].iloc[0] < 53.5 and -6.4 < df["_lon"].iloc[0] < -6.1


def test_history_anchor_places_only_on_a_clear_match():
    hist = pd.DataFrame({
        "source": "History seed list", "source_id": ["a", "b", "c"], "name": ["Inst A", "Inst B", "Inst C"],
        "category": "x", "denomination": "catholic", "lat": [None, None, None], "lon": [None, None, None],
        "address": "", "source_url": "", "raw_use": "Order", "anchor": ["test abbey", "test convent", ""],
    })
    pts = pd.DataFrame({
        "source": "NIAH", "source_id": ["1", "2", "3"],
        "name": ["Test Abbey", "Test Convent", "Test Convent Annex"],
        "lat": [53.30, 53.40, 53.60], "lon": [-6.2, -6.2, -6.2],
    })
    placed, unplaced = sources.place_history_sites(hist, pts)
    assert list(placed["source_id"]) == ["a"] and placed["lat"].iloc[0] == 53.30
    assert "placed by name on NIAH record 1" in placed["raw_use"].iloc[0]
    assert list(unplaced["source_id"]) == ["b", "c"]  # b matches two far-apart records


def test_drop_near_other_keeps_catholic_points():
    pts = sources.parse_overpass(OSM)
    other = sources.parse_overpass(OSM, other_only=True)
    assert list(other["name"]) == ["Test Parish Church"]
    unmarked = pd.DataFrame([{**pts.iloc[0].to_dict(), "denomination": "unknown", "lat": 54.1, "lon": -6.3, "name": "X"}])
    kept, dropped = build.drop_near_other(pd.concat([pts, unmarked], ignore_index=True), other, 100)
    assert dropped == 1 and "X" not in set(kept["name"])


def test_name_leads_combine_seed_patrons_and_operators(dublin):
    schools = pd.DataFrame({"raw_use": ["CATHOLIC · patron: ARCHBISHOP OF DUBLIN"] * 3 + ["CATHOLIC · patron: CEIST"]})
    osm = pd.DataFrame({"raw_use": [json.dumps({"operator": "Test Parish"}), json.dumps({"amenity": "school"})]})
    leads = names.name_leads(schools, osm, pd.DataFrame())
    assert {"Archdiocese of Dublin", "Archbishop Of Dublin", "Test Parish"} <= set(leads["name"])
    assert "Archdiocese of Armagh" not in set(leads["name"])
    assert leads.loc[leads["name"] == "Archbishop Of Dublin", "count"].iloc[0] == 3


def test_industrial_schools_reference_list(dublin):
    s = sources.load_industrial_schools()
    assert "Artane Industrial School" in set(s["name"])
    assert "Marlborough House" not in set(s["name"])  # State-run
    assert s["raw_use"].str.contains("now: St David's CBS").any()
    config.set_county("Louth")
    louth = sources.load_industrial_schools()
    assert list(louth["source_id"]) == ["Dundalk"] and louth["lat"].notna().all()


def test_redress_transfers_match_the_appendix_total(dublin):
    t = pd.read_csv(config.SEED_DIR / "redress_property_transfers.csv", dtype=str).fillna("")
    appendix1 = t[t["ref"].str.startswith("A1-")]
    assert len(appendix1) == 55
    assert round(appendix1["value_eur"].astype(float).sum(), 2) == 58_725_275.00  # total printed in the note
    d = sources.load_redress_transfers()
    assert "Gate Lodge, Goldenbridge" in set(d["name"]) and d["lat"].isna().all()
    assert d["raw_use"].str.contains("€220,000").any()


def test_hiqa_keeps_only_church_providers(dublin):
    centres = pd.DataFrame([
        {"centre_id": "1", "name": "Nazareth House Malahide Road", "type": "older persons' centre", "slug": "nazareth-house",
         "address": "Malahide Road", "centre_type": "", "provider": "Nazareth Care Ireland", "report": ""},
        {"centre_id": "2", "name": "St Joseph's Nursing Home", "type": "older persons' centre", "slug": "st-josephs",
         "address": "", "centre_type": "", "provider": "St Joseph's Nursing Home Limited", "report": ""},
        {"centre_id": "3", "name": "Example disability centre", "type": "disability centre", "slug": "c",
         "address": "", "centre_type": "", "provider": "Saint John of God Community Services CLG", "report": ""},
    ])
    church = sources.hiqa_church_centres(centres)
    assert list(church["source_id"]) == ["1", "3"]
    leads = names.care_providers(centres)
    assert set(leads["name"]) == {"Nazareth Care Ireland", "Saint John of God Community Services CLG"}


def test_rps_frame_reads_cp1252_geojson():
    gj = {"features": [{"properties": {"Name": "Church of St François"},
                        "geometry": {"type": "Point", "coordinates": [-6.26, 53.35]}}]}
    df = sources._rps_frame("geojson", json.dumps(gj, ensure_ascii=False).encode("cp1252"))
    assert df["Name"].iloc[0] == "Church of St François"


def test_rps_frame_repairs_irish_grid_published_as_itm():
    # St David's CBS, Artane, as Dublin City Council's GeoJSON gives it.
    gj = {"features": [{"properties": {"Name": "Test"},
                        "geometry": {"type": "Point", "coordinates": [-11.833421, 48.835184]}}]}
    df = sources._rps_frame("geojson", json.dumps(gj).encode())
    assert build._metres(df["_lat"].iloc[0], df["_lon"].iloc[0], 53.381044, -6.217571) < 10


def test_rps_frame_reads_web_mercator():
    gj = {"features": [{"properties": {"Name": "Test"},
                        "geometry": {"type": "Point", "coordinates": [-692110.0, 7050980.0]}}]}
    df = sources._rps_frame("geojson", json.dumps(gj).encode())
    assert 53.3 < df["_lat"].iloc[0] < 53.4 and -6.3 < df["_lon"].iloc[0] < -6.1


def test_run_pilot_imports():
    import run_pilot  # noqa: F401  (a syntax error here would only show in the live build)


def test_run_pilot_end_to_end_with_offline_sources(dublin, tmp_path, monkeypatch):
    import run_pilot

    church = pd.DataFrame([{"source": "NIAH", "source_id": "1", "name": "Goldenbridge Convent", "category": "convent",
                            "denomination": "catholic", "lat": 53.337, "lon": -6.318, "address": "Inchicore",
                            "source_url": "", "raw_use": "convent"}], columns=sources.SITE_COLUMNS)
    monkeypatch.setattr(config, "OUT_DIR", tmp_path)
    for name in ("fetch_osm", "fetch_rps", "fetch_schools", "fetch_valuation"):
        monkeypatch.setattr(sources, name, lambda refresh=False, other_only=False: sources._empty())
    monkeypatch.setattr(sources, "fetch_niah", lambda refresh=False: church)
    monkeypatch.setattr(sources, "fetch_hiqa_centres", lambda refresh=False: pd.DataFrame(
        columns=["centre_id", "name", "type", "slug", "address", "centre_type", "provider", "report"]))
    monkeypatch.setattr(sources, "fetch_charity_names", lambda refresh=False: pd.DataFrame())
    summary, points, sites, leads, stats = run_pilot.run()
    assert {"Goldenbridge Convent", "Gate Lodge, Goldenbridge"} <= set(points["name"])
