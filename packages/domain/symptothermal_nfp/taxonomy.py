from __future__ import annotations

from enum import Enum


class StringEnum(str, Enum):
    """Small helper that keeps enum values friendly for JSON and CLI output."""

    def __str__(self) -> str:
        return self.value


class TemperatureUnit(StringEnum):
    CELSIUS = "celsius"
    FAHRENHEIT = "fahrenheit"


class FluidSensation(StringEnum):
    DRY = "dry"
    STICKY = "sticky"
    CREAMY = "creamy"
    WATERY = "watery"
    SLIPPERY = "slippery"


class FluidQuantity(StringEnum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class BleedingLevel(StringEnum):
    NONE = "none"
    SPOTTING = "spotting"
    LIGHT = "light"
    MEDIUM = "medium"
    HEAVY = "heavy"


class CervixHeight(StringEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class CervixFirmness(StringEnum):
    FIRM = "firm"
    MEDIUM = "medium"
    SOFT = "soft"


class CervixOpening(StringEnum):
    CLOSED = "closed"
    MEDIUM = "medium"
    OPEN = "open"


class FertilityState(StringEnum):
    PRE_OV_INFERTILE = "pre_ov_infertile"
    FERTILE = "fertile"
    POST_OV_INFERTILE = "post_ov_infertile"
