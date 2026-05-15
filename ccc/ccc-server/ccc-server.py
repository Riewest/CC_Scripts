#!/usr/bin/env python

import asyncio
import json
import logging
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer


from protocols import Protocols
from computers.computer import Computer
from computers.factory import create_computer

from websockets.asyncio.server import serve
from websockets import broadcast
from websockets.exceptions import ConnectionClosedError

logger = logging.getLogger(__name__)
logger.setLevel(os.getenv("WS_LOG_LEVEL", "INFO").upper())
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)

# create formatter
formatter = logging.Formatter('%(levelname)s-%(asctime)s %(message)s', datefmt='%H:%M:%S')

# add formatter to ch
ch.setFormatter(formatter)

# add ch to logger
logger.addHandler(ch)

connected_computers = {}
event_loop = None

def recieveTelemetry(computer:Computer, data:dict):
    logger.info(f"Received telemetry from computer: {computer.computer_id}")
    logger.debug(f"{data}")
    computer.telemetry = data

def processMessages(computer:Computer, message_raw:str):
    try:
        message = json.loads(message_raw)
        protocol = message.get("protocol")
        if protocol == Protocols.TELEMETRY:
            recieveTelemetry(computer, message.get("data"))
        else:
            logger.warning(f"Unknown protocol: {protocol}")
    except json.JSONDecodeError:
        logger.error("Failed to decode JSON message")

async def recieve(websocket):
    # Check if the "computer_id" header is present
    computer_id = websocket.request.headers.get("computer_id")
    if not computer_id:
        logger.warning("Connection denied: Missing 'computer_id' header")
        await websocket.close()
        return
    
    connecting_computer = create_computer(computer_id, websocket)

    path = websocket.request.path

    group = type(connecting_computer).__name__
    # Initialize Path
    if group not in connected_computers:
        connected_computers[group] = dict()

    
    # Keep track of connected clients
    connected_computers[group][computer_id] = connecting_computer


    logger.info(f"Computer {computer_id} Connected - Type: {group}")
    try:
        # Handle incoming messages
        async for message in websocket:
            try:
                processMessages(connected_computers[group][computer_id], message)
            except Exception as e:
                logger.error(f"Error processing message: {e}")
    
    except ConnectionClosedError:
        if computer_id in connected_computers[group]:
            del connected_computers[group][computer_id]
            logger.info(f"Computer {computer_id} Disconnected - Type: {group}")
    finally:
        # Remove the client when they disconnect
        if computer_id in connected_computers[group]:
            del connected_computers[group][computer_id]
            logger.info(f"Computer {computer_id} Disconnected - Type: {group}")

async def pathBroadcast(path, message):
    # Broadcast the message to all clients on the specified path
    if path in connected_computers and len(connected_computers[path]) > 0:
        broadcast(connected_computers[path].values(), message, raise_exceptions=False)

# --- HTTP Dashboard ---

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

def serialize_computers():
    result = {}
    for channel, computers in connected_computers.items():
        result[channel] = {}
        for cid, computer in computers.items():
            t = computer.telemetry or {}
            result[channel][cid] = {
                "id": cid,
                "label": t.get("label"),
                "is_turtle": t.get("is_turtle"),
                "is_pocket": t.get("is_pocket"),
                "telemetry": t,
            }
    return result

class DashboardHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # silence default HTTP request logging

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            index_path = os.path.join(STATIC_DIR, "index.html")
            try:
                with open(index_path, "rb") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(content)
            except FileNotFoundError:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"index.html not found")
        elif self.path == "/api/computers":
            data = json.dumps(serialize_computers())
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(data.encode())
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/api/command":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            try:
                payload = json.loads(body)
                channel = payload.get("channel")
                computer_id = payload.get("computer_id")
                code = payload.get("code", "").strip()
                if not channel or not computer_id or not code:
                    self.send_response(400)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": "Missing channel, computer_id, or code"}).encode())
                    return
                computer = connected_computers.get(channel, {}).get(computer_id)
                if not computer:
                    self.send_response(404)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": "Computer not found"}).encode())
                    return
                future = asyncio.run_coroutine_threadsafe(computer.sendCommand(code), event_loop)
                future.result(timeout=5)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": True}).encode())
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())
        else:
            self.send_response(404)
            self.end_headers()

def start_http_server(port=8767):
    server = HTTPServer(("localhost", port), DashboardHandler)
    logger.info(f"Dashboard available at http://localhost:{port}")
    server.serve_forever()

async def main():
    global event_loop
    event_loop = asyncio.get_running_loop()
    async with serve(recieve, "localhost", 8766) as server:
        await server.serve_forever()

http_thread = threading.Thread(target=start_http_server, daemon=True)
http_thread.start()
asyncio.run(main())