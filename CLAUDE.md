# Telegram MCP Server

Telegram MCP server that lets AI agents read, write, and organize Telegram via Telethon.

See [AGENTS.md](AGENTS.md) for architecture, tool reference, AI workflows, and development notes.

## Setup

1. Create `.env` with `TELEGRAM_API_ID` and `TELEGRAM_API_HASH` from https://my.telegram.org/apps
2. Create venv and install deps: `python3 -m venv .venv && .venv/bin/pip install -e .`
3. Authenticate: `.venv/bin/python3 telegram_mcp_server.py` (QR code recommended)
4. The `.mcp.json` registers the server with Claude Code automatically
