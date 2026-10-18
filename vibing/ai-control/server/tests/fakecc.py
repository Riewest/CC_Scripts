from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient


class FakeCC:
    def __init__(self, client: TestClient, device_id: str, secret: str, kind: str = "computer") -> None:
        self.client = client
        self.device_id = device_id
        self.secret = secret
        self.kind = kind
        self.websocket: Any = None

    def __enter__(self) -> FakeCC:
        self.websocket = self.client.websocket_connect("/ws/computer")
        self.websocket.__enter__()
        self.websocket.send_json(
            {
                "v": 1,
                "type": "hello",
                "id": "fake-hello",
                "data": {
                    "device_id": self.device_id,
                    "secret": self.secret,
                    "kind": self.kind,
                    "label": "Fake CC",
                    "cc_version": "1.120.0",
                    "client_version": "test",
                    "capabilities": ["terminal", "filesystem"],
                },
            }
        )
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        if self.websocket is not None:
            self.websocket.__exit__(exc_type, exc_value, traceback)

    def receive_json(self) -> dict:
        if self.websocket is None:
            raise RuntimeError("fake client is not connected")
        return self.websocket.receive_json()

    def send_json(self, message: dict) -> None:
        if self.websocket is None:
            raise RuntimeError("fake client is not connected")
        self.websocket.send_json(message)

    def disconnect(self) -> None:
        if self.websocket is None:
            raise RuntimeError("fake client is not connected")
        self.websocket.close()
