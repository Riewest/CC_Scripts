from collections.abc import Iterable
from enum import Enum

from computers.computer import Computer


class TurtleType(Enum):
	DEFAULT = "turtle"
	MINING = "mining_turtle"
	CRAFTY = "crafty_turtle"
	FELLING = "felling_turtle"
	FARMING = "farming_turtle"
	DIGGING = "digging_turtle"
	MELEE = "melee_turtle"
	ENDER = "ender_turtle"
	WIRELESS = "wireless_turtle"


class Turtle(Computer):
	"""ComputerCraft turtle computer type."""

	def __init__(self, *args, turtle_types: Iterable[TurtleType | str] | None = None, **kwargs):
		super().__init__(*args, **kwargs)
		self.types = set()

		if turtle_types is None:
			self.types.add(TurtleType.DEFAULT)
		else:
			self.set_types(turtle_types)

	def _normalize_type(self, turtle_type):
		if isinstance(turtle_type, TurtleType):
			return turtle_type
		if isinstance(turtle_type, str):
			for value in TurtleType:
				if turtle_type == value.name or turtle_type == value.value:
					return value
		raise ValueError(f"Invalid turtle type: {turtle_type}")

	def set_types(self, turtle_types):
		self.types = {self._normalize_type(t) for t in turtle_types}
		if not self.types:
			self.types.add(TurtleType.DEFAULT)
		self.type = next(iter(self.types))

	def add_type(self, turtle_type):
		self.types.add(self._normalize_type(turtle_type))
		self.type = next(iter(self.types))

	def remove_type(self, turtle_type):
		self.types.discard(self._normalize_type(turtle_type))
		if not self.types:
			self.types.add(TurtleType.DEFAULT)
		self.type = next(iter(self.types))

	def has_type(self, turtle_type):
		return self._normalize_type(turtle_type) in self.types