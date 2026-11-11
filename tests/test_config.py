from app.config import Settings


def make(url: str) -> Settings:
    return Settings(database_url=url, secret_key="x" * 40)


def test_plain_postgresql_url_gets_the_psycopg_driver():
    assert (
        make("postgresql://user:pw@host/db?sslmode=require").database_url
        == "postgresql+psycopg://user:pw@host/db?sslmode=require"
    )


def test_postgres_scheme_is_accepted_too():
    assert make("postgres://user:pw@host/db").database_url == "postgresql+psycopg://user:pw@host/db"


def test_a_url_that_already_names_a_driver_is_left_alone():
    url = "postgresql+psycopg://user:pw@host/db"
    assert make(url).database_url == url
