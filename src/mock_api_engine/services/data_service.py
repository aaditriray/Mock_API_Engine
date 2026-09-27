from typing import Any
from uuid import uuid4

from mock_api_engine.repositories.json_data_repository import JsonDataRepository
from mock_api_engine.services.projection import ProjectionInputError, calculate_projection


class DataNotFoundError(Exception):
    pass


class InvalidQuotationIdError(Exception):
    pass


class InvalidQuotationActionError(Exception):
    pass


class InvalidProjectionInputError(Exception):
    pass


class DataService:
    def __init__(self, repository: JsonDataRepository) -> None:
        self._repository = repository

    def create(self, payload: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        record_id = str(uuid4())
        data = self._merge(self._repository.get_template(), payload)
        self._repository.save(record_id, data)
        return record_id, data

    def create_quotation(self, payload: dict[str, Any]) -> dict[str, Any]:
        action = payload.get("action")
        if action == "Init":
            return self._repository.create_quotation(
                None, self._repository.get_quote_template()
            )
        if action == "CALC":
            return self.calculate_quotation(payload)
        if action == "CLONE":
            quotation_id = payload.get("quotation_id")
            if not isinstance(quotation_id, str) or not quotation_id.strip():
                raise InvalidQuotationIdError("quotation_id is required for CLONE")

            parent_quotation_id = quotation_id.strip()
            quotation = self._repository.clone_quotation(parent_quotation_id)
            if quotation is None:
                raise DataNotFoundError(parent_quotation_id)
            return quotation
        if action != "Save":
            raise InvalidQuotationActionError(
                "action must be 'Init', 'Save', 'CALC', or 'CLONE'"
            )

        quotation_id = payload.get("quotation_id")
        if not isinstance(quotation_id, str) or not quotation_id.strip():
            raise InvalidQuotationIdError("quotation_id must be a string")

        normalized_id = quotation_id.strip()
        existing_quotation = self._repository.get_quotation(normalized_id)
        if existing_quotation is None:
            raise DataNotFoundError(normalized_id)

        updates = {key: value for key, value in payload.items() if key != "quotation_id"}
        updated_quotation = self._merge(existing_quotation, updates)
        updated_quotation["quotation_id"] = normalized_id
        self._repository.save(normalized_id, updated_quotation)
        return updated_quotation

    def calculate_quotation(self, payload: dict[str, Any]) -> dict[str, Any]:
        quotation_id = payload.get("quotation_id")
        if not isinstance(quotation_id, str) or not quotation_id.strip():
            raise InvalidQuotationIdError("quotation_id is required for CALC")

        normalized_id = quotation_id.strip()
        quotation = self._repository.get_quotation(normalized_id)
        if quotation is None:
            raise DataNotFoundError(normalized_id)

        updates = {
            key: value
            for key, value in payload.items()
            if key not in {"quotation_id", "annuity_rate_percent"}
        }
        quotation = self._merge(quotation, updates)
        quotation.pop("annuity_rate_percent", None)
        try:
            quotation["projection"] = calculate_projection(quotation)
        except ProjectionInputError as exc:
            raise InvalidProjectionInputError(str(exc)) from exc

        quotation["quotation_id"] = normalized_id
        self._repository.save(normalized_id, quotation)
        return quotation

    def get_quotation(self, quotation_id: str) -> dict[str, Any]:
        quotation = self._repository.get_quotation(quotation_id)
        if quotation is None:
            raise DataNotFoundError(quotation_id)
        return quotation

    def get_linked_quotations(self, quotation_id: str) -> dict[str, Any]:
        linked_quotations = self._repository.get_linked_quotations(quotation_id)
        if linked_quotations is None:
            raise DataNotFoundError(quotation_id)
        return linked_quotations

    def get_static_response(self, reference_number: str, page_context: str) -> Any:
        found, response = self._repository.get_static_response(
            reference_number, page_context
        )
        if not found:
            raise DataNotFoundError(reference_number)
        return response

    @classmethod
    def _merge(cls, template: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
        merged = template.copy()
        for key, value in payload.items():
            if isinstance(merged.get(key), dict) and isinstance(value, dict):
                merged[key] = cls._merge(merged[key], value)
            else:
                merged[key] = value
        return merged