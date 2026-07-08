"""
Clean and standardize an incoming org service-area file (shapefile, KML, KMZ, GeoJSON)
into the project's standard GeoJSON schema.

Usage:
    python clean_org_boundary.py <input_file> <org_name> <org_short> <category> <website> <source_note>

Example:
    python clean_org_boundary.py ../data/raw/swsd_district_boundary.kml \
        "Snowmass Water and Sanitation District" "SWSD" "Water Providers" "swsd.org" \
        "Service area boundary, general perimeter. Provided by Darrell Smith via Google Earth export, June 2026."

Output is written to ../data/clean/<org_short>.geojson
"""

import sys
import geopandas as gpd
from shapely.geometry import Polygon, MultiPolygon


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


def clean_org_boundary(input_path, org_name, org_short, category, website, source_note, output_dir="../data/clean"):
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
        "source_note": [source_note],
        "geometry": [merged_geom]
    }, crs="EPSG:4326")

    # Sanity check: print approximate area in sq km (using Colorado-appropriate projection)
    area_km2 = gdf_clean.to_crs(epsg=26953).geometry.area.iloc[0] / 1e6
    print(f"Org: {org_name}")
    print(f"Valid geometry: {gdf_clean.geometry.is_valid.all()}")
    print(f"Approx area: {area_km2:.1f} sq km")
    print(f"Bounds: {gdf_clean.geometry.bounds.values[0]}")

    output_path = f"{output_dir}/{org_short.lower().replace(' ', '_')}.geojson"
    gdf_clean.to_file(output_path, driver="GeoJSON")
    print(f"\nExported to: {output_path}")
    return gdf_clean


if __name__ == "__main__":
    if len(sys.argv) != 7:
        print(__doc__)
        sys.exit(1)

    clean_org_boundary(
        input_path=sys.argv[1],
        org_name=sys.argv[2],
        org_short=sys.argv[3],
        category=sys.argv[4],
        website=sys.argv[5],
        source_note=sys.argv[6]
    )
