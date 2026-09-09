/* Links the organization directory to the embedded map.
 *
 * The map lives in an iframe on a different origin, so the only channel
 * between them is window.postMessage. This script is the page's half of that
 * conversation. It is entirely optional - with JavaScript disabled or this
 * file absent, the directory still works as a directory and the map still
 * works as a map. They just stop talking to each other.
 *
 * DEPLOYMENT
 *   The WordPress bundle (scripts/build_directory.py --wordpress) inlines
 *   this file automatically - edit here and regenerate, never in the page.
 *   The standalone GitHub Pages build loads it as a separate script. If the
 *   map is ever served from a new origin, update MAP_ORIGIN below AND the
 *   ALLOWED_ORIGINS list in the map's own index.html - both ends check.
 *
 * BEHAVIOUR
 *   "Show on map" in an entry   ->  map frames and highlights that area
 *   Picking an org in a map popup ->  entry opens and scrolls into view
 *
 * SECURITY
 *   Every message is checked against MAP_ORIGIN in both directions, and the
 *   sender must be the map frame's own window. Accepting messages from any
 *   origin would let any page that can reach this one drive the directory;
 *   posting to '*' would broadcast to whatever happens to be loaded in the
 *   frame. Neither is acceptable on a government site.
 *
 *   How the map learns where to reply: this script posts pchr:hello into the
 *   frame, and the map answers only that window at that origin. The map used
 *   to read document.referrer instead, which any Referrer-Policy stricter
 *   than the browser default silently blanks – the county could have hardened
 *   its headers and lost the map->directory half without an error anywhere.
 */
