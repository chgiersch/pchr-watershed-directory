# PCHR Watershed Directory Map

An interactive map and text directory of the organizations that manage water in the Roaring Fork
watershed, built for Pitkin County Healthy Rivers.

## Live site

**https://chgiersch.github.io/pchr-watershed-directory/**

Published by GitHub Pages from the **`main`** branch, root folder. Every merge into `main` triggers
a rebuild - watch it under the repo's Actions tab.

`main` is deliberately not where work happens. It only ever receives merges from `release/*` or
`hotfix/*` branches, so whatever is live corresponds to a tagged version you can roll back to. Day
to day work lands on `dev`. See CONTRIBUTING notes in `.github/PULL_REQUEST_TEMPLATE.md`.

Two pages are served:

| Path | What it is |
|---|---|
| `/` (`index.html`) | The map alone. This is what gets embedded in an iframe. |
| `/directory.html` | The prototype host page - map plus directory, showing how the two link together. |

The directory is destined for the county's WordPress site, not for Pages. `directory.html` exists
so the linkage can be developed and reviewed before that handoff.

## Getting started

The map itself needs no build step - `index.html` is a static file that loads its data at runtime.
You only need Python for the data pipeline in `scripts/`.

```bash
git clone git@github.com:chgiersch/pchr-watershed-directory.git
cd pchr-watershed-directory

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

The clone pulls about 58 MB, most of it the PMTiles basemap archives, so it isn't instant.

`geopandas` is the slow install - it binds to GDAL, GEOS and PROJ, and pip has to fetch those
wheels. If it fails to build, install those libraries first (`brew install gdal geos proj` on
macOS) and retry.

### Running it locally

```bash
python3 scripts/serve.py
```

Then open **http://localhost:8000/directory.html**.

Use that script, not a generic server. It does two things a plain server doesn't, and both have
cost real debugging time here:

**Range requests.** The basemap is a PMTiles archive read by HTTP byte-range requests, and
`python3 -m http.server` ignores `Range` headers - see the local testing note further down for
what that failure looks like.

**No caching.** Without a `Cache-Control` header Chrome caches served files, and in particular
keeps running a STALE `index.html` inside the directory page's iframe even after a hard reload of
the parent page. The symptom is maddening: the directory shows new code, the map runs old code,
and the postMessage link between them silently dies (8/27/26). The script sends `no-store`, so
what's in the browser is always what's on disk.

**Port 8000 specifically.** `index.html` validates the origin of every `postMessage` against a
fixed allowlist, and only `localhost:8000` and `127.0.0.1:8000` are on it. On any other port the
page loads and looks correct, but the map and directory silently stop talking to each other.

Open `directory.html`, not `index.html`. On its own `index.html` is just the map; the two-way link
only exists when the map is embedded in the host page.

### Testing the cross-origin path

In production the directory lives on the county's WordPress and the map is an iframe from GitHub
Pages - two different origins, with the origin checks on both sides doing real work. Served
locally, both files come from the same origin and `directory-map-link.js` detects that, so none of
that code actually runs.

`localhost` and `127.0.0.1` are distinct origins to a browser despite being the same server, and
both are already allowlisted - so the real path can be exercised without touching `index.html`:

1. Point the iframe at the other hostname: in `directory.html`, `src="index.html"` becomes
   `src="http://localhost:8000/index.html"`
2. In `directory-map-link.js`, set `MAP_ORIGIN` to `'http://localhost:8000'`
3. Load the page at **http://127.0.0.1:8000/directory.html** - note the different hostname; using
   `localhost` for both puts you back to same-origin and tests nothing
4. Confirm both directions work: an org in a map popup scrolls the directory, and "Show on map"
   moves the map

Then the negative case, which is the half that actually proves the check is enforced. Set
`MAP_ORIGIN` to `'http://localhost:9999'` and reload. Both directions should stop working. Only
one of them reports anything: `postMessage` throws a visible console error going out, while
incoming messages are dropped by a silent guard clause. To see that rejection rather than infer
it, add a listener of your own before clicking:

```js
window.addEventListener('message', e => console.log('RX from', e.origin, e.data));
```

The message still arrives - it is the app's own origin check that discards it.

Revert when finished. `directory.html` is generated, so rebuild rather than hand-editing it back:

```bash
python3 scripts/build_directory.py
git checkout directory-map-link.js
git status --short        # must be empty
```

Do not commit a hardcoded `localhost` in either file.

## Folder layout

```
pchr-watershed-directory/
├── index.html                          # the map - MapLibre GL JS, single file
├── directory.html                      # GENERATED - do not hand-edit
├── directory.css                       # directory styling, kept separate to port into WordPress
├── directory-map-link.js               # host side of the map/directory postMessage link
├── requirements.txt                    # Python deps for scripts/ only
├── data/
│   ├── raw/                            # originals exactly as received, never edited
│   ├── clean/
│   │   ├── boundaries.geojson          # every service-area shape, one row each
│   │   └── orgs.json                   # every org, pointing at a boundary_id
│   ├── reference/                      # map context that isn't an org boundary
│   │   ├── nhd_rivers.geojson
│   │   └── caucuses.geojson
│   └── basemap/                        # self-hosted PMTiles archives
├── scripts/                            # data pipeline
│   ├── build_directory.py              # orgs.json  ->  directory.html
│   ├── fetch_dola_district.py          # pull an official boundary from Colorado DOLA
│   ├── clean_org_boundary.py           # validity repair, hole removal, clipping
│   └── build_dwr_areas.py              # NOT currently used by the map
└── .github/
    └── PULL_REQUEST_TEMPLATE.md
