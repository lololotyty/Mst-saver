# ---------------------------------------------------
# File Name: get_func.py
# Description: Core functionality for message handling
# Author: Gagan
# GitHub: https://github.com/devgaganin/
# Version: 2.0.5
# License: MIT License
# ---------------------------------------------------

import asyncio
import time
import gc
import os
import re
import logging
from typing import Callable
from devgagan import app
import aiofiles
from devgagan import sex as gf
from telethon.tl.types import DocumentAttributeVideo, Message
from telethon.sessions import StringSession
import pymongo
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import (
    ChannelBanned, 
    ChannelInvalid, 
    ChannelPrivate, 
    ChatIdInvalid, 
    ChatInvalid,
    FloodWait,
    RPCError
)
from pyrogram.enums import MessageMediaType, ParseMode
from devgagan.core.func import (
    chk_user,
    subscribe,
    gen_link,
    progress_bar,
    get_chat_id,
    split_and_upload_file,
    video_metadata
)
from config import (
    MONGO_DB as MONGODB_CONNECTION_STRING,
    LOG_GROUP,
    OWNER_ID,
    STRING,
    API_ID,
    API_HASH
)
from devgagan.core.mongo import db as odb
from telethon import TelegramClient, events, Button
from devgagantools import fast_upload

logger = logging.getLogger(__name__)

# Constants
VIDEO_EXTENSIONS = ['mp4', 'mov', 'avi', 'mkv', 'flv', 'wmv', 'webm', 'mpg', 'mpeg', '3gp', 'ts', 'm4v', 'f4v', 'vob']
DOCUMENT_EXTENSIONS = ['pdf', 'docs']
SIZE_LIMIT = 2 * 1024 * 1024 * 1024  # 2GB

# MongoDB setup
DB_NAME = "smart_users"
COLLECTION_NAME = "super_user"
mongo_app = pymongo.MongoClient(MONGODB_CONNECTION_STRING)
db = mongo_app[DB_NAME]
collection = db[COLLECTION_NAME]

# Initialize pro client if STRING is available
if STRING:
    from devgagan import pro
    logger.info("Pro client initialized successfully")
else:
    pro = None
    logger.warning("STRING not available, pro client disabled")

# User storage
user_chat_ids = {}
user_rename_preferences = {}
user_caption_preferences = {}

def thumbnail(sender):
    """Get thumbnail path for a sender"""
    return f'{sender}.jpg' if os.path.exists(f'{sender}.jpg') else None

async def fetch_upload_method(user_id):
    """Fetch user's preferred upload method"""
    user_data = collection.find_one({"user_id": user_id})
    return user_data.get("upload_method", "Pyrogram") if user_data else "Pyrogram"

async def format_caption_to_html(caption: str) -> str:
    """Convert markdown-style formatting to HTML"""
    if not caption:
        return None
        
    caption = re.sub(r"^> (.*)", r"<blockquote>\1</blockquote>", caption, flags=re.MULTILINE)
    caption = re.sub(r"```(.*?)```", r"<pre>\1</pre>", caption, flags=re.DOTALL)
    caption = re.sub(r"`(.*?)`", r"<code>\1</code>", caption)
    caption = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", caption)
    caption = re.sub(r"\*(.*?)\*", r"<b>\1</b>", caption)
    caption = re.sub(r"__(.*?)__", r"<i>\1</i>", caption)
    caption = re.sub(r"_(.*?)_", r"<i>\1</i>", caption)
    caption = re.sub(r"~~(.*?)~~", r"<s>\1</s>", caption)
    caption = re.sub(r"\|\|(.*?)\|\|", r"<details>\1</details>", caption)
    caption = re.sub(r"\[(.*?)\]\((.*?)\)", r'<a href="\2">\1</a>', caption)
    
    return caption.strip()

