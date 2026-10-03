"""
tests/test_multimodal_knowledge.py
Unit & Integration tests for vazus_core/multimodal_knowledge.py
"""

import os
import sys
import tempfile
import unittest

sys.stdout.reconfigure(encoding='utf-8')

from vazus_core.multimodal_knowledge import (
    get_whisper_model_with_fallback,
    normalize_russian_text,
    is_garbage_transcript,
    generate_thumbnail,
    transcribe_media_high_precision,
    transcribe_and_chunk_media,
    index_scenes_to_supergraph
)


class TestMultimodalKnowledge(unittest.TestCase):

    def test_normalize_russian_text(self):
        sample_raw = "[МУЗЫКА]  Приветствую  всех  слушателей! (аплодисменты) \xa0сегодня \u200bразберем тему. "
        normalized = normalize_russian_text(sample_raw)
        self.assertEqual(normalized, "Приветствую всех слушателей! сегодня разберем тему.")

    def test_is_garbage_transcript(self):
        self.assertTrue(is_garbage_transcript(""))
        self.assertTrue(is_garbage_transcript("   "))
        self.assertTrue(is_garbage_transcript("Субтитры создал DMM"))
        self.assertTrue(is_garbage_transcript("Продолжение следует"))
        self.assertTrue(is_garbage_transcript("да да да да да да"))
        self.assertFalse(is_garbage_transcript("В этом уроке мы обсудим построение архитектуры SuperGraph."))

    def test_get_whisper_model_with_fallback(self):
        model, loaded_name = get_whisper_model_with_fallback("tiny")
        self.assertIsNotNone(model, "Whisper model should not be None")
        self.assertTrue(any(base in loaded_name for base in ["large-v3-turbo", "medium", "small", "tiny"]), f"Loaded model {loaded_name} not in expected candidates")

    def test_generate_thumbnail_audio(self):
        courses_dir = os.environ.get("VAZUS_COURSES_DIR", r"C:\Users\Vaz\Videos\Courses")
        sample_audio = os.path.join(courses_dir, "Курс _Покоритель Наташек 6_0_", "media_174.oga")
        if os.path.exists(sample_audio):
            thumb_path = generate_thumbnail(sample_audio, 10.0)
            self.assertTrue(os.path.exists(thumb_path), f"Thumbnail file should exist at {thumb_path}")

    def test_transcribe_and_index_pipeline(self):
        courses_dir = os.environ.get("VAZUS_COURSES_DIR", r"C:\Users\Vaz\Videos\Courses")
        sample_media = os.path.join(courses_dir, "Курс _Покоритель Наташек 6_0_", "media_174.oga")
        if os.path.exists(sample_media):
            scenes = transcribe_and_chunk_media(sample_media)
            self.assertIsInstance(scenes, list)
            if scenes:
                first_scene = scenes[0]
                required_keys = ["scene_id", "source_file", "start_sec", "end_sec", "transcript", "thumbnail_path"]
                for k in required_keys:
                    self.assertIn(k, first_scene, f"Key {k} missing from scene dict")
                
                with tempfile.TemporaryDirectory() as tmp_dir:
                    test_db = os.path.join(tmp_dir, "test_vazus.db")
                    indexed_count = index_scenes_to_supergraph(scenes, db_path=test_db)
                    self.assertEqual(indexed_count, len(scenes))


if __name__ == "__main__":
    unittest.main()
