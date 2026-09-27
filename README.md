# Mock API Engine

A lightweight FastAPI service for persisting arbitrary JSON payloads and managing quotation-style records in a file-backed JSON store.

## Overview

The application exposes two main data patterns:

- Generic JSON records via `POST /data`
- Quotation workflow operations via `POST /create`, `GET /data`, and `GET /linked-quotes`

All records are stored as JSON files under the configured data directory. Static templates and response lookups are also kept in the data folder, making the service easy to configure without changing Python code.

## Project structure

- `src/mock_api_engine/main.py` creates the FastAPI app and loads the repository on startup.
- `src/mock_api_engine/api/controllers/data_controller.py` defines the HTTP routes.
- `src/mock_api_engine/services/data_service.py` contains the write and merge logic.
- `src/mock_api_engine/repositories/json_data_repository.py` handles JSON persistence, templates, static responses, and quotation relationships.
- `src/mock_api_engine/core/settings.py` resolves the configured data directory from the environment.
- `data/static/` contains default template and mock response fixtures.

## Requirements

- Python 3.12+
- `uv` (recommended) or a standard virtual environment

## Installation and run

```powershell
uv sync
uv run uvicorn mock_api_engine.main:app --app-dir src --reload
```

The app runs at `http://127.0.0.1:8000` by default.

The default storage directory is `data` relative to the current working directory. To override it:

```powershell
$env:MOCK_API_DATA_DIR = '.\data\records'
uv run uvicorn mock_api_engine.main:app --app-dir src --reload
```

You can also launch the packaged entry point after installation:

```powershell
mock-api-engine
```

## API endpoints

### `POST /data`

Creates a new generic JSON record.

Request body:

```json
{
  "customer": {
    "name": "Jane Doe"
  },
  "status": "active"
}
```

Response:

```json
{
  "status": "created",
  "id": "<uuid>",
  "data": {
    "customer": {
      "name": "Jane Doe"
    },
    "status": "active"
  }
}
```

This endpoint merges the supplied payload onto the static template in `data/static/template.json`, saves the result as `<id>.json`, and returns the generated ID plus the merged object.

### `GET /data`

Fetches stored data for a quotation or a static mock response.

Query parameters:

- `quotation_id` (required)
- `page_context` (optional)

Behavior:

- Without `page_context`, returns the stored quotation JSON for the given `quotation_id`.
- With `page_context`, looks up a mock response in `data/static/responses.json` using the `quotation_id` and `page_context` keys.

Example:

```http
GET /data?quotation_id=QTN-2026-001501
GET /data?quotation_id=REF-123&page_context=home
```

If a record or static response is missing, the API returns HTTP 404.

### `POST /create`

Creates and manages quotation records. The request body must include an `action` field.

#### `Init`

```json
{
  "action": "Init"
}
```

- Loads `data/static/New_Quote_Template.json`
- Generates a new `quotation_id` in the format `QTN-YYYY-######`
- Saves the quotation file under the configured data directory
- Returns the created quotation payload

#### `Save`

```json
{
  "action": "Save",
  "quotation_id": "QTN-2026-001501",
  "customer": {
    "name": "Jane Smith"
  }
}
```

- Finds the existing quotation by `quotation_id`
- Recursively merges the new fields over the stored record
- Saves the updated JSON back to disk
- Returns the updated quotation

#### `CALC`

```json
{
  "action": "CALC",
  "quotation_id": "QTN-2026-001501"
}
```

- Loads the target quotation
- Recalculates the `projection` field using basis data in the quotation
- Projects growth across low, mid, and high scenarios (2%, 5%, and 8%)
- Uses the customer date of birth, pension plan retirement age, contribution data, and transfer value to calculate outputs
- Saves the updated projected quotation

The projection logic is illustrative and includes a fixed 5% annuity conversion rate and a 25% tax-free cash assumption, without product charges or inflation adjustments.

#### `CLONE`

```json
{
  "action": "CLONE",
  "quotation_id": "QTN-2026-001501"
}
```

- Copies the specified quotation to a new record ID
- Sets `parent_quotation_id` on the new child quotation
- Persists parent/child links in `data/quotation_relationships.json`

### `GET /linked-quotes`

Returns the relationship data for a quotation.

```http
GET /linked-quotes?quotation_id=QTN-2026-001501
```

Example response:

```json
{
  "parent_quotation_id": "QTN-2026-001500",
  "child_quotation_ids": [
    "QTN-2026-001501",
    "QTN-2026-001502"
  ]
}
```

If the given quotation has no children, `child_quotation_ids` is an empty list.

## Storage behavior

- Records are persisted as JSON files in the configured data directory.
- Startup loads all JSON files from the directory so existing records are available immediately.
- Static content such as templates and response mappings is read from `data/static/`.
- Quotation parent/child links are stored in `data/quotation_relationships.json`.

## Notes

- The JSON repository is designed for a single application process.
- Multiple worker processes will each maintain their own in-memory relationship state and their own local copy of the file-backed store.
- The generic `POST /data` payload is intentionally flexible and not bound to a strict Pydantic request schema.
