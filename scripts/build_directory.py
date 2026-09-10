#!/usr/bin/env python3
"""
Generate the organization directory as static HTML from data/clean/orgs.json.

WHY GENERATED RATHER THAN HAND-WRITTEN
--------------------------------------
Seventeen organizations with names, service areas, missions and funding status
already live in orgs.json. Hand-authoring the same content in HTML means two
copies that drift apart the first time anything changes - the problem this
project has already had to unpick once.

WHY STATIC HTML RATHER THAN RENDERED IN THE BROWSER
---------------------------------------------------
Two reasons, both hard requirements:

  Translation. WPML - the plugin the county uses - only translates content that
  exists in the WordPress page. Anything a script writes into the DOM at load
  time is invisible to it. Given how much of the Roaring Fork valley is
  Spanish-speaking, an untranslatable directory isn't acceptable.

  Accessibility. The map renders to a <canvas>, which screen readers cannot
  interpret. The directory is the text equivalent that carries the same
  information (WCAG 2.1 SC 1.1.1), so it has to be real markup present in the
  document, not assembled afterwards.

HANDOFF
-------
After the initial seed the COUNTY owns this content in WordPress - that was the
decision. So this script is a one-time generator, not an ongoing pipeline, and
orgs.json will go stale relative to the published directory. It still drives
the map's popups, which is why those are kept deliberately thin (name and
service area only) - less surface to drift.

Re-running this later would overwrite county edits. Don't, unless you've
checked with them first.

OUTPUT
------
Semantic HTML with BEM-ish classes, styled entirely from directory.css.
Deliberately not Gutenberg block markup: block syntax varies by WordPress
version and theme, and there's no WordPress instance here to verify it renders.
Converting this to blocks later is mechanical; going the other way isn't.

USAGE
-----
    python3 scripts/build_directory.py                # write directory.html
    python3 scripts/build_directory.py --wordpress      # self-contained bundle
                                                        # for one WP HTML block
"""

import argparse
import html
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ORGS = REPO / "data" / "clean" / "orgs.json"
OUT_PAGE = REPO / "directory.html"
OUT_WORDPRESS = REPO / "_working" / "directory-wordpress.html"

# Order the sections appear in, with the framing sentence for each.
#
# Local first, then state and regional, then providers, then caucuses - the
# grouping set on the program's stakeholder roster, 8/25/26. This reverses the
# outward-in order agreed on the 7/30 call: someone arriving at this
# page is far more likely to be looking for the organization working on their
# river than for a state agency, and the first section is the one that gets
# read. Broadest-first was tidier taxonomy and worse for the reader.
#
# The strings here must match the `section` values in orgs.json exactly - that
# field is what assigns an org to a section, and a mismatch silently produces
# an empty section rather than an error.
SECTIONS = [
    (
        # "Local" is load-bearing: watersheds nest, so the Crystal is a
        # sub-watershed of the Roaring Fork, which sits inside the Colorado
        # basin. Without it the heading doesn't distinguish itself from the
        # basin-scale section below.
        "Local watershed organizations",
        "Organizations working at the scale of the Roaring Fork watershed or one "
        "of its sub-watersheds - research, restoration, advocacy and regional "
        "planning.",
    ),
    (
        # Not "watershed-wide": three of the four here are basin-scale or
        # statewide, and reusing "watershed" would collide with the section
        # above. DWR is the exception - a state agency whose local jurisdiction
        # is exactly this watershed - which is why it sits under a different
        # heading here than in the map popup. The popup groups by geographic
        # extent, this groups by type of body. Both are right on their own axis.
        "Basin and statewide organizations",
        "Agencies and bodies that set water policy, administer water rights and "
        "fund projects at state or Colorado River basin scale. Their "
        "jurisdictions reach well beyond the Roaring Fork - each entry states "
        "its actual extent.",
    ),
    (
        "Water providers",
        "The districts and municipalities that deliver water, treat wastewater, "
        "or hold water rights for a defined service area. These are the "
        "organizations most likely to serve a specific address.",
    ),
]

