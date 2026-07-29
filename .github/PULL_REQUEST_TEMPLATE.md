<!--
Target branch check:
  feature/*  -> dev
  release/*  -> main   (then merge back into dev)
  hotfix/*   -> main   (then merge back into dev)
-->

## What this does

<!-- One or two sentences. What problem does this solve, or what does it add? -->

## Why this way

<!-- The reasoning the diff can't show: constraints, tradeoffs, and any obvious
     alternative that was considered and rejected (and why). If a fix, state the
     confirmed root cause - not just the symptom. -->

## Data changes

<!-- Delete this section if no data files changed.
     - Which boundaries/orgs/reference layers were added, edited, or removed
     - Source and pull date for anything new (source / pulldate / srcurl / caveat)
     - Geometry check: `holes: 0, valid: True` for every affected row?
     - Confirm one shape = one row in boundaries.geojson - no duplicate copies
       added in data/reference/ or as standalone per-org files -->

## How this was verified

<!-- What was actually checked, and how. Be specific about what was confirmed
     vs. assumed - "reloaded and the layer renders" is different from "compared
     against the DOLA source". -->

## Needs eyes before merge

<!-- Anything visual - styling, label placement, color, layout - is Chris's call.
     List what to look at and where: which zoom, which area of the map. -->

- [ ] 

## Left undone

<!-- Known gaps, follow-ups, anything deliberately deferred. Link an issue if
     there is one. Delete if nothing. -->

---

## Checklist

- [ ] Targeting the right branch (see comment at top)
- [ ] No debug code, temporary filters, commented-out blocks, or stale comments
- [ ] Derived files regenerated if their sources changed
- [ ] Syntax checked / the thing actually runs
- [ ] README updated if structure, schema, or conventions changed
