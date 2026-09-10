#!/usr/bin/env python3
"""
Replace one boundary in data/clean/boundaries.geojson from a file someone sent us.

WHERE THIS SITS
---------------
Two scripts put geometry into boundaries.geojson, and the difference is where the
data comes from:

    fetch_dola_district.py    pulls from Colorado DOLA's live service, by lgid
    ingest_local_boundary.py  reads a file we were emailed (this one)

Both end the same way: one row replaced, clipped to the Roaring Fork HUC-8, area
and label anchor recomputed, provenance recorded. Nothing else is touched.

DOLA is preferred where it has the district, because it is authoritative and
current. Use this when a district sends its own file, or when DOLA doesn't carry
the boundary at all.

USAGE
-----
Look at what's in a file before committing to anything:

    python3 scripts/ingest_local_boundary.py --inspect data/raw/ConservancyDistricts.zip

Then pick the feature you want and replace a row:

    python3 scripts/ingest_local_boundary.py \
        --input data/raw/ConservancyDistricts.zip \
        --name-field DISTNAME \
        --name "Basalt Water Conservancy District" \
        --boundary-id bwcd_boundary \
        --source "Colorado conservancy districts shapefile via West Divide WCD" \
        --pulldate 2026-08-26 \
        --caveat "Provided by Gwen Garcelon, 8/26/26." \
        --dry-run

Drop --dry-run to actually write.

READING THE OUTPUT
------------------
It always prints the before/after areas. That comparison is the check that
matters: geospatial code fails silently far more often than it raises, and a
boundary that lands in the wrong place still renders perfectly happily. If the
new area isn't in the neighbourhood you expect, stop and find out why before
writing.
"""

import argparse
import sys
from datetime import date
from pathlib import Path

import geopandas as gpd
from shapely.geometry import MultiPolygon, Polygon
from shapely.validation import make_valid

REPO = Path(__file__).resolve().parent.parent
BOUNDARIES = REPO / "data" / "clean" / "boundaries.geojson"

# Everything on the map is cut to this. It's a row in boundaries.geojson rather
# than a separate file - one shape, one place.
FRAME_ID = "huc8_roaring_fork"

# Equal-area projection for the continental US. Areas MUST be measured here and
# never in EPSG:4326: degrees are not a unit of area, and a degree of longitude
# at this latitude is about 20% shorter than a degree of latitude. Measuring in
# 4326 produces a number that looks plausible and is meaningless.
EQUAL_AREA = "EPSG:5070"


def read_any(path: Path) -> gpd.GeoDataFrame:
    """Read a shapefile, zipped shapefile, KML or GeoJSON into EPSG:4326.

    Separate function because the zip handling is the non-obvious part and it's
    the format districts most often send - a shapefile is really 5-7 sibling
    files, so it almost always arrives zipped.
    """
    if path.suffix.lower() == ".zip":
        # GDAL's virtual filesystem reads inside the archive without unpacking.
        gdf = gpd.read_file(f"zip://{path}")
    else:
        gdf = gpd.read_file(path)

    if gdf.crs is None:
        raise SystemExit(
            f"{path.name} has no CRS. A shapefile carries it in the .prj - if that "
            "file is missing from the zip, ask the sender for it rather than guessing."
        )
    # Report the incoming CRS. A file arriving in something other than what you
    # assumed is the single most common cause of a boundary landing in the wrong
    # place, and it never raises an error.
    print(f"  read {len(gdf)} feature(s) from {path.name}, CRS {gdf.crs.to_string()}")
    return gdf.to_crs("EPSG:4326")


def inspect(path: Path) -> None:
    """Print every feature with its area, so you can pick one by name."""
    gdf = read_any(path)
    name_cols = [c for c in gdf.columns if gdf[c].dtype == object and c != "geometry"]
    eq = gdf.to_crs(EQUAL_AREA)
    print(f"\n  text columns you could match on: {', '.join(name_cols) or '(none)'}\n")
    for i, row in gdf.iterrows():
        label = " | ".join(str(row[c]) for c in name_cols[:2]) or f"feature {i}"
        print(f"  [{i:>3}] {eq.geometry.iloc[i].area / 1e6:>10,.1f} km²   {label}")


