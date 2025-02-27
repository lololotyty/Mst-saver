# ---------------------------------------------------
# File Name: func.py
# Description: Core functionality for the Telegram bot
# ---------------------------------------------------

import math
import time
import re
import cv2
import os
import asyncio
import subprocess
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
    else:
        return 1

async def gen_link(app, chat_id):
    link = await app.export_chat_invite_link(chat_id)
    return link

async def subscribe(app, message):
    update_channel = CHANNEL_ID
    url = await gen_link(app, update_channel)
    if update_channel:
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
        except Exception:
            await message.reply_text("Something Went Wrong. Contact us @Shimps_bot")
            return 1

def get_link(string):
    regex = r"(?i)\b((?:https?://|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:'\".,<>?«»""'']))"
    url = re.findall(regex, string)
    try:
        link = [x[0] for x in url][0]
        return link if link else False
    except Exception:
        return False

def video_metadata(file):
    default_values = {'width': 1, 'height': 1, 'duration': 1}
    try:
        vcap = cv2.VideoCapture(file)
        if not vcap.isOpened():
            return default_values

        width = round(vcap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = round(vcap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = vcap.get(cv2.CAP_PROP_FPS)
        frame_count = vcap.get(cv2.CAP_PROP_FRAME_COUNT)

        if fps <= 0:
            return default_values

        duration = round(frame_count / fps)
        if duration <= 0:
            return default_values

        vcap.release()
        return {'width': width, 'height': height, 'duration': duration}
    except Exception as e:
        logger.error(f"Error in video_metadata: {e}")
        return default_values

async def screenshot(video_path, duration, user_id):
    try:
        if not os.path.exists(video_path):
            return None
            
        thumbnail_path = f"thumb_{user_id}_{int(time.time())}.jpg"
        
        # Take screenshot at 20% of the video duration
        timestamp = duration * 0.2
        
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
    tmp = ((str(days) + "d, ") if days else "") + \
        ((str(hours) + "h, ") if hours else "") + \
        ((str(minutes) + "m, ") if minutes else "") + \
        ((str(seconds) + "s, ") if seconds else "") + \
        ((str(milliseconds) + "ms, ") if milliseconds else "")
    return tmp[:-2]

PROGRESS_BAR = """\n
│ **__Completed:__** {1}/{2}
│ **__Bytes:__** {0}%
│ **__Speed:__** {3}/s
│ **__ETA:__** {4}
╰─────────────────────╯
"""

last_update_time = time.time()

async def progress_callback(current, total, progress_message):
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
