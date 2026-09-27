import json
import os
import re
import tempfile
from datetime import date
from pathlib import Path
from threading import RLock
from typing import Any


class JsonDataRepository:
    _RELATIONSHIPS_FILENAME = "quotation_relationships.json"

    def __init__(self, data_directory: Path) -> None:
        self._data_directory = data_directory
        self._static_directory = data_directory / "static"
        self._quotation_children: dict[str, list[str]] = {}
        self._lock = RLock()

    def load(self) -> None:
        with self._lock:
            self._data_directory.mkdir(parents=True, exist_ok=True)
            for data_file in self._data_directory.glob("*.json"):
                try:
                    json.loads(data_file.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError) as exc:
                    raise RuntimeError(
                        f"Unable to load JSON record at {data_file}"
                    ) from exc
            relationships_path = self._data_directory / self._RELATIONSHIPS_FILENAME
            if relationships_path.is_file():
                try:
                    relationships = json.loads(
                        relationships_path.read_text(encoding="utf-8")
                    )
                    parent_to_children = relationships["parent_to_children"]
                    if not isinstance(parent_to_children, dict) or any(
                        not isinstance(parent, str)
                        or not isinstance(children, list)
                        or any(not isinstance(child, str) for child in children)
                        for parent, children in parent_to_children.items()
                    ):
                        raise ValueError("Invalid parent-to-children mapping")
                except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
                    raise RuntimeError(
                        f"Unable to load quotation relationships at {relationships_path}"
                    ) from exc
                self._quotation_children = {
                    parent: list(dict.fromkeys(children))
                    for parent, children in parent_to_children.items()
                }
            else:
                self._quotation_children = {}

    def save(self, record_id: str, data: dict[str, Any]) -> None:
        with self._lock:
            self._data_directory.mkdir(parents=True, exist_ok=True)
            record_path = self._data_directory / f"{record_id}.json"
            self._write_json(record_path, data)

    def create_quotation(
        self, quotation_id: str | None, template: dict[str, Any]
    ) -> dict[str, Any]:
        with self._lock:
            self._data_directory.mkdir(parents=True, exist_ok=True)
            if quotation_id is None:
                quotation_id = self._next_quotation_id(template)
            elif re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", quotation_id) is None:
                raise ValueError("quotation_id contains unsupported characters")

            record_path = self._data_directory / f"{quotation_id}.json"
            if record_path.exists():
                existing_quotation = self.get_quotation(quotation_id)
                if existing_quotation is not None:
                    return existing_quotation
                raise RuntimeError(
                    f"A non-quotation record already uses ID {quotation_id}"
                )

            quotation = {**template, "quotation_id": quotation_id}
            self._write_json(record_path, quotation)
            return quotation

    def get_quote_template(self) -> dict[str, Any]:
        template = self._read_json(
            self._static_directory / "New_Quote_Template.json"
        )
        if not isinstance(template, dict):
            raise RuntimeError("The quotation template must contain a JSON object")
        return template

    def get_quotation(self, quotation_id: str) -> dict[str, Any] | None:
        if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", quotation_id) is None:
            return None

        with self._lock:
            quotation_path = self._data_directory / f"{quotation_id}.json"
            if not quotation_path.is_file():
                return None
            quotation = self._read_json(quotation_path)
            if not isinstance(quotation, dict) or quotation.get("quotation_id") != quotation_id:
                return None
            return quotation

    def clone_quotation(self, parent_quotation_id: str) -> dict[str, Any] | None:
        with self._lock:
            parent = self.get_quotation(parent_quotation_id)
            if parent is None:
                return None

            child_quotation_id = self._next_quotation_id(parent)
            child = {
                **parent,
                "quotation_id": child_quotation_id,
                "parent_quotation_id": parent_quotation_id,
            }
            child_path = self._data_directory / f"{child_quotation_id}.json"
            if child_path.exists():
                raise RuntimeError(f"Quotation ID collision: {child_quotation_id}")

            updated_children = list(
                dict.fromkeys(
                    [*self._quotation_children.get(parent_quotation_id, []), child_quotation_id]
                )
            )
            self._write_json(child_path, child)
            try:
                relationships = {
                    **self._quotation_children,
                    parent_quotation_id: updated_children,
                }
                self._write_json(
                    self._data_directory / self._RELATIONSHIPS_FILENAME,
                    {"parent_to_children": relationships},
                )
            except Exception:
                child_path.unlink(missing_ok=True)
                raise

            self._quotation_children[parent_quotation_id] = updated_children
            return child

    def get_quotation_relationships(self) -> dict[str, list[str]]:
        with self._lock:
            return {
                parent: list(children)
                for parent, children in self._quotation_children.items()
            }

    def get_linked_quotations(self, quotation_id: str) -> dict[str, Any] | None:
        with self._lock:
            quotation = self.get_quotation(quotation_id)
            if quotation is None:
                return None

            parent_id = quotation_id
            if quotation_id not in self._quotation_children:
                related_parent_id = quotation.get("parent_quotation_id")
                if isinstance(related_parent_id, str) and related_parent_id:
                    parent_id = related_parent_id

            return {
                "parent_quotation_id": parent_id,
                "child_quotation_ids": list(self._quotation_children.get(parent_id, [])),
            }

    def get_template(self) -> dict[str, Any]:
        template = self._read_static_json("template.json")
        if not isinstance(template, dict):
            raise RuntimeError("The static template must contain a JSON object")
        return template

    def get_static_response(
        self, reference_number: str, page_context: str
    ) -> tuple[bool, Any]:
        responses = self._read_static_json("responses.json")
        if not isinstance(responses, dict):
            raise RuntimeError("Static responses must contain a JSON object")

        reference_responses = responses.get(reference_number)
        if not isinstance(reference_responses, dict) or page_context not in reference_responses:
            return False, None
        return True, reference_responses[page_context]

    def _read_static_json(self, filename: str) -> Any:
        path = self._static_directory / filename
        return self._read_json(path)

    @staticmethod
    def _read_json(path: Path) -> Any:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Unable to load static JSON file at {path}") from exc

    def _next_quotation_id(self, template: dict[str, Any]) -> str:
        year = date.today().year
        prefix = f"QTN-{year}-"
        highest_number = 0

        template_id = template.get("quotation_id")
        if isinstance(template_id, str) and template_id.startswith(prefix):
            suffix = template_id[len(prefix):]
            if suffix.isdigit():
                highest_number = int(suffix)

        for record_path in self._data_directory.glob(f"{prefix}*.json"):
            suffix = record_path.stem[len(prefix):]
            if suffix.isdigit():
                highest_number = max(highest_number, int(suffix))

        return f"{prefix}{highest_number + 1:06d}"

    @staticmethod
    def _write_json(path: Path, data: dict[str, Any]) -> None:
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=path.parent,
                delete=False,
            ) as temporary_file:
                temporary_path = Path(temporary_file.name)
                json.dump(data, temporary_file, indent=2)
            os.replace(temporary_path, path)
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)