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
    _proxies = []
    
    @classmethod
    async def get_proxy(cls, type="residential"):
        if type == "residential" and cls._residential_proxy:
            return cls._residential_proxy

        if not cls._proxies:
            try:
                print("[Proxy] Fetching fresh free proxy list from TheSpeedX...")
                async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
                    async with session.get("https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt", timeout=10) as resp:
                        if resp.status == 200:
                            text = await resp.text()
                            cls._proxies = [f"http://{line.strip()}" for line in text.split('\n') if line.strip()]
                            random.shuffle(cls._proxies)
                            print(f"[Proxy] Loaded {len(cls._proxies)} free HTTP proxies.")
            except Exception as e:
                print(f"[Proxy] Fetch error: {e}")
        
        if cls._proxies:
            return random.choice(cls._proxies)
        return cls._residential_proxy

class YouTubeReverse:
    """
    High-speed Reverse Engineered YouTube Engine.
    Modified to prioritize functional public APIs.
    """
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        }

    async def fetch_video_info(self, url):
        """
        Races multiple reverse engines to get the fastest valid link.
        """
        # FASTEST engines (sequential or fast-fail)
        fast_engines = [
            self._engine_native,      # Directly from YouTube HTML (Reverse)
            self._engine_savefrom,    # SaveFrom (Very fast scraper)
        ]
        
        for engine in fast_engines:
            try:
                print(f"[*] Trying FAST engine: {engine.__name__}")
                result = await engine(url)
                if result and result.get("url"):
                    return result
            except: continue

        # Parallel race for API Proxies (Piped/Invidious) - Speed boost
        print("[*] Racing Proxy APIs (Piped/Invidious)...")
        proxy_engines = [self._engine_piped(url), self._engine_invidious(url)]
        for future in asyncio.as_completed(proxy_engines, timeout=10):
            try:
                result = await future
                if result and result.get("url"):
                    return result
            except: continue

        # HEAVY fallbacks (sequential)
        heavy_engines = [
            self._engine_ytdlp,       # Gold Standard
            self._engine_selenium,    # Last Resort
        ]
        
        for engine in heavy_engines:
            try:
                print(f"[*] Trying HEAVY engine: {engine.__name__}")
                result = await engine(url)
                if result and result.get("url"):
                    return result
            except Exception as e:
                print(f"[Reverse] {engine.__name__} failed: {e}")
                continue
                
        return None

    async def _engine_selenium(self, url):
        """
        LAST RESORT: Use Selenium to bypass complex JS blocks.
        """
        def _selenium_task():
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            import time

            chrome_options = Options()
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument(f"--user-agent={self.headers['User-Agent']}")
            
            driver = None
            try:
                driver = webdriver.Chrome(options=chrome_options)
                # Set page load timeout to be safe
                driver.set_page_load_timeout(20)
                driver.get(url)
                
                # Wait for player data to load
                time.sleep(3)
                
                script = "return JSON.stringify(window.ytInitialPlayerResponse);"
                data_json = driver.execute_script(script)
                if not data_json:
                    # Fallback search in HTML
                    html = driver.page_source
                    match = re.search(r'ytInitialPlayerResponse\s*=\s*({.+?});', html)
                    if match: data_json = match.group(1)

                if data_json:
                    data = json.loads(data_json)
                    streaming_data = data.get("streamingData", {})
                    formats = streaming_data.get("formats", []) + streaming_data.get("adaptiveFormats", [])
                    formats = [f for f in formats if "url" in f]
                    
                    if formats:
                        best_f = sorted(formats, key=lambda x: x.get("height", 0), reverse=True)[0]
                        return {
                            "title": data.get("videoDetails", {}).get("title", "YT Video"),
                            "url": best_f["url"],
                            "thumbnail": data.get("videoDetails", {}).get("thumbnail", {}).get("thumbnails", [{}])[-1].get("url"),
                            "quality": f"{best_f.get('height', '720')}p",
                            "engine": "selenium-reverse"
                        }
            except Exception as e:
                print(f"[Selenium] Error: {e}")
            finally:
                if driver: driver.quit()
            return None

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _selenium_task)

    def _extract_video_id(self, url):
        import re
        patterns = [
            r"(?:v=|\/)([0-9A-Za-z_-]{11}).*",
            r"youtu\.be\/([0-9A-Za-z_-]{11})",
            r"embed\/([0-9A-Za-z_-]{11})",
            r"shorts\/([0-9A-Za-z_-]{11})"
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    async def _engine_native(self, url):
        """
        EXTRACTOR: Directly from YouTube HTML. 
        """
        video_id = self._extract_video_id(url)
        if not video_id: return None

        try:
            # Cycle through high-quality User Agents
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
            }
            
            # LOAD COOKIES if present
            jar = aiohttp.CookieJar()
            cookie_path = os.path.join(os.path.dirname(__file__), 'cookies.txt')
            if os.path.exists(cookie_path):
                print(f"[Native] Loading cookies from {cookie_path}")
                try:
                    import http.cookiejar
                    # Netscape format parser
                    mozilla_jar = http.cookiejar.MozillaCookieJar(cookie_path)
                    mozilla_jar.load(ignore_discard=True, ignore_expires=True)
                    for cookie in mozilla_jar:
                        jar.update_cookies({cookie.name: cookie.value}, url="https://youtube.com")
                except Exception as ce:
                    print(f"[Native] Cookie load error: {ce}")

            # Try residential proxy first, then direct
            test_proxies = [await ProxyManager.get_proxy("residential"), None]

            for proxy_url in test_proxies:
                try:
                    p_label = proxy_url if proxy_url else "DIRECT"
                    print(f"[*] Trying Native Extraction via {p_label}")
                    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False), cookie_jar=jar) as session:
                        async with session.get(f"https://www.youtube.com/watch?v={video_id}", headers=headers, proxy=proxy_url, timeout=10) as resp:
                            if resp.status != 200: continue
                            html = await resp.text()

                            import re
                            match = re.search(r'ytInitialPlayerResponse\s*=\s*({.+?});', html)
                            if not match:
                                match = re.search(r'var\s+ytInitialPlayerResponse\s*=\s*({.+?});', html)
                            
                            if match:
                                data = json.loads(match.group(1))
                                streaming_data = data.get("streamingData", {})
                                formats = streaming_data.get("formats", []) + streaming_data.get("adaptiveFormats", [])
                                
                                best_url = None
                                title = data.get("videoDetails", {}).get("title", "YT Video")
                                thumb = data.get("videoDetails", {}).get("thumbnail", {}).get("thumbnails", [{}])[-1].get("url")
                                
                                formats = [f for f in formats if "url" in f]
                                combined = sorted([f for f in formats if f.get("acodec") != "none" and f.get("vcodec") != "none"], 
                                                key=lambda x: x.get("height", 0), reverse=True)
                                
                                best_f = combined[0] if combined else (sorted(formats, key=lambda x: x.get("height", 0), reverse=True)[0] if formats else None)

                                if best_f:
                                    return {
                                        "title": title,
                                        "url": best_f["url"],
                                        "thumbnail": thumb,
                                        "quality": f"{best_f.get('height', '720')}p",
                                        "engine": "native-reverse"
                                    }
                except Exception as ex:
                    print(f"[Native] Error on {p_label}: {ex}")
                    continue
        except Exception as e:
            print(f"[Native] Outer Exception: {e}")
        return None

    async def _engine_piped(self, url):
        """
        Piped API Proxy - Excellent for bypassing IP blocks.
        """
        video_id = self._extract_video_id(url)
        if not video_id: return None
        
        instances = [
            "https://pipedapi.kavin.rocks", 
            "https://api.piped.private.coffee", 
            "https://pipedapi.moomoo.me",
            "https://piped.video",
            "https://piped.tokhmi.xyz",
            "https://pipedapi.smnz.de",
            "https://pipedapi.adminforge.de",
            "https://piped-api.garudalinux.org"
        ]
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
                                    "engine": "piped-api"
                                }
                except Exception as e:
                    # Silently ignore connection errors but log status mismatch
                    continue
        return None

    async def _engine_savefrom(self, url):
        """
        SaveFrom.net Scraper
        """
        try:
            print("[*] Trying engine: SaveFrom")
            async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
                post_data = {"url": url}
                # Use their internal API endpoint
                async with session.post("https://worker.savefrom.net/api/convert", json=post_data, timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        title = data.get("title", "YouTube Video")
                        thumbnail = data.get("thumb")
                        links = data.get("url", [])
                        if links:
                            # Usually the first link is the best
                            return {
                                "title": title,
                                "url": links[0].get("url"),
                                "thumbnail": thumbnail,
                                "quality": links[0].get("quality", "720p"),
                                "engine": "savefrom"
                            }
        except: pass
        return None

    async def _engine_ytdlp(self, url):
        """
        High-performance yt-dlp library extraction with optional proxy.
        """
        proxy_url = await ProxyManager.get_proxy("residential")
        
        def _extract():
            # Try residential proxy first, then direct
            for p in [proxy_url, None]:
                try:
                    ydl_opts = {
                        'quiet': True,
                        'no_warnings': True,
                        'nocheckcertificate': True,
                        'noplaylist': True,
                        'format': 'best[ext=mp4]/best',
                    }
                    if p: 
                        ydl_opts['proxy'] = p
                        print(f"[*] Trying yt-dlp via Proxy: {p[:30]}...")
                    else:
                        print("[*] Trying yt-dlp DIRECT...")
                    
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        info = ydl.extract_info(url, download=False)
                        if info and info.get("url"):
                            return {
                                "title": info.get("title"),
                                "url": info.get("url"),
                                "thumbnail": info.get("thumbnail"),
                                "quality": f"{info.get('height', '720')}p",
                                "engine": "yt-dlp"
                            }
                except Exception as e:
                    print(f"[yt-dlp] Attempt failed: {e}")
                    continue
            return None

        # Run in executor to avoid blocking
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _extract)

    async def _engine_invidious(self, url):
        """
        Invidious API Proxy.
        """
        video_id = self._extract_video_id(url)
        if not video_id: return None
        
        instances = [
            "https://inv.tux.pizza", 
            "https://yewtu.be", 
            "https://vid.puffyan.us",
            "https://invidious.nerdvpn.de",
            "https://inv.nadeko.net",
            "https://invidious.perennialte.ch",
            "https://invidious.no-logs.com",
            "https://invidious.jing.rocks",
            "https://invidious.privacydev.net"
        ]
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
                                    "engine": "invidious-api"
                                }
                except Exception as e:
                    continue
        return None

    # Removed _engine_cobalt_v10 (Deprecated)
