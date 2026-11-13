# Spec Delta

## MODIFIED Requirements

### Requirement: Minimum frame version
The integration SHALL refuse a frame that lacks an endpoint or a field it needs, as an openframe before 0.6.0 lacks the brightness, during setup with a message that names the minimum openframe version 0.6.0, and SHALL NOT create the frame. A frame already added that lacks such an endpoint or field SHALL get a repair issue naming the minimum version, which goes away once the frame answers again.

#### Scenario: Frame before the slideshow API
- **WHEN** the user pairs a frame whose app answers 404 for the slideshow endpoint
- **THEN** the flow ends with "frame outdated" naming the minimum openframe version, and no frame is added

#### Scenario: Frame before the brightness
- **WHEN** the user pairs a frame on openframe 0.5.0, whose display state has no brightness
- **THEN** the flow ends with "frame outdated" naming openframe 0.6.0, the pairing is revoked on the frame, and no frame is added

#### Scenario: Frame downgraded after setup
- **WHEN** an older openframe without the slideshow API or the brightness is installed on a frame that is already added
- **THEN** its entities become unavailable and Home Assistant shows a repair issue naming the minimum openframe version, until the frame runs a newer openframe again
