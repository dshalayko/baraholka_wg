import os

import uvicorn


def main() -> None:
    reload_enabled = os.getenv("UVICORN_RELOAD", "false").lower() in {"1", "true", "yes"}
    uvicorn.run("webserver.app:app", host="0.0.0.0", port=8001, reload=reload_enabled)


if __name__ == "__main__":
    main()
