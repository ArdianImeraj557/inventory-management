"""
Tests for restocking API endpoints.
"""
import pytest

import main


@pytest.fixture(autouse=True)
def clear_restocking_orders():
    """Restocking orders are module-level state; reset them so tests stay independent."""
    main.restocking_orders.clear()
    yield
    main.restocking_orders.clear()


class TestRestockingEndpoints:
    """Test suite for restocking-related endpoints."""

    def test_demand_forecasts_have_pricing_and_lead_time(self, client):
        """Test that every forecast has the fields restocking depends on."""
        response = client.get("/api/demand")
        assert response.status_code == 200

        for forecast in response.json():
            assert isinstance(forecast["unit_cost"], (int, float))
            assert forecast["unit_cost"] > 0
            assert isinstance(forecast["lead_time_days"], int)
            assert forecast["lead_time_days"] > 0

    def test_get_restocking_orders_empty(self, client):
        """Test that no restocking orders exist before any are submitted."""
        response = client.get("/api/restocking-orders")
        assert response.status_code == 200
        assert response.json() == []

    def test_create_restocking_order(self, client):
        """Test submitting a valid restocking order."""
        payload = {
            "budget": 5000,
            "items": [
                {"item_sku": "WDG-001", "quantity": 100},  # 12.50, 7 days
                {"item_sku": "BRG-102", "quantity": 2},    # 45.00, 14 days
            ],
        }
        response = client.post("/api/restocking-orders", json=payload)
        assert response.status_code == 201

        order = response.json()
        assert order["status"] == "Submitted"
        assert order["order_number"].startswith("RST-")
        assert order["budget"] == 5000
        assert len(order["items"]) == 2
        assert "T" in order["submitted_date"]
        assert "T" in order["expected_delivery"]

    def test_restocking_order_total_calculation(self, client):
        """Test that totals are computed from server-side prices."""
        demand = {f["item_sku"]: f for f in client.get("/api/demand").json()}
        payload = {
            "budget": 10000,
            "items": [
                {"item_sku": "GSK-203", "quantity": 40},
                {"item_sku": "FLT-405", "quantity": 25},
            ],
        }
        order = client.post("/api/restocking-orders", json=payload).json()

        expected_total = sum(
            line["quantity"] * demand[line["item_sku"]]["unit_cost"]
            for line in payload["items"]
        )
        assert abs(order["total_cost"] - expected_total) < 0.01

        for item in order["items"]:
            assert item["unit_cost"] == demand[item["sku"]]["unit_cost"]
            assert abs(item["line_total"] - item["quantity"] * item["unit_cost"]) < 0.01

    def test_restocking_order_lead_time_is_max_of_items(self, client):
        """Test that order lead time equals the slowest item's lead time."""
        payload = {
            "budget": 10000,
            "items": [
                {"item_sku": "FLT-405", "quantity": 10},  # 5 days
                {"item_sku": "CTL-330", "quantity": 1},   # 18 days
                {"item_sku": "PSU-501", "quantity": 5},   # 7 days
            ],
        }
        order = client.post("/api/restocking-orders", json=payload).json()

        assert order["lead_time_days"] == max(i["lead_time_days"] for i in order["items"])
        assert order["lead_time_days"] == 18

    def test_restocking_order_over_budget(self, client):
        """Test that an order exceeding the budget is rejected."""
        payload = {"budget": 100, "items": [{"item_sku": "MTR-304", "quantity": 1}]}  # 420.00
        response = client.post("/api/restocking-orders", json=payload)
        assert response.status_code == 422
        assert "exceeds budget" in response.json()["detail"].lower()
        assert client.get("/api/restocking-orders").json() == []

    def test_restocking_order_exactly_at_budget(self, client):
        """Test that an order whose total equals the budget is accepted."""
        payload = {"budget": 132.93, "items": [{"item_sku": "PSU-501", "quantity": 7}]}  # 7 x 18.99
        response = client.post("/api/restocking-orders", json=payload)
        assert response.status_code == 201
        assert response.json()["total_cost"] == 132.93

    def test_restocking_order_one_cent_over_budget(self, client):
        """Test that exceeding the budget by a single cent is rejected."""
        payload = {"budget": 132.92, "items": [{"item_sku": "PSU-501", "quantity": 7}]}
        response = client.post("/api/restocking-orders", json=payload)
        assert response.status_code == 422

    def test_restocking_order_duplicate_sku(self, client):
        """Test that the same SKU listed twice is rejected."""
        payload = {
            "budget": 1000,
            "items": [
                {"item_sku": "WDG-001", "quantity": 1},
                {"item_sku": "WDG-001", "quantity": 2},
            ],
        }
        response = client.post("/api/restocking-orders", json=payload)
        assert response.status_code == 422
        assert "duplicate" in response.json()["detail"].lower()

    def test_restocking_order_unknown_sku(self, client):
        """Test that an unknown SKU is rejected."""
        payload = {"budget": 1000, "items": [{"item_sku": "NOPE-999", "quantity": 1}]}
        response = client.post("/api/restocking-orders", json=payload)
        assert response.status_code == 422
        assert "unknown" in response.json()["detail"].lower()

    def test_restocking_order_empty_items(self, client):
        """Test that an order with no items is rejected."""
        response = client.post("/api/restocking-orders", json={"budget": 1000, "items": []})
        assert response.status_code == 422

    def test_restocking_order_non_positive_quantity(self, client):
        """Test that zero quantities are rejected by validation."""
        payload = {"budget": 1000, "items": [{"item_sku": "WDG-001", "quantity": 0}]}
        response = client.post("/api/restocking-orders", json=payload)
        assert response.status_code == 422

    def test_get_restocking_orders_newest_first(self, client):
        """Test that submitted orders are listed newest first."""
        first = client.post(
            "/api/restocking-orders",
            json={"budget": 1000, "items": [{"item_sku": "WDG-001", "quantity": 1}]},
        ).json()
        second = client.post(
            "/api/restocking-orders",
            json={"budget": 1000, "items": [{"item_sku": "BRG-102", "quantity": 1}]},
        ).json()

        orders = client.get("/api/restocking-orders").json()
        assert [o["order_number"] for o in orders] == [second["order_number"], first["order_number"]]

    def test_restocking_orders_not_in_customer_orders(self, client):
        """Test that restocking orders don't change customer order data."""
        before = len(client.get("/api/orders").json())
        client.post(
            "/api/restocking-orders",
            json={"budget": 1000, "items": [{"item_sku": "WDG-001", "quantity": 1}]},
        )
        assert len(client.get("/api/orders").json()) == before
