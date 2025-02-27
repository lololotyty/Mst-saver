# ---------------------------------------------------
# File Name: ytdl.py
# Description: YouTube downloader module
# ---------------------------------------------------

import yt_dlp
import os
import tempfile
import time
import asyncio
import random
import string
import requests
import logging
import cv2
import aiohttp
import aiofiles
from concurrent.futures import ThreadPoolExecutor
from devgagan import sex as client, app
from pyrogram import Client, filters
from telethon import events
from telethon.sync import TelegramClient
from telethon.tl.types import DocumentAttributeVideo
from devgagan.core.func import screenshot, video_metadata, progress_bar
from telethon.tl.functions.messages import EditMessageRequest
from devgagantools import fast_upload
from mutagen.id3 import ID3, TIT2, TPE1, COMM, APIC
from mutagen.mp3 import MP3

logger = logging.getLogger(__name__)
thread_pool = ThreadPoolExecutor()
ongoing_downloads = {}

def d_thumbnail(thumbnail_url, save_path):
    try:
        if not thumbnail_url:
            return None
            
        response = requests.get(thumbnail_url, stream=True, timeout=10)
        response.raise_for_status()
        
        with open(save_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        
        # Verify the thumbnail was saved properly
        if os.path.exists(save_path) and os.path.getsize(save_path) > 0:
            return save_path
        return None
        
    except (requests.exceptions.RequestException, IOError) as e:
        logger.error(f"Failed to download thumbnail: {e}")
        if os.path.exists(save_path):
            os.remove(save_path)
        return None

async def process_video(client, event, url, cookies_env_var, check_duration_and_size=False):
    start_time = time.time()
    logger.info(f"Received link: {url}")
    
    cookies = None
    if cookies_env_var:
        cookies = os.getenv(cookies_env_var)

    random_filename = get_random_string() + ".mp4"
    download_path = os.path.abspath(random_filename)
    logger.info(f"Generated random download path: {download_path}")

    temp_cookie_path = None
    if cookies:
        with tempfile.NamedTemporaryFile(delete=False, mode='w', suffix='.txt') as temp_cookie_file:
            temp_cookie_file.write(cookies)
            temp_cookie_path = temp_cookie_file.name
        logger.info(f"Created temporary cookie file at: {temp_cookie_path}")

    thumbnail_file = None
    THUMB = None
    thumb_path = None
    metadata = {'width': None, 'height': None, 'duration': None, 'thumbnail': None}

    ydl_opts = {
        'outtmpl': download_path,
        'format': 'best',
        'cookiefile': temp_cookie_path if temp_cookie_path else None,
        'writethumbnail': True,
        'verbose': True,
    }
    
    progress_message = await event.reply("**__Starting download...__**")
    logger.info("Starting the download process...")
    
    try:
        info_dict = await fetch_video_info(url, ydl_opts, progress_message, check_duration_and_size)
        if not info_dict:
            return
            
        await asyncio.to_thread(download_video, url, ydl_opts)
        title = info_dict.get('title', 'Powered by Shimperd')
        
        # Get video metadata
        k = video_metadata(download_path)
        metadata['width'] = info_dict.get('width') or k['width']
        metadata['height'] = info_dict.get('height') or k['height']
        metadata['duration'] = int(info_dict.get('duration') or 0) or k['duration']
        
        # Handle thumbnail
        thumbnail_url = info_dict.get('thumbnail')
        if thumbnail_url:
            thumb_path = os.path.join(tempfile.gettempdir(), get_random_string() + ".jpg")
            thumbnail_file = d_thumbnail(thumbnail_url, thumb_path)
            if thumbnail_file:
                logger.info(f"Thumbnail saved at: {thumbnail_file}")
                THUMB = thumbnail_file
        
        if not THUMB:
            THUMB = await screenshot(download_path, metadata['duration'], event.sender_id)

        # Upload process
        chat_id = event.chat_id
        SIZE = 2 * 1024 * 1024
        caption = f"{title}"

        if os.path.exists(download_path) and os.path.getsize(download_path) > SIZE:
            prog = await client.send_message(chat_id, "**__Starting Upload...__**")
            await split_and_upload_file(app, chat_id, download_path, caption)
            await prog.delete()
        
        if os.path.exists(download_path):
            await progress_message.delete()
            prog = await client.send_message(chat_id, "**__Starting Upload...__**")
            uploaded = await fast_upload(
                client, download_path,
                reply=prog,
                progress_bar_function=lambda done, total: progress_callback(done, total, chat_id)
            )
            await client.send_file(
                event.chat_id,
                uploaded,
                caption=f"**{title}**",
                attributes=[
                    DocumentAttributeVideo(
                        duration=metadata['duration'],
                        w=metadata['width'],
                        h=metadata['height'],
                        supports_streaming=True
                    )
                ],
                thumb=THUMB if THUMB else None
            )
            if prog:
                await prog.delete()
        else:
            await event.reply("**__File not found after download. Something went wrong!__**")
            
    except Exception as e:
        logger.exception("An error occurred during download or upload.")
        await event.reply(f"**__An error occurred: {e}__**")
    finally:
        # Cleanup files
        for file_path in [download_path, temp_cookie_path, thumb_path, thumbnail_file]:
            if file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception as e:
                    logger.error(f"Error removing file {file_path}: {e}")

async def split_and_upload_file(app, sender, file, caption):
    if not os.path.exists(file):
        await app.send_message(sender, "❌ File not found!")
        return

    file_size = os.path.getsize(file)
    start = await app.send_message(sender, f"ℹ️ File size: {file_size / (1024 * 1024):.2f} MB")
    PART_SIZE = 1.9 * 1024 * 1024 * 1024

    part_number = 0
    async with aiofiles.open(file, mode="rb") as f:
        while True:
            chunk = await f.read(PART_SIZE)
            if not chunk:
                break

            base_name, file_ext = os.path.splitext(file)
            part_file = f"{base_name}.part{str(part_number).zfill(3)}{file_ext}"

            async with aiofiles.open(part_file, mode="wb") as part_f:
                await part_f.write(chunk)

            edit = await app.send_message(sender, f"⬆️ Uploading part {part_number + 1}...")
            part_caption = f"{caption} \n\n**Part : {part_number + 1}**"
            
            await app.send_document(
                sender, 
                document=part_file, 
                caption=part_caption,
                progress=progress_bar,
                progress_args=(
                    "╭─────────────────────╮\n│      **__Pyro Uploader__**\n├─────────────────────",
                    edit,
                    time.time()
                )
            )
            
            await edit.delete()
            os.remove(part_file)
            part_number += 1

    await start.delete()
    os.remove(file)
