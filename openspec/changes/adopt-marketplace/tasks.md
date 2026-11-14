# Tasks

## 1. Repository

- [x] 1.1 `.github/workflows/release-please.yml`: the header comment says that the Marketplace (and HACS on Home Assistant 2026.10) offers a published release as an update and that neither sees drafts; `.github/workflows/validate.yml`: the header and the `hacs` job's comment say that the job checks `hacs.json` and the folder structure, which the Marketplace requires as well; verify: `git diff` touches only comments in both files, and the workflows' checks pass on the pull request
- [x] 1.2 `CLAUDE.md`: the rule on drafts gives the Marketplace and HACS as the reason; verify: `grep -n HACS CLAUDE.md` shows no statement that is only true for HACS
- [x] 1.3 `README.md`: check that installation, updating from 0.1.0 and the requirements match the delta spec (the Marketplace section came with #10); verify: every step of the scenario "Install from the Marketplace" appears in the README as written

## 2. Devices

- [x] 2.1 Rows in `../openframe-private/DEVICE_TEST.md` with their references: installing 0.2.0 from the Marketplace on the owner's Home Assistant over the copy by hand (`integration-distribution` › Installation through the Marketplace › Install from the Marketplace) and the next release appearing under Settings › Updates (› Releases › New release), with a note that the Marketplace checks custom repositories every 48 hours, so the row waits up to that long or uses a manual check; verify: the rows exist with their references
- [x] 2.2 Run the installation row with the owner, who installs it (the owner had already installed 0.2.0 from the Marketplace, so only the reading remained); read afterwards (read-only) that `custom_components/openframe/manifest.json` shows 0.2.0 and that the Marketplace keeps an update entity for it; verify: the result is entered in the row, and the update row stays open with a note until the next release

## 3. Integration

- [x] 3.1 `openspec validate adopt-marketplace`; verify: exit 0 without warnings

## Workflow follow-up

- When archiving, adjust the Purpose sentence of `openspec/specs/integration-distribution/spec.md` ("installation through HACS") to name the Marketplace, since the sync keeps an existing Purpose.
- Run the update row of 2.1 with the next release that changes the version.
