# PCHR Watershed Directory Map – Project Structure

## Folder layout

```
pchr_watershed_map/
├── data/
│   ├── raw/         # Original files exactly as received (shapefiles, KML, KMZ, etc.)
│   ├── clean/        # Standardized GeoJSON, one file per org, output of clean_org_boundary.py
│   └── reference/    # Watershed boundary, rivers/creeks, roads, municipal boundaries (HUC-8, NHD, etc.)
├── scripts/          # Reusable Python scripts for the data pipeline
└── build/            # Tippecanoe/PMTiles output - the final tile archive for the map
```

## Workflow for each incoming org file

1. **Save the raw file exactly as received** into `data/raw/`. Keep the original filename or
   rename clearly (e.g. `swsd_district_boundary.kml`). Never edit raw files directly.

2. **Run the cleaning script** to standardize it:

   ```bash
   cd scripts
   python clean_org_boundary.py <input_file> "<Org Name>" "<ORG_SHORT>" "<Category>" "<website>" "<source note>"
   ```

   Example:
   ```bash
   python clean_org_boundary.py ../data/raw/swsd_district_boundary.kml \
     "Snowmass Water and Sanitation District" "SWSD" "Water Providers" "swsd.org" \
     "Service area boundary, general perimeter. Provided by Darrell Smith via Google Earth export, June 2026."
   ```

3. **Check the script output** - it prints validity, approximate area, and bounds as a sanity
   check. If the area or bounds look wrong for that org, stop and investigate before moving on.

4. **Clean file lands in `data/clean/`** as `<org_short>.geojson`, ready for the next pipeline step
   (DuckDB → GeoParquet → Tippecanoe → PMTiles).

## Standard schema

Every cleaned org file has the same five properties, so they merge cleanly later:

| Field         | Description                                              |
|---------------|------------------------------------------------------------|
| `org_name`    | Full organization name                                     |
| `org_short`   | Short code/abbreviation (used in filenames)                |
| `category`    | One of: Conservation & Advocacy, Governance & Policy, Water Providers, Infrastructure & Planning |
| `website`     | Org's website, no protocol (e.g. `swsd.org`)                |
| `source_note` | Who provided the file, how, and when - keeps provenance clear |

## Org tracker

| Org | Status | File received | Cleaned |
|---|---|---|---|
| Snowmass Water and Sanitation District | Done | KML via Darrell Smith, 6/24/26 | ✓ |
| Roaring Fork Conservancy | Pending | | |
| RWAPA | Pending - likely whole watershed | | |
| Pitkin County Healthy Rivers | Resolved - HUC-8 boundary, no separate file needed | | |
| CVEPA | Pending | | |
| Division of Water Resources (DWR) | Pending - no map exists, will hand-draw at El Jebel per Heather | | |
| Colorado Basin Roundtable | Pending - likely no polygon, point/label only | | |
| Colorado Water Conservation Board | Pending - likely no polygon, point/label only | | |
| Colorado River District | Pending - likely no polygon, point/label only | | |
| Basalt Water Conservancy District | Pending - web contact out until Monday | | |
| West Divide Water Conservancy District | Pending | | |
| Roaring Fork Water and Sanitation District | Pending | | |
| Town of Carbondale | Pending - may pull from county GIS directly | | |
| City of Aspen | Pending - may pull from county GIS directly | | |
| City of Glenwood Springs | Pending - may pull from county GIS directly | | |

## Reference layers (not org-specific)

The map needs to work at three scales:

1. **Local** - zoomed into the Roaring Fork/Pitkin County area, where most orgs sit.
2. **Basin (CO)** - zoomed out to Colorado's portion of the Colorado River
   watershed, for statewide orgs (Colorado River District, CWCB, Basin
   Roundtable). This is the CO's West Slope HUC-8 set, clipped to the state
   line - matches where these orgs actually operate.
3. **Basin (context)** - a light outline-only layer for when someone zooms all
   the way out, showing the full Upper Colorado Region (HUC-2 #14: CO, UT, WY,
   NM down to Lake Powell/Glen Canyon Dam). No org data lives out here - it's
   just geographic context so the CO orgs read as "part of a bigger river
   system." Stops at Lake Powell; not extending into the Lower Basin (AZ/NV/CA).

To be pulled into `data/reference/`:
- Local scale: HUC-8 watershed boundary (14010004 - Roaring Fork) from USGS WBD
- Basin (CO) scale: HUC-8 subwatersheds making up Colorado's West Slope/Colorado
  River Basin in CO (headwaters, Eagle, Blue, Gunnison, Roaring Fork, etc.),
  clipped to the CO state line - from USGS WBD
- Basin (context) scale: Upper Colorado Region boundary (HUC-2 #14) from USGS
  WBD, outline only, low opacity, no interactivity
- Rivers/creeks from NHD
- Roads, municipal/county boundaries from Pitkin County GIS (pending confirmation)
- Hillshade/DEM (optional, for basemap)
