#!/usr/bin/env python
"""Run the Mini App locally, in a plain browser, with test data.

    python run_debug.py                 # http://localhost:8002
    python run_debug.py --reset         # wipe + reseed the debug data first
    python run_debug.py --port 8100     # another port
    python run_debug.py --reload        # uvicorn autoreload

What debug mode changes (see devmode/env.py and devmode/fake_telegram.py):

  * Auth is NOT bypassed. The page is served with a stubbed
    window.Telegram.WebApp whose initData is signed with the debug bot token,
    so webserver/auth.py verifies it through its normal HMAC path.
  * Telegram is faked. Channel posts, DMs, edits and deletions are recorded
    instead of sent, and shown at /__debug__/channel.
  * Data is isolated. DB_PATH points at data/debug/debug.db and BOT_TOKEN at a
    bot that does not exist, so the real database, channel and bot are
    untouched even if a call slips past the fakes.

Switch test user, jump to a bid screen, or reseed from the 🐞 toolbar in the
top-left corner of the app.
"""

import argparse
import asyncio
import os
import sys


def main() -> int:
    # PORT lets a launcher assign a free port (the debug URLs, including the bid
    # links, are built from whatever port we end up on).
    default_port = int(os.environ.get("PORT") or 8002)

    parser = argparse.ArgumentParser(description="Run the Mini App in debug mode with test data.")
    parser.add_argument("--port", type=int, default=default_port, help="HTTP port (default: $PORT or 8002)")
    parser.add_argument("--host", default="127.0.0.1", help="bind address (default: 127.0.0.1)")
    parser.add_argument("--reset", action="store_true", help="wipe and reseed the debug data before starting")
    parser.add_argument("--reload", action="store_true", help="restart on source changes")
    parser.add_argument("--log-level", default="INFO", help="app log level (default: INFO)")
    parser.add_argument("--seed-only", action="store_true", help="reseed the debug data and exit")
    args = parser.parse_args()

    import uvicorn

    from devmode import env, server

    if args.reset or args.seed_only:
        env.apply(args.port, args.log_level)
        server._patch_telegram()
        asyncio.run(server.reset_debug_data())
        if args.seed_only:
            return 0

    app = server.build_app(args.port, args.log_level)
    base_url = f"http://localhost:{args.port}"

    print()
    print("  ┌─ DEBUG MODE ──────────────────────────────────────────")
    print(f"  │  Mini App          {base_url}/")
    print(f"  │  Виртуальный TG    {base_url}/__debug__/channel")
    print(f"  │  Другой юзер       {base_url}/?as=bidder   (owner | bidder | noname)")
    print(f"  │  Экран ставки      {base_url}/?bid=7")
    print("  │")
    print("  │  Реальные бот, канал и база НЕ используются.")
    print("  └───────────────────────────────────────────────────────")
    print()

    if args.reload:
        # Reload needs an import string, so re-enter through devmode.asgi.
        os.environ["DEVMODE_PORT"] = str(args.port)
        os.environ["DEVMODE_LOG_LEVEL"] = args.log_level
        uvicorn.run("devmode.asgi:app", host=args.host, port=args.port, reload=True)
    else:
        uvicorn.run(app, host=args.host, port=args.port, log_level=args.log_level.lower())
    return 0


if __name__ == "__main__":
    sys.exit(main())