def tidy(geom, min_part_km2: float, keep_all: bool):
    """Repair and simplify one incoming geometry. Returns (geometry, notes).

    Deliberately identical in behaviour to fetch_dola_district.py's tidy(), so a
    boundary looks the same whether it came from DOLA or from an email. If you
    change the rules, change them in both places.
    """
    notes = []
    if not geom.is_valid:
        # Self-intersections and other topology errors. make_valid can return a
        # GeometryCollection, so anything non-polygonal gets dropped below.
        geom = make_valid(geom)

    parts = [p for p in (geom.geoms if geom.geom_type.startswith("Multi") else [geom])
             if p.geom_type == "Polygon"]
    if not parts:
        raise SystemExit("Nothing polygonal left after repair - inspect the source file.")

    areas = (gpd.GeoSeries(parts, crs="EPSG:4326").to_crs(EQUAL_AREA).area / 1e6).tolist()
    ranked = sorted(zip(parts, areas), key=lambda t: -t[1])

    print(f"  {len(parts)} part(s):")
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
            notes.append(f"Dropped {dropped} part(s) under {min_part_km2} km² "
                         f"({lost:.3f} km² total) as digitizing artifacts.")
            print(f"  dropping {dropped} part(s) under {min_part_km2} km²")
        if not kept:
            raise SystemExit(f"Every part is under {min_part_km2} km². Lower "
                             "--min-part-km2 or pass --keep-all-parts.")

    # Exterior rings only. Interior holes in this kind of source data are
    # digitizing slivers, and they render as stray gap shapes on the map - see
    # the README's interior-holes note for what that looked like.
    holes = sum(len(p.interiors) for p in kept)
    cleaned = [Polygon(p.exterior) for p in kept]
    if holes:
        notes.append(f"Dropped {holes} interior hole(s) from the source geometry.")
        print(f"  dropping {holes} interior hole(s)")

    return (cleaned[0] if len(cleaned) == 1 else MultiPolygon(cleaned)), notes


