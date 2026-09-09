---
name: "annotated-coding"
description: "Documentation and explanation standard for code in this repository: how much to annotate, at what level, and which categories of code require annotation because they fail silently. Use whenever writing, editing, refactoring or explaining code of any kind – Python, JavaScript, SQL, shell, notebooks, config. Trigger on requests like 'write a script that…', 'build me a…', 'fix this code', 'add a feature to…', 'why isn't this working', or any task where code will be produced or modified. Governs annotation depth, diff visibility, and the requirement that a reader who did not write the code can debug it. Applies IN ADDITION TO dev-workflow, which governs git and commit protocol. Consult before writing any code."
---

# Annotated Coding

The documentation standard for this repository. Code here is maintained by one
person and will eventually be handed to someone who has never met them, so the
bar is not "does it run" but "can a competent engineer who did not write this
read it, find the broken line, and understand why it broke."

That bar applies to every change, and it is the standard the rest of this
document serves.

---

## TWO AUDIENCES, TWO LEVELS OF DETAIL

Source files and generated artifacts are documented differently.

**Source is written to be read.** `directory.css`, `directory-map-link.js`,
`index.html`, everything in `scripts/` – these carry full explanation. A reader
arriving cold should not have to reconstruct reasoning from the diff history.

**Generated artifacts carry only what survives the trip.** The WordPress bundle
is pasted into a page the maintainer does not control and cannot easily inspect.
It keeps the provenance header and any comment that would stop someone editing
the bundle by hand instead of the source. Explanatory commentary belongs in the
source it was generated from.

The distinction is source versus artifact, not branch versus branch. Stripping
comments when promoting to `main` does not work under GitFlow: release branches
merge into both `main` and `dev`, so a trim made at release time propagates
straight back into the working branch and the explanation is lost everywhere. If
a leaner shipped file is wanted, the place to do it is the build step in
`scripts/build_directory.py`, which already inlines and rewrites content – not
the git history.

---

## THREE LEVELS OF ANNOTATION

Every change is explained at three levels. Not every level needs equal weight –
a one-line fix does not need a file-level tour – but decide consciously what
each level needs.

### Level 1 – File

What this file's job is, in one or two sentences, and where it sits relative to
everything else. Written when the file is created, restated when returning to it
after time away.

> `scripts/build_reference_extents.py` – reads the reference boundary GeoJSON and
> emits the label anchor points the map uses for context layers. Nothing else
> computes anchors; this is the only place that happens.

The second sentence carries more weight than the first. Knowing a file is the
*only* place something happens is what makes it findable later.

### Level 2 – Function

What it takes, what it returns, what it does in between, and the part most often
skipped and most valuable: **why it exists as a separate function at all.**

> `render_entry(org)` – takes one org dict, returns its HTML fragment. Separate
> from `build_fragment()` because the entry markup is the thing most likely to
> change when the county revises the template, and isolating it means a markup
> change cannot break section assembly.

### Level 3 – Line

Not every line. Annotate a line when any of these hold:

- **It uses an unfamiliar library, idiom or pattern.** Not everyone maintaining
  this will know the same tools.
- **It looks wrong but is right.** The counterintuitive line is the one someone
  later "fixes" into a bug. `overflow-x: clip` on `body` is the standing example
  in this repo.
- **It encodes a decision.** A magic number, threshold, projection, or fill
  value. Where did it come from, and what happens if it changes?
- **It would fail silently.** See the section below.

Skip lines that are self-evident to an experienced engineer. Over-annotating
obvious code is noise, and noise trains a reader to skim, which defeats the
purpose.

---

## COMMENTS EXPLAIN WHY, AND NAME THE INCIDENT

The house style in this codebase is that a comment carries what the code cannot:
the constraint, the non-obvious reason, the incident the line prevents. Match it.

```
/* overflow-x: clip, not hidden - hidden on body creates a scroll container
   that breaks position: sticky on the map. Changing this un-sticks the map. */
```

That comment is worth permanent residence because it stops a specific, plausible
regression. A comment that restates the line does not.

**Stale comments are worse than no comments.** When a comment narrates history
that no longer matters, delete it. Keep the ones that would prevent someone from
reintroducing a bug.

---

## SHOW THE DIFF

Changes to existing code are reviewed as diffs. Reproduce that regardless of the
environment or tooling in use.

