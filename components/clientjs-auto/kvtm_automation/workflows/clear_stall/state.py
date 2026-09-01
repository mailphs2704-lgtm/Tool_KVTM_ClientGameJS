from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import shutil
import time

from ...models import VisualFingerprint
from .manifest import ClearStallManifest, PurchasedRecord


CARRYOVER_VERSION = 2


class CarryoverStore:
    """Persistent unsold VP state, isolated from run diagnostics.

    Layout under one clone profile:

    ```text
    <profile-clear-stall-root>/
    ├─ state/
    │  ├─ carryover.json
    │  └─ templates/<perceptual-hash>.png
    └─ runs/<timestamp>/...
    ```

    Keeping state separate from run folders prevents rebuild/cleanup code from
    confusing diagnostic artifacts with data needed by the next scheduled run.
    """

    def __init__(self, profile_root: Path) -> None:
        self.profile_root = Path(profile_root).resolve()
        self.state_dir = self.profile_root / "state"
        self.template_dir = self.state_dir / "templates"
        self.path = self.state_dir / "carryover.json"

    def load(self, profile_id: str) -> list[PurchasedRecord]:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return []
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Không đọc được carryover Dọn quầy: {exc}") from exc

        if not isinstance(payload, dict):
            raise RuntimeError("Carryover Dọn quầy không phải JSON object")
        if int(payload.get("version") or 0) != CARRYOVER_VERSION:
            raise RuntimeError("Carryover Dọn quầy sai phiên bản")
        if str(payload.get("profile_id") or "") != str(profile_id):
            raise RuntimeError("Carryover Dọn quầy không thuộc clone hiện tại")
        raw_items = payload.get("items")
        if not isinstance(raw_items, list):
            raise RuntimeError("Carryover Dọn quầy thiếu danh sách VP")

        records: list[PurchasedRecord] = []
        for raw in raw_items:
            record = PurchasedRecord.from_dict(raw)
            copy = record.carryover_copy()
            if copy is not None:
                records.append(copy)
        return records

    def save(self, manifest: ClearStallManifest) -> None:
        pending: list[PurchasedRecord] = []
        for record in manifest.records:
            copy = record.carryover_copy()
            if copy is None:
                continue
            copy = self._persist_template(copy)
            pending.append(copy)

        if not pending:
            try:
                self.path.unlink(missing_ok=True)
            except OSError:
                pass
            self._remove_unused_templates(set())
            return

        self.state_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": CARRYOVER_VERSION,
            "profile_id": str(manifest.profile_id),
            "updated_at": time.time(),
            "items": [
                {
                    "fingerprint": record.fingerprint.to_dict(),
                    "source_view": 0,
                    "source_local_slot": 0,
                    "source_physical_slot": 0,
                    "purchased_quantity": record.purchased_quantity,
                    "sold_quantity": 0,
                }
                for record in pending
            ],
        }
        temporary = self.path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(self.path)
        self._remove_unused_templates(
            {record.fingerprint.group_key for record in pending}
        )

    def _persist_template(self, record: PurchasedRecord) -> PurchasedRecord:
        fingerprint = record.fingerprint
        source = Path(fingerprint.template_file) if fingerprint.template_file else None
        destination = self.template_dir / f"{fingerprint.group_key}.png"
        if source is not None and source.is_file():
            self.template_dir.mkdir(parents=True, exist_ok=True)
            if source.resolve() != destination.resolve():
                shutil.copy2(source, destination)
        elif not destination.is_file():
            # The quantity remains recorded, but resale must not guess an item
            # identity if its persistent visual template is gone.
            return record

        persisted = replace(
            fingerprint,
            template_file=str(destination) if destination.is_file() else fingerprint.template_file,
        )
        return replace(record, fingerprint=persisted)

    def _remove_unused_templates(self, group_keys: set[str]) -> None:
        if not self.template_dir.is_dir():
            return
        for path in self.template_dir.glob("*.png"):
            if path.stem not in group_keys:
                try:
                    path.unlink()
                except OSError:
                    pass
