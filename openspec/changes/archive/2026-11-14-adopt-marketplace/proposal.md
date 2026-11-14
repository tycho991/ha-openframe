# Proposal

## Why

Home Assistant 2026.11 replaced HACS with its built-in Marketplace: HACS refuses to start there, and custom repositories are added under Settings › Marketplace › Add from link. The spec `integration-distribution` still promises installation and updates through HACS, and the release workflow, the validate workflow and `CLAUDE.md` give HACS as the reason for their rules. The README already describes the Marketplace (#10); the rest of the repository should say the same.

## What Changes

- **Installation and updates through the Marketplace.** The spec names the Marketplace of Home Assistant 2026.11 and later as the way to install `tycho991/ha-openframe` and to receive new releases as updates, and keeps HACS for Home Assistant 2026.10, which stays the minimum version.
- **Comments and rules that name HACS.** The release workflow says that the Marketplace (and HACS on 2026.10) offers a release as an update and ignores drafts; the validate workflow says that the HACS check covers `hacs.json`, which the Marketplace reads as well; `CLAUDE.md` gives the same reason for releases that are not drafts.
- **Device check.** Installing 0.2.0 from the Marketplace on the owner's Home Assistant, and the next release appearing as an update there, are recorded as device rows.

### Out of scope

- Raising the minimum Home Assistant version to 2026.11 or dropping `hacs.json`: the Marketplace needs `hacs.json`, and Home Assistant 2026.10 users still install through HACS.
- Replacing the `hacs/action` check: no Marketplace-specific validator is documented, and the Marketplace requires what that check verifies.
- Any change to the integration's code.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `integration-distribution`: installation through the Marketplace (and HACS on 2026.10), updates offered by the Marketplace, the minimum Home Assistant version stated in `hacs.json` for both.

## Impact

- `.github/workflows/release-please.yml` and `.github/workflows/validate.yml`: comments only.
- `CLAUDE.md`: the rule on drafts.
- `openspec/specs/integration-distribution/spec.md` through the delta; its Purpose sentence is adjusted when the change is archived.
- `../openframe-private/DEVICE_TEST.md`: rows for the Marketplace.
- Users: none; the README already describes the Marketplace.