**When editing existing code, show what changed before or alongside the change.**
Old line, new line, one sentence on why – even where edits happen through tool
calls that do not surface a visible diff.

```
- if (e.origin !== MAP_ORIGIN) return;
+ if (e.origin !== MAP_ORIGIN || e.source !== frame.contentWindow) return;

Origin alone does not identify the sender - any frame served from the same
origin could post a message. Pinning the source window closes that.
```

**Never make a multi-file change without listing the files and what each one
got.** A change touching four files described as "updated the pipeline" is
exactly what becomes undebuggable.

**Never make an unrequested change silently.** If something else needs fixing
along the way, say so and either ask or flag it in the summary. An unexplained
change discovered later undermines confidence in every other change.

---

## WHERE WRONG OUTPUT LOOKS LIKE RIGHT OUTPUT

Some categories of code fail without erroring. These get annotated whether or not
they look obvious, because the normal debugging instinct – look for the error –
does not fire.

**Geospatial code.** Projection mismatches, unit confusion (degrees versus
metres), silent reprojection, null geometries, and coordinate order (lat/lon
versus lon/lat) all produce output that renders without complaint and is wrong.
State the CRS at every boundary where data enters or leaves.

**Filters and joins.** A filter matching nothing returns an empty result, not an
error. A join on a mismatched key returns fewer rows, not an error. After any
filter or join, state the expected count and add a check.

**Statistical code.** A calculation that runs has no idea whether its assumptions
hold. Annotate what the method assumes and what a violation would look like in
the output.

**Fill values and nodata.** `-9999` treated as an elevation quietly wrecks a
mean. State the nodata convention for any raster or array.

For these categories, prefer an assertion or a printed count over a comment about
one. A comment saying "should be 17 orgs" is worth less than a line that checks –
which is why `scripts/check.py` exists and why new findings become checks rather
than patches.

---

## STRUCTURE

**One logical block at a time.** Deliver a block, explain it, confirm it works,
then move to the next. Two hundred lines explained retroactively is a wall of
text attached to code already skimmed.

**In notebooks: one operation per cell**, each printing evidence it did its job.
Not `print("done")` – print the shape, the row count, the CRS, the value range.
Those prints are the debugging trail.

**Save intermediate outputs to disk.** A pipeline whose intermediates vanish on
restart cannot be debugged incrementally.

**Prefer explicit over clever.** A three-deep nested comprehension is impressive
and unmaintainable. Write the loop. Read speed matters more than line count.

---

## THE HANDOFF STATEMENT

Close a meaningful block of work with a short statement of what the reader can
now do independently. Not a quiz – a handoff.

> You can now change the dry-spell threshold on line 34, swap the input
> collection from Sentinel-2 to Landsat on line 12 plus the band names on 18–20,
> and tell from the printed row count whether the date filter did what you
> expect.

This confirms the explanation covered what matters and surfaces what it did not.
If that sentence cannot be written honestly, the explanation is incomplete.

**When something is called unclear, treat it as signal about the code, not just
the explanation.** Often the right response is simpler code rather than a better
paragraph.

---

## ANTI-PATTERNS

Things that feel efficient and defeat the purpose:

**Delivering working code with no explanation because it works.** Code that works
and is not understood is the specific risk this standard exists to manage.

**Explaining after the fact instead of alongside.** Retroactive explanation
attached to already-delivered code gets skimmed.

**"This handles the edge cases."** Which ones? Handled how? The phrasing hides
exactly the complexity that will need debugging.

**Silently rewriting a file when asked to change one thing.** Even when the
rewrite is better. Say what you intend and why.

**Agreeing with the proposed approach instead of flagging a real problem.** If
the approach is wrong, the statistics do not support the conclusion, or the code
works by accident, say so plainly and early.

**Assuming generated code is correct because it ran.** Read what was produced
before presenting it. Review only engages if there is something to review.

---

## RELATIONSHIP TO DEV-WORKFLOW

`dev-workflow` governs process: GitFlow branching, commit protocol, when to ask
before committing, verification discipline, debugging sequence.

This skill governs comprehension: how code is explained while it is written.

Both apply to the same work. `dev-workflow` decides whether a change is ready to
commit; this one decides whether the change is understood. Where they overlap –
both care about a clear diff before a commit – follow both.
