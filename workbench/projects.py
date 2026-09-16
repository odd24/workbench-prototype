"""Project persistence and project-level ordering behavior."""

from __future__ import annotations

from pathlib import Path

from .markdown_io import dump_markdown, now_iso, slugify
from .records import TYPE_DIRS


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

    def create_project(self, payload: dict) -> dict:
        name = str(payload.get("name", "")).strip()
        if not name:
            raise ValueError("项目名称不能为空")
        base = slugify(name)
        project_id, index = base, 2
        while self.project(project_id):
            project_id, index = f"{base}-{index}", index + 1
        folder = self.projects_dir / project_id
        for child in (*TYPE_DIRS.values(), "assets/images", "assets/files"):
            (folder / child).mkdir(parents=True, exist_ok=True)
        stamp = now_iso()
        meta = {"id": project_id, "type": "project", "name": name, "status": payload.get("status", "active"), "color": payload.get("color", "#4d78e8"), "workflow_template": payload.get("workflow_template", "standard"), "created": stamp, "updated": stamp}
        body = f"# {name}\n\n{payload.get('description', '').strip()}"
        (folder / "README.md").write_text(dump_markdown(meta, body), encoding="utf-8")
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
        for key in ("name", "status", "color", "workflow_template", "issue_status_order", "todo_status_order", "idea_status_order", "mixed_status_order", "issue_record_sort", "todo_record_sort", "idea_record_sort", "info_record_sort", "mixed_record_sort", "issue_record_order", "todo_record_order", "idea_record_order", "info_record_order", "mixed_record_order", "issue_status_record_sorts", "todo_status_record_sorts", "idea_status_record_sorts", "mixed_status_record_sorts"):
            if key in payload:
                if key == "name" and not str(payload[key]).strip():
                    raise ValueError("项目名称不能为空")
                if key.endswith("_order") and (not isinstance(payload[key], list) or any(not isinstance(item, str) for item in payload[key])):
                    raise ValueError("顺序必须是字符串列表")
                if key.endswith("_record_sort") and payload[key] not in {"manual", "updated", "priority", "due", "title", "created"}:
                    raise ValueError("不支持的记录排序规则")
                if key.endswith("_status_record_sorts") and (not isinstance(payload[key], dict) or any(not isinstance(status, str) or mode not in {"manual", "updated", "priority", "due", "title", "created"} for status, mode in payload[key].items())):
                    raise ValueError("不支持的状态记录排序设置")
                meta[key] = payload[key]
        meta["updated"] = now_iso()
        description = payload.get("description", project.get("description", ""))
        body = f"# {meta['name']}\n\n{str(description).strip()}"
        readme.write_text(dump_markdown(meta, body), encoding="utf-8")
        return {**meta, "description": description, "path": str(readme.parent)}

    def delete_project(self, project_id: str) -> dict:
        project = self.project(project_id)
        if not project:
            raise FileNotFoundError(project_id)
        return self._move_to_trash(self.projects_dir / project_id, project_id, "project", project["name"])
