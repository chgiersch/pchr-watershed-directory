#!/usr/bin/env python3
"""
Build the state-zoom reference layers: Colorado outline, county lines, and the
true extents of the basin- and state-scale organizations.

WHY THESE EXIST
---------------
The county's review (Tim Braun, 8/26/26) landed on a real gap: statewide and
basin-scale organizations were unrecognizable as such on a watershed-only map.
The fix is letting the map zoom out to Colorado, with each of those orgs shown
at its actual extent instead of all of them borrowing the watershed highlight.

There is no statewide basemap on purpose. At state zoom the reader needs
jurisdiction outlines and a few landmarks, not street detail - and a statewide
z0-15 PMTiles extract would run to hundreds of MB against GitHub's 100 MB
file limit. So state-scale context is drawn from the small GeoJSONs this
script produces, and the detailed basemap keeps its watershed bbox.

WHAT IT WRITES
--------------
data/reference/co_counties.geojson
    All 64 Colorado counties, simplified for state zoom. Drawn as faint lines:
    county boundaries ARE the landmark grid in rural Colorado, and CRD's edges
    visibly follow them, which is what makes its shape legible.

data/reference/reference_extents.geojson
    One feature per organization extent that is bigger than the watershed:

    extent_id        used by     what it is
    state_colorado   CWCB, DWR   state outline (dissolved from the counties)
    cbrt_basin       CBRT        Colorado River mainstem basin within CO
                                 (USGS WBD HUC-4 1401, clipped to the state)
    crd_district     CRD         the district's official boundary from
                                 Colorado DOLA (lgid 64046)

    The Roaring Fork watershed is NOT in this file. It already lives as the
    frame row in data/clean/boundaries.geojson - one shape, one place - and
    the map assembles its runtime reference source from both files.

VERIFY BEFORE COMMITTING
------------------------
CBRT: HUC-4 1401 was confirmed against the roundtable's published map by
Chris, 8/27/26. Re-check only if the WBD source or the boundary changes.

CRD: compare against the district's own map -
coloradoriverdistrict.org/map-gallery/. The DOLA shape should match it;
a county-based reconstruction was rejected 8/27/26 for overshooting it.

USAGE
-----
    python3 scripts/build_reference_extents.py            # fetch + write both
    python3 scripts/build_reference_extents.py --dry-run  # fetch + report only

Needs network (Census and USGS). Run from your own machine, not the sandbox.
"""

import argparse
import io
import sys
from datetime import date
from pathlib import Path

import geopandas as gpd
import requests
from shapely.ops import unary_union
from shapely.validation import make_valid

REPO = Path(__file__).resolve().parent.parent
OUT_COUNTIES = REPO / "data" / "reference" / "co_counties.geojson"
OUT_EXTENTS = REPO / "data" / "reference" / "reference_extents.geojson"

# Census cartographic boundary files, 1:500k - generalized for thematic
# mapping, which is exactly this use. The raw TIGER lines are far heavier and
# carry coastal water that just bloats the file.
CENSUS_COUNTIES = (
    "https://www2.census.gov/geo/tiger/GENZ2023/shp/cb_2023_us_county_500k.zip"
)

# USGS Watershed Boundary Dataset REST service - same source the project's
# HUC-8 and HUC-10 shapes came from. Layer 2 is HUC-4 subregions.
WBD_HUC4 = "https://hydro.nationalmap.gov/arcgis/rest/services/wbd/MapServer/2/query"

# The River District's own boundary, from Colorado DOLA - the same registry
# every other district on this map came from. lgid found 8/27/26 via
# fetch_dola_district.py --search "river water conservation" --layer all.
#
# A first version of this script reconstructed the district from county
# polygons (12 whole + 3 partial, per Montrose County's description). It was
# wrong twice over: the partial counties' membership follows the Gunnison
# basin divide, not the mainstem basin this script had to hand, and the real
# boundary carries carve-outs county math cannot know about. Chris compared
# the reconstruction against the district's published map and it visibly
# overshot. Lesson already learned once on this project with BWCD: fetch the
# authoritative shape, don't derive it.
DOLA_ALL = ("https://services3.arcgis.com/DgjqnJA1rgO92Soi/arcgis/rest/services/"
            "All_Active_DOLA_Districts_-_private_staging_area_view/FeatureServer/0/query")
