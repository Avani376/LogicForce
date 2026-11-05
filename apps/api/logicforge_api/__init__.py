"""LogicForge API — thin HTTP boundary over the deterministic engines.

Pure engines compute; this package only translates JSON ⇄ engine calls and maps
typed engine errors onto HTTP responses. No business logic lives here.
"""

API_VERSION = "1"
