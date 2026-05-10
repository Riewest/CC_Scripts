#!/usr/bin/env python

import asyncio
import json
import logging

from websockets.asyncio.server import serve
from websockets import broadcast
from websockets.exceptions import ConnectionClosedError

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)

# create formatter
formatter = logging.Formatter('%(levelname)s-%(asctime)s %(message)s', datefmt='%H:%M:%S')

# add formatter to ch
ch.setFormatter(formatter)

# add ch to logger
logger.addHandler(ch)


connected_clients = {}

async def relay(websocket):
    # Check if the "computer_id" header is present
    computer_id = websocket.request.headers.get("computer_id")
    if not computer_id:
        logger.warning("Connection denied: Missing 'computer_id' header")
        await websocket.close()
        return
    
    path = websocket.request.path
    # Initialize Path
    if path not in connected_clients:
        connected_clients[path] = dict()

    # Keep track of connected clients
    connected_clients[path][computer_id] = websocket

    logger.info(f"Computer {computer_id} Connected - Channel: {path}")
    try:
        # Handle incoming messages
        async for message in websocket:
            
            logger.info(f"{path} {computer_id}: {message}")
            try:
                json_object = json.loads(message)
                if isinstance(json_object, dict) and "protocol" in json_object:
                    json_object["subprotocol"] = json_object.pop("protocol")
                    message = json.dumps(json_object)
                # Broadcast the message to all clients on the same path
                await pathBroadcast(path, message)
            except ValueError as e:
                pass
    
    except ConnectionClosedError:
        if computer_id in connected_clients[path]:
            del connected_clients[path][computer_id]
            logger.info(f"Computer {computer_id} Disconnected - Channel: {path}")
    finally:
        # Remove the client when they disconnect
        if computer_id in connected_clients[path]:
            del connected_clients[path][computer_id]
            logger.info(f"Computer {computer_id} Disconnected - Channel: {path}")

async def pathBroadcast(path, message):
    # Broadcast the message to all clients on the specified path
    if path in connected_clients and len(connected_clients[path]) > 0:
        broadcast(connected_clients[path].values(), message, raise_exceptions=False)

async def main():
    async with serve(relay, "localhost", 8765) as server:
        await server.serve_forever()

asyncio.run(main())