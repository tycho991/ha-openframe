# Spec Delta

## RENAMED Requirements

- FROM: `### Requirement: Display switch`
- TO: `### Requirement: Display light`

## MODIFIED Requirements

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

### Requirement: Errors of commands
A command the frame refuses or does not answer SHALL fail in Home Assistant with a translated message, and the entity SHALL keep the state the frame reports.

#### Scenario: Frame unreachable
- **WHEN** the user switches the display while the frame does not answer
- **THEN** Home Assistant shows "The frame does not answer" and the light keeps its previous state

## ADDED Requirements

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
