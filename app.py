from copy import deepcopy

import requests
from flask import Flask, jsonify, request


# This URL is the starting point for every OpenFoodFacts request.
OPENFOODFACTS_BASE_URL = "https://world.openfoodfacts.org"

# This list acts as a temporary database. It resets each time the app restarts.
INITIAL_INVENTORY = [
    {
        "id": 1,
        "product_name": "Organic Almond Milk",
        "brands": "Silk",
        "barcode": "0025293000729",
        "ingredients_text": "Filtered water, almonds, cane sugar",
        "price": 4.99,
        "stock": 12,
    },
    {
        "id": 2,
        "product_name": "Crunchy Peanut Butter",
        "brands": "365 Everyday Value",
        "barcode": "0099482457552",
        "ingredients_text": "Dry roasted peanuts, salt",
        "price": 3.79,
        "stock": 8,
    },
]


# A custom exception lets the routes identify errors from the external API.
class ProductLookupError(Exception):
    pass


def fetch_openfoodfacts_product(barcode=None, name=None):
    # OpenFoodFacts asks clients to identify their application with a User-Agent.
    headers = {"User-Agent": "InventoryManagementStudentProject/1.0"}
    try:
        if barcode:
            # A barcode identifies one product, so it can be included in the URL.
            response = requests.get(
                f"{OPENFOODFACTS_BASE_URL}/api/v2/product/{barcode}.json",
                headers=headers,
                timeout=10,
            )
            response.raise_for_status()
            payload = response.json()
            product = payload.get("product") if payload.get("status") == 1 else None
        elif name:
            # Name searches use query parameters and may return several products.
            response = requests.get(
                f"{OPENFOODFACTS_BASE_URL}/cgi/search.pl",
                params={
                    "search_terms": name,
                    "search_simple": 1,
                    "action": "process",
                    "json": 1,
                    "page_size": 1,
                },
                headers=headers,
                timeout=10,
            )
            response.raise_for_status()
            products = response.json().get("products", [])
            # This project uses the first search result when at least one exists.
            product = products[0] if products else None
        else:
            raise ProductLookupError("Provide a barcode or name")
    except requests.RequestException as error:
        raise ProductLookupError("OpenFoodFacts is currently unavailable") from error
    except ValueError as error:
        raise ProductLookupError("OpenFoodFacts returned invalid data") from error

    if not product:
        return None

    # Keep a small, consistent set of fields instead of saving the entire API response.
    return {
        "barcode": str(product.get("code") or barcode or ""),
        "product_name": product.get("product_name") or product.get("product_name_en") or name,
        "brands": product.get("brands", ""),
        "ingredients_text": product.get("ingredients_text", ""),
        "image_url": product.get("image_front_small_url") or product.get("image_url", ""),
        "categories": product.get("categories", ""),
    }


def validate_inventory_fields(data, partial=False):
    # Collect every validation problem so the client can fix them together.
    errors = {}

    # PATCH requests are partial, so they do not need to include a product name.
    if not partial and not data.get("product_name"):
        errors["product_name"] = "Product name is required"

    if "product_name" in data and (
        not isinstance(data["product_name"], str) or not data["product_name"].strip()
    ):
        errors["product_name"] = "Product name must be a non-empty string"

    if "price" in data:
        if isinstance(data["price"], bool) or not isinstance(data["price"], (int, float)):
            errors["price"] = "Price must be a number"
        elif data["price"] < 0:
            errors["price"] = "Price cannot be negative"

    if "stock" in data:
        if isinstance(data["stock"], bool) or not isinstance(data["stock"], int):
            errors["stock"] = "Stock must be an integer"
        elif data["stock"] < 0:
            errors["stock"] = "Stock cannot be negative"

    return errors


