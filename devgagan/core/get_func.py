# ---------------------------------------------------
# File Name: get_func.py
# Description: Core functionality for message handling
# ---------------------------------------------------

import asyncio
import time
import os
import re
import logging
from pyrogram import errors
from devgagan import app
from devgagan import sex as gf
from telethon.tl.types import DocumentAttributeVideo
from pyrogram.enums import MessageMediaType
from devgagan.core.func import (
    progress_bar, 
    get_chat_id,
    chk_user,
    split_and_upload_file
)
from config import (
    MONGO_DB, 
    LOG_GROUP, 
    OWNER_ID, 
    STRING, 
    API_ID, 
    API_HASH
)

logger = logging.getLogger(__name__)

# Constants
VIDEO_EXTENSIONS = ['mp4', 'mov', 'avi', 'mkv', 'flv', 'wmv', 'webm']
DOCUMENT_EXTENSIONS = ['pdf', 'docs']
SIZE_LIMIT = 2 * 1024 * 1024 * 1024  # 2GB

async def get_msg(userbot, user_id, msg_id, link, retry_count=0, message=None):
    """
    Get and process message from a channel/group
    """
    try:
        # Get chat ID first
        chat_id, error = await get_chat_id(userbot, link)
        if error:
            await message.reply(f"❌ {error}")
            return
            
        if not chat_id:
            await message.reply("❌ Could not determine chat ID. Please check the link.")
            return

        # Extract message ID from link if present
        if '/c/' in link or '/b/' in link:
            msg_id = int(link.split('/')[-1])
        elif '?message=' in link:
            msg_id = int(link.split('?message=')[-1])
        elif '/s/' in link:
            msg_id = int(link.split('/s/')[-1])
        else:
            msg_id = int(link.split('/')[-1])

        try:
            msg = await userbot.get_messages(chat_id, msg_id)
            if msg:
                await copy_message_with_chat_id(app, userbot, user_id, chat_id, msg_id, message)
            else:
                await message.reply("❌ Message not found. Please check the link.")
        except errors.FloodWait as e:
            if retry_count < 3:
                await asyncio.sleep(e.value)
                return await get_msg(userbot, user_id, msg_id, link, retry_count + 1, message)
            else:
                await message.reply(f"❌ Too many retries. Please try again later. Error: {str(e)}")
        except Exception as e:
            await message.reply(f"❌ Error getting message: {str(e)}")
            
    except Exception as e:
        logger.error(f"Error in get_msg: {str(e)}")
        await message.reply(f"❌ Error processing request: {str(e)}")

async def copy_message_with_chat_id(app, userbot, sender, chat_id, message_id, edit):
    """Copy message from source to destination with proper handling"""
    try:
        msg = await userbot.get_messages(chat_id, message_id)
        if not msg or msg.service or msg.empty:
            await edit.edit("❌ Invalid message or empty content")
            return

        # Handle different message types
        if msg.media == MessageMediaType.WEB_PAGE:
            await clone_message(app, msg, sender, None, edit.id, LOG_GROUP)
            return

        if msg.text:
            await clone_text_message(app, msg, sender, None, edit.id, LOG_GROUP)
            return

        # Handle media messages
        file = await download_and_process_media(userbot, msg, edit)
        if not file:
            return

        try:
            await upload_processed_media(app, msg, file, sender, edit)
        finally:
            if os.path.exists(file):
                os.remove(file)

    except Exception as e:
        logger.error(f"Error in copy_message: {str(e)}")
        await edit.edit(f"❌ Error: {str(e)}")

async def download_and_process_media(userbot, msg, edit):
    """Download and process media files"""
    try:
        file = await userbot.download_media(
            msg,
            progress=progress_bar,
            progress_args=(
                "╭─────────────────────╮\n│ **__Downloading...__**\n├─────────────────────",
                edit,
                time.time()
            )
        )
        return file
    except Exception as e:
        logger.error(f"Error downloading media: {str(e)}")
        await edit.edit(f"❌ Download failed: {str(e)}")
        return None

async def upload_processed_media(app, msg, file, sender, edit):
    """Upload processed media files"""
    try:
        file_size = os.path.getsize(file)
        caption = msg.caption.markdown if msg.caption else ""

        if file_size > SIZE_LIMIT:
            await split_and_upload_file(app, sender, file, caption)
        else:
            await app.send_document(
                sender,
                file,
                caption=caption,
                progress=progress_bar,
                progress_args=(
                    "╭─────────────────────╮\n│ **__Uploading...__**\n├─────────────────────",
                    edit,
                    time.time()
                )
            )
    except Exception as e:
        logger.error(f"Error uploading media: {str(e)}")
        await edit.edit(f"❌ Upload failed: {str(e)}")

# Add other helper functions as needed...
