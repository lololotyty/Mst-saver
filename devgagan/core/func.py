# ---------------------------------------------------
# File Name: func.py
# Description: Core functionality for the Telegram bot
# ---------------------------------------------------

__all__ = [
    'chk_user',
    'gen_link', 
    'subscribe',
    'get_seconds',
    'progress_callback',
    'humanbytes',
    'TimeFormatter',
    'convert',
    'userbot_join',
    'get_link',
    'video_metadata',
    'screenshot',
    'prog_bar',
    'get_chat_id',
    'split_and_upload_file'
]

import math
import time
import re
import os
import cv2
import asyncio
import logging
import aiofiles
from datetime import datetime as dt
from pyrogram import enums
from pyrogram.enums import ParseMode
from config import CHANNEL_ID, OWNER_ID 
from devgagan.core.mongo.plans_db import premium_users
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.errors import (
    FloodWait, 
    InviteHashInvalid, 
    InviteHashExpired, 
    UserAlreadyParticipant, 
    UserNotParticipant
)

logger = logging.getLogger(__name__)

# Constants
SIZE_LIMIT = 2 * 1024 * 1024 * 1024  # 2GB
PROGRESS_BAR = """
│ **__Completed:__** {1}/{2}
│ **__Bytes:__** {0}%
│ **__Speed:__** {3}/s
│ **__ETA:__** {4}
╰─────────────────────╯
"""

last_update_time = time.time()

async def chk_user(message, user_id):
    """Check if user is premium or owner"""
    user = await premium_users()
    if user_id in user or user_id in OWNER_ID:
        return 0
    return 1

async def gen_link(app, chat_id):
    """Generate invite link for a chat"""
    try:
        # First try to get chat info to validate chat_id
        try:
            chat = await app.get_chat(chat_id)
            if not chat:
                logger.error(f"Chat not found: {chat_id}")
                return None
        except Exception as e:
            logger.error(f"Error getting chat info: {e}")
            return None

        # Then try to generate invite link
        try:
            link = await app.export_chat_invite_link(chat_id)
            return link
        except Exception as e:
            logger.error(f"Error generating invite link: {e}")
            return None
            
    except Exception as e:
        logger.error(f"Error in gen_link: {e}")
        return None

async def subscribe(app, message):
    """Handle user subscription to required channels"""
    update_channel = CHANNEL_ID
    if not update_channel:
        return 0
        
    try:
        # First verify the channel exists
        try:
            chat = await app.get_chat(update_channel)
            if not chat:
                logger.error("Update channel not found")
                return 0
        except Exception as e:
            logger.error(f"Error getting update channel: {e}")
            return 0
            
        # Then try to get/generate invite link
        url = await gen_link(app, update_channel)
        if not url:
            logger.error("Could not generate invite link")
            return 0
            
        try:
            user = await app.get_chat_member(update_channel, message.from_user.id)
            if user.status == "kicked":
                await message.reply_text("You are Banned. Contact -- @Shimps_bot")
                return 1
                
        except UserNotParticipant:
            caption = "Join our channel to use the bot"
            await message.reply_photo(
                photo="https://graph.org/file/94027ad785c6ba022fcd0-1d4e0c2f339471ce84.jpg",
                caption=caption,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Join Now...", url=url)]])
            )
            return 1
            
    except Exception as e:
        logger.error(f"Error in subscribe: {e}")
        await message.reply_text("Something Went Wrong. Contact us @Shimps_bot")
        return 1
        
    return 0

async def get_seconds(time_string):
    """Convert time string to seconds"""
    try:
        value = int(''.join(filter(str.isdigit, time_string)))
        unit = ''.join(filter(str.isalpha, time_string.lower()))
        
        multipliers = {
            's': 1,
            'min': 60,
            'hour': 3600,
            'day': 86400,
            'month': 2592000,  # 30 days
            'year': 31536000   # 365 days
        }
        
        return value * multipliers.get(unit, 0)
    except Exception as e:
        logger.error(f"Error converting time: {e}")
        return 0

def humanbytes(size):
    """Convert bytes to human readable format"""
    if not size:
        return ""
    power = 2**10
    n = 0
    Dic_powerN = {0: ' ', 1: 'K', 2: 'M', 3: 'G', 4: 'T'}
    while size > power:
        size /= power
        n += 1
    return str(round(size, 2)) + " " + Dic_powerN[n] + 'B'

def TimeFormatter(milliseconds: int) -> str:
    """Format milliseconds to readable time string"""
    seconds, milliseconds = divmod(int(milliseconds), 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    
    parts = []
    if days: parts.append(f"{days}d")
    if hours: parts.append(f"{hours}h")
    if minutes: parts.append(f"{minutes}m")
    if seconds: parts.append(f"{seconds}s")
    if milliseconds: parts.append(f"{milliseconds}ms")
    
    return ", ".join(parts) if parts else "0s"

def convert(seconds):
    """Convert seconds to HH:MM:SS format"""
    seconds = seconds % (24 * 3600)
    hours = seconds // 3600
    seconds %= 3600
    minutes = seconds // 60
    seconds %= 60
    return "%d:%02d:%02d" % (hours, minutes, seconds)
