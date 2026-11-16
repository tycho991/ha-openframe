# Spec Delta

## Purpose

Lets users and automations change a frame's photos and albums from Home Assistant: hide, comment, crop, delete and upload photos, and hide albums.

## ADDED Requirements

### Requirement: Target of a photo action
Every photo and album action SHALL target openframe frames as devices. An action with a photo ID SHALL target exactly one frame and SHALL fail if the photo does not exist on it. An action without a photo ID SHALL act on the photo on screen of each targeted frame.

#### Scenario: Two frames with a photo ID
- **WHEN** an automation calls `openframe.set_photo_hidden` with a photo ID and two frames as target
- **THEN** the action fails with a message that a photo ID needs exactly one frame, and no photo changes

#### Scenario: Unknown photo
- **WHEN** the action names a photo ID the frame does not have
- **THEN** the action fails with "photo not found"

### Requirement: Photo on screen by default
Without a photo ID, a photo action SHALL act on the photo the frame shows at the moment the action runs. If a targeted frame shows no photo, the action SHALL fail for that frame with a message saying so.

#### Scenario: Hide the photo on the wall
- **WHEN** an automation calls `openframe.set_photo_hidden` with `hidden: true` and a frame as target, without a photo ID
- **THEN** the photo on screen of that frame is hidden and does not appear again in the slideshow

#### Scenario: Frame without photos
- **WHEN** the action runs without a photo ID on a frame with an empty library
- **THEN** the action fails with "the frame shows no photo"

### Requirement: Hiding and showing a photo
`openframe.set_photo_hidden` SHALL hide a photo with `hidden: true` and show it again with `hidden: false`.

#### Scenario: Show again
- **WHEN** `openframe.set_photo_hidden` runs with a hidden photo's ID and `hidden: false`
- **THEN** the photo is visible again, unless its album is hidden

### Requirement: Comment of a photo
`openframe.set_photo_comment` SHALL set the comment of a photo; an empty comment SHALL remove it. A comment longer than the frame allows SHALL fail with the frame's message.

#### Scenario: New comment
- **WHEN** the action sets the comment "Summer 2025" on the photo on screen
- **THEN** the frame's caption shows "Summer 2025" within 5 seconds

#### Scenario: Remove the comment
- **WHEN** the action sets an empty comment
- **THEN** the photo has no comment

### Requirement: Section of a photo
`openframe.set_photo_crop` SHALL set a photo's section as focus point `x`, `y` (fractions 0 to 1) and `zoom` (above 0, at most 4), and SHALL remove it with `reset: true`. Values out of range SHALL be refused before the frame is asked.

#### Scenario: Focus on the upper part
- **WHEN** the action sets `x` 0.5, `y` 0.2 and `zoom` 1 on a portrait photo of a landscape frame
- **THEN** the frame shows the upper part of the photo from its next appearance on

#### Scenario: Reset
- **WHEN** the action runs with `reset: true`
- **THEN** the photo has no section and the fill mode applies to it again

#### Scenario: Zoom out of range
- **WHEN** the action is called with `zoom` 5
- **THEN** Home Assistant refuses it naming `zoom`, and the frame is not asked

### Requirement: Deleting a photo
`openframe.delete_photo` SHALL delete a photo of the frame's local folder. A photo of a remote source SHALL NOT be deleted; the action SHALL fail with a message that it can only be hidden.

#### Scenario: Local photo
- **WHEN** the action deletes a photo that was uploaded to the frame
- **THEN** the photo is gone from the frame's library

#### Scenario: Photo of a Nextcloud share
- **WHEN** the action names a photo of a remote source
- **THEN** the action fails with "photos of a remote source can only be hidden" and the photo stays

### Requirement: Uploading photos
`openframe.upload_photo` SHALL upload one or more files from folders Home Assistant allows (`allowlist_external_dirs`) to one frame, optionally into an album, and SHALL return the IDs and paths of the new photos. A file outside the allowed folders SHALL be refused before anything is sent.

#### Scenario: Camera snapshot to the frame
- **WHEN** an automation uploads `/media/snapshots/door.jpg` into the album `visitors`
- **THEN** the photo is in the frame's album `visitors`, and the response contains its ID

#### Scenario: Folder not allowed
- **WHEN** the action names `/config/secrets.yaml`
- **THEN** the action fails with "path not allowed" and nothing is sent to the frame

#### Scenario: Unsupported file
- **WHEN** the action uploads a text file
- **THEN** the action fails with the frame's message about the unsupported format, and nothing is stored

### Requirement: Hiding an album
`openframe.set_album_hidden` SHALL hide or show an album by its path, also a sub-album whose switch is disabled.

#### Scenario: Hide a sub-album
- **WHEN** the action hides `holiday/2024`
- **THEN** the frame shows no photo of `holiday/2024` from the next change on, and the other albums of `holiday` stay visible

### Requirement: Photo actions for administrators
Photo and album actions SHALL be allowed for Home Assistant administrators and for automations and scripts, and SHALL be refused for a signed-in user without administrator rights.

#### Scenario: Non-admin user
- **WHEN** a user without administrator rights calls `openframe.delete_photo` from the developer tools
- **THEN** the action is refused as unauthorized and the photo stays

#### Scenario: Automation
- **WHEN** an automation calls `openframe.set_photo_hidden`
- **THEN** the action runs

### Requirement: Responses of photo actions
Actions that change a photo SHALL return the photo's updated record (ID, album, path, hidden, comment, section) when the caller asks for a response.

#### Scenario: Response in a script
- **WHEN** a script calls `openframe.set_photo_comment` with `response_variable`
- **THEN** the variable contains the photo's ID and its new comment

### Requirement: Fresh entities after a photo action
After a photo or album action, the photo counts, the album switches and the photo on screen SHALL show the change within one polling interval.

#### Scenario: Hidden by an action
- **WHEN** an action hides one of 120 visible photos
- **THEN** within 15 seconds the visible photos sensor shows 119