# Caucuses are not mapped and not in orgs.json - the 7/30 call decided against
# drawing all 13, since most aren't water-themed. They appear here as a short
# closing section pointing at the county's own list.
CAUCUS_SECTION = {
    "title": "Caucuses",
    "intro": (
        "Pitkin County has 13 officially recognized caucuses - neighborhood "
        "organizations that advise the Board of County Commissioners on land "
        "use and other matters affecting their area. Two are named for the "
        "creeks they sit on and regularly engage on water issues."
    ),
    "entries": [
        (
            "Snowmass-Capitol Creek Caucus",
            "Snowmass Creek and Capitol Creek valleys",
            "Founded 1974. Works to preserve the rural character of the two "
            "valleys and has pursued projects to protect stream flows in both "
            "creeks.",
            "snowcapcaucus.org",
        ),
        (
            "Crystal River Caucus",
            "Crystal River valley",
            "Advises the county on land use and regulation within the caucus "
            "area.",
            None,
        ),
    ],
    "footer": (
        "A full list of Pitkin County caucuses and their boundaries is "
        "available from Pitkin County."
    ),
}

# Where the iframe points.
#
# The local prototype uses a relative path so it embeds the map in THIS working
# tree - otherwise you're previewing whatever is published on GitHub Pages,
# which serves from main and can be many commits behind. That bit once already.
#
# The WordPress fragment needs the absolute published URL, since it'll be
# served from the county's domain.
MAP_URL_LOCAL = "index.html"
MAP_URL_PUBLISHED = "https://chgiersch.github.io/pchr-watershed-directory/"


def esc(text):
    return html.escape(str(text), quote=True)


# Explicit "show me this one" control, emitted for every organization that has
# a shape on the map.
#
# Expanding an entry used to move the map on its own. That conflated two
# different intentions - "I want to read about this" and "I want to see where
# this is" - and meant the map jumped around while someone was simply browsing
# the text. A real button separates them, and it's the affordance a reader can
# actually see; nothing about a disclosure triangle suggests it drives a map.
#
# A <button>, not a link: it performs an action on this page rather than
# navigating anywhere, so it needs to be a button for keyboard and screen
# reader users to get the right behaviour and announcement. It degrades to
# nothing useful without JavaScript, which is why it carries no href to break.
# Emitted with the `hidden` attribute: the button only works when
# directory-map-link.js is running, and that script can die silently - a
# lower-role save stripping script tags, a missing wrapper id (incident
# 2026-09-02), a plugin change. The script reveals the buttons on successful
# init, so a dead script means no buttons rather than seventeen dead ones.
SHOW_ON_MAP = (
    '<button type="button" class="org__show" data-show-on-map hidden>'
    '<svg class="org__show-icon" viewBox="0 0 16 16" aria-hidden="true" '
    'focusable="false">'
    '<path d="M8 1.6a4.3 4.3 0 0 0-4.3 4.3c0 3.2 4.3 8.5 4.3 8.5s4.3-5.3 '
    '4.3-8.5A4.3 4.3 0 0 0 8 1.6Z" fill="none" stroke="currentColor" '
    'stroke-width="1.5" stroke-linejoin="round"/>'
    '<circle cx="8" cy="5.9" r="1.45" fill="currentColor"/>'
    "</svg>"
    "Show on map</button>"
)


def render_actions(show_on_map, website):
    """The action row at the foot of an entry: show-on-map, then the website."""
    items = []
    if show_on_map:
        items.append(SHOW_ON_MAP)
    if website:
        site = esc(website)
        items.append(
            f'<a class="org__site" href="https://{site}" rel="noopener">{site}</a>'
        )
    if not items:
        return []
    return (
        ['      <p class="org__actions">']
        + [f"        {item}" for item in items]
        + ["      </p>"]
    )


