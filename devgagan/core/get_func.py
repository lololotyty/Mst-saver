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

        # Process message
        await process_message(userbot, chat_id, msg_id, user_id, message)
        
    except Exception as e:
        logger.error(f"Error in get_msg: {e}")
        if retry_count < 3:
            await asyncio.sleep(2)
            return await get_msg(userbot, user_id, msg_id, link, retry_count + 1, message)
        await message.reply(f"❌ Failed to process message: {str(e)}")

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

async def load_user_session(user_id):
    """Load user session from database"""
    try:
        user_data = await db.get_session(user_id)
        if user_data:
            return user_data.get("session")
        return None
    except Exception as e:
        logger.error(f"Error loading session: {e}")
        return None

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