async def get_msg(userbot, user_id, msg_id, link, retry_count=0, message=None):
    """Process and handle message from link"""
    try:
        # Get chat ID
        chat_id, error = await get_chat_id(userbot, link)
        if error:
            await message.reply(f"❌ {error}")
            return
            
        if not chat_id:
            await message.reply("❌ Could not determine chat ID. Please check the link.")
            return

        # Extract message ID from link
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
        except FloodWait as e:
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
    """Copy message between chats with proper handling"""
    try:
        msg = await userbot.get_messages(chat_id, message_id)
        if not msg or msg.service or msg.empty:
            await edit.edit("❌ Invalid message or empty content")
            return

        # Handle different message types
        if msg.web_page:
            await clone_message(app, msg, sender, None, edit.id, LOG_GROUP)
            return

        if msg.text:
            await clone_text_message(app, msg, sender, None, edit.id, LOG_GROUP)
            return

        # Handle media messages
        if msg.media:
            file = await download_and_process_media(userbot, msg, edit)
            if not file:
                return

            try:
                await upload_processed_media(app, msg, file, sender, edit)
            finally:
                if os.path.exists(file):
                    os.remove(file)
        else:
            await edit.edit("❌ Unsupported message type")

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
            # Determine media type and use appropriate upload method
            if msg.video:
                metadata = video_metadata(file)
                await app.send_video(
                    sender,
                    file,
                    caption=caption,
                    duration=metadata['duration'],
                    width=metadata['width'],
                    height=metadata['height'],
                    progress=progress_bar,
                    progress_args=(
                        "╭─────────────────────╮\n│ **__Uploading...__**\n├─────────────────────",
                        edit,
                        time.time()
                    )
                )
            elif msg.photo:
                await app.send_photo(
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

async def clone_message(app, msg, target_chat_id, topic_id, edit_id, log_group):
    """Clone a message to target chat"""
    edit = await app.edit_message_text(target_chat_id, edit_id, "Cloning...")
    devgaganin = await app.send_message(target_chat_id, msg.text.markdown, reply_to_message_id=topic_id)
    await devgaganin.copy(log_group)
    await edit.delete()

async def clone_text_message(app, msg, target_chat_id, topic_id, edit_id, log_group):
    """Clone a text message to target chat"""
    edit = await app.edit_message_text(target_chat_id, edit_id, "Cloning text message...")
    devgaganin = await app.send_message(target_chat_id, msg.text.markdown, reply_to_message_id=topic_id)
    await devgaganin.copy(log_group)
    await edit.delete()

async def handle_sticker(app, msg, target_chat_id, topic_id, edit_id, log_group):
    """Handle sticker messages"""
    edit = await app.edit_message_text(target_chat_id, edit_id, "Handling sticker...")
    result = await app.send_sticker(target_chat_id, msg.sticker.file_id, reply_to_message_id=topic_id)
    await result.copy(log_group)
    await edit.delete()

async def download_user_stories(userbot, chat_id, msg_id, edit, sender):
    """Download and process user stories"""
    try:
        story = await userbot.get_stories(chat_id, msg_id)
        if not story:
            await edit.edit("No story available for this user.")
            return  
        if not story.media:
            await edit.edit("The story doesn't contain any media.")
            return

        await edit.edit("Downloading Story...")
        file_path = await userbot.download_media(story)
        
        if story.media:
            await edit.edit("Uploading Story...")
            if story.media == MessageMediaType.VIDEO:
                await app.send_video(sender, file_path)
            elif story.media == MessageMediaType.DOCUMENT:
                await app.send_document(sender, file_path)
            elif story.media == MessageMediaType.PHOTO:
                await app.send_photo(sender, file_path)

        if file_path and os.path.exists(file_path):
            os.remove(file_path)  
            
        await edit.edit("Story processed successfully.")
    except RPCError as e:
        logger.error(f"Failed to fetch story: {e}")
        await edit.edit(f"Error: {e}")

# Database helper functions
def load_user_data(user_id, key, default_value=None):
    """Load user data from database"""
    try:
        user_data = collection.find_one({"_id": user_id})
        return user_data.get(key, default_value) if user_data else default_value
    except Exception as e:
        logger.error(f"Error loading {key}: {e}")
        return default_value

def save_user_data(user_id, key, value):
    """Save user data to database"""
    try:
        collection.update_one(
            {"_id": user_id},
            {"$set": {key: value}},
            upsert=True
        )
    except Exception as e:
        logger.error(f"Error saving {key}: {e}")

# User preference functions
load_delete_words = lambda user_id: set(load_user_data(user_id, "delete_words", []))
save_delete_words = lambda user_id, words: save_user_data(user_id, "delete_words", list(words))
load_replacement_words = lambda user_id: load_user_data(user_id, "replacement_words", {})
save_replacement_words = lambda user_id, replacements: save_user_data(user_id, "replacement_words", replacements)
load_user_session = lambda user_id: load_user_data(user_id, "session")
set_dupload = lambda user_id, value: save_user_data(user_id, "dupload", value)
get_dupload = lambda user_id: load_user_data(user_id, "dupload", False)

async def set_rename_command(user_id, custom_rename_tag):
    """Set custom rename tag for user"""
    user_rename_preferences[str(user_id)] = custom_rename_tag

get_user_rename_preference = lambda user_id: user_rename_preferences.get(str(user_id), 'Shimperd')

async def set_caption_command(user_id, custom_caption):
    """Set custom caption for user"""
    user_caption_preferences[str(user_id)] = custom_caption

get_user_caption_preference = lambda user_id: user_caption_preferences.get(str(user_id), 'Shimperd')
