#!/usr/bin/env python3
"""
Instagram Downloader Telegram Bot
Created by: SWAYAM
Telegram: @regnis

A production-ready Telegram bot that downloads Instagram content:
- Profile pictures from Instagram profiles
- Videos/Audio from Instagram reels
- Handles rate limiting and authentication
- Beautiful emoji-rich interface
"""

import os
import re
import asyncio
import logging
import tempfile
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import aiohttp
import aiofiles
from pathlib import Path

# Telegram Bot imports
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    filters, ContextTypes
)
from telegram.constants import ParseMode

# Instagram content download imports
from instagrapi import Client
import yt_dlp

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration
class Config:
    BOT_TOKEN = os.getenv('BOT_TOKEN', 'YOUR_BOT_TOKEN_HERE')
    INSTAGRAM_USERNAME = os.getenv('INSTAGRAM_USERNAME', '')  # Optional for rate limit bypass
    INSTAGRAM_PASSWORD = os.getenv('INSTAGRAM_PASSWORD', '')  # Optional for rate limit bypass
    WEBHOOK_URL = os.getenv('WEBHOOK_URL', '')  # For keep-alive pings
    PORT = int(os.getenv('PORT', 8000))
    
    # Rate limiting settings
    MAX_REQUESTS_PER_HOUR = 30
    CLEANUP_INTERVAL = 300  # 5 minutes

# Global variables for rate limiting and session management
user_requests: Dict[int, list] = {}
instagram_client: Optional[Client] = None
last_cleanup = datetime.now()

# Emojis for beautiful UI
EMOJIS = {
    'robot': '🤖',
    'instagram': '📸',
    'video': '🎥',
    'audio': '🎵',
    'profile': '👤',
    'download': '⬇️',
    'success': '✅',
    'error': '❌',
    'warning': '⚠️',
    'loading': '⏳',
    'fire': '🔥',
    'star': '⭐',
    'link': '🔗',
    'music': '🎶',
    'camera': '📷'
}

async def setup_instagram_client() -> Optional[Client]:
    """Setup Instagram client with optional authentication for rate limit bypass"""
    global instagram_client
    
    try:
        client = Client()
        
        # If credentials are provided, login to bypass rate limits
        if Config.INSTAGRAM_USERNAME and Config.INSTAGRAM_PASSWORD:
            logger.info("Logging into Instagram with provided credentials...")
            client.login(Config.INSTAGRAM_USERNAME, Config.INSTAGRAM_PASSWORD)
            logger.info("Successfully logged into Instagram")
        
        instagram_client = client
        return client
    except Exception as e:
        logger.error(f"Failed to setup Instagram client: {e}")
        return None

def is_rate_limited(user_id: int) -> bool:
    """Check if user has exceeded rate limits"""
    global user_requests, last_cleanup
    
    # Cleanup old requests every 5 minutes
    now = datetime.now()
    if now - last_cleanup > timedelta(minutes=5):
        cleanup_old_requests()
        last_cleanup = now
    
    if user_id not in user_requests:
        user_requests[user_id] = []
    
    # Remove requests older than 1 hour
    hour_ago = now - timedelta(hours=1)
    user_requests[user_id] = [
        req_time for req_time in user_requests[user_id] 
        if req_time > hour_ago
    ]
    
    # Check if user has exceeded limit
    if len(user_requests[user_id]) >= Config.MAX_REQUESTS_PER_HOUR:
        return True
    
    # Add current request
    user_requests[user_id].append(now)
    return False

def cleanup_old_requests():
    """Clean up old request records to prevent memory leaks"""
    global user_requests
    hour_ago = datetime.now() - timedelta(hours=1)
    
    for user_id in list(user_requests.keys()):
        user_requests[user_id] = [
            req_time for req_time in user_requests[user_id] 
            if req_time > hour_ago
        ]
        
        # Remove empty lists
        if not user_requests[user_id]:
            del user_requests[user_id]

