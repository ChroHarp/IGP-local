# Repository Guidelines

## Project Structure & Module Organization

This repository is a local-first Django 5.2 application for managing gifted-education IGP records.

- `igp_project/` contains project URLs, ASGI/WSGI entry points, and split settings (`base.py`, `dev.py`, `prod.py`).
- `accounts/` is the main application. Models, policies, forms, import logic, admin customizations, migrations, management commands, and tests live here.
- `templates/admin/accounts/` contains Django Admin template overrides; related JavaScript and CSS are under `accounts/static/admin/accounts/`.
- `import_templates/` contains de-identified spreadsheet examples and import templates.
- `PRODUCT.md` and `PROJECT_PLAN.md` document scope and implementation decisions.

Keep migrations in `accounts/migrations/`; do not edit an applied migration when a new migration can express the change.

## Build, Test, and Development Commands

Use Python 3.13 and `uv` from PowerShell:

```powershell
$env:UV_CACHE_DIR = "$PWD\.uv-cache"
uv sync                                      # create/update the virtual environment
.\.venv\Scripts\python.exe manage.py migrate # apply database migrations
.\.venv\Scripts\python.exe manage.py runserver
.\.venv\Scripts\python.exe manage.py check   # validate Django configuration
.\.venv\Scripts\python.exe manage.py test    # run the full test suite
```

After model changes, run `manage.py makemigrations` and commit the generated migration with the code.

## Coding Style & Naming Conventions

Follow standard Python conventions: four-space indentation, `snake_case` functions and modules, `PascalCase` classes, and uppercase constants. Keep imports grouped as standard library, Django/third-party, then local imports. Prefer Django model constraints and centralized access policies over duplicating validation or authorization in views and admin classes. No formatter or linter is currently configured, so match nearby code and keep changes focused.

## Testing Guidelines

Tests use Django's `TestCase` and live in `accounts/tests.py`. Name classes by feature (`StudentAccessTests`) and methods as `test_<expected_behavior>`. Add regression tests for permissions, model constraints, imports, and Admin workflows. Use synthetic data only. Run both `manage.py check` and `manage.py test` before opening a pull request.

## Commit & Pull Request Guidelines

Recent history uses short, imperative subjects such as `Add IGP learning outcome workflow` and `Fix learning outcome admin grouping`. Keep each commit cohesive. Pull requests should explain the user-visible change, list migrations and verification commands, link relevant issues, and include screenshots for Admin or template changes.

## Security & Configuration

Copy settings from `.env.example`; never commit `.env`, SQLite databases, `media/`, logs, backups, OAuth secrets, or real student data. Preserve role-based visibility rules, and treat the initial superuser as an offline break-glass account.
