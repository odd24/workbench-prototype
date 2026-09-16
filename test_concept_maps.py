import tempfile
import unittest
from pathlib import Path

import server
from server import Repository
from workbench.concept_maps import CONCEPT_MAP_HEIGHT, CONCEPT_MAP_WIDTH, ConceptMapRepository


class ConceptMapRepositoryTests(unittest.TestCase):
    def test_repository_facade_uses_extracted_concept_map_repository(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Repository(Path(directory))
            created = repo.create_concept_map({"title": "模块边界"})

            self.assertIsInstance(repo._concept_map_repository, ConceptMapRepository)
            self.assertEqual(repo._concept_map_repository.get(created["id"])[0], repo.get_concept_map(created["id"])[0])
            self.assertEqual(server.CONCEPT_MAP_WIDTH, CONCEPT_MAP_WIDTH)
            self.assertEqual(server.CONCEPT_MAP_HEIGHT, CONCEPT_MAP_HEIGHT)

    def test_update_is_atomically_persisted_and_reloaded(self):
        with tempfile.TemporaryDirectory() as directory:
            data_dir = Path(directory)
            repo = Repository(data_dir)
            created = repo.create_concept_map({"title": "原子写入"})
            repo.update_concept_map(created["id"], {
                "viewport": {"x": 12, "y": -8, "zoom": 1.4},
                "nodes": [{"id": "stable-node", "text": "稳定节点", "x": 10, "y": 20}],
            })

            self.assertEqual(list(repo.concept_maps_dir.glob("*.tmp")), [])
            reloaded = Repository(data_dir).get_concept_map(created["id"])[0]
            self.assertEqual(reloaded["nodes"][0]["id"], "stable-node")
            self.assertEqual(reloaded["viewport"], {"x": 12.0, "y": -8.0, "zoom": 1.4})


if __name__ == "__main__":
    unittest.main()