def extract_instagram_info(url: str) -> Dict[str, Any]:
    """Extract Instagram URL information and determine content type"""
    # Instagram URL patterns
    patterns = {
        'profile': r'instagram\.com/([^/]+)/?$',
        'reel': r'instagram\.com/reel/([^/]+)',
        'post': r'instagram\.com/p/([^/]+)',
        'story': r'instagram\.com/stories/([^/]+)/([^/]+)'
    }
    
    for content_type, pattern in patterns.items():
        match = re.search(pattern, url)
        if match:
            return {
                'type': content_type,
                'id': match.group(1),
                'url': url
            }
    
    return {'type': 'unknown', 'id': None, 'url': url}

async def safe_delete_file(file_path: str):
    """Safely delete a file with error handling"""
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"Deleted file: {file_path}")
    except Exception as e:
        logger.error(f"Failed to delete file {file_path}: {e}")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    welcome_message = f"""{EMOJIS['robot']} **Welcome to Instagram Downloader Bot!**

{EMOJIS['fire']} **What I can do:**
{EMOJIS['profile']} Download profile pictures from Instagram profiles
{EMOJIS['video']} Download videos from Instagram reels
{EMOJIS['audio']} Extract audio from Instagram reels
{EMOJIS['camera']} Send captions and media information

{EMOJIS['link']} **How to use:**
Just send me any Instagram URL and I'll handle the rest!

{EMOJIS['star']} **Created by:** SWAYAM
{EMOJIS['link']} **Contact:** [Developer](tg://user?id=regnis)

{EMOJIS['warning']} **Note:** This bot respects Instagram's terms of service and implements rate limiting."""
    
    await update.message.reply_text(
        welcome_message,
        parse_mode=ParseMode.MARKDOWN,
        disable_web_page_preview=True
    )

async def download_profile_picture(username: str) -> Optional[str]:
    """Download Instagram profile picture"""
    global instagram_client
    
    try:
        if not instagram_client:
            # Fallback to yt-dlp for profile pictures
            return await download_with_ytdlp(f"https://instagram.com/{username}")
        
        # Get user info
        user_info = instagram_client.user_info_by_username(username)
        profile_pic_url = user_info.profile_pic_url_hd or user_info.profile_pic_url
        
        if not profile_pic_url:
            return None
        
        # Download profile picture
        temp_dir = tempfile.gettempdir()
        filename = f"profile_{username}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        file_path = os.path.join(temp_dir, filename)
        
        async with aiohttp.ClientSession() as session:
            async with session.get(profile_pic_url) as response:
                if response.status == 200:
                    async with aiofiles.open(file_path, 'wb') as f:
                        async for chunk in response.content.iter_chunked(8192):
                            await f.write(chunk)
                    return file_path
        
        return None
    except Exception as e:
        logger.error(f"Failed to download profile picture for {username}: {e}")
        return None

async def download_with_ytdlp(url: str, audio_only: bool = False) -> Optional[Dict[str, Any]]:
    """Download Instagram content using yt-dlp"""
    try:
        temp_dir = tempfile.gettempdir()
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        ydl_opts = {
            'outtmpl': os.path.join(temp_dir, f'instagram_{timestamp}.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
        }
        
        if audio_only:
            ydl_opts.update({
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }]
            })
        else:
            ydl_opts['format'] = 'best[height<=720]'
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            
            # Find the downloaded file
            downloaded_file = None
            for file in os.listdir(temp_dir):
                if file.startswith(f'instagram_{timestamp}'):
                    downloaded_file = os.path.join(temp_dir, file)
                    break
            
            return {
                'file_path': downloaded_file,
                'title': info.get('title', 'Instagram Content'),
                'description': info.get('description', ''),
                'uploader': info.get('uploader', ''),
                'duration': info.get('duration', 0)
            }
    
    except Exception as e:
        logger.error(f"Failed to download with yt-dlp: {e}")
        return None

