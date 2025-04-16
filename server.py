import asyncio
import random
import json
from datetime import datetime, timedelta
from typing import Set

import redis.asyncio as redis
import websockets
from websockets.server import WebSocketServerProtocol

# Redis connection from default URL
r = redis.from_url("redis://redis:6379/0")

# Set of connected websocket clients
connected_clients: Set[WebSocketServerProtocol] = set()


async def register(websocket: WebSocketServerProtocol) -> None:
    """
    Register a new client connection and send the current count immediately.

    :param websocket: The WebSocket connection object.
    """
    connected_clients.add(websocket)
    print("🟢 Client connected", flush=True)
    current = await get_current_count()
    await websocket.send(json.dumps({"count": current}))


async def unregister(websocket: WebSocketServerProtocol) -> None:
    """
    Unregister a client connection when it is closed.

    :param websocket: The WebSocket connection object.
    """
    connected_clients.remove(websocket)
    print("🔴 Client disconnected", flush=True)


async def get_current_count() -> int:
    """
    Retrieve the current community count from Redis.

    :returns: The current count as an integer.
    """
    value = await r.get("community_count")
    return int(value) if value else 5000


async def increase_counter() -> None:
    """
    Increment the counter by a random value if the daily target has not been reached,
    and broadcast the updated count to all connected clients.
    """
    print("🔁 Checking whether to increment counter...", flush=True)
    added_today = int(await r.get("added_today") or 0)
    target_today = int(await r.get("target_today") or random.randint(120, 160))
    await r.set("target_today", target_today)

    if added_today >= target_today:
        print("✅ Daily limit reached, skipping increment.", flush=True)
        return

    increment = random.randint(3, 10)
    if added_today + increment > target_today:
        increment = target_today - added_today

    new_count = await r.incrby("community_count", increment)
    await r.incrby("added_today", increment)
    print(f"[{datetime.now()}] ✅ Counter increased by {increment}. New count: {new_count}", flush=True)

    payload = json.dumps({"count": new_count})
    await asyncio.gather(*[client.send(payload) for client in connected_clients])


async def update_loop() -> None:
    """
    Periodically call `increase_counter` at random intervals (30 to 90 minutes).
    """
    print("🕒 Update loop started", flush=True)
    while True:
        interval = random.randint(1800, 5400)
        print(f"⏳ Sleeping for {interval // 60} min...", flush=True)
        await asyncio.sleep(interval)
        await increase_counter()


async def daily_reset() -> None:
    """
    Reset the daily increment tracking variables at midnight UTC
    and save the current community count as a historical snapshot
    in a Redis hash under the 'history' key.
    """
    print("🗓 Daily reset loop started", flush=True)
    while True:
        now = datetime.now()
        tomorrow = datetime.combine(now.date() + timedelta(days=1), datetime.min.time())
        delta = (tomorrow - now).total_seconds()
        print(f"🛌 Sleeping until midnight UTC (in {int(delta // 3600)}h {int((delta % 3600) // 60)}m)", flush=True)
        await asyncio.sleep(delta)

        current_count = await r.get("community_count")
        if current_count is not None:
            await r.hset("history", now.date().isoformat(), int(current_count))

        await r.delete("added_today", "target_today")
        print(f"♻️ Daily reset completed. Snapshot saved for {now.date().isoformat()} = {current_count}", flush=True)


async def handler(websocket: WebSocketServerProtocol, _) -> None:
    """
    Handle lifecycle of a client WebSocket connection.

    :param websocket: The WebSocket connection object.
    :param _: The path argument (unused).
    """
    await register(websocket)
    try:
        await websocket.wait_closed()
    finally:
        await unregister(websocket)


async def main() -> None:
    """
    Start the WebSocket server and background tasks for updating and resetting.
    """
    print("🚀 Starting WebSocket server...", flush=True)
    server = await websockets.serve(handler, "0.0.0.0", 8765)
    print("✅ WebSocket server started on ws://0.0.0.0:8765", flush=True)

    # Optional: run daily_reset in background so it doesn't block
    asyncio.create_task(daily_reset())

    await asyncio.gather(update_loop(), server.wait_closed())


if __name__ == "__main__":
    print("🐍 Script started", flush=True)
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"❌ Fatal error in main(): {e}", flush=True)