def display_name(org):
    """Compose "Full Name (ABBR)" from org_name + org_short.

    The abbreviation is appended, never baked into org_name - two rows used
    to carry it in the name field (one as the whole name, one leading), which
    made the list read inconsistently and duplicated the short code in two
    fields. Skipped where it adds nothing: when the short code is just a
    word of the name uppercased (BASALT in "Town of Basalt"), the reader
    already has it.
    """
    name = org["org_name"]
    short = org.get("org_short", "")
    if not short or short.lower() in name.lower():
        return esc(name)
    return f'{esc(name)} <span class="org__abbr">({esc(short)})</span>'


def funding_badge(value):
    """Turn the roster's free-text funding answer into a flag plus detail.

    Values look like 'No', 'Yes - rebates to homeowners', or a longer sentence.
    Anything not starting with 'no' counts as offering funding.
    """
    raw = (value or "").strip()
    offers = not raw.lower().startswith("no")
    detail = raw.split("-", 1)[1].strip() if offers and "-" in raw else ""
    return offers, detail


def render_entry(org):
    """One organization as a <details> disclosure.

    Native <details>/<summary> rather than a scripted accordion: it works with
    no JavaScript, is keyboard operable and screen-reader friendly out of the
    box, and the collapsed content stays in the DOM - which matters, because
    this text is the map's accessible equivalent and has to be reachable.

    Always visible: name, service area, mission. That's enough to answer "who
    handles water where I live" by scanning. The longer description, funding
    detail and link sit behind the disclosure, because 1,300 words of
    description shown all at once buries exactly what most people came for.
    """
    slug = esc(org["org_short"].lower())
    attrs = f' id="org-{slug}"'
    # boundary_id lets a click here find the matching shape on the map once the
    # postMessage wiring exists. Harmless as a data attribute until then.
    if org.get("boundary_id"):
        attrs += f' data-boundary="{esc(org["boundary_id"])}"'

    offers, detail = funding_badge(org.get("provides_funding"))

    # The summary wraps an <h3> rather than a plain span. The HTML spec allows
    # summary to contain a single heading element, and it matters here: screen
    # reader users navigate long pages by jumping between headings, and with 19
    # organizations a flat list of spans gives them nothing to jump to.
    #
    # The funding flag lives inside the heading because summary can hold EITHER
    # one heading or phrasing content, not a heading plus siblings. It reads as
    # "Snowmass Water and Sanitation District, offers funding", which is a
    # reasonable thing to hear.
    flag = ('<span class="org__flag">Offers funding</span>' if offers else "")

    # The extent, visible on the COLLAPSED row. Tim's county review (8/26/26)
    # made the case for this: "the state-wide orgs can't be recognized as such"
    # - because the scope only appeared after expanding. Shown as plain text
    # right of the name, so a scan down the closed list answers "how big is
    # each of these" without a single click. The words come from orgs.json's
    # `scope` field, the same one the expanded body and the map popup show -
    # one source of truth, three surfaces.
    extent = (f'<span class="org__extent">{esc(org["scope"])}</span>'
              if org.get("scope") else "")

    parts = [f'  <details class="org"{attrs}>']
    parts.append('    <summary class="org__summary">')
    parts.append(
        '      <h3 class="org__name">'
        f'<span class="org__title">{display_name(org)}{extent}</span>'
        f'{flag}</h3>'
    )
    parts.append("    </summary>")
    parts.append('    <div class="org__body">')

    if org.get("scope"):
        parts.append(
            '      <p class="org__scope">'
            f'<span class="org__label">Service area</span> {esc(org["scope"])}'
            "</p>"
        )
    if org.get("mission"):
        parts.append(f'      <p class="org__mission">{esc(org["mission"])}</p>')
    if org.get("description"):
        parts.append(f'      <p class="org__desc">{esc(org["description"])}</p>')

    # Current-year focus, from the program's stakeholder roster (8/25/26).
    # The year lives in the
    # LABEL on purpose: the content self-dates, so a reader can always judge
    # its freshness and the annual maintenance task is unambiguous - update
    # the items and the year together, or delete the field from orgs.json and
    # the section vanishes for that organization. Rendered only where the
    # roster had substance; a list for multiple items, a sentence for one.
    if org.get("priorities_2026"):
        items = org["priorities_2026"]
        if len(items) > 1:
            lis = "".join(f"\n        <li>{esc(i)}</li>" for i in items)
            parts.append(
                '      <div class="org__priorities">'
                '<span class="org__label">2026 priorities</span>'
                f'<ul>{lis}\n      </ul></div>'
            )
        else:
            parts.append(
                '      <p class="org__priorities">'
                '<span class="org__label">2026 priorities</span> '
                f'{esc(items[0])}</p>'
            )

    meta = []
    if org.get("funding_model"):
        meta.append(
            '        <div class="org__meta-item">'
            '<dt class="org__label">Funded by</dt>'
            f'<dd>{esc(org["funding_model"])}</dd></div>'
        )
    if offers:
        meta.append(
            '        <div class="org__meta-item">'
            '<dt class="org__label">Offers funding</dt>'
            f'<dd>{esc(detail) if detail else "Yes"}</dd></div>'
        )
    if meta:
        parts.append('      <dl class="org__meta">')
        parts.extend(meta)
        parts.append("      </dl>")

    parts.extend(render_actions(bool(org.get("boundary_id")), org.get("website")))

    parts.append("    </div>")
    parts.append("  </details>")
    return "\n".join(parts)


