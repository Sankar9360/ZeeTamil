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

# Telegram விவரங்கள்
API_ID = 23990433
API_HASH = "e6c4b6ee1933711bc4da9d7d17e1eb20"
BOT_TOKEN = "6489443094:AAFZfStZWucxMwtvk0i7XcbI2aYZvYpNT8E"
TARGET_CHANNEL = "@gteer3"

# Streamtape API விவரங்கள்
ST_API_LOGIN = "2ff044f4502a6976ffa4"
ST_API_KEY = "BAj63LW23DuQJm"  # Screenshot-ல் கீழே உள்ள Key

app = Client(
    "streamtape_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

def get_streamtape_api_link(url: str):
    """அதிகாரப்பூர்வ Streamtape API வழியாக தடையில்லா direct download link பெறுதல்"""
    id_m = re.search(r"/v/([a-zA-Z0-9_\-]+)", url)
    if not id_m:
        return None, "Video ID கண்டறிய முடியவில்லை."
    
    file_id = id_m.group(1)

    # 1. Download ticket உருவாக்குதல்
    ticket_api = f"https://api.streamtape.com/file/dlticket?file={file_id}&login={ST_API_LOGIN}&key={ST_API_KEY}"
    res = requests.get(ticket_api, timeout=15).json()

    if res.get("status") != 200:
        return None, res.get("msg", "Ticket உருவாக்க முடியவில்லை.")

    ticket = res["result"]["ticket"]
    wait_time = int(res["result"].get("wait_time", 5))

    # Streamtape காத்திருக்கச் சொல்லும் நொடிகள்
    if wait_time > 0:
        time.sleep(wait_time)

    # 2. டிக்கெட்டைப் பயன்படுத்தி நேரடி லிங்க் பெறுதல்
    dl_api = f"https://api.streamtape.com/file/dl?file={file_id}&ticket={ticket}"
    dl_res = requests.get(dl_api, timeout=15).json()

    if dl_res.get("status") != 200:
        return None, dl_res.get("msg", "Download link பெற முடியவில்லை.")

    return dl_res["result"]["url"], None

async def download_file(download_url, output_path, status_msg):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
    }
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(download_url, allow_redirects=True) as resp:
            if resp.status != 200:
                return False
            
            total_size = int(resp.headers.get("content-length", 0))
            downloaded = 0
            last_edit = time.time()

            async with aiofiles.open(output_path, mode='wb') as f:
                async for chunk in resp.content.iter_chunked(2 * 1024 * 1024):
                    await f.write(chunk)
                    downloaded += len(chunk)
                    now = time.time()

                    if now - last_edit > 3:
                        last_edit = now
                        if total_size > 0:
                            percent = (downloaded / total_size) * 100
                            cur_mb = downloaded / (1024 * 1024)
                            tot_mb = total_size / (1024 * 1024)
                            text = f"📥 **Downloading (Official API)...**\n`{percent:.1f}%` ({cur_mb:.1f}MB / {tot_mb:.1f}MB)"
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
    
    use_file = final_video if os.path.exists(final_video) and os.path.getsize(final_video) > 100000 else raw_video

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

    status_msg = await message.reply_text("🔑 **Streamtape API மூலம் டவுன்லோட் டிக்கெட் பெறப்படுகிறது...**")
    raw_video = f"raw_{message.id}.mp4"
    ready_video = f"ready_{message.id}.mp4"
    thumb_file = f"thumb_{message.id}.jpg"

    try:
        # Step 1: API Link பெறுதல்
        direct_url, err = await asyncio.to_thread(get_streamtape_api_link, url)
        if not direct_url:
            await status_msg.edit_text(f"❌ பிழை: {err}")
            return

        # Step 2: டவுன்லோட் செய்தல்
        await status_msg.edit_text("📥 **டவுன்லோட் தொடங்குகிறது...**")
        success = await download_file(direct_url, raw_video, status_msg)

        if not success or not os.path.exists(raw_video) or os.path.getsize(raw_video) < 100000:
            await status_msg.edit_text("❌ டவுன்லோட் தோல்வியடைந்தது.")
            return

        file_size_mb = os.path.getsize(raw_video) / (1024 * 1024)
        await status_msg.edit_text(f"⚙️ **{file_size_mb:.1f}MB டவுன்லோட் ஆகிவிட்டது! சீரமைக்கப்படுகிறது...**")

        # Step 3: Faststart & Thumbnail
        duration, width, height, final_upload_file = await asyncio.to_thread(
            fix_and_get_metadata, raw_video, ready_video, thumb_file
        )
        thumb_path = thumb_file if os.path.exists(thumb_file) else None

        # Step 4: அப்லோட் செய்தல்
        await status_msg.edit_text("📤 **சேனலில் அப்லோட் செய்யப்படுகிறது...**")
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
    print("Bot is starting with Official Streamtape API...")
    app.run()
    
