"""Merge site points from all sources and draw the map."""

import math

import folium
import pandas as pd

from . import config

SOURCE_COLOURS = {
    "OpenStreetMap": "#2b6cb0",
    "NIAH": "#b7791f",
    "Dept of Education: primary-schools": "#2f855a",
    "Dept of Education: post-primary-schools": "#276749",
    "Tailte Éireann valuation list": "#6b46c1",
    "History seed list": "#c53030",
}


def _metres(lat1, lon1, lat2, lon2):
    r = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def merge_sites(points, radius_m=config.MERGE_RADIUS_M):
    """Group points within radius_m of each other into candidate sites.

    Simple single-link grouping, fine for a county (a few thousand points).
    Returns (points with a site_id column, one row per candidate site).
    """
    pts = points.dropna(subset=["lat", "lon"]).reset_index(drop=True).copy()
    parent = list(range(len(pts)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    lat, lon = pts["lat"].astype(float).values, pts["lon"].astype(float).values
    order = sorted(range(len(pts)), key=lambda i: lat[i])
    deg = radius_m / 111_000
    for a_idx, i in enumerate(order):
        for j in order[a_idx + 1:]:
            if lat[j] - lat[i] > deg:
                break
            if abs(lon[j] - lon[i]) < deg * 2 and _metres(lat[i], lon[i], lat[j], lon[j]) <= radius_m:
                parent[find(j)] = find(i)
    roots = [find(i) for i in range(len(pts))]
    ids = {r: n + 1 for n, r in enumerate(dict.fromkeys(roots))}
    pts["site_id"] = [f"{config.COUNTY[:2].upper()}-{ids[r]:04d}" for r in roots]

    def summarise(g):
        named = g[g["name"].astype(str).str.strip() != ""]
        return pd.Series({
            "name": named["name"].iloc[0] if len(named) else "",
            "all_names": " | ".join(dict.fromkeys(named["name"].astype(str))),
            "categories": ", ".join(sorted(set(g["category"].dropna().astype(str)))),
            "sources": ", ".join(sorted(set(g["source"]))),
            "n_sources": g["source"].nunique(),
            "denomination": "catholic" if (g["denomination"] == "catholic").any() else "unknown",
            "lat": g["lat"].astype(float).mean(),
            "lon": g["lon"].astype(float).mean(),
            "source_refs": " | ".join(g["source"] + ": " + g["source_id"].astype(str)),
            # Columns to fill during the pilot, in roadmap order.
            "folio_number": "",
            "registered_owner": "",
            "evidence_grade": "D",
            "checked_on": "",
        })

    if pts.empty:
        cols = ["site_id", "name", "all_names", "categories", "sources", "n_sources", "denomination",
                "lat", "lon", "source_refs", "folio_number", "registered_owner", "evidence_grade", "checked_on"]
        return pts, pd.DataFrame(columns=cols)
    sites = pts.groupby("site_id").apply(summarise, include_groups=False).reset_index()
    sites = sites.sort_values(["n_sources", "name"], ascending=[False, True])
    return pts, sites


def _detail(row):
    """School patron, NIAH use, or OSM tags: whatever the source says about use."""
    raw = row.get("raw_use")
    if not isinstance(raw, str) or not raw.strip() or raw.startswith("{"):
        return ""
    return f"{raw}<br>"


def _popup(row):
    gmap = f"https://www.google.com/maps/search/?api=1&query={row.lat:.6f},{row.lon:.6f}"
    return folium.Popup(
        f"<b>{row['name'] or '(unnamed)'}</b><br>"
        f"<i>{row['category']}</i> · {row['source']}<br>"
        f"Denomination: {row['denomination']}<br>"
        f"{_detail(row)}"
        f"{row['address']}<br>"
        f"<a href='{row['source_url']}' target='_blank'>source record</a> · "
        f"<a href='{gmap}' target='_blank'>open location</a><br>"
        f"Site {row['site_id']} · grade D (unverified lead)",
        max_width=320,
    )


def draw_map(points, sites, path=None):
    if points.empty:
        centre = [53.9, -6.5]
    else:
        centre = [points["lat"].astype(float).mean(), points["lon"].astype(float).mean()]
    m = folium.Map(location=centre, zoom_start=10, tiles="OpenStreetMap", control_scale=True)
    for source, g in points.groupby("source"):
        layer = folium.FeatureGroup(name=f"{source} ({len(g)})", show=True)
        colour = SOURCE_COLOURS.get(source, "#4a5568")
        for _, row in g.iterrows():
            folium.CircleMarker(
                [row.lat, row.lon], radius=5, color=colour, fill=True, fill_opacity=0.8,
                weight=1, popup=_popup(row), tooltip=row["name"] or row["category"],
            ).add_to(layer)
        layer.add_to(m)
    multi = sites[sites["n_sources"] > 1]
    ring = folium.FeatureGroup(name=f"Sites confirmed by 2+ sources ({len(multi)})", show=False)
    for _, s in multi.iterrows():
        folium.Circle([s.lat, s.lon], radius=config.MERGE_RADIUS_M, color="#000", weight=2, fill=False,
                      tooltip=f"{s['name']} · {s['sources']}").add_to(ring)
    ring.add_to(m)
    folium.LayerControl(collapsed=False).add_to(m)
    title = (
        f"<div style='position:fixed;top:10px;left:50px;z-index:9999;background:white;padding:8px 12px;"
        f"border:1px solid #999;border-radius:4px;font:13px sans-serif;max-width:360px'>"
        f"<b>Who Owns the Land? First-attempt map, County {config.COUNTY}</b><br>"
        f"Candidate Church sites from open data. Every point is a grade D lead: "
        f"location only, ownership not checked.</div>"
    )
    m.get_root().html.add_child(folium.Element(title))
    if path:
        m.save(str(path))
    return m
