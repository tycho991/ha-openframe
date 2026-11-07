# Spec Delta

## Purpose

Shows the photos of openframe frames in Home Assistant's media browser, by frame and album, served through Home Assistant so that only signed-in users can see them.

## ADDED Requirements

### Requirement: Frames and albums as folders
The media browser SHALL have an entry "openframe" with one folder per frame. A frame's folder SHALL list its top-level albums and a folder "All photos"; an album's folder SHALL list its sub-albums and the photos directly in it. Hidden photos and albums SHALL be listed and marked as hidden.

#### Scenario: Nested albums
- **WHEN** the user opens the frame's folder and then `holiday`
- **THEN** the folder `holiday` lists the sub-album `2024` and the photos that lie directly in `holiday`

#### Scenario: Hidden photo
- **WHEN** an album contains a hidden photo
- **THEN** the media browser lists it with "(hidden)" after its title

### Requirement: Photos in a folder
Photos SHALL be listed newest first with a thumbnail and titled by their comment, or by their file name without one. A folder SHALL list at most 500 photos; a folder with more SHALL say in its title how many of how many it shows.

#### Scenario: Large album
- **WHEN** an album has 1,200 photos directly in it
- **THEN** its folder lists the 500 newest and its title says "500 of 1200"

### Requirement: Opening a photo
Opening a photo in the media browser SHALL show it uncropped in the frame's full size (longest edge at most 2048 pixels).

#### Scenario: Open
- **WHEN** the user clicks a photo in the media browser
- **THEN** Home Assistant shows the whole photo, not the part the frame shows

### Requirement: Photos only for signed-in users
Photo images SHALL reach the browser only through Home Assistant, for signed-in users or through a signed link that Home Assistant issued and that expires. The frame's address and token SHALL NOT reach the browser.

#### Scenario: Without signing in
- **WHEN** a request for a photo image reaches Home Assistant without a session and without a valid signature
- **THEN** Home Assistant answers with 401 and does not ask the frame

#### Scenario: Image source in the browser
- **WHEN** the user opens a photo in the media browser
- **THEN** the image's address points to Home Assistant, not to the frame
