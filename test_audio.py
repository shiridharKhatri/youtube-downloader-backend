import asyncio
import json
import base64
import os

async def test_audio():
    # Use a short video for testing
    url = "https://www.youtube.com/watch?v=jNQXAC9IVRw" 
    
    import aiohttp
    async with aiohttp.ClientSession() as session:
        # Start task
        async with session.get(f"http://localhost:8088/start-download?url={url}&type=audio") as resp:
            data = await resp.json()
            task_id = data['task_id']
            print(f"Started task: {task_id}")
            
        # Poll status
        for _ in range(60):
            async with session.get(f"http://localhost:8088/task-status/{task_id}") as resp:
                status = await resp.json()
                print(f"Status: {status['status']}, Progress: {status['progress']}")
                if status['status'] == 'completed':
                    print("Download completed!")
                    print(f"File: {status['file']}")
                    return
                if status['status'] == 'error':
                    print(f"Error: {status['error']}")
                    return
            await asyncio.sleep(2)

if __name__ == "__main__":
    asyncio.run(test_audio())
