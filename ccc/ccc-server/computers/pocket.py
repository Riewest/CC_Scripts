from collections.abc import Iterable
from enum import Enum

from computers.computer import Computer


class PocketUpgrade(Enum):
	NONE = "none"
	SPEAKER = "speaker"
	WIRELESS_MODEM = "wireless_modem"
	ENDER_MODEM = "ender_modem"


class PocketComputer(Computer):
	"""ComputerCraft pocket computer type."""

	def __init__(self, *args, upgrade: PocketUpgrade | str | None = None, **kwargs):
		super().__init__(*args, **kwargs)
		self.upgrade = self._normalize_upgrade(upgrade) if upgrade is not None else PocketUpgrade.NONE

	def _normalize_upgrade(self, upgrade):
		if isinstance(upgrade, PocketUpgrade):
			return upgrade
		if isinstance(upgrade, str):
			for value in PocketUpgrade:
				if upgrade == value.name or upgrade == value.value:
					return value
		raise ValueError(f"Invalid pocket upgrade: {upgrade}")

	def set_upgrade(self, upgrade: PocketUpgrade | str | None):
		self.upgrade = self._normalize_upgrade(upgrade) if upgrade is not None else PocketUpgrade.NONE

	def has_upgrade(self, upgrade: PocketUpgrade | str) -> bool:
		return self.upgrade == self._normalize_upgrade(upgrade)
