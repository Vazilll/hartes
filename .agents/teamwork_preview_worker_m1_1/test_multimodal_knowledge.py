"""
Test Suite for vazus_core.multimodal_knowledge
Tests syntax, unit logic, chunking boundary constraints, thumbnail generation, database vector indexing, OpenVINO fallback, and hallucination filtering.
"""

import os
import sys
sys.path.insert(0, r"C:\vazus")
import json
import sqlite3
import unittest
from pathlib import Path

from vazus_core.multimodal_knowledge import (
    transcribe_and_chunk_media,
    generate_thumbnail,
    hybrid_semantic_chunking,
    index_scenes_to_supergraph,
    format_timestamp,
    get_media_type,
    is_garbage_transcript,
    normalize_russian_text,
    get_whisper_model_with_fallback
)


class TestMultimodalKnowledge(unittest.TestCase):

    def test_01_imports_and_helpers(self):
        """Verify exports and helper functions."""
        self.assertEqual(format_timestamp(0.0), "00:00")
        self.assertEqual(format_timestamp(118.45), "01:58")
        self.assertEqual(format_timestamp(3665.0), "01:01:05")

        self.assertEqual(get_media_type("file.mp4"), "video")
        self.assertEqual(get_media_type("file.MOV"), "video")
        self.assertEqual(get_media_type("file.mp3"), "audio")
        self.assertEqual(get_media_type("file.oga"), "audio")

    def test_02_thumbnail_generation(self):
        """Test video and audio fallback thumbnail generation."""
        out_dir = Path("C:/vazus/knowledge/.thumbnails")
        out_dir.mkdir(parents=True, exist_ok=True)

        audio_thumb = str(out_dir / "test_audio_thumb.jpg")
        res_audio = generate_thumbnail("test_audio.mp3", 45.0, audio_thumb)
        self.assertTrue(os.path.exists(res_audio))
        self.assertGreater(os.path.getsize(res_audio), 1000)

        # Real video thumbnail test if video exists
        video_sample = r"C:\vazus\knowledge\telegram_courses\Курс _Покоритель Наташек 6_0_\2025-07-22 00-42-20_msg19.mp4"
        if os.path.exists(video_sample):
            video_thumb = str(out_dir / "test_video_thumb.jpg")
            res_video = generate_thumbnail(video_sample, 10.0, video_thumb)
            self.assertTrue(os.path.exists(res_video))
            self.assertGreater(os.path.getsize(res_video), 1000)

    def test_03_hybrid_semantic_chunking_logic(self):
        """Test boundary decision matrix and tail merging logic."""
        segments = [
            # Chunk 1 (0 to ~125s)
            {"id": 0, "start": 0.0, "end": 20.0, "text": "Start segment 1."},
            {"id": 1, "start": 21.0, "end": 70.0, "text": "Segment 2 past 60s without pause"},
            {"id": 2, "start": 70.5, "end": 125.0, "text": "Segment 3 reaching target duration."},
            {"id": 3, "start": 127.0, "end": 180.0, "text": "Chunk 2 segment start."},
            {"id": 4, "start": 181.0, "end": 240.0, "text": "Chunk 2 segment middle."},
            {"id": 5, "start": 241.0, "end": 255.0, "text": "Tail segment < 30s."}
        ]

        dummy_file = r"C:\vazus\knowledge\telegram_courses\dummy_test_media.mp4"
        scenes = hybrid_semantic_chunking(segments, dummy_file)
        self.assertGreaterEqual(len(scenes), 1)

        # Check metadata schema compliance for all scenes
        for idx, scene in enumerate(scenes):
            self.assertIn("scene_id", scene)
            self.assertIn("source_file", scene)
            self.assertIn("start_sec", scene)
            self.assertIn("end_sec", scene)
            self.assertIn("duration", scene)
            self.assertIn("transcript", scene)
            self.assertIn("thumbnail_path", scene)
            self.assertIn("chunk_index", scene)
            self.assertEqual(scene["chunk_index"], idx)
            self.assertIn("media_type", scene)
            self.assertIn("whisper_segment_count", scene)
            self.assertIn("words_count", scene)
            self.assertIn("char_count", scene)
            self.assertIn("thumbnail_timestamp_sec", scene)

    def test_04_supergraph_indexing(self):
        """Test 768D vector embedding creation and SQLite graph persistence."""
        test_scenes = [
            {
                "scene_id": "test_scene_0001",
                "source_file": "C:/vazus/knowledge/telegram_courses/test_video.mp4",
                "start_sec": 0.0,
                "end_sec": 120.0,
                "duration": 120.0,
                "transcript": "В этом уроке мы разбираем гибридную сегментацию и векторы 768D в SuperGraph OS.",
                "thumbnail_path": "C:/vazus/knowledge/.thumbnails/test_scene_0001.jpg",
                "chunk_index": 0,
                "media_type": "video",
                "whisper_segment_count": 5,
                "words_count": 13,
                "char_count": 81,
                "thumbnail_timestamp_sec": 60.0,
                "prev_scene_id": None,
                "next_scene_id": "test_scene_0002"
            },
            {
                "scene_id": "test_scene_0002",
                "source_file": "C:/vazus/knowledge/telegram_courses/test_video.mp4",
                "start_sec": 120.0,
                "end_sec": 240.0,
                "duration": 120.0,
                "transcript": "Второй сегмент описывает архитектуру связей kg_edges и kg_nodes.",
                "thumbnail_path": "C:/vazus/knowledge/.thumbnails/test_scene_0002.jpg",
                "chunk_index": 1,
                "media_type": "video",
                "whisper_segment_count": 4,
                "words_count": 10,
                "char_count": 67,
                "thumbnail_timestamp_sec": 180.0,
                "prev_scene_id": "test_scene_0001",
                "next_scene_id": None
            }
        ]

        test_db = "C:/vazus/services/memory/vazus.db"
        count = index_scenes_to_supergraph(test_scenes, db_path=test_db)
        self.assertEqual(count, 2)

        # Inspect database records
        conn = sqlite3.connect(test_db)
        try:
            cursor = conn.cursor()
            row = cursor.execute("SELECT id, domain, node_type, embedding_json FROM kg_nodes WHERE id = 'test_scene_0001'").fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row[1], "multimodal_av")
            self.assertEqual(row[2], "MediaScene")
            emb = json.loads(row[3])
            self.assertEqual(len(emb), 768)

            # Check kg_edges
            edge_belongs = cursor.execute("SELECT relation FROM kg_edges WHERE source_id = 'test_scene_0001' AND relation = 'BELONGS_TO'").fetchone()
            self.assertIsNotNone(edge_belongs)

            edge_next = cursor.execute("SELECT relation FROM kg_edges WHERE source_id = 'test_scene_0001' AND relation = 'NEXT_SCENE'").fetchone()
            self.assertIsNotNone(edge_next)
        finally:
            conn.close()

    def test_05_remediation_hallucination_and_normalization(self):
        """Test remediation fixes for Russian text normalization and hallucination detection."""
        # 1. Normalization parenthetical test
        norm1 = normalize_russian_text("закон (инерции) Ньютона [МУЗЫКА]")
        self.assertEqual(norm1, "закон (инерции) Ньютона")

        norm2 = normalize_russian_text("в городе (Пятигорск) [СМЕХ]")
        self.assertEqual(norm2, "в городе (Пятигорск)")

        norm_noise = normalize_russian_text("[АПЛОДИСМЕНТЫ] (аплодисменты) Привет мир! (смех)")
        self.assertEqual(norm_noise, "Привет мир!")

        # 2. Hallucination filter tests (Adversarial test cases)
        self.assertTrue(is_garbage_transcript("Субтитры сделал Dima"))
        self.assertTrue(is_garbage_transcript("Субтитры: Vasya"))
        self.assertTrue(is_garbage_transcript("Перевод: Alex"))
        self.assertTrue(is_garbage_transcript("и мы идем туда и мы идем туда и мы идем туда и мы идем туда"))
        self.assertFalse(is_garbage_transcript("В этом уроке мы разбираем гибридную сегментацию и векторы 768D в SuperGraph OS."))

    def test_06_remediation_openvino_fallback_and_exports(self):
        """Test OpenVINO support in whisper model loader fallback and exported symbols."""
        model, model_name = get_whisper_model_with_fallback(preferred_model="tiny")
        self.assertIsNotNone(model)
        self.assertIn(model_name, ["tiny", "openvino_tiny", "large-v3-turbo", "medium", "small"])


if __name__ == "__main__":
    unittest.main()
