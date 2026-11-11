PASSWORD = "TestPassword123"


def test_register_returns_a_customer_without_any_password_data(client):
    response = client.post(
        "/users",
        json={"email": "a@example.com", "password": PASSWORD, "full_name": "A"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["role"] == "customer"
    assert body["timezone"] == "UTC"
    assert "password" not in body and "hashed_password" not in body


def test_duplicate_email_is_rejected_ignoring_case(client):
    first = client.post(
        "/users",
        json={"email": "Bob@Example.com", "password": PASSWORD, "full_name": "Bob"},
    )
    second = client.post(
        "/users",
        json={"email": "bob@example.com", "password": PASSWORD, "full_name": "Bob"},
    )
    assert first.status_code == 201
    assert first.json()["email"] == "bob@example.com"  # stored lowercase
    assert second.status_code == 409


def test_registration_cannot_choose_a_role(client):
    response = client.post(
        "/users",
        json={
            "email": "sneaky@example.com",
            "password": PASSWORD,
            "full_name": "Sneaky",
            "role": "admin",
        },
    )
    assert response.status_code == 201
    assert response.json()["role"] == "customer"


def test_login_then_me(client, make_account):
    account = make_account("a@example.com")
    response = client.get("/users/me", headers=account.headers)
    assert response.status_code == 200
    assert response.json()["email"] == "a@example.com"


def test_wrong_password_and_unknown_email_look_identical(client, make_account):
    make_account("a@example.com")
    wrong_password = client.post(
        "/auth/login", data={"username": "a@example.com", "password": "not-the-one"}
    )
    unknown_email = client.post(
        "/auth/login", data={"username": "nobody@example.com", "password": PASSWORD}
    )
    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json()


def test_user_can_update_their_own_timezone(client, make_account):
    account = make_account("a@example.com")
    patch = client.patch(
        "/users/me", json={"timezone": "Asia/Tokyo"}, headers=account.headers
    )
    assert patch.status_code == 200
    assert client.get("/users/me", headers=account.headers).json()["timezone"] == "Asia/Tokyo"