CRD_LGID = "64046"

# Simplification tolerance in meters (applied in EPSG:5070). 250 m is
# invisible at state zoom - one screen pixel there is roughly 900 m - and
# cuts the county file to a fraction of its raw size.
TOLERANCE_M = 250


def fetch_counties() -> gpd.GeoDataFrame:
    """Download the national county file and keep Colorado (STATEFP 08)."""
    print(f"Fetching {CENSUS_COUNTIES.rsplit('/', 1)[-1]} ...")
    resp = requests.get(CENSUS_COUNTIES, timeout=300)
    resp.raise_for_status()
    # geopandas/pyogrio reads a zipped shapefile straight from bytes - no
    # unpacking step, same as the ingest script's zip:// handling.
    gdf = gpd.read_file(io.BytesIO(resp.content))
    co = gdf[gdf["STATEFP"] == "08"].copy()
    if len(co) != 64:
        # Colorado has had exactly 64 counties since 2001 (Broomfield). Any
        # other count means the filter or the source changed - stop, because
        # the state outline is dissolved from this set.
        raise SystemExit(f"Expected 64 Colorado counties, got {len(co)}.")
    print(f"  {len(co)} Colorado counties, CRS {co.crs.to_string()}")
    return co.to_crs("EPSG:4326")


def fetch_cbrt_basin() -> "gpd.GeoSeries":
    """HUC-4 1401: the Colorado River mainstem basin (headwaters subregion)."""
    print("Fetching HUC-4 1401 from USGS WBD ...")
    resp = requests.get(WBD_HUC4, params={
        "where": "huc4 = '1401'",
        "outFields": "huc4,name",
        "f": "geojson",
    }, timeout=300)
    resp.raise_for_status()
    payload = resp.json()
    if "error" in payload:
        raise SystemExit(f"WBD returned an error: {payload['error']}")
    feats = payload.get("features", [])
    if len(feats) != 1:
        raise SystemExit(f"Expected exactly one HUC-4 1401 feature, got {len(feats)}.")
    print(f"  got: {feats[0]['properties'].get('name', '?')}")
    return gpd.GeoDataFrame.from_features(feats, crs="EPSG:4326").geometry


def fetch_crd() -> "gpd.GeoSeries.geometry":
    """The River District's official boundary from DOLA, by lgid."""
    print(f"Fetching CRD (lgid {CRD_LGID}) from Colorado DOLA ...")
    resp = requests.get(DOLA_ALL, params={
        "where": f"lgid = '{CRD_LGID}'",
        "outFields": "lgname,lgid",
        "f": "geojson",
    }, timeout=300)
    resp.raise_for_status()
    payload = resp.json()
    if "error" in payload:
        raise SystemExit(f"DOLA returned an error: {payload['error']}")
    feats = payload.get("features", [])
    if not feats:
        raise SystemExit(f"No feature with lgid={CRD_LGID} in DOLA All Active Districts.")
    name = feats[0]["properties"].get("lgname", "?")
    print(f"  got: {name} ({len(feats)} feature(s))")
    geoms = gpd.GeoDataFrame.from_features(feats, crs="EPSG:4326").geometry
    return make_valid(unary_union(geoms.values))


def simplify(geom, tolerance_m=TOLERANCE_M):
    """Simplify in an equal-area CRS so the tolerance means meters everywhere.

    Simplifying in EPSG:4326 would make the tolerance degrees - a unit whose
    ground size changes with latitude, so shapes would be simplified unevenly.
    """
    s = gpd.GeoSeries([geom], crs="EPSG:4326").to_crs("EPSG:5070")
    out = s.simplify(tolerance_m, preserve_topology=True).to_crs("EPSG:4326")
    return make_valid(out.iloc[0])


