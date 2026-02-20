import asyncio
import aiohttp
import json

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
        engines = [
            self._engine_native,      # NEW: Directly from YouTube (No reliance on 3rd parties)
            self._engine_cobalt_v10,  # Fallback to Cobalt
            self._engine_dummy 
        ]
        
        # We can run these in parallel or sequence. Sequence is better for "not depending on others"
        # as it tries the native one first.
        for engine in engines:
            try:
                result = await engine(url)
                if result and result.get("url"):
                    return result
            except Exception as e:
                print(f"[Reverse] {engine.__name__} failed: {e}")
                continue
        return None

    def _extract_video_id(self, url):
        import re
        patterns = [
            r"(?:v=|\/)([0-9A-Za-z_-]{11}).*",
            r"youtu\.be\/([0-9A-Za-z_-]{11})",
            r"embed\/([0-9A-Za-z_-]{11})"
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    async def _engine_native(self, url):
        """
        EXTRACTOR: Directly from YouTube HTML. 
        Zero dependencies on 3rd party APIs.
        """
        video_id = self._extract_video_id(url)
        if not video_id: return None

        try:
            # Use a generic desktop user agent
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
                "Accept-Language": "en-US,en;q=0.9",
            }
            
            async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
                async with session.get(f"https://www.youtube.com/watch?v={video_id}", headers=headers, timeout=10) as resp:
                    if resp.status != 200: return None
                    html = await resp.text()

                    # Find ytInitialPlayerResponse
                    import json
                    import re
                    match = re.search(r'ytInitialPlayerResponse\s*=\s*({.+?});', html)
                    if not match:
                        # Alternative match pattern
                        match = re.search(r'var\s+ytInitialPlayerResponse\s*=\s*({.+?});', html)
                    
                    if match:
                        data = json.loads(match.group(1))
                        streaming_data = data.get("streamingData", {})
                        formats = streaming_data.get("formats", []) + streaming_data.get("adaptiveFormats", [])
                        
                        # Find best format with a URL (some might be ciphered 'signatureCipher')
                        # For simple "not depend on other", we prioritize non-ciphered links
                        best_url = None
                        title = data.get("videoDetails", {}).get("title", "YT Video")
                        thumb = data.get("videoDetails", {}).get("thumbnail", {}).get("thumbnails", [{}])[-1].get("url")
                        
                        # Sort formats by resolution (height) descending
                        formats = [f for f in formats if "url" in f]
                        combined = sorted([f for f in formats if f.get("acodec") != "none" and f.get("vcodec") != "none"], 
                                         key=lambda x: x.get("height", 0), reverse=True)
                        
                        best_f = None
                        if combined:
                            best_f = combined[0]
                        elif formats:
                            best_f = sorted(formats, key=lambda x: x.get("height", 0), reverse=True)[0]

                        if best_f:
                            return {
                                "title": title,
                                "url": best_f["url"],
                                "thumbnail": thumb,
                                "quality": f"{best_f.get('height', '720')}p",
                                "engine": "native"
                            }
        except Exception as e:
            print(f"[Native] Error: {e}")
        return None

    async def _engine_cobalt_v10(self, url):
        """
        Updated Cobalt V10 API (Requires valid instance).
        Since public instances are restricted, this acts as a framework.
        """
        try:
            # Note: Many public instances are now authenticated. 
            # We will use the V10 format for future-proofing.
            async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
                payload = {"url": url}
                headers = {"Accept": "application/json", "Content-Type": "application/json"}
                # Try a known instance if available or stay with standard
                async with session.post("https://api.cobalt.tools/", json=payload, headers=headers, timeout=5) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("url"):
                            return {"title": "YT Video", "url": data.get("url"), "quality": "HD", "engine": "cobalt"}
        except: pass
        return None

    async def _engine_dummy(self, url):
        return None
