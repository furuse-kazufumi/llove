"""Internationalisation (i18n) for llove.

Strings the user sees live in TOML files under ``llove/i18n/locales/``.
At runtime, a single :class:`Translator` resolves dotted keys to the active
locale, falling back to ``en`` when a key is missing.

Usage::

    from llove.i18n import t, set_locale

    set_locale("ja")
    title = t("ui.pane.sensor_stream_title")
    body = t("scenario.scada.phase1")

The locale is chosen in this order:

1. Explicit ``set_locale("xx")`` call (or ``--lang`` from the CLI).
2. ``LLOVE_LANG`` environment variable (e.g. ``ja``).
3. ``locale.getdefaultlocale()`` first segment (e.g. ``ja_JP`` -> ``ja``).
4. Fallback ``en``.

Adding a new language is just adding ``llove/i18n/locales/<code>.toml``
with the same key tree as ``en.toml``. See ``docs/i18n.md`` for the full
contributor guide.
"""
from __future__ import annotations

import locale as _locale
import os
import tomllib
from importlib.resources import files
from pathlib import Path

DEFAULT_LOCALE = "en"


class Translator:
    """Resolves dotted-key strings from TOML files; falls back to ``en``."""

    def __init__(self) -> None:
        self._cache: dict[str, dict] = {}
        self._active: str = DEFAULT_LOCALE
        self._fallback = self._load(DEFAULT_LOCALE)
        self._auto_detect()

    def _auto_detect(self) -> None:
        env = os.environ.get("LLOVE_LANG", "").strip().lower()
        if env:
            self.set_locale(env)
            return
        try:
            sys_locale = _locale.getdefaultlocale()[0]
        except Exception:  # nosec B110 — locale lookup is best-effort
            sys_locale = None
        if sys_locale:
            primary = sys_locale.split("_")[0].lower()
            if self._has_locale(primary):
                self._active = primary

    def _has_locale(self, code: str) -> bool:
        return self._locale_path(code).exists()

    def _locale_path(self, code: str) -> Path:
        # Use importlib.resources so the lookup also works from an installed wheel.
        try:
            return Path(str(files("llove.i18n.locales").joinpath(f"{code}.toml")))
        except Exception:  # nosec B110 — package layout fallback for editable installs
            return Path(__file__).parent / "locales" / f"{code}.toml"

    def _load(self, code: str) -> dict:
        if code in self._cache:
            return self._cache[code]
        p = self._locale_path(code)
        if not p.exists():
            self._cache[code] = {}
            return {}
        with p.open("rb") as fh:
            data = tomllib.load(fh)
        self._cache[code] = data
        return data

    def set_locale(self, code: str) -> None:
        """Activate a locale. Loading is lazy on first ``t()`` call."""
        code = code.strip().lower()
        if not code:
            return
        if not self._has_locale(code):
            # Fall back silently; no exception so apps stay running.
            self._active = DEFAULT_LOCALE
            return
        self._active = code

    @property
    def active_locale(self) -> str:
        return self._active

    def t(self, key: str, /, **subs: object) -> str:
        """Resolve a dotted key. ``subs`` are str.format kwargs."""
        active = self._load(self._active) if self._active != DEFAULT_LOCALE else self._fallback
        value = self._lookup(active, key)
        if value is None:
            value = self._lookup(self._fallback, key)
        if value is None:
            return key  # last-ditch: show the key itself
        if subs:
            try:
                return value.format(**subs)
            except (KeyError, IndexError):
                return value
        return value

    @staticmethod
    def _lookup(tree: dict, key: str) -> str | None:
        node: object = tree
        for part in key.split("."):
            if not isinstance(node, dict) or part not in node:
                return None
            node = node[part]
        return node if isinstance(node, str) else None


# Module-level singleton — convenient and matches LLMesh's util style.
_translator = Translator()


def t(key: str, /, **subs: object) -> str:
    """Resolve a translation key under the active locale."""
    return _translator.t(key, **subs)


def set_locale(code: str) -> None:
    """Activate a locale. ``code`` is e.g. ``"en"`` / ``"ja"``."""
    _translator.set_locale(code)


def active_locale() -> str:
    """Return the currently active locale code."""
    return _translator.active_locale


def available_locales() -> list[str]:
    """Enumerate every locale TOML found in ``llove/i18n/locales/``."""
    here = Path(__file__).parent / "locales"
    return sorted(p.stem for p in here.glob("*.toml"))


__all__ = ["t", "set_locale", "active_locale", "available_locales", "Translator"]
