#!/usr/bin/env python3
"""
Project lint: verifies this repository's own accepted patterns.

Generic linters cannot know this project's rules - they were established the
expensive way, and each check below names the incident-class it prevents.
Run from anywhere; paths resolve against the repo root:

    python3 scripts/check.py

Exit code 0 means every check passed. Any failure prints the rule and the
reason it exists, and exits 1 - suitable for a pre-commit hook or CI step.

The checks fall into three groups:
  SYNTAX     - the code parses at all (node --check, py_compile)
  EMBED      - the WordPress-embedding contract: nothing in the shipped CSS
               or JS may reach outside this feature's containers or origins
  ARTIFACTS  - generated outputs are structurally sound (only when present;
               _working/ artifacts are gitignored and may not exist)
"""

import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

CSS = REPO / "directory.css"
LINK_JS = REPO / "directory-map-link.js"
MAP_HTML = REPO / "index.html"
ORGS = REPO / "data" / "clean" / "orgs.json"
BOUNDARIES = REPO / "data" / "clean" / "boundaries.geojson"
PAGE = REPO / "directory.html"
BUNDLE = REPO / "_working" / "directory-wordpress.html"

failures = []
skipped = []


def check(name, ok, why_it_exists):
    """Record one result. `why_it_exists` names the incident-class prevented."""
    if ok:
        print(f"  ok      {name}")
    else:
        print(f"  FAIL    {name}")
        failures.append((name, why_it_exists))


def extract_map_script(html_text):
    """The map's application code is the largest inline <script> block."""
    blocks = re.findall(r"<script[^>]*>(.*?)</script>", html_text, re.S)
    return max(blocks, key=len) if blocks else ""


# ---------------------------------------------------------------- SYNTAX ----

def run_syntax_checks():
    print("SYNTAX")
    for py in sorted((REPO / "scripts").glob("*.py")):
        r = subprocess.run([sys.executable, "-m", "py_compile", str(py)],
                           capture_output=True)
        check(f"py_compile {py.name}", r.returncode == 0,
              "Python that does not parse cannot be trusted to have been run.")

    map_js = extract_map_script(MAP_HTML.read_text())
    tmp = REPO / "_working" / "_check_map.js"
    tmp.parent.mkdir(exist_ok=True)
    tmp.write_text(map_js)
    for label, path in (("index.html inline script", tmp),
                        ("directory-map-link.js", LINK_JS)):
        r = subprocess.run(["node", "--check", str(path)], capture_output=True)
        check(f"node --check {label}", r.returncode == 0,
              "A syntax error in shipped JS disables every feature after it, "
              "silently on some browsers.")
    tmp.unlink()


# ----------------------------------------------------------------- EMBED ----

def run_embed_checks():
    print("EMBED CONTRACT")
    css = CSS.read_text()
    link_js = LINK_JS.read_text()
    map_js = extract_map_script(MAP_HTML.read_text())

    # Every custom property namespaced. Custom properties are page-global
    # inside WordPress; a generic name (--gap) collides with theme updates.
    # Line-anchored: a declaration starts its line with --, while a BEM
    # modifier followed by a pseudo-class (.x--mod:focus) does not - the
    # unanchored version of this pattern false-positived on exactly that.
    bad_defs = re.findall(r"(?m)^\s*(--(?!wmd-)[\w-]+)\s*:", css)
    bad_refs = re.findall(r"var\(--(?!wmd-)", css)
    check("CSS custom properties all --wmd- prefixed",
          not bad_defs and not bad_refs,
          "Unprefixed page-global variable names collide with the host theme; "
          f"offenders: {sorted(set(bad_defs))[:5]}")

    # Selector scoping. Only :root and the audited body rule may address
    # anything outside this feature's class-scoped containers. A bare element
    # or universal selector restyles the county's page (box-sizing and
    # a:focus-visible both shipped that way once and were caught in audit).
    loose = []
    for m in re.finditer(r"^([^\s/@}][^\{]*)\{", css, re.M):
        sel = m.group(1).strip()
        for part in sel.split(","):
            part = part.strip()
            if not part:
                continue
            if part == ":root" or part == "body":
                continue
            if part.startswith(".") or part.startswith("@"):
                continue
            loose.append(part)
    check("CSS selectors scoped to feature classes (plus :root, body)",
          not loose,
          "Element-level selectors restyle the host WordPress page; "
          f"offenders: {loose[:5]}")

    # The audited body rule: exactly the three properties whose host-page
    # effect was analyzed (margin, background match the theme; overflow-x
    # clip is the sticky fix). Anything added needs the same analysis.
    body_m = re.search(r"^body\s*\{([^}]*)\}", css, re.M)
    body_props = sorted(p.split(":")[0].strip()
                        for p in body_m.group(1).split(";") if p.strip()) if body_m else []
    check("body rule limited to the audited property set",
          body_props == ["background", "margin", "overflow-x"],
          "Every body declaration reaches the host page; each needs explicit "
          f"analysis. Found: {body_props}")
    check("body carries overflow-x: clip (sticky-map guard)",
          bool(body_m) and "clip" in body_m.group(1),
          "The host theme's overflow-x:hidden on body silently disables "
          "position:sticky; clip provides the clipping without the breakage.")

    # Link script safety envelope: the county page runs this verbatim.
    sinks = re.findall(r"innerHTML|insertAdjacent|document\.write|eval\(|"
                       r"new Function|localStorage|sessionStorage|"
                       r"document\.cookie|XMLHttpRequest|fetch\(", link_js)
    check("link script free of injection/exfiltration sinks",
          not sinks,
          f"The host-page script's worst case must stay 'scrolls and toggles "
          f"a class'; found: {sorted(set(sinks))}")
    check("link script wrapped in strict-mode IIFE",
          "(function () {" in link_js and "'use strict'" in link_js,
          "Globals written on the county's page can collide with theme or "
          "plugin code.")

    # Origins pinned at both ends - the silent failure mode when they drift
    # is 'everything renders, nothing links'.
    check("link script pins MAP_ORIGIN to the published map",
          "https://chgiersch.github.io" in link_js,
          "Host->map messages are refused unless the target origin matches.")
    check("map allowlists the county origin",
          "https://pitkincountyrivers.com" in map_js,
          "Map->host messages are dropped unless the sender is allowlisted.")

    # Debug hygiene in the map application code.
    noisy = re.findall(r"console\.(log|debug|table|info)\(|debugger\b", map_js)
    check("map script free of debug output", not noisy,
          f"Debug statements ship to every visitor; found: {sorted(set(noisy))}")

    # Shipped and public source speaks in roles, not stakeholder names.
    named = []
    for path in (CSS, LINK_JS, MAP_HTML):
        for name in ("Gwen", "Tim Braun", "Braun,"):
            if name in path.read_text():
                named.append(f"{path.name}:{name}")
    check("shipped source free of stakeholder first names", not named,
          f"Roles outlast people, and view-source is public; found: {named}")


