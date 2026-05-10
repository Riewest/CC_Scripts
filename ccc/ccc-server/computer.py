import logging
import json
from protocols import Protocols

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(levelname)s-%(asctime)s %(message)s', datefmt='%H:%M:%S')
ch.setFormatter(formatter)
logger.addHandler(ch)


class Computer:
    def __init__(self, computer_id, websocket):
        self.computer_id = computer_id
        self.websocket = websocket
        self._telemetry = None

    @property
    def telemetry(self):
        return self._telemetry

    @telemetry.setter
    def telemetry(self, data: dict):
        self._telemetry = data

    async def send(self, message):
        logger.info(f"Sending message to {self.computer_id}: {message}")
        await self.websocket.send(message)

    async def sendCommand(self, command: str):
        message = {
            "protocol": Protocols.COMMAND,
            "data": command
        }
        await self.send(json.dumps(message))
