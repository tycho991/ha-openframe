# frame-connection Specification

## Purpose

Connects Home Assistant to openframe frames on the local network: pairing a frame, keeping its token valid, following a changed address, and reading its state reliably without straining weak frames.

## Requirements

### Requirement: Adding a frame by its address
The user SHALL add a frame with its host name or IP address and port (default 8080). The integration SHALL read the frame's info without a token and SHALL refuse an address where no openframe frame with API version 1 answers. The frame's durable ID SHALL identify it; adding a frame that is already set up SHALL be aborted.

#### Scenario: Frame found
- **WHEN** the user enters `192.168.100.215` and port 8080 and an openframe frame answers there
- **THEN** the integration continues with the pairing step and names the frame by its name from the info

#### Scenario: Nothing answers
- **WHEN** the user enters an address where nothing answers within 10 seconds
- **THEN** the form shows "cannot connect" and stays open with the entered values

#### Scenario: Same frame again
- **WHEN** the user adds a frame whose ID belongs to a frame that is already set up, under another address
- **THEN** the flow is aborted with "already configured"

### Requirement: Pairing with the code on the frame
After the address step the integration SHALL ask the frame to show a pairing code and SHALL ask the user for the six-digit code. With a correct code it SHALL store the token and the client ID it receives and SHALL create the frame. It SHALL send the device name "Home Assistant".

#### Scenario: Correct code
- **WHEN** the user types the code the frame shows
- **THEN** the frame is added, and the frame's list of paired devices shows "Home Assistant"

#### Scenario: Wrong code
- **WHEN** the user types a wrong code
- **THEN** the form shows "wrong code" and the user can try again

#### Scenario: Expired code
- **WHEN** the user types a code that has expired
- **THEN** the form shows "code expired", and the frame shows a new code

#### Scenario: Locked after wrong codes
- **WHEN** the frame answers that pairing by code is locked
- **THEN** the form says to wait a minute and try again

### Requirement: Minimum frame version
The integration SHALL refuse a frame that lacks an endpoint it needs, during setup with a message that names the minimum openframe version, and SHALL NOT create the frame. A frame already added that lacks such an endpoint SHALL get a repair issue naming the minimum version, which goes away once the frame answers again.

#### Scenario: Frame before the slideshow API
- **WHEN** the user pairs a frame whose app answers 404 for the slideshow endpoint
- **THEN** the flow ends with "frame outdated" naming the minimum openframe version, and no frame is added

#### Scenario: Frame downgraded after setup
- **WHEN** an older openframe without the slideshow API is installed on a frame that is already added
- **THEN** its entities become unavailable and Home Assistant shows a repair issue naming the minimum openframe version, until the frame runs a newer openframe again

### Requirement: Re-authentication after a revoked pairing
When the frame answers 401 to the stored token, the integration SHALL stop polling the frame and SHALL start Home Assistant's re-authentication, which pairs again with a code shown on the frame and replaces the stored token.

#### Scenario: Pairing revoked in the web UI
- **WHEN** the user revokes the pairing "Home Assistant" in the frame's web UI
- **THEN** Home Assistant shows a re-authentication for the frame within one polling interval, and after pairing again the entities work without being created anew

#### Scenario: Re-authentication with another frame
- **WHEN** the address of the frame now leads to a frame with another ID during re-authentication
- **THEN** the flow is aborted with "wrong frame" and the stored token is unchanged

### Requirement: Changed address
The user SHALL be able to enter a new address for a frame without pairing again. The integration SHALL accept the new address only if the frame there has the same ID, and SHALL keep the token.

#### Scenario: New IP address
- **WHEN** the frame got a new IP address and the user enters it in the reconfiguration
- **THEN** the integration uses the new address with the old token, and the entities stay the same

#### Scenario: Another frame at the new address
- **WHEN** the user enters an address where a frame with another ID answers
- **THEN** the form shows "wrong frame" and the old address stays

### Requirement: Removing a frame
When the user removes a frame from Home Assistant, the integration SHALL revoke its own pairing on the frame. If the frame does not answer, the removal SHALL go ahead anyway.

#### Scenario: Removal
- **WHEN** the user deletes the frame in Home Assistant while the frame is reachable
- **THEN** "Home Assistant" disappears from the frame's list of paired devices

#### Scenario: Removal of an unreachable frame
- **WHEN** the user deletes a frame that is switched off
- **THEN** the frame is removed from Home Assistant without an error

### Requirement: Polling the frame
The integration SHALL read the display and slideshow state every 15 seconds. It SHALL read settings, albums and photo counts again only when the frame's library, settings or app version changed, and in any case every 10 minutes. Sources and update state SHALL be read every minute and every 15 seconds while a sync or download runs.

#### Scenario: Photo change on the frame
- **WHEN** the frame shows a new photo
- **THEN** the photo entities show it within 15 seconds

#### Scenario: Nothing changed
- **WHEN** neither library, settings nor app version change for five minutes
- **THEN** the integration does not read the settings, albums or photo counts in that time

#### Scenario: Setting changed in the web UI
- **WHEN** the user changes the interval in the frame's web UI
- **THEN** the interval entity shows the new value within 15 seconds

### Requirement: Fresh state after a command
After a command from Home Assistant succeeds, the affected entities SHALL show the new state at once, without waiting for the next polling interval.

#### Scenario: Next photo
- **WHEN** the user presses "Next photo"
- **THEN** the photo entities show the new photo as soon as the frame has answered

### Requirement: Availability
When the frame does not answer, its entities SHALL become unavailable after the first failed poll and available again after the next successful one. An unreachable frame SHALL be logged once when it goes away and once when it comes back.

#### Scenario: Frame switched off
- **WHEN** the frame loses power
- **THEN** its entities are unavailable within 15 seconds, and the log has one entry for it

#### Scenario: Frame back
- **WHEN** the frame answers again
- **THEN** its entities are available within 15 seconds with the frame's current state

### Requirement: Token kept private
The token SHALL NOT appear in logs, error messages or the diagnostics download.

#### Scenario: Diagnostics
- **WHEN** the user downloads the diagnostics of a frame
- **THEN** the file contains the frame's info and state but the token is redacted