# ------------------------------------------------------------------ DATA ----

def run_data_checks():
    print("DATA")
    orgs = json.loads(ORGS.read_text())
    check("orgs.json holds 17 organizations", len(orgs) == 17,
          f"An accidental deletion or duplication is invisible until the page "
          f"renders short; found {len(orgs)}.")
    required = {"org_name", "org_short", "section", "scope", "tier"}
    missing = [o.get("org_short", "?") for o in orgs
               if not required.issubset(o)]
    check("every org carries the required fields", not missing,
          f"The generator and the map both index these; incomplete: {missing}")

    sections = {o["section"] for o in orgs}
    expected = {"Local watershed organizations",
                "Basin and statewide organizations",
                "Water providers"}
    check("org sections match the generator's SECTIONS strings",
          sections == expected,
          "A mismatched string silently produces an EMPTY directory section "
          f"rather than an error; found: {sorted(sections)}")

    b = json.loads(BOUNDARIES.read_text())
    check("boundaries.geojson holds 11 features",
          len(b.get("features", [])) == 11,
          f"One shape, one place - a change in count means a shape was added "
          f"or lost outside the scripted pipeline; found {len(b.get('features', []))}.")


# ------------------------------------------------------------- ARTIFACTS ----

def run_artifact_checks():
    print("ARTIFACTS")
    page = PAGE.read_text()
    check("standalone page carries the development-copy notice",
          'class="prototype-note"' in page,
          "The GitHub Pages copy must point readers at the official county "
          "page once that page is live.")

    if not BUNDLE.exists():
        skipped.append("bundle checks (_working/directory-wordpress.html "
                       "not present - run build_directory.py --wordpress)")
        return
    bundle = BUNDLE.read_text()
    check("bundle contains the id=\"directory\" wrapper",
          'id="directory"' in bundle,
          "The link script exits silently without it - both directions of "
          "the map/directory link die with no error (incident 2026-09-02).")
    check("bundle omits the development-copy notice",
          '<p class="prototype-note"' not in bundle,
          "The county page IS the official copy; the notice belongs only on "
          "the standalone build.")
    # Comments stripped first: the provenance header legitimately MENTIONS
    # <script> tags in prose, which a naive count reads as a tag (this
    # check's own first run failed on exactly that).
    bundle_code = re.sub(r"<!--.*?-->", "", bundle, flags=re.S)
    check("bundle inlines exactly one style and one script block",
          bundle_code.count("<style>") == 1 and bundle_code.count("<script>") == 1,
          "The single-block architecture is the zero-dependency guarantee; "
          "extra blocks mean the structure drifted.")
    check("bundle carries a provenance header",
          "GENERATED PAGE" in bundle,
          "The deployed page must be traceable to a repository version.")

    # The robustness pair: controls dormant until proven alive, failures loud.
    check("Show-on-map buttons emitted hidden",
          'data-show-on-map hidden' in bundle,
          "If the link script dies silently, live buttons become seventeen "
          "dead controls on the page under review.")
    check("link script reveals the hidden buttons on init",
          "removeAttribute('hidden')" in LINK_JS.read_text(),
          "Buttons emitted hidden stay hidden forever without the reveal.")
    check("map shows a visible message on data-load failure",
          "map-load-error" in extract_map_script(MAP_HTML.read_text()),
          "A failed fetch must not leave a silently blank map; the directory "
          "is the designed fallback and the message must say so.")


if __name__ == "__main__":
    run_syntax_checks()
    run_embed_checks()
    run_data_checks()
    run_artifact_checks()

    print()
    for s in skipped:
        print(f"  skipped {s}")
    if failures:
        print(f"\n{len(failures)} CHECK(S) FAILED:\n")
        for name, why in failures:
            print(f"  {name}\n    why this rule exists: {why}\n")
        sys.exit(1)
    print("all checks passed")
