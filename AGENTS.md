# Repository Guidelines

## Project Structure & Module Organization

This repository is a compact local-first web application with no package manager or build step.

- `server.py` contains the HTTP API, Markdown repository logic, import/export, and CLI entry point.
- `index.html`, `app.js`, and `styles.css` implement the browser UI using vanilla HTML, JavaScript, and CSS.
- `test_server.py` contains backend and repository regression tests.
- `workbench-data/` holds generated projects, records, attachments, configuration, and trash; it is local runtime data and is intentionally ignored by Git.
- `preview*.png` files are local visual-review captures, not production assets.

Keep backend behavior in `server.py` and UI behavior in `app.js`; avoid introducing generated artifacts or machine-specific configuration into commits.

## Document Editing Architecture

Markdown is the durable local storage and interchange format, not the primary UI model. Both the record editor and the knowledge-base editor must share the same rendering, content-block normalization, and serialization helpers in `app.js`.

- Treat paragraphs, headings, lists, task lists, quotes, code blocks, dividers, and tables as typed content blocks before serializing them.
- Keep structural blocks as direct children of the editor. Do not use `execCommand('insertHTML')` to insert lists, tasks, tables, quotes, or code blocks because browsers can create invalid nested markup.
- Convert editor DOM to the shared document model first, then serialize that model to Markdown. Convert imported or stored Markdown through the shared renderer and hydrate block metadata before editing.
- Preserve standard Markdown whenever it can represent the content. Use compatible HTML or metadata extensions only for features that standard Markdown cannot represent without data loss.
- A visual state that looks correct before saving is not sufficient. Every editor feature must survive visual editor → model → Markdown → reload → visual editor round trips.
- Keep reading mode free of editing controls, and do not expose Markdown syntax in the default visual editing experience.

## Build, Test, and Development Commands

```powershell
python server.py --seed-demo
```

Starts the app at `http://127.0.0.1:4173` and creates demo content only when no projects exist. Use `python server.py` for normal subsequent runs, or double-click `start-workbench.cmd` on Windows.

```powershell
python -m unittest -v
python -m py_compile server.py test_server.py
node --check app.js
```

The first command runs the full test suite; the second performs a quick Python syntax check. There is no compilation or dependency-install step.

## Coding Style & Naming Conventions

Use 4-space indentation and standard-library-first imports in Python. Follow `snake_case` for functions and variables, `PascalCase` for classes, and uppercase names for constants. In JavaScript and CSS, preserve the existing 2-space indentation, single-quoted JavaScript strings, `camelCase` identifiers, and kebab-case CSS classes. Keep functions focused and reuse existing repository/API helpers. No formatter or linter is configured, so match neighboring code closely.

## Testing Guidelines

Tests use Python's `unittest`. Add new cases to `test_server.py`, name methods `test_<behavior>`, and isolate filesystem operations with `tempfile.TemporaryDirectory`. Cover both successful workflows and validation/error paths. For UI changes, run the server and verify the affected view, persistence after reload, and narrow-window layout. For editor changes, test the same content in both record and knowledge-base editors and include at least one save-and-reopen round trip for every affected block type.

## Commit & Pull Request Guidelines

Recent commits use short, imperative summaries such as `Enhance asset workflows and configuration management`. Keep each commit focused and avoid committing `workbench-data/`, caches, previews, or local `.workbench-*.json` settings. Pull requests should explain the user-visible change, list verification commands, note data-format or API changes, link relevant issues, and include before/after screenshots for visual changes.

## Security & Configuration

Use `WORKBENCH_DATA_DIR` to test against disposable data outside the repository. Do not include personal Markdown content, exported archives, credentials, or absolute machine paths in commits.