def ingest(args) -> None:
    gdf = read_any(Path(args.input))

    if args.name_field not in gdf.columns:
        raise SystemExit(f"No column '{args.name_field}'. Columns are: "
                         + ", ".join(gdf.columns))

    # A filter that matches nothing returns an empty frame, not an error - so
    # check the count explicitly rather than letting an empty result flow on and
    # fail later with something unrecognisable.
    match = gdf[gdf[args.name_field].astype(str).str.strip() == args.name.strip()]
    if match.empty:
        near = gdf[gdf[args.name_field].astype(str)
                   .str.contains(args.name.split()[0], case=False, na=False)]
        raise SystemExit(
            f"No feature where {args.name_field} == {args.name!r}.\n"
            + ("Did you mean:\n  " + "\n  ".join(sorted(set(near[args.name_field])))
               if not near.empty else "Run --inspect to see what's in the file.")
        )
    print(f"  matched {len(match)} feature(s) on {args.name_field} == {args.name!r}")

    geom = match.geometry.iloc[0]
    for extra in match.geometry.iloc[1:]:
        geom = geom.union(extra)   # multi-row districts are one district

    geom, notes = tidy(geom, args.min_part_km2, args.keep_all_parts)

    boundaries = gpd.read_file(BOUNDARIES)
    if args.boundary_id not in set(boundaries["boundary_id"]):
        raise SystemExit(f"'{args.boundary_id}' isn't in boundaries.geojson. Existing ids:\n  "
                         + "\n  ".join(sorted(boundaries["boundary_id"])))
    idx = boundaries.index[boundaries["boundary_id"] == args.boundary_id][0]

    frame = boundaries.loc[boundaries["boundary_id"] == FRAME_ID, "geometry"].iloc[0]
    eq = gpd.GeoSeries([geom, frame], crs="EPSG:4326").to_crs(EQUAL_AREA)
    full_km2 = eq.iloc[0].area / 1e6
    clipped_eq = make_valid(eq.iloc[0].intersection(eq.iloc[1]))
    clipped_km2 = clipped_eq.area / 1e6

    if clipped_km2 == 0:
        raise SystemExit("The clipped shape is empty - this boundary doesn't overlap "
                         "the Roaring Fork watershed at all. Check the source CRS.")

    old_km2 = float(boundaries.loc[idx, "areasqkm"])
    print()
    print(f"  full extent        {full_km2:>10,.2f} km²")
    print(f"  clipped to basin   {clipped_km2:>10,.2f} km²  ({clipped_km2 / full_km2 * 100:.1f}% inside)")
    print(f"  currently on map   {old_km2:>10,.2f} km²")
    print(f"  change             {clipped_km2 - old_km2:>+10,.2f} km²  "
          f"({(clipped_km2 / old_km2 - 1) * 100:+.1f}%)")

    if args.dry_run:
        print("\n--dry-run: nothing written.")
        return

    clipped = gpd.GeoSeries([clipped_eq], crs=EQUAL_AREA).to_crs("EPSG:4326").iloc[0]

    # Label anchor. representative_point() is guaranteed to fall INSIDE the
    # polygon; a centroid is not, on a concave or multi-part shape. The map
    # renders labels from these precomputed points because MapLibre otherwise
    # places one label per polygon per tile and repeats the name.
    anchor_src = (max(clipped_eq.geoms, key=lambda p: p.area)
                  if clipped_eq.geom_type == "MultiPolygon" else clipped_eq)
    anchor = (gpd.GeoSeries([anchor_src.representative_point()], crs=EQUAL_AREA)
              .to_crs("EPSG:4326").iloc[0])

    caveat = f"{args.caveat} ".strip() + " " + " ".join(notes)
    if clipped_km2 < full_km2 - 0.01:
        caveat += (f" CLIPPED to the Roaring Fork HUC-8 for display - this is NOT the "
                   f"legal boundary; the full district is {full_km2:,.0f} km² and "
                   f"{full_km2 - clipped_km2:,.0f} km² lies outside the watershed.")

    boundaries.loc[idx, "geometry"] = clipped
    boundaries.loc[idx, "areasqkm"] = round(clipped_km2, 2)
    boundaries.loc[idx, "label_lon"] = round(anchor.x, 6)
    boundaries.loc[idx, "label_lat"] = round(anchor.y, 6)
    boundaries.loc[idx, "source"] = args.source
    boundaries.loc[idx, "srcurl"] = args.srcurl
    boundaries.loc[idx, "pulldate"] = args.pulldate or date.today().isoformat()
    boundaries.loc[idx, "caveat"] = " ".join(caveat.split())

    boundaries["pulldate"] = boundaries["pulldate"].astype(str)
    # Serialize fully before opening the file. open(path, 'w') truncates
    # immediately, so a failure inside to_json() would leave an empty file where
    # the project's only copy of every boundary used to be.
    json_text = boundaries.to_json()
    BOUNDARIES.write_text(json_text)
    print(f"\nUpdated '{args.boundary_id}' in {BOUNDARIES.relative_to(REPO)}.")
    print("Reload the map and confirm the shape looks right before committing.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--inspect", metavar="FILE", help="list features and areas, write nothing")
    ap.add_argument("--input", help="file to ingest (.zip, .shp, .kml, .geojson)")
    ap.add_argument("--name-field", help="column holding the district name, e.g. DISTNAME")
    ap.add_argument("--name", help="exact value to match in --name-field")
    ap.add_argument("--boundary-id", help="row in boundaries.geojson to replace")
    ap.add_argument("--source", default="", help="provenance, e.g. 'KML export via <person>'")
    ap.add_argument("--srcurl", default="", help="source URL, blank if received by email")
    ap.add_argument("--pulldate", default="", help="YYYY-MM-DD received (default: today)")
    ap.add_argument("--caveat", default="", help="who provided it, known limitations")
    ap.add_argument("--min-part-km2", type=float, default=1.0,
                    help="drop MultiPolygon parts smaller than this (default 1.0)")
    ap.add_argument("--keep-all-parts", action="store_true", help="keep every part, however small")
    ap.add_argument("--dry-run", action="store_true", help="report only, write nothing")
    args = ap.parse_args()

    try:
        if args.inspect:
            inspect(Path(args.inspect))
        elif all([args.input, args.name_field, args.name, args.boundary_id]):
            ingest(args)
        else:
            ap.error("use --inspect FILE, or all of --input, --name-field, --name, --boundary-id")
    except KeyboardInterrupt:
        sys.exit(1)
