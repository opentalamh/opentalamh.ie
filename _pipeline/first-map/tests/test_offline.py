"""Offline checks of the parsing and merging logic, using made-up fixture records.

The fixtures are invented test data, not real sites. Run: python -m pytest tests
"""

import pandas as pd

from wotl import build, sources

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
        "Registered Charity Number": [1, 2, 3],
        "Registered Charity Name": ["Test Diocesan Trust", "Test Sports Club", "Sisters of Test"],
        "Primary Address": ["Dundalk, Co. Louth", "Drogheda, Co. Louth", "Cork"],
    })
    out = sources.parse_charities(df)
    assert list(out["name"]) == ["Test Diocesan Trust", "Sisters of Test"]
    assert list(out["in_county"]) == [True, False]
