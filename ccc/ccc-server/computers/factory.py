from urllib.parse import urlparse, parse_qs

from computers.computer import Computer
from computers.turtle import Turtle, TurtleType
from computers.pocket import PocketComputer, PocketUpgrade

DEFAULT_COMPUTER_LABEL = "Unnamed Computer #%s"


def _bool(params: dict, key: str) -> bool:
    return params.get(key, ["false"])[0].lower() == "true"


def create_computer(computer_id, websocket) -> Computer:
    """Parse the websocket request path and return the appropriate Computer subclass."""
    path = websocket.request.path
    params = parse_qs(urlparse(path).query)

    is_advanced = _bool(params, "isAdvanced")
    is_turtle = _bool(params, "isTurtle")
    is_pocket = _bool(params, "isPocket")
    label = params.get("computerLabel", [None])[0] or DEFAULT_COMPUTER_LABEL % computer_id
    status = params.get("status", [None])[0]

    if is_turtle:
        turtle_types = []
        flag_map = {
            "isMining":   TurtleType.MINING,
            "isCrafty":   TurtleType.CRAFTY,
            "isFelling":  TurtleType.FELLING,
            "isFarming":  TurtleType.FARMING,
            "isDigging":  TurtleType.DIGGING,
            "isMelee":    TurtleType.MELEE,
            "isEnder":    TurtleType.ENDER,
            "isWireless": TurtleType.WIRELESS,
        }
        for flag, turtle_type in flag_map.items():
            if _bool(params, flag):
                turtle_types.append(turtle_type)

        return Turtle(computer_id, websocket, is_advanced=is_advanced,
                      turtle_types=turtle_types or None, label=label, status=status)

    if is_pocket:
        if _bool(params, "isEnder"):
            upgrade = PocketUpgrade.ENDER_MODEM
        elif _bool(params, "isWireless"):
            upgrade = PocketUpgrade.WIRELESS_MODEM
        else:
            upgrade = PocketUpgrade.NONE

        return PocketComputer(computer_id, websocket, is_advanced=is_advanced,
                              upgrade=upgrade, label=label, status=status)

    return Computer(computer_id, websocket, is_advanced=is_advanced, label=label, status=status)
