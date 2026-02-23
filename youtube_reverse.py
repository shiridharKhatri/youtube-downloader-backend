import asyncio
import aiohttp
import json
import os
import traceback
import random
import yt_dlp
import re

from dotenv import load_dotenv
load_dotenv()

class ProxyManager:
    _residential_proxy = os.getenv("PROXY_URL")

    @classmethod
    async def get_proxy(cls):
        # Only return if it's a valid string
        if isinstance(cls._residential_proxy, str) and len(cls._residential_proxy) > 10:
            return cls._residential_proxy
        return None

class YouTubeReverse:
    """
    Hyper-Robust YouTube Engine.
    Uses residential proxies and multi-api racing to bypass all blocks.
    """
    def __init__(self):
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1"
        ]

    async def fetch_video_info(self, url):
        """
        Ultimate Parallel Race: Engines compete for the fastest response.
        """
        print(f"[*] Starting Ultimate Race for: {url}")
        
        # Parallel Engines
        fast_tasks = [
            self._engine_cobalt(url),   # Turbo
            self._engine_native(url),   # Resi Scraper
            self._engine_piped(url),    # API Loop
            self._engine_invidious(url),# API Loop
            self._engine_savefrom(url), # External Scraper
            self._engine_ytdlp(url, use_proxy=True) # Resi yt-dlp
        ]
        
        # Racer Loop: First valid response wins.
        for future in asyncio.as_completed(fast_tasks, timeout=12):
            try:
                result = await future
                if result and result.get("url"):
                    print(f"[Race] Winner: {result.get('engine', 'unknown')}")
                    return result
            except: continue

        # Heavy Fallbacks
        print("[*] Race Failed. Trying Sequential Fallbacks...")
        heavy_engines = [
            lambda u: self._engine_ytdlp(u, use_proxy=False), 
            self._engine_selenium
        ]
        
        for engine_coro in heavy_engines:
            try:
                result = await engine_coro(url)
                if result and result.get("url"):
                    return result
            except: continue
                
        return None

    async def _engine_cobalt(self, url):
        """
        Cobalt API (v10) Mirror Racing.
        """
        instances = [
            "https://api.cobalt.tools/api/json",
            "https://cobalt.shizuri.com/api/json",
            "https://api.cobalt.red/api/json"
        ]
        
        async def _hit(api_url):
            payload = {"url": url, "vQuality": "1080", "isAudioOnly": False}
            headers = {"Accept": "application/json", "User-Agent": random.choice(self.user_agents)}
            try:
                async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
                    async with session.post(api_url, json=payload, headers=headers, timeout=8) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            if data.get("url"):
                                return {
                                    "title": data.get("text", "YouTube Video"),
                                    "url": data["url"],
                                    "thumbnail": None,
                                    "quality": "1080p", "width": 1920, "height": 1080,
                                    "engine": f"cobalt-{api_url.split('/')[2]}"
                                }
            except: pass
            return None

        # Mini-race for Cobalt instances
        tasks = [_hit(inst) for inst in instances]
        for f in asyncio.as_completed(tasks):
            res = await f
            if res: return res
        return None

    async def _engine_native(self, url):
        """
        Native YouTube Scraper with Residential Proxy.
        """
        video_id = self._extract_video_id(url)
        if not video_id: return None
        proxy = await ProxyManager.get_proxy()
        
        try:
            headers = {"User-Agent": self.user_agents[0]}
            async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
                async with session.get(f"https://www.youtube.com/watch?v={video_id}", headers=headers, proxy=proxy, timeout=7) as resp:
                    if resp.status != 200: return None
                    html = await resp.text()
                    match = re.search(r'ytInitialPlayerResponse\s*=\s*({.+?});', html) or \
                            re.search(r'var\s+ytInitialPlayerResponse\s*=\s*({.+?});', html)
                    if match:
                        data = json.loads(match.group(1))
                        streaming_data = data.get("streamingData", {})
                        formats = streaming_data.get("formats", []) + streaming_data.get("adaptiveFormats", [])
                        formats = [f for f in formats if "url" in f]
                        combined = sorted([f for f in formats if f.get("acodec") != "none" and f.get("vcodec") != "none"], 
                                        key=lambda x: x.get("height", 0), reverse=True)
                        best_f = combined[0] if combined else (sorted(formats, key=lambda x: x.get("height", 0), reverse=True)[0] if formats else None)
                        if best_f:
                            return {
                                "title": data.get("videoDetails", {}).get("title"),
                                "url": best_f["url"],
                                "thumbnail": data.get("videoDetails", {}).get("thumbnail", {}).get("thumbnails", [{}])[-1].get("url"),
                                "quality": f"{best_f.get('height', '720')}p",
                                "width": best_f.get("width", 1280), "height": best_f.get("height", 720), 
                                "engine": "native-residential"
                            }
        except: pass
        return None

    async def _engine_piped(self, url):
        video_id = self._extract_video_id(url)
        if not video_id: return None
        instances = ["https://pipedapi.kavin.rocks", "https://api.piped.victr.me", "https://pipedapi.lunar.icu", "https://api-piped.mha.fi"]
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
            for instance in instances:
                try:
                    async with session.get(f"{instance}/streams/{video_id}", timeout=5) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            streams = data.get("videoStreams", [])
                            if streams:
                                best = sorted(streams, key=lambda x: x.get("height", 0), reverse=True)[0]
                                return {
                                    "title": data.get("title"),
                                    "url": best["url"],
                                    "thumbnail": data.get("thumbnailUrl"),
                                    "quality": best.get("quality", "720p"),
                                    "width": best.get("width", 1280), "height": best.get("height", 720),
                                    "engine": "piped-api"
                                }
                except: continue
        return None

    async def _engine_invidious(self, url):
        video_id = self._extract_video_id(url)
        if not video_id: return None
        instances = ["https://inv.tux.pizza", "https://yewtu.be", "https://iv.melmac.space", "https://inv.nadeko.net"]
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
            for instance in instances:
                try:
                    async with session.get(f"{instance}/api/v1/videos/{video_id}", timeout=5) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            streams = data.get("formatStreams", [])
                            if streams:
                                best = sorted(streams, key=lambda x: int(x.get("resolution", "0").replace("p","")), reverse=True)[0]
                                return {
                                    "title": data.get("title"),
                                    "url": best["url"],
                                    "thumbnail": data.get("videoThumbnails", [{}])[0].get("url"),
                                    "quality": best.get("resolution", "720p"),
                                    "width": 1280, "height": 720, "engine": "invidious-api"
                                }
                except: continue
        return None

    async def _engine_savefrom(self, url):
        try:
            async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
                async with session.post("https://worker.savefrom.net/api/convert", json={"url": url}, timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        links = data.get("url", [])
                        if links:
                            return {
                                "title": data.get("title"),
                                "url": links[0].get("url"),
                                "thumbnail": data.get("thumb"),
                                "quality": "720p", "width": 1280, "height": 720,
                                "engine": "savefrom"
                            }
        except: pass
        return None

    async def _engine_ytdlp(self, url, use_proxy=True):
        proxy = await ProxyManager.get_proxy() if use_proxy else None
        def _extract():
            opts = {'quiet': True, 'no_warnings': True, 'nocheckcertificate': True}
            if proxy: opts['proxy'] = proxy
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
                formats = sorted([f for f in info.get('formats', []) if f.get('vcodec') != 'none' and f.get('acodec') != 'none' and f.get('url')],
                               key=lambda x: x.get('height', 0), reverse=True)
                if formats:
                    best = formats[0]
                    return {
                        "title": info.get("title"),
                        "url": best["url"],
                        "thumbnail": info.get("thumbnail"),
                        "quality": f"{best.get('height', '720')}p",
                        "width": best.get("width", 1280), "height": best.get("height", 720),
                        "engine": f"yt-dlp-{'proxy' if proxy else 'direct'}"
                    }
            return None
        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, _extract)
        except: return None

    async def _engine_selenium(self, url):
        def _selenium_task():
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            import time
            chrome_options = Options()
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            driver = webdriver.Chrome(options=chrome_options)
            try:
                driver.get(url)
                time.sleep(5)
                data_json = driver.execute_script("return JSON.stringify(window.ytInitialPlayerResponse);")
                if data_json:
                    data = json.loads(data_json)
                    vd = data.get("videoDetails", {})
                    formats = data.get("streamingData", {}).get("formats", []) + data.get("streamingData", {}).get("adaptiveFormats", [])
                    formats = [f for f in formats if "url" in f]
                    if formats:
                        best = sorted(formats, key=lambda x: x.get("height", 0), reverse=True)[0]
                        return {
                            "title": vd.get("title"),
                            "url": best["url"],
                            "thumbnail": vd.get("thumbnail", {}).get("thumbnails", [{}])[-1].get("url"),
                            "quality": f"{best.get('height', '720')}p",
                            "width": best.get("width", 1280), "height": best.get("height", 720),
                            "engine": "selenium"
                        }
            finally: driver.quit()
            return None
        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, _selenium_task)
        except: return None

    def _extract_video_id(self, url):
        match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11}).*", url)
        return match.group(1) if match else None
