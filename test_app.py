from unittest.mock import Mock

import pytest
import requests

import app as app_module
from app import ProductLookupError, create_app, fetch_openfoodfacts_product


@pytest.fixture
def sample_product():
    return {
        "barcode": "123456789",
        "product_name": "Test Granola",
        "brands": "Test Foods",
        "ingredients_text": "Oats, honey",
        "image_url": "https://example.com/granola.jpg",
        "categories": "Breakfasts",
    }


@pytest.fixture
def client(sample_product):
    flask_app = create_app(
        {
            "TESTING": True,
            "PRODUCT_LOOKUP": lambda barcode=None, name=None: sample_product.copy(),
        }
    )
    return flask_app.test_client()


def test_get_inventory(client):
    response = client.get("/inventory")
    assert response.status_code == 200
    assert len(response.get_json()) == 2


def test_get_single_inventory_item(client):
    response = client.get("/inventory/1")
    assert response.status_code == 200
    assert response.get_json()["product_name"] == "Organic Almond Milk"


def test_get_missing_inventory_item(client):
    assert client.get("/inventory/999").status_code == 404


def test_create_inventory_item(client):
    response = client.post(
        "/inventory",
        json={"product_name": "Green Tea", "price": 2.5, "stock": 20},
    )
    assert response.status_code == 201
    assert response.get_json()["id"] == 3
    assert len(client.get("/inventory").get_json()) == 3


@pytest.mark.parametrize(
    "payload",
    [{}, {"product_name": "Tea", "price": -1}, {"product_name": "Tea", "stock": 2.5}],
)
def test_create_rejects_invalid_data(client, payload):
    assert client.post("/inventory", json=payload).status_code == 400


def test_patch_inventory_item(client):
    response = client.patch("/inventory/1", json={"price": 5.49, "stock": 15})
    assert response.status_code == 200
    assert response.get_json()["price"] == 5.49
    assert response.get_json()["stock"] == 15


def test_patch_rejects_unknown_fields(client):
    response = client.patch("/inventory/1", json={"id": 100})
    assert response.status_code == 400
    assert "id" in response.get_json()["error"]


def test_delete_inventory_item(client):
    response = client.delete("/inventory/2")
    assert response.status_code == 204
    assert client.get("/inventory/2").status_code == 404


def test_search_external_product(client, sample_product):
    response = client.get("/products/search?barcode=123456789")
    assert response.status_code == 200
    assert response.get_json() == sample_product


def test_search_requires_query(client):
    assert client.get("/products/search").status_code == 400


def test_import_external_product(client):
    response = client.post(
        "/inventory/import",
        json={"name": "Test Granola", "price": 6.25, "stock": 4},
    )
    assert response.status_code == 201
    assert response.get_json()["id"] == 3
    assert response.get_json()["stock"] == 4


def test_external_lookup_failure_returns_502():
    def failing_lookup(**_kwargs):
        raise ProductLookupError("Service unavailable")

    client = create_app({"TESTING": True, "PRODUCT_LOOKUP": failing_lookup}).test_client()
    assert client.get("/products/search?name=granola").status_code == 502


def test_fetch_product_by_barcode(monkeypatch):
    response = Mock()
    response.json.return_value = {
        "status": 1,
        "product": {"code": "123", "product_name": "Granola", "brands": "Acme"},
    }
    response.raise_for_status.return_value = None
    monkeypatch.setattr(app_module.requests, "get", Mock(return_value=response))

    product = fetch_openfoodfacts_product(barcode="123")
    assert product["product_name"] == "Granola"
    assert product["barcode"] == "123"


def test_fetch_product_by_name(monkeypatch):
    response = Mock()
    response.json.return_value = {"products": [{"code": "456", "product_name": "Oat Bar"}]}
    response.raise_for_status.return_value = None
    request_mock = Mock(return_value=response)
    monkeypatch.setattr(app_module.requests, "get", request_mock)

    product = fetch_openfoodfacts_product(name="oat bar")
    assert product["product_name"] == "Oat Bar"
    assert request_mock.call_args.kwargs["params"]["search_terms"] == "oat bar"


def test_fetch_product_handles_network_error(monkeypatch):
    monkeypatch.setattr(
        app_module.requests,
        "get",
        Mock(side_effect=requests.RequestException("network error")),
    )
    with pytest.raises(ProductLookupError, match="unavailable"):
        fetch_openfoodfacts_product(barcode="123")