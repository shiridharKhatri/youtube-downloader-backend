from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
import uvicorn
import aiohttp
import asyncio
import os
import uuid
import tempfile
import yt_dlp
from typing import Optional
from youtube_downloader import YouTubeDownloader, USER_AGENT

import os
import ssl

# LOCAL TEST FIX: Bypass SSL certificate verification for local development
# This solves the "CERTIFICATE_VERIFY_FAILED" error on Mac/Windows
os.environ['PYTHONHTTPSVERIFY'] = '0'
try:
    import certifi
    os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()
    os.environ['SSL_CERT_FILE'] = certifi.where()
except ImportError:
    pass

try:
    ssl._create_default_https_context = ssl._create_unverified_context
except AttributeError:
    pass

app = FastAPI(
    title="TikDown YouTube API",
    description="High-performance YouTube Downloader API",
    version="1.0.0"
)

# Enable CORS for frontend flexibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

downloader = YouTubeDownloader()

@app.get("/")
async def health_check():
    return {"status": "online", "engine": "TubeFetch Pro"}

# Memory database for download progress tracking
download_tasks = {}

async def run_download_task(task_id: str, url: str, type_str: str, itag: Optional[str]):
    try:
        def my_hook(d):
            if d['status'] == 'downloading':
                p = d.get('downloaded_bytes', 0)
                t = d.get('total_bytes', 0) or d.get('total_bytes_estimate', 0)
                if t > 0:
                    download_tasks[task_id]["progress"] = round((p / t) * 100, 2)
            elif d['status'] == 'finished':
                download_tasks[task_id]["progress"] = 100
                download_tasks[task_id]["status"] = "processing" # Usually merging or converting

        temp_dir = tempfile.gettempdir()
        out_temp = os.path.join(temp_dir, f"{task_id}.%(ext)s")
        
        opts = {
            'outtmpl': out_temp,
            'progress_hooks': [my_hook],
            'nocheckcertificate': True,
            'quiet': True,
            'no_warnings': True,
            'user_agent': USER_AGENT,
            'force_ipv4': True,
            # 'concurrent_fragment_downloads': 5, # aria2c level speed natively!
        }

        # USE COOKIES IF PRESENT (To bypass VPS IP blocks)
        cookie_path = os.path.join(os.path.dirname(__file__), 'cookies.txt')
        if os.path.exists(cookie_path):
            print(f"[Cookies] Using cookies for download from: {cookie_path}")
            opts['cookiefile'] = cookie_path
        
        if type_str == "audio":
            opts['format'] = 'bestaudio/best'
            opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]
        else:
            if itag and itag != "999" and itag != "null":
                opts['format'] = f"{itag}+bestaudio/best"
            else:
                opts['format'] = "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4] / b"
            opts['merge_output_format'] = 'mp4'

        def _download():
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                return ydl.prepare_filename(info)
                
        loop = asyncio.get_event_loop()
        final_file = await loop.run_in_executor(None, _download)
        
        # Extensions change after merging/conversion
        base, ext = os.path.splitext(final_file)
        if type_str == "audio":
            if not os.path.exists(final_file) or ext != '.mp3':
                # Check if .mp3 exists (postprocessors usually rename it)
                if os.path.exists(base + '.mp3'):
                    final_file = base + '.mp3'
                else:
                    # Some versions might keep both or have different naming
                    # We'll trust the base + .mp3 for extraction
                    final_file = base + '.mp3'
        else:
            if not os.path.exists(final_file) or ext != '.mp4':
                if os.path.exists(base + '.mp4'):
                    final_file = base + '.mp4'
                else:
                    final_file = base + '.mp4'
            
        if not os.path.exists(final_file):
            raise Exception(f"Final file not found: {final_file}")

        download_tasks[task_id]["status"] = "completed"
        download_tasks[task_id]["file"] = final_file
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[Task Error] {e}")
        download_tasks[task_id]["status"] = "error"
        download_tasks[task_id]["error"] = str(e)

@app.get("/start-download")
async def start_download(url: str, type: str = "video", itag: Optional[str] = None):
    task_id = str(uuid.uuid4())
    download_tasks[task_id] = {
        "status": "starting", 
        "progress": 0, 
        "file": None, 
        "error": None
    }
    asyncio.create_task(run_download_task(task_id, url, type, itag))
    return {"task_id": task_id}

