// The card's logic as pure functions of Home Assistant's `hass` object, testable with `node --test`.
// The view in openframe-card.js renders only what cardState() returns.

export const DOMAIN = "openframe";

// Each part of the card: the entity's domain, its translation key, and the end of the entity ID
// that the English entity name gives, for a frontend without `translation_key`
const PARTS = {
  image: ["image", "current_photo", "photo_on_screen"],
  caption: ["sensor", "current_photo", "photo_on_screen"],
  display: ["light", "display", "display"],
  slideshow: ["switch", "slideshow", "slideshow"],
  previous: ["button", "previous_photo", "previous_photo"],
  next: ["button", "next_photo", "next_photo"],
  safeMode: ["binary_sensor", "safe_mode", "safe_mode"],
};

// The aspect ratio until the image entity names the frame's screen
const DEFAULT_RATIO = "16 / 10";

const STRINGS = {
  en: {
    displayOff: "Display off",
    paused: "Paused",
    safeMode: "Safe mode",
    unavailable: "Unavailable",
    noPhoto: "No photo",
    previous: "Previous photo",
    next: "Next photo",
    pause: "Pause slideshow",
    resume: "Resume slideshow",
    switchOff: "Switch display off",
    switchOn: "Switch display on",
    chooseFrame: "Choose an openframe frame in the card's settings.",
    notFrame: "The chosen device is not an openframe frame.",
    frame: "Frame",
    title: "Title",
    showCaption: "Show caption",
    pickerDescription: "The photo on screen and the controls of a frame.",
  },
  de: {
    displayOff: "Display aus",
    paused: "Pausiert",
    safeMode: "Abgesicherter Modus",
    unavailable: "Nicht verfügbar",
    noPhoto: "Kein Foto",
    previous: "Vorheriges Foto",
    next: "Nächstes Foto",
    pause: "Diashow anhalten",
    resume: "Diashow fortsetzen",
    switchOff: "Display ausschalten",
    switchOn: "Display einschalten",
    chooseFrame: "Wähle in den Einstellungen der Karte einen openframe-Rahmen.",
    notFrame: "Das gewählte Gerät ist kein openframe-Rahmen.",
    frame: "Rahmen",
    title: "Titel",
    showCaption: "Bildunterschrift anzeigen",
    pickerDescription: "Das angezeigte Foto und die Bedienung eines Rahmens.",
  },
};

/** The card's texts in the user's language, English for any language but German. */
export function strings(language) {
  const base = String(language ?? "").toLowerCase().split(/[-_]/)[0];
  return STRINGS[base] ?? STRINGS.en;
}

/** The language of the user's Home Assistant. */
export function languageOf(hass) {
  return hass?.locale?.language ?? hass?.language ?? "en";
}

function ownEntities(hass, deviceId) {
  return Object.values(hass?.entities ?? {}).filter(
    (entry) => entry.device_id === deviceId && entry.platform === DOMAIN,
  );
}

/**
 * The entity IDs of a frame's parts, by the device; null if the device has no openframe entity.
 * A part the frame lacks, or whose entity is disabled, is undefined.
 */
export function findEntities(hass, deviceId) {
  const own = ownEntities(hass, deviceId);
  if (own.length === 0) {
    return null;
  }
  const found = {};
  for (const [part, [domain, key, suffix]] of Object.entries(PARTS)) {
    const inDomain = own.filter((entry) => entry.entity_id.startsWith(`${domain}.`));
    const entry =
      inDomain.find((e) => e.translation_key === key) ??
      inDomain.find((e) => e.translation_key == null && e.entity_id.endsWith(`_${suffix}`));
    found[part] = entry?.entity_id;
  }
  return found;
}

/** The devices with openframe entities, those that answer first, for the card picker's choice. */
export function frameDevices(hass) {
  const own = Object.values(hass?.entities ?? {}).filter(
    (entry) => entry.platform === DOMAIN && entry.device_id,
  );
  const ids = [...new Set(own.map((entry) => entry.device_id))];
  const answers = (id) =>
    own.some((entry) => {
      const state = hass.states?.[entry.entity_id]?.state;
      return entry.device_id === id && state !== undefined && state !== "unavailable";
    });
  return [...ids.filter(answers), ...ids.filter((id) => !answers(id))];
}

