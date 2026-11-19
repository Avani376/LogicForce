"""Vercel serverless entry point for the FastAPI app (single-origin mode).

Serves both the API routes and the built frontend from one function.
Vercel's Python runtime imports this module and wraps the ASGI app.
"""

import os
import sys

# Add the repo-relative engine package roots so the engines are importable.
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _engine in ("logic", "sequential", "verify", "faults", "repair", "optimize",
                "cpu8086", "cosim", "numsys", "boolean", "pic8259", "curriculum"):
    _p = os.path.join(_ROOT, "engines", _engine)
    if _p not in sys.path:
        sys.path.insert(0, _p)

_api_dir = os.path.join(_ROOT, "apps", "api")
if _api_dir not in sys.path:
    sys.path.insert(0, _api_dir)

# Now the FastAPI app is importable.
from logicforge_api.main import app  # noqa: E402

# Vercel ASGI entry point.
application = app
