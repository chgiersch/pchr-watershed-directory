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
   python clean_org_boundary.py <input_file> "<Org Name>" "<ORG_SHORT>" "<Category>" "<website>" "<source>" "<pulldate>" "<srcurl>" "<caveat>"
   ```

   Example:
   ```bash
   python clean_org_boundary.py ../data/raw/swsd_district_boundary.kml \
     "Snowmass Water and Sanitation District" "SWSD" "Water Providers" "swsd.org" \
     "KML export via Google Earth" "2026-06-24" "" \
     "Provided by Darrell Smith. Service area boundary, general perimeter."
   ```

3. **Check the script output** - it prints validity, approximate area, and bounds as a sanity
   check. If the area or bounds look wrong for that org, stop and investigate before moving on.

4. **Clean file lands in `data/clean/`** as `<org_short>.geojson`, ready for the next pipeline step
   (DuckDB → GeoParquet → Tippecanoe → PMTiles).

## Standard schema

Every cleaned org file has the same eight properties, so they merge cleanly later:

| Field       | Description                                              |
|-------------|------------------------------------------------------------|
| `org_name`  | Full organization name                                     |
| `org_short` | Short code/abbreviation (used in filenames)                |
| `category`  | One of: Conservation & Advocacy, Governance & Policy, Water Providers, Infrastructure & Planning |
| `website`   | Org's website, no protocol (e.g. `swsd.org`)                |
| `source`    | Where the geometry came from, e.g. "KML export" or "Colorado DOLA - Water and Sanitation Districts" |
| `pulldate`  | Date the file was received/pulled, `YYYY-MM-DD`             |
| `srcurl`    | Source URL if applicable, blank string if received via email/file |
| `caveat`    | Short freeform note: who provided it, confirmations, known limitations or approximations |

**Metadata note (as of 7/28/26):** this replaces the original single `source_note` free-text
field. Field names are all ≤10 characters and values are kept short and structured on purpose -
Shapefile's `.dbf` format truncates field names past 10 characters and text values past 254
characters, and the old long-paragraph `source_note` got silently cut off mid-sentence in a real
export (WDWCD's shapefile lost its last sentence). GeoJSON has no such limit and remains the
canonical, full-fidelity format; Shapefile exports exist only so ArcGIS Pro can browse the data
(see "Why GeoJSON doesn't always show up in ArcGIS" below) and should not be treated as an
archival copy for anything text-heavy.

**Coverage (as of 7/28/26):** all 8 standalone org files, `boundaries.geojson`, `orgs.json`,
and `orgs_proof_of_concept.geojson` use this schema. The `data/reference/` backdrop layers
(HUC-8/HUC-10/basin/caucuses/PLSS grid) were migrated to the same `source`/`pulldate`/`srcurl`/
`caveat` fields in this same pass, on top of whatever feature-specific fields each already had
(e.g. `huc8`, `areasqkm`, `caucus_name`). `wdwcd_pitkin_official.geojson` is now marked
superseded in its own `caveat` field - see the Reference layers section below.

## Boundaries vs. orgs (normalized structure)

Several orgs share the exact same boundary (e.g. RFC/RWAPA/PCHR all use the Roaring
Fork HUC-8; CBRT/CWCB/CRD all use the CO West Slope basin). Storing the same
polygon once per org causes stacked fills to render at compounded opacity on the
map, and risks the shapes drifting out of sync if one copy gets edited later.

So as of the proof-of-concept pass, geometry and org attributes are split into two files:

- `data/clean/boundaries.geojson` (+ `.shp`) - one row per **unique** shape, keyed by
  `boundary_id`, carrying the geometry's own `source`/`pulldate`/`srcurl`/`caveat`.
- `data/clean/orgs.json` - one row per **org** (name, category, website, `boundary_id`,
  `category_confirmed`, and an org-specific `caveat`), no geometry of its own.

Rendering should draw each unique boundary once, then join to `orgs.json` on
`boundary_id` at click-time to show all org(s) tied to that shape in the popup - and to
show that boundary's own provenance fields alongside the org's caveat.
`data/clean/orgs_proof_of_concept.geojson`/`.shp` (the flattened, one-row-per-org
version with duplicated geometry) still exists for a quick visual scan in ArcGIS,
but `boundaries.geojson` + `orgs.json` is the source of truth going forward.

## Why GeoJSON doesn't always show up in ArcGIS

ArcGIS Pro's Catalog pane doesn't treat `.geojson` as a fully native, always-recognized
format the way it does Shapefile or File Geodatabase - GeoJSON read support was added
later and is still inconsistent, especially over a network share (e.g. a Parallels VM
shared folder), where Catalog sometimes shows the file as a generic non-spatial icon
even though it's perfectly valid. The fix isn't to change the GeoJSON - it's to also
export a `.shp` copy for ArcGIS review, and keep GeoJSON as the real source of truth
for the web map.

## Org tracker

| Org | Status | File received | Cleaned |
|---|---|---|---|
| Snowmass Water and Sanitation District | Done | KML via Darrell Smith, 6/24/26 | ✓ |
| Roaring Fork Conservancy | Resolved - Roaring Fork Watershed, no separate file needed | | |
| RWAPA | Resolved - confirmed whole Roaring Fork Watershed by Gwen, 7/2/26; no separate file needed | | |
| Pitkin County Healthy Rivers | Resolved - HUC-8 boundary is the "official" HR boundary per Tim Braun (county), 6/15/26; no separate file needed | | |
| CVEPA | Resolved - confirmed by CVEPA via Gwen, 7/28/26: service area is only the Crystal River Watershed, matches HUC-10 1401000407 "Crystal River" (938 km²). Using that boundary directly; no separate org shapefile needed. | | |
| Division of Water Resources (DWR) | Pending - no map exists, will hand-draw. Dividing line is near Emma, not El Jebel as first thought (per Heather Ramsey via Gwen, 7/2/26): Bill covers Emma-up/Aspen-Basalt side, Heather covers Emma-down/Carbondale-El Jebel side | | |
| Colorado Basin Roundtable | Pending - likely no polygon, point/label only | | |
| Colorado Water Conservation Board | Pending - likely no polygon, point/label only | | |
| Colorado River District | Pending - likely no polygon, point/label only | | |
| Basalt Water Conservancy District | Done | KML from Eric Mangeot (Sphero Environmental), 7/9/26. Exported as a closed boundary line rather than a polygon - clean_org_boundary.py now auto-converts closed lines to polygons. | ✓ |
| West Divide Water Conservancy District | Done - real, FULL official district boundary pulled from Colorado DOLA's statewide "All Active Districts" dataset (services3.arcgis.com, 7/28/26), ~2,009 sq km, De Beque/Rifle/Silt through Glenwood Springs/Carbondale to Capitol Peak/Marble. Supersedes both the Pitkin-County-only sliver and the RF-HUC8-minus-Crystal-HUC10 approximation - this is authoritative statewide data, not a guess. | | ✓ |
| Roaring Fork Water and Sanitation District | Done - real official boundary pulled from Colorado DOLA's "Water and Sanitation Districts" dataset (7/28/26), ~7.3 sq km, matches the 2007 CAD map's Iron Bridge/Aspen Glen/Teller Springs/Cottrell Ranch clusters along CR 109. | RFWSDmap.pdf | ✓ |
| Mid-Valley Metropolitan District | Done - real official boundary pulled from Colorado DOLA's "All Active Districts" dataset (7/28/26), ~8.6 sq km, matches the PLSS-referenced SGM map (LGID-64211, El Jebel/Emma area). | mvmd_map.pdf | ✓ |
| Town of Carbondale | Done - real official municipal boundary from Colorado DOLA's "Municipal Boundaries" dataset (7/28/26), ~5.2 sq km. Water supply is the Crystal River, with substantial water rights on it (per Gwen, 7/28/26) - noted in the popup description. | | ✓ |
| City of Aspen | Done - real official municipal boundary from Colorado DOLA's "Municipal Boundaries" dataset (7/28/26), ~10.0 sq km. Water comes from Maroon and Castle Creeks, with new storage ideas at Woody Creek to replace the reservoirs given up on Maroon/Castle Creeks (per Gwen, 7/28/26) - noted in the popup description. | | ✓ |
| City of Glenwood Springs | Done - real official municipal boundary from Colorado DOLA's "Municipal Boundaries" dataset (7/28/26), ~15.4 sq km. Water supply is Grizzly and No Name creeks plus some Roaring Fork water rights (per Gwen, 7/28/26) - noted in the popup description. | | ✓ |
| Town of Basalt | Done - real official municipal boundary from Colorado DOLA's "Municipal Boundaries" dataset (7/28/26), ~5.3 sq km. One of the original 3 PDF-only orgs (alongside RFWSD/Mid-Valley Metro) - resolved the same way instead of manually georeferencing the PDF. Straddles Eagle/Pitkin/Garfield county lines. | | ✓ |
| Snowmass Capitol Creek Caucus | Real boundary pulled directly from Pitkin County GIS (`data/reference/caucuses.geojson`/`data/clean/caucuses_v2.shp`, 7/28/26) - no shapefile request needed. Scope question below: is this one of 13 Pitkin caucuses to include, or all 13? | | |
| Crystal River Caucus | Real boundary pulled directly from Pitkin County GIS, same file as above - no shapefile request needed. Same scope question as Snowmass Capitol Creek Caucus. | | |
| Other 11 Pitkin caucuses (Emma, Fryingpan Valley, Woody Creek, Tennis Club, Smuggler, Castle Creek, East of Aspen, Maroon Creek, Owl Creek, Upper Snowmass Creek, Brush Creek) | Real boundaries already pulled (same file), not yet decided whether they belong on a water-org-specific map since most aren't water-themed. Pending scope call with Gwen. | | |

## Gwen's August to-do list (as of 7/28/26)

Down to one real data gap and one scope question. Pulling directly from Colorado's statewide DOLA GIS service (services3.arcgis.com, the state's authoritative special-district/municipal tracking system - separate from Pitkin County's own GIS server used earlier) resolved West Divide, RFWSD, Mid-Valley Metro, and all four municipalities (Carbondale, Aspen, Glenwood Springs, Basalt) in one pass, so none of those need shapefile requests anymore.

- **Only real data gap left:** Division of Water Resources (DWR) - no map exists anywhere; the Bill/Heather Emma-line split still needs to be hand-drawn. Not something a GIS pull can solve.
- **Scope decision, not data-gathering:** how many of the 13 officially recognized Pitkin caucuses belong on this map - just the 2 water-named ones (Snowmass/Capitol, Crystal River), or all 13? Boundary data is already in hand for all of them either way.
- **Worth a sanity check with the district, not urgent:** West Divide's DOLA-sourced boundary is the full official district (~2,009 sq km) - worth a quick "does this look right to you?" the next time Gwen's in touch with them, since state-maintained special-district data is known to sometimes trace back to old scanned drawings.
- **No longer needed:** shapefiles/KML/PDFs from RFWSD, Mid-Valley Metro, Town of Basalt, West Divide, or the other three municipalities, and CVEPA/Snowmass Capitol Creek Caucus/Crystal River Caucus boundary confirmations (all resolved with real data, 7/28/26). This closes out all three of the original PDF-only orgs (RFWSD, Mid-Valley Metro, Basalt) - none needed manual PDF georeferencing after all.

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

**Status (as of 7/28/26):** `huc8_roaring_fork.geojson`, `co_west_slope_basin.geojson` (+ its
dissolved single-polygon version), `upper_colorado_region.geojson`, and `huc10_crystal_river.geojson`
are pulled and now carry the full `source`/`pulldate`/`srcurl`/`caveat` schema.
`caucuses.geojson` (all 13 official Pitkin caucuses) is also pulled and migrated - scope decision
(2 vs. 13 on the map) still pending with Gwen. `plss_grid_mvmd.geojson` (BLM PLSS section grid)
is migrated too, but is an orphaned georeferencing aid - MVMD's real boundary came from DOLA
instead, so this file isn't used in the final map. `wdwcd_pitkin_official.geojson` (the old
Pitkin-County-only sliver) is migrated and explicitly marked `SUPERSEDED` in its `caveat` field -
kept for reference/comparison only, not used in the final map since `data/clean/wdwcd.geojson`
now has the real full district boundary.
