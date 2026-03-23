"""Religion ID to display name resolution from EU5 localization files."""

from __future__ import annotations

import os
import re

_CULREL_PATH = "main_menu/localization/russian/customizable_localization_ru_culrel_l_russian.yml"
_RELIGION_EN_PATH = "main_menu/localization/english/religion_l_english.yml"

# Paradox localization YAML: key: "value" lines
_LOC_PATTERN = re.compile(r'^\s*([\w_]+):\s*"([^"]*)"', re.MULTILINE)


def _parse_localization_yml(path: str) -> dict[str, str]:
    """Extract key -> value pairs from Paradox localization YAML format."""
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8-sig") as f:
            content = f.read()
    except OSError:
        return {}
    return dict(_LOC_PATTERN.findall(content))


class ReligionData:
    """Resolves religion IDs to display names using game localization files."""

    def __init__(self, path_resolver):
        self.path_resolver = path_resolver
        self.id_to_name: dict[int, str] = {}
        self._load()

    def _load(self) -> None:
        # 1. Load slug -> name from religion_l_english (defines valid religion slugs)
        slug_to_name: dict[str, str] = {}
        for path in reversed(self.path_resolver.resolve_path(_RELIGION_EN_PATH)):
            kv = _parse_localization_yml(path)
            for key, val in kv.items():
                if key.endswith("_ADJ") or key.endswith("_desc") or key.endswith("_group"):
                    continue
                if "_god" in key or key.startswith("worship_"):
                    continue
                slug_to_name[key] = val

        valid_religion_slugs = frozenset(slug_to_name.keys())

        # 2. Load id -> slug from customizable_localization (*_tt: "id") for religions only
        id_to_slug: dict[int, str] = {}
        for path in reversed(self.path_resolver.resolve_path(_CULREL_PATH)):
            kv = _parse_localization_yml(path)
            for key, val in kv.items():
                if key.endswith("_tt") and val.isdigit():
                    slug = key[:-3]  # strip _tt
                    if slug in valid_religion_slugs:
                        rid = int(val)
                        id_to_slug[rid] = slug

        # 3. Build id -> name
        for rid, slug in id_to_slug.items():
            name = slug_to_name.get(slug)
            if name:
                self.id_to_name[rid] = name
            else:
                self.id_to_name[rid] = slug.replace("_", " ").title()

    def resolve(self, religion_id) -> str:
        """Return display name for a religion ID. Handles float, int, NaN."""
        if religion_id is None or (isinstance(religion_id, float) and religion_id != religion_id):
            return "Unknown"
        rid = int(religion_id) if isinstance(religion_id, (int, float)) else None
        if rid is None:
            return str(religion_id)
        return self.id_to_name.get(rid, f"Religion {rid}")