def create_app(test_config=None):
    # The application factory creates a fresh Flask app and inventory for each test/run.
    app = Flask(__name__)
    app.config.from_mapping(
        # deepcopy prevents changes from modifying the original starter list.
        INVENTORY=deepcopy(INITIAL_INVENTORY),
        PRODUCT_LOOKUP=fetch_openfoodfacts_product,
    )
    if test_config:
        # Tests can replace settings, including the real external API function.
        app.config.update(test_config)

    def find_item(item_id):
        # next returns the first matching item, or None when no ID matches.
        return next(
            (item for item in app.config["INVENTORY"] if item["id"] == item_id),
            None,
        )

    # Route decorators connect an HTTP method and URL to the function below it.
    @app.get("/inventory")
    def get_inventory():
        return jsonify(app.config["INVENTORY"])

    @app.get("/inventory/<int:item_id>")
    def get_inventory_item(item_id):
        item = find_item(item_id)
        if item is None:
            return jsonify(error="Inventory item not found"), 404
        return jsonify(item)

    @app.post("/inventory")
    def create_inventory_item():
        # silent=True returns None instead of raising an error for invalid JSON.
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify(error="A JSON object is required"), 400

        errors = validate_inventory_fields(data)
        if errors:
            return jsonify(errors=errors), 400

        allowed_fields = {
            "product_name",
            "brands",
            "barcode",
            "ingredients_text",
            "image_url",
            "categories",
            "price",
            "stock",
        }
        # Ignore unexpected fields so clients cannot choose their own IDs.
        item = {key: value for key, value in data.items() if key in allowed_fields}
        # The next ID is one greater than the largest existing ID.
        item["id"] = max((entry["id"] for entry in app.config["INVENTORY"]), default=0) + 1
        item.setdefault("price", 0.0)
        item.setdefault("stock", 0)
        app.config["INVENTORY"].append(item)
        return jsonify(item), 201

    @app.patch("/inventory/<int:item_id>")
    def update_inventory_item(item_id):
        item = find_item(item_id)
        if item is None:
            return jsonify(error="Inventory item not found"), 404

        data = request.get_json(silent=True)
        if not isinstance(data, dict) or not data:
            return jsonify(error="A non-empty JSON object is required"), 400

        allowed_fields = {"product_name", "price", "stock"}
        # Set subtraction finds submitted fields that are not allowed here.
        unknown_fields = set(data) - allowed_fields
        if unknown_fields:
            return jsonify(error=f"Fields cannot be updated: {', '.join(sorted(unknown_fields))}"), 400

        errors = validate_inventory_fields(data, partial=True)
        if errors:
            return jsonify(errors=errors), 400

        item.update(data)
        return jsonify(item)

    @app.delete("/inventory/<int:item_id>")
    def delete_inventory_item(item_id):
        item = find_item(item_id)
        if item is None:
            return jsonify(error="Inventory item not found"), 404
        app.config["INVENTORY"].remove(item)
        return "", 204

    @app.get("/products/search")
    def search_products():
        # Query parameters come from URLs such as ?barcode=123 or ?name=milk.
        barcode = request.args.get("barcode")
        name = request.args.get("name")
        if not barcode and not name:
            return jsonify(error="Provide a barcode or name"), 400
        try:
            product = app.config["PRODUCT_LOOKUP"](barcode=barcode, name=name)
        except ProductLookupError as error:
            return jsonify(error=str(error)), 502
        if product is None:
            return jsonify(error="Product not found"), 404
        return jsonify(product)

    @app.post("/inventory/import")
    def import_inventory_item():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify(error="A JSON object is required"), 400
        if not data.get("barcode") and not data.get("name"):
            return jsonify(error="Provide a barcode or name"), 400

        try:
            product = app.config["PRODUCT_LOOKUP"](
                barcode=data.get("barcode"), name=data.get("name")
            )
        except ProductLookupError as error:
            return jsonify(error=str(error)), 502
        if product is None:
            return jsonify(error="Product not found"), 404

        # Add local inventory values to the product returned by OpenFoodFacts.
        product.update(price=data.get("price", 0.0), stock=data.get("stock", 0))
        errors = validate_inventory_fields(product)
        if errors:
            return jsonify(errors=errors), 400
        product["id"] = max(
            (entry["id"] for entry in app.config["INVENTORY"]), default=0
        ) + 1
        app.config["INVENTORY"].append(product)
        return jsonify(product), 201

    return app


# Flask's command-line tool imports this ready-to-run application object.
app = create_app()


# This block runs only when app.py is executed directly with Python.
if __name__ == "__main__":
    app.run(debug=True)