from app.models.user import UserRole


def create_business(client, headers, name="Test Salon", timezone="America/Boise"):
    response = client.post(
        "/businesses", json={"name": name, "timezone": timezone}, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_service(client, headers, business_id, name="Haircut", duration=60):
    response = client.post(
        f"/businesses/{business_id}/services",
        json={"name": name, "duration_minutes": duration, "price_cents": 2500},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


# --- Businesses ---------------------------------------------------------------

def test_creating_a_business_promotes_a_customer_to_owner(client, make_account):
    owner = make_account("owner@example.com")
    assert client.get("/users/me", headers=owner.headers).json()["role"] == "customer"

    business = create_business(client, owner.headers)

    assert business["owner_id"] == owner.id
    assert client.get("/users/me", headers=owner.headers).json()["role"] == "business_owner"


def test_business_list_is_public_and_paginated(client, make_account):
    owner = make_account("owner@example.com")
    for name in ("One", "Two", "Three"):
        create_business(client, owner.headers, name=name)

    assert len(client.get("/businesses").json()) == 3
    assert len(client.get("/businesses?limit=2").json()) == 2
    page_two = client.get("/businesses?limit=2&offset=2").json()
    assert [b["name"] for b in page_two] == ["Three"]
    assert client.get("/businesses?limit=0").status_code == 422


def test_unknown_business_is_404(client):
    assert client.get("/businesses/999").status_code == 404


def test_customer_fails_the_role_check(client, make_account):
    owner = make_account("owner@example.com")
    customer = make_account("customer@example.com")
    business = create_business(client, owner.headers)

    response = client.patch(
        f"/businesses/{business['id']}", json={"name": "Hacked"}, headers=customer.headers
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "You do not have permission to do this"


def test_other_owner_fails_the_ownership_check(client, make_account):
    owner = make_account("owner@example.com")
    rival = make_account("rival@example.com")
    business = create_business(client, owner.headers)
    create_business(client, rival.headers, name="Rival Shop")  # rival becomes an owner too

    response = client.patch(
        f"/businesses/{business['id']}", json={"name": "Hacked"}, headers=rival.headers
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "You do not own this business"


def test_admin_can_edit_any_business(client, make_account):
    owner = make_account("owner@example.com")
    admin = make_account("admin@example.com", role=UserRole.ADMIN)
    business = create_business(client, owner.headers)

    response = client.patch(
        f"/businesses/{business['id']}", json={"name": "Renamed"}, headers=admin.headers
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Renamed"


def test_owner_can_edit_and_delete(client, make_account):
    owner = make_account("owner@example.com")
    business = create_business(client, owner.headers)
    url = f"/businesses/{business['id']}"

    edited = client.patch(url, json={"description": "Cuts and color"}, headers=owner.headers)
    assert edited.json()["description"] == "Cuts and color"
    assert edited.json()["name"] == "Test Salon"  # untouched fields stay

    assert client.delete(url, headers=owner.headers).status_code == 204
    assert client.get(url).status_code == 404


# --- Services -----------------------------------------------------------------

def test_service_lifecycle_with_soft_delete(client, make_account):
    owner = make_account("owner@example.com")
    business = create_business(client, owner.headers)
    other_business = create_business(client, owner.headers, name="Second Shop")
    service = create_service(client, owner.headers, business["id"])

    # The same name twice in one business is a conflict, but fine in another.
    duplicate = client.post(
        f"/businesses/{business['id']}/services",
        json={"name": "Haircut", "duration_minutes": 30, "price_cents": 100},
        headers=owner.headers,
    )
    assert duplicate.status_code == 409
    create_service(client, owner.headers, other_business["id"])

    listing = client.get(f"/businesses/{business['id']}/services").json()
    assert [s["id"] for s in listing] == [service["id"]]

    # Deactivating hides it from the public list, but it still exists.
    deactivated = client.patch(
        f"/services/{service['id']}", json={"is_active": False}, headers=owner.headers
    )
    assert deactivated.status_code == 200
    assert client.get(f"/businesses/{business['id']}/services").json() == []
    assert client.get(f"/services/{service['id']}").json()["is_active"] is False


def test_service_validation(client, make_account):
    owner = make_account("owner@example.com")
    business = create_business(client, owner.headers)
    response = client.post(
        f"/businesses/{business['id']}/services",
        json={"name": "Bad", "duration_minutes": 30, "price_cents": -1},
        headers=owner.headers,
    )
    assert response.status_code == 422


def test_only_the_owner_can_add_services(client, make_account):
    owner = make_account("owner@example.com")
    rival = make_account("rival@example.com")
    business = create_business(client, owner.headers)
    create_business(client, rival.headers, name="Rival Shop")

    response = client.post(
        f"/businesses/{business['id']}/services",
        json={"name": "Haircut", "duration_minutes": 30, "price_cents": 100},
        headers=rival.headers,
    )
    assert response.status_code == 403


def test_deleting_a_business_deletes_its_services(client, make_account):
    owner = make_account("owner@example.com")
    business = create_business(client, owner.headers)
    service = create_service(client, owner.headers, business["id"])

    client.delete(f"/businesses/{business['id']}", headers=owner.headers)
    assert client.get(f"/services/{service['id']}").status_code == 404
