# PCHR Watershed Directory

Interactive map + organization directory for Pitkin County Healthy Rivers.
Two deployment targets from one repo:

1. Standalone map (`index.html`) - MapLibre GL JS + PMTiles, published via
   GitHub Pages from `main`. Embedded as an iframe by target 2.
2. WordPress bundle - `python3 scripts/build_directory.py --wordpress`
   generates `_working/directory-wordpress.html`, a single self-contained
   HTML block (inline style + markup + inline script) pasted into a page on
   pitkincountyrivers.com. `directory.css` and `directory-map-link.js` are
   inlined into it at build time - edit the source files, never the bundle.

The two halves talk across origins via postMessage; both ends pin origins
exactly. `scripts/check.py` is the project lint and encodes the incident
history - read it before changing anything it covers.

## Commands

- Lint (run before EVERY commit): `python3 scripts/check.py`
- Build both outputs: `python3 scripts/build_directory.py --wordpress`
- Dev server (Range + no-store, required for PMTiles and honest iframe
  testing): `python3 scripts/serve.py` then http://localhost:8000/

## Hard rules

- GitFlow: `main` (released) / `dev` (integration) / `feature|fix|docs/*`
  branches. Merge commits, NEVER squash. Releases follow RELEASING.md
  literally, including the verify-main-moved-before-tagging step.
- Chris approves every commit. Propose the commit message, wait.
- Chris verifies all visual output himself. Never claim a rendered page
  looks right - hand him a test script instead.
- `check.py` green before any commit. If a change legitimately breaks a
  check, the check gets updated in the same commit with reasoning.
- New accepted review findings either get fixed or become a new check in
  `scripts/check.py` - reviews ratchet into lint rules.
- The WordPress bundle is deployed by hand-paste. A repo change is NOT
  deployed until the bundle is rebuilt (no -dirty in its header) and
  re-pasted. Map-side changes deploy via GitHub Pages on release, no paste.

## Embed contract (why the CSS/JS look the way they do)

- Shipped code runs verbatim on a government WordPress page. All CSS
  selectors are class-scoped except `:root` and one audited `body` rule
  (margin, background, overflow-x: clip - the clip is a sticky-position
  fix; do not change without re-analysis).
- All CSS custom properties use the `--wmd-` prefix (page-global namespace).
- The link script is a strict-mode IIFE with no injection/exfiltration
  sinks. Worst case must remain "scrolls and toggles a class".
- Shipped source speaks in roles, never stakeholder first names.

## Conventions

- En-dash (–) in prose, never em-dash. Applies to comments, docs, commit
  messages, and any text Chris will paste or send.
- Paste-ready shell blocks contain NO `#` comments - Chris's zsh executes
  stray `#` fragments.
- Comments explain WHY and name the incident they prevent, matching the
  style already in the codebase.
- Data lives in `data/clean/orgs.json` (17 orgs) and
  `data/clean/boundaries.geojson` (11 features); the generator and map
  both index them. Section strings must match the generator's SECTIONS
  exactly - a mismatch silently renders an empty section.

## Environment

- Node comes from nvm, not Homebrew. `scripts/check.py` shells out to
  `node --check`; with node missing the SYNTAX group silently loses those
  two checks rather than failing loudly.
- `.venv` was built against Homebrew python 3.14.3 and the installed
  Homebrew python is now 3.14.7. If imports start failing oddly, recreate
  it: `python3 -m venv .venv && pip install -r requirements.txt`.
- Intel Mac, and Homebrew has dropped Intel support. GDAL/GEOS/PROJ under
  `geopandas` are the likely first thing to stop building – MacPorts still
  supports Intel and is the fallback worth reinstalling at that point, not
  before.

## Working style

Chris is an MS GIS student building this pro bono; he maintains everything
in this repo himself and must understand every change well enough to debug
it alone. Explain reasoning at decision points, show diffs before applying
when asked, and prefer one small reviewed change over three fast ones. The
`.claude/skills/annotated-coding` and `.claude/skills/dev-workflow` skills
govern this in detail - honor them.
