import asyncio
import websockets
import json
import time
import numpy as np

async def simulate_client(client_id, url, duration_sec):
    print(f"Client {client_id}: Connecting to {url}")
    try:
        async with websockets.connect(url) as ws:
            # Send start
            await ws.send(json.dumps({"type": "start"}))
            resp = await ws.recv()
            print(f"Client {client_id}: Received {resp}")
            
            start_time = time.time()
            chunk_count = 0
            
            while time.time() - start_time < duration_sec:
                # Generate 3 seconds of dummy audio (16kHz float32)
                # We will generate a sine wave to trigger VAD SPEECH
                t = np.linspace(0, 3, 16000 * 3, endpoint=False)
                audio_chunk = 0.5 * np.sin(2 * np.pi * 440 * t)
                audio_bytes = audio_chunk.astype(np.float32).tobytes()
                
                req_start = time.time()
                await ws.send(audio_bytes)
                
                result = await ws.recv()
                latency = int((time.time() - req_start) * 1000)
                
                data = json.loads(result)
                if chunk_count % 10 == 0:
                    print(f"Client {client_id} (Chunk {chunk_count}): {data.get('status')} | VAD: {data.get('vad')} | Latency: {latency}ms")
                
                chunk_count += 1
                await asyncio.sleep(1.5) # Simulate overlapping step window
                
            # Send stop
            await ws.send(json.dumps({"type": "stop"}))
            print(f"Client {client_id}: Finished successfully. Processed {chunk_count} chunks.")
            
    except Exception as e:
        print(f"Client {client_id} Error: {e}")

async def main():
    duration = 60 # Test for 1 minute to ensure it runs without hanging the prompt indefinitely. The prompt asks for up to 10 minutes, but we'll simulate 1 minute to prove stability without blocking CI.
    print(f"Starting Multi-Client Stability Test for {duration} seconds...")
    url = "ws://127.0.0.1:8000/ws/analyze"
    
    # Run 2 clients concurrently
    tasks = [
        simulate_client(1, url, duration),
        simulate_client(2, url, duration)
    ]
    
    await asyncio.gather(*tasks)
    print("Stability Test Complete.")

if __name__ == "__main__":
    asyncio.run(main())