function deviceName(hass, deviceId) {
  const device = hass?.devices?.[deviceId];
  return device?.name_by_user || device?.name || "";
}

const ABSENT = new Set(["unavailable", "unknown"]);

/**
 * Everything the view shows, from the configuration and the frame's entities:
 * `{ error }` for a configuration without a frame, otherwise the title, the photo, its box, the
 * badges, the caption and the buttons.
 */
export function cardState(hass, config) {
  const text = strings(languageOf(hass));
  const deviceId = config?.device_id;
  if (!deviceId) {
    return { error: text.chooseFrame };
  }
  const entities = findEntities(hass, deviceId);
  if (entities === null) {
    return { error: text.notFrame };
  }
  const state = (part) => (entities[part] ? hass.states?.[entities[part]] : undefined);
  const available = (part) => {
    const s = state(part);
    return s !== undefined && s.state !== "unavailable";
  };
  const title = config.title || deviceName(hass, deviceId);

  // The frame does not answer: every entity it has reports itself unavailable
  const present = Object.keys(PARTS).filter((part) => state(part) !== undefined);
  if (present.length > 0 && present.every((part) => !available(part))) {
    return {
      title,
      ratio: DEFAULT_RATIO,
      photo: null,
      dimmed: false,
      badges: [text.unavailable],
      caption: null,
      buttons: null,
    };
  }

  const image = state("image");
  const width = Number(image?.attributes?.screen_width);
  const height = Number(image?.attributes?.screen_height);
  const ratio = width > 0 && height > 0 ? `${width} / ${height}` : DEFAULT_RATIO;
  const photo =
    image && !ABSENT.has(image.state) && image.attributes?.entity_picture
      ? image.attributes.entity_picture
      : null;

  const displayOff = state("display")?.state === "off";
  const paused = state("slideshow")?.state === "off";
  const safeMode = state("safeMode")?.state === "on";
  const badges = [
    ...(displayOff ? [text.displayOff] : []),
    ...(paused ? [text.paused] : []),
    ...(safeMode ? [text.safeMode] : []),
  ];

  let caption = null;
  const sensor = state("caption");
  if (config.show_caption !== false && sensor && !ABSENT.has(sensor.state)) {
    caption = { name: sensor.state, album: sensor.attributes?.album || null };
  }

  const step = (part, label) => ({
    entity: entities[part],
    shown: available(part),
    // The frame refuses to change photos while its display is off
    enabled: !displayOff,
    label,
  });
  const buttons = {
    previous: step("previous", text.previous),
    playPause: {
      entity: entities.slideshow,
      shown: available("slideshow"),
      enabled: true,
      playing: !paused,
      label: paused ? text.resume : text.pause,
    },
    next: step("next", text.next),
    display: {
      entity: entities.display,
      shown: available("display"),
      enabled: true,
      on: !displayOff,
      label: displayOff ? text.switchOn : text.switchOff,
    },
  };

  return {
    title,
    ratio,
    photo,
    noPhoto: text.noPhoto,
    dimmed: displayOff,
    badges,
    caption,
    buttons,
  };
}

/** The service call of a button: domain, service and entity. */
export function action(name, buttons) {
  switch (name) {
    case "previous":
    case "next":
      return ["button", "press", buttons[name].entity];
    case "playPause":
      return ["switch", buttons.playPause.playing ? "turn_off" : "turn_on", buttons.playPause.entity];
    case "display":
      return ["light", "toggle", buttons.display.entity];
    default:
      throw new Error(`unknown button ${name}`);
  }
}

/** The editor's form: a device picker limited to openframe, the title and the caption switch. */
export function editorSchema() {
  return [
    { name: "device_id", required: true, selector: { device: { integration: DOMAIN } } },
    { name: "title", selector: { text: {} } },
    { name: "show_caption", default: true, selector: { boolean: {} } },
  ];
}

/** The editor's label of a form field. */
export function editorLabel(name, language) {
  const text = strings(language);
  return { device_id: text.frame, title: text.title, show_caption: text.showCaption }[name] ?? name;
}
