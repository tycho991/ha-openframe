# Spec Delta

## Purpose

A dashboard card for one openframe frame that shows what the frame shows, in the frame's shape, and offers the controls used most: previous, play/pause, next and display on/off.

## ADDED Requirements

### Requirement: Card loads by itself
The integration SHALL serve the card and load it into Home Assistant's frontend by itself, without an entry under dashboard resources. After an update of the integration, the browser SHALL load the new card version after a reload of the page.

#### Scenario: Fresh install
- **WHEN** the integration is set up and the user edits a dashboard
- **THEN** "openframe" is offered in the card picker without adding a resource

#### Scenario: Integration updated
- **WHEN** the integration is updated to a new version and the user reloads the page
- **THEN** the dashboard uses the card of the new version

### Requirement: Choosing the frame
The card SHALL show one frame, chosen by its device. Its editor SHALL offer a device picker limited to openframe frames, an optional title (the device name by default) and whether to show the caption (on by default). The same options SHALL work in YAML.

#### Scenario: Card from the picker
- **WHEN** the user adds the card from the card picker in a Home Assistant with one frame
- **THEN** the card shows that frame without further input

#### Scenario: YAML
- **WHEN** the card is configured as `type: custom:openframe-card` with `device_id` of a frame and `show_caption: false`
- **THEN** it shows that frame without a caption

#### Scenario: Device of another integration
- **WHEN** `device_id` names a device that is not an openframe frame
- **THEN** the card shows an error naming the problem instead of the photo

### Requirement: Photo in the frame's shape
The card SHALL show the photo on screen as the frame shows it, in a box of the frame's aspect ratio in its current orientation, with black where the frame shows black borders. It SHALL show the new photo within 15 seconds of a photo change on the frame.

#### Scenario: Landscape frame
- **WHEN** the frame has a 1024x600 screen in landscape
- **THEN** the card's photo box has the aspect ratio 1024:600

#### Scenario: Portrait frame
- **WHEN** the same frame is set to portrait
- **THEN** the card's photo box has the aspect ratio 600:1024

### Requirement: States on the card
While the display is off, the card SHALL show the photo dimmed with a "Display off" badge. It SHALL show a "Paused" badge while the slideshow is paused, a "Safe mode" badge in safe mode, and an "Unavailable" state without controls while the frame does not answer.

#### Scenario: Display off at night
- **WHEN** the frame's display is off by the schedule
- **THEN** the card shows the last photo dimmed with "Display off"

#### Scenario: Frame unreachable
- **WHEN** the frame does not answer
- **THEN** the card shows "Unavailable", and its buttons are hidden

### Requirement: Controls on the card
The card SHALL offer previous, play/pause and next, and a display button that switches the display on and off. Previous and next SHALL be disabled while the display is off. The display button SHALL be hidden while the frame cannot switch its display.

#### Scenario: Pause on the card
- **WHEN** the user presses play/pause on the card while the slideshow plays
- **THEN** the slideshow pauses and the card shows "Paused"

#### Scenario: Display on from the card
- **WHEN** the display is off and the user presses the display button
- **THEN** the display goes on and the photo is no longer dimmed

#### Scenario: Next at night
- **WHEN** the display is off
- **THEN** previous and next are disabled

### Requirement: Caption on the card
With the caption switched on, the card SHALL show the name of the photo on screen below the photo, as the sensor of the photo on screen names it, and its album in a second line. A long text SHALL end with an ellipsis instead of growing the card.

#### Scenario: Photo with comment
- **WHEN** the frame shows a photo with the comment "Summer 2025" in the album `holiday/2025`
- **THEN** the card shows "Summer 2025" and below it "holiday/2025"

### Requirement: Languages and themes
The card's texts SHALL be English and German, following the user's Home Assistant language, English for any other language. The card SHALL use the theme's colours and SHALL be legible in light and dark themes.

#### Scenario: German user
- **WHEN** the user's Home Assistant language is German
- **THEN** the badge reads "Display aus" instead of "Display off"

### Requirement: Card on a phone
The card SHALL fit a phone screen 360 pixels wide without horizontal scrolling, with buttons at least 44 pixels in size, and SHALL work in the sections view and the masonry view.

#### Scenario: Phone
- **WHEN** the dashboard with the card is opened on a phone 360 pixels wide
- **THEN** the photo and all buttons are visible without horizontal scrolling and each button is at least 44 pixels in size
