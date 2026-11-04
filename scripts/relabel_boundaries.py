#!/usr/bin/env python3
"""Recompute every boundary's label anchor as the pole of inaccessibility.

The anchors in data/clean/boundaries.geojson were written one row at a time
by the ingest scripts using representative_point(), which guarantees only a
point INSIDE the polygon - on Snowmass W&S it landed on the narrow upper
lobe, so the map label only appeared deep into the zoom (live click-through,
2026-11-04). polylabel anchors at the center of the widest part instead,
where there is room for the text. Geometry, area and provenance fields are
untouched: the anchor is derived display data, not provenance.

Run:  .venv/bin/python3 scripts/relabel_boundaries.py [--dry-run]
"""
import argparse
from pathlib import Path

import geopandas as gpd
from shapely.ops import polylabel

REPO = Path(__file__).resolve().parents[1]
BOUNDARIES = REPO / "data" / "clean" / "boundaries.geojson"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true",
                    help="print old -> new anchors, write nothing")
    args = ap.parse_args()

    boundaries = gpd.read_file(BOUNDARIES)
    # EPSG:5070 (equal-area, meters) for the distance math, matching the
    # ingest scripts; anchors are stored back in EPSG:4326.
    eq = boundaries.to_crs("EPSG:5070")

    for idx, geom in eq.geometry.items():
        row = boundaries.loc[idx]
        if geom is None or geom.geom_type not in ("Polygon", "MultiPolygon"):
            print(f"{row['boundary_id']:<28} skipped ({geom.geom_type if geom else 'empty'})")
            continue
        # Largest part only - same rule the ingest scripts use, so an
        # archipelago of slivers cannot pull the label off the main body.
        part = (max(geom.geoms, key=lambda p: p.area)
                if geom.geom_type == "MultiPolygon" else geom)
        # 10 m tolerance: the label moves by map-pixel amounts, so survey
        # precision would only slow the search down.
        anchor_eq = polylabel(part, tolerance=10)
        anchor = (gpd.GeoSeries([anchor_eq], crs="EPSG:5070")
                  .to_crs("EPSG:4326").iloc[0])
        print(f"{row['boundary_id']:<28} "
              f"({row['label_lon']:.6f}, {row['label_lat']:.6f}) -> "
              f"({anchor.x:.6f}, {anchor.y:.6f})")
        boundaries.loc[idx, "label_lon"] = round(anchor.x, 6)
        boundaries.loc[idx, "label_lat"] = round(anchor.y, 6)

    if args.dry_run:
        print("\n--dry-run: nothing written.")
        return

    boundaries["pulldate"] = boundaries["pulldate"].astype(str)
    # Serialize fully before opening the file - a failure mid-write on an
    # already-truncated file destroys the data (same guard as the ingest
    # scripts).
    json_text = boundaries.to_json()
    BOUNDARIES.write_text(json_text)
    print(f"\nRewrote label anchors in {BOUNDARIES.relative_to(REPO)}.")
    print("Reload the map and confirm label placement before committing.")


if __name__ == "__main__":
    main()
