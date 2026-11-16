"""Constants of the openframe integration."""

from typing import Final

DOMAIN: Final = "openframe"

CONF_CLIENT_ID: Final = "client_id"

DEFAULT_PORT: Final = 8080

# The device name the frame lists in its paired devices
DEVICE_NAME: Final = "Home Assistant"

# The first openframe release with the brightness in the display state; older frames are refused
MIN_OPENFRAME_VERSION: Final = "0.6.0"
API_VERSION: Final = 1

# openframe's photo ID: the source and the SHA-1 of the photo's path
PHOTO_ID_PATTERN: Final = r"^[a-z][a-z0-9]*-[0-9a-f]{40}$"
