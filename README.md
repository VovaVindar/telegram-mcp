# telegram-mcp

Telegram [MCP](https://modelcontextprotocol.io) server that gives AI agents full access to your chats, channels, and groups. Works with any MCP-compatible client ([Claude Code](https://docs.anthropic.com/en/docs/claude-code), [Cursor](https://cursor.com), etc.). Built with [Telethon](https://github.com/LonamiWebs/Telethon).

Read messages, send replies, and organize your Telegram: auto-categorize channels into folders, mute noisy chats, archive stale ones, and clean up subscriptions. See [AGENTS.md](AGENTS.md) for ready-to-use workflows.

## What can it do?

**Read** - list chats/channels/groups, fetch and search messages, get chat details

**Write** - send, edit, delete, and forward messages, pin/unpin, mark as read

**Organize** - archive/unarchive, mute/unmute, create and manage chat folders

## AI Workflows

The tools are designed to work together for multi-step organization tasks. [AGENTS.md](AGENTS.md) includes ready-to-use workflows:

- **Auto-organize channels into folders** - fetch all channels, sample recent messages to infer topics, group into themed folders
- **Identify cleanup candidates** - find inactive or high-unread channels, suggest archive/mute/unsubscribe
- **Triage unread messages** - summarize what's important across chats, bulk mark-read the rest
- **Reorganize existing folders** - audit folder structure, find uncategorized chats, restructure

## Setup

### 1. Get Telegram API credentials

Go to [my.telegram.org/apps](https://my.telegram.org/apps) and create an application. You'll get an `API_ID` and `API_HASH`.

### 2. Install

```bash
git clone https://github.com/VovaVindar/telegram-mcp.git
cd telegram-mcp
python3 -m venv .venv
.venv/bin/pip install -e .
```

### 3. Configure

```bash
cp .env.example .env
# Edit .env with your API_ID and API_HASH
```

### 4. Authenticate

```bash
.venv/bin/python3 telegram_mcp_server.py
```

Scan the QR code with your Telegram app (Settings > Devices > Link Desktop Device). This creates a `telegram.session` file that stores your auth state.

### 5. Connect to Claude Code

The `.mcp.json` file registers the server automatically. Just open Claude Code in this directory and the tools will be available.

To use it from any directory, add this to your `~/.claude/claude_code_config.json`:

```json
{
  "mcpServers": {
    "telegram-mcp": {
      "command": "/absolute/path/to/telegram-mcp/.venv/bin/fastmcp",
      "args": ["run", "/absolute/path/to/telegram-mcp/telegram_mcp_server.py"]
    }
  }
}
```

## Available Tools

| Tool | Description |
|------|-------------|
| `list_dialogs` | List chats/channels/groups with optional filter |
| `get_messages` | Fetch messages (use `"me"` for Saved Messages) |
| `search_messages` | Search messages by text, optionally within a chat |
| `get_chat_info` | Get details about a chat or user |
| `send_message` | Send a message (supports reply) |
| `edit_message` | Edit an existing message |
| `delete_messages` | Delete messages by ID |
| `forward_messages` | Forward messages between chats |
| `archive_chat` | Archive a chat |
| `unarchive_chat` | Unarchive a chat |
| `pin_message` | Pin a message in a chat |
| `unpin_message` | Unpin a message |
| `mark_read` | Mark all messages in a chat as read |
| `mute_chat` | Mute a chat (optionally for N hours) |
| `unmute_chat` | Unmute a chat |
| `list_folders` | List all chat folders |
| `create_folder` | Create a new folder with specified chats |
| `update_folder` | Rename or modify folder chats |
| `delete_folder` | Delete a folder |

## Tips

- Use `chat_id="me"` to target Saved Messages
- Paginate with `offset_id`: pass the last message ID from the previous batch
- Folder names are limited to 12 characters by Telegram

## License

[MIT](LICENSE)
