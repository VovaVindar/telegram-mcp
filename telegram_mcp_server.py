import os
import logging
from pathlib import Path
from typing import Annotated

from dotenv import load_dotenv
from fastmcp import FastMCP
from pydantic import Field
from telethon import TelegramClient
from telethon.tl.types import Channel, Chat, User

# Load .env from the same directory as this script
load_dotenv(Path(__file__).parent / ".env")

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

API_ID = int(os.environ["TELEGRAM_API_ID"])
API_HASH = os.environ["TELEGRAM_API_HASH"]
SESSION_PATH = str(Path(__file__).parent / "telegram")

mcp = FastMCP("Telegram")
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
