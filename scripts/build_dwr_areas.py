#!/usr/bin/env python3
"""
Build the two Division of Water Resources commissioner areas for the Roaring
Fork (Water District 38) and append them to data/clean/boundaries.geojson.

WHY THIS EXISTS
---------------
DWR publishes no map of the split between its two local water commissioners -
only a narrative description. Heather Ramsey supplied the actual breakdown by
creek (7/30/26):

  Bill Blakeslee  - Emma UP the Roaring Fork (Aspen & Basalt area):
      Brush Creek, Capitol Creek, Castle Creek, Fryingpan River, Owl Creek,
      Ruedi Reservoir, Sopris Creek, Snowmass Creek, Woody Creek

  Heather Ramsey  - Emma DOWN the Roaring Fork (Carbondale / El Jebel area):
      Blue Creek, Cattle Creek, Crystal River, Four Mile Creek, Prince Creek,
      Three Mile Creek, Thomas Creek, Thompson Creek

Rather than hand-drawing a line near Emma, this builds each area from USGS
HUC-12 subwatersheds. Water commissioners administer by drainage, so drainage
boundaries are the right unit - and the result is defensible against a source
rather than being an eyeballed guess.

Her creek list maps almost exactly onto HUC-10 groupings. The one group that
splits across both commissioners is 1401000408, which contains Sopris Creek
(Bill) and Blue Creek (Heather) - and that IS the Emma line: Sopris enters the
Roaring Fork just above Emma, Blue Creek just below.

Creeks she named that aren't HUC-12 names (Owl, Prince, Three Mile, Thomas)
fall inside subwatersheds already assigned to the correct commissioner, so
they're covered without special handling.

STATUS: NOT CURRENTLY USED BY THE MAP
-------------------------------------
Run 7/29/26, and the output was deliberately NOT kept. The two areas tile the
watershed exactly (58% / 42%), so drawing them put a third stacked fill over
every point on the map - on top of BWCD's 77% - which buried the small
municipal shapes and made the popup's "here" list read DWR + BWCD + town
almost everywhere. DWR also isn't a service area in the sense the other
polygons are: nobody is "served by" a water commissioner, it's who
administers water rights where. So DWR is described in text instead, per the
original decision on the 7/30 planning call.

This script is kept because the reasoning below (mapping Heather's creek list
onto subwatersheds) is the hard part and shouldn't have to be redone. If the
areas are ever wanted - a dedicated toggle, a separate figure, an outline-only
treatment - run it again rather than rebuilding the logic.

CAVEATS worth keeping in mind
-----------------------------
- Drainage divides are an interpretation of a narrative description, not an
  official DWR boundary. The caveat field says so.
- The shared edge follows subwatershed divides, so near Emma it will not be a
  clean line across the valley - it steps around the Sopris/Blue Creek
  drainages. That's more accurate than a straight line, but looks less tidy.

USAGE
-----
    python3 scripts/build_dwr_areas.py            # writes the boundaries
    python3 scripts/build_dwr_areas.py --dry-run  # fetch + report, write nothing

Requires network access (queries the USGS WBD service) plus geopandas/requests.
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests
from shapely.geometry import Polygon, MultiPolygon, shape
from shapely.ops import unary_union
from shapely.validation import make_valid

REPO = Path(__file__).resolve().parent.parent
BOUNDARIES = REPO / "data" / "clean" / "boundaries.geojson"

WBD_HUC12 = "https://hydro.nationalmap.gov/arcgis/rest/services/wbd/MapServer/6/query"
ROARING_FORK_HUC8 = "14010004"

# HUC-10 groups (digits 9-10 of the HUC-12 code), assigned from Heather's list.
UPPER_GROUPS = {"01", "02", "03", "04", "05", "06"}
#  01 headwaters Roaring Fork (Lincoln, Difficult, Hunter, McFarlane)
#  02 Castle Creek        03 Maroon Creek
#  04 Snowmass / Capitol  05 Fryingpan incl. Ruedi Reservoir
#  06 Woody Creek / Brush Creek
LOWER_GROUPS = {"07", "09", "10"}
#  07 Crystal River incl. Thompson Creek
#  09 Cattle Creek        10 Fourmile Creek / outlet Roaring Fork

# Group 08 straddles the split - assign its two subwatersheds individually.
SPLIT_GROUP = "08"
SPLIT_ASSIGNMENT = {
    "140100040801": "upper",   # Sopris Creek  - Bill, enters just above Emma
    "140100040802": "lower",   # Blue Creek    - Heather, just below Emma
}


def side_for(huc12: str) -> str:
    group = huc12[8:10]
    if group == SPLIT_GROUP:
        try:
            return SPLIT_ASSIGNMENT[huc12]
        except KeyError:
            raise SystemExit(
                f"HUC-12 {huc12} is in group {SPLIT_GROUP} but isn't in "
                "SPLIT_ASSIGNMENT. The WBD may have re-delineated this group - "
                "check which drainage it covers and assign it explicitly."
            )
    if group in UPPER_GROUPS:
        return "upper"
    if group in LOWER_GROUPS:
        return "lower"
    raise SystemExit(
        f"HUC-12 {huc12} is in unrecognized group {group}. The WBD may have "
        "added a subwatershed - assign it to UPPER_GROUPS or LOWER_GROUPS."
    )


def fetch_subwatersheds() -> gpd.GeoDataFrame:
    """All HUC-12s inside the Roaring Fork HUC-8, in WGS84."""
    params = {
        "where": f"huc12 LIKE '{ROARING_FORK_HUC8}%'",
        "outFields": "huc12,name,areasqkm",
        "outSR": "4326",
        "f": "geojson",
    }
    print(f"Querying USGS WBD for HUC-12s under {ROARING_FORK_HUC8} ...")
    resp = requests.get(WBD_HUC12, params=params, timeout=120)
    resp.raise_for_status()
    payload = resp.json()

    if "features" not in payload:
        raise SystemExit(f"Unexpected response from WBD:\n{json.dumps(payload)[:500]}")

    rows = []
    for feat in payload["features"]:
        props = feat.get("properties") or feat.get("attributes") or {}
        geom = shape(feat["geometry"])
        if not geom.is_valid:
            geom = make_valid(geom)
        rows.append(
            {
                "huc12": props["huc12"],
                "name": props.get("name", ""),
                "geometry": geom,
            }
        )

    gdf = gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:4326")
    print(f"  {len(gdf)} subwatersheds returned")
    return gdf


def drop_holes(geom):
    """Keep exterior rings only.

    Dissolving adjacent subwatersheds leaves hairline gaps where their shared
    edges don't perfectly coincide - the same artifact that produced scattered
    'fragment' shapes earlier in this project. A drainage area has no genuine
    internal exclaves, so any interior ring here is noise.
    """
    if geom.geom_type == "Polygon":
        return Polygon(geom.exterior)
    if geom.geom_type == "MultiPolygon":
        return MultiPolygon([Polygon(p.exterior) for p in geom.geoms])
    return geom


def build(dry_run: bool = False) -> None:
    subs = fetch_subwatersheds()
    subs["side"] = subs["huc12"].map(side_for)

    counts = subs["side"].value_counts().to_dict()
    print(f"  assigned: upper={counts.get('upper', 0)}  lower={counts.get('lower', 0)}")

    boundaries = gpd.read_file(BOUNDARIES)
    watershed = boundaries.loc[
        boundaries["boundary_id"] == "huc8_roaring_fork", "geometry"
    ].iloc[0]

    # Work in an equal-area projection so reported areas are true.
    subs_eq = subs.to_crs("EPSG:5070")
    ws_eq = gpd.GeoSeries([watershed], crs="EPSG:4326").to_crs("EPSG:5070").iloc[0]

    built = {}
    for side in ("upper", "lower"):
        parts = subs_eq.loc[subs_eq["side"] == side, "geometry"].tolist()
        merged = unary_union(parts)
        # Clip to our own watershed so the outer edge matches the rest of the
        # project exactly instead of wobbling along a second WBD generalization.
        merged = drop_holes(make_valid(merged.intersection(ws_eq)))
        built[side] = merged
        print(f"  {side}: {merged.area / 1e6:>8,.1f} km²")

    total = sum(g.area for g in built.values()) / 1e6
    print(f"  combined: {total:,.1f} km²  (watershed is {ws_eq.area / 1e6:,.1f})")
    overlap = built["upper"].intersection(built["lower"]).area / 1e6
    print(f"  overlap between the two: {overlap:,.3f} km² (should be ~0)")

    if dry_run:
        print("\n--dry-run: nothing written.")
        return

    meta = {
        "upper": dict(
            boundary_id="dwr_upper",
            name="DWR Water District 38 - upper (Blakeslee)",
            label="DWR upper",
            caveat=(
                "Division of Water Resources commissioner area, Emma upstream - "
                "Aspen and Basalt side. No official map of this split exists; DWR "
                "describes it narratively. Built from USGS HUC-12 "
                "subwatersheds matching the creeks Heather Ramsey listed for Bill "
                "Blakeslee (Brush, Capitol, Castle, Fryingpan, Owl, Ruedi, Sopris, "
                "Snowmass, Woody). Water commissioners administer by drainage, so "
                "drainage divides are the appropriate unit - but this is an "
                "interpretation of a written description, NOT an official boundary. "
                "Clipped to the Roaring Fork HUC-8."
            ),
        ),
        "lower": dict(
            boundary_id="dwr_lower",
            name="DWR Water District 38 - lower (Ramsey)",
            label="DWR lower",
            caveat=(
                "Division of Water Resources commissioner area, Emma downstream - "
                "Carbondale and El Jebel side, including the Crystal River. No "
                "official map of this split exists; DWR describes it narratively. "
                "Built from USGS HUC-12 subwatersheds matching the creeks "
                "Heather Ramsey listed for her own area (Blue, Cattle, Crystal, "
                "Four Mile, Prince, Three Mile, Thomas, Thompson). Water "
                "commissioners administer by drainage, so drainage divides are the "
                "appropriate unit - but this is an interpretation of a written "
                "description, NOT an official boundary. Clipped to the Roaring "
                "Fork HUC-8."
            ),
        ),
    }

    new_rows = []
    for side, geom_eq in built.items():
        geom = gpd.GeoSeries([geom_eq], crs="EPSG:5070").to_crs("EPSG:4326").iloc[0]
        anchor_src = (
            max(geom_eq.geoms, key=lambda p: p.area)
            if geom_eq.geom_type == "MultiPolygon"
            else geom_eq
        )
        anchor = (
            gpd.GeoSeries([anchor_src.representative_point()], crs="EPSG:5070")
            .to_crs("EPSG:4326")
            .iloc[0]
        )
        m = meta[side]
        new_rows.append(
            {
                "id": None,
                "boundary_id": m["boundary_id"],
                "name": m["name"],
                "label": m["label"],
                "display": "org",
                "areasqkm": round(geom_eq.area / 1e6, 2),
                "huc_code": "",
                "label_lon": round(anchor.x, 6),
                "label_lat": round(anchor.y, 6),
                "source": "USGS WBD HUC-12 subwatersheds, grouped per DWR commissioner creek list",
                "pulldate": date.today().isoformat(),
                "srcurl": WBD_HUC12,
                "caveat": m["caveat"],
                "geometry": geom,
            }
        )

    existing = boundaries[~boundaries["boundary_id"].isin(["dwr_upper", "dwr_lower"])]
    out = gpd.GeoDataFrame(
        pd.concat([existing, gpd.GeoDataFrame(new_rows, crs="EPSG:4326")], ignore_index=True),
        crs="EPSG:4326",
    )
    out["id"] = range(len(out))
    out["pulldate"] = out["pulldate"].astype(str)

    # Build the whole string before opening the file - if serialization raises
    # after open(), the file is already truncated and the data is gone.
    json_text = out.to_json()
    BOUNDARIES.write_text(json_text)

    print(f"\nWrote {BOUNDARIES.relative_to(REPO)} - now {len(out)} boundaries.")
    print("Add matching entries to data/clean/orgs.json for DWR, then reload the map.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="fetch and report, write nothing")
    args = ap.parse_args()
    try:
        build(dry_run=args.dry_run)
    except requests.RequestException as exc:
        sys.exit(f"Network error querying the WBD service: {exc}")
