# AGENTS.md

This file describes how AI agents can use telegram-mcp to organize and manage a user's Telegram account. Any AI model or agent framework that discovers this file can use these workflows.

## Server Overview

telegram-mcp is an MCP (Model Context Protocol) server that provides 19 tools for reading, writing, and organizing Telegram chats, channels, and groups. It connects via Telethon (user account, not bot API), so it has full access to everything the user can see.

## Agent Workflows

### 1. Auto-organize channels into folders

The primary workflow. Analyze all channel subscriptions and create themed folders.

**Steps:**
1. Call `list_dialogs(filter="channels", limit=200)` to get all channels with IDs, names, and unread counts.
2. For each channel, call `get_chat_info(chat_id)` and `get_messages(chat_id, limit=5)` in parallel to get metadata and sample recent content.
3. Analyze channel names, descriptions, and message content to infer topics.
4. Group channels into 5-10 thematic folders (e.g., "Coding", "Design", "News", "Personal").
5. Present the plan to the user as a table before making changes.
6. On confirmation, call `create_folder(name, chat_ids)` for each folder **sequentially** (parallel calls will cause ID collisions).

**Constraints:**
- Folder names are limited to 12 characters.
- Telegram allows up to 10 custom folders.
- Create folders one at a time, not in parallel.

### 2. Identify cleanup candidates

Find channels worth unsubscribing from or archiving.

**Steps:**
1. Call `list_dialogs(filter="channels", limit=200)`.
2. Flag channels where `last_message_date` is older than 6 months (inactive/dead).
3. Flag channels with very high `unread_count` (500+) as potentially abandoned by the user.
4. For flagged channels, call `get_messages(chat_id, limit=3)` to check if the channel announced it's shutting down or migrating.
5. Present results as a table with channel name, last active date, unread count, and recommendation (archive, mute, or unsubscribe).
6. On confirmation, call `archive_chat` or `mute_chat` as requested. Note: there is no `leave_chat` tool, so the user must unsubscribe manually.

### 3. Triage unread messages

Help the user catch up on unread messages across chats.

**Steps:**
1. Call `list_dialogs(limit=50)` to get chats sorted by recent activity with unread counts.
2. For chats with high unread counts, call `get_messages(chat_id, limit=20)` to summarize recent conversation.
3. Present a prioritized summary: what's important, what can be skipped.
4. Offer to `mark_read(chat_id)` for chats the user wants to dismiss.

### 4. Bulk mute/archive

Quiet down noisy chats in bulk.

**Steps:**
1. Call `list_dialogs(limit=100)` to get all recent chats.
2. Identify chats with high message volume (high unread counts, frequent `last_message_date`).
3. Present candidates for muting or archiving.
4. On confirmation, call `mute_chat(chat_id, hours)` or `archive_chat(chat_id)` for each.

### 5. Reorganize existing folders

Audit and restructure existing folder organization.

**Steps:**
1. Call `list_folders()` to get current folder structure with included chat IDs.
2. Call `list_dialogs(limit=200)` to get all chats.
3. Identify chats not in any folder, chats that might fit better in a different folder, or folders that are too large/small.
4. Present reorganization plan.
5. On confirmation, use `update_folder(folder_id, add_chat_ids, remove_chat_ids)` to move chats between folders, or `create_folder`/`delete_folder` as needed.

## Tool Reference

### Read tools
- `list_dialogs(limit, filter)` - filter options: "all", "channels", "groups", "dms"
- `get_messages(chat_id, limit, offset_id)` - use `chat_id="me"` for Saved Messages, paginate with `offset_id`
- `search_messages(query, chat_id, limit)` - omit `chat_id` for global search
- `get_chat_info(chat_id)` - note: `member_count` and `about` may not be available for all channels

### Write tools
- `send_message(chat_id, text, reply_to_msg_id)`
- `edit_message(chat_id, message_id, new_text)`
- `delete_messages(chat_id, message_ids)`
- `forward_messages(from_chat_id, to_chat_id, message_ids)`

### Organize tools
- `archive_chat(chat_id)` / `unarchive_chat(chat_id)`
- `pin_message(chat_id, message_id)` / `unpin_message(chat_id, message_id)`
- `mark_read(chat_id)`
- `mute_chat(chat_id, hours)` / `unmute_chat(chat_id)` - omit `hours` to mute permanently
- `list_folders()` / `create_folder(name, chat_ids)` / `update_folder(folder_id, name, add_chat_ids, remove_chat_ids)` / `delete_folder(folder_id)`

## Important Notes

- Always present a plan and ask for user confirmation before making changes.
- Create folders sequentially, never in parallel.
- Folder names max 12 characters.
- No `leave_chat` tool exists. Users must manually unsubscribe from channels.
- Use parallel agent calls when fetching info for many channels (batch into groups of 10-15).
- `get_chat_info` may not return `member_count` or `about` for channels where the user is not an admin.
