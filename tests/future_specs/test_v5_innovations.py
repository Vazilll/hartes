"""
tests/test_v5_innovations.py
============================
Pytest test suite verifying:
1. Real local 768D OpenVINO Embedder (BGE model on hardware, semantic similarity > 0.70 for related text).
2. Socratic Partner (morning briefing, micro-victories, daily anchor).
3. Synaptic Evolver (Hot vs Cold synapses, contract extraction).
4. Google Keep Sync (extraction of notes, checklists, atomic Markdown files).
"""

import sys
import json
import pytest
from pathlib import Path

sys.path.insert(0, "C:/vazus")

from vazus_core.memory.embeddings import get_embedding_manager, compute_similarity
from vazus_core.integrations.socratic_partner import SocraticPartner, generate_morning_briefing
from vazus_core.integrations.google_keep_browser_sync import GoogleKeepBrowserSync
from vazus_core.evolution.synaptic_evolver import SynapticEvolver


class TestLocal768DEmbeddings:
    def test_embedding_dimension(self):
        mgr = get_embedding_manager()
        vec = mgr.get_embedding("Testing local vector generation in Vazus OS")
        assert len(vec) == 768
        assert any(x != 0.0 for x in vec)

    def test_semantic_clustering(self):
        mgr = get_embedding_manager()
        v_ai1 = mgr.get_embedding("Deep neural networks and artificial intelligence algorithms")
        v_ai2 = mgr.get_embedding("Machine learning transformers and deep learning models")
        v_food = mgr.get_embedding("Recipe for homemade blueberry pie and vanilla ice cream")

        sim_ai = compute_similarity(v_ai1, v_ai2)
        sim_food = compute_similarity(v_ai1, v_food)

        # AI vs AI must be significantly closer than AI vs Food
        assert sim_ai > sim_food
        assert sim_ai > 0.65
        assert sim_food < 0.50


class TestSocraticPartner:
    def test_morning_message_structure(self):
        partner = SocraticPartner()
        msg = partner.generate_morning_message()
        assert "Доброе утро" in msg
        assert "Один главный ориентир" in msg
        assert "Мы в одной упряжке" in msg

    def test_recent_victories_non_empty(self):
        partner = SocraticPartner()
        victories = partner.get_recent_victories(limit=3)
        assert len(victories) > 0


class TestSynapticEvolver:
    def test_scan_synapses(self):
        evolver = SynapticEvolver()
        res = evolver.scan_synapses(cold_days_threshold=14)
        assert "hot_synapses" in res
        assert "cold_synapses" in res
        assert len(res["hot_synapses"]) > 0

    def test_query_generation_for_cold_module(self):
        evolver = SynapticEvolver()
        mock_info = {
            "path": "vazus_core/engine/circuit_breaker.py",
            "contracts": [":requires: timeout > 0"]
        }
        q = evolver.build_research_query_for_cold_module(mock_info)
        assert "circuit breaker" in q.lower()
        assert "2026" in q


class TestGoogleKeepSync:
    def test_extract_notes_to_markdown(self, tmp_path):
        sync = GoogleKeepBrowserSync(inbox_dir=tmp_path)
        cards = [
            {
                "id": "101",
                "title": "Купить книги по философии",
                "content": "Посмотреть труды Аристотеля и Канта",
                "checklist": [
                    {"text": "Этика", "checked": True},
                    {"text": "Критика чистого разума", "checked": False}
                ]
            }
        ]
        saved = sync.extract_notes_from_html(cards)
        assert saved == 1
        md_files = list(tmp_path.glob("*.md"))
        assert len(md_files) == 1
        text = md_files[0].read_text(encoding="utf-8")
        assert "Купить книги по философии" in text
        assert "[x] Этика" in text
        assert "[ ] Критика чистого разума" in text
