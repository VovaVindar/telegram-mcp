import os
import logging
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated

from dotenv import load_dotenv
from fastmcp import FastMCP
from pydantic import Field
from telethon import TelegramClient
from telethon.tl.functions.account import UpdateNotifySettingsRequest
from telethon.tl.functions.messages import (
    GetDialogFiltersRequest,
    UpdateDialogFilterRequest,
)
from telethon.tl.types import Channel, Chat, DialogFilter, InputPeerNotifySettings, TextWithEntities, User
from telethon.utils import get_peer_id

# Load .env from the same directory as this script
load_dotenv(Path(__file__).parent / ".env")

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

API_ID = int(os.environ["TELEGRAM_API_ID"])
API_HASH = os.environ["TELEGRAM_API_HASH"]
SESSION_PATH = str(Path(__file__).parent / "telegram")

mcp = FastMCP("Telegram")

# Set WAL mode on the session database to prevent stale journal locks
_session_db = SESSION_PATH + ".session"
if Path(_session_db).exists():
    with sqlite3.connect(_session_db) as _conn:
        _conn.execute("PRAGMA journal_mode=WAL")
    del _conn

tg = TelegramClient(SESSION_PATH, API_ID, API_HASH)


async def ensure_connected():
    if not tg.is_connected():
        await tg.connect()
        if not await tg.is_user_authorized():
            raise RuntimeError(
                "Not authenticated. Run this script directly first to log in: "
                "python telegram_mcp_server.py"
            )


def _entity_type(entity) -> str:
    if isinstance(entity, Channel):
        return "channel" if entity.broadcast else "group"
    if isinstance(entity, Chat):
        return "group"
    if isinstance(entity, User):
        return "saved_messages" if entity.is_self else "dm"
    return "unknown"


def _format_message(msg) -> dict:
    result = {
        "id": msg.id,
        "text": msg.text or "",
        "date": msg.date.isoformat() if msg.date else None,
        "sender_id": msg.sender_id,
    }
    if msg.sender:
        name_parts = []
        if hasattr(msg.sender, "first_name") and msg.sender.first_name:
            name_parts.append(msg.sender.first_name)
        if hasattr(msg.sender, "last_name") and msg.sender.last_name:
            name_parts.append(msg.sender.last_name)
        if hasattr(msg.sender, "title") and msg.sender.title:
            name_parts.append(msg.sender.title)
        result["sender_name"] = " ".join(name_parts) if name_parts else None
    if msg.media:
        result["has_media"] = True
        result["media_type"] = type(msg.media).__name__
    return result


@mcp.tool()
async def list_dialogs(
    limit: Annotated[int, Field(description="Max number of dialogs to return")] = 50,
    filter: Annotated[
        str, Field(description="Filter: 'all', 'channels', 'groups', 'dms'")
    ] = "all",
) -> list[dict]:
    """List your Telegram chats, channels, and groups."""
    await ensure_connected()
    dialogs = []
    async for d in tg.iter_dialogs(limit=limit):
        dtype = _entity_type(d.entity)
        if filter != "all" and not dtype.startswith(filter.rstrip("s")):
            continue
        dialogs.append(
            {
                "id": d.id,
                "name": d.name,
                "type": dtype,
                "unread_count": d.unread_count,
                "last_message_date": d.date.isoformat() if d.date else None,
            }
        )
    return dialogs


@mcp.tool()
async def get_messages(
    chat_id: Annotated[
        str,
        Field(description="Chat ID (number) or 'me' for saved messages"),
    ],
    limit: Annotated[int, Field(description="Number of messages to fetch")] = 30,
    offset_id: Annotated[
        int, Field(description="Fetch messages older than this message ID")
    ] = 0,
) -> list[dict]:
    """Get messages from a chat, channel, or saved messages."""
    await ensure_connected()
    target = "me" if chat_id == "me" else int(chat_id)
    messages = []
    async for msg in tg.iter_messages(target, limit=limit, offset_id=offset_id):
        messages.append(_format_message(msg))
    return messages


@mcp.tool()
async def search_messages(
    query: Annotated[str, Field(description="Text to search for")],
    chat_id: Annotated[
        str | None,
        Field(description="Chat ID to search in, or omit to search everywhere"),
    ] = None,
    limit: Annotated[int, Field(description="Max results")] = 20,
) -> list[dict]:
    """Search messages by text across all chats or within a specific chat."""
    await ensure_connected()
    target = None
    if chat_id:
        target = "me" if chat_id == "me" else int(chat_id)
    messages = []
    async for msg in tg.iter_messages(target, search=query, limit=limit):
        messages.append(_format_message(msg))
    return messages