```

**`directory.html` is generated.** `scripts/build_directory.py` writes it from `orgs.json`. Edit
the script or the data, never the HTML - a hand edit is silently destroyed by the next build.

After the county takes the directory into WordPress, they own that content and `orgs.json` will go
stale relative to what's published. Re-running the generator at that point would overwrite their
edits. Don't, without asking them first.

**One shape, one place.** Every polygon the map draws lives exactly once, as a row in
`data/clean/boundaries.geojson`. There are no per-org files, no duplicate copies in
`data/reference/`, and no flattened export with the geometry repeated per org.

This wasn't always true, and the drift caused real bugs: the Roaring Fork HUC-8 and the CO West
Slope basin each existed both as a `boundaries.geojson` row *and* as a standalone reference file,
and both copies were being drawn — producing overlapping outlines that read as scattered dotted
fragments across the map. Consolidated 7/30/26.

`data/reference/` now holds only shapes that are *not* any org's service area: the HUC-2 context
outline, the rivers layer, and the caucus boundaries (pending a scope decision — see Gwen's list).

Shapefiles are gitignored. They're a derived format, and keeping a committed `.shp` beside every
`.geojson` is the same drift problem in a different costume. Export locally if a desktop tool
needs to read the data.

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

## Data model: boundaries + orgs

Several orgs share the exact same service area — RFC/RWAPA/PCHR all use the Roaring Fork HUC-8;
CBRT/CWCB/CRD all use the CO West Slope basin. So geometry and org attributes are separate:

**`data/clean/boundaries.geojson`** — one row per unique shape:

| Field | Description |
|---|---|
| `boundary_id` | Stable key orgs point at, e.g. `wdwcd_boundary`, `huc8_roaring_fork` |
| `name` | Human-readable name of the shape |
| `areasqkm` | Area in km², computed in EPSG:5070 (Conus Albers) |
| `huc_code` | HUC-8/HUC-10 code for watershed shapes, empty string otherwise |
| `source` | Where the geometry came from, e.g. "Colorado DOLA - Municipal Boundaries" |
| `pulldate` | When it was received/pulled, `YYYY-MM-DD` |
| `srcurl` | Source URL, empty string if received by email/file |
| `caveat` | Provenance and known limitations, including any cleaning applied |

**`data/clean/orgs.json`** — one row per org: `org_name`, `org_short`, `category`, `website`,
`boundary_id`, `category_confirmed`, and an org-specific `caveat`. No geometry.

`index.html` draws each boundary once from `boundaries.geojson`, then joins to `orgs.json` on
`boundary_id` at click-time so the popup can list every org tied to that shape. `name`/`areasqkm`/
`huc_code` live on the boundary row itself, which is why no separate reference file needs loading
to render the watershed/basin context blocks.

**Categories:** Conservation & Advocacy, Governance & Policy, Water Providers,
Infrastructure & Planning.

**Why field names stay ≤10 characters and values stay short:** a holdover from when Shapefile
exports were committed (`.dbf` truncates field names past 10 chars and text past 254). The
constraint is no longer binding since GeoJSON is the only committed format, but the schema is
kept as-is because it's already consistent across every file and nothing is gained by churning it.

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
| Snowmass Capitol Creek Caucus | Real boundary pulled directly from Pitkin County GIS (`data/reference/caucuses.geojson`, 7/28/26) - no shapefile request needed. Scope question below: is this one of 13 Pitkin caucuses to include, or all 13? | | |
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
- Rivers/creeks from NHD - **done, see below**

**Status (as of 7/30/26):** the Roaring Fork HUC-8, Crystal River HUC-10, and CO West Slope basin
are all rows in `data/clean/boundaries.geojson` — they're real assigned service areas
(RFC/RWAPA/PCHR, CVEPA, and CBRT/CWCB/CRD respectively), not backdrop, so they belong with the
other boundaries rather than in `reference/`.

`data/reference/` now holds only the two shapes that aren't anyone's service area:
`nhd_rivers.geojson` and `caucuses.geojson` (all 13 official Pitkin caucuses — scope decision,
2 vs. 13, still pending with Gwen).

`upper_colorado_region.geojson` (HUC-2 context outline) went too, in the 7/30/26 clip: once
everything was cut to the Roaring Fork HUC-8 and the zoom floor was set to that extent, a
region-scale outline could never come into view.

Removed in the 7/30/26 consolidation: the undissolved 30-feature `co_west_slope_basin.geojson`
(superseded by the dissolved version, which then moved into `boundaries.geojson`),
`wdwcd_pitkin_official.geojson` (the old Pitkin-County-only sliver, already marked SUPERSEDED —
`boundaries.geojson` carries the real full district), `plss_grid_mvmd.geojson` (orphaned
georeferencing aid; MVMD's real boundary came from DOLA), the nine standalone per-org GeoJSON
files, and `orgs_proof_of_concept.geojson` (a flattened copy with geometry duplicated per org).

**Duplicate-layer fix (7/30/26) - the actual cause of the "fragments":** `co_west_slope_basin` and
`huc8_roaring_fork` were each being drawn **twice**. Both shapes exist as rows in
`boundaries.geojson` (they're the real assigned org boundary for CBRT/CWCB/CRD and RFC/RWAPA/PCHR
respectively), so `org-fill`/`org-outline` drew them - but they *also* had their own dedicated
"context" layers left over from before those org assignments existed: `basin-fill`/`basin-outline`
and `huc8-fill`/`huc8-outline`. The same polygon rendered on top of itself as a dashed backdrop plus
a solid, `line-offset`-nudged org outline, so every shared edge showed as two slightly-separated
lines - reading as scattered dotted/fragmented shapes, especially where the two boundaries run
close together. Fixed by deleting the four redundant layers entirely; `org-fill`/`org-outline` now
draw all 12 boundaries exactly once each, no filters or exclusions. The `name`/`areasqkm`/`huc_code`
metadata that the popup's "Watershed"/"Basin" block needs was folded into `boundaries.geojson`, so
the standalone reference files could be deleted rather than kept around just for their attributes.
Clicking either shape still surfaces its orgs, via the normal `org-fill` path like everything else.

Worth recording, since this took several passes to find: two *other* real bugs were fixed along the
way and neither was the cause of what was being reported. (1) The `org-fill-hover` layer removal
(above) was genuine dead code but not the fragment source. (2) Interior holes in the geometry (see
below) were real and worth fixing, but also not the fragment source - a fix for them was committed,
then reverted after the artifacts persisted, then re-applied once the duplicate-layer cause was
actually identified. Lesson: when a visual artifact traces a boundary's *edges*, suspect duplicate
or offset rendering of the same geometry before suspecting the geometry itself.

**Interior-holes fix (7/29/26, completed 7/30/26):** separately from the above, several polygons
carried tiny interior holes that showed as small notches cut out of the fill. The CO West Slope
basin had 422 of them (up to ~1.7 km², most far smaller) from an imperfect `unary_union` dissolve
of the 30 HUC-8 subbasins - adjacent subwatersheds didn't seal perfectly along shared edges, most
visible near Kremmling. Six DOLA-sourced municipal/district boundaries had the same issue from
their own source geometry: `wdwcd_boundary` (36 holes), `basalt_boundary` (19), `aspen_boundary`
(11), `gws_boundary` (8), `mvmd_boundary` (6), `carbondale_boundary` (5) - 85 total. All fixed by
keeping only each polygon's exterior ring (`Polygon(geom.exterior)`, applied per-part for
`MultiPolygon` rows) and dropping interior rings, since neither a watershed nor a municipal
district has legitimate internal exclaves. All 12 rows in `boundaries.geojson` verify as
`holes: 0, valid: True`.

**Rivers (added 7/29/26):** `data/reference/nhd_rivers.geojson` - 12 named main-stem rivers and
tributaries (Roaring Fork, Crystal, Fryingpan, Colorado rivers plus
Snowmass/Capitol/Castle/Maroon/Woody/Brush/Cattle/West Divide creeks - the set tied to this
project's orgs/caucuses), pulled from USGS NHD's small-scale flowline layer (already pre-generalized
for exactly this kind of overview map, unlike the large-scale/high-resolution layer which is full of
tiny unnamed segments). Geometry further simplified server-side (`maxAllowableOffset=300` meters).
This is a deliberately curated subset, not the full named-stream network for the area (that's ~250
names in just this bbox, many outside the actual watershed). **One feature per river** (12 total,
20KB) - NHD initially returns each river as dozens of separate short reach segments (Roaring Fork
alone was 49), which rendered as fragmented-looking dashes with a repeated label on every segment;
merged via `shapely.ops.linemerge` into one continuous line per river before saving.
Rendered with sky-blue lines + italic labels, layered above the basemap's roads/labels (rivers
should read clearly even where they cross a road) and above the org fill/outline.

## Basemap

`index.html` renders the basemap from a self-hosted [Protomaps](https://protomaps.com) PMTiles
archive at `data/basemap/roaring-fork.pmtiles`, instead of hotlinking OpenStreetMap's raster tile
server directly. Reasons: OSM's own tile usage policy asks production sites not to do that (they
block heavy use without warning), and PMTiles is a single static file that serves for free from
GitHub Pages alongside the rest of this repo - no tile server, no API key, no third-party account.
The underlying data is still OpenStreetMap (ODbL - attribution required, already wired into the
source's `attribution` field), Protomaps just repackages it into this format.

**Generated 7/28/26** with:

```
brew install pmtiles

