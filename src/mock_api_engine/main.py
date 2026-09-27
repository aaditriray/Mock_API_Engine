from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

import uvicorn
from fastapi import FastAPI

from mock_api_engine.api.controllers.data_controller import router as data_router
from mock_api_engine.core.settings import Settings
from mock_api_engine.repositories.json_data_repository import JsonDataRepository
from mock_api_engine.services.data_service import DataService


def create_app(data_directory: Path | None = None) -> FastAPI:
    settings = Settings.from_environment(data_directory)
    repository = JsonDataRepository(settings.data_directory)
    service = DataService(repository)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        repository.load()
        yield

    app = FastAPI(title="Mock API Engine", lifespan=lifespan)
    app.state.data_service = service
    app.include_router(data_router)
    return app


app = create_app()


def main() -> None:
    uvicorn.run(app, host="0.0.0.0", port=8000)