@mcp.tool()
async def get_chat_info(
    chat_id: Annotated[str, Field(description="Chat ID (number) or username")],
) -> dict:
    """Get details about a specific chat or channel."""
    await ensure_connected()
    target = int(chat_id) if chat_id.lstrip("-").isdigit() else chat_id
    entity = await tg.get_entity(target)
    info = {
        "id": entity.id,
        "type": _entity_type(entity),
    }
    if isinstance(entity, (Channel, Chat)):
        info["title"] = entity.title
        if hasattr(entity, "username") and entity.username:
            info["username"] = entity.username
        full = await tg.get_entity(entity)
        if hasattr(entity, "participants_count"):
            info["member_count"] = entity.participants_count
    elif isinstance(entity, User):
        info["name"] = f"{entity.first_name or ''} {entity.last_name or ''}".strip()
        if entity.username:
            info["username"] = entity.username
    return info


@mcp.tool()
async def send_message(
    chat_id: Annotated[
        str,
        Field(description="Chat ID (number) or 'me' for saved messages"),
    ],
    text: Annotated[str, Field(description="Message text to send")],
    reply_to_msg_id: Annotated[
        int | None,
        Field(description="Message ID to reply to"),
    ] = None,
) -> dict:
    """Send a text message to a chat, channel, or saved messages."""
    await ensure_connected()
    target = "me" if chat_id == "me" else int(chat_id)
    msg = await tg.send_message(target, text, reply_to=reply_to_msg_id)
    return _format_message(msg)


@mcp.tool()
async def edit_message(
    chat_id: Annotated[
        str,
        Field(description="Chat ID (number) or 'me' for saved messages"),
    ],
    message_id: Annotated[int, Field(description="ID of the message to edit")],
    new_text: Annotated[str, Field(description="New text for the message")],
) -> dict:
    """Edit the text of an existing message."""
    await ensure_connected()
    target = "me" if chat_id == "me" else int(chat_id)
    msg = await tg.edit_message(target, message_id, text=new_text)
    return _format_message(msg)


@mcp.tool()
async def delete_messages(
    chat_id: Annotated[
        str,
        Field(description="Chat ID (number) or 'me' for saved messages"),
    ],
    message_ids: Annotated[
        list[int], Field(description="List of message IDs to delete")
    ],
) -> dict:
    """Delete one or more messages from a chat."""
    await ensure_connected()
    target = "me" if chat_id == "me" else int(chat_id)
    affected = await tg.delete_messages(target, message_ids)
    return {"deleted_count": len(affected)}


@mcp.tool()
async def forward_messages(
    from_chat_id: Annotated[
        str,
        Field(description="Source chat ID (number) or 'me' for saved messages"),
    ],
    to_chat_id: Annotated[
        str,
        Field(description="Destination chat ID (number) or 'me' for saved messages"),
    ],
    message_ids: Annotated[
        list[int], Field(description="List of message IDs to forward")
    ],
) -> list[dict]:
    """Forward messages from one chat to another."""
    await ensure_connected()
    from_target = "me" if from_chat_id == "me" else int(from_chat_id)
    to_target = "me" if to_chat_id == "me" else int(to_chat_id)
    msgs = await tg.forward_messages(to_target, message_ids, from_target)
    if not isinstance(msgs, list):
        msgs = [msgs]
    return [_format_message(msg) for msg in msgs]


@mcp.tool()
async def archive_chat(
    chat_id: Annotated[
        str,
        Field(description="Chat ID (number) or 'me' for saved messages"),
    ],
) -> dict:
    """Archive a chat."""
    await ensure_connected()
    entity = await tg.get_input_entity("me" if chat_id == "me" else int(chat_id))
    await tg.edit_folder(entity, folder=1)
    return {"archived": True, "chat_id": chat_id}


@mcp.tool()
async def unarchive_chat(
    chat_id: Annotated[
        str,
        Field(description="Chat ID (number) or 'me' for saved messages"),
    ],
) -> dict:
    """Unarchive a chat."""
    await ensure_connected()
    entity = await tg.get_input_entity("me" if chat_id == "me" else int(chat_id))
    await tg.edit_folder(entity, folder=0)
    return {"archived": False, "chat_id": chat_id}


