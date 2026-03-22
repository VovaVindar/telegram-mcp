# Telegram MCP Server

Lightweight MCP server that gives Claude Code read and write access to Telegram via Telethon.

## Setup

1. Create `.env` with `TELEGRAM_API_ID` and `TELEGRAM_API_HASH` from https://my.telegram.org/apps
2. Create venv and install deps: `python3 -m venv .venv && .venv/bin/pip install -e .`
3. Authenticate: `.venv/bin/python3 telegram_mcp_server.py` (QR code recommended)
4. The `.mcp.json` registers the server with Claude Code automatically

## Architecture

Single-file server (`telegram_mcp_server.py`) using FastMCP + Telethon.

- `ensure_connected()` — lazy-connects and checks auth on every tool call
- Session file (`telegram.session`) stores auth state, created during interactive login
- `.env` holds API credentials, loaded via python-dotenv

## Available MCP Tools

- `list_dialogs(limit, filter)` — list chats/channels/groups
- `get_messages(chat_id, limit, offset_id)` — fetch messages (use `"me"` for saved messages)
- `search_messages(query, chat_id, limit)` — search by text
- `get_chat_info(chat_id)` — get chat/user details
- `send_message(chat_id, text, reply_to_msg_id)` — send a message
- `edit_message(chat_id, message_id, new_text)` — edit a message
- `delete_messages(chat_id, message_ids)` — delete messages
- `forward_messages(from_chat_id, to_chat_id, message_ids)` — forward messages
- `archive_chat(chat_id)` — archive a chat
- `unarchive_chat(chat_id)` — unarchive a chat
- `pin_message(chat_id, message_id)` — pin a message
- `unpin_message(chat_id, message_id)` — unpin a message
- `mark_read(chat_id)` — mark all messages as read
- `mute_chat(chat_id, hours)` — mute a chat (omit hours for forever)
- `unmute_chat(chat_id)` — unmute a chat

## Key Details

- `chat_id="me"` targets Saved Messages
- Paginate with `offset_id` (pass last message ID from previous batch)
- Telethon is archived (Feb 2026) but functional; monitor for alternatives