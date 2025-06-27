import asyncio
import websockets

HOST = "0.0.0.0"
PORT = 8765

async def echo(websocket):
    async for message in websocket:
        print(f"Received: {message}")
        await websocket.send(message)

async def main():
    async with websockets.serve(echo, HOST, PORT):
        print(f"WebSocket server running on ws://{HOST}:{PORT}")
        await asyncio.Future()  # run forever

if __name__ == "__main__":
    asyncio.run(main())
