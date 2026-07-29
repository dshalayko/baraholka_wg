"""Import target for `run_debug.py --reload`.

uvicorn's reloader needs an import string rather than an app object, so it
re-imports this module in each worker process.
"""

import os

from devmode import server

app = server.build_app(
    int(os.getenv("DEVMODE_PORT", "8002")),
    os.getenv("DEVMODE_LOG_LEVEL", "INFO"),
)
