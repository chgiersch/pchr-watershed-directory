/* Links the organization directory to the embedded map.
 *
 * The map lives in an iframe on a different origin, so the only channel
 * between them is window.postMessage. This script is the page's half of that
 * conversation. It is entirely optional - with JavaScript disabled or this
 * file absent, the directory still works as a directory and the map still
 * works as a map. They just stop talking to each other.
 *
 * TO USE IN WORDPRESS
 *   Enqueue this file, or paste it into a script block on the page. Set
 *   MAP_ORIGIN below to wherever the map is actually served from.
 *
 * BEHAVIOUR
 *   "Show on map" in an entry   ->  map frames and highlights that area
 *   Picking an org in a map popup ->  entry opens and scrolls into view
 *
 * SECURITY
 *   Every message is checked against MAP_ORIGIN in both directions. Accepting
 *   messages from any origin would let any page that can reach this one drive
 *   the directory; posting to '*' would broadcast to whatever happens to be
 *   loaded in the frame. Neither is acceptable on a government site.
 */
(function () {
  'use strict';

  // Where the map is served from. Must match exactly - scheme, host and port,
  // no trailing slash.
  var MAP_ORIGIN = 'https://chgiersch.github.io';

  var frame = document.querySelector('.map-panel__frame');
  var directory = document.getElementById('directory');
  if (!frame || !directory) return;

  // Allow the map to be served from the same origin as the page during local
  // development, without having to edit MAP_ORIGIN.
  try {
    var src = new URL(frame.getAttribute('src'), window.location.href);
    if (src.origin === window.location.origin) MAP_ORIGIN = src.origin;
  } catch (e) { /* leave the configured value */ }

  function entryFor(boundaryId) {
    return directory.querySelector('[data-boundary="' + CSS.escape(boundaryId) + '"]');
  }

  function send(payload) {
    if (!frame.contentWindow) return;
    frame.contentWindow.postMessage(payload, MAP_ORIGIN);
  }

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
    if (ev.origin !== MAP_ORIGIN) return;
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
        var summary = target.querySelector('summary');
        if (summary) summary.focus({ preventScroll: true });
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
