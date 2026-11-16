## ADDED Requirements

### Requirement: Crop editor on the card
A crop button on the photo SHALL open an editor for the photo on screen at that moment. The editor SHALL show the whole photo behind a fixed frame of the frame's aspect ratio; dragging SHALL move the focus point, pinching, the mouse wheel and the minus and plus buttons SHALL zoom within the range the frame allows for this photo.

#### Scenario: Open the editor
- **WHEN** the user presses the crop button while the frame shows a portrait photo on a landscape frame
- **THEN** the editor shows that photo with the part the frame shows inside the frame's shape

#### Scenario: Photo changes while editing
- **WHEN** the frame changes to another photo while the editor is open
- **THEN** the editor keeps editing the photo it was opened for

#### Scenario: Zoom limits
- **WHEN** the user zooms out as far as the editor allows
- **THEN** the whole photo is visible inside the frame's shape with black borders, and zooming out further changes nothing

### Requirement: Saving a section from the card
The editor SHALL save the section with "Save", remove it with "Automatic" and close without a change with "Cancel". What the editor shows SHALL be what the frame shows after saving, within the rounding of one screen pixel.

#### Scenario: Save
- **WHEN** the user moves the focus point to the upper part and presses "Save"
- **THEN** the photo has the new section, and the frame shows the same part as the editor did when the photo appears next

#### Scenario: Automatic
- **WHEN** the user presses "Automatic" on a photo with a section
- **THEN** the photo has no section and the editor closes

### Requirement: Crop editor not offered
The crop button SHALL NOT be shown while no photo is on screen, while the frame is unavailable or in safe mode, or while the user is not an administrator of Home Assistant.

#### Scenario: Non-admin user
- **WHEN** a Home Assistant user without administrator rights opens the dashboard
- **THEN** the card shows the photo and controls but no crop button

### Requirement: Hiding the photo on screen from the card
A hide button on the card SHALL hide the photo on screen after a confirmation in the card, and the card SHALL say that the photo will not appear again. It SHALL follow the same visibility rules as the crop button.

#### Scenario: Hide from the card
- **WHEN** the user presses the hide button and confirms
- **THEN** the photo on screen is hidden and the card shows "Photo hidden"

#### Scenario: Cancel
- **WHEN** the user presses the hide button and cancels
- **THEN** nothing changes
