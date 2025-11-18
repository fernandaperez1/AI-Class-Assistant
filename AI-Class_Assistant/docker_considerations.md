# Considerations for running locally

When developing locally, it's convenient to use a `docker-compose.override.yml` so you don't conflict with the production `nginx` port bindings and so the Vite dev server is accessible from your host.

Create a `docker-compose.override.yml` in the project root with the following contents:

```yaml
services:
  frontend:
    ports:
      - "5173:5173"

  nginx:
    ports:
      - "8080:80"
      - "8443:443"
```

How to use it

- Docker Compose automatically picks up `docker-compose.override.yml` when you run `docker compose` locally. With the override in place you can start the commonly used services like this:

```bash
docker compose up frontend backend db bot
```

Notes and troubleshooting

- The override exposes the frontend dev server on `http://localhost:5173`. If you see "refused to connect" or Vite host errors, ensure `frontend/vite.config.js` has `server.host: '0.0.0.0'` and includes `localhost` in `server.allowedHosts`.
- The production `nginx` listens on ports 80/443. The override maps those to `8080`/`8443` locally to avoid conflicts.
- If CORS or WebSocket errors occur, verify the backend `CORS_ORIGINS` includes `http://localhost:5173` and restart the backend container so it reloads `.env`.

This setup keeps the production Compose file untouched while making local development simple and conflict-free.
