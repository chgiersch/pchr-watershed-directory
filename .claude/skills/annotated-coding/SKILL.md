---
name: "annotated-coding"
description: "How to write and explain code FOR Chris so that he understands, retains, and can independently debug it. Use this skill whenever writing, editing, refactoring, or explaining code of any kind for Chris — Python, ArcPy, JavaScript, Google Earth Engine, SQL, shell, notebooks, config files, anything. Trigger on requests like 'write a script that…', 'build me a…', 'fix this code', 'add a feature to…', 'help me with this function', 'why isn't this working', or any task where code will be produced or modified. Also trigger when Chris is working in Cursor, Cowork, Claude Code, or a Jupyter notebook, and when producing code as part of a larger deliverable (a capstone analysis, a client map, a data pipeline). This skill governs explanation depth, diff visibility, and the requirement that Chris can debug the result without help. It applies IN ADDITION TO dev-workflow, which governs git and commit protocol. Consult before writing any code."
---

# Annotated Coding

How to produce code for Chris such that he ends up understanding it, not just possessing it.

Chris ships fast with AI assistance and is good at it. The PCHR watershed map went from nothing
to working in three days. The risk that comes with that speed is not bad code — it is code he
owns but cannot fully explain, which becomes code he cannot debug at 11pm the night before a
client demo.

This skill exists to close that gap without slowing him down much.

---

## THE RULE THAT OVERRIDES EVERYTHING

**The test for any piece of code delivered to Chris: could he debug it alone, tomorrow, without
you?**

Not "is it correct." Not "does it run." Could he open the file, read it, find the broken line,
and understand why it broke.

If the answer is no, the work is not finished regardless of whether the code works. Add the
explanation, or restructure the code into something explainable, or both.

This is the whole point. Everything below is in service of it.

---

## THREE LEVELS OF ANNOTATION

Every code deliverable gets explained at three levels. Not every level needs equal weight — a
one-line fix does not need a file-level tour — but consciously decide what each level needs.

### Level 1 — File

State what this file's job is, in one or two sentences, and where it sits relative to everything
else. Do this when creating a file, and restate it briefly when returning to a file after time
away.

> `scene_scoring.py` — takes a date range and an AOI, pulls PRISM daily precipitation, and scores
> every available Sentinel-2 scene by how dry the preceding period was. Outputs a ranked CSV.
> Nothing else in the pipeline reads PRISM; this is the only place that happens.

The second sentence matters more than the first. Knowing a file is the *only* place something
happens is what makes it findable six months later.

### Level 2 — Function

For each function: what it takes, what it gives back, and what it does in between. Plus the part
that is easy to skip and most valuable — **why it exists as a separate function at all.**

> `score_dry_spell(precip_series, window_days)` — takes a pandas Series of daily precipitation
> and a lookback window, returns a single float score. Higher = drier. It is separate from
> `rank_scenes()` because the scoring rule is the thing most likely to change, and keeping it
> isolated means changing it does not risk breaking the ranking logic.

### Level 3 — Line

Not every line. Annotate a line when any of these are true:

- **It is doing something Chris has not seen before.** New library, new idiom, new pattern.
- **It looks wrong but is right.** The counterintuitive line is the one that gets "fixed" into a
  bug six months later.
- **It encodes a decision.** A magic number, a threshold, a chosen projection, a fill value.
  Where did that come from and what happens if it changes?
- **It would fail silently.** Especially anything statistical or geospatial — see below.

Skip annotation on lines that are self-evident to someone with a decade of software experience.
Over-annotating obvious code is noise, and noise trains him to skim, which defeats the purpose.

---

## SHOW THE DIFF, ALWAYS

Chris specifically values Cursor's line-by-line change view and specifically dislikes tools that
change files invisibly. Reproduce that experience regardless of environment.

**When editing existing code, always show what changed before or alongside the change.** Old
line, new line, one sentence on why. Even in environments where edits happen through tool calls
that do not surface a visible diff.

```
- scenes = scenes.filter(ee.Filter.lt('CLOUD_COVER', 20))
+ scenes = scenes.filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))

Sentinel-2 uses CLOUDY_PIXEL_PERCENTAGE; CLOUD_COVER is the Landsat property name. The old
filter silently matched nothing, which is why the collection came back empty rather than erroring.
```

**Never make a multi-file change without listing the files and what each one got.** A change that
touches four files and is described as "updated the pipeline" is exactly the kind of thing that
becomes undebuggable.

**Never make an unrequested change silently.** If something else needs fixing along the way, say
so and either ask or flag it clearly in the summary. Discovering an unexplained change later
destroys trust in every other change.

---

## CALIBRATE TO WHAT CHRIS ALREADY KNOWS

He has a decade of iOS development and product leadership. Do not explain what a function is, what
a loop does, what version control is for, or why you would extract a constant. That is
condescending and wastes his attention.

