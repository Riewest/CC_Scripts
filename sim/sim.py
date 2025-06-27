import asyncio
import json
from flask import Flask, render_template
import threading
import websockets

app = Flask(__name__)

connected_client = None
inventory_queue = None  # Will be created inside the event loop
loop = None  # Global event loop reference

async def ws_handler(websocket):
    global connected_client, inventory_queue
    connected_client = websocket
    try:
        async for message in websocket:
            await inventory_queue.put(message)
            await websocket.send(json.dumps({"status": "received"}))
    except websockets.ConnectionClosed:
        print("Client disconnected")
        connected_client = None

async def ws_server():
    global inventory_queue
    inventory_queue = asyncio.Queue()
    async with websockets.serve(ws_handler, "0.0.0.0", 8765):
        print("WebSocket server started on port 8765")
        await asyncio.Future()  # run forever

def run_flask():
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)

@app.route("/inventory_view")
def inventory_view():
    global connected_client, inventory_queue, loop

    if connected_client is None:
        return "No client connected", 503

    async def request_and_wait():
        await connected_client.send("request_inventory")
        try:
            message = await asyncio.wait_for(inventory_queue.get(), timeout=5)
            return json.loads(message)
        except asyncio.TimeoutError:
            return None

    # Schedule the coroutine in the existing loop, wait for result synchronously
    future = asyncio.run_coroutine_threadsafe(request_and_wait(), loop)
    try:
        inventories = future.result(timeout=6)
    except asyncio.TimeoutError:
        return "Timeout waiting for inventory data", 504

    if not inventories:
        return "No inventory data received", 504

    if isinstance(inventories, dict):
        inventories = [inventories]

    return render_template("inventory_view.html", inventories=inventories)

def main():
    global loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # Start Flask in separate thread
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    # Run websocket server (and event loop) in main thread
    loop.run_until_complete(ws_server())

if __name__ == "__main__":
    main()