# Find today's build filename at https://maps.protomaps.com/builds/, then:
pmtiles extract https://build.protomaps.com/YYYYMMDD.pmtiles data/basemap/roaring-fork.pmtiles \
  --bbox=-108.6,38.6,-106.0,40.0 --maxzoom=15
```

The bbox covers West Divide's full district, the whole Roaring Fork valley, and Basalt, with a
buffer for panning - deliberately tighter than the CO West Slope basin reference layer, since that
one is just a low-opacity backdrop and doesn't need street-level tile detail. `--maxzoom=15` (the
basemap's own max) gives full street/building detail in Aspen/Basalt/Carbondale/Glenwood Springs;
the resulting file is ~88.5MB, under GitHub's 100MB per-file limit but past their 50MB warning
threshold (harmless - the push still succeeds). Drop to `--maxzoom=14` or `13` if a future re-pull
creeps over 100MB.

If this file doesn't exist yet, the map still renders fine - just with no basemap detail (blank
background) - since org boundaries and reference layers load from this repo's own GeoJSON,
independent of the basemap.

### Initial view

The map opens framed on the Roaring Fork HUC-8 watershed bounds (`bounds` option in the
MapLibre constructor, computed from that boundary's extent in `data/clean/boundaries.geojson`) rather
than a fixed center/zoom - this is a watershed map first, org directory second, so it should open
already showing the watershed.

### Org fill/outline styling

`org-fill` is intentionally low-opacity (0.15) and inserted *before* the basemap's roads/labels in
the layer stack, so street detail and place names stay legible through the tint instead of getting
washed out underneath it. `org-outline` stays on top of everything (thin lines don't obscure much).
Where two boundaries share an edge (e.g. WDWCD's district line running along a municipal line), a
`line-offset` on the outline nudges coincident lines apart so both colors show as parallel strips
instead of one flatly covering the other - this isn't foolproof (offset direction depends on each
source file's own vertex winding order, which we don't control), so some pairs may still overlap
imperfectly. A more correct fix (real shared-edge detection via GeoPandas, styled as a proper
double-line convention) is a planned post-launch polish item, not done yet.

### Terrain relief (hillshade)

`index.html` wires up a `raster-dem` source + `hillshade` layer pointing at
`data/basemap/roaring-fork-terrain.pmtiles`, from [Mapterhorn](https://mapterhorn.com)'s free,
Terrarium-encoded elevation PMTiles (BSD-3 licensed, Copernicus DEM at 30m resolution for this
area). **Generated 7/29/26** with:

```
pmtiles extract https://download.mapterhorn.com/planet.pmtiles data/basemap/roaring-fork-terrain.pmtiles \
  --bbox=-108.6,38.6,-106.0,40.0 --maxzoom=10
