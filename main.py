import asyncio
import logging
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

import requests
import yt_dlp
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from flask import Flask, jsonify
import threading

# Configure logging with beautiful formatting
logging.basicConfig(
    format='🚀 %(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot Configuration
BOT_TOKEN = os.getenv('BOT_TOKEN')
REPL_URL = os.getenv('REPL_URL', 'https://your-repl-name.username.repl.co')

# Flask app for health endpoint
app = Flask(__name__)

@app.route('/health')
def health_check():
    """Health endpoint for keep-alive pings"""
    return jsonify({"status": "✅ Bot is alive", "timestamp": datetime.now().isoformat()})

def run_flask():
    """Run Flask in a separate thread"""
    app.run(host='0.0.0.0', port=8080, debug=False)

class InstagramTelegramBot:
    def __init__(self):
        self.downloads_dir = Path("downloads")
        self.downloads_dir.mkdir(exist_ok=True)
        self.user_sessions: Dict[int, Dict[str, Any]] = {}
        self.session_timeout = 300  # 5 minutes
        
    def extract_instagram_info(self, text: str) -> Optional[tuple]:
        """Extract Instagram URL and determine type"""
        patterns = {
            'profile': r'https?://(?:www\.)?instagram\.com/([^/?#]+)/?(?:\?.*)?$',
            'post': r'https?://(?:www\.)?instagram\.com/p/([^/?#]+)/?(?:\?.*)?',
            'reel': r'https?://(?:www\.)?instagram\.com/reel/([^/?#]+)/?(?:\?.*)?',
            'story': r'https?://(?:www\.)?instagram\.com/stories/([^/?#]+)/([^/?#]+)/?(?:\?.*)?'
        }
        
        for url_type, pattern in patterns.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(0), url_type
        
        return None
    
    def is_session_valid(self, user_id: int) -> bool:
        """Check if user session is still valid"""
        if user_id not in self.user_sessions:
            return False
        
        session_time = self.user_sessions[user_id].get('timestamp', 0)
        return (time.time() - session_time) < self.session_timeout
    
    def create_session(self, user_id: int, url: str, url_type: str) -> None:
        """Create a new user session"""
        self.user_sessions[user_id] = {
            'url': url,
            'url_type': url_type,
            'timestamp': time.time()
        }
    
    def clear_session(self, user_id: int) -> None:
        """Clear user session"""
        self.user_sessions.pop(user_id, None)
    
    async def safe_delete_file(self, filepath: str) -> None:
        """Safely delete a file with error handling"""
        try:
            if filepath and os.path.exists(filepath):
                os.remove(filepath)
                logger.info(f"🗑️ Successfully deleted: {filepath}")
        except Exception as e:
            logger.error(f"❌ Error deleting file {filepath}: {e}")
    
    async def download_with_ytdlp(self, url: str, audio_only: bool = False) -> tuple[Optional[str], str, Optional[str]]:
        """Download Instagram content using yt-dlp"""
        timestamp = int(time.time())
        filepath = None
        
        try:
            if audio_only:
                ydl_opts = {
                    'format': 'bestaudio/best',
                    'outtmpl': str(self.downloads_dir / f'audio_{timestamp}.%(ext)s'),
                    'quiet': True,
                    'no_warnings': True,
                    'extractaudio': True,
                    'audioformat': 'mp3',
                    'audioquality': '192',
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '192',
                    }],
                }
            else:
                ydl_opts = {
                    'format': 'best[ext=mp4]/best',
                    'outtmpl': str(self.downloads_dir / f'media_{timestamp}.%(ext)s'),
                    'quiet': True,
                    'no_warnings': True,
                }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Extract info first
                info = ydl.extract_info(url, download=False)
                
                # Check if content is available
                if info.get('availability') == 'private':
                    return None, "🔒 This account/content is private and cannot be downloaded.", None
                
                # Download the content
                ydl.download([url])
                
                # Get metadata
                title = info.get('title', '')
                description = info.get('description', '')
                uploader = info.get('uploader', '')
                
                # Create caption
                caption_parts = []
                if uploader:
                    caption_parts.append(f"👤 **{uploader}**")
                if title and title != uploader:
                    caption_parts.append(f"📝 {title}")
                if description and description != title:
                    # Truncate description if too long
                    desc = description[:200] + "..." if len(description) > 200 else description
                    caption_parts.append(f"💬 {desc}")
                
                caption = "\n\n".join(caption_parts) if caption_parts else None
                
                # Find downloaded file
                file_pattern = f"{'audio' if audio_only else 'media'}_{timestamp}.*"
                for file_path in self.downloads_dir.glob(file_pattern):
                    return str(file_path), "✅ Download successful!", caption
                
                return None, "❌ Download completed but file not found.", None
                
        except yt_dlp.DownloadError as e:
            error_msg = str(e).lower()
            if 'private' in error_msg or 'not available' in error_msg:
                return None, "🔒 This account/content is private and cannot be downloaded.", None
            return None, f"❌ Download failed: {str(e)}", None
        except Exception as e:
            logger.error(f"❌ Download error: {e}")
            return None, f"❌ An error occurred during download: {str(e)}", None

