# ---------------------------------------------------
# File Name: main.py
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
# More readable 
# ---------------------------------------------------

import time
import random
import string
import asyncio
import logging
from pyrogram import filters, Client
from devgagan import app
from config import API_ID, API_HASH, FREEMIUM_LIMIT, PREMIUM_LIMIT, OWNER_ID
from devgagan.core.get_func import get_msg, load_user_session
from devgagan.core.func import *
from devgagan.core.mongo import db
from pyrogram.errors import FloodWait
from datetime import datetime, timedelta
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
import subprocess
from devgagan.modules.shrink import is_user_verified
import re

# Configure logger
logger = logging.getLogger(__name__)

async def generate_random_name(length=8):
    return ''.join(random.choices(string.ascii_lowercase, k=length))

users_loop = {}
interval_set = {}
batch_mode = {}

async def process_and_upload_link(userbot, user_id, msg_id, link, retry_count, message):
    try:
        await get_msg(userbot, user_id, msg_id, link, retry_count, message)
        await asyncio.sleep(15)
    finally:
        pass

async def check_interval(user_id, freecheck):
    if freecheck != 1 or await is_user_verified(user_id):
        return True, None

    now = datetime.now()
    if user_id in interval_set:
        cooldown_end = interval_set[user_id]
        if now < cooldown_end:
            remaining_time = (cooldown_end - now).seconds
            return False, f"Please wait {remaining_time} seconds(s) before sending another link. Alternatively, purchase premium for instant access.\n\n> Hey 👋 You can suck owners dick to use the bot free for 3 hours without any time limit."
        else:
            del interval_set[user_id]

    return True, None

async def set_interval(user_id, interval_minutes=45):
    if user_id not in OWNER_ID and not await is_user_verified(user_id):
        interval_set[user_id] = datetime.now() + timedelta(minutes=interval_minutes)

async def initialize_userbot(user_id):
    try:
        session = await load_user_session(user_id)  # Changed to await here
        if session:
            return Client(
                f"user_{user_id}",
                api_id=API_ID,
                api_hash=API_HASH,
                session_string=session
            )
    except Exception as e:
        logger.error(f"Error initializing userbot: {e}")
    return None

async def is_normal_tg_link(link):
    return 't.me/' in link and not 'tg://' in link

async def process_special_links(userbot, user_id, msg, link):
    # Handle special Telegram links (like tg:// links)
    parts = link.split('?')
    if len(parts) != 2:
        await msg.edit_text("Invalid link format")
        return

    params = dict(param.split('=') for param in parts[1].split('&'))
    message_id = int(params.get('message_id', 0))
    
    if message_id:
        await process_and_upload_link(userbot, user_id, msg.id, link, 0, msg)
        await set_interval(user_id)

@app.on_message(
    filters.regex(r'https?://(?:www\.)?t\.me/[^\s]+|tg://openmessage\?user_id=\w+&message_id=\d+')
    & filters.private
)
async def single_link(_, message):
    user_id = message.chat.id

    # Check subscription and batch mode
    if await subscribe(_, message) == 1 or user_id in batch_mode:
        return

    # Check if user is already in a loop
    if users_loop.get(user_id, False):
        await message.reply(
            "You already have an ongoing process. Please wait for it to finish or cancel it with /cancel."
        )
        return

    # Check freemium limits
    if await chk_user(message, user_id) == 1 and FREEMIUM_LIMIT == 0 and user_id not in OWNER_ID and not await is_user_verified(user_id):
        await message.reply("Free service is currently not available. Upgrade to premium for access.")
        return

    # Check cooldown
    can_proceed, response_message = await check_interval(user_id, await chk_user(message, user_id))
    if not can_proceed:
        await message.reply(response_message)
        return

    # Add user to the loop
    users_loop[user_id] = True

    if "tg://openmessage" in message.text:
        link = message.text
    else:
        # Extract URL using regex
        regex = r"(?i)\b((?:https?://|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:'\".,<>?«»""'']))"
        try:
            urls = re.findall(regex, message.text)
            link = urls[0][0] if urls else None
        except Exception:
            link = None

    if not link:
        await message.reply("❌ No valid link found in message")
        return

    msg = await message.reply("Processing...")
    userbot = await initialize_userbot(user_id)

    try:
        if await is_normal_tg_link(link):
            await process_and_upload_link(userbot, user_id, msg.id, link, 0, message)
            await set_interval(user_id, interval_minutes=45)
        else:
            await process_special_links(userbot, user_id, msg, link)
            
    except FloodWait as fw:
        await msg.edit_text(f'Try again after {fw.x} seconds due to floodwait from Telegram.')
    except Exception as e:
        await msg.edit_text(f"Link: `{link}`\n\n**Error:** {str(e)}")
    finally:
        users_loop[user_id] = False
        if userbot:
            await userbot.stop()
        try:
            await msg.delete()
        except Exception:
            pass

@app.on_message(filters.command("cancel") & filters.private)
async def cancel_process(_, message):
    user_id = message.chat.id
    if user_id in users_loop:
        users_loop[user_id] = False
        await message.reply("✅ Process cancelled successfully!")
    else:
        await message.reply("❌ No active process to cancel.")

@app.on_message(filters.command("batch") & filters.private)
async def batch_command(_, message):
    user_id = message.chat.id
    
    if await subscribe(_, message) == 1:
        return
        
    if user_id in batch_mode:
        batch_mode.pop(user_id)
        await message.reply("Batch mode disabled!")
    else:
        batch_mode[user_id] = []
        await message.reply(
            "Batch mode enabled!\n"
            "Send me links one by one.\n"
            "When done, send /done to start the process.\n"
            "To cancel, send /cancel"
        )

@app.on_message(filters.command("done") & filters.private)
async def done_command(_, message):
    user_id = message.chat.id
    
    if user_id not in batch_mode:
        await message.reply("No active batch process. Use /batch to start one.")
        return
        
    links = batch_mode.pop(user_id)
    if not links:
        await message.reply("No links were provided!")
        return
        
    msg = await message.reply("Processing batch...")
    userbot = await initialize_userbot(user_id)
    
    try:
        for link in links:
            try:
                await process_and_upload_link(userbot, user_id, msg.id, link, 0, message)
                await asyncio.sleep(2)
            except Exception as e:
                await message.reply(f"Error processing {link}: {str(e)}")
    finally:
        if userbot:
            await userbot.stop()
        await msg.delete()

@app.on_message(filters.text & filters.private)
async def handle_batch_links(_, message):
    user_id = message.chat.id
    
    if user_id not in batch_mode:
        return
        
    link = message.text
    if link.startswith('/'):
        return
        
    batch_mode[user_id].append(link)
    await message.reply("Link added to batch!")