async def handle_instagram_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle Instagram URL messages"""
    user_id = update.effective_user.id
    message_text = update.message.text
    
    # Check rate limiting
    if is_rate_limited(user_id):
        await update.message.reply_text(
            f"{EMOJIS['warning']} **Rate limit exceeded!**\n\n"
            f"You can only make {Config.MAX_REQUESTS_PER_HOUR} requests per hour. "
            f"Please try again later.",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # Extract Instagram URL
    instagram_urls = re.findall(r'https?://(?:www\.)?instagram\.com/[^\s]+', message_text)
    
    if not instagram_urls:
        await update.message.reply_text(
            f"{EMOJIS['error']} **No valid Instagram URL found!**\n\n"
            f"Please send a valid Instagram URL.",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    url = instagram_urls[0]
    info = extract_instagram_info(url)
    
    # Send processing message
    processing_msg = await update.message.reply_text(
        f"{EMOJIS['loading']} **Processing your request...**\n\n"
        f"{EMOJIS['link']} URL: `{url}`\n"
        f"{EMOJIS['instagram']} Type: {info['type'].title()}",
        parse_mode=ParseMode.MARKDOWN
    )
    
    try:
        if info['type'] == 'profile':
            await handle_profile_download(update, context, info, processing_msg)
        elif info['type'] in ['reel', 'post']:
            await handle_reel_download(update, context, info, processing_msg)
        else:
            await processing_msg.edit_text(
                f"{EMOJIS['error']} **Unsupported content type!**\n\n"
                f"I can only download profile pictures and reels/posts.",
                parse_mode=ParseMode.MARKDOWN
            )
    
    except Exception as e:
        logger.error(f"Error handling Instagram URL: {e}")
        await processing_msg.edit_text(
            f"{EMOJIS['error']} **An error occurred!**\n\n"
            f"Please try again later or contact support.",
            parse_mode=ParseMode.MARKDOWN
        )

async def handle_profile_download(update: Update, context: ContextTypes.DEFAULT_TYPE, 
                                info: Dict[str, Any], processing_msg):
    """Handle profile picture download"""
    username = info['id']
    
    # Download profile picture
    file_path = await download_profile_picture(username)
    
    if file_path and os.path.exists(file_path):
        try:
            # Send profile picture
            with open(file_path, 'rb') as photo:
                await update.message.reply_photo(
                    photo=photo,
                    caption=f"{EMOJIS['success']} **Profile Picture Downloaded!**\n\n"
                           f"{EMOJIS['profile']} **Username:** @{username}\n"
                           f"{EMOJIS['link']} **Profile:** [View on Instagram]({info['url']})",
                    parse_mode=ParseMode.MARKDOWN
                )
            
            await processing_msg.delete()
            
        finally:
            # Clean up file
            await safe_delete_file(file_path)
    else:
        await processing_msg.edit_text(
            f"{EMOJIS['error']} **Failed to download profile picture!**\n\n"
            f"The profile might be private or the URL is invalid.",
            parse_mode=ParseMode.MARKDOWN
        )

async def handle_reel_download(update: Update, context: ContextTypes.DEFAULT_TYPE, 
                             info: Dict[str, Any], processing_msg):
    """Handle reel/post download with format selection"""
    # Create inline keyboard for format selection
    keyboard = [
        [
            InlineKeyboardButton(f"{EMOJIS['video']} Video", callback_data=f"video_{info['id']}"),
            InlineKeyboardButton(f"{EMOJIS['audio']} Audio Only", callback_data=f"audio_{info['id']}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await processing_msg.edit_text(
        f"{EMOJIS['download']} **Choose download format:**\n\n"
        f"{EMOJIS['video']} **Video:** Download the full video\n"
        f"{EMOJIS['audio']} **Audio Only:** Extract audio as MP3\n\n"
        f"{EMOJIS['link']} URL: `{info['url']}`",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )
    
    # Store URL in context for callback
    context.user_data[f"url_{info['id']}"] = info['url']

async def handle_format_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle format selection callback"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    format_type, content_id = data.split('_', 1)
    
    # Get URL from context
    url_key = f"url_{content_id}"
    if url_key not in context.user_data:
        await query.edit_message_text(
            f"{EMOJIS['error']} **Session expired!**\n\n"
            f"Please send the Instagram URL again.",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    url = context.user_data[url_key]
    audio_only = format_type == 'audio'
    
    # Update message to show downloading status
    await query.edit_message_text(
        f"{EMOJIS['loading']} **Downloading {format_type}...**\n\n"
        f"Please wait while I process your request.",
        parse_mode=ParseMode.MARKDOWN
    )
    
    try:
        # Download content
        result = await download_with_ytdlp(url, audio_only)
        
        if result and result['file_path'] and os.path.exists(result['file_path']):
            try:
                # Prepare caption
                caption = f"{EMOJIS['success']} **Download Complete!**\n\n"
                
                if result.get('title'):
                    caption += f"{EMOJIS['camera']} **Title:** {result['title'][:100]}...\n"
                
                if result.get('uploader'):
                    caption += f"{EMOJIS['profile']} **Creator:** {result['uploader']}\n"
                
                if result.get('duration'):
                    duration_min = result['duration'] // 60
                    duration_sec = result['duration'] % 60
                    caption += f"{EMOJIS['video']} **Duration:** {duration_min}:{duration_sec:02d}\n"
                
                caption += f"\n{EMOJIS['link']} **Source:** [Instagram]({url})"
                
                # Send file
                with open(result['file_path'], 'rb') as file:
                    if audio_only:
                        await query.message.reply_audio(
                            audio=file,
                            caption=caption,
                            parse_mode=ParseMode.MARKDOWN
                        )
                    else:
                        await query.message.reply_video(
                            video=file,
                            caption=caption,
                            parse_mode=ParseMode.MARKDOWN
                        )
                
                await query.delete_message()
                
            finally:
                # Clean up file
                await safe_delete_file(result['file_path'])
        else:
            await query.edit_message_text(
                f"{EMOJIS['error']} **Download failed!**\n\n"
                f"The content might be private, deleted, or temporarily unavailable.",
                parse_mode=ParseMode.MARKDOWN
            )
    
    except Exception as e:
        logger.error(f"Error in format callback: {e}")
        await query.edit_message_text(
            f"{EMOJIS['error']} **An error occurred during download!**\n\n"
            f"Please try again later.",
            parse_mode=ParseMode.MARKDOWN
        )
    
    finally:
        # Clean up context
        if url_key in context.user_data:
            del context.user_data[url_key]

async def keep_alive_ping():
    """Send periodic pings to keep the bot alive on free hosting"""
    if not Config.WEBHOOK_URL:
        return
    
    while True:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(Config.WEBHOOK_URL, timeout=10) as response:
                    logger.info(f"Keep-alive ping sent. Status: {response.status}")
        except Exception as e:
            logger.error(f"Keep-alive ping failed: {e}")
        
        # Wait 5 minutes before next ping
        await asyncio.sleep(300)

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors"""
    logger.error(f"Update {update} caused error {context.error}")
    
    if update and update.effective_message:
        await update.effective_message.reply_text(
            f"{EMOJIS['error']} **An unexpected error occurred!**\n\n"
            f"Please try again later or contact support.",
            parse_mode=ParseMode.MARKDOWN
        )

