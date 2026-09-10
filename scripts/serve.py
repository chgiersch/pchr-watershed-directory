#!/usr/bin/env python3
"""
Local dev server. Run from the repo root:

    python3 scripts/serve.py          # serves on port 8000
    python3 scripts/serve.py 8001     # if you must - but see the port warning

This exists because plain servers have burned this project twice over:

  RANGE REQUESTS - the PMTiles basemap is read by HTTP byte-range requests,
  and python3 -m http.server ignores Range headers: it answers 200 with the
  whole 17 MB archive, the PMTiles client hangs up, and the server logs a
  BrokenPipeError that looks like a bug in this project.

  CACHING - with no Cache-Control header, Chrome caches served files and, in
  particular, keeps serving a STALE index.html inside the directory page's
  iframe even after a hard reload of the parent (hard reload refreshes the
  page's own resources, not necessarily a frame's document). The symptom is
  maddening: the directory shows new code, the map runs old code, and the
  postMessage link between them silently dies (8/27/26). no-store makes the
  browser fetch from disk every time, which is exactly right for development.

Port 8000 specifically: index.html validates postMessage origins against an
allowlist that includes only localhost:8000 and 127.0.0.1:8000. On another
port everything renders and the map/directory link silently does nothing.
"""

import sys
from http.server import ThreadingHTTPServer

try:
    from RangeHTTPServer import RangeRequestHandler
except ImportError:
    sys.exit("RangeHTTPServer is not installed. Run: pip install -r requirements.txt")


class DevHandler(RangeRequestHandler):
    """Range support from RangeHTTPServer, plus no-store on every response."""

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    if port != 8000:
        print(f"WARNING: port {port} is not in the map's postMessage origin "
              "allowlist - the map/directory link will not work.")
    print(f"Serving on http://localhost:{port} (Range: yes, caching: disabled)")
    ThreadingHTTPServer(("", port), DevHandler).serve_forever()