def render_caucus_entry(name, area, note, site):
    # Same collapsed-row extent as the orgs, for the same reason - and because
    # a list where some rows carry it and some don't reads as an error.
    parts = ['  <details class="org">']
    parts.append('    <summary class="org__summary">')
    parts.append(
        '      <h3 class="org__name">'
        f'<span class="org__title">{esc(name)}'
        f'<span class="org__extent">{esc(area)}</span></span></h3>'
    )
    parts.append("    </summary>")
    parts.append('    <div class="org__body">')
    parts.append(
        '      <p class="org__scope">'
        f'<span class="org__label">Area</span> {esc(area)}</p>'
    )
    parts.append(f'      <p class="org__desc">{esc(note)}</p>')
    # No show-on-map button: the caucuses aren't drawn (7/30 call).
    parts.extend(render_actions(False, site))
    parts.append("    </div>")
    parts.append("  </details>")
    return "\n".join(parts)


# Shown on the STANDALONE GitHub Pages build only - never in the WordPress
# bundle, which is the official page. Once the county's page is live, the
# Pages copy is the one people might reach out of context, and this tells
# them what they're looking at. Delete this constant (and the
# .prototype-note CSS rule) if the Pages copy is ever retired.
PROTOTYPE_NOTE = """<p class="prototype-note">
  <strong>Development copy.</strong> The official version of this page is
  published by Pitkin County Healthy Rivers at pitkincountyrivers.com.
</p>"""

# The intro sits OUTSIDE .map-panel so it scrolls away with the page while
# the panel - which holds only the iframe - pins to the top. It cannot live
# inside the sticky element: position sticky only travels within the parent,
# and a parent that is merely intro+map tall gives it nowhere to go
# (discovered the hard way on the live preview, 2026-09-02).
# One visible sentence of context; the how-to folds into a native disclosure
# beneath it. Instruction paragraphs above interactive content go unread, and
# the fold costs one line of height where the paragraph cost five - height
# the pinned map needs. Each instruction also lives where its action is
# (buttons are self-labeling; the map shows a first-click hint), so this list
# is the reference copy, not the only teacher. Native <details>: keyboard
# operable, screen-reader friendly, WPML-translatable, no script.
MAP_EMBED = """<p class="map-panel__intro" id="map-intro">
    Interactive map and directory of water management service areas in the
    Roaring Fork watershed; only organizations serving the watershed appear
    on this page.
</p>
<details class="map-help">
  <summary>How to use this page</summary>
  <ul>
    <li>Click any colored area on the map to see the organizations that
        serve it, then select one to jump to its full entry below.</li>
    <li>Press &ldquo;Show on map&rdquo; in any listing to highlight that
        organization&rsquo;s territory &ndash; statewide and basin
        organizations zoom out to their full extent within Colorado.</li>
    <li>The house button on the map returns to the Roaring Fork
        watershed view.</li>
  </ul>
</details>
<div class="map-panel">
  <iframe
    class="map-panel__frame"
    src="__MAP_URL__"
    title="Map of water management service areas in the Roaring Fork watershed"
    aria-describedby="map-intro"
    loading="lazy"></iframe>
</div>"""