def main():
    """Main function to run the bot"""
    if not Config.BOT_TOKEN or Config.BOT_TOKEN == 'YOUR_BOT_TOKEN_HERE':
        logger.error("BOT_TOKEN not set! Please set your bot token in environment variables.")
        return
    
    # Create application
    application = Application.builder().token(Config.BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(MessageHandler(
        filters.TEXT & filters.Regex(r'instagram\.com'), 
        handle_instagram_url
    ))
    application.add_handler(CallbackQueryHandler(
        handle_format_callback, 
        pattern=r'^(video|audio)_'
    ))
    
    # Add error handler
    application.add_error_handler(error_handler)
    
    # Setup Instagram client
    async def post_init(application: Application):
    # Setup Instagram client inside the running loop
    await setup_instagram_client()

    # Start keep-alive task if webhook URL is provided
    if Config.WEBHOOK_URL:
        application.create_task(keep_alive_ping())

# Pass post_init into Application.builder()
application = Application.builder().token(Config.BOT_TOKEN).post_init(post_init).build()

    
    logger.info("Starting Instagram Downloader Bot...")
    
    # Run the bot
    if Config.WEBHOOK_URL:
        # For production with webhook
        application.run_webhook(
            listen="0.0.0.0",
            port=Config.PORT,
            webhook_url=Config.WEBHOOK_URL
        )
    else:
        # For development with polling
        application.run_polling()

if __name__ == '__main__':
    main()
