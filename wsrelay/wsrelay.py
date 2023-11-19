#!/usr/bin/env python

import asyncio
import json
import logging

from websockets.server import serve
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

async def relay(websocket, path):
    # Check if the "computer_id" header is present
    computer_id = websocket.request_headers.get("computer_id")
    if not computer_id:
        logger.warning("Connection denied: Missing 'computer_id' header")
        await websocket.close()
        return
    
    # Initialize Path
    if path not in connected_clients:
        connected_clients[path] = dict()
    
    # If there was already a connection then close it
    # if computer_id in connected_clients[path]:
    #     await websocket.close()

    # Keep track of connected clients
    connected_clients[path][computer_id] = websocket

    logger.info(f"Computer {computer_id} Connected - Channel: {path}")
    try:
        # Handle incoming messages
        async for message in websocket:
            logger.info(f"{path} {computer_id}: {message}")
            try:
                json_object = json.loads(message)
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
        # for client in connected_clients[path].values():
        #     try:
        #         await client.send(message)
        #     except asyncio.exceptions.IncompleteReadError:
        #         pass

async def main():
    async with serve(relay, "0.0.0.0", 8765, compression=None):
        logger.info("WSRelay Started... Time to Conquer the Server :)")
        await asyncio.Future()  # run forever

asyncio.run(main())