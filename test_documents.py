import json
import tempfile
import unittest
from pathlib import Path

from server import Repository
from workbench.configuration import ConfigurationRepository
from workbench.documents import DocumentRepository


class KnowledgeRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp.name)
        self.repo = Repository(self.data_dir)

    def tearDown(self):
        self.temp.cleanup()

    def test_repository_facade_uses_extracted_knowledge_repositories(self):
        self.assertIsInstance(self.repo._configuration_repository, ConfigurationRepository)
        self.assertIsInstance(self.repo._document_repository, DocumentRepository)

        document = self.repo.create_document({"title": "知识边界", "category": "架构", "body": "# 知识边界\n"})
        self.repo.save_document_categories(["空分类", "架构"])

        self.assertEqual(self.repo._document_repository.get_document(document["id"])[0]["title"], "知识边界")
        self.assertEqual(self.repo._configuration_repository.document_categories(), ["空分类", "架构"])

    def test_legacy_document_order_and_empty_categories_survive_reload(self):
        first = self.repo.create_document({"title": "第一篇", "category": "技术"})
        second = self.repo.create_document({"title": "第二篇", "category": "技术"})
        self.repo.save_document_categories(["空分类", "技术"])
        legacy = {"mode": "manual", "order": [second["id"], first["id"]]}
        (self.repo.config_dir / "document-sort.json").write_text(
            json.dumps(legacy, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        self.assertEqual(self.repo.document_sort()["legacy_order"], legacy["order"])
        migrated = self.repo.save_document_sort({})
        self.assertEqual(migrated["file_orders"]["技术"], legacy["order"])

        reloaded = Repository(self.data_dir)
        self.assertEqual(reloaded.document_categories(), ["空分类", "技术"])
        self.assertEqual(reloaded.document_sort()["file_orders"]["技术"], legacy["order"])


if __name__ == "__main__":
    unittest.main()
