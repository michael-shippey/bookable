# Bookable
[![CI](https://github.com/michael-shippey/bookable/actions/workflows/ci.yml/badge.svg)](https://github.com/michael-shippey/bookable/actions/workflows/ci.yml)

A booking/reservation REST API built with FastAPI and PostgreSQL.

## Run it

    docker compose up --build

- API docs: http://localhost:8000/docs
- Health check: http://localhost:8000/health
- DB check: http://localhost:8000/health/db

## Run tests

    docker compose run --rm api pytest
