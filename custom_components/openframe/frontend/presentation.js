// What the frame shows of a photo: a copy of openframe's `presentation.ts` (web UI), which is itself
// a copy of `Presentation.of` in its core (openspec change photo-crop, design decisions 1 to 3). The
// crop editor follows every finger movement with it without asking the frame. All three run the
// cases of openframe's `api/fixtures/presentation-cases.json`, which tools/update-contract.sh copies
// to tests/contract/ at the pinned release, so they cannot drift apart unnoticed. The frame's
// `presentation` stays the authority.
//
// Sizes are {width, height}; a section (crop) is {x, y, zoom} with the focus point as fractions of
// the photo after EXIF rotation; a presentation is the shown window {x, y, width, height} as
// fractions of the photo and the zoom it is shown with.

// `auto` crops at most this share of the photo in the direction in which it does not fit the screen
export const AUTO_MAX_CROP = 0.25;
export const MAX_ZOOM = 4;
const EPSILON = 1e-9;

// The screen in the configured orientation, from the device's natural resolution
export function screenFor(natural, orientation) {
  const long = Math.max(natural.width, natural.height);
  const short = Math.min(natural.width, natural.height);
  return orientation === "landscape" ? { width: long, height: short } : { width: short, height: long };
}

function cover(photo, screen) {
  return Math.max(screen.width / photo.width, screen.height / photo.height);
}

// At most 1, and exactly 1 where only rounding keeps it below
function fraction(value) {
  return value >= 1 - EPSILON ? 1 : value;
}

export function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

// From fully visible to one original pixel per screen pixel, at most 4; a photo smaller than the
// screen allows 1
export function zoomRange(photo, screen) {
  const c = cover(photo, screen);
  const fit = Math.min(screen.width / photo.width, screen.height / photo.height);
  return { min: fit / c, max: Math.max(1, Math.min(MAX_ZOOM, 1 / c)) };
}

// What the frame shows of `photo` on `screen`: with `crop` its section, else the preset of `fillMode`
export function presentationOf(photo, screen, crop, fillMode) {
  const range = zoomRange(photo, screen);
  let zoom;
  if (crop) zoom = clamp(crop.zoom, range.min, range.max);
  else if (fillMode === "fill") zoom = 1;
  else if (fillMode === "fit") zoom = range.min;
  else zoom = Math.min(1, range.min / (1 - AUTO_MAX_CROP));
  const scale = cover(photo, screen) * zoom;
  const w = fraction(screen.width / (scale * photo.width));
  const h = fraction(screen.height / (scale * photo.height));
  const cx = clamp(crop?.x ?? 0.5, w / 2, 1 - w / 2);
  const cy = clamp(crop?.y ?? 0.5, h / 2, 1 - h / 2);
  return { x: cx - w / 2, y: cy - h / 2, width: w, height: h, zoom };
}

// Where the shown part of the photo stands on the screen, as fractions of the screen: the rest is
// black borders
export function shownArea(photo, screen, presentation) {
  const scale = cover(photo, screen) * presentation.zoom;
  return {
    width: Math.min(1, (presentation.width * photo.width * scale) / screen.width),
    height: Math.min(1, (presentation.height * photo.height * scale) / screen.height),
  };
}
