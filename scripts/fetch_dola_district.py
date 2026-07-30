#!/usr/bin/env python3
"""
Pull an authoritative district or municipal boundary from Colorado DOLA and
replace the matching row in data/clean/boundaries.geojson.

WHY
---
DOLA (Department of Local Affairs) maintains the state's special-district and
municipal boundary registry. It's the authoritative source, and most boundaries
in this project already come from it. Anything sourced from an org-provided KML
or a georeferenced PDF is a second-hand copy that can drift or be generalized -
Snowmass W&S, for instance, arrived as a KML whose own note called it a
"general perimeter", which is smoother than the district's published map.

Use this to move a boundary onto the authoritative source, or to refresh one
after a district reports a change.

FINDING AN LGID
---------------
Search by name first (no geometry, cheap):

    python3 scripts/fetch_dola_district.py --search snowmass
    python3 scripts/fetch_dola_district.py --search "west divide" --layer all

Then fetch by the LGID it prints:

    python3 scripts/fetch_dola_district.py --lgid 49013 --boundary-id swsd_boundary
    python3 scripts/fetch_dola_district.py --lgid 49013 --boundary-id swsd_boundary --dry-run

WHAT IT DOES TO THE GEOMETRY
----------------------------
Matches how every other boundary in this project is prepared:
  - drops interior holes (source data carries digitizing slivers that render as
    stray gap shapes - see the README's interior-holes note)
  - drops parts under --min-part-km2 (default 1.0) as digitizing artifacts,
    unless --keep-all-parts is passed. Some districts have genuinely detached
    inclusions, so check the reported part list before accepting.
  - clips to the Roaring Fork HUC-8, since the map is watershed-scoped
  - recomputes areasqkm in EPSG:5070 and a label anchor inside the shape

It always prints the before/after so you can see what changed, and never
touches any row other than the one named by --boundary-id.
"""

import argparse
import sys
from datetime import date
from pathlib import Path

import geopandas as gpd
import requests
from shapely.geometry import MultiPolygon, Polygon, shape
from shapely.validation import make_valid

REPO = Path(__file__).resolve().parent.parent
BOUNDARIES = REPO / "data" / "clean" / "boundaries.geojson"

DOLA = "https://services3.arcgis.com/DgjqnJA1rgO92Soi/arcgis/rest/services"
LAYERS = {
    "watsan": (
        f"{DOLA}/Water_and_Sanitation_Districts/FeatureServer/0/query",
        "Colorado DOLA - Water and Sanitation Districts",
    ),
    "all": (
        f"{DOLA}/All_Active_DOLA_Districts_-_private_staging_area_view/FeatureServer/0/query",
        "Colorado DOLA - All Active Districts",
    ),
    "muni": (
        f"{DOLA}/Colorado_Municipal_Boundaries/FeatureServer/0/query",
        "Colorado DOLA - Municipal Boundaries",
    ),
}


def query(url: str, params: dict) -> dict:
    resp = requests.get(url, params={**params, "f": "geojson"}, timeout=120)
    resp.raise_for_status()
    payload = resp.json()
    if "error" in payload:
        raise SystemExit(f"DOLA returned an error: {payload['error']}")
    return payload


def search(term: str, layer: str) -> None:
    url, label = LAYERS[layer]
    payload = query(
        url,
        {
            "where": f"UPPER(lgname) LIKE '%{term.upper()}%'",
            "outFields": "lgname,lgid",
            "returnGeometry": "false",
        },
    )
    feats = payload.get("features", [])
    if not feats:
        print(f"No match for '{term}' in {label}.")
        print("Try --layer all, or a shorter search term.")
        return
    print(f"{label} - {len(feats)} match(es):\n")
    for f in feats:
        p = f["properties"]
        print(f"  lgid {p.get('lgid'):>8}   {p.get('lgname')}")


def tidy(geom, min_part_km2: float, keep_all: bool):
    """Clean up source geometry; returns (geometry, notes)."""
    notes = []
    if not geom.is_valid:
        geom = make_valid(geom)

    parts = list(geom.geoms) if geom.geom_type == "MultiPolygon" else [geom]

    # Measure parts in an equal-area CRS before deciding what to drop.
    areas = (
        gpd.GeoSeries(parts, crs="EPSG:4326").to_crs("EPSG:5070").area / 1e6
    ).tolist()
    ranked = sorted(zip(parts, areas), key=lambda t: -t[1])

    print(f"  source has {len(parts)} part(s):")
    for i, (_, a) in enumerate(ranked[:12], 1):
        print(f"      {i:>2}. {a:>10,.3f} km²")
    if len(ranked) > 12:
        print(f"      ... and {len(ranked) - 12} more")

    if keep_all:
        kept = [p for p, _ in ranked]
    else:
        kept = [p for p, a in ranked if a >= min_part_km2]
        dropped = len(ranked) - len(kept)
        if dropped:
            lost = sum(a for _, a in ranked if a < min_part_km2)
            notes.append(
                f"Dropped {dropped} part(s) under {min_part_km2} km² "
                f"({lost:.3f} km² total) as digitizing artifacts."
            )
            print(f"  dropping {dropped} part(s) under {min_part_km2} km²")
        if not kept:
            raise SystemExit(
                f"Every part is under {min_part_km2} km². Lower --min-part-km2 "
                "or pass --keep-all-parts."
            )

    # Exterior rings only - interior holes in this source data are slivers.
    holes = sum(len(p.interiors) for p in kept)
    cleaned = [Polygon(p.exterior) for p in kept]
    if holes:
        notes.append(f"Dropped {holes} interior hole(s) from the source geometry.")
        print(f"  dropping {holes} interior hole(s)")

    out = cleaned[0] if len(cleaned) == 1 else MultiPolygon(cleaned)
    return out, notes


