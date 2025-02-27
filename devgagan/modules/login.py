# ---------------------------------------------------
# File Name: login.py
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

import random
import os
import asyncio
import string
import logging
from pyrogram import filters, Client
from devgagan import app
from devgagan.core.mongo import db
from devgagan.core.func import subscribe, chk_user
from config import API_ID as api_id, API_HASH as api_hash
from pyrogram.errors import (
    ApiIdInvalid,
    PhoneNumberInvalid,
    PhoneCodeInvalid,
    PhoneCodeExpired,
    SessionPasswordNeeded,
    PasswordHashInvalid,
    FloodWait,
    TimeoutError
)

logger = logging.getLogger(__name__)

def generate_random_name(length=7):
    """Generate a random string of specified length"""
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(length))

async def delete_session_files(user_id):
    """Delete session files and database entry for a user"""
    session_file = f"session_{user_id}.session"
    memory_file = f"session_{user_id}.session-journal"

    session_file_exists = os.path.exists(session_file)
    memory_file_exists = os.path.exists(memory_file)

    if session_file_exists:
        os.remove(session_file)
    
    if memory_file_exists:
        os.remove(memory_file)

    # Delete session from the database
    if session_file_exists or memory_file_exists:
        await db.remove_session(user_id)
        return True  # Files were deleted
    return False  # No files found

async def initialize_connection(client, message):
    """Initialize connection with Telegram servers"""
    try:
        await client.connect()
        return True
    except Exception as e:
        logger.error(f"Connection error: {e}")
        await message.reply("❌ Failed to establish connection. Please try again later.")
        return False

@app.on_message(filters.command("logout"))
async def clear_db(client, message):
    """Handle user logout"""
    user_id = message.chat.id
    files_deleted = await delete_session_files(user_id)
    
    try:
        await db.remove_session(user_id)
    except Exception as e:
        logger.error(f"Error removing session from DB: {e}")

    if files_deleted:
        await message.reply("✅ Your session data and files have been cleared from memory and disk.")
    else:
        await message.reply("✅ Logged out with flag -m")

@app.on_message(filters.command("login"))
async def generate_session(_, message):
    """Handle user login process"""
    # Check if user has joined required channels
    joined = await subscribe(_, message)
    if joined == 1:
        return
        
    user_id = message.chat.id   
    
    # Initialize client
    client = Client(f"session_{user_id}", api_id, api_hash)
    
    try:
        # Check connection first
        if not await initialize_connection(client, message):
            await client.disconnect()
            return

        # Get phone number
        number = await _.ask(
            user_id, 
            'Please enter your phone number along with the country code. \nExample: +19876543210',
            filters=filters.text
        )   
        phone_number = number.text
        
        # Send OTP
        await message.reply("📲 Sending OTP...")
        await client.send_code(phone_number)
        
        # Get OTP
        try:
            otp_code = await _.ask(
                user_id, 
                "Please check for an OTP in your official Telegram account. Once received, enter the OTP in the following format: \nIf the OTP is `12345`, please enter it as `1 2 3 4 5`.",
                filters=filters.text,
                timeout=600
            )
        except TimeoutError:
            await message.reply('⏰ Time limit of 10 minutes exceeded. Please restart the session.')
            await client.disconnect()
            return

        phone_code = otp_code.text.replace(" ", "")
        
        # Try to sign in
        try:
            await client.sign_in(phone_number, phone_code)
        except SessionPasswordNeeded:
            # Handle 2FA if enabled
            try:
                two_step_msg = await _.ask(
                    user_id,
                    'Your account has two-step verification enabled. Please enter your password.',
                    filters=filters.text,
                    timeout=300
                )
                password = two_step_msg.text
                await client.check_password(password=password)
            except TimeoutError:
                await message.reply('⏰ Time limit of 5 minutes exceeded. Please restart the session.')
                await client.disconnect()
                return
            except PasswordHashInvalid:
                await message.reply('❌ Invalid password. Please restart the session.')
                await client.disconnect()
                return

        # Successfully logged in, save session
        string_session = await client.export_session_string()
        await db.set_session(user_id, string_session)
        await message.reply("✅ Login successful!")

    except ApiIdInvalid:
        await message.reply('❌ Invalid API ID/Hash combination. Please check your configuration.')
    except PhoneNumberInvalid:
        await message.reply('❌ Invalid phone number format. Please try again.')
    except PhoneCodeInvalid:
        await message.reply('❌ Invalid OTP code. Please try again.')
    except PhoneCodeExpired:
        await message.reply('❌ OTP code expired. Please request a new one.')
    except FloodWait as e:
        await message.reply(f'❌ Too many attempts. Please wait {e.x} seconds before trying again.')
    except Exception as e:
        logger.error(f"Login error: {e}")
        await message.reply("❌ An unexpected error occurred. Please try again later.")
    finally:
        try:
            await client.disconnect()
        except Exception as e:
            logger.error(f"Error disconnecting client: {e}")
