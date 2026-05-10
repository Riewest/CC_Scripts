from enum import Enum


class Protocols(str, Enum):
    TELEMETRY = "TELEMETRY"
    COMMAND = "COMMAND"
    COMMAND_SUCCESS = "COMMAND_SUCCESS"
    COMMAND_ERROR = "COMMAND_ERROR"