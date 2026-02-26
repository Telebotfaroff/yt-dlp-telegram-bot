import os
import asyncio
import yt_dlp
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

app = Client(
    "bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

queue = asyncio.Queue()
processing = False


# Progress bar
def progress_bar(percent):

    filled = int(percent / 5)
    bar = "█" * filled + "░" * (20 - filled)

    return f"""
{bar}

{percent:.2f}%
"""


# Download function
async def download_video(url, quality, msg):

    loop = asyncio.get_event_loop()

    file = f"{DOWNLOAD_DIR}/{msg.id}.mp4"
    thumb = f"{DOWNLOAD_DIR}/{msg.id}.jpg"

    def hook(d):

        if d['status'] == 'downloading':

            percent = float(
                d['_percent_str']
                .replace('%', '')
                .strip()
            )

            asyncio.run_coroutine_threadsafe(
                msg.edit(
                    f"Downloading...\n{progress_bar(percent)}"
                ),
                loop
            )

    ydl_opts = {

        "format": quality,
        "outtmpl": file,
        "progress_hooks": [hook],
        "writethumbnail": True,
        "quiet": True
    }

    def run():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)

            thumb_url = info.get("thumbnail")

            if thumb_url:
                os.system(f"wget '{thumb_url}' -O {thumb}")

            return info.get("title", "video")

    title = await asyncio.to_thread(run)

    return file, thumb, title


# Queue processor
async def process_queue():

    global processing

    if processing:
        return

    processing = True

    while not queue.empty():

        url, quality, message = await queue.get()

        msg = await message.reply("Starting download...")

        try:

            file, thumb, title = await download_video(
                url,
                quality,
                msg
            )

            await msg.edit("Uploading...")

            await app.send_video(
                CHANNEL_ID,
                file,
                caption=title,
                thumb=thumb if os.path.exists(thumb) else None
            )

            await app.send_video(
                message.chat.id,
                file,
                caption=title,
                thumb=thumb if os.path.exists(thumb) else None
            )

            await msg.edit("Done")

            os.remove(file)
            if os.path.exists(thumb):
                os.remove(thumb)

        except Exception as e:

            await msg.edit(str(e))

    processing = False


# Quality selection
@app.on_message(filters.private & filters.text)
async def quality_select(client, message):

    url = message.text

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


@app.on_callback_query()
async def callback(client, callback):

    quality, url = callback.data.split("|")

    await queue.put(
        (
            url,
            quality,
            callback.message
        )
    )

    await callback.message.edit("Added to queue")

    asyncio.create_task(process_queue())


print("Bot running")

app.run()
