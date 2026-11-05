"""
Tests for task and purchase order API endpoints, plus data-file encoding.
"""
import pytest

import main


@pytest.fixture(autouse=True)
def reset_state():
    """Tasks and purchase orders are module-level lists; restore them after each test.

    purchase_orders is seeded from purchase_orders.json, so it is snapshotted and
    restored rather than simply cleared.
    """
    saved_pos = list(main.purchase_orders)
    main.tasks.clear()
    main.task_counter = 0
    yield
    main.tasks.clear()
    main.task_counter = 0
    main.purchase_orders[:] = saved_pos


def first_backlog_item_id(client):
    items = client.get("/api/backlog").json()
    assert len(items) > 0
    return items[0]["id"]


def po_payload(backlog_item_id, **overrides):
    payload = {
        "backlog_item_id": backlog_item_id,
        "supplier_name": "Acme Supply",
        "quantity": 350,
        "unit_cost": 6.2,
        "expected_delivery_date": "2026-12-01",
        "notes": "Rush",
    }
    payload.update(overrides)
    return payload


class TestTaskEndpoints:
    """Test suite for task endpoints."""

    def test_get_tasks_empty(self, client):
        """Test that the task list starts empty."""
        response = client.get("/api/tasks")
        assert response.status_code == 200
        assert response.json() == []

    def test_create_task(self, client):
        """Test creating a task."""
        response = client.post(
            "/api/tasks", json={"title": "Count stock", "priority": "high", "dueDate": "2026-11-20"}
        )
        assert response.status_code == 201

        task = response.json()
        assert task["title"] == "Count stock"
        assert task["priority"] == "high"
        assert task["dueDate"] == "2026-11-20"
        assert task["status"] == "pending"
        assert isinstance(task["id"], str)

    def test_get_tasks_newest_first(self, client):
        """Test that tasks are listed newest first."""
        first = client.post("/api/tasks", json={"title": "A", "dueDate": "2026-11-20"}).json()
        second = client.post("/api/tasks", json={"title": "B", "dueDate": "2026-11-21"}).json()

        ids = [t["id"] for t in client.get("/api/tasks").json()]
        assert ids == [second["id"], first["id"]]

    def test_create_task_invalid_priority(self, client):
        """Test that an unknown priority is rejected."""
        response = client.post(
            "/api/tasks", json={"title": "X", "priority": "urgent", "dueDate": "2026-11-20"}
        )
        assert response.status_code == 422

    def test_create_task_empty_title(self, client):
        """Test that an empty title is rejected."""
        response = client.post("/api/tasks", json={"title": "", "dueDate": "2026-11-20"})
        assert response.status_code == 422

    def test_toggle_task(self, client):
        """Test toggling a task to completed and back."""
        task = client.post("/api/tasks", json={"title": "A", "dueDate": "2026-11-20"}).json()

        response = client.patch(f"/api/tasks/{task['id']}")
        assert response.status_code == 200
        assert response.json()["status"] == "completed"

        assert client.patch(f"/api/tasks/{task['id']}").json()["status"] == "pending"

    def test_delete_task(self, client):
        """Test deleting a task."""
        task = client.post("/api/tasks", json={"title": "A", "dueDate": "2026-11-20"}).json()

        response = client.delete(f"/api/tasks/{task['id']}")
        assert response.status_code == 200
        assert client.get("/api/tasks").json() == []

    def test_task_ids_unique_after_delete(self, client):
        """Test that a new task never reuses the id of a deleted one."""
        first = client.post("/api/tasks", json={"title": "A", "dueDate": "2026-11-20"}).json()
        client.delete(f"/api/tasks/{first['id']}")
        second = client.post("/api/tasks", json={"title": "B", "dueDate": "2026-11-20"}).json()
        assert second["id"] != first["id"]

    def test_nonexistent_task(self, client):
        """Test that toggling or deleting an unknown task returns 404."""
        assert client.patch("/api/tasks/task-999").status_code == 404
        response = client.delete("/api/tasks/task-999")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestPurchaseOrderEndpoints:
    """Test suite for purchase order endpoints."""

    def test_create_purchase_order(self, client):
        """Test creating a purchase order for a backlog item."""
        backlog_id = first_backlog_item_id(client)
        response = client.post("/api/purchase-orders", json=po_payload(backlog_id))
        assert response.status_code == 201

        po = response.json()
        assert po["backlog_item_id"] == backlog_id
        assert po["supplier_name"] == "Acme Supply"
        assert po["quantity"] == 350
        assert po["status"] == "Pending"
        assert po["id"].startswith("PO-")
        assert "T" in po["created_date"]

    def test_get_purchase_order_by_backlog_item(self, client):
        """Test fetching the PO created for a backlog item."""
        backlog_id = first_backlog_item_id(client)
        created = client.post("/api/purchase-orders", json=po_payload(backlog_id)).json()

        response = client.get(f"/api/purchase-orders/{backlog_id}")
        assert response.status_code == 200
        assert response.json()["id"] == created["id"]

    def test_backlog_reflects_purchase_order(self, client):
        """Test that the backlog marks items that have a PO."""
        backlog_id = first_backlog_item_id(client)
        before = {b["id"]: b for b in client.get("/api/backlog").json()}[backlog_id]
        assert before["has_purchase_order"] is False
        assert before["purchase_order_id"] is None

        created = client.post("/api/purchase-orders", json=po_payload(backlog_id)).json()

        after = {b["id"]: b for b in client.get("/api/backlog").json()}[backlog_id]
        assert after["has_purchase_order"] is True
        assert after["purchase_order_id"] == created["id"]

    def test_duplicate_purchase_order(self, client):
        """Test that a second PO for the same backlog item is rejected."""
        backlog_id = first_backlog_item_id(client)
        client.post("/api/purchase-orders", json=po_payload(backlog_id))
        response = client.post("/api/purchase-orders", json=po_payload(backlog_id))
        assert response.status_code == 409

    def test_purchase_order_unknown_backlog_item(self, client):
        """Test that a PO for an unknown backlog item returns 404."""
        response = client.post("/api/purchase-orders", json=po_payload("nonexistent-999"))
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_get_nonexistent_purchase_order(self, client):
        """Test that fetching a PO that doesn't exist returns 404."""
        backlog_id = first_backlog_item_id(client)
        response = client.get(f"/api/purchase-orders/{backlog_id}")
        assert response.status_code == 404

    @pytest.mark.parametrize(
        "overrides",
        [
            {"quantity": 0},
            {"unit_cost": 0},
            {"supplier_name": ""},
            {"expected_delivery_date": "12/01/2026"},
        ],
    )
    def test_purchase_order_validation(self, client, overrides):
        """Test that invalid PO fields are rejected."""
        backlog_id = first_backlog_item_id(client)
        response = client.post("/api/purchase-orders", json=po_payload(backlog_id, **overrides))
        assert response.status_code == 422


class TestDataEncoding:
    """Test that data files are decoded as UTF-8."""

    def test_non_ascii_names_decoded(self, client):
        """Test that the ± in PSU-504's name isn't mangled into mojibake."""
        items = {i["sku"]: i for i in client.get("/api/inventory").json()}
        name = items["PSU-504"]["name"]
        assert "±15V" in name
        assert "Â" not in name
