# Docker and Redis Verification (Windows)

This guide verifies Docker is running and Redis is reachable, with expected output examples.

## 1) Verify Docker Desktop is running

Run:
```powershell
docker version
```

Expected output includes both **Client** and **Server** sections:
```
Client: Docker Engine - Community
...
Server: Docker Engine - Community
...
```

If you see only the client or an error like:
```
open //./pipe/dockerDesktopLinuxEngine: The system cannot find the file specified
```
Docker Desktop is not running yet. Start Docker Desktop and retry.

## 2) Verify Docker can list containers

Run:
```powershell
docker ps
```

Expected output when Docker is healthy:
```
CONTAINER ID   IMAGE         COMMAND                  STATUS          PORTS                    NAMES
```

If Redis is running, you should see a `redis` image container in this list.

## 3) Start Redis with Docker (if not running)

Run:
```powershell
docker run -d --name redis-local -p 6379:6379 redis:7
```

Expected output: a container id (long hash).

## 4) Test Redis health

Option A (no local redis-cli needed):
```powershell
docker exec -it redis-local redis-cli ping
```

Expected output:
```
PONG
```

Option B (if you have redis-cli installed locally):
```powershell
redis-cli ping
```

Expected output:
```
PONG
```

## 5) Common issues and fixes

- **`redis-cli` not recognized**: Use `docker exec` (Option A) or install Redis tools.
- **Port already in use**: Stop the existing container or change the host port:
  ```powershell
  docker run -d --name redis-local -p 6380:6379 redis:7
  ```
  Then test with:
  ```powershell
  docker exec -it redis-local redis-cli ping
  ```

## Quick checklist

- Docker Desktop started
- `docker version` shows Client + Server
- `docker ps` works without error
- `redis-cli ping` (via docker exec) returns `PONG`
