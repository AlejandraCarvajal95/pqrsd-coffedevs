This pull request sets up the foundational infrastructure and conventions for the PQRSD Coffee Devs project. It introduces backend configuration, database connection and initialization, project documentation, environment variable management, and continuous integration (CI) workflows. The changes aim to ensure secure handling of secrets, consistent development practices, and smooth local and CI-based deployment.

**Key changes:**

### Project Documentation and Conventions

-   Added `README.md` and `CLAUDE.md` with detailed setup instructions, team conventions, security guidelines, and workflow processes for both backend and frontend. These documents also include guidance for handling secrets and environment variables, as well as a project structure overview. [\[1\]](https://github.com/AlejandraCarvajal95/pqrsd-coffedevs/pull/1/files#diff-b335630551682c19a781afebcf4d07bf978fb1f8ac04c6bf87428ed5106870f5R1-R104) [\[2\]](https://github.com/AlejandraCarvajal95/pqrsd-coffedevs/pull/1/files#diff-6ebdb617a8104a7756d0cf36578ab01103dc9f07e4dc6feb751296b9c402faf7R1-R47)

### Environment and Secret Management

-   Overhauled `.env.example` with clear instructions, required and optional variables, and placeholder values (`cambiar-esto`). Emphasized never storing secrets in the repository.
-   Added `.dockerignore` in `backend/` to prevent sensitive files and unnecessary artifacts (e.g., `.env`, `.pem`, bytecode, virtual environments) from being copied into Docker images.

### Backend Application and Database

-   Implemented backend configuration in `backend/app/config.py` to strictly read all settings from environment variables, enforce presence of required secrets, and avoid leaking secret values.
-   Established database connection logic in `backend/app/db.py`, including robust initialization, session management, and health checks. The schema is created on startup without migrations (per hackathon decision).
-   Added main FastAPI application in `backend/app/main.py` with a health endpoint and proper router setup under `/api`.
-   Created a Dockerfile for the backend to ensure reproducible builds, run as a non-root user, and expose the correct port.
-   Ensured all data models are imported and registered via `backend/app/models/__init__.py`.

### Continuous Integration (CI)

-   Introduced a comprehensive GitHub Actions workflow (`.github/workflows/ci.yml`) with jobs for secret scanning, backend linting and testing, frontend build, and end-to-end Docker Compose smoke tests. The workflow is designed to block merges to protected branches unless all checks pass.