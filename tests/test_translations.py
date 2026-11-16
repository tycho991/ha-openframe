"""Translations, and the entity table and the examples of the README."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml
from freezegun.api import FrozenDateTimeFactory
from homeassistant.components.automation.config import async_validate_config_item
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.check_config import async_check_ha_config_file
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.openframe import PLATFORMS
from custom_components.openframe.const import DOMAIN
from tests.conftest import mock_entry, tick
from tests.fake_frame import FRAME_ID, FakeFrame

# The placeholder device ID of the README's examples
EXAMPLE_DEVICE_ID = "0123456789abcdef0123456789abcdef"
JPEG = b"\xff\xd8\xff\xe0 a snapshot"

ROOT = Path(__file__).parent.parent
TRANSLATIONS = ROOT / "custom_components" / "openframe" / "translations"


def keys(tree: dict, prefix: str = "") -> set[str]:
    found: set[str] = set()
    for key, value in tree.items():
        path = f"{prefix}.{key}" if prefix else key
        found |= keys(value, path) if isinstance(value, dict) else {path}
    return found


def placeholders(tree: dict) -> dict[str, set[str]]:
    flat: dict[str, set[str]] = {}

    def walk(node: dict, prefix: str) -> None:
        for key, value in node.items():
            path = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                walk(value, path)
            else:
                flat[path] = set(re.findall(r"\{(\w+)\}", value))

    walk(tree, "")
    return flat


def test_both_translations_have_the_same_keys_and_placeholders() -> None:
    en = json.loads((TRANSLATIONS / "en.json").read_text())
    de = json.loads((TRANSLATIONS / "de.json").read_text())
    assert keys(en) == keys(de)
    assert placeholders(en) == placeholders(de)


async def test_readme_lists_every_entity_key(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    frame.add_photo("holiday/1.jpg")
    frame.add_source("nc1", "Shared photos")
    await tick(hass, freezer, 60)
    table = (ROOT / "README.md").read_text().split("## Entities")[1].split("\n## ")[0]
    listed = set(re.findall(r"`([a-z_<>]+)`", table))
    entries = er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
    assert entries
    for registry_entry in entries:
        key = registry_entry.unique_id.removeprefix(f"{FRAME_ID}_")
        key = re.sub(r"^album_.*", "album_<name>", key)
        key = re.sub(r"^(sync|last_sync|sync_problem)_nc1$", r"\1_<source>", key)
        assert key in listed, f"{registry_entry.domain} {key} is missing in the README"
    assert {e.platform for e in entries} == {DOMAIN}


async def test_readme_examples_use_existing_entities_and_actions(
    hass: HomeAssistant, frame: FakeFrame, freezer: FrozenDateTimeFactory
) -> None:
    frame.info["name"] = "Photo frame"
    config_entry = mock_entry(frame)
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    readme = (ROOT / "README.md").read_text()
    entities = readme.split("## Entities")[1].split("\n## ")[0]
    examples = readme.split("## Automation examples")[1].split("\n## ")[0]
    # The section on updating from 0.1.0 names the removed switch on purpose
    for found in set(re.findall(r"\b([a-z_]+\.photo_frame_[a-z_]+)", entities + examples)):
        assert hass.states.get(found) is not None, f"{found} does not exist"
    for domain, service in set(re.findall(r"- action: ([a-z_]+)\.([a-z_]+)", examples)):
        # Actions of other integrations (a camera's snapshot) are only checked by the config check
        if domain in {DOMAIN, *PLATFORMS}:
            assert hass.services.has_service(domain, service), f"{domain}.{service} does not exist"


def yaml_blocks(section: str) -> list[str]:
    text = (ROOT / "README.md").read_text().split(f"\n## {section}\n")[1].split("\n## ")[0]
    return re.findall(r"```yaml\n(.*?)```", text, re.DOTALL)


@pytest.mark.parametrize("example", yaml_blocks("Automation examples"))
async def test_readme_example_passes_the_config_check(
    hass: HomeAssistant, tmp_path: Path, example: str
) -> None:
    """Each automation example of the README passes Home Assistant's config check, and each of
    its automations the automation editor's stricter check."""
    (tmp_path / "configuration.yaml").write_text(example)
    hass.config.config_dir = str(tmp_path)
    result = await async_check_ha_config_file(hass)
    assert not result.errors, result.errors
    # The config check only logs an invalid automation and keeps it; the editor's check raises
    automations = yaml.safe_load(example)["automation"]
    assert automations
    for number, automation in enumerate(automations):
        await async_validate_config_item(hass, str(number), automation)


async def test_readme_photo_examples_run(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry, tmp_path: Path
) -> None:
    """The photo action examples of the README do what they say against the fake frame."""
    media = tmp_path / "media"
    (media / "snapshots").mkdir(parents=True)
    hass.config.allowlist_external_dirs = {str(media.resolve())}
    device = dr.async_get(hass).async_get_device_by_identifier((DOMAIN, FRAME_ID), entry.entry_id)
    assert device is not None
    automations = []
    for example in yaml_blocks("Automation examples"):
        if "openframe." in example:
            text = example.replace(EXAMPLE_DEVICE_ID, device.id).replace("/media/", f"{media}/")
            automations += yaml.safe_load(text)["automation"]
    assert len(automations) == 2

    async def snapshot(call: ServiceCall) -> None:
        await hass.async_add_executor_job(Path(call.data["filename"]).write_bytes, JPEG)

    hass.services.async_register("camera", "snapshot", snapshot)
    hass.states.async_set("binary_sensor.doorbell", "off")
    assert await async_setup_component(hass, "automation", {"automation": automations})
    photo = frame.add_photo("a/1.jpg")

    hass.bus.async_fire("zha_event", {"command": "double"})
    await hass.async_block_till_done()
    assert photo.hidden is True

    hass.states.async_set("binary_sensor.doorbell", "on")
    await hass.async_block_till_done()
    [visitor] = [p for p in frame.photos if p.album == "visitors"]
    assert re.fullmatch(r"visitors/door_\d{8}_\d{6}\.jpg", visitor.path)