def fetch(lgid: str, boundary_id: str, layer: str, min_part_km2: float,
          keep_all: bool, dry_run: bool) -> None:
    url, source_label = LAYERS[layer]
    payload = query(url, {"where": f"lgid = '{lgid}'", "outFields": "lgname,lgid"})
    feats = payload.get("features", [])
    if not feats:
        raise SystemExit(f"No feature with lgid={lgid} in {source_label}.")
    if len(feats) > 1:
        print(f"Note: {len(feats)} features share lgid={lgid}; merging them.")

    name = feats[0]["properties"].get("lgname", "")
    geom = shape(feats[0]["geometry"])
    for f in feats[1:]:
        geom = geom.union(shape(f["geometry"]))

    print(f"\nFetched: {name}  (lgid {lgid})")
    geom, notes = tidy(geom, min_part_km2, keep_all)

    boundaries = gpd.read_file(BOUNDARIES)
    if boundary_id not in set(boundaries["boundary_id"]):
        raise SystemExit(
            f"'{boundary_id}' isn't in boundaries.geojson. Existing ids:\n  "
            + "\n  ".join(sorted(boundaries["boundary_id"]))
        )
    idx = boundaries.index[boundaries["boundary_id"] == boundary_id][0]

    # Clip to the watershed - this map is watershed-scoped.
    ws = boundaries.loc[
        boundaries["boundary_id"] == "huc8_roaring_fork", "geometry"
    ].iloc[0]
    eq = gpd.GeoSeries([geom, ws], crs="EPSG:4326").to_crs("EPSG:5070")
    full_km2 = eq.iloc[0].area / 1e6
    clipped_eq = make_valid(eq.iloc[0].intersection(eq.iloc[1]))
    clipped_km2 = clipped_eq.area / 1e6

    old_km2 = float(boundaries.loc[idx, "areasqkm"])
    print()
    print(f"  full district      {full_km2:>10,.2f} km²")
    print(f"  clipped to basin   {clipped_km2:>10,.2f} km²  ({clipped_km2/full_km2*100:.1f}% inside)")
    print(f"  currently on map   {old_km2:>10,.2f} km²")
    print(f"  change             {clipped_km2 - old_km2:>+10,.2f} km²")

    if dry_run:
        print("\n--dry-run: nothing written.")
        return

    clipped = gpd.GeoSeries([clipped_eq], crs="EPSG:5070").to_crs("EPSG:4326").iloc[0]
    anchor_src = (
        max(clipped_eq.geoms, key=lambda p: p.area)
        if clipped_eq.geom_type == "MultiPolygon"
        else clipped_eq
    )
    anchor = (
        gpd.GeoSeries([anchor_src.representative_point()], crs="EPSG:5070")
        .to_crs("EPSG:4326")
        .iloc[0]
    )

    today = date.today()
    caveat = (
        f"Official boundary from {source_label} (lgid {lgid}), pulled "
        f"{today.month}/{today.day}/{today:%y}. "
        + " ".join(notes)
    ).strip()
    if clipped_km2 < full_km2 - 0.01:
        caveat += (
            f" CLIPPED to the Roaring Fork HUC-8 for display - this is NOT the "
            f"legal boundary; the full district is {full_km2:,.0f} km² and "
            f"{full_km2 - clipped_km2:,.0f} km² lies outside the watershed."
        )

    boundaries.loc[idx, "geometry"] = clipped
    boundaries.loc[idx, "areasqkm"] = round(clipped_km2, 2)
    boundaries.loc[idx, "label_lon"] = round(anchor.x, 6)
    boundaries.loc[idx, "label_lat"] = round(anchor.y, 6)
    boundaries.loc[idx, "source"] = source_label
    boundaries.loc[idx, "srcurl"] = url.replace("/query", "")
    boundaries.loc[idx, "pulldate"] = today.isoformat()
    boundaries.loc[idx, "caveat"] = caveat

    boundaries["pulldate"] = boundaries["pulldate"].astype(str)
    # Serialize fully before opening the file - a failure mid-write on an
    # already-truncated file destroys the data.
    json_text = boundaries.to_json()
    BOUNDARIES.write_text(json_text)
    print(f"\nUpdated '{boundary_id}' in {BOUNDARIES.relative_to(REPO)}.")
    print("Reload the map and confirm the shape looks right before committing.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--search", metavar="TERM", help="find LGIDs by name")
    ap.add_argument("--lgid", help="DOLA local government id to fetch")
    ap.add_argument("--boundary-id", help="row in boundaries.geojson to replace")
    ap.add_argument("--layer", choices=sorted(LAYERS), default="watsan",
                    help="which DOLA dataset (default: watsan)")
    ap.add_argument("--min-part-km2", type=float, default=1.0,
                    help="drop MultiPolygon parts smaller than this (default 1.0)")
    ap.add_argument("--keep-all-parts", action="store_true",
                    help="keep every part, however small")
    ap.add_argument("--dry-run", action="store_true", help="report only, write nothing")
    args = ap.parse_args()

    try:
        if args.search:
            search(args.search, args.layer)
        elif args.lgid and args.boundary_id:
            fetch(args.lgid, args.boundary_id, args.layer,
                  args.min_part_km2, args.keep_all_parts, args.dry_run)
        else:
            ap.error("use --search TERM, or both --lgid and --boundary-id")
    except requests.RequestException as exc:
        sys.exit(f"Network error talking to DOLA: {exc}")
