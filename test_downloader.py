import asyncio
from youtube_downloader import YouTubeDownloader

async def main():
    downloader = YouTubeDownloader()
    url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    print(f"Testing URL: {url}")
    info = await downloader.get_media_info(url)
    print("Result:")
    print(info)

if __name__ == "__main__":
    asyncio.run(main())
