"""
Unit tests for vazus_core.ast_pruner
Verifies AST signature extraction, body pruning, docstring preservation,
syntax validation, token reduction, and organic_memory logging.
"""

import unittest
import os
import sqlite3
from vazus_core.ast_pruner import ASTPruner
from vazus_core.organic_memory_bridge import search_memory, DB_PATH

class TestASTPruner(unittest.TestCase):

    def setUp(self):
        self.sample_code = '''
class DataProcessor:
    """Processes incoming data frames with vector embeddings."""
    
    def __init__(self, name: str, batch_size: int = 64) -> None:
        """Initialize DataProcessor with configuration."""
        self.name = name
        self.batch_size = batch_size
        self.data_store = []
        for i in range(100):
            self.data_store.append(f"item_{i}")

    async def process_async(self, items: list[dict], threshold: float = 0.95) -> dict[str, float]:
        """
        Process items asynchronously and compute confidence scores.
        
        Args:
            items: input items to evaluate
            threshold: minimum score cutoff
        Returns:
            dictionary of item id to confidence
        """
        results = {}
        for item in items:
            score = len(item) * threshold
            if score > threshold:
                results[item.get("id", "unk")] = score
        return results

def standalone_function(x: int, y: int = 10) -> int:
    """Adds x and y."""
    temp = x * 2
    temp2 = temp + y
    return temp2
'''

    def test_prune_ast_validity(self):
        pruned = ASTPruner.prune_ast(self.sample_code)
        self.assertTrue(ASTPruner.validate_signatures(pruned))
        self.assertIn("class DataProcessor:", pruned)
        self.assertIn("def __init__(self, name: str, batch_size: int=64) -> None:", pruned)
        self.assertIn('"""Initialize DataProcessor with configuration."""', pruned)
        self.assertIn("async def process_async(self, items: list[dict], threshold: float=0.95) -> dict[str, float]:", pruned)
        self.assertIn("...", pruned)
        # Verify internal implementation loops/vars are pruned
        self.assertNotIn("self.data_store.append", pruned)
        self.assertNotIn("results[item.get", pruned)

    def test_extract_signatures(self):
        sig = ASTPruner.extract_signatures(self.sample_code)
        self.assertEqual(len(sig["classes"]), 1)
        cls_info = sig["classes"][0]
        self.assertEqual(cls_info["name"], "DataProcessor")
        self.assertEqual(len(cls_info["methods"]), 2)
        method_names = [m["name"] for m in cls_info["methods"]]
        self.assertIn("__init__", method_names)
        self.assertIn("process_async", method_names)

    def test_prune_and_log_large_file(self):
        target_file = r"C:\vazus\vazus_core\integrations\kgb_analytical_extractor.py"
        pruned_code, stats = ASTPruner.prune_file(target_file, log_memory=True)
        self.assertTrue(stats["is_valid"])
        self.assertGreaterEqual(stats["reduction_percentage"], 70.0)
        
        # Verify memory log entry in vazus.db
        insights = search_memory("kgb_analytical_extractor.py")
        self.assertGreater(len(insights), 0)
        self.assertTrue(any(ins.get("category") in ("ast_pruner", "code_optimization") for ins in insights))

    def test_prune_vazus_core_db(self):
        target_file = r"C:\vazus\vazus_core\memory\db.py"
        pruned_code, stats = ASTPruner.prune_file(target_file, log_memory=True)
        self.assertTrue(stats["is_valid"])
        self.assertTrue(ASTPruner.validate_signatures(pruned_code))
        self.assertGreaterEqual(stats["reduction_percentage"], 70.0)
        self.assertIn("def init_db_schemas", pruned_code)
        self.assertIn("def get_db_connection", pruned_code)
        self.assertIn("def pack_vector_f32", pruned_code)
        self.assertIn("def unpack_vector_f32", pruned_code)


if __name__ == "__main__":
    unittest.main()

