from __future__ import annotations

from enum import Enum


class StringEnum(str, Enum):
    """Small helper that keeps enum values friendly for JSON and CLI output."""

    def __str__(self) -> str:
        return self.value


class TemperatureUnit(StringEnum):
    CELSIUS = "celsius"
    FAHRENHEIT = "fahrenheit"


class RuleContext(StringEnum):
    STANDARD = "standard"
    POST_HORMONAL = "post_hormonal"
    POSTPARTUM = "postpartum"
    POST_MISCARRIAGE = "post_miscarriage"
    DELAYED_FERTILITY = "delayed_fertility"


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


class MucusColor(StringEnum):
    NONE = "none"
    CLOUDY = "cloudy"
    WHITE = "white"
    YELLOW = "yellow"
    CLEAR = "clear"


class MucusTexture(StringEnum):
    NONE = "none"
    STICKY = "sticky"
    TACKY = "tacky"
    CRUMBLY = "crumbly"
    CREAMY = "creamy"
    STRETCHY = "stretchy"
    SLIPPERY = "slippery"


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
