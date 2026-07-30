"""
Clean and standardize an incoming org service-area file (shapefile, KML, KMZ, GeoJSON)
into the project's standard GeoJSON schema.

Usage:
    python clean_org_boundary.py <input_file> <org_name> <org_short> <category> <website> <source> <pulldate> <srcurl> <caveat>

Metadata fields (kept short and structured so they survive Shapefile's 10-char field
name limit and 254-char text limit without truncation - see README "Standard schema"):
    source    - where the file/data came from, e.g. "KML export" or "Colorado DOLA - Water and Sanitation Districts"
    pulldate  - date received/pulled, YYYY-MM-DD
    srcurl    - source URL if applicable, blank string "" if received via email/file
    caveat    - short freeform note: who provided it, known limitations, approximations, confirmations

Example:
    python clean_org_boundary.py ../data/raw/swsd_district_boundary.kml \
        "Snowmass Water and Sanitation District" "SWSD" "Water Providers" "swsd.org" \
        "KML export via Google Earth" "2026-06-24" "" \
        "Provided by Darrell Smith. Service area boundary, general perimeter."

Output is written to ../data/clean/<org_short>.geojson
"""

import sys
import geopandas as gpd
from shapely.geometry import Polygon, MultiPolygon, LineString, MultiLineString


def close_lines_to_polygons(geom):
    """Some GIS exports (e.g. Google Earth/KML) save a boundary as a closed line
    rather than a filled polygon. If we get a LineString/MultiLineString whose
    ring(s) are closed (first point == last point), convert to Polygon(s)."""
    if isinstance(geom, LineString):
        coords = list(geom.coords)
        if len(coords) >= 4 and coords[0] == coords[-1]:
            return Polygon(coords)
        raise ValueError("Got an open LineString - can't convert to a boundary polygon")
    elif isinstance(geom, MultiLineString):
        polys = []
        for line in geom.geoms:
            coords = list(line.coords)
            if len(coords) >= 4 and coords[0] == coords[-1]:
                polys.append(Polygon(coords))
            else:
                raise ValueError("Got an open line within a MultiLineString - can't convert")
        return polys[0] if len(polys) == 1 else MultiPolygon(polys)
    return geom


def drop_z(geom):
    """Strip elevation (Z) values - not needed for 2D service area polygons."""
    if geom.geom_type == "Polygon":
        return Polygon([(x, y) for x, y, *_ in geom.exterior.coords])
    elif geom.geom_type == "MultiPolygon":
        return MultiPolygon([
            Polygon([(x, y) for x, y, *_ in poly.exterior.coords])
            for poly in geom.geoms
        ])
    return geom


def clean_org_boundary(input_path, org_name, org_short, category, website, source, pulldate, srcurl, caveat, output_dir="../data/clean"):
    # Auto-detect driver for KML/KMZ
    driver = "KML" if input_path.lower().endswith((".kml", ".kmz")) else None

    gdf = gpd.read_file(input_path, driver=driver) if driver else gpd.read_file(input_path)

    if gdf.empty:
        raise ValueError(f"No features found in {input_path}")

    # Reproject to WGS84 if needed
    if gdf.crs is None:
        print("WARNING: No CRS found, assuming EPSG:4326")
        gdf = gdf.set_crs("EPSG:4326")
    elif gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs("EPSG:4326")

    # Convert closed boundary lines to polygons (some KML exports do this)
    line_types = {"LineString", "MultiLineString"}
    if gdf.geometry.geom_type.isin(line_types).any():
        print("NOTE: input has line geometry (closed boundary ring) - converting to polygon")
        gdf["geometry"] = gdf["geometry"].apply(close_lines_to_polygons)

    # Drop Z dimension
    gdf["geometry"] = gdf["geometry"].apply(drop_z)

    # Dissolve multiple features into one if needed (some orgs may send multi-part boundaries)
    if len(gdf) > 1:
        print(f"NOTE: {len(gdf)} features found, dissolving into a single boundary")
        merged_geom = gdf.geometry.union_all()
    else:
        merged_geom = gdf.geometry.iloc[0]

    # Validate and fix geometry if needed
    if not merged_geom.is_valid:
        print("WARNING: Invalid geometry detected, attempting fix with buffer(0)")
        merged_geom = merged_geom.buffer(0)

    gdf_clean = gpd.GeoDataFrame({
        "org_name": [org_name],
        "org_short": [org_short],
        "category": [category],
        "website": [website],
        "source": [source],
        "pulldate": [pulldate],
        "srcurl": [srcurl],
        "caveat": [caveat],
        "geometry": [merged_geom]
    }, crs="EPSG:4326")

    # Sanity check: print approximate area in sq km (using Colorado-appropriate projection)
    area_km2 = gdf_clean.to_crs(epsg=26953).geometry.area.iloc[0] / 1e6
    print(f"Org: {org_name}")
    print(f"Valid geometry: {gdf_clean.geometry.is_valid.all()}")
    print(f"Approx area: {area_km2:.1f} sq km")
    print(f"Bounds: {gdf_clean.geometry.bounds.values[0]}")

    # Use plain file write, not gdf.to_file() - GDAL's overwrite (delete-then-recreate)
    # fails with "Operation not permitted" on this project's mounted folder.
    output_path = f"{output_dir}/{org_short.lower().replace(' ', '_')}.geojson"
    with open(output_path, "w") as f:
        f.write(gdf_clean.to_json())
    print(f"\nExported to: {output_path}")
    return gdf_clean


if __name__ == "__main__":
    if len(sys.argv) != 10:
        print(__doc__)
        sys.exit(1)

    clean_org_boundary(
        input_path=sys.argv[1],
        org_name=sys.argv[2],
        org_short=sys.argv[3],
        category=sys.argv[4],
        website=sys.argv[5],
        source=sys.argv[6],
        pulldate=sys.argv[7],
        srcurl=sys.argv[8],
        caveat=sys.argv[9]
    )
