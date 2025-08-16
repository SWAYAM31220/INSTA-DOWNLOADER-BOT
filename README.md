# 📸 Instagram Downloader Telegram Bot

> A production-ready Telegram bot that downloads Instagram content with beautiful emoji-rich interface and rate limiting protection.

**Created by:** SWAYAM  
**Contact:** [@regnis](https://t.me/regnis)

## 🌟 Features

- 📷 **Profile Pictures**: Download high-quality profile pictures from Instagram profiles
- 🎥 **Reels & Posts**: Download videos from Instagram reels and posts
- 🎵 **Audio Extraction**: Extract audio from videos as MP3 files
- 📝 **Captions**: Always includes media captions and information
- 🛡️ **Rate Limiting**: Built-in protection against Instagram rate limits
- 🔐 **Authentication**: Optional Instagram login for enhanced access
- 💎 **Beautiful UI**: Emoji-rich interface with inline keyboards
- 🚀 **Keep Alive**: Auto-ping functionality for free hosting platforms
- 🗑️ **Auto Cleanup**: Automatically deletes files after sending

## 🛠️ Tech Stack

- **Python 3.8+**
- **python-telegram-bot**: Telegram Bot API wrapper
- **instagrapi**: Instagram private API client
- **yt-dlp**: Universal video downloader
- **aiohttp**: Async HTTP client
- **Railway.app**: Recommended hosting platform

## 📋 Prerequisites

1. **Python 3.8 or higher**
2. **Telegram Bot Token** (from [@BotFather](https://t.me/BotFather))
3. **Instagram Account** (optional, for rate limit bypass)
4. **FFmpeg** (for audio extraction)

## 🚀 Quick Setup

### 1. Clone the Repository
```bash
git clone <your-repo-url>
cd INSTA-DOWNLOADER
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Install FFmpeg

**Windows:**
- Download from [FFmpeg official site](https://ffmpeg.org/download.html)
- Add to PATH environment variable

**macOS:**
```bash
brew install ffmpeg
```

**Linux:**
```bash
sudo apt update
sudo apt install ffmpeg
```

### 4. Configure Environment Variables

1. Copy the example environment file:
```bash
cp .env.example .env
```

2. Edit `.env` with your credentials:
```env
BOT_TOKEN=your_telegram_bot_token_here
INSTAGRAM_USERNAME=your_instagram_username  # Optional
INSTAGRAM_PASSWORD=your_instagram_password  # Optional
WEBHOOK_URL=https://your-app-name.railway.app  # For production
PORT=8000
```

### 5. Run the Bot

**Development (Polling):**
```bash
python instagram_bot.py
```

**Production (Webhook):**
Set `WEBHOOK_URL` in your environment and deploy to a hosting platform.

## 🌐 Deployment on Railway.app

### 1. Prepare for Deployment

1. Create a `Procfile`:
```
web: python instagram_bot.py
```

2. Create `runtime.txt`:
```
python-3.11.0
```

### 2. Deploy to Railway

1. **Connect Repository:**
   - Go to [Railway.app](https://railway.app)
   - Create new project from GitHub repo

2. **Set Environment Variables:**
   - Add all variables from `.env.example`
   - Set `WEBHOOK_URL` to your Railway app URL

3. **Deploy:**
   - Railway will automatically deploy your bot
   - Monitor logs for any issues

## 📱 Usage

### Commands

- `/start` - Get welcome message and instructions

### Supported URLs

- **Profile Pictures**: `https://instagram.com/username`
- **Reels**: `https://instagram.com/reel/ABC123`
- **Posts**: `https://instagram.com/p/ABC123`

### How to Use

1. **Start the bot**: Send `/start` to get instructions
2. **Send Instagram URL**: Paste any supported Instagram URL
3. **Choose format** (for reels): Select video or audio-only
4. **Download**: Bot will process and send your content

## ⚙️ Configuration

### Rate Limiting

- **Default**: 30 requests per hour per user
- **Cleanup**: Every 5 minutes
- **Bypass**: Use Instagram credentials for higher limits

### File Management

- **Auto-deletion**: Files are deleted immediately after sending
- **Temp directory**: Uses system temp folder
- **Cleanup**: Automatic cleanup of old request records

### Keep Alive

- **Interval**: Every 5 minutes
- **Purpose**: Prevents free hosting platforms from sleeping
- **Requirement**: Set `WEBHOOK_URL` environment variable

## 🔧 Advanced Configuration

### Custom Rate Limits

Modify in `instagram_bot.py`:
```python
class Config:
    MAX_REQUESTS_PER_HOUR = 50  # Increase limit
    CLEANUP_INTERVAL = 600      # 10 minutes
```

### Instagram Authentication

For better rate limits and access to more content:
1. Set `INSTAGRAM_USERNAME` and `INSTAGRAM_PASSWORD`
2. Bot will automatically login on startup
3. Handles session management and rate limiting

## 🐛 Troubleshooting

### Common Issues

1. **"Rate limit exceeded"**
   - Wait for the rate limit to reset (1 hour)
   - Add Instagram credentials for higher limits

2. **"Failed to download"**
   - Check if the content is public
   - Verify the URL is correct
   - Try again later

3. **"FFmpeg not found"**
   - Install FFmpeg and add to PATH
   - Restart the bot after installation

4. **Bot not responding**
   - Check bot token is correct
   - Verify internet connection
   - Check Railway logs for errors

### Logs

The bot provides detailed logging:
- **INFO**: Normal operations
- **ERROR**: Failed operations
- **DEBUG**: Detailed debugging info

## 📄 License

This project is for educational purposes. Please respect Instagram's Terms of Service and use responsibly.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📞 Support

- **Creator**: SWAYAM
- **Telegram**: [@regnis](https://t.me/regnis)
- **Issues**: Create an issue on GitHub

## ⚠️ Disclaimer

This bot is for educational and personal use only. Users are responsible for complying with Instagram's Terms of Service and applicable laws. The creators are not responsible for any misuse of this software.

---

**Made with ❤️ by SWAYAM**