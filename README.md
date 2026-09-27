# Mock API Engine

## Application Structure

- `api/controllers` handles HTTP routes, request/response models, and HTTP errors.
- `services` contains application use cases and business rules.
- `models` defines validated request, record, and response types.
- `repositories` owns the in-memory cache and per-record JSON persistence.
- `core` contains application configuration.

## Run

Install the project and start the API with `mock-api-engine`, or run it in development mode:

```powershell
uv sync
uv run uvicorn mock_api_engine.main:app --app-dir src --reload
```

The API listens on `http://127.0.0.1:8000`. Records are stored as individual `<id>.json` files in the `data` directory by default. Set `MOCK_API_DATA_DIR` to choose a different location before startup:

```powershell
$env:MOCK_API_DATA_DIR = '.\data\records'
uv run uvicorn mock_api_engine.main:app --app-dir src --reload
```

`POST /data` accepts any JSON object, recursively merges it over `data/static/template.json`, and saves the result as a new JSON file in the data directory. Request values override template values; object properties not supplied in the request are retained. The response includes the generated record ID and merged data.

`GET /data` requires `quotation_id`. With no `page_context`, it returns the saved quotation JSON. When `page_context` is supplied, it looks up a static response in `data/static/responses.json` using `quotation_id` and `page_context` as keys. Each value can be any JSON response. For example:

```json
{
	"REF-123": {
		"home": { "message": "Static mock response" }
	}
}
```

Missing quotations or lookup keys return 404. Edit these static JSON files to change the template or lookup responses without changing application code. This local JSON repository is intended for a single application process.

`GET /linked-quotes?quotation_id=<id>` returns the quotation's parent ID and all child quotation IDs. The supplied ID may refer to either the parent or one of its children. A valid quotation with no children returns an empty `child_quotation_ids` list.

`POST /create` uses the request's `action` field:

- `{"action": "Init"}` clones `data/static/New_Quote_Template.json`, assigns a new `quotation_id`, saves it in the `data` directory, and returns the new quotation.
- `{"action": "Save", "quotation_id": "<id>", ...}` loads that quotation, recursively merges the request fields (new values replace existing values), saves the updated JSON, and returns it. The quotation ID must already exist.
- `{"action": "CALC", "quotation_id": "<id>"}` recalculates and saves the quotation projection. CALC uses gross annual growth scenarios of 2%, 5%, and 8%, projects from the customer's date of birth to the plan's retirement age, and applies a fixed 5% annuity conversion rate. Tax-free cash is illustrated as 25% without an allowance cap. Results are illustrative, with no product-charge or inflation adjustment.
- `{"action": "CLONE", "quotation_id": "<id>"}` copies the existing quotation to a new quotation ID and sets `parent_quotation_id` to the source ID. Parent-to-child links are held in memory and persisted in `data/quotation_relationships.json`; each parent can have multiple children.

Request fields other than `action` and `quotation_id` are handled as arbitrary JSON for `Save`. CALC uses the quotation's `customer.date_of_birth`, `customer.annual_salary_gbp` when percentage-only contributions are supplied, `pension_plan.retirement_age`, `pension_plan.contributions`, and `transfer.transfer_value_gbp` as its calculation inputs.
# Mock API Engine

Records are kept in the in-memory store and persisted as individual JSON files. On startup, the API loads every `*.json` record from the storage directory; each successful `POST /data` writes a file named `<id>.json` before updating memory.

POST request and template structures are not tied to a Pydantic request model. Existing JSON records remain readable as arbitrary JSON objects.

By default, files are stored in the `data` directory under the process working directory. Set `MOCK_API_DATA_DIR` to use another directory. For example, in PowerShell:

```powershell
$env:MOCK_API_DATA_DIR = '.\data\records'
python -m uvicorn mock_api_engine.main:app --app-dir src
```

This file-backed store is intended for a single application process. Multiple worker processes would each maintain a separate in-memory store.