@mcp.tool()
async def pin_message(
    chat_id: Annotated[
        str,
        Field(description="Chat ID (number) or 'me' for saved messages"),
    ],
    message_id: Annotated[int, Field(description="ID of the message to pin")],
) -> dict:
    """Pin a message in a chat."""
    await ensure_connected()
    entity = await tg.get_input_entity("me" if chat_id == "me" else int(chat_id))
    await tg.pin_message(entity, message_id)
    return {"pinned": True, "message_id": message_id}


@mcp.tool()
async def unpin_message(
    chat_id: Annotated[
        str,
        Field(description="Chat ID (number) or 'me' for saved messages"),
    ],
    message_id: Annotated[int, Field(description="ID of the message to unpin")],
) -> dict:
    """Unpin a message in a chat."""
    await ensure_connected()
    entity = await tg.get_input_entity("me" if chat_id == "me" else int(chat_id))
    await tg.unpin_message(entity, message_id)
    return {"unpinned": True, "message_id": message_id}


@mcp.tool()
async def mark_read(
    chat_id: Annotated[
        str,
        Field(description="Chat ID (number) or 'me' for saved messages"),
    ],
) -> dict:
    """Mark all messages in a chat as read."""
    await ensure_connected()
    entity = await tg.get_input_entity("me" if chat_id == "me" else int(chat_id))
    await tg.send_read_acknowledge(entity)
    return {"marked_read": True, "chat_id": chat_id}


@mcp.tool()
async def mute_chat(
    chat_id: Annotated[
        str,
        Field(description="Chat ID (number) or 'me' for saved messages"),
    ],
    hours: Annotated[
        float | None,
        Field(description="Hours to mute for, or omit to mute forever"),
    ] = None,
) -> dict:
    """Mute notifications for a chat. Omit hours to mute forever."""
    await ensure_connected()
    entity = await tg.get_input_entity("me" if chat_id == "me" else int(chat_id))
    if hours is not None:
        mute_until = datetime.now(timezone.utc) + timedelta(hours=hours)
    else:
        mute_until = datetime(2038, 1, 1, tzinfo=timezone.utc)
    await tg(UpdateNotifySettingsRequest(
        peer=entity,
        settings=InputPeerNotifySettings(mute_until=mute_until),
    ))
    return {"muted": True, "chat_id": chat_id}


@mcp.tool()
async def unmute_chat(
    chat_id: Annotated[
        str,
        Field(description="Chat ID (number) or 'me' for saved messages"),
    ],
) -> dict:
    """Unmute notifications for a chat."""
    await ensure_connected()
    entity = await tg.get_input_entity("me" if chat_id == "me" else int(chat_id))
    await tg(UpdateNotifySettingsRequest(
        peer=entity,
        settings=InputPeerNotifySettings(
            mute_until=datetime(1970, 1, 1, tzinfo=timezone.utc)
        ),
    ))
    return {"muted": False, "chat_id": chat_id}


@mcp.tool()
async def list_folders() -> list[dict]:
    """List all chat folders."""
    await ensure_connected()
    result = await tg(GetDialogFiltersRequest())
    folders = []
    for f in result.filters:
        if not isinstance(f, DialogFilter):
            continue
        folders.append({
            "id": f.id,
            "title": f.title.text if isinstance(f.title, TextWithEntities) else f.title,
            "include_peers": [get_peer_id(p) for p in f.include_peers],
            "exclude_peers": [get_peer_id(p) for p in f.exclude_peers],
            "pinned_peers": [get_peer_id(p) for p in f.pinned_peers],
            "contacts": f.contacts,
            "non_contacts": f.non_contacts,
            "groups": f.groups,
            "broadcasts": f.broadcasts,
            "bots": f.bots,
        })
    return folders


@mcp.tool()
async def create_folder(
    name: Annotated[str, Field(description="Name for the new folder")],
    chat_ids: Annotated[
        list[str],
        Field(description="List of chat IDs to include in the folder"),
    ],
) -> dict:
    """Create a new chat folder with the specified chats."""
    await ensure_connected()
    result = await tg(GetDialogFiltersRequest())
    existing_ids = [
        f.id for f in result.filters if isinstance(f, DialogFilter)
    ]
    new_id = max(existing_ids) + 1 if existing_ids else 2
    peers = []
    for cid in chat_ids:
        entity = await tg.get_input_entity("me" if cid == "me" else int(cid))
        peers.append(entity)
    dialog_filter = DialogFilter(
        id=new_id,
        title=TextWithEntities(text=name, entities=[]),
        include_peers=peers,
        exclude_peers=[],
        pinned_peers=[],
    )
    await tg(UpdateDialogFilterRequest(id=new_id, filter=dialog_filter))
    return {"created": True, "folder_id": new_id, "name": name, "chat_count": len(chat_ids)}