# Initialize bot instance
bot = InstagramTelegramBot()

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command with beautiful formatting"""
    welcome_message = """
🎬✨ **Instagram Media Downloader Bot** ✨🎬

🌟 **What I can do for you:**
📸 Download Instagram profile pictures
🎥 Download Instagram reels & posts  
🎵 Extract audio from videos
📝 Get captions & descriptions
🚀 Lightning-fast downloads

💡 **How to use:**
Just send me any Instagram link and watch the magic happen! ✨

📱 **Supported Links:**
🔗 Profile URLs → Profile picture
🎬 Reel URLs → Video or Audio choice
📷 Post URLs → Media content

---
✨ **Created with ❤️ by:** SWAYAM  
📞 [Contact Developer](https://t.me/regnis)

🎯 **Ready to download? Send me an Instagram link!** 🚀
"""
    
    await update.message.reply_text(
        welcome_message,
        parse_mode=ParseMode.MARKDOWN,
        disable_web_page_preview=True
    )

async def handle_instagram_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle messages containing Instagram URLs"""
    user_id = update.effective_user.id
    message_text = update.message.text
    
    # Extract Instagram URL and type
    instagram_info = bot.extract_instagram_info(message_text)
    
    if not instagram_info:
        await update.message.reply_text(
            "❌🔗 **Invalid Instagram URL!**\n\n"
            "✅ **Supported formats:**\n"
            "📸 Profile: `instagram.com/username`\n"
            "🎥 Reel: `instagram.com/reel/xxx`\n"
            "📷 Post: `instagram.com/p/xxx`\n\n"
            "💡 Please send a valid Instagram link! 🚀",
            parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=True
        )
        return
    
    url, url_type = instagram_info
    
    # Send initial processing message
    processing_msg = await update.message.reply_text(
        f"⏳✨ **Processing your request...**\n"
        f"🔍 Analyzing {url_type} URL\n"
        f"🚀 Please wait a moment!",
        parse_mode=ParseMode.MARKDOWN
    )
    
    try:
        if url_type == 'profile':
            await handle_profile_download(update, processing_msg, url)
        elif url_type in ['reel', 'post']:
            await handle_media_choice(update, processing_msg, url, url_type, user_id)
        else:
            await processing_msg.edit_text(
                "❌🚫 **Unsupported Content Type**\n\n"
                "This type of Instagram content is not supported yet.\n"
                "💡 Try profile, reel, or post URLs! 🎯",
                parse_mode=ParseMode.MARKDOWN
            )
    except Exception as e:
        logger.error(f"❌ Error handling message: {e}")
        await processing_msg.edit_text(
            f"💥 **Oops! Something went wrong**\n\n"
            f"❌ Error: `{str(e)}`\n"
            f"🔄 Please try again or contact support! 💪",
            parse_mode=ParseMode.MARKDOWN
        )

async def handle_profile_download(update: Update, processing_msg, url: str) -> None:
    """Handle Instagram profile picture download"""
    filepath = None
    
    try:
        await processing_msg.edit_text(
            "📸✨ **Downloading Profile Picture...**\n"
            "🔍 Fetching high-quality image\n"
            "⏳ Almost ready!",
            parse_mode=ParseMode.MARKDOWN
        )
        
        filepath, status_msg, caption = await bot.download_with_ytdlp(url)
        
        if filepath and os.path.exists(filepath):
            # Send the profile picture
            with open(filepath, 'rb') as photo:
                caption_text = f"📸✨ **Profile Picture Downloaded!**\n\n{caption}" if caption else "📸✨ **Profile Picture Downloaded!**"
                await update.message.reply_photo(
                    photo=photo,
                    caption=caption_text,
                    parse_mode=ParseMode.MARKDOWN
                )
            
            await processing_msg.delete()
            
        else:
            await processing_msg.edit_text(
                f"🔒💔 **Download Failed**\n\n{status_msg}\n\n"
                "💡 **Possible reasons:**\n"
                "🔐 Private account\n"
                "🚫 Content not accessible\n"
                "🌐 Network issues",
                parse_mode=ParseMode.MARKDOWN
            )
    
    except Exception as e:
        logger.error(f"❌ Profile download error: {e}")
        await processing_msg.edit_text(
            f"💥 **Profile Download Failed**\n\n"
            f"❌ Error: `{str(e)}`\n"
            f"🔄 Please try again! 💪",
            parse_mode=ParseMode.MARKDOWN
        )
    
    finally:
        if filepath:
            await bot.safe_delete_file(filepath)

async def handle_media_choice(update: Update, processing_msg, url: str, url_type: str, user_id: int) -> None:
    """Handle media download with format choice"""
    try:
        # Create user session
        bot.create_session(user_id, url, url_type)
        
        # Create inline keyboard
        keyboard = [
            [
                InlineKeyboardButton("🎥✨ Video", callback_data=f"video_{user_id}"),
                InlineKeyboardButton("🎵🔥 Audio Only", callback_data=f"audio_{user_id}")
            ],
            [InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_{user_id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        content_type = "🎬 Reel" if url_type == 'reel' else "📷 Post"
        
        await processing_msg.edit_text(
            f"🎯✨ **{content_type} Detected!**\n\n"
            f"📥 **Choose your download format:**\n"
            f"🎥 Video → Full quality video\n"
            f"🎵 Audio → MP3 audio only\n\n"
            f"⚡ **Click below to proceed!** 🚀",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"❌ Media choice error: {e}")
        await processing_msg.edit_text(
            f"💥 **Error Creating Options**\n\n"
            f"❌ Error: `{str(e)}`\n"
            f"🔄 Please try sending the link again! 💪",
            parse_mode=ParseMode.MARKDOWN
        )

async def handle_button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline keyboard button callbacks"""
    query = update.callback_query
    user_id = update.effective_user.id
    
    await query.answer()
    
    # Check session validity
    if not bot.is_session_valid(user_id):
        await query.edit_message_text(
            "⏰💔 **Session Expired!**\n\n"
            "❌ Your download session has expired.\n"
            "🔄 Please send the Instagram link again to start fresh! 🚀",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # Parse callback data
    action, callback_user_id = query.data.split('_', 1)
    callback_user_id = int(callback_user_id)
    
    if user_id != callback_user_id:
        await query.answer("❌ This button is not for you!", show_alert=True)
        return
    
    session = bot.user_sessions[user_id]
    url = session['url']
    url_type = session['url_type']
    
    if action == 'cancel':
        bot.clear_session(user_id)
        await query.edit_message_text(
            "❌🚫 **Download Cancelled**\n\n"
            "🔄 Send another Instagram link to try again! 🚀",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # Handle download
    audio_only = action == 'audio'
    format_emoji = "🎵" if audio_only else "🎥"
    format_text = "Audio" if audio_only else "Video"
    
    await query.edit_message_text(
        f"⏳{format_emoji} **Downloading {format_text}...**\n\n"
        f"🔄 Processing your request\n"
        f"📦 Preparing download\n"
        f"⚡ Almost ready!",
        parse_mode=ParseMode.MARKDOWN
    )
    
    filepath = None
    
    try:
        filepath, status_msg, caption = await bot.download_with_ytdlp(url, audio_only)
        
        if filepath and os.path.exists(filepath):
            # Send the file
            with open(filepath, 'rb') as file:
                caption_text = f"{format_emoji}✅ **{format_text} Downloaded Successfully!**"
                if caption:
                    caption_text += f"\n\n{caption}"
                
                if audio_only:
                    await query.message.reply_audio(
                        audio=file,
                        caption=caption_text[:1024],  # Telegram limit
                        parse_mode=ParseMode.MARKDOWN
                    )
                else:
                    await query.message.reply_video(
                        video=file,
                        caption=caption_text[:1024],  # Telegram limit
                        parse_mode=ParseMode.MARKDOWN,
                        supports_streaming=True
                    )
            
            await query.delete_message()
            
        else:
            await query.edit_message_text(
                f"🔒💔 **Download Failed**\n\n{status_msg}\n\n"
                "💡 **Possible reasons:**\n"
                "🔐 Private content\n"
                "🚫 Content unavailable\n"
                "🌐 Network issues\n\n"
                "🔄 Try again or contact support! 💪",
                parse_mode=ParseMode.MARKDOWN
            )
    
    except Exception as e:
        logger.error(f"❌ Button callback error: {e}")
        await query.edit_message_text(
            f"💥 **Download Failed**\n\n"
            f"❌ Error: `{str(e)}`\n"
            f"🔄 Please try again! 💪",
            parse_mode=ParseMode.MARKDOWN
        )
    
    finally:
        # Clean up
        bot.clear_session(user_id)
        if filepath:
            await bot.safe_delete_file(filepath)

async def keep_alive_task():
    """Background task to keep the bot alive on Replit"""
    while True:
        try:
            await asyncio.sleep(300)  # 5 minutes
            
            if REPL_URL:
                response = requests.get(f"{REPL_URL}/health", timeout=10)
                current_time = datetime.now().strftime("%H:%M:%S")
                
                if response.status_code == 200:
                    logger.info(f"💚 Keep-alive successful at {current_time}")
                else:
                    logger.warning(f"⚠️ Keep-alive returned {response.status_code} at {current_time}")
            
        except Exception as e:
            logger.error(f"❌ Keep-alive error: {e}")

def main() -> None:
    """Main function to start the bot"""
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN environment variable is required!")
        return
    
    # Start Flask server in background thread
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info("🌐 Flask health endpoint started on port 8080")
    
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_instagram_message))
    application.add_handler(CallbackQueryHandler(handle_button_callback))
    
    # Start keep-alive task
    asyncio.create_task(keep_alive_task())
    
    # Start bot
    logger.info("🚀✨ Instagram Telegram Bot is running! ✨🚀")
    logger.info("🎯 Ready to process Instagram downloads!")
    
    application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()