import os
import re
import urllib.request
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message

# உங்கள் Telegram விவரங்கள்
API_ID = 23990433
API_HASH = "e6c4b6ee1933711bc4da9d7d17e1eb20"
BOT_TOKEN = "6489443094:AAFZfStZWucxMwtvk0i7XcbI2aYZvYpNT8E"
TARGET_CHANNEL = -1002156111560

app = Client(
    "streamtape_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

def extract_streamtape_url(page_url: str):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    req = urllib.request.Request(page_url, headers=headers)
    with urllib.request.urlopen(req) as resp:
        html = resp.read().decode("utf-8")

    # Streamtape வீடியோ லிங்க் பாகங்களை பிரித்தெடுத்தல்
    # பொதுவாக: document.getElementById('robotlink').innerHTML = '//streamtape.com/get_video?id=...&token=...';
    match = re.search(r"getElementById\('robotlink'\)\.innerHTML\s*=\s*'([^']+)'\s*\+\s*'([^']+)'", html)
    if not match:
        # மாற்று முறை
        match = re.search(r"getElementById\('robotlink'\)\.innerHTML\s*=\s*'([^']+)'", html)
        if match:
            link = "https:" + match.group(1)
            return link
        return None

    part1, part2 = match.groups()
    final_url = "https:" + part1 + part2
    return final_url

@app.on_message(filters.command("start") & filters.private)
async def start_handler(client: Client, message: Message):
    await message.reply_text("வணக்கம்! Streamtape வீடியோ வாட்ச் URL-ஐ அனுப்புங்கள் (எ.கா: https://streamtape.to/v/...). நான் டவுன்லோட் செய்து சேனலில் அப்லோட் செய்கிறேன்.")

@app.on_message(filters.text & filters.private)
async def download_and_upload(client: Client, message: Message):
    url = message.text.strip()
    
    if not url.startswith("http"):
        await message.reply_text("சரியான URL-ஐ அனுப்பவும்!")
        return

    status_msg = await message.reply_text("Streamtape வீடியோ லிங்க் எடுக்கப்படுகிறது...")
    output_filename = f"video_{message.id}.mp4"

    # Step 1: நேரடி வீடியோ URL எடுப்பது
    direct_video_url = None
    if "streamtape" in url:
        try:
            direct_video_url = extract_streamtape_url(url)
        except Exception as e:
            await status_msg.edit_text(f"வீடியோ விவரங்களை எடுக்க முடியவில்லை: {str(e)}")
            return

    download_target = direct_video_url if direct_video_url else url

    # Step 2: yt-dlp வழியாக சரியான Headers உடன் டவுன்லோட் செய்தல் (403 வராமல் தடுக்க)
    await status_msg.edit_text("வீடியோ டவுன்லோட் ஆகிறது... காத்திருக்கவும்.")
    cmd = [
        "yt-dlp",
        "--add-header", "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "--add-header", f"Referer: {url}",
        "-o", output_filename,
        download_target
    ]

    process = await asyncio.create_subprocess_exec(*cmd)
    await process.communicate()

    if process.returncode != 0 or not os.path.exists(output_filename):
        await status_msg.edit_text("டவுன்லோட் தோல்வியடைந்தது! Streamtape லிங்க் வேலை செய்கிறதா எனச் சோதிக்கவும்.")
        return

    # Step 3: Telegram சேனலுக்கு அப்லோட் செய்தல்
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
        # சேமிப்பக இடம் நிரம்பாமல் இருக்க ஃபைலை நீக்குதல்
        if os.path.exists(output_filename):
            os.remove(output_filename)

if __name__ == "__main__":
    print("Bot is starting...")
    app.run()
    
