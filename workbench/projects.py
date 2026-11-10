"""Project persistence and project-level ordering behavior."""

from __future__ import annotations

from pathlib import Path

from .markdown_io import dump_markdown, now_iso
from .persistence import atomic_write_text
from .project_identity import disk_occupied, next_project_id
from .records import TYPE_DIRS


PROJECT_DIRECTORIES = (*TYPE_DIRS.values(), 'assets/images', 'assets/files')
PROJECT_EDIT_FIELDS = ("name", "status", "color", "workflow_template", "issue_status_order", "todo_status_order",
                       "idea_status_order", "mixed_status_order", "issue_record_sort", "todo_record_sort",
                       "idea_record_sort", "info_record_sort", "mixed_record_sort", "issue_record_order",
                       "todo_record_order", "idea_record_order", "info_record_order", "mixed_record_order",
                       "issue_status_record_sorts", "todo_status_record_sorts", "idea_status_record_sorts",
                       "mixed_status_record_sorts")


def project_metadata_patch(payload):
    from .workflow_changes import SORT_MODES
    changes = {key:payload[key] for key in PROJECT_EDIT_FIELDS if key in payload}
    for key, value in changes.items():
        if key == "name" and not str(value).strip():
            raise ValueError("项目名称不能为空")
        if key.endswith("_order") and (not isinstance(value, list) or any(not isinstance(item, str) for item in value)):
            raise ValueError("顺序必须是字符串列表")
        if key.endswith("_record_sort") and value not in SORT_MODES:
            raise ValueError("不支持的记录排序规则")
        if key.endswith("_status_record_sorts") and (not isinstance(value, dict) or any(not isinstance(status, str) or mode not in SORT_MODES for status, mode in value.items())):
            raise ValueError("不支持的状态记录排序设置")
    return changes


def project_readme(project_id, payload, stamp):
    meta = {"id": project_id, "type": "project", "name": str(payload["name"]).strip(),
            "status": payload.get("status", "active"), "color": payload.get("color", "#4d78e8"),
            "workflow_template": payload.get("workflow_template", "standard"), "created": stamp, "updated": stamp}
    body = f"# {meta['name']}\n\n{payload.get('description', '').strip()}"
    return meta, dump_markdown(meta, body)


class ProjectRepository:
    """Own project Markdown and directories behind the Repository facade."""

    def __init__(
        self,
        projects_dir: Path,
        load_markdown,
        project_sort,
        save_project_sort,
        list_records,
        move_to_trash,
    ):
        self.projects_dir = projects_dir
        self.load_markdown = load_markdown
        self.project_sort = project_sort
        self.save_project_sort = save_project_sort
        self.list_records = list_records
        self._move_to_trash = move_to_trash
        self.reserved_ids = lambda: set()

    def allocate_project_id(self, name, extra_occupied=()):
        return next_project_id(name, disk_occupied(self.projects_dir.parent) | self.reserved_ids() | set(extra_occupied))

    def _unsorted_projects(self) -> list[dict]:
        projects = []
        for readme in self.projects_dir.glob("*/README.md"):
            meta, body = self.load_markdown(readme)
            if meta.get("type") != "project":
                continue
            meta["description"] = body.removeprefix(f"# {meta.get('name', '')}").strip()
            meta["path"] = str(readme.parent)
            projects.append(meta)
        return projects

    def list_projects(self) -> list[dict]:
        projects = self._unsorted_projects()
        sorting = self.project_sort()
        mode = sorting["mode"]
        if mode == "name":
            return sorted(projects, key=lambda item: item.get("name", "").casefold())
        if mode == "created":
            return sorted(projects, key=lambda item: item.get("created", ""), reverse=True)
        if mode == "record_count":
            counts: dict[str, int] = {}
            for record in self.list_records():
                project_id = record.get("project_id")
                if project_id:
                    counts[project_id] = counts.get(project_id, 0) + 1
            return sorted(projects, key=lambda item: (counts.get(item.get("id"), 0), item.get("name", "")), reverse=True)
        if mode == "updated":
            return sorted(projects, key=lambda item: item.get("updated", ""), reverse=True)
        positions = {project_id: index for index, project_id in enumerate(sorting["order"])}
        return sorted(projects, key=lambda item: (positions.get(item.get("id"), 999999), item.get("created", "")))

    def project(self, project_id: str) -> dict | None:
        return next((item for item in self.list_projects() if item.get("id") == project_id), None)

    def create_project(self, payload: dict, *, extra_occupied=()) -> dict:
        name = str(payload.get("name", "")).strip()
        if not name:
            raise ValueError("项目名称不能为空")
        project_id = self.allocate_project_id(name, extra_occupied)
        folder = self.projects_dir / project_id
        folder.mkdir(exist_ok=False)
        for child in PROJECT_DIRECTORIES:
            (folder / child).mkdir(parents=True, exist_ok=True)
        stamp = now_iso()
        meta, readme = project_readme(project_id, payload, stamp)
        atomic_write_text(folder / "README.md", readme)
        sorting = self.project_sort()
        if sorting["mode"] == "custom":
            sorting["order"] = [project["id"] for project in self.list_projects()]
            self.save_project_sort(sorting)
        return {**meta, "description": payload.get("description", ""), "path": str(folder)}

    def update_project(self, project_id: str, payload: dict) -> dict:
        project = self.project(project_id)
        if not project:
            raise FileNotFoundError(project_id)
        readme = self.projects_dir / project_id / "README.md"
        meta, body = self.load_markdown(readme)
        meta.update(project_metadata_patch(payload))
        meta["updated"] = now_iso()
        description = payload.get("description", project.get("description", ""))
        body = f"# {meta['name']}\n\n{str(description).strip()}"
        atomic_write_text(readme, dump_markdown(meta, body))
        return {**meta, "description": description, "path": str(readme.parent)}

    def delete_project(self, project_id: str) -> dict:
        project = self.project(project_id)
        if not project:
            raise FileNotFoundError(project_id)
        return self._move_to_trash(self.projects_dir / project_id, project_id, "project", project["name"])
