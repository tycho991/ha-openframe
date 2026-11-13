# frame-entities Specification

## Purpose

Represents each openframe frame in Home Assistant as one device whose entities show and control the display, the slideshow, the photo on screen, the settings used in automations, the library and the frame's health.

## Requirements

### Requirement: One device per frame
Each frame SHALL be one device named after the frame, with the app version as software version, the Android version as hardware version and a link to the frame's web UI. A new app version SHALL show on the device after the frame updated itself. Entity names SHALL be translated into English and German.

#### Scenario: Device page
- **WHEN** the user opens the device page of a frame on openframe 0.5.0 with Android 6.0.1
- **THEN** it shows the frame's name, software version 0.5.0, hardware "Android 6.0.1" and a link to `http://<address>:<port>/`

#### Scenario: Frame updated itself
- **WHEN** the frame installs a new app version
- **THEN** the device shows the new version within one minute

### Requirement: Display light
A light SHALL show whether the display is on and SHALL switch it on and off, with the reason (`schedule`, `manual`, `wake`, `none`), the next change by itself, whether the schedule dims at the moment and whether Android's automatic brightness is on as attributes. The light SHALL be unavailable while the frame can neither switch its display nor set its brightness.

#### Scenario: Display off from an automation
- **WHEN** an automation turns the display light off
- **THEN** the frame's display goes off and the light shows off with the reason `manual`

#### Scenario: No device administrator
- **WHEN** the frame reports that it cannot switch the display, but may set the brightness
- **THEN** the light is available, shows the display's state, and turning it off fails with the message that openframe is not a device administrator

#### Scenario: Nothing to control
- **WHEN** the frame reports that it can neither switch the display nor set the brightness
- **THEN** the display light is unavailable

### Requirement: Slideshow controls
A switch SHALL show whether the slideshow plays (on) or is paused (off) and SHALL pause and resume it. Buttons SHALL switch to the next and previous photo. Pressing one while the display is off SHALL fail with a message that the display is off.

#### Scenario: Pause from Home Assistant
- **WHEN** the user turns the slideshow switch off
- **THEN** the frame keeps the current photo until the switch is turned on again

#### Scenario: Previous photo
- **WHEN** the user presses "Previous photo"
- **THEN** the frame shows the previous photo

#### Scenario: Next photo at night
- **WHEN** the user presses "Next photo" while the display is off
- **THEN** Home Assistant shows the error "The display is off" and the photo is unchanged

### Requirement: Photo on screen
An image entity SHALL show the photo on screen as the frame shows it, and SHALL change when the photo or its section changes. A sensor SHALL name the photo on screen by its comment, or by its file name without one, with album, capture date, place and photo ID as attributes. Without a photo on screen both SHALL have no value.

#### Scenario: New photo
- **WHEN** the frame changes to a photo with the comment "Summer 2025"
- **THEN** the image entity shows that photo and the sensor shows "Summer 2025"

#### Scenario: Photo without comment
- **WHEN** the frame shows `holiday/IMG_0042.jpg` without a comment
- **THEN** the sensor shows "IMG_0042.jpg" and its album attribute is `holiday`

#### Scenario: Empty library
- **WHEN** the frame has no visible photos
- **THEN** the image entity shows no image and the sensor is unknown

### Requirement: Settings as configuration entities
The interval, order, transition, transition duration, fill mode, orientation, clock on/off, display schedule on/off and automatic update check SHALL be configuration entities with the frame's ranges and choices. A change SHALL be sent to the frame and SHALL change nothing else. The display schedule switch SHALL be unavailable while the display cannot be switched.

#### Scenario: Interval from an automation
- **WHEN** an automation sets the interval to 60 seconds
- **THEN** the frame changes photos every 60 seconds and its other settings are unchanged

#### Scenario: Value out of range
- **WHEN** the user tries to set the interval to 2 seconds
- **THEN** Home Assistant refuses the value, because the frame's minimum is 5 seconds

#### Scenario: Fill mode
- **WHEN** the user selects the fill mode `fit`
- **THEN** the frame shows photos without a section fully visible from the next change on

### Requirement: Photo counts
Sensors SHALL show the number of photos, of visible photos and of hidden photos, and the number of albums.

#### Scenario: Photo hidden in the web UI
- **WHEN** the user hides one of 120 visible photos in the web UI
- **THEN** within 15 seconds the visible photos show 119 and the hidden photos one more

### Requirement: One switch per album
Each album SHALL have a switch that is on while the album is shown and off while it is hidden, with its photo count as attribute. New albums SHALL get a switch without reloading, the switch of a removed album SHALL become unavailable. Switches of sub-albums SHALL be disabled by default.

#### Scenario: Hide an album
- **WHEN** the user turns the switch of the album `holiday` off
- **THEN** the frame no longer shows photos of `holiday` and its sub-albums from the next change on

#### Scenario: New album
- **WHEN** a folder `2026` is added to the frame
- **THEN** a switch for `2026` appears within 15 seconds, without a reload of the integration

#### Scenario: Sub-album
- **WHEN** the frame has the album `holiday/2024`
- **THEN** its switch exists but is disabled until the user enables it

