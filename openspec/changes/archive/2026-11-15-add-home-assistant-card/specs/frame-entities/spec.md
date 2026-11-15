## ADDED Requirements

### Requirement: Screen format of the frame
The image entity of the photo on screen SHALL carry the frame's screen width and height in pixels in the current orientation as attributes, swapped while the frame runs in portrait. They SHALL change within 15 seconds of a change of the orientation.

#### Scenario: Landscape
- **WHEN** a frame with a 1024x600 screen runs in landscape
- **THEN** the image entity has the attributes `screen_width` 1024 and `screen_height` 600

#### Scenario: Switched to portrait
- **WHEN** the orientation of that frame is set to portrait
- **THEN** within 15 seconds the attributes are `screen_width` 600 and `screen_height` 1024