def area_km2(geom) -> float:
    return gpd.GeoSeries([geom], crs="EPSG:4326").to_crs("EPSG:5070").area.iloc[0] / 1e6


def anchor(geom):
    """Label point guaranteed inside the shape - centroids drift outside on
    concave shapes, and every label on this map renders from a precomputed
    point because MapLibre places one label per polygon per tile."""
    eq = gpd.GeoSeries([geom], crs="EPSG:4326").to_crs("EPSG:5070").iloc[0]
    src = max(eq.geoms, key=lambda p: p.area) if eq.geom_type == "MultiPolygon" else eq
    pt = gpd.GeoSeries([src.representative_point()], crs="EPSG:5070").to_crs("EPSG:4326").iloc[0]
    return round(pt.x, 6), round(pt.y, 6)


def main(dry_run: bool) -> None:
    today = date.today().isoformat()
    counties = fetch_counties()
    huc1401 = fetch_cbrt_basin()
    crd = fetch_crd()

    # ---- State outline: dissolve the counties rather than fetching a second
    # file. One download, and the outline can never disagree with the county
    # lines drawn on top of it.
    state = make_valid(unary_union(counties.geometry.values))

    # ---- CBRT: the mainstem basin, kept inside Colorado. Chris compared this
    # against the roundtable's published map 8/27/26 - good match.
    cbrt = make_valid(huc1401.iloc[0].intersection(state))

    extents = [
        ("state_colorado", "Colorado", state,
         "US Census cartographic boundary 1:500k, counties dissolved",
         "Statewide agencies (CWCB; DWR is statewide with local District 38)."),
        ("cbrt_basin", "Colorado River Basin", cbrt,
         "USGS WBD HUC-4 1401, clipped to Colorado",
         "Colorado Basin Roundtable. HUC-4 1401 approximation confirmed "
         "against the roundtable's published map by Chris, 8/27/26."),
        ("crd_district", "Colorado River District", crd,
         f"Colorado DOLA - All Active Districts (lgid {CRD_LGID})",
         "Official district boundary. VERIFY against the district's own "
         "published map (coloradoriverdistrict.org/map-gallery/) - a county "
         "reconstruction was rejected 8/27/26 for visibly overshooting it."),
    ]

    print()
    rows = []
    for eid, label, geom, source, caveat in extents:
        geom = simplify(geom)
        lon, lat = anchor(geom)
        km2 = area_km2(geom)
        print(f"  {eid:<16} {km2:>12,.0f} km²   label anchor {lon}, {lat}")
        rows.append({
            "extent_id": eid, "label": label, "areasqkm": round(km2, 1),
            "source": source, "pulldate": today, "caveat": caveat,
            "label_lon": lon, "label_lat": lat, "geometry": geom,
        })

    counties_out = counties[["NAME", "geometry"]].rename(columns={"NAME": "name"})
    counties_out["geometry"] = [simplify(g) for g in counties_out.geometry]

    if dry_run:
        print("\n--dry-run: nothing written.")
        return

    # Serialize fully before opening either file - open(path, 'w') truncates
    # immediately, so a failure mid-serialization would destroy the previous
    # copy. Same rule as every other writer in scripts/.
    extents_gdf = gpd.GeoDataFrame(rows, crs="EPSG:4326")
    extents_text = extents_gdf.to_json()
    counties_text = counties_out.to_json()
    OUT_EXTENTS.write_text(extents_text)
    OUT_COUNTIES.write_text(counties_text)

    print(f"\nWrote {OUT_EXTENTS.relative_to(REPO)} "
          f"({OUT_EXTENTS.stat().st_size / 1024:,.0f} KB)")
    print(f"Wrote {OUT_COUNTIES.relative_to(REPO)} "
          f"({OUT_COUNTIES.stat().st_size / 1024:,.0f} KB)")
    print("\nEyeball both against the published CBRT and CRD maps before "
          "committing - see VERIFY notes in each feature's caveat.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="fetch + report, write nothing")
    args = ap.parse_args()
    try:
        main(args.dry_run)
    except requests.RequestException as exc:
        sys.exit(f"Network error: {exc}")