def build_fragment(orgs):
    out = []
    for title, intro in SECTIONS:
        members = [o for o in orgs if o.get("section") == title]
        if not members:
            continue
        # Alphabetical within each section, as agreed - no implied ranking.
        members.sort(key=lambda o: o["org_name"].lower())
        slug = title.lower().replace(" ", "-")
        out.append(f'<section class="dir-section" aria-labelledby="{slug}">')
        out.append(f'  <h2 class="dir-section__title" id="{slug}">{esc(title)}</h2>')
        out.append(f'  <p class="dir-section__intro">{esc(intro)}</p>')
        out.append('  <div class="dir-section__list">')
        out.append("\n".join(render_entry(o) for o in members))
        out.append("  </div>")
        out.append("</section>")

    c = CAUCUS_SECTION
    out.append('<section class="dir-section" aria-labelledby="caucuses">')
    out.append(f'  <h2 class="dir-section__title" id="caucuses">{esc(c["title"])}</h2>')
    out.append(f'  <p class="dir-section__intro">{esc(c["intro"])}</p>')
    out.append('  <div class="dir-section__list">')
    out.append("\n".join(render_caucus_entry(*e) for e in c["entries"]))
    out.append("  </div>")
    out.append(f'  <p class="dir-section__note">{esc(c["footer"])}</p>')
    out.append("</section>")
    return "\n".join(out)


PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Water Management Organizations - Roaring Fork Watershed</title>
  <link href="https://fonts.googleapis.com/css2?family=Kameron:wght@600;700&family=Montserrat:wght@400;500;600&display=swap" rel="stylesheet" />
  <link rel="stylesheet" href="directory.css" />
</head>
<body>

<a class="skip-link" href="#directory">Skip to the organization directory</a>

<header class="page-header">
  <h1>Water Management Organizations</h1>
  <p>Pitkin County Healthy Rivers &middot; Roaring Fork Watershed</p>
</header>

__PROTOTYPE_NOTE__

<!-- Sticky map. The visible intro doubles as the iframe's description: it
     tells everyone - not only screen reader users - that nothing here is
     map-only, which is what makes the canvas acceptable under WCAG 2.1 AA. -->
__MAP_EMBED__

<main class="directory" id="directory">
__FRAGMENT__
</main>

<footer class="page-footer">
  <p>
    Service-area boundaries are clipped to the Roaring Fork watershed and are
    not legal boundaries. Several districts extend beyond the watershed; each
    organization's full jurisdiction is described in its entry above.
  </p>
</footer>

<!-- Optional. Links the directory to the map in both directions. Everything
     above works without it. -->
<script src="directory-map-link.js"></script>

