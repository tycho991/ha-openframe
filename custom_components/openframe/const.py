"""Constants of the openframe integration."""

from typing import Final

DOMAIN: Final = "openframe"

CONF_CLIENT_ID: Final = "client_id"

DEFAULT_PORT: Final = 8080

# The device name the frame lists in its paired devices
DEVICE_NAME: Final = "Home Assistant"

# The first openframe release with the slideshow API; older frames are refused
MIN_OPENFRAME_VERSION: Final = "0.5.0"
API_VERSION: Final = 1
