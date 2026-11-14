# Design

## Context

Home Assistant 2026.11 ships the Marketplace integration and refuses HACS ("HACS does not work on Home Assistant 2026.11 and newer … replaced by the native Marketplace integration"). According to https://www.home-assistant.io/integrations/marketplace, a custom repository is added under Settings › Marketplace › Add from link and must be a public GitHub repository with a `hacs.json` and the folder structure of its type; installed repositories get an update entity, custom repositories are checked for new versions every 48 hours with a GitHub connection, only stable releases are offered by default, and a version whose minimum Home Assistant is too new is left out in favour of earlier ones. HACS content is migrated automatically; a copy by hand is not mentioned. ha-openframe has `hacs.json` with `homeassistant: 2026.10.0`, CI runs `hacs/action` and hassfest, and releases are published by release-please, not as drafts. The owner's Home Assistant runs 2026.11.0. See proposal.md for why.

## Goals / Non-Goals

**Goals:**
- The spec, the workflows' comments and `CLAUDE.md` describe the channel users actually have.

**Non-Goals:**
- Changing what the integration does, its minimum Home Assistant version, or its CI checks.

## Decisions

### 1. Marketplace first, HACS kept for 2026.10

The requirement names the Marketplace for 2026.11 and later and HACS for 2026.10. The minimum stays 2026.10, so dropping HACS would leave those users without a way to receive updates.

*Alternative:* raise the minimum to 2026.11 and drop HACS. Rejected: it gains nothing for the code, and the Marketplace reads the same `hacs.json`.

### 2. Keep `hacs/action` as the check of `hacs.json`

The Marketplace documents no validator of its own and requires exactly what `hacs/action` checks (a public repository, `hacs.json`, the integration's folder structure). The job stays; its comment says why.

### 3. The requirement on releases names "not a draft"

The rule "releases are not drafts" was justified by HACS ignoring drafts. Drafts are not visible to the Marketplace either (it reads published releases), so the rule moves into the requirement itself instead of depending on one tool.

## Risks / Trade-offs

- [The Marketplace's behaviour for custom repositories is new and only documented in prose] → The device rows check installation and the update offer on the owner's Home Assistant; the update row runs with the next release that changes the version.
- [Installing from the Marketplace over a copy by hand is not documented; it may refuse the existing folder or leave it without an update entity] → The device row runs exactly this on the owner's Home Assistant. If it fails, the owner makes a backup, removes the copy and installs from the Marketplace again; the config entry stays, since it lives in the configuration, not in `custom_components`. The README then gets that step.
- [The scenario "Install with HACS" can no longer be checked on the owner's Home Assistant 2026.11] → It stays covered by the `hacs/action` check and the earlier device run of 0.1.0.
