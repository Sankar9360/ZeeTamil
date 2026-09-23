import os
import subprocess
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message

# Railway Environment Variables வழியாக பெறப்படும்
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
TARGET_CHANNEL = os.environ.get("TARGET_CHANNEL")  # எ.கா: @mychannel அல்லது -100xxxxxxxxxx

app = Client(
    "streamtape_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

@app.on_message(filters.command("start") & filters.private)
async def start_handler(client: Client, message: Message):
    await message.reply_text("வணக்கம்! Streamtape அல்லது ஏதேனும் வீடியோ URL-ஐ அனுப்புங்கள். நான் டவுன்லோட் செய்து சேனலில் அப்லோட் செய்கிறேன்.")

@app.on_message(filters.text & filters.private)
async def download_and_upload(client: Client, message: Message):
    url = message.text.strip()
    
    if not url.startswith("http"):
        await message.reply_text("சரியான URL-ஐ அனுப்பவும்!")
        return

    status_msg = await message.reply_text("வீடியோ விவரங்கள் சரிபார்க்கப்படுகின்றன...")
    output_filename = f"video_{message.id}.mp4"

    # Step 1: yt-dlp வழியாக டவுன்லோட் செய்தல் (403 எரர் வராமல் தடுக்க)
    await status_msg.edit_text("வீடியோ டவுன்லோட் ஆகிறது... காத்திருக்கவும்.")
    cmd = [
        "yt-dlp",
        "-f", "best",
        "-o", output_filename,
        url
    ]

    process = await asyncio.create_subprocess_exec(*cmd)
    await process.communicate()

    if process.returncode != 0 or not os.path.exists(output_filename):
        await status_msg.edit_text("டவுன்லோட் தோல்வியடைந்தது! லிங்க் சரியாக உள்ளதா எனப் பார்க்கவும்.")
        return

    # Step 2: சேனலுக்கு அப்லோட் செய்தல்
    await status_msg.edit_text("சேனலுக்கு அப்லோட் ஆகிறது...")
    try:
        await client.send_video(
            chat_id=TARGET_CHANNEL,
            video=output_filename,
            caption=f"Uploaded: {url}",
            supports_streaming=True
        )
        await status_msg.edit_text("வெற்றிகரமாக சேனலில் பதிவேற்றப்பட்டது!")
    except Exception as e:
        await status_msg.edit_text(f"அப்லோட் செய்வதில் பிழை: {str(e)}")
    finally:
        # Step 3: Railway Storage நிரம்பாமல் இருக்க ஃபைலை நீக்குதல்
        if os.path.exists(output_filename):
            os.remove(output_filename)

if __name__ == "__main__":
    print("Bot is starting...")
    app.run()
  
