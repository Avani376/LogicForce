"""Suite-wide fixtures.

The integration tests make many requests from one address; the production rate
limiter would 429 them, so this conftest disables it for the suite. The rate
limiter itself is exercised separately in tests/integration/test_api_hardening.py
with a dedicated app instance.
"""

import os

os.environ["LOGICFORGE_RATE_LIMIT"] = "off"
