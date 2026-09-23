import os
import re
import time
import asyncio
import subprocess
import requests
from pyrogram import Client, filters
from pyrogram.types import Message

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

def extract_streamtape(url: str):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "Referer": "https://streamtape.to/"
    }
    resp = requests.get(url, headers=headers, timeout=20)
    html = resp.text

    # Extract Video ID
    id_m = re.search(r"get_video\?id=([a-zA-Z0-9_\-]+)", html)
    if not id_m:
        id_m = re.search(r"/v/([a-zA-Z0-9_\-]+)", url)
    if not id_m:
        return None
    video_id = id_m.group(1)

    # Extract Token via Substring logic
    sub_m = re.search(r"\+ \('([^']+)'\)\.substring\(([0-9]+)\)", html)
    token = None
    if sub_m:
        raw_str = sub_m.group(1)
        offset = int(sub_m.group(2))
        token = raw_str[offset:]
    else:
        tok_m = re.search(r"&token=([a-zA-Z0-9_\-]+)", html)
        if tok_m:
            token = tok_m.group(1)

    if not token:
        return None

    clean_tok = token.replace("&token=", "")
    return f"https://streamtape.com/get_video?id={video_id}&token={clean_tok}&stream=1"

def download_streamtape(stream_url, page_url, output_path):
    # yt-dlp headers vazhiyaaga proper file download seiyum
    cmd = [
        "yt-dlp",
        "--no-check-certificates",
        "--add-header", "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "--add-header", f"Referer: {page_url}",
        "-o", output_path,
        stream_url
    ]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return proc.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 100000

def fix_faststart(raw_video, final_video, thumb_path):
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
    await message.reply_text("Vanakkam! Streamtape URL-ai anuppavum.")

@app.on_message(filters.text & filters.private)
async def handle_video(client: Client, message: Message):
    url = message.text.strip()
    
    if not ("streamtape" in url or url.startswith("http")):
        await message.reply_text("Sariyana Streamtape URL-ai anuppavum!")
        return

    status_msg = await message.reply_text("🔍 **Extracting Stream Link...**")
    raw_video = f"raw_{message.id}.mp4"
    ready_video = f"ready_{message.id}.mp4"
    thumb_file = f"thumb_{message.id}.jpg"

    try:
        direct_url = await asyncio.to_thread(extract_streamtape, url)
        if not direct_url:
            await status_msg.edit_text("❌ Video token extract panna mudiyavillai. Link expired aagiyirukkalaam.")
            return

        await status_msg.edit_text("📥 **Downloading Video from Server... (Wait 1-2 mins)**")
        success = await asyncio.to_thread(download_streamtape, direct_url, url, raw_video)

        if not success or not os.path.exists(raw_video) or os.path.getsize(raw_video) < 100000:
            await status_msg.edit_text("❌ Download tholviyadainthadhu (Empty response / Server Blocked).")
            return

        file_size_mb = os.path.getsize(raw_video) / (1024 * 1024)
        await status_msg.edit_text(f"⚙️ **Downloaded {file_size_mb:.1f}MB! Optimizing...**")
        
        duration, width, height, final_upload_file = await asyncio.to_thread(
            fix_faststart, raw_video, ready_video, thumb_file
        )
        thumb_path = thumb_file if os.path.exists(thumb_file) else None

        await status_msg.edit_text("📤 **Starting Upload to Channel...**")
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
        await status_msg.edit_text("✅ **Vetrigaramaaga upload seiyyappattadhu!**")

    except Exception as e:
        await status_msg.edit_text(f"❌ Error: {str(e)}")
    finally:
        for f in [raw_video, ready_video, thumb_file]:
            if os.path.exists(f):
                os.remove(f)

if __name__ == "__main__":
    print("Bot is starting...")
    app.run()
    