### Requirement: Remote sources
Each remote source of the frame SHALL have a button that starts a sync, a timestamp sensor of the last sync with the numbers of added, updated and removed photos as attributes, and a problem sensor that is on while the last sync failed, with the error as attribute. These entities SHALL be named after the source and SHALL follow a renamed source without changing their entity IDs.

#### Scenario: Sync from Home Assistant
- **WHEN** the user presses the sync button of a source
- **THEN** the frame syncs that source, and the last sync sensor shows the new time when it is done

#### Scenario: Failed sync
- **WHEN** the last sync of a source failed because the server was unreachable
- **THEN** its problem sensor is on and names the error

#### Scenario: Source renamed
- **WHEN** the user renames a source in the frame's web UI
- **THEN** its three entities carry the new name within a minute and keep their entity IDs

### Requirement: App update entity
An update entity SHALL show the installed and the latest app version with the release notes as plain text, and SHALL show progress while the frame downloads or installs. Installing SHALL open the installation dialog on the frame, which someone confirms there. While the frame may not install apps or runs an unofficial build, installing SHALL NOT be offered.

#### Scenario: Update ready
- **WHEN** the frame has downloaded a newer version
- **THEN** the update entity shows it with its release notes and offers to install it

#### Scenario: Install from Home Assistant
- **WHEN** the user installs the update in Home Assistant
- **THEN** the frame wakes its display and shows Android's installation dialog

#### Scenario: Installing not allowed
- **WHEN** the frame reports that it may not install apps
- **THEN** the update entity shows the new version without the install action

### Requirement: Checking for an update
A button SHALL ask the frame to check for an update now, also while automatic checks are off.

#### Scenario: Check now
- **WHEN** the user presses "Check for update"
- **THEN** the frame checks GitHub for a new version and the update entity shows the result

### Requirement: Health of the frame
A problem sensor SHALL be on while the frame runs in safe mode, and a button SHALL start the frame normally again, available only in safe mode. A diagnostic sensor SHALL be on while the frame changes photos instantly because its display could not keep up with the transition.

#### Scenario: Safe mode
- **WHEN** the frame started in safe mode after repeated crashes
- **THEN** the safe mode sensor is on, the slideshow entities are unavailable and the button "Leave safe mode" is available

#### Scenario: Leave safe mode
- **WHEN** the user presses "Leave safe mode"
- **THEN** the frame starts normally, and the safe mode sensor is off after it is back

### Requirement: Errors of commands
A command the frame refuses or does not answer SHALL fail in Home Assistant with a translated message, and the entity SHALL keep the state the frame reports.

#### Scenario: Frame unreachable
- **WHEN** the user switches the display while the frame does not answer
- **THEN** Home Assistant shows "The frame does not answer" and the light keeps its previous state

### Requirement: Brightness of the display light
While the display is on, the light SHALL show the brightness the frame reports. Turning the light on with a brightness SHALL set the display to it at once, as openframe does for `PUT /display`: outside a dim period it becomes the frame's fixed level, during one it holds until the period ends. A display that is on SHALL NOT be switched by it. While the frame may not modify system settings, the light SHALL only switch on and off.

#### Scenario: Dim from an automation
- **WHEN** an automation turns the display light on with a brightness of 50 % at noon
- **THEN** the display is at 50 % at once, the light shows 50 %, and the brightness mode shows the fixed level

#### Scenario: Dimmed by the schedule
- **WHEN** the schedule dims the display to 20 % in the evening
- **THEN** the light shows 20 % and its attribute for dimming is on

#### Scenario: Woken display dimmed
- **WHEN** someone woke the display at night and an automation sets the light to 30 %
- **THEN** the display is at 30 % and still goes off when the wake ends

#### Scenario: Without permission
- **WHEN** the frame may not modify system settings
- **THEN** the light offers only on and off, and switching the display still works

### Requirement: Former display switch
When the integration loads a frame that was added with an earlier version, it SHALL remove that version's display switch once, so that the display has only the light, also while the frame does not answer or is outdated.

#### Scenario: Update from a version with the switch
- **WHEN** the user updates the integration on a Home Assistant that had `switch.photo_frame_display` and restarts
- **THEN** `switch.photo_frame_display` is gone and `light.photo_frame_display` shows and switches the display

### Requirement: Brightness settings as configuration entities
A select SHALL set the brightness mode (Android's setting, a fixed level, automatic) and a number SHALL set the schedule's dim level from 1 to 100 %. Automatic SHALL be offered only on a frame with a light sensor. A change SHALL be sent to the frame and SHALL change nothing else; a mode the frame refuses SHALL fail with the frame's reason.

#### Scenario: Automatic from an automation
- **WHEN** an automation selects the mode automatic on a frame with a light sensor
- **THEN** Android's automatic brightness is on and the light's attribute for it is on

#### Scenario: No light sensor
- **WHEN** the user opens the brightness mode of a frame without a light sensor
- **THEN** automatic is not offered

#### Scenario: Fixed level without permission
- **WHEN** the frame may not modify system settings and the user selects the fixed level
- **THEN** Home Assistant shows the frame's reason and the mode stays Android's setting

#### Scenario: Dim level
- **WHEN** the user sets the dim level to 25 %
- **THEN** the frame dims to 25 % from the next dim time, and its other settings are unchanged
