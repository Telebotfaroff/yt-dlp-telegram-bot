import os
import asyncio
import yt_dlp
from dotenv import load_dotenv
from pyrogram import Client, filters
from pyrogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton
)

# Load env
load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Create bot
app = Client(
    "ytbot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# Queue system
queue = asyncio.Queue()
processing = False


# Progress bar generator
def progress_bar(percent):

    filled = int(percent / 5)
    empty = 20 - filled

    bar = "█" * filled + "░" * empty

    return f"""
{bar}

{percent:.2f}%
"""


# Download function
async def download_video(url, quality, status_msg):

    loop = asyncio.get_event_loop()

    file_path = f"{DOWNLOAD_DIR}/{status_msg.id}.mp4"
    thumb_path = f"{DOWNLOAD_DIR}/{status_msg.id}.jpg"

    def progress_hook(d):

        if d["status"] == "downloading":

            percent_str = d.get("_percent_str", "0%")
            percent = float(percent_str.replace("%", "").strip())

            text = f"Downloading...\n{progress_bar(percent)}"

            asyncio.run_coroutine_threadsafe(
                status_msg.edit(text),
                loop
            )

    ydl_opts = {

        "format": quality,
        "outtmpl": file_path,
        "progress_hooks": [progress_hook],
        "writethumbnail": True,
        "quiet": True,
        "merge_output_format": "mp4"
    }

    def run():

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:

            info = ydl.extract_info(url, download=True)

            thumb_url = info.get("thumbnail")

            if thumb_url:
                os.system(
                    f"wget '{thumb_url}' -O '{thumb_path}'"
                )

            title = info.get("title", "video")

            return title

    title = await asyncio.to_thread(run)

    return file_path, thumb_path, title


# Queue processor
async def process_queue():

    global processing

    if processing:
        return

    processing = True

    while not queue.empty():

        url, quality, message = await queue.get()

        status = await message.reply("Queued...")

        try:

            file_path, thumb_path, title = await download_video(
                url,
                quality,
                status
            )

            await status.edit("Uploading...")

            # Upload to channel
            await app.send_video(
                CHANNEL_ID,
                file_path,
                caption=title,
                thumb=thumb_path if os.path.exists(thumb_path) else None
            )

            # Upload to user
            await app.send_video(
                message.chat.id,
                file_path,
                caption=title,
                thumb=thumb_path if os.path.exists(thumb_path) else None
            )

            await status.edit("Completed")

        except Exception as e:

            await status.edit(f"Error: {str(e)}")

        finally:

            if os.path.exists(file_path):
                os.remove(file_path)

            if os.path.exists(thumb_path):
                os.remove(thumb_path)

    processing = False


# Start command
@app.on_message(filters.command("start"))
async def start(client, message):

    await message.reply(
        "Send any video link to download.\n\n"
        "Supports YouTube, Instagram, Facebook, etc."
    )


# Receive URL
@app.on_message(filters.private & filters.text)
async def quality_menu(client, message):

    url = message.text.strip()

    keyboard = InlineKeyboardMarkup([

        [
            InlineKeyboardButton(
                "Best",
                callback_data=f"best|{url}"
            )
        ],

        [
            InlineKeyboardButton(
                "720p",
                callback_data=f"bestvideo[height<=720]+bestaudio/best[height<=720]|{url}"
            )
        ],

        [
            InlineKeyboardButton(
                "480p",
                callback_data=f"bestvideo[height<=480]+bestaudio/best[height<=480]|{url}"
            )
        ]
    ])

    await message.reply(
        "Select quality:",
        reply_markup=keyboard
    )


# Handle quality selection
@app.on_callback_query()
async def handle_callback(client, callback_query):

    data = callback_query.data

    quality, url = data.split("|", 1)

    await queue.put((
        url,
        quality,
        callback_query.message
    ))

    await callback_query.message.edit(
        "Added to queue"
    )

    asyncio.create_task(process_queue())


print("Bot started successfully")

app.run()
