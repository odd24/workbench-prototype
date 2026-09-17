"""Concept map normalization and JSON persistence."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from workbench.markdown_io import now_iso
from workbench.persistence import atomic_write_json
from workbench.security import validate_category_name


CONCEPT_MAP_WIDTH = 12_000.0
CONCEPT_MAP_HEIGHT = 8_000.0
TrashMover = Callable[[Path, str, str, str], dict]


class ConceptMapRepository:
    def __init__(self, concept_maps_dir: Path, config_dir: Path, id_lock: Any, move_to_trash: TrashMover):
        self.concept_maps_dir = concept_maps_dir
        self.config_dir = config_dir
        self._id_lock = id_lock
        self._move_to_trash = move_to_trash

    @staticmethod
    def concept_map_number(value, default=0.0) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return float(default)
        return number if abs(number) <= 100_000 else float(default)

    def normalize(self, payload: dict, current: dict | None = None) -> dict:
        if not isinstance(payload, dict):
            raise ValueError("概念图数据无效")
        base = current or {}
        title = str(payload.get("title", base.get("title", ""))).strip()[:120]
        if not title:
            raise ValueError("概念图标题不能为空")
        raw_nodes = payload.get("nodes", base.get("nodes", []))
        raw_edges = payload.get("edges", base.get("edges", []))
        if not isinstance(raw_nodes, list) or len(raw_nodes) > 500:
            raise ValueError("概念图节点数量无效")
        if not isinstance(raw_edges, list) or len(raw_edges) > 1000:
            raise ValueError("概念图关系数量无效")
        nodes, node_ids, node_types = [], set(), {}
        for index, raw in enumerate(raw_nodes):
            if not isinstance(raw, dict):
                continue
            node_id = str(raw.get("id", "")).strip()
            if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", node_id) or node_id in node_ids:
                node_id = f"node-{index + 1}"
                while node_id in node_ids:
                    node_id += "x"
            node_ids.add(node_id)
            node_type = str(raw.get("type", "concept"))
            if node_type not in {"concept", "linking_phrase"}:
                node_type = "concept"
            node_types[node_id] = node_type
            shape = str(raw.get("shape", "rounded"))
            if shape not in {"rounded", "rectangle", "pill", "ellipse"}:
                shape = "rounded"
            default_fill = "#eef0f2" if node_type == "linking_phrase" else "#ffffff"
            default_border = "#eef0f2" if node_type == "linking_phrase" else "#9eb4c7"
            color = str(raw.get("color", default_fill))
            if not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
                color = default_fill
            border_color = str(raw.get("border_color", default_border))
            if not re.fullmatch(r"#[0-9a-fA-F]{6}", border_color):
                border_color = default_border
            text_color = str(raw.get("text_color", "#213044"))
            if not re.fullmatch(r"#[0-9a-fA-F]{6}", text_color):
                text_color = "#213044"
            font_weight = int(raw.get("font_weight", 400)) if str(raw.get("font_weight", 400)).isdigit() else 400
            if font_weight not in {400, 600, 700}:
                font_weight = 400
            min_width, min_height = (30, 22) if node_type == "linking_phrase" else (72, 30)
            nodes.append({
                "id": node_id, "text": str(raw.get("text", "新概念")).strip()[:500] or "新概念",
                "type": node_type,
                "note": str(raw.get("note", ""))[:5000],
                "x": self.concept_map_number(raw.get("x")), "y": self.concept_map_number(raw.get("y")),
                "width": min(420, max(min_width, self.concept_map_number(raw.get("width"), 120))),
                "height": min(260, max(min_height, self.concept_map_number(raw.get("height"), 38))),
                "color": color.lower(), "border_color": border_color.lower(), "text_color": text_color.lower(),
                "font_size": min(32, max(10, int(self.concept_map_number(raw.get("font_size"), 13)))),
                "font_weight": font_weight, "shape": shape,
            })
        edges, edge_ids = [], set()
        for index, raw in enumerate(raw_edges):
            if not isinstance(raw, dict) or raw.get("from") not in node_ids or raw.get("to") not in node_ids or raw.get("from") == raw.get("to"):
                continue
            edge_id = str(raw.get("id", "")).strip()
            if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", edge_id) or edge_id in edge_ids:
                edge_id = f"edge-{index + 1}"
                while edge_id in edge_ids:
                    edge_id += "x"
            edge_ids.add(edge_id)
            color = str(raw.get("color", "#64748b"))
            if not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
                color = "#64748b"
            default_arrowhead = "none" if node_types.get(raw["to"]) == "linking_phrase" else "to"
            arrowhead = str(raw.get("arrowhead", default_arrowhead))
            if arrowhead not in {"none", "to", "from", "both"}:
                arrowhead = default_arrowhead
            if node_types.get(raw["to"]) == "linking_phrase" and arrowhead not in {"none", "from"}:
                arrowhead = "none"
            elif node_types.get(raw["from"]) == "linking_phrase" and node_types.get(raw["to"]) == "concept":
                arrowhead = "to"
            edges.append({
                "id": edge_id, "from": raw["from"], "to": raw["to"],
                "label": str(raw.get("label", "相关于")).strip()[:120],
                "color": color.lower(), "dashed": bool(raw.get("dashed", False)), "arrowhead": arrowhead,
            })
        viewport = payload.get("viewport", base.get("viewport", {}))
        if not isinstance(viewport, dict):
            viewport = {}
        zoom = min(3, max(.2, self.concept_map_number(viewport.get("zoom"), 1)))
        return {
            "version": 2, "title": title,
            "project_id": str(payload.get("project_id", base.get("project_id", "")) or "").strip()[:80] or None,
            "category": validate_category_name(payload.get("category", base.get("category", "未分类"))),
            "focus_question": str(payload.get("focus_question", base.get("focus_question", ""))).strip()[:500],
            "theme": str(payload.get("theme", base.get("theme", "light"))) if str(payload.get("theme", base.get("theme", "light"))) in {"light", "paper", "dots"} else "light",
            "viewport": {"x": self.concept_map_number(viewport.get("x")), "y": self.concept_map_number(viewport.get("y")), "zoom": zoom},
            "nodes": nodes, "edges": edges,
        }

    def list(self) -> list[dict]:
        maps = []
        for path in self.concept_maps_dir.glob("CMAP-*.json"):
            try:
                item = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(item, dict):
                continue
            concept_count = sum(1 for node in item.get("nodes", []) if node.get("type", "concept") != "linking_phrase")
            relation_count = sum(1 for node in item.get("nodes", []) if node.get("type") == "linking_phrase")
            if not relation_count:
                relation_count = sum(1 for edge in item.get("edges", []) if edge.get("label"))
            maps.append({key: item.get(key) for key in ("id", "title", "project_id", "focus_question", "category", "created", "updated")} | {"category": str(item.get("category") or "未分类"), "node_count": concept_count, "relation_count": relation_count, "edge_count": len(item.get("edges", []))})
        return sorted(maps, key=lambda item: item.get("updated", ""), reverse=True)

    def categories(self) -> list[str]:
        path = self.config_dir / "concept-map-categories.json"
        try:
            configured = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            configured = []
        if not isinstance(configured, list):
            configured = []
        categories = list(dict.fromkeys(str(item).strip() for item in configured if str(item).strip()))
        for concept_map in self.list():
            category = str(concept_map.get("category") or "未分类").strip() or "未分类"
            if category not in categories:
                categories.append(category)
        return categories

    def save_categories(self, categories: list) -> list[str]:
        if not isinstance(categories, list):
            raise ValueError("概念图分类格式无效")
        cleaned = []
        for value in categories:
            name = validate_category_name(value, default="", label="分类名称")
            if not name:
                continue
            if name not in cleaned:
                cleaned.append(name)
        for concept_map in self.list():
            category = str(concept_map.get("category") or "未分类").strip() or "未分类"
            if category not in cleaned:
                cleaned.append(category)
        atomic_write_json(self.config_dir / "concept-map-categories.json", cleaned)
        return cleaned

    def ensure_category(self, category: str) -> str:
        name = validate_category_name(category)
        categories = self.categories()
        if name not in categories:
            categories.append(name)
            self.save_categories(categories)
        return name

    def rename_category(self, old_name: str, new_name: str) -> dict:
        old_name = str(old_name).strip()
        new_name = validate_category_name(new_name, default="", label="分类名称")
        categories = self.categories()
        if old_name not in categories:
            raise FileNotFoundError(old_name)
        if not new_name:
            raise ValueError("分类名称不能为空")
        if new_name != old_name and new_name in categories:
            raise ValueError("分类名称已存在")
        changed = 0
        for summary in self.list():
            if summary.get("category") != old_name:
                continue
            item, path = self.get(summary["id"])
            if item and path:
                item["category"], item["updated"] = new_name, now_iso()
                self.write(path, item)
                changed += 1
        renamed = [new_name if category == old_name else category for category in categories]
        return {"categories": self.save_categories(list(dict.fromkeys(renamed))), "updated_maps": changed}

    def delete_category(self, name: str) -> dict:
        name = str(name).strip()
        categories = self.categories()
        if name not in categories:
            raise FileNotFoundError(name)
        if name == "未分类":
            raise ValueError("“未分类”是系统默认分类，不能删除")
        changed = 0
        for summary in self.list():
            if summary.get("category") != name:
                continue
            item, path = self.get(summary["id"])
            if item and path:
                item["category"], item["updated"] = "未分类", now_iso()
                self.write(path, item)
                changed += 1
        remaining = [category for category in categories if category != name]
        if "未分类" not in remaining:
            remaining.append("未分类")
        return {"categories": self.save_categories(remaining), "updated_maps": changed}

    def get(self, map_id: str) -> tuple[dict, Path] | tuple[None, None]:
        if not re.fullmatch(r"CMAP-\d+", str(map_id)):
            return None, None
        path = self.concept_maps_dir / f"{map_id}.json"
        if not path.is_file():
            return None, None
        try:
            item = json.loads(path.read_text(encoding="utf-8"))
            return (item, path) if isinstance(item, dict) else (None, None)
        except json.JSONDecodeError:
            return None, None

    @staticmethod
    def write(path: Path, item: dict) -> dict:
        atomic_write_json(path, item)
        return item

    def create(self, payload: dict) -> dict:
        with self._id_lock:
            used = [int(match.group(1)) for path in self.concept_maps_dir.glob("CMAP-*.json") if (match := re.fullmatch(r"CMAP-(\d+)", path.stem))]
            map_id, stamp = f"CMAP-{max(used, default=0) + 1:04d}", now_iso()
            normalized = self.normalize(payload)
            normalized["category"] = self.ensure_category(normalized["category"])
            if not normalized["nodes"]:
                width, height = float(min(240, max(90, len(normalized["title"]) * 14 + 22))), 38.0
                normalized["nodes"] = [{"id": "node-1", "type": "concept", "text": normalized["title"], "note": "", "x": (CONCEPT_MAP_WIDTH - width) / 2, "y": (CONCEPT_MAP_HEIGHT - height) / 2, "width": width, "height": height, "color": "#f4f8fa", "border_color": "#9eb4c7", "text_color": "#213044", "font_size": 13, "font_weight": 400, "shape": "rounded"}]
            item = {"id": map_id, **normalized, "created": stamp, "updated": stamp}
            return self.write(self.concept_maps_dir / f"{map_id}.json", item)

    def update(self, map_id: str, payload: dict) -> dict:
        current, path = self.get(map_id)
        if not current or not path:
            raise FileNotFoundError(map_id)
        normalized = self.normalize(payload, current)
        normalized["category"] = self.ensure_category(normalized["category"])
        item = {**current, **normalized, "id": map_id, "updated": now_iso()}
        return self.write(path, item)

    def delete(self, map_id: str) -> dict:
        item, path = self.get(map_id)
        if not item or not path:
            raise FileNotFoundError(map_id)
        return self._move_to_trash(path, map_id, "concept-map", item.get("title", map_id))
