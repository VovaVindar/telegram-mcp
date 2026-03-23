# Telegram MCP Server

MCP server that lets Claude Code read, write, and organize Telegram via Telethon.

## Setup

1. Create `.env` with `TELEGRAM_API_ID` and `TELEGRAM_API_HASH` from https://my.telegram.org/apps
2. Create venv and install deps: `python3 -m venv .venv && .venv/bin/pip install -e .`
3. Authenticate: `.venv/bin/python3 telegram_mcp_server.py` (QR code recommended)
4. The `.mcp.json` registers the server with Claude Code automatically

## Architecture

Single-file server (`telegram_mcp_server.py`) using FastMCP + Telethon.

- `ensure_connected()` lazy-connects and checks auth on every tool call
- Session file (`telegram.session`) stores auth state, created during interactive login
- `.env` holds API credentials, loaded via python-dotenv

## Available MCP Tools

**Read**
- `list_dialogs(limit, filter)` - list chats/channels/groups
- `get_messages(chat_id, limit, offset_id)` - fetch messages (use `"me"` for saved messages)
- `search_messages(query, chat_id, limit)` - search by text
- `get_chat_info(chat_id)` - get chat/user details

**Write**
- `send_message(chat_id, text, reply_to_msg_id)` - send a message
- `edit_message(chat_id, message_id, new_text)` - edit a message
- `delete_messages(chat_id, message_ids)` - delete messages
- `forward_messages(from_chat_id, to_chat_id, message_ids)` - forward messages

**Organize**
- `archive_chat(chat_id)` / `unarchive_chat(chat_id)` - archive/unarchive a chat
- `pin_message(chat_id, message_id)` / `unpin_message(chat_id, message_id)` - pin/unpin
- `mark_read(chat_id)` - mark all messages as read
- `mute_chat(chat_id, hours)` / `unmute_chat(chat_id)` - mute/unmute (omit hours for forever)
- `list_folders()` - list all chat folders
- `create_folder(name, chat_ids)` - create a new folder with chats
- `update_folder(folder_id, name, add_chat_ids, remove_chat_ids)` - rename or modify folder chats
- `delete_folder(folder_id)` - delete a folder

## AI Organizer Workflows

See [AGENTS.md](AGENTS.md) for full workflow descriptions. Key ones:

1. **Auto-organize channels into folders**: Fetch all channels, sample recent messages, infer topics, group into themed folders.
2. **Cleanup candidates**: Find inactive (6+ months) or high-unread channels, suggest archive/mute/unsubscribe.
3. **Triage unread**: Summarize unread messages across chats, help user catch up, bulk mark-read.
4. **Reorganize folders**: Audit existing folders, find uncategorized chats, suggest restructuring.

## Key Details

- `chat_id="me"` targets Saved Messages
- Paginate with `offset_id` (pass last message ID from previous batch)
- Telethon is archived (Feb 2026) but functional; monitor for alternatives
- Telegram folder names have a **12-character limit**
- `DialogFilter.title` requires `TextWithEntities(text=name, entities=[])` in Telethon 1.42+ (TL layer change from plain string)
- `get_chat_info` does not return `member_count` or `about`/description for most channels (only available to admins)
- No `leave_chat`/unsubscribe tool exists, users must leave channels manually
- When creating multiple folders, do it **sequentially** (parallel calls to `create_folder` will compute the same `new_id` and collide)
