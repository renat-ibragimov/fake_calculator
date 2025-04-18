import asyncio
import random
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Set

import websockets
from websockets.server import WebSocketServerProtocol

BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "data/counter_state.json"
HISTORY_FILE = BASE_DIR / "data/history.csv"
DEFAULT_COUNT = 1138314
connected_clients: Set[WebSocketServerProtocol] = set()

def load_state() -> dict:
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {
            "community_count": DEFAULT_COUNT,
            "added_today": 0,
            "target_today": random.randint(120, 160)
        }

def save_state(state: dict) -> None:
    with open(DATA_FILE, "w") as f:
        json.dump(state, f)

    if not Path(HISTORY_FILE).exists():
        with open(HISTORY_FILE, "w") as f:
            f.write("date,count\n")
            f.write(f"{datetime.now().date()},{state['community_count']}\n")

async def register(websocket: WebSocketServerProtocol) -> None:
    connected_clients.add(websocket)
    print("🟢 Client connected", flush=True)
    state = load_state()
    await websocket.send(json.dumps({"count": state["community_count"]}))

async def unregister(websocket: WebSocketServerProtocol) -> None:
    connected_clients.remove(websocket)
    print("🔴 Client disconnected", flush=True)

async def increase_counter() -> None:
    print("🔁 Checking whether to increment counter...", flush=True)
    state = load_state()

    if state["added_today"] >= state["target_today"]:
        print("✅ Daily limit reached, skipping increment.", flush=True)
        return

    increment = random.randint(3, 10)
    if state["added_today"] + increment > state["target_today"]:
        increment = state["target_today"] - state["added_today"]

    state["community_count"] += increment
    state["added_today"] += increment
    save_state(state)

    print(f"[{datetime.now()}] ✅ Counter increased by {increment}. New count: {state['community_count']}", flush=True)

    payload = json.dumps({"count": state["community_count"]})
    await asyncio.gather(*[client.send(payload) for client in connected_clients])

async def update_loop() -> None:
    print("🕒 Update loop started", flush=True)
    while True:
        interval = random.randint(1800, 5400)
        print(f"⏳ Sleeping for {interval // 60} min...", flush=True)
        await asyncio.sleep(interval)
        await increase_counter()

async def daily_reset() -> None:
    print("🗓 Daily reset loop started", flush=True)
    while True:
        now = datetime.now()
        tomorrow = datetime.combine(now.date() + timedelta(days=1), datetime.min.time())
        delta = (tomorrow - now).total_seconds()
        print(f"🛌 Sleeping until midnight UTC (in {int(delta // 3600)}h {int((delta % 3600) // 60)}m)", flush=True)
        await asyncio.sleep(delta)

        state = load_state()
        with open(HISTORY_FILE, "a") as f:
            f.write(f"{now.date()},{state['community_count']}\n")
        state["added_today"] = 0
        state["target_today"] = random.randint(120, 160)
        save_state(state)

        print(f"♻️ Daily reset completed. Snapshot saved for {now.date()} = {state['community_count']}", flush=True)

async def handler(websocket: WebSocketServerProtocol, _) -> None:
    await register(websocket)
    try:
        await websocket.wait_closed()
    finally:
        await unregister(websocket)

async def main() -> None:
    print("🚀 Starting WebSocket server...", flush=True)
    server = await websockets.serve(handler, "0.0.0.0", 8765)
    print("✅ WebSocket server started on ws://0.0.0.0:8765", flush=True)
    asyncio.create_task(daily_reset())
    await asyncio.gather(update_loop(), server.wait_closed())

if __name__ == "__main__":
    print("🐍 Script started", flush=True)
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"❌ Fatal error in main(): {e}", flush=True)
