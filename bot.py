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
    
    response = requests.get(url, headers=headers, timeout=20)
    html = response.text

    # Streamtape வீடியோ ஐடி மற்றும் டோக்கனைப் பிரித்தெடுத்தல்
    id_match = re.search(r"get_video\?id=([a-zA-Z0-9_\-]+)", html)
    if not id_match:
        # மற்றொரு முறை
        id_match = re.search(r"/v/([a-zA-Z0-9_\-]+)", url)
    
    video_id = id_match.group(1) if id_match else None

    # Substring டோக்கனை எடுத்தல்
    sub_match = re.search(r"\+ \('([^']+)'\)\.substring\(([0-9]+)\)", html)
    token = None
    if sub_match:
        full_str = sub_match.group(1)
        offset = int(sub_match.group(2))
        token = full_str[offset:]
    else:
        # நேரடி டோக்கன் வடிவம்
        token_match = re.search(r"&token=([a-zA-Z0-9_\-]+)", html)
        if token_match:
            token = token_match.group(1)

    if video_id and token:
        # டொமைன் பிழைகளைத் தவிர்க்க நிலையான டொமைனில் லிங்க் உருவாக்குதல்
        clean_token = token.replace("&token=", "")
        final_url = f"https://streamtape.com/get_video?id={video_id}&token={clean_token}"
        return final_url

    # Fallback முறை
    robot_match = re.findall(r"ById\('robotlink'\)\.innerHTML\s*=\s*'([^']+)'\s*\+\s*'([^']+)'", html)
    if robot_match:
        raw = "https:" + robot_match[0][0] + robot_match[0][1]
        raw = re.sub(r"streamtape[a-z0-9]+\.to", "streamtape.com", raw)
        return raw

    return None

async def download_file(download_url, output_path):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Referer": "https://streamtape.com/"
    }
    
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(download_url, allow_redirects=True) as resp:
            if resp.status != 200:
                print(f"Failed with status: {resp.status}")
                return False
            
            async with aiofiles.open(output_path, mode='wb') as f:
                async for chunk in resp.content.iter_chunked(2 * 1024 * 1024):  # 2MB chunks
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
        # Step 1: தூய streamtape.com லிங்க்கை உருவாக்குதல்
        direct_url = await asyncio.to_thread(get_streamtape_download_link, url)
        
        if not direct_url:
            await status_msg.edit_text("வீடியோ லிங்க் கிடைக்கவில்லை! வீடியோ நீக்கப்பட்டிருக்கலாம்.")
            return

        # Step 2: டவுன்லோட் செய்தல்
        await status_msg.edit_text("வீடியோ டவுன்லோட் ஆகிறது... காத்திருக்கவும்.")
        success = await download_file(direct_url, output_filename)

        if not success or not os.path.exists(output_filename):
            await status_msg.edit_text("வீடியோ டவுன்லோட் செய்ய முடியவில்லை (Blocked / Link Expired).")
            return

        # Step 3: Telegram சேனலுக்கு அப்லோட் செய்தல்
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
        if os.path.exists(output_filename):
            os.remove(output_filename)

if __name__ == "__main__":
    print("Bot is starting...")
    app.run()
    
