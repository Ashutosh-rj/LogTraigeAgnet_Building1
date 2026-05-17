# Security Model

## Authentication

- Passwords are hashed with bcrypt.
- Access tokens are signed JWTs with short expiry.
- Refresh tokens are random opaque values stored only as SHA-256 hashes.
- Refresh token rotation revokes the previous token and records the replacement token.

## Authorization

Roles:

- `admin`: full administrative control.
- `responder`: incident operations, triage, notifications, and search.
- `viewer`: read-only dashboard and search access.

Route dependencies enforce the minimum role required for each operation.

## Runtime Secrets

Production mode requires `JWT_SECRET` and rejects weak values. Local development may generate ephemeral process secrets so `docker compose up --build` can start without committing a `.env` file.

## API Hardening

- Pydantic v2 validates all payloads.
- SQLAlchemy parameterization prevents SQL injection.
- Rate limiting applies to all API routes.
- CORS is restricted to configured origins.
- Security headers are added to every response.
- Request IDs are propagated through logs and responses.

