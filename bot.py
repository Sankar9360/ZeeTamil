import os
import re
import asyncio
import aiohttp
import aiofiles
import requests
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

def get_streamtape_download_link(url: str):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Referer": "https://streamtape.to/"
    }
    
    # பக்கத்தை எடுத்தல்
    response = requests.get(url, headers=headers, timeout=15)
    html = response.text

    # Streamtape-ன் மறைக்கப்பட்ட லிங்க் வடிவங்களை பிரித்தெடுத்தல்
    # வடிவம் 1: get_video?id=...&token=...
    match = re.search(r"document\.getElementById\('[\w\d]+'\)\.innerHTML\s*=\s*['\"]([^'\"]+)['\"];", html)
    if not match:
        match = re.search(r"innerHTML\s*=\s*['\"]([^'\"]+get_video[^'\"]*)['\"]", html)

    # வடிவம் 2: டோக்கன் சேர்க்கும் வடிவம்
    token_match = re.search(r"&token=([a-zA-Z0-9_\-]+)", html)

    if match:
        raw_link = match.group(1)
        if not raw_link.startswith("http"):
            raw_link = "https:" + raw_link
        return raw_link

    # மாற்று முறை: robotlink ஐடி வழியே எடுத்தல்
    robot_match = re.findall(r"ById\('robotlink'\)\.innerHTML\s*=\s*'([^']+)'\s*\+\s*'([^']+)'", html)
    if robot_match:
        part1, part2 = robot_match[0]
        return "https:" + part1 + part2

    return None

async def download_file(download_url, output_path, status_msg):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Referer": "https://streamtape.to/"
    }
    
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(download_url) as resp:
            if resp.status != 200:
                return False
            
            async with aiofiles.open(output_path, mode='wb') as f:
                async for chunk in resp.content.iter_chunked(1024 * 1024):  # 1MB chunks
                    await f.write(chunk)
            return True

@app.on_message(filters.command("start") & filters.private)
async def start_handler(client: Client, message: Message):
    await message.reply_text("வணக்கம்! Streamtape வீடியோ URL-ஐ அனுப்புங்கள். நான் சேனலில் பதிவேற்றுகிறேன்.")

@app.on_message(filters.text & filters.private)
async def handle_video(client: Client, message: Message):
    url = message.text.strip()
    
    if not ("streamtape" in url or url.startswith("http")):
        await message.reply_text("சரியான Streamtape URL-ஐ அனுப்பவும்!")
        return

    status_msg = await message.reply_text("Streamtape பக்கத்திலிருந்து வீடியோ லிங்க் எடுக்கப்படுகிறது...")
    output_filename = f"video_{message.id}.mp4"

    try:
        # Step 1: பைதான் வழியே Direct Link-ஐ டீகோட் செய்தல்
        direct_url = await asyncio.to_thread(get_streamtape_download_link, url)
        
        if not direct_url:
            await status_msg.edit_text("வீடியோ லிங்க் கிடைக்கவில்லை! வீடியோ நீக்கப்பட்டிருக்கலாம் அல்லது Streamtape பாதுகாப்பு மாறியிருக்கலாம்.")
            return

        # Step 2: வீடியோவை டவுன்லோட் செய்தல்
        await status_msg.edit_text("வீடியோ டவுன்லோட் ஆகிறது... காத்திருக்கவும்.")
        success = await download_file(direct_url, output_filename, status_msg)

        if not success or not os.path.exists(output_filename):
            await status_msg.edit_text("வீடியோ டவுன்லோட் செய்ய முடியவில்லை (403/Blocked).")
            return

        # Step 3: சேனலுக்கு அப்லோட் செய்தல்
        await status_msg.edit_text("சேனலுக்கு அப்லோட் செய்யப்படுகிறது...")
        await client.send_video(
            chat_id=TARGET_CHANNEL,
            video=output_filename,
            caption=f"Uploaded: {url}",
            supports_streaming=True
        )
        await status_msg.edit_text("வெற்றிகரமாக அப்லோட் செய்யப்பட்டது!")

    except Exception as e:
        await status_msg.edit_text(f"பிழை ஏற்பட்டது: {str(e)}")
    finally:
        # தேவையில்லாத ஃபைலை நீக்குதல்
        if os.path.exists(output_filename):
            os.remove(output_filename)

if __name__ == "__main__":
    print("Bot is starting...")
    app.run()
    