**Solid ground — build on it, do not explain it:**
general programming, software architecture, APIs, JSON, debugging methodology, git, Python
fundamentals, JavaScript, ArcPy, ArcGIS Pro geoprocessing, SQL basics.

**Newer ground — explain the concept, not just the syntax:**
Google Earth Engine Python API (as distinct from the JavaScript API he knows), machine learning
and `sklearn` patterns, embeddings and vector representations, cloud-native geospatial formats
(STAC, COG, Zarr, GeoParquet), `xarray` and n-dimensional arrays, statistical methods beyond the
descriptive, `asyncio` and concurrency patterns in Python.

**When introducing something from the newer list, explain the idea before the code.** Two or
three sentences on what the thing *is* and why it exists, then the implementation. The syntax is
easy to look up; the mental model is what makes it stick.

When unsure which list something falls in, ask rather than guessing. "Have you worked with xarray
before?" costs one line and saves either a wasted explanation or a silent gap.

---

## WHERE WRONG OUTPUT LOOKS LIKE RIGHT OUTPUT

Some categories of code fail without erroring. These get annotation whether or not they seem
obvious, because the normal debugging instinct — look for the error — does not fire.

**Statistical code.** A regression that runs and returns coefficients has no idea whether the
assumptions hold. Annotate: what assumption does this method make, and what would violating it
look like in the output? If a p-value, effect size, or correlation is being computed, say what a
suspicious result would look like.

**Geospatial code.** Projection mismatches, unit confusion (degrees versus meters), silent
reprojection, null geometries, and coordinate order (lat/lon versus lon/lat) all produce output
that renders without complaint and is wrong. Annotate the CRS at every boundary where data
enters or leaves.

**Filters and joins.** A filter that matches nothing returns an empty result, not an error. A
join on a mismatched key returns fewer rows, not an error. After any filter or join, say what the
expected row count is and add a check.

**Fill values and nodata.** `-9999` treated as an elevation will quietly wreck a mean. State what
the nodata convention is for any raster or array.

For these categories, prefer adding an actual assertion or print statement in the code over a
comment about it. A comment saying "should be 47 rows" is worth less than a line that checks.

---

## STRUCTURE FOR LEARNING

**One logical block at a time.** Deliver a block, explain it, confirm it works, then move to the
next. Do not deliver 200 lines and then explain them retroactively — by then the explanation is a
wall of text attached to code he has already skimmed.

**In notebooks: one operation per cell.** Every cell does one thing and prints evidence that it
did it. Not `print("done")` — print the actual shape, the row count, the CRS, the value range.
The print statements are the debugging trail.

**Save outputs to disk, never only in memory.** A pipeline whose intermediate results vanish on
kernel restart cannot be debugged incrementally.

**Prefer explicit over clever.** A list comprehension nested three deep is impressive and
unmaintainable. Write the loop. Chris's read speed matters more than line count.

---

## THE COMPREHENSION CHECK

After delivering a meaningful block of code, close with a short statement of what he should now be
able to do independently. Not a quiz — a handoff.

> You should now be able to change the dry-spell threshold (line 34), swap the input collection
> from Sentinel-2 to Landsat (line 12, plus the band names on 18–20), and tell from the printed
> row count whether the date filter is doing what you expect.

This does two things: it confirms the explanation covered the parts that actually matter, and it
surfaces the parts it did not. If you cannot write this sentence honestly, the explanation was
incomplete.

**When he says something is unclear, that is signal about the code, not just the explanation.**
Consider whether the right response is a better explanation or simpler code. Often it is the
second.

---

## ANTI-PATTERNS

Things that feel efficient and defeat the purpose:

**Delivering working code with no explanation because it works.** The whole risk being managed
here is code that works and is not understood.

**Explaining after the fact instead of alongside.** Retroactive explanation attached to already-
delivered code gets skimmed.

**"This handles the edge cases."** Which edge cases? Handled how? This phrasing hides exactly the
complexity that will need debugging.

**Silently rewriting a file when asked to change one thing.** Even if the rewrite is better. Say
what you want to do and why.

**Matching his enthusiasm instead of flagging a real problem.** If the approach is wrong, or the
statistics do not support the conclusion, or the code works by accident, say so. He builds fast,
which means a wrong direction propagates fast.

**Assuming the AI-generated code is right because it ran.** Read what was produced before
presenting it. Chris's engineering judgment is the safeguard here, but it only engages if he is
given something to judge.

---

## RELATIONSHIP TO DEV-WORKFLOW

`dev-workflow` governs process: GitFlow branching, commit protocol, when to ask before committing,
verification discipline, debugging sequence.

This skill governs comprehension: how code is explained while it is being written.

Both apply to the same work. `dev-workflow` decides whether a change is ready to commit; this one
decides whether Chris understands what he is committing. When they overlap — for example, both
care about presenting a clear diff before a commit — follow both.
