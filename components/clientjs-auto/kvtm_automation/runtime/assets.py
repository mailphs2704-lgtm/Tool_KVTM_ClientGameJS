from __future__ import annotations

from pathlib import Path
from typing import Iterable

from ..errors import TemplateNotFound


_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}


class AssetLibrary:
    """Lazy index over reference templates copied from the recovered AUTO PRO assets."""

    def __init__(self, roots: Iterable[Path]) -> None:
        self.roots = tuple(Path(root).resolve() for root in roots if Path(root).exists())
        self._index: dict[str, list[Path]] | None = None

    @classmethod
    def from_package(cls, component_root: Path, auto_root: Path) -> "AssetLibrary":
        component_root = Path(component_root).resolve()
        auto_root = Path(auto_root).resolve()
        return cls(
            (
                component_root / "assets" / "items",
                component_root / "assets",
                auto_root / "assets" / "items",
                auto_root / "assets",
            )
        )

    def _build_index(self) -> dict[str, list[Path]]:
        if self._index is not None:
            return self._index
        index: dict[str, list[Path]] = {}
        seen: set[Path] = set()
        for root in self.roots:
            if not root.is_dir():
                continue
            for path in root.rglob("*"):
                if not path.is_file() or path.suffix.lower() not in _IMAGE_SUFFIXES:
                    continue
                resolved = path.resolve()
                if resolved in seen:
                    continue
                seen.add(resolved)
                index.setdefault(path.stem.lower(), []).append(resolved)
                index.setdefault(path.name.lower(), []).append(resolved)
        self._index = index
        return index

    def candidates(self, name: str) -> tuple[Path, ...]:
        key = str(name).strip().lower()
        if not key:
            return ()
        index = self._build_index()
        result = list(index.get(key, ()))
        if not Path(key).suffix:
            for suffix in _IMAGE_SUFFIXES:
                result.extend(index.get(key + suffix, ()))
        unique: list[Path] = []
        seen: set[Path] = set()
        for path in result:
            if path in seen:
                continue
            seen.add(path)
            unique.append(path)
        return tuple(unique)

    def require(self, name: str) -> Path:
        candidates = self.candidates(name)
        if not candidates:
            raise TemplateNotFound(f"Không tìm thấy template: {name}")
        return candidates[0]

    def has(self, name: str) -> bool:
        return bool(self.candidates(name))
