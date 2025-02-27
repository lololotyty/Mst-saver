# ---------------------------------------------------
# File Name: func.py
# Description: A Pyrogram bot for downloading files from Telegram channels or groups 
#              and uploading them back to Telegram.
# Author: Gagan
# GitHub: https://github.com/devgaganin/
# Telegram: https://t.me/team_spy_pro
# YouTube: https://youtube.com/@dev_gagan
# Created: 2025-01-11
# Last Modified: 2025-01-11
# Version: 2.0.5
# License: MIT License
# ---------------------------------------------------

__all__ = [
    'chk_user',
    'gen_link', 
    'subscribe',
    'get_seconds',
    'progress_bar',
    'humanbytes',
    'TimeFormatter',
    'convert',
    'userbot_join',
    'get_link',
    'video_metadata',
    'screenshot',
    'progress_callback',
    'prog_bar'
]

import math
import time
import re
import os
import cv2
import asyncio
import logging
from datetime import datetime as dt
from pyrogram import enums
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

async def chk_user(message, user_id):
    user = await premium_users()
    if user_id in user or user_id in OWNER_ID:
        return 0
    return 1

async def gen_link(app, chat_id):
    try:
        link = await app.export_chat_invite_link(chat_id)
        return link
    except Exception as e:
        logger.error(f"Error generating invite link: {e}")
        return None

async def subscribe(app, message):
    update_channel = CHANNEL_ID
    if not update_channel:
        return 0
        
    try:
        url = await gen_link(app, update_channel)
        if not url:
            return 0
            
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

PROGRESS_BAR = """
│ **__Completed:__** {1}/{2}
│ **__Bytes:__** {0}%
│ **__Speed:__** {3}/s
│ **__ETA:__** {4}
╰─────────────────────╯
"""

def humanbytes(size):
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
    seconds = seconds % (24 * 3600)
    hours = seconds // 3600
    seconds %= 3600
    minutes = seconds // 60
    seconds %= 60
    return "%d:%02d:%02d" % (hours, minutes, seconds)

async def userbot_join(userbot, invite_link):
    try:
        await userbot.join_chat(invite_link)
        return "Successfully joined the Channel"
    except UserAlreadyParticipant:
        return "User is already a participant."
    except (InviteHashInvalid, InviteHashExpired):
        return "Could not join. Maybe your link is expired or Invalid."
    except FloodWait as e:
        return f"Too many requests, try again after {e.x} seconds."
    except Exception as e:
        logger.error(f"Error joining chat: {e}")
        return "Could not join, try joining manually."

def get_link(string):
    regex = r"(?i)\b((?:https?://|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:'\".,<>?«»""'']))"
    try:
        urls = re.findall(regex, string)
        return urls[0][0] if urls else False
    except Exception:
        return False

def video_metadata(file):
    default_values = {'width': 1, 'height': 1, 'duration': 1}
    if not os.path.exists(file):
        return default_values
        
    try:
        cap = cv2.VideoCapture(file)
        if not cap.isOpened():
            return default_values

        width = round(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = round(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)

        if fps <= 0 or frame_count <= 0:
            return default_values

        duration = round(frame_count / fps)
        return {'width': width, 'height': height, 'duration': duration}

    except Exception as e:
        logger.error(f"Error in video_metadata: {e}")
        return default_values
    finally:
        if 'cap' in locals():
            cap.release()

async def screenshot(video_path, duration, user_id):
    try:
        if not os.path.exists(video_path):
            return None
            
        thumbnail_path = f"thumb_{user_id}_{int(time.time())}.jpg"
        timestamp = duration * 0.2  # Take screenshot at 20% of duration
        
        cap = cv2.VideoCapture(video_path)
        cap.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000)
        ret, frame = cap.read()
        
        if ret:
            cv2.imwrite(thumbnail_path, frame)
            if os.path.exists(thumbnail_path):
                return thumbnail_path
        return None
        
    except Exception as e:
        logger.error(f"Error generating screenshot: {e}")
        return None
    finally:
        if 'cap' in locals():
            cap.release()

last_update_time = time.time()

async def progress_callback(current, total, progress_message):
    try:
        percent = (current / total) * 100
        global last_update_time
        current_time = time.time()

        if current_time - last_update_time >= 10 or percent % 10 == 0:
            completed_blocks = int(percent // 10)
            remaining_blocks = 10 - completed_blocks
            progress_bar = "♦" * completed_blocks + "◇" * remaining_blocks
            current_mb = current / (1024 * 1024)
            total_mb = total / (1024 * 1024)
            
            await progress_message.edit(
                f"╭──────────────────╮\n"
                f"│        **__Uploading...__**       \n"
                f"├──────────\n"
                f"│ {progress_bar}\n\n"
                f"│ **__Progress:__** {percent:.2f}%\n"
                f"│ **__Uploaded:__** {current_mb:.2f} MB / {total_mb:.2f} MB\n"
                f"╰──────────────────╯\n\n"
                f"**__Powered by Shimperd__**"
            )
            last_update_time = current_time
    except Exception as e:
        logger.error(f"Error in progress callback: {e}")

async def progress_bar(current, total, ud_type, message, start):
    try:
        now = time.time()
        diff = now - start
        if round(diff % 10.00) == 0 or current == total:
            percentage = current * 100 / total
            speed = current / diff
            elapsed_time = round(diff) * 1000
            time_to_completion = round((total - current) / speed) * 1000
            estimated_total_time = elapsed_time + time_to_completion

            elapsed_time = TimeFormatter(milliseconds=elapsed_time)
            estimated_total_time = TimeFormatter(milliseconds=estimated_total_time)

            progress = "{0}{1}".format(
                ''.join(["♦" for _ in range(math.floor(percentage / 10))]),
                ''.join(["◇" for _ in range(10 - math.floor(percentage / 10))])
            )

            tmp = progress + PROGRESS_BAR.format(
                round(percentage, 2),
                humanbytes(current),
                humanbytes(total),
                humanbytes(speed),
                estimated_total_time if estimated_total_time != '' else "0 s"
            )
            
            await message.edit(text=f"{ud_type}\n│ {tmp}")
            
    except Exception as e:
        logger.error(f"Error in progress bar: {e}")

async def prog_bar(current, total, ud_type, message, start):
    """Alternative progress bar implementation"""
    try:
        await progress_bar(current, total, ud_type, message, start)
    except Exception as e:
        logger.error(f"Error in prog_bar: {e}")
