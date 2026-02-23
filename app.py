from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
import uvicorn
import aiohttp
import asyncio
import os
import uuid
import tempfile
from typing import Optional
from dotenv import load_dotenv
load_dotenv()

from youtube_downloader import YouTubeDownloader, USER_AGENT

import os
import ssl


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
        # STEP 1: Get direct playable URL via Reverse Engine
        info = await downloader.get_media_info(url)
        if not info or not info.get("play"):
            raise Exception("Could not retrieve a playable URL.")
        
        play_url = info["play"]
        temp_dir = tempfile.gettempdir()
        final_file = os.path.join(temp_dir, f"{task_id}.{'mp3' if type_str == 'audio' else 'mp4'}")

        print(f"[*] Starting streaming download: {play_url[:60]}...")
        
        # STEP 2: Use FFmpeg with a pipe for maximum speed and compatibility
        import subprocess
        
        # Build FFmpeg command
        if type_str == "audio":
            # MP3 Conversion
            cmd = ["ffmpeg", "-y", "-i", "pipe:0", "-vn", "-ar", "44100", "-ac", "2", "-b:a", "192k", final_file]
        else:
            # MP4 Remuxing with faststart (no transcoding for speed)
            cmd = ["ffmpeg", "-y", "-i", "pipe:0", "-c", "copy", "-movflags", "faststart", final_file]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL
        )

        # Download and pipe
        proxy = os.getenv("PROXY_URL")
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
            async with session.get(play_url, headers={"User-Agent": USER_AGENT}, proxy=proxy, timeout=300) as resp:
                if resp.status >= 400:
                    raise Exception(f"YouTube stream error: {resp.status}")
                
                total_size = int(resp.headers.get('content-length', 0))
                downloaded = 0
                
                async for chunk in resp.content.iter_chunked(512 * 1024):
                    if not chunk: break
                    process.stdin.write(chunk)
                    await process.stdin.drain()
                    downloaded += len(chunk)
                    
                    if total_size > 0:
                        download_tasks[task_id]["progress"] = round((downloaded / total_size) * 100, 1)
                    else:
                        # Fallback progress for unknown size
                        download_tasks[task_id]["progress"] = min(99, download_tasks[task_id].get("progress", 0) + 0.5)

                process.stdin.close()
                await process.wait()

        if not os.path.exists(final_file) or os.path.getsize(final_file) < 1000:
            raise Exception("Final file is missing or too small.")

        download_tasks[task_id]["status"] = "completed"
        download_tasks[task_id]["progress"] = 100
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
    ULTRA-ROBUST Streaming using native proxying.
    Bypasses all yt-dlp IP blocks.
    """
    # 1. Get the direct URL via reverse engine
    info = await downloader.get_media_info(url)
    if not info or not info.get("play"):
        raise HTTPException(status_code=404, detail="Could not retrieve stream URL")
    
    target_url = info["play"]
    
    async def stream_generator():
        proxy = os.getenv("PROXY_URL")
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
            try:
                headers = {"User-Agent": USER_AGENT, "Range": "bytes=0-"}
                async with session.get(target_url, headers=headers, proxy=proxy) as resp:
                    async for chunk in resp.content.iter_chunked(1024 * 1024):
                        yield chunk
            except Exception as e:
                print(f"[Streaming Error] {e}")

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
        proxy = os.getenv("PROXY_URL")
        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=connector) as session:
            try:
                # 1. Try with minimal headers
                async with session.get(url, headers=headers, proxy=proxy) as resp:
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
