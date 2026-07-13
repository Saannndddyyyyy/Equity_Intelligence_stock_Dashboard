from app.models.alert import Alert
from app.services.email_service import EmailService


def test_health_endpoint(client):
    """
    Checks that the health endpoint is responding.
    """
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_watchlist_crud(client):
    """
    Verifies adding, reading, updating, and deleting watchlist items.
    """
    # 1. Create
    payload = {
        "symbol": "TCS",
        "exchange": "NSE",
        "purchase_price": 3800.0,
        "quantity": 10,
        "average_cost": 3820.0,
        "target_price": 4500.0,
        "stop_loss": 3500.0,
        "purchase_date": "2026-07-13",
        "notes": "Premium IT major",
    }
    response = client.post("/api/watchlist", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "TCS"
    assert data["quantity"] == 10
    item_id = data["id"]

    # 2. Duplicate Check
    response_dup = client.post("/api/watchlist", json=payload)
    assert response_dup.status_code == 400

    # 3. Read
    response_get = client.get("/api/watchlist")
    assert response_get.status_code == 200
    assert len(response_get.json()) == 1
    assert response_get.json()[0]["symbol"] == "TCS"

    # 4. Update
    payload["quantity"] = 15
    response_put = client.put(f"/api/watchlist/{item_id}", json=payload)
    assert response_put.status_code == 200
    assert response_put.json()["quantity"] == 15

    # 5. Delete
    response_del = client.delete(f"/api/watchlist/{item_id}")
    assert response_del.status_code == 200

    response_get_empty = client.get("/api/watchlist")
    assert len(response_get_empty.json()) == 0


def test_download_template(client):
    """
    Checks that the excel template serves correctly.
    """
    response = client.get("/api/watchlist/download-template")
    assert response.status_code == 200
    assert (
        response.headers["content-type"]
        == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


def test_alert_deduplication(db):
    """
    Checks that alert hashes detect and suppress duplicate triggers.
    """
    email_service = EmailService(db)
    symbol = "RELIANCE"
    event_type = "PRICE_ALERT"
    date_str = "2026-07-13"

    alert_hash = email_service.generate_alert_hash(symbol, event_type, date_str)
    assert not email_service.is_duplicate_alert(alert_hash)

    # Save a mock alert to DB
    alert = Alert(
        symbol=symbol,
        event_type=event_type,
        severity="Medium",
        summary="Test price shift alert",
        alert_hash=alert_hash,
    )
    db.add(alert)
    db.commit()

    # Verify deduplicator flags duplicate
    assert email_service.is_duplicate_alert(alert_hash)
