# ---------------------------------------------------
# File Name: func.py
# Description: Core functionality for the Telegram bot
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
        link = await app.export_chat_invite_link(chat_id)
        return link
    except Exception as e:
        logger.error(f"Error generating invite link: {e}")
        return None

async def subscribe(app, message):
    """Handle user subscription to required channels"""
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

async def userbot_join(userbot, invite_link):
    """Join a chat using userbot"""
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
        return f"An error occurred: {str(e)}"

def get_link(text, message=None):
    """Extract URL from text or get chat link"""
    if message:
        # Original chat link functionality
        try:
            chat = text.split()[1]
            try:
                chat = int(chat)
            except ValueError:
                pass
            
            try:
                link = await app.export_chat_invite_link(chat)
                return link
            except Exception as e:
                logger.error(f"Error getting chat link: {e}")
                return None
                
        except Exception as e:
            logger.error(f"Error in get_link: {e}")
            return None
    else:
        # URL extraction functionality
        regex = r"(?i)\b((?:https?://|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:'\".,<>?«»""'']))"
        try:
            urls = re.findall(regex, text)
            return urls[0][0] if urls else False
        except Exception:
            return False

def video_metadata(file_path):
    """Extract video metadata"""
    try:
        cap = cv2.VideoCapture(file_path)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        duration = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) / cap.get(cv2.CAP_PROP_FPS))
        cap.release()
        return {
            'width': width,
            'height': height,
            'duration': duration
        }
    except Exception as e:
        logger.error(f"Error getting video metadata: {e}")
        return {
            'width': 1280,
            'height': 720,
            'duration': 0
        }

async def screenshot(file, duration, sender):
    """Generate video thumbnail"""
    try:
        if not file or not os.path.exists(file):
            return None
            
        thumbnail_path = f"{sender}_thumb.jpg"
        cap = cv2.VideoCapture(file)
        
        # Set position to 20% of duration
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(duration * 0.2 * cap.get(cv2.CAP_PROP_FPS)))
        
        success, frame = cap.read()
        if success:
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

async def get_chat_id(app, chat_link):
    """Get chat ID from a channel username or invite link"""
    try:
        # Handle t.me links
        if 't.me/' in chat_link:
            username = chat_link.split('t.me/')[1].split('/')[0]
        else:
            username = chat_link.split('/')[-1]
            
        # Remove any trailing message ID
        username = username.split('?')[0]
        
        try:
            # Try getting chat info
            chat = await app.get_chat(username)
            return chat.id, None
        except Exception as e:
            # If username lookup fails, try joining if it's a private channel
            try:
                if 'joinchat' in chat_link or '+' in chat_link:
                    await app.join_chat(chat_link)
                    chat = await app.get_chat(chat_link)
                    return chat.id, None
            except Exception as join_error:
                return None, f"Failed to join chat: {str(join_error)}"
                
            return None, f"Could not find chat: {str(e)}"
            
    except Exception as e:
        return None, f"Error processing link: {str(e)}"

async def progress_callback(current, total, progress_message):
    """Handle progress updates for file operations"""
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
    """Show progress bar for file operations"""
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

async def split_and_upload_file(app, sender, file, caption):
    """Split large files and upload them in parts"""
    try:
        if not os.path.exists(file):
            await app.send_message(sender, "❌ File not found!")
            return

        file_size = os.path.getsize(file)
        start = await app.send_message(
            sender, 
            f"ℹ️ File size: {file_size / (1024 * 1024):.2f} MB"
        )
        
        # Set part size to slightly less than 2GB to be safe
        PART_SIZE = 1.9 * 1024 * 1024 * 1024

        part_number = 0
        async with aiofiles.open(file, mode="rb") as f:
            while True:
                chunk = await f.read(int(PART_SIZE))
                if not chunk:
                    break

                # Create part filename
                base_name, file_ext = os.path.splitext(file)
                part_file = f"{base_name}.part{str(part_number).zfill(3)}{file_ext}"

                # Write part to file
                async with aiofiles.open(part_file, mode="wb") as part_f:
                    await part_f.write(chunk)

                # Upload part
                edit = await app.send_message(
                    sender, 
                    f"⬆️ Uploading part {part_number + 1}..."
                )
                
                part_caption = f"{caption}\n\n**Part : {part_number + 1}**"
                
                try:
                    await app.send_document(
                        sender,
                        document=part_file,
                        caption=part_caption,
                        parse_mode=ParseMode.MARKDOWN,
                        progress=progress_bar,
                        progress_args=(
                            "╭─────────────────────╮\n│ **__Pyro Uploader__**\n├─────────────────────",
                            edit,
                            time.time()
                        )
                    )
                except Exception as e:
                    logger.error(f"Error uploading part {part_number + 1}: {e}")
                    await edit.edit(f"❌ Error uploading part {part_number + 1}: {str(e)}")
                    return
                finally:
                    await edit.delete()
                    if os.path.exists(part_file):
                        os.remove(part_file)

                part_number += 1

        await start.delete()
        
    except Exception as e:
        logger.error(f"Error in split_and_upload_file: {e}")
        await app.send_message(sender, f"❌ Error processing file: {str(e)}")
    finally:
        if os.path.exists(file):
            os.remove(file)
