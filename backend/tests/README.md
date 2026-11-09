# Backend tests

* `tests/unit/` — pure logic (upload safety gate, tokens, storage). No services needed.
* `tests/integration/` — the real API against PostgreSQL and Redis. The schema is built
  with the real Alembic migrations on every run, so migrations are tested too.

Defaults: `postgresql+asyncpg://akshara@localhost:5432/akshara_test` and Redis db 15.
Override with `AKSHARA_TEST_DATABASE_URL` / `AKSHARA_TEST_REDIS_URL`. Create the test database
once before the first run (`createdb -O akshara akshara_test`). Its schema is dropped and rebuilt
on every run, so never point it at real data.

```bash
uv run pytest -q                 # everything
uv run pytest -q -m "not integration"   # unit tests only
```