@app.get("/task-status/{task_id}")
async def task_status(task_id: str):
    task = download_tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@app.get("/download-file/{task_id}")
async def fetch_download_file(task_id: str, filename: str = "video.mp4"):
    task = download_tasks.get(task_id)
    if not task or task["status"] != "completed" or not task["file"]:
        raise HTTPException(status_code=404, detail="File not ready")
        
    path = task["file"]
    
    media_type = "video/mp4"
    if filename.endswith(".mp3"): media_type = "audio/mpeg"
    
    from fastapi.responses import FileResponse
    return FileResponse(path, media_type=media_type, filename=filename)

@app.get("/status")
async def get_status():
    return {"status": "online"}

@app.get("/stream")
async def stream_video(url: str, filename: Optional[str] = "video.mp4"):
    """
    ULTRA-ROBUST Streaming using yt-dlp piping.
    This bypasses all 403 Forbidden issues.
    """
    import subprocess
    from youtube_downloader import USER_AGENT
    
    # We use a generator to pipe the stdout from yt-dlp
    async def stream_generator():
        # Build command for high speed piping
        # -o - writes to stdout
        cmd = [
            "yt-dlp",
            "--quiet",
            "--no-warnings",
            "--user-agent", USER_AGENT,
            "--nocheckcertificate",
            "--force-ipv4",
            "-f", "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4] / b", # Best MP4
            "-o", "-", # Stream to stdout
            url
        ]
        
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        try:
            while True:
                chunk = await proc.stdout.read(1024 * 1024) # 1MB chunks
                if not chunk:
                    break
                yield chunk
        except Exception as e:
            print(f"[Streaming Error] {e}")
        finally:
            try: proc.kill()
            except: pass

    return StreamingResponse(
        stream_generator(),
        media_type="video/mp4",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Access-Control-Allow-Origin": "*",
            "Accept-Ranges": "bytes"
        }
    )

@app.get("/info")
async def get_info(url: str):
    """
    Analyzes a YouTube URL and returns metadata + download formats.
    """
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")
    
    info = await downloader.get_media_info(url)
    if not info:
        raise HTTPException(status_code=404, detail="Could not analyze video")
    
    return info

@app.get("/proxy")
async def proxy_media(url: str, filename: Optional[str] = "video.mp4"):
    """
    High-performance Streaming Proxy with logging.
    """
    from youtube_downloader import USER_AGENT
    print(f"[*] Proxying request for: {url[:100]}...")
    
    # Minimal headers often work better for direct video URLs
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Range": "bytes=0-", # Force start
    }
    
    async def stream_generator():
        # Specifically bypass SSL inside the proxy
        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=connector) as session:
            try:
                # 1. Try with minimal headers
                async with session.get(url, headers=headers) as resp:
                    print(f"[Proxy] Response Status: {resp.status}")
                    
                    if resp.status == 403:
                        print("[Proxy] 403 Forbidden - Retrying with strictly minimal headers...")
                        async with session.get(url, headers={"User-Agent": USER_AGENT}) as resp2:
                            if resp2.status >= 400:
                                yield f"Error: YouTube 403 Forbidden even after retry.".encode()
                                return
                            # Success on retry!
                            async for chunk in resp2.content.iter_chunked(1024 * 1024):
                                yield chunk
                            return

                    if resp.status >= 400:
                        yield f"Error: YouTube returned status {resp.status}".encode()
                        return
                    
                    async for chunk in resp.content.iter_chunked(1024 * 1024):
                        yield chunk
            except Exception as e:
                print(f"[Proxy Error] {e}")
                yield f"Proxy Error: {str(e)}".encode()

    media_type = "video/mp4"
    if filename.endswith(".mp3"): media_type = "audio/mpeg"
    elif filename.endswith(".m4a"): media_type = "audio/mp4"

    return StreamingResponse(
        stream_generator(),
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Access-Control-Allow-Origin": "*",
            "Accept-Ranges": "bytes"
        }
    )

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8088)
