# Running the tests

Everything here assumes the setup from the README's *Quick start* (a venv with `pip install -e '.[test]'`
and `playwright install chromium`).

## Layers and the smoke suite

| Layer (folder = marker) | What it checks | Network |
|---|---|---|
| `tests/unit` – `unit` | price parsing, shopping-case validation, config profiles, marker rules | none |
| `tests/component` – `component` | page objects and the workflow against a routed fake shop: paging, price filter, variants, cart, budget | none |
| `tests/e2e` – `e2e` | the assignment scenario, one test per case of `data/shopping_cases.json` | live |

- Every test has exactly one layer marker; this is checked at collection time (`tests/support/markers.py`,
  `tests/plugins/markers.py`).
- `smoke` marks the critical case(s): a case with `"smoke": true` in the data file. Pull requests run it.
- Allure labels: layer → epic, smoke → severity critical.
- The pytest setup is split into `tests/plugins/` (environment, markers, cases); shared helpers are in
  `tests/support/`.

```bash
pytest -m "unit or component" -n auto   # no network (~30 s)
pytest -m e2e                           # the assignment scenario, all data cases (live)
pytest -m smoke                         # what a pull request runs
pytest -m e2e --headed --slowmo 300     # watch it run
pytest -m e2e --env ci                  # another profile from config/environments.json (ci, debug)
pytest -m e2e --browser firefox         # after: playwright install firefox
```

## What the e2e test checks

Cases: computers, phones, sneakers with colour swatches, a case that forces the search onto page 2, a
random-quantity case, and a no-results case.

- The workflow's own check (from the brief): the cart Sub-Total <= `max_price` × number of items.
- The found URLs are within `limit`, unique, and every collected price is <= `max_price`.
- Each added item's price on its own product page is <= `max_price` (a second page confirms the listing).
- The data file's expected outcomes (`expect_empty`, `min_results`, `min_search_pages`).
- The shop refused no product ("Please select ...", "Enter valid recipient name"): a refusal means a missed
  option or field. Only products the shop marks as not buyable and forms with a required file upload are skipped.
- The cart holds exactly the units that were added.

## Data-driven inputs

**Shopping cases** ([data/shopping_cases.json](../data/shopping_cases.json)): one e2e test per entry.
- The loader validates types and rejects unknown keys.
- Cases are loaded at collection time (`tests/plugins/cases.py`). A broken file becomes one failing test,
  `test_shopping_flow[invalid-cases-file-...]`, and the offline layers still run.

| Field | Required | Meaning |
|---|---|---|
| `name`, `query`, `max_price`, `limit`, `seed` | yes | Case id, search text, price limit (string, so it stays exact), max results, random seed |
| `search_in_descriptions` | no | Tick "Search In product descriptions" (more results, so the search pages) |
| `expect_empty` | no | The search must return nothing |
| `min_results` | no | At least this many products must be found |
| `min_search_pages` | no | The search must read at least this many result pages |
| `smoke` | no | `true` also puts the case in the `smoke` suite |
| `max_quantity` | no | Default 1 (the assignment). If greater than 1, each item gets a random quantity 1..`max_quantity` from the seeded RNG. The budget is then `max_price` × total units, because the brief's budget is per item (unit). |

## Profiles and environment variables

[config/environments.json](../config/environments.json) holds three profiles:

| Profile | Purpose |
|---|---|
| `demo-webshop` | Default |
| `ci` | Longer timeouts, larger viewport |
| `debug` | Adds `slow_mo` |

- Each profile sets `base_url`, `timeout_ms`, `expect_timeout_ms`, `locale`, `viewport`, and optionally
  `slow_mo`. Unknown keys are rejected.
- `--base-url` and `--slowmo` on the command line take precedence over the profile.

| Variable | Meaning |
|---|---|
| `SHOP_ENV` | Profile name, same as `--env` |
| `SHOP_EMAIL`, `SHOP_PASSWORD` | Optional existing account. Unset (the default) means a fresh user is registered per test. Set both or neither. Not allowed with `-n` > 1 (one shared cart). |
| `SHOP_CASES` | Other shopping-cases file, same as `--cases PATH` |

They are documented in [.env.example](../.env.example) and read from the environment. A `.env` file is not
loaded automatically. The password is never logged.

## Parallel runs, reruns, timeouts

```bash
pytest -m "unit or component" -n auto   # all CPU cores
pytest -m e2e -n 3 --e2e-reruns 1       # what CI runs after a merge and nightly
```

- **Isolation:** tests are independent (a new user and cart per test).
- **Artifacts under `-n`:** `artifacts/` is cleaned once by the controller, so no worker deletes another
  worker's files.
- **Reruns:** only e2e tests rerun (`--e2e-reruns N`), because only they depend on the public demo site.
- **Timeouts:**
  - Unit and component tests: 3 s for actions and `expect()`, 60 s per test.
  - e2e tests: the profile's timeouts, 300 s per test (pytest-timeout).

## Reports and artifacts

| Output | Where | Notes |
|---|---|---|
| HTML report | `artifacts/reports/report.html` | Self-contained; failure screenshots embedded |
| JUnit XML | `artifacts/reports/junit.xml` | For CI |
| Allure results | `artifacts/allure-results/` | `allure serve artifacts/allure-results` (needs the Allure CLI) |
| Per-test artifacts | `artifacts/playwright/<test>/` | Numbered screenshots and `run-log.json` (search results, options, quantities, statuses, cart, threshold) |
| On failure | same folder + Allure | Playwright trace (`playwright show-trace trace.zip`) and a failure screenshot |

**The committed sample:**
- `artifacts/` is git-ignored and overwritten by every run.
- `reports/` holds a committed sample of a full serial run, plus the screenshots of one assignment case
  (`reports/sample-run/`).
- Refresh it with `python scripts/refresh_sample_report.py`. The script also removes the machine's hostname
  from the JUnit file.

## Installing exact versions, code quality

```bash
pip install --require-hashes -r requirements.lock      # what CI installs (requirements-dev.lock adds ruff, mypy, pre-commit)
pip install --no-deps --no-build-isolation -e .

# regenerate after changing pyproject.toml (add --upgrade to update); Dependabot only updates GitHub Actions
uv pip compile pyproject.toml --group build --extra test --universal --python-version 3.11 --generate-hashes -o requirements.lock
uv pip compile pyproject.toml --group build --extra test --extra dev --universal --python-version 3.11 --generate-hashes -o requirements-dev.lock

ruff check . && ruff format --check . && mypy
pre-commit install   # ruff, ruff-format and basic file checks on every commit
```
