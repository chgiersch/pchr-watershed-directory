# PCHR Watershed Directory Map

Interactive map + text directory of water-management organizations in the
Roaring Fork watershed, for Pitkin County Healthy Rivers.

`README.md` is thorough and current — read it before changing anything
structural. This file covers what a session needs up front and the rules that
aren't obvious from the code.

## Commands

```bash
source .venv/bin/activate                     # data scripts only; the map needs no build
python3 scripts/serve.py                      # → http://localhost:8000/directory.html
python3 scripts/check.py                      # project lint — must pass before any release
python3 scripts/build_directory.py --wordpress  # regenerate the WordPress bundle
```

Use `scripts/serve.py`, never `python3 -m http.server`. The basemap is a PMTiles
archive read by HTTP byte-range requests, and the stdlib server ignores `Range`
headers. This has cost real debugging time — see the README's local-testing note.

`scripts/check.py` shells out to `node --check`. Node comes from nvm here; if
`node` isn't on PATH the SYNTAX group silently loses coverage.

## Branching — `main` is not where work happens

`main` is published live by GitHub Pages and only ever receives merges from
`release/*` or `hotfix/*`. Day-to-day work goes on `dev`, via `feature/*`,
`fix/*` or `docs/*` branches.

**Never commit directly to `main`.** If a session starts there, branch off `dev`.

`RELEASING.md` is a step-by-step checklist with guards at each stage — follow it
literally. Two releases (v1.1.0 and the first v1.3.0) shipped mis-tagged by
skipping step 4, which is the "read the `git log` output before tagging" guard.
Merge commits, never squash.

## Architecture

- `index.html` — the map alone, static, fetches its GeoJSON at runtime. This is
  what gets embedded in an iframe on the county's site.
- `directory.html` — prototype host page; map plus directory, showing the
  linkage. Not the deliverable — it exists so the two can be reviewed together.
- `directory-map-link.js` — cross-origin bridge between them.
- `scripts/build_directory.py` — generates the directory HTML; `--wordpress`
  emits the self-contained bundle that's pasted into WordPress.
- `data/clean/` + `data/reference/` — GeoJSON, the source of truth.
  `data/basemap/` — PMTiles archives (~58 MB, most of the clone).

## Conventions the lint enforces

`scripts/check.py` encodes rules learned the expensive way; each check names the
incident class it prevents. In particular:

- **CSS custom properties must be `--wmd-` prefixed**, and selectors scoped to
  feature classes. The bundle drops into someone else's WordPress theme — an
  unscoped rule leaks into the host page.
- **`directory-map-link.js` stays a strict-mode IIFE** with `MAP_ORIGIN` pinned
  to the published map, and the map allowlists the county origin. No dynamic
  injection or exfiltration sinks.
- **No stakeholder first names in shipped source.** The repo is public.
- Shapefiles are gitignored on purpose — GeoJSON is canonical, and a second
  copy of every shape drifts silently. Export locally if a desktop tool needs one.

Scratch work goes in `_working/` (gitignored). Don't commit it.

## Environment notes

`.venv` was built against Homebrew `python@3.14` (3.14.3); the installed
Homebrew python is now 3.14.7. If imports start failing oddly, recreate it:
`python3 -m venv .venv && pip install -r requirements.txt`.

`geopandas` is the slow install — it binds to GDAL/GEOS/PROJ. This is an Intel
Mac and Homebrew has dropped Intel support, so those wheels may eventually stop
building. `brew install gdal geos proj` first, per the README. If Homebrew can't
supply them any more, MacPorts still supports Intel and is the fallback worth
reaching for at that point.
