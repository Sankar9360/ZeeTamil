import os
import re
import time
import asyncio
import aiohttp
import aiofiles
import requests
import subprocess
from pyrogram import Client, filters
from pyrogram.types import Message

# உங்கள் Telegram விவரங்கள்
API_ID = 23990433
API_HASH = "e6c4b6ee1933711bc4da9d7d17e1eb20"
BOT_TOKEN = "6489443094:AAFZfStZWucxMwtvk0i7XcbI2aYZvYpNT8E"
TARGET_CHANNEL = "@gteer3"

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

    # Video ID எடுத்தல்
    id_match = re.search(r"get_video\?id=([a-zA-Z0-9_\-]+)", html)
    if not id_match:
        id_match = re.search(r"/v/([a-zA-Z0-9_\-]+)", url)
    video_id = id_match.group(1) if id_match else None

    # Substring Token எடுத்தல்
    sub_match = re.search(r"\+ \('([^']+)'\)\.substring\(([0-9]+)\)", html)
    token = None
    if sub_match:
        full_str = sub_match.group(1)
        offset = int(sub_match.group(2))
        token = full_str[offset:]
    else:
        token_match = re.search(r"&token=([a-zA-Z0-9_\-]+)", html)
        if token_match:
            token = token_match.group(1)

    if video_id and token:
        clean_token = token.replace("&token=", "")
        return f"https://streamtape.com/get_video?id={video_id}&token={clean_token}"

    robot_match = re.findall(r"ById\('robotlink'\)\.innerHTML\s*=\s*'([^']+)'\s*\+\s*'([^']+)'", html)
    if robot_match:
        raw = "https:" + robot_match[0][0] + robot_match[0][1]
        return re.sub(r"streamtape[a-z0-9]+\.to", "streamtape.com", raw)

    return None

async def download_file(download_url, output_path):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Referer": "https://streamtape.com/"
    }
    
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(download_url, allow_redirects=True) as resp:
            if resp.status != 200:
                return False
            
            async with aiofiles.open(output_path, mode='wb') as f:
                async for chunk in resp.content.iter_chunked(2 * 1024 * 1024):
                    await f.write(chunk)
            return True

def get_video_metadata(video_path, thumb_path):
    """வீடியோவின் நேரம், அகலம்/உயரம் மற்றும் தம்ப்நெயில் எடுக்கும் செயல்முறை"""
    duration = 0
    width = 1280
    height = 720
    
    try:
        # 1. கால அளவு மற்றும் அளவுகளைப் பெறுதல்
        cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height,duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path
        ]
        output = subprocess.check_output(cmd).decode().split()
        if len(output) >= 3:
            width = int(output[0])
            height = int(output[1])
            duration = int(float(output[2]))
    except Exception:
        pass

    try:
        # 2. தம்ப்நெயில் இமேஜ் உருவாக்குதல்
        ss_time = "00:00:02" if duration > 3 else "00:00:00"
        thumb_cmd = [
            "ffmpeg", "-y", "-ss", ss_time,
            "-i", video_path, "-vframes", "1",
            "-q:v", "2", thumb_path
        ]
        subprocess.run(thumb_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

    return duration, width, height

# அப்லோட் சதவீதத்தை Telegram-ல் காட்ட
last_edit_time = {}

async def progress_callback(current, total, status_msg):
    now = time.time()
    msg_id = status_msg.id
    if msg_id not in last_edit_time or (now - last_edit_time[msg_id]) > 4:
        last_edit_time[msg_id] = now
        percent = current * 100 / total
        curr_mb = current / (1024 * 1024)
        tot_mb = total / (1024 * 1024)
        try:
            await status_msg.edit_text(f"சேனலுக்கு அப்லோட் ஆகிறது...\n\n🚀 {percent:.1f}% ({curr_mb:.1f} MB / {tot_mb:.1f} MB)")
        except Exception:
            pass

@app.on_message(filters.command("start") & filters.private)
async def start_handler(client: Client, message: Message):
    await message.reply_text("வணக்கம்! Streamtape URL-ஐ அனுப்பவும். நான் முறையான தம்ப்நெயில் மற்றும் நேரத்துடன் @gteer3 சேனலில் அப்லோட் செய்கிறேன்.")

@app.on_message(filters.text & filters.private)
async def handle_video(client: Client, message: Message):
    url = message.text.strip()
    
    if not ("streamtape" in url or url.startswith("http")):
        await message.reply_text("சரியான Streamtape URL-ஐ அனுப்பவும்!")
        return

    status_msg = await message.reply_text("Streamtape பக்கத்திலிருந்து வீடியோ லிங்க் எடுக்கப்படுகிறது...")
    output_filename = f"video_{message.id}.mp4"
    thumb_filename = f"thumb_{message.id}.jpg"

    try:
        # Step 1: Direct link பெறுதல்
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

        # Step 3: மெட்டாடேட்டா & தம்ப்நெயில் எடுத்தல்
        await status_msg.edit_text("தம்ப்நெயில் மற்றும் மெட்டாடேட்டா தயாராகிறது...")
        duration, width, height = await asyncio.to_thread(get_video_metadata, output_filename, thumb_filename)
        thumb_path = thumb_filename if os.path.exists(thumb_filename) else None

        # Step 4: அப்லோட் செய்தல்
        await status_msg.edit_text("சேனலுக்கு அப்லோட் தொடங்குகிறது...")
        await client.send_video(
            chat_id=TARGET_CHANNEL,
            video=output_filename,
            duration=duration,
            width=width,
            height=height,
            thumb=thumb_path,
            caption=f"Uploaded: {url}",
            supports_streaming=True,
            progress=progress_callback,
            progress_args=(status_msg,)
        )
        await status_msg.edit_text("வெற்றிகரமாக சேனலில் அப்லோட் செய்யப்பட்டது!")

    except Exception as e:
        await status_msg.edit_text(f"பிழை ஏற்பட்டது: {str(e)}")
    finally:
        # ஃபைல்களை நீக்குதல்
        if os.path.exists(output_filename):
            os.remove(output_filename)
        if os.path.exists(thumb_filename):
            os.remove(thumb_filename)

if __name__ == "__main__":
    print("Bot is starting...")
    app.run()
        
