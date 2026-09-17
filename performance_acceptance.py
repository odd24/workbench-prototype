"""RF-504 repeatable large-data acceptance using only temporary data."""

from __future__ import annotations

import hashlib
import io
import json
import os
import platform
import subprocess
import tempfile
import time
import zipfile
from pathlib import Path

from server import Repository


PROJECT_COUNT = int(os.environ.get("WORKBENCH_PERF_PROJECTS", "12"))
RECORD_COUNT = int(os.environ.get("WORKBENCH_PERF_RECORDS", "1200"))
DOCUMENT_COUNT = int(os.environ.get("WORKBENCH_PERF_DOCUMENTS", "160"))
ATTACHMENT_COUNT = int(os.environ.get("WORKBENCH_PERF_ATTACHMENTS", "120"))
LONG_MARKDOWN_BYTES = int(os.environ.get("WORKBENCH_PERF_MARKDOWN_BYTES", str(1024 * 1024)))


def timed(metrics: dict, name: str, callback):
    started = time.perf_counter()
    result = callback()
    metrics[name] = round((time.perf_counter() - started) * 1000, 2)
    return result


def long_markdown() -> str:
    section = "## 大数据章节\n\n这是用于 RF-504 的长 Markdown。包含 **粗体**、`代码`、[[ISSUE-0001]] 与中文。\n\n"
    return ("# RF-504 长文档\n\n" + section * (LONG_MARKDOWN_BYTES // len(section.encode("utf-8")) + 1))[:LONG_MARKDOWN_BYTES]


def concept_map_payload() -> dict:
    nodes = []
    for index in range(500):
        nodes.append({
            "id": f"node-{index}",
            "text": f"性能节点 {index}",
            "type": "linking_phrase" if index % 5 == 1 else "concept",
            "x": (index % 25) * 180,
            "y": (index // 25) * 100,
            "width": 130,
            "height": 44,
        })
    edges = [
        {"id": f"edge-{index}", "from": f"node-{index}", "to": f"node-{index + 1}", "label": ""}
        for index in range(499)
    ]
    return {"title": "RF-504 五百节点概念图", "category": "性能验收", "nodes": nodes, "edges": edges}


def populate(root: Path, metrics: dict) -> dict:
    repository = Repository(root)
    projects = timed(metrics, "create_projects_ms", lambda: [
        repository.create_project({"name": f"性能项目 {index:02d}", "description": "RF-504 临时样本"})
        for index in range(PROJECT_COUNT)
    ])
    records = []

    def create_records():
        for index in range(RECORD_COUNT):
            record_type = ("issue", "todo", "info")[index % 3]
            payload = {
                "type": record_type,
                "title": f"性能记录 {index:04d}",
                "project_id": projects[index % len(projects)]["id"],
                "tags": ["性能", f"批次-{index % 20}"],
                "body": f"# 性能记录 {index:04d}\n\n" + ("正文与搜索关键字 performance-token。\n" * 24),
            }
            if record_type == "info":
                payload["info_fields"] = [{"name": "命令", "value": f"echo record-{index}\necho done", "note": "只复制不执行"}]
            records.append(repository.create_record(payload))
        return records

    timed(metrics, "create_records_ms", create_records)
    documents = []
    large_body = long_markdown()

    def create_documents():
        for index in range(DOCUMENT_COUNT):
            body = large_body if index == 0 else f"# 性能文档 {index:03d}\n\n" + ("知识库正文。\n" * 60)
            documents.append(repository.create_document({
                "title": f"性能文档 {index:03d}", "category": f"分类 {index % 16:02d}", "body": body,
            }))
        return documents

    timed(metrics, "create_documents_ms", create_documents)
    persisted_long_document, _ = repository.get_document(documents[0]["id"])
    persisted_large_body = persisted_long_document["body"]
    attachment_bytes = ("附件内容-" * 128).encode("utf-8")

    def create_attachments():
        for index in range(ATTACHMENT_COUNT):
            record = records[index % len(records)]
            repository.add_record_attachment_stream(
                record["id"], f"attachment-{index:03d}.txt", io.BytesIO(attachment_bytes), len(attachment_bytes), False,
            )

    timed(metrics, "create_attachments_ms", create_attachments)
    concept_map = timed(metrics, "create_concept_map_ms", lambda: repository.create_concept_map(concept_map_payload()))
    return {
        "projectId": projects[0]["id"],
        "documentId": documents[0]["id"],
        "conceptMapId": concept_map["id"],
        "projectCount": PROJECT_COUNT,
        "recordCount": RECORD_COUNT,
        "documentCount": DOCUMENT_COUNT,
        "attachmentCount": ATTACHMENT_COUNT,
        "longDocumentLength": len(persisted_large_body),
        "longDocumentBytes": len(persisted_large_body.encode("utf-8")),
        "longDocumentSha256": hashlib.sha256(persisted_large_body.encode("utf-8")).hexdigest(),
        "conceptMapEdgeCount": len(concept_map["edges"]),
    }


def backend_acceptance(root: Path, manifest: dict, metrics: dict):
    repository = timed(metrics, "repository_reload_ms", lambda: Repository(root))
    projects = timed(metrics, "list_projects_ms", repository.list_projects)
    summaries = timed(metrics, "list_record_summaries_ms", repository.list_record_summaries)
    signatures = timed(metrics, "record_signatures_ms", repository.record_signatures)
    documents = timed(metrics, "list_documents_ms", repository.list_documents)
    matches = timed(metrics, "search_ms", lambda: repository.search("performance-token"))
    archive = timed(metrics, "export_zip_ms", repository.export_zip)
    with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
        bad_member = bundle.testzip()
        archive_entries = len(bundle.infolist())
    long_document, _ = repository.get_document(manifest["documentId"])
    concept_map, _ = repository.get_concept_map(manifest["conceptMapId"])
    attachments = sum(len(record.get("attachments") or []) for record in repository.list_records())
    assert len(projects) == manifest["projectCount"]
    assert len(summaries) == len(signatures) == manifest["recordCount"]
    assert len(documents) == manifest["documentCount"]
    assert len(matches) == min(50, manifest["recordCount"])
    assert all("performance-token" in record.get("body", "") for record in matches)
    assert attachments == manifest["attachmentCount"]
    assert hashlib.sha256(long_document["body"].encode("utf-8")).hexdigest() == manifest["longDocumentSha256"]
    assert len(concept_map["nodes"]) == 500
    assert len(concept_map["edges"]) == manifest["conceptMapEdgeCount"]
    assert bad_member is None
    return {"archiveBytes": len(archive), "archiveEntries": archive_entries, "searchResults": len(matches)}


def main():
    metrics = {}
    with tempfile.TemporaryDirectory(prefix="workbench-rf504-") as directory:
        root = Path(directory)
        manifest = populate(root, metrics)
        integrity = backend_acceptance(root, manifest, metrics)
        environment = os.environ.copy()
        environment["WORKBENCH_PERF_DATA"] = str(root)
        environment["WORKBENCH_PERF_MANIFEST"] = json.dumps(manifest, ensure_ascii=False)
        browser = subprocess.run(
            ["node", "performance_browser.js"], cwd=Path(__file__).parent, env=environment,
            capture_output=True, text=True, encoding="utf-8",
        )
        if browser.returncode:
            raise RuntimeError(f"浏览器性能验收失败\nSTDOUT:\n{browser.stdout}\nSTDERR:\n{browser.stderr}")
        browser_metrics = json.loads(browser.stdout)
        report = {
            "machine": {
                "platform": platform.platform(),
                "processor": platform.processor(),
                "cpuCount": os.cpu_count(),
                "python": platform.python_version(),
            },
            "sample": manifest,
            "backendMs": metrics,
            "integrity": integrity,
            "browser": browser_metrics,
        }
        print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
