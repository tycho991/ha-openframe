"""Translations and the entity table of the README."""

from __future__ import annotations

import json
import re
from pathlib import Path

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.openframe.const import DOMAIN
from tests.conftest import tick
from tests.fake_frame import FRAME_ID, FakeFrame

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
