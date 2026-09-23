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

    id_match = re.search(r"get_video\?id=([a-zA-Z0-9_\-]+)", html)
    if not id_match:
        id_match = re.search(r"/v/([a-zA-Z0-9_\-]+)", url)
    video_id = id_match.group(1) if id_match else None

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

# டவுன்லோட் Progress Bar காட்டும் செயல்முறை
async def download_file(download_url, output_path, status_msg):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Referer": "https://streamtape.com/"
    }
    
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(download_url, allow_redirects=True) as resp:
            if resp.status != 200:
                return False
            
            total_size = int(resp.headers.get("content-length", 0))
            downloaded = 0
            last_edit = time.time()

            async with aiofiles.open(output_path, mode='wb') as f:
                async for chunk in resp.content.iter_chunked(1024 * 1024):  # 1MB Chunks
                    await f.write(chunk)
                    downloaded += len(chunk)
                    now = time.time()

                    # 3 விநாடிகளுக்கு ஒருமுறை Status Update செய்தல்
                    if now - last_edit > 3:
                        last_edit = now
                        if total_size > 0:
                            percent = (downloaded / total_size) * 100
                            cur_mb = downloaded / (1024 * 1024)
                            tot_mb = total_size / (1024 * 1024)
                            text = f"📥 **Downloading...**\n`{percent:.1f}%` ({cur_mb:.1f}MB / {tot_mb:.1f}MB)"
                        else:
                            cur_mb = downloaded / (1024 * 1024)
                            text = f"📥 **Downloading...**\n{cur_mb:.1f}MB"
                        
                        try:
                            await status_msg.edit_text(text)
                        except Exception:
                            pass
            return True

def fix_and_get_metadata(raw_video, final_video, thumb_path):
    fix_cmd = [
        "ffmpeg", "-y", "-i", raw_video,
        "-c", "copy", "-movflags", "+faststart",
        final_video
    ]
    subprocess.run(fix_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    use_file = final_video if os.path.exists(final_video) else raw_video

    duration = 0
    width = 1280
    height = 720
    
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration:stream=width,height",
            "-of", "csv=p=0",
            use_file
        ]
        out = subprocess.check_output(cmd).decode().split()
        for line in out:
            parts = line.split(",")
            if len(parts) == 2 and parts[0].isdigit():
                width = int(parts[0])
                height = int(parts[1])
            elif len(parts) == 1:
                try:
                    duration = int(float(parts[0]))
                except ValueError:
                    pass
    except Exception:
        pass

    try:
        ss_time = str(min(2, max(0, duration // 2)))
        thumb_cmd = [
            "ffmpeg", "-y", "-ss", ss_time,
            "-i", use_file, "-vframes", "1",
            "-q:v", "2", thumb_path
        ]
        subprocess.run(thumb_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

    return duration, width, height, use_file

# அப்லோட் Progress Bar காட்டும் செயல்முறை
last_upload_edit = {}

async def upload_progress(current, total, status_msg):
    now = time.time()
    msg_id = status_msg.id
    if msg_id not in last_upload_edit or (now - last_upload_edit[msg_id]) > 3:
        last_upload_edit[msg_id] = now
        percent = (current / total) * 100
        cur_mb = current / (1024 * 1024)
        tot_mb = total / (1024 * 1024)
        try:
            await status_msg.edit_text(f"📤 **Uploading to Channel...**\n`{percent:.1f}%` ({cur_mb:.1f}MB / {tot_mb:.1f}MB)")
        except Exception:
            pass

@app.on_message(filters.command("start") & filters.private)
async def start_handler(client: Client, message: Message):
    await message.reply_text("வணக்கம்! Streamtape URL-ஐ அனுப்பவும்.")

@app.on_message(filters.text & filters.private)
async def handle_video(client: Client, message: Message):
    url = message.text.strip()
    
    if not ("streamtape" in url or url.startswith("http")):
        await message.reply_text("சரியான Streamtape URL-ஐ அனுப்பவும்!")
        return

    status_msg = await message.reply_text("🔍 **Processing Link...**")
    raw_video = f"raw_{message.id}.mp4"
    ready_video = f"ready_{message.id}.mp4"
    thumb_file = f"thumb_{message.id}.jpg"

    try:
        # Step 1: Link பிரித்தெடுத்தல்
        direct_url = await asyncio.to_thread(get_streamtape_download_link, url)
        if not direct_url:
            await status_msg.edit_text("❌ வீடியோ லிங்க் கிடைக்கவில்லை!")
            return

        # Step 2: Downloading Progress உடன் டவுன்லோட்
        await status_msg.edit_text("📥 **Starting Download...**")
        success = await download_file(direct_url, raw_video, status_msg)

        if not success or not os.path.exists(raw_video):
            await status_msg.edit_text("❌ டவுன்லோட் தோல்வியடைந்தது.")
            return

        # Step 3: Faststart & Thumbnail
        await status_msg.edit_text("⚙️ **Optimizing Video & Thumbnail...**")
        duration, width, height, final_upload_file = await asyncio.to_thread(
            fix_and_get_metadata, raw_video, ready_video, thumb_file
        )
        thumb_path = thumb_file if os.path.exists(thumb_file) else None

        # Step 4: Uploading Progress உடன் அப்லோட்
        await status_msg.edit_text("📤 **Starting Upload...**")
        await client.send_video(
            chat_id=TARGET_CHANNEL,
            video=final_upload_file,
            duration=duration,
            width=width,
            height=height,
            thumb=thumb_path,
            caption=f"Uploaded: {url}",
            supports_streaming=True,
            progress=upload_progress,
            progress_args=(status_msg,)
        )
        await status_msg.edit_text("✅ **வெற்றிகரமாக சேனலில் பதிவேற்றப்பட்டது!**")

    except Exception as e:
        await status_msg.edit_text(f"❌ பிழை: {str(e)}")
    finally:
        for f in [raw_video, ready_video, thumb_file]:
            if os.path.exists(f):
                os.remove(f)

if __name__ == "__main__":
    print("Bot is starting...")
    app.run()
                
