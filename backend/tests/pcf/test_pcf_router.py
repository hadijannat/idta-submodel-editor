"""
Tests for PCF API router endpoints.
TDD: Tests written first.
"""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    """Create test client with PCF router."""
    from fastapi import FastAPI
    from app.routers.pcf import router

    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as test_client:
        yield test_client


def test_calculate_endpoint_success(client):
    """POST /api/pcf/calculate returns calculated CO2e."""
    response = client.post(
        "/api/pcf/calculate",
        json={
            "activities": [
                {
                    "id": "act-001",
                    "name": "Electricity",
                    "category": "scope2",
                    "quantity": 1000.0,
                    "unit": "kWh",
                    "factor_value": 0.42,
                    "factor_unit": "kg CO2e/kWh",
                }
            ]
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total_co2e_kg"] == pytest.approx(420.0)
    assert len(data["activities"]) == 1
    assert data["activities"][0]["co2e_kg"] == pytest.approx(420.0)


def test_calculate_endpoint_multiple_activities(client):
    """POST /api/pcf/calculate handles multiple activities."""
    response = client.post(
        "/api/pcf/calculate",
        json={
            "activities": [
                {
                    "id": "a1",
                    "name": "Energy",
                    "category": "scope2",
                    "quantity": 100,
                    "unit": "kWh",
                    "factor_value": 0.5,
                    "factor_unit": "kg CO2e/kWh",
                },
                {
                    "id": "a2",
                    "name": "Transport",
                    "category": "scope3",
                    "quantity": 200,
                    "unit": "km",
                    "factor_value": 0.1,
                    "factor_unit": "kg CO2e/km",
                },
            ]
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total_co2e_kg"] == pytest.approx(70.0)  # 50 + 20


def test_calculate_endpoint_empty_activities(client):
    """POST /api/pcf/calculate with empty list returns zero."""
    response = client.post(
        "/api/pcf/calculate",
        json={"activities": []},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total_co2e_kg"] == 0.0
    assert data["activities"] == []


def test_calculate_endpoint_invalid_category(client):
    """POST /api/pcf/calculate rejects invalid category."""
    response = client.post(
        "/api/pcf/calculate",
        json={
            "activities": [
                {
                    "id": "bad",
                    "name": "Invalid",
                    "category": "scope4",  # Invalid
                    "quantity": 100,
                    "unit": "kg",
                    "factor_value": 1.0,
                    "factor_unit": "kg CO2e/kg",
                }
            ]
        },
    )

    assert response.status_code == 422  # Validation error
    data = response.json()
    assert "detail" in data
    assert any(
        error["loc"][-1] == "category" and error["type"] == "literal_error"
        for error in data["detail"]
    )


def test_calculate_endpoint_missing_required_field(client):
    """POST /api/pcf/calculate requires all fields."""
    response = client.post(
        "/api/pcf/calculate",
        json={
            "activities": [
                {
                    "id": "incomplete",
                    "name": "Missing quantity",
                    "category": "scope1",
                    # Missing: quantity, unit, factor_value, factor_unit
                }
            ]
        },
    )

    assert response.status_code == 422
    data = response.json()
    assert "detail" in data
    missing_fields = {error["loc"][-1] for error in data["detail"]}
    assert {"quantity", "unit", "factor_value", "factor_unit"} <= missing_fields


def test_validate_endpoint_structure(client):
    """POST /api/pcf/validate returns validation structure."""
    response = client.post(
        "/api/pcf/validate",
        json={
            "form_data": {"elements": {}},
            "template_schema": {"elements": []},
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert "valid" in data
    assert "errors" in data
    assert "warnings" in data
    assert "completeness_score" in data


def test_validate_endpoint_missing_required_pcf_field(client):
    """POST /api/pcf/validate flags missing PcfCO2eq as error."""
    # This validates that the PCF validator is wired up
    # Detailed validation logic is tested in test_pcf_validator.py
    response = client.post(
        "/api/pcf/validate",
        json={
            "form_data": {"elements": {}},
            "template_schema": {
                "elements": [
                    {
                        "idShort": "PcfCO2eq",
                        "modelType": "Property",
                        "cardinality": "[1]",
                        "semanticId": {
                            "keys": [{"value": "0173-1#02-ABG855#003"}]
                        },
                    }
                ]
            },
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is False
    assert len(data["errors"]) >= 1


def test_health_check(client):
    """GET /api/pcf/health returns service status."""
    response = client.get("/api/pcf/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "calculator" in data["services"]
    assert "validator" in data["services"]
    assert "factors" in data["services"]
    assert "factors" in data
    assert "version" in data["factors"]
