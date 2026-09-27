from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request, status

from mock_api_engine.services.data_service import (
    DataNotFoundError,
    DataService,
    InvalidQuotationActionError,
    InvalidQuotationIdError,
    InvalidProjectionInputError,
)

router = APIRouter(tags=["data"])


def get_data_service(request: Request) -> DataService:
    return request.app.state.data_service


@router.post("/data")
def create_data(payload: dict[str, Any], request: Request) -> dict[str, Any]:
    record_id, data = get_data_service(request).create(payload)
    return {"status": "created", "id": record_id, "data": data}


@router.post("/create", status_code=status.HTTP_201_CREATED)
def create_quotation(
    payload: dict[str, Any], request: Request
) -> dict[str, Any]:
    try:
        return get_data_service(request).create_quotation(payload)
    except InvalidQuotationActionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except InvalidQuotationIdError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except InvalidProjectionInputError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except DataNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Quotation not found") from exc


@router.get("/linked-quotes")
def get_linked_quotations(
    request: Request,
    quotation_id: str = Query(),
) -> dict[str, Any]:
    try:
        return get_data_service(request).get_linked_quotations(quotation_id)
    except DataNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Quotation not found") from exc


@router.get("/data", response_model=None)
def get_data(
    request: Request,
    quotation_id: str = Query(),
    page_context: str | None = Query(default=None),
) -> Any:
    service = get_data_service(request)
    try:
        if page_context is not None:
            return service.get_static_response(quotation_id, page_context)
        return service.get_quotation(quotation_id)
    except DataNotFoundError as exc:
        detail = "Static response not found" if page_context is not None else "Quotation not found"
        raise HTTPException(status_code=404, detail=detail) from exc