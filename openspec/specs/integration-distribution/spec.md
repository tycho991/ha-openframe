# integration-distribution Specification

## Purpose

Delivers the openframe integration to Home Assistant users: installation through HACS, versioned releases, the supported Home Assistant version and a tested contract with the openframe API.

## Requirements

### Requirement: Installation through HACS
The integration SHALL be installable through HACS as a custom repository from `tycho991/ha-openframe`, and by copying `custom_components/openframe` into the configuration folder. After a restart of Home Assistant it SHALL be offered under "Add integration" as "openframe".

#### Scenario: Install with HACS
- **WHEN** the user adds `https://github.com/tycho991/ha-openframe` as a custom repository of the type integration in HACS and downloads it
- **THEN** after a restart "openframe" can be added under Settings › Devices & services

### Requirement: Releases
Every release SHALL be a GitHub release with a semantic version tag and release notes. The version in the integration's manifest SHALL equal the release version. HACS SHALL offer a new release as an update.

#### Scenario: New release
- **WHEN** a release 0.2.0 is published
- **THEN** HACS offers the update from 0.1.0 to 0.2.0, and the installed manifest shows version 0.2.0

### Requirement: Supported Home Assistant version
The integration SHALL state its minimum Home Assistant version for HACS and SHALL work with that version and with the latest stable one. HACS SHALL refuse the installation on an older Home Assistant.

#### Scenario: Too old Home Assistant
- **WHEN** a user with a Home Assistant older than the minimum tries to download the integration in HACS
- **THEN** HACS refuses it and names the minimum version

### Requirement: Contract with the openframe API
Every request and response of the integration SHALL match openframe's API contract of the pinned openframe release. A new openframe release SHALL be adopted only after the tests pass against its contract.

#### Scenario: Response outside the contract
- **WHEN** a test fixture of the fake frame contains a field the pinned contract does not have
- **THEN** the tests fail and name the fixture and the field

#### Scenario: New openframe release
- **WHEN** openframe publishes a release that renames a field the integration reads
- **THEN** the update of the pinned contract fails its tests and is not merged
