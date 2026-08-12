## 2026-07-24T12:25:12Z

You are Worker 1 for Milestone 1 (R1: High-Precision ASR Upgrade in `vazus_core/multimodal_knowledge.py`).
Working directory: C:\vazus\.agents\teamwork_preview_worker_m1_1
Master spec: C:\vazus\.agents\orchestrator\PROJECT.md
Explorer Handoffs:
- C:\vazus\.agents\teamwork_preview_explorer_m1_1\handoff.md
- C:\vazus\.agents\teamwork_preview_explorer_m1_2\handoff.md
- C:\vazus\.agents\teamwork_preview_explorer_m1_3\handoff.md

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Your objectives:
1. Update / create `C:\vazus\vazus_core\multimodal_knowledge.py` to implement:
   - `get_whisper_model_with_fallback(preferred_model: str = "large-v3-turbo")` supporting `large-v3-turbo` with fallbacks to `medium`, `small`, `tiny`.
   - `normalize_russian_text(text: str) -> str` to clean noise tags (`[МУЗЫКА]`, `[АПЛОДИСМЕНТЫ]`), whitespace, numbers/punctuation for Russian speech.
   - `is_garbage_transcript(text: str) -> bool` to detect Whisper hallucination loops (e.g. "Субтитры", "Продолжение следует", repetitive n-grams).
   - `transcribe_media_high_precision(file_path: str, model_name: str = "large-v3-turbo") -> List[Dict]` with `vad_filter=True`, `compute_type="int8"`, `language="ru"`, returning scene dictionaries (`scene_id`, `source_file`, `start_sec`, `end_sec`, `transcript`, `thumbnail_path`).
   - `transcribe_and_chunk_media(file_path: str) -> List[Dict]` calling `transcribe_media_high_precision`.
   - `generate_thumbnail(video_path: str, timestamp_sec: float, output_path: str) -> str` extracting video frame at timestamp or generating audio fallback card thumbnail in `C:\vazus\knowledge\.thumbnails\`.
   - `index_scenes_to_supergraph(scenes: List[Dict], db_path: str)` indexing scenes into `vazus.db` with 768D embeddings via `UnifiedEmbeddingManager`.
2. Run build and test verification using `C:\vazus\.venv\Scripts\python.exe`:
   - Verify syntax: `python.exe -m py_compile C:\vazus\vazus_core\multimodal_knowledge.py`
   - Run test import and execution on sample file `C:\vazus\knowledge\telegram_courses\Курс _Покоритель Наташек 6_0_\media_174.oga` or another media file in `C:\vazus\knowledge`.
3. Document exact build/test output in your `handoff.md` and send a message back to parent.