@mcp.tool()
async def update_folder(
    folder_id: Annotated[int, Field(description="ID of the folder to update")],
    name: Annotated[
        str | None,
        Field(description="New name for the folder"),
    ] = None,
    add_chat_ids: Annotated[
        list[str] | None,
        Field(description="Chat IDs to add to the folder"),
    ] = None,
    remove_chat_ids: Annotated[
        list[str] | None,
        Field(description="Chat IDs to remove from the folder"),
    ] = None,
) -> dict:
    """Update an existing folder — rename or modify its chats."""
    await ensure_connected()
    result = await tg(GetDialogFiltersRequest())
    folder = None
    for f in result.filters:
        if isinstance(f, DialogFilter) and f.id == folder_id:
            folder = f
            break
    if folder is None:
        raise ValueError(f"Folder with ID {folder_id} not found")
    if name is not None:
        folder.title = TextWithEntities(text=name, entities=[])
    if add_chat_ids:
        existing_peer_ids = {get_peer_id(p) for p in folder.include_peers}
        for cid in add_chat_ids:
            entity = await tg.get_input_entity("me" if cid == "me" else int(cid))
            if get_peer_id(entity) not in existing_peer_ids:
                folder.include_peers.append(entity)
    if remove_chat_ids:
        remove_ids = set()
        for cid in remove_chat_ids:
            entity = await tg.get_input_entity("me" if cid == "me" else int(cid))
            remove_ids.add(get_peer_id(entity))
        folder.include_peers = [
            p for p in folder.include_peers if get_peer_id(p) not in remove_ids
        ]
    await tg(UpdateDialogFilterRequest(id=folder_id, filter=folder))
    return {"updated": True, "folder_id": folder_id}


@mcp.tool()
async def delete_folder(
    folder_id: Annotated[int, Field(description="ID of the folder to delete")],
) -> dict:
    """Delete a chat folder."""
    await ensure_connected()
    await tg(UpdateDialogFilterRequest(id=folder_id, filter=DialogFilter(
        id=folder_id, title=TextWithEntities(text="", entities=[]), include_peers=[]
    )))
    return {"deleted": True, "folder_id": folder_id}


async def _qr_login():
    """Authenticate via QR code — scan with your phone's Telegram app."""
    import asyncio
    import qrcode
    from telethon.errors import SessionPasswordNeededError

    await tg.connect()
    print("\n=== QR Code Login ===")
    print("Scan the QR code with Telegram on your phone:")
    print("  Settings → Devices → Link Desktop Device\n")

    qr_login = await tg.qr_login()

    # Display QR code
    def display_qr(url):
        qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_L)
        qr.add_data(url)
        qr.make(fit=True)
        qr.print_ascii(invert=True)

    display_qr(qr_login.url)

    # Wait for scan, regenerating QR if it expires
    try:
        logged_in = False
        for attempt in range(5):
            try:
                await qr_login.wait(timeout=30)
                logged_in = True
                break
            except asyncio.TimeoutError:
                print(f"\nQR expired, generating new one... (attempt {attempt + 2}/5)")
                await qr_login.recreate()
                display_qr(qr_login.url)
        if not logged_in:
            print("QR login timed out after 5 attempts. Please try again.")
            await tg.disconnect()
            return
    except SessionPasswordNeededError:
        import getpass
        password = getpass.getpass("2FA password required: ")
        await tg.sign_in(password=password)

    me = await tg.get_me()
    if me:
        print(f"\nLogged in as {me.first_name} (ID: {me.id})")
        print("Session saved. You can now register this server with Claude Code.")
    else:
        print("Login failed.")
    await tg.disconnect()


async def _phone_login():
    """Authenticate via phone number + code (original method)."""
    await tg.start()
    me = await tg.get_me()
    print(f"Logged in as {me.first_name} (ID: {me.id})")
    print("Session saved. You can now register this server with Claude Code.")
    await tg.disconnect()


async def _interactive_login():
    """Choose login method."""
    print("Telegram MCP — Authentication")
    print("1. QR Code (recommended — scan with your phone)")
    print("2. Phone number + code")
    choice = input("\nChoose method [1/2]: ").strip()
    if choice == "2":
        await _phone_login()
    else:
        await _qr_login()


if __name__ == "__main__":
    import asyncio

    asyncio.run(_interactive_login())
