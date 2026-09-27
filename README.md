# Inventory Management System

An administrator inventory portal with a Flask REST API, an in-memory product database, OpenFoodFacts integration, and a command-line frontend.

## Design

The inventory is reset to two sample products whenever the Flask process restarts. Every item has a unique integer `id`. Prices must be non-negative numbers, and stock levels must be non-negative integers.

| Method | Route | Input | Output and effect | CLI trigger |
| --- | --- | --- | --- | --- |
| GET | `/inventory` | None | All items; no change | `list` |
| GET | `/inventory/<id>` | Integer path ID | One item or 404; no change | `get ID` |
| POST | `/inventory` | JSON product; `product_name` required | New item with generated ID; appends to array | `add NAME` |
| PATCH | `/inventory/<id>` | JSON containing name, price, or stock | Updated item; changes matching array entry | `update ID` |
| DELETE | `/inventory/<id>` | Integer path ID | Empty 204 response; removes matching entry | `delete ID` |
| GET | `/products/search` | `barcode` or `name` query parameter | OpenFoodFacts details; no inventory change | `find` |
| POST | `/inventory/import` | JSON barcode/name plus optional price/stock | OpenFoodFacts product with generated ID; appends to array | `import` |

## Setup

Python 3.12 and Pipenv are recommended.

```bash
git clone <repository-url>
cd Summative-Lab-Python-REST-API-with-Flask--Inventory-Management-System
python -m pip install pipenv
pipenv install --dev
pipenv run flask --app app run --debug
```

In another terminal, use `pipenv run python cli.py ...` to run CLI commands. The API defaults to `http://127.0.0.1:5000`; use `--api-url` before the command to choose another server.

## CLI Examples

```bash
pipenv run python cli.py list
pipenv run python cli.py get 1
pipenv run python cli.py add "Green Tea" --price 2.50 --stock 20 --brand "Tea Co"
pipenv run python cli.py update 1 --price 5.49 --stock 15
pipenv run python cli.py delete 2
pipenv run python cli.py find --barcode 737628064502
pipenv run python cli.py find --name "oat milk"
pipenv run python cli.py import --barcode 737628064502 --price 3.99 --stock 10
```

## Direct API Examples

```bash
curl http://127.0.0.1:5000/inventory
curl -X POST http://127.0.0.1:5000/inventory \
	-H "Content-Type: application/json" \
	-d '{"product_name":"Green Tea","price":2.5,"stock":20}'
curl -X PATCH http://127.0.0.1:5000/inventory/1 \
	-H "Content-Type: application/json" \
	-d '{"stock":15}'
curl -X DELETE http://127.0.0.1:5000/inventory/2
```

## Tests

The test suite mocks OpenFoodFacts, so it does not require network access.

```bash
pipenv run pytest -v
```

## Git Workflow

Develop each feature on a focused branch, commit it, push it, and merge it through a pull request. For example:

```bash
git switch -c feature/inventory-api
git add app.py test_app.py
git commit -m "Add inventory REST API"
git push -u origin feature/inventory-api
```

After the pull request is merged, update the main branch and delete the completed branch with `git branch -d feature/inventory-api`. Repository branches and pull requests must be created and merged in GitHub; they cannot be demonstrated by application code alone.
