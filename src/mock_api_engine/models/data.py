from typing import Literal

from pydantic import BaseModel, ConfigDict


class CreateDataRequest(BaseModel):
    customerName: str
    referenceNumber: str
    referenceType: str
    customerAddress: str
    customerEmail: str
    customerPhone: str
    customerDateOfBirth: str
    


class DataRecord(CreateDataRequest):
    model_config = ConfigDict(extra="allow")

    customerName: str | None = None
    referenceNumber: str | None = None
    referenceType: str | None = None
    customerAddress: str | None = None
    customerEmail: str | None = None
    customerPhone: str | None = None
    customerDateOfBirth: str | None = None
    id: str
    modified: bool


class CreateDataResponse(BaseModel):
    status: Literal["created"]
    id: str
    data: DataRecord