# Spec Delta

## RENAMED Requirements

- FROM: `### Requirement: Installation through HACS`
- TO: `### Requirement: Installation through the Marketplace`

## MODIFIED Requirements

### Requirement: Installation through the Marketplace
The integration SHALL be installable as a custom repository from `tycho991/ha-openframe` through the Marketplace of Home Assistant 2026.11 and later, through HACS on Home Assistant 2026.10, and by copying `custom_components/openframe` into the configuration folder. After a restart of Home Assistant it SHALL be offered under "Add integration" as "openframe".

#### Scenario: Install from the Marketplace
- **WHEN** the user adds `tycho991/ha-openframe` under Settings › Marketplace › Add from link as an integration and installs the latest version
- **THEN** after a restart "openframe" can be added under Settings › Devices & services, and the integration has an update entity

#### Scenario: Install with HACS
- **WHEN** the user of Home Assistant 2026.10 adds `https://github.com/tycho991/ha-openframe` as a custom repository of the type integration in HACS and downloads it
- **THEN** after a restart "openframe" can be added under Settings › Devices & services

### Requirement: Releases
Every release SHALL be a published GitHub release, not a draft, with a semantic version tag and release notes. The version in the integration's manifest SHALL equal the release version. The Marketplace, and HACS on Home Assistant 2026.10, SHALL offer a new release as an update.

#### Scenario: New release
- **WHEN** a release after the installed one is published
- **THEN** the Marketplace offers the update under Settings › Updates, and after installing it and a restart the installed manifest shows the new version

### Requirement: Supported Home Assistant version
The integration SHALL state its minimum Home Assistant version in `hacs.json`, which the Marketplace and HACS read, and SHALL work with that version and with the latest stable one. HACS SHALL refuse the installation on an older Home Assistant.

#### Scenario: Too old Home Assistant
- **WHEN** a user with a Home Assistant older than the minimum tries to download the integration in HACS
- **THEN** HACS refuses it and names the minimum version
