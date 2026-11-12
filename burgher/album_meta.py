"""
Per-album metadata read from an ``album.yaml`` file inside the album folder.

The file is optional and every key in it is optional; a missing file means
"behave exactly as before". It is written by tintinburgh-studio but is meant
to stay hand-editable::

    secret: true                     # same effect as a .secret file
    cover: DSCF1234.jpg              # album thumbnail, beats main.*
    photo_order: [b.jpg, a.jpg]      # unlisted photos follow in date order
    subalbum_order: [Porto, Lisboa]  # dir names, unlisted follow newest first
    embedded_order: [_Under, _WU]    # dir names as on disk, unlisted follow oldest first
    photos:
      a.jpg:
        description: Ribeira at dusk.

Must stay Python 3.9 compatible.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, TypeVar

import yaml

META_FILENAME = "album.yaml"
# Generated alt texts, one line per photo ({filename: text}). Kept apart from album.yaml
# because tintinburgh-studio rewrites that file's `photos` block from its own form and
# would drop any extra key. A hand-written description always wins over this.
ALT_FILENAME = "alt.yaml"

T = TypeVar("T")


class AlbumMetaError(Exception):
    pass


@dataclass
class AlbumMeta:
    secret: bool = False
    cover: Optional[str] = None
    photo_order: List[str] = field(default_factory=list)
    subalbum_order: List[str] = field(default_factory=list)
    embedded_order: List[str] = field(default_factory=list)
    photos: Dict[str, dict] = field(default_factory=dict)

    def description(self, filename: str) -> Optional[str]:
        entry = self.photos.get(filename)
        if not isinstance(entry, dict):
            return None
        text = entry.get("description")
        if not text:
            return None
        text = str(text).strip()
        return text or None


def load_alt_texts(folder: Path) -> Dict[str, str]:
    """alt.yaml in the album folder -> {filename: alt text}; {} when absent."""
    path = folder / ALT_FILENAME
    if not path.exists():
        return {}
    with open(path) as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in data.items()
    ):
        raise AlbumMetaError(f"{path}: expected a mapping of filename to alt text")
    return {k: v.strip() for k, v in data.items() if v.strip()}


def _str_list(path: Path, key: str, value) -> List[str]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise AlbumMetaError(f"{path}: '{key}' must be a list of strings")
    return value


def load_album_meta(folder: Path) -> AlbumMeta:
    path = Path(folder) / META_FILENAME
    if not path.exists():
        return AlbumMeta()

    with open(path, "r", encoding="utf-8") as f:
        try:
            raw = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise AlbumMetaError(f"{path}: invalid yaml: {e}") from e

    if raw is None:
        return AlbumMeta()
    if not isinstance(raw, dict):
        raise AlbumMetaError(f"{path}: top level must be a mapping")

    secret = raw.get("secret", False)
    if not isinstance(secret, bool):
        raise AlbumMetaError(f"{path}: 'secret' must be true or false")

    cover = raw.get("cover")
    if cover is not None and not isinstance(cover, str):
        raise AlbumMetaError(f"{path}: 'cover' must be a filename")

    photos = raw.get("photos") or {}
    if not isinstance(photos, dict):
        raise AlbumMetaError(f"{path}: 'photos' must be a mapping of filename -> fields")
    for name, entry in photos.items():
        if entry is not None and not isinstance(entry, dict):
            raise AlbumMetaError(f"{path}: photos['{name}'] must be a mapping")

    return AlbumMeta(
        secret=secret,
        cover=cover or None,
        photo_order=_str_list(path, "photo_order", raw.get("photo_order")),
        subalbum_order=_str_list(path, "subalbum_order", raw.get("subalbum_order")),
        embedded_order=_str_list(path, "embedded_order", raw.get("embedded_order")),
        photos={k: (v or {}) for k, v in photos.items()},
    )


def apply_order(items: Iterable[T], explicit: List[str], key: Callable[[T], str]) -> List[T]:
    """
    Items whose key is listed in ``explicit`` come first, in that order; the
    rest keep their incoming order. Keys in ``explicit`` without a matching
    item are ignored.
    """
    items = list(items)
    if not explicit:
        return items

    by_key = {}
    for item in items:
        by_key.setdefault(key(item), item)

    ordered = []
    seen = set()
    for k in explicit:
        item = by_key.get(k)
        if item is not None and k not in seen:
            ordered.append(item)
            seen.add(k)

    ordered.extend(item for item in items if key(item) not in seen)
    return ordered
