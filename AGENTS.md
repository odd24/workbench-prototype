# Repository Guidelines

## Project Structure & Module Organization

This repository is a compact local-first web application with no package manager or build step.

- `server.py` contains the HTTP API, Markdown repository logic, import/export, and CLI entry point.
- `index.html`, `app.js`, and `styles.css` implement the browser UI using vanilla HTML, JavaScript, and CSS.
- `test_server.py` contains backend and repository regression tests.
- `workbench-data/` holds generated projects, records, attachments, configuration, and trash; it is local runtime data and is intentionally ignored by Git.
- `preview*.png` files are local visual-review captures, not production assets.

Keep backend behavior in `server.py` and UI behavior in `app.js`; avoid introducing generated artifacts or machine-specific configuration into commits.

## Build, Test, and Development Commands

```powershell
python server.py --seed-demo
```

Starts the app at `http://127.0.0.1:4173` and creates demo content only when no projects exist. Use `python server.py` for normal subsequent runs, or double-click `start-workbench.cmd` on Windows.

```powershell
python -m unittest -v
python -m py_compile server.py test_server.py
```

The first command runs the full test suite; the second performs a quick Python syntax check. There is no compilation or dependency-install step.

## Coding Style & Naming Conventions

Use 4-space indentation and standard-library-first imports in Python. Follow `snake_case` for functions and variables, `PascalCase` for classes, and uppercase names for constants. In JavaScript and CSS, preserve the existing 2-space indentation, single-quoted JavaScript strings, `camelCase` identifiers, and kebab-case CSS classes. Keep functions focused and reuse existing repository/API helpers. No formatter or linter is configured, so match neighboring code closely.

## Testing Guidelines

Tests use Python's `unittest`. Add new cases to `test_server.py`, name methods `test_<behavior>`, and isolate filesystem operations with `tempfile.TemporaryDirectory`. Cover both successful workflows and validation/error paths. For UI changes, run the server and manually verify the affected view, persistence after reload, and narrow-window layout.

## Commit & Pull Request Guidelines

Recent commits use short, imperative summaries such as `Enhance asset workflows and configuration management`. Keep each commit focused and avoid committing `workbench-data/`, caches, previews, or local `.workbench-*.json` settings. Pull requests should explain the user-visible change, list verification commands, note data-format or API changes, link relevant issues, and include before/after screenshots for visual changes.

## Security & Configuration

Use `WORKBENCH_DATA_DIR` to test against disposable data outside the repository. Do not include personal Markdown content, exported archives, credentials, or absolute machine paths in commits.
