"""
vazus_core.google_sync_engine — Compatibility bridge for GoogleSuperSyncEngine.
"""
from vazus_core.google_super_sync_engine import GoogleSuperSyncEngine as GoogleSyncEngine

class MarkdownTaskExtractor:
    """Extracts markdown tasks for sync."""
    @staticmethod
    def extract_tasks(text: str):
        import re
        return re.findall(r'- \[(?: |x)\] (.*)', text)

__all__ = ["GoogleSyncEngine", "MarkdownTaskExtractor"]