```

First attempt used `--maxzoom=11` and came out to 103MB - just over GitHub's 100MB cap. Dropping to
`--maxzoom=10` (hillshade doesn't need street-level zoom to look good) brought it down to ~39.5MB,
comfortably under the limit. This is a separate file from the main basemap's ~88.5MB, so it has its
own independent 100MB budget and doesn't compete with it.

### Local testing note: use RangeHTTPServer, not plain `http.server`

PMTiles reads the archive via HTTP byte-range requests, and Python's built-in
`python3 -m http.server` has unreliable Range support - it can silently ignore `Range` headers and
return the *entire* file instead of the requested slice (confirmed 7/28/26: it failed this way for
every file on the server, not just the large pmtiles one, so it's not about file size). The pmtiles
JS library detects this and throws `"Server returned no content-length header or content-length
exceeding request"` rather than silently corrupting itself - if you see that error locally, this is
why.

Use the project's dev server instead, which layers `Cache-Control: no-store` on top of
RangeHTTPServer's Range support (see "Running it locally" above for why both matter):

```
python3 scripts/serve.py
```

`http.server` also raises `BrokenPipeError` in its own console when this happens. That traceback
is a symptom, not a separate problem: it answered `200` and started streaming the whole 17 MB
archive, and the PMTiles client - which wanted a few KB - hung up on it.

This is purely a local dev server limitation. GitHub Pages handles Range requests correctly,
confirmed 7/30/26 against the live archive:

```
curl -s -o /dev/null -D - -r 0-99 \
  https://chgiersch.github.io/pchr-watershed-directory/data/basemap/roaring-fork.pmtiles

HTTP/2 206
content-range: bytes 0-99/18743140
access-control-allow-origin: *
```

Use `-r`, not `-I -H "Range: ..."`. The latter sends a HEAD request, which servers answer with
`200` whether or not they support ranges - so it looks like a failure when nothing is wrong.