(function () {
  'use strict';

  // Where the map is served from. Must match exactly - scheme, host and port,
  // no trailing slash.
  var MAP_ORIGIN = 'https://chgiersch.github.io';

  var frame = document.querySelector('.map-panel__frame');
  var directory = document.getElementById('directory');
  if (!frame || !directory) return;

  // Reveal the "Show on map" buttons - they are emitted hidden and only
  // useful once this script's handlers exist. Reaching this line proves the
  // guards above passed; a script that never runs leaves no dead controls.
  directory.querySelectorAll('[data-show-on-map]').forEach(function (b) {
    b.removeAttribute('hidden');
  });

  // Local development only. scripts/serve.py serves the directory and the map
  // from one loopback origin, and the cross-origin rehearsal in README.md
  // serves them from two (localhost vs 127.0.0.1), so on loopback the map's
  // origin is read from the iframe. The outer gate is THIS page's hostname:
  // on the county site it is never loopback, so the block is inert there.
  //
  // That gate is the whole point. The earlier version trusted the iframe src
  // whenever it matched the page's origin, and a lazy-load plugin swaps the
  // src for a same-origin placeholder before this script runs – which would
  // have retargeted MAP_ORIGIN at the county's own origin (review finding 3,
  // 2026-09-05). check.py asserts the src read stays inside this gate.
  var LOOPBACK_HOSTS = ['localhost', '127.0.0.1', '[::1]'];
  function isLoopback(hostname) {
    return LOOPBACK_HOSTS.indexOf(hostname) !== -1;
  }
  if (isLoopback(window.location.hostname)) {
    try {
      var src = new URL(frame.getAttribute('src'), window.location.href);
      if (isLoopback(src.hostname)) MAP_ORIGIN = src.origin;
    } catch (e) { /* unparseable src – keep the published origin */ }
  }

  function entryFor(boundaryId) {
    return directory.querySelector('[data-boundary="' + CSS.escape(boundaryId) + '"]');
  }

  function send(payload) {
    if (!frame.contentWindow) return;
    frame.contentWindow.postMessage(payload, MAP_ORIGIN);
  }

  // Introduce this page to the map. The map replies only to the window and
  // origin it hears this from, so nothing flows map->directory until a hello
  // lands. Sent twice because either timing alone can miss: immediately, for
  // a map that finished loading before this script ran (cached, or the
  // script placed low on the page – the frame's load event has already fired
  // and will not fire again), and on the load event, for a map still loading
  // now. A hello posted before the map's listener exists is dropped by the
  // browser; a duplicate reaching a map that already knows us is answered
  // again with the same ready message, which is harmless.
  function hello() {
    send({ type: 'pchr:hello' });
  }
  hello();
  frame.addEventListener('load', hello);

  /* ---- Directory -> map ---------------------------------------------- */

  // An explicit button, not the disclosure toggle. Expanding an entry means
  // "I want to read this"; it shouldn't also move the map out from under
  // someone who is just browsing. One control, one intention.
  //
  // Delegated from the directory root so entries added or reordered later in
  // WordPress keep working without rebinding anything.
  directory.addEventListener('click', function (ev) {
    var btn = ev.target.closest('[data-show-on-map]');
    if (!btn) return;

    var entry = btn.closest('details.org');
    if (!entry) return;

    var boundaryId = entry.getAttribute('data-boundary');
    if (!boundaryId) return;   // caucuses and orgs with no mapped shape

    // Seven organizations share the watershed boundary, and the map labels it
    // differently depending on whether the one you picked operates beyond the
    // watershed - so it needs to know which, not just the shape.
    var orgShort = (entry.id || '').replace(/^org-/, '').toUpperCase();
    send({ type: 'pchr:focus', boundaryId: boundaryId, orgShort: orgShort });
    markSelected(entry);

    // On a narrow screen the map isn't sticky, so it may be scrolled well off
    // the top - pressing the button would appear to do nothing at all. Bring
    // it back into view. On desktop it's already pinned, so leave the scroll
    // position alone.
    var panel = document.querySelector('.map-panel');
    if (panel && window.getComputedStyle(panel).position !== 'sticky') {
      panel.scrollIntoView({
        block: 'start',
        behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches
          ? 'auto' : 'smooth'
      });
    }
  });

  /* ---- Map -> directory ---------------------------------------------- */

  window.addEventListener('message', function (ev) {
    // Origin alone does not identify the sender: any frame this page embeds
    // from the map's origin could post here. The map frame's own window is
    // the only legitimate partner (review finding 23).
    if (ev.origin !== MAP_ORIGIN || ev.source !== frame.contentWindow) return;
    var msg = ev.data;
    if (!msg || typeof msg !== 'object') return;

    // A shape was clicked on the map. Mark the matching entry so it's already
    // highlighted when the reader gets there - but do NOT scroll. Clicking
    // around the map shouldn't drag the page about underneath; scrolling is
    // reserved for the explicit request below.
    if (msg.type === 'pchr:selected' && msg.boundaryId) {
      var entry = entryFor(msg.boundaryId);
      if (!entry) return;
      markSelected(entry);
      return;
    }

    // Someone picked an organization inside the map popup. That IS an explicit
    // "take me to this one", so open it and scroll.
    if (msg.type === 'pchr:showOrg' && msg.orgShort) {
      var target = document.getElementById('org-' + String(msg.orgShort).toLowerCase());
      if (!target) return;

      target.open = true;
      markSelected(target);

      // Expand first, then scroll - and measure after the browser has laid the
      // expanded entry out, or the position is computed against the collapsed
      // height and lands short.
      //
      // scrollIntoView can't be used here: the map panel is sticky, so it sits
      // over the top of the page and would cover the entry title. The offset
      // below puts the title just clear of it.
      window.requestAnimationFrame(function () {
        // The sticky element is .map-panel, which holds only the iframe.
        // Its height is how much of the viewport the pinned map covers, and
        // the scroll target must clear it.
        var panel = document.querySelector('.map-panel');
        var overlap = 0;
        if (panel && window.getComputedStyle(panel).position === 'sticky') {
          overlap = panel.getBoundingClientRect().height;
        }
        var top = window.scrollY + target.getBoundingClientRect().top - overlap - 12;
        window.scrollTo({
          top: Math.max(top, 0),
          behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches
            ? 'auto' : 'smooth'
        });

        // Move focus to the entry so keyboard and screen reader users land
        // where the scroll just went, instead of being left behind.
        //
        // Quiet-focus dance: the originating click happened in the IFRAME's
        // document, so the host document has no recent pointer activity and
        // the browser's :focus-visible heuristic treats this programmatic
        // focus as keyboard-like - painting a focus ring at a mouse user.
        // The temporary class suppresses that one ring; the first real
        // keyboard press (or leaving the element) removes the class, so a
        // keyboard user's ring returns immediately - required by WCAG 2.4.7.
        var summary = target.querySelector('summary');
        if (summary) {
          summary.classList.add('org__summary--map-focus');
          summary.focus({ preventScroll: true });
          var restore = function () {
            summary.classList.remove('org__summary--map-focus');
          };
          summary.addEventListener('blur', restore, { once: true });
          summary.addEventListener('keydown', restore, { once: true });
        }
      });
    }
  });

  function markSelected(entry) {
    directory.querySelectorAll('.org.is-selected').forEach(function (el) {
      el.classList.remove('is-selected');
    });
    entry.classList.add('is-selected');
  }
})();
