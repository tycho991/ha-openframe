## MODIFIED Requirements

### Requirement: App update entity
An update entity titled "openframe app" SHALL show the installed and the latest app version with the release notes as plain text, and SHALL show progress while the frame downloads or installs. Installing SHALL open the installation dialog on the frame, which someone confirms there; the release notes SHALL start with a sentence that says so. While the frame may not install apps or runs an unofficial build, installing SHALL NOT be offered.

#### Scenario: Update ready
- **WHEN** the frame has downloaded a newer version
- **THEN** the update entity shows it with its release notes and offers to install it

#### Scenario: Install from Home Assistant
- **WHEN** the user installs the update in Home Assistant
- **THEN** the frame wakes its display and shows Android's installation dialog

#### Scenario: Installing not allowed
- **WHEN** the frame reports that it may not install apps
- **THEN** the update entity shows the new version without the install action

#### Scenario: Confirmation on the frame
- **WHEN** the user opens the update in Home Assistant, whose language is German
- **THEN** the release notes start with the German sentence that installing opens a dialog on the frame's screen, to be confirmed there within 10 minutes, followed by the frame's notes

#### Scenario: Two updates named openframe
- **WHEN** a frame offers a new app version and the integration's own update is waiting as well
- **THEN** Settings › Updates lists the frame's update as "openframe app" with its version under the frame's name, and the integration's update as "openframe"

## ADDED Requirements

### Requirement: Refused installation
When the frame refuses an install request with `install_cooldown`, the error message SHALL name the cause from the frame's last update error (dialog not confirmed within 10 minutes, cancelled on the frame, or one of the two if the frame names neither), SHALL say that Home Assistant can ask again 30 minutes later, and SHALL name "Install update" in the frame menu as the way to install at once.

#### Scenario: Dialog not confirmed
- **WHEN** nobody confirmed the dialog of a request from Home Assistant, and the user installs again 5 minutes after the frame discarded it
- **THEN** Home Assistant shows that nobody confirmed the dialog within 10 minutes, that it can ask again 30 minutes after that, and that the frame menu installs at once, and no dialog appears on the frame

#### Scenario: Dialog cancelled
- **WHEN** someone cancelled the dialog on the frame, and the user installs again from Home Assistant
- **THEN** Home Assistant shows that the installation was cancelled on the frame, with the 30 minutes and the frame menu

#### Scenario: Cause not reported
- **WHEN** the frame refuses with `install_cooldown` and its update state names no error
- **THEN** Home Assistant shows that the last dialog was cancelled or not confirmed, with the 30 minutes and the frame menu