</body>
</html>
"""


def git_version() -> str:
    """Tag or short hash of HEAD, with a -dirty suffix for uncommitted work.

    Stamped into the WordPress bundle so anyone can trace exactly what is
    deployed. Falls back to the date alone when git is unavailable.
    """
    import subprocess
    from datetime import date
    try:
        v = subprocess.run(["git", "describe", "--tags", "--always", "--dirty"],
                           capture_output=True, text=True, cwd=REPO,
                           check=True).stdout.strip()
    except Exception:
        v = "unknown"
    return f"{v}, generated {date.today().isoformat()}"


def build_wordpress_bundle(fragment: str) -> str:
    """One self-contained blob for a single CORE Custom HTML block.

    Styles and script are inlined rather than managed as separate WordPress
    pieces (Additional CSS, an enhanced block plugin's CSS/JS tabs) so the
    page has zero dependencies beyond WordPress core. Core blocks survive
    theme swaps and plugin removals; per-plugin storage does not. The whole
    update procedure becomes: regenerate, select all, paste over the block.
    """
    css = (REPO / "directory.css").read_text()
    js = (REPO / "directory-map-link.js").read_text()

    # A literal closing tag inside the inlined JS or CSS would terminate the
    # wrapper element early and truncate the page. Neither file has one; this
    # guards against that changing.
    for token, name in (("</script", "directory-map-link.js"),
                        ("</style", "directory.css")):
        if token.lower() in js.lower() or token.lower() in css.lower():
            raise SystemExit(f"'{token}' found in {name} - it would break the "
                             "inline bundle. Restructure before regenerating.")

    header = f"""<!--
  Pitkin County Healthy Rivers - Water Management Directory
  GENERATED PAGE - {git_version()}
  Source: https://github.com/chgiersch/pchr-watershed-directory

  Maintainer notes:
  - Do not hand-edit this block. Content is generated from the repository
    above (scripts/build_directory.py --wordpress); regenerate and paste the
    whole block to update.
  - Edit this page with the WordPress editor only. Opening it in Cornerstone
    and saving will overwrite this block.
  - Only an Administrator should edit and save this page. WordPress strips
    <script> tags on save for lower roles, which silently disables the
    map/directory linking.
-->"""

    embed = MAP_EMBED.replace("__MAP_URL__", MAP_URL_PUBLISHED)
    # The id="directory" wrapper is REQUIRED, not decorative: the link script
    # locates the directory by that id and exits silently if it is absent.
    # Its omission from the first bundle disabled both directions of the
    # map/directory link on the live preview (2026-09-02) while every message
    # still arrived - the hardest kind of failure to see. The class carries
    # the directory's typography and layout.
    return (f"{header}\n<style>\n{css}</style>\n\n"
            f"{embed}\n\n"
            f'<div id="directory" class="directory">\n{fragment}\n</div>\n\n'
            f"<script>\n{js}</script>\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--wordpress", action="store_true",
                    help="write the self-contained WordPress bundle "
                         "(styles + markup + script in one block)")
    args = ap.parse_args()

    orgs = json.loads(ORGS.read_text())
    fragment = build_fragment(orgs)

    if args.wordpress:
        bundle = build_wordpress_bundle(fragment)
        OUT_WORDPRESS.parent.mkdir(parents=True, exist_ok=True)
        OUT_WORDPRESS.write_text(bundle)
        print(f"Wrote {OUT_WORDPRESS.relative_to(REPO)} ({len(bundle):,} chars)")
        print(f"  iframe points at {MAP_URL_PUBLISHED}")
        print("  Paste the ENTIRE file into one core Custom HTML block.")
        print("  That URL serves from main - make sure main is current first.")
        if "-dirty" in bundle.splitlines()[2]:
            print("  WARNING: built from uncommitted changes (version is -dirty).")
        return

    page = (PAGE
            .replace("__FRAGMENT__", fragment)
            .replace("__PROTOTYPE_NOTE__", PROTOTYPE_NOTE)
            .replace("__MAP_EMBED__", MAP_EMBED.replace("__MAP_URL__", MAP_URL_LOCAL)))
    OUT_PAGE.write_text(page)

    counts = {}
    for o in orgs:
        counts[o.get("section", "?")] = counts.get(o.get("section", "?"), 0) + 1
    print(f"Wrote {OUT_PAGE.relative_to(REPO)}")
    for title, _ in SECTIONS:
        print(f"  {title:32} {counts.get(title, 0)}")
    print(f"  {'Caucuses':32} {len(CAUCUS_SECTION['entries'])}")


if __name__ == "__main__":
    main()
