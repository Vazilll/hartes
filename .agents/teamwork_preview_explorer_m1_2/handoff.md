# Handoff Report — Milestone 1 (R1: High-Precision ASR Upgrade)

**Agent**: Explorer 2  
**Target Module**: `C:\vazus\vazus_core\multimodal_knowledge.py`  
**Master Spec**: `C:\vazus\.agents\orchestrator\PROJECT.md`  

---

## 1. Observation

- **Primary Target File**: `C:\vazus\vazus_core\multimodal_knowledge.py` (451 lines).
- **Interface Contract (`PROJECT.md` line 25)**:
  ```python
  transcribe_media_high_precision(file_path: str, model_name: str = "large-v3-turbo") -> List[Dict]
  ```
  *Includes Russian speech normalization and garbage/hallucination transcript filtering.*
- **Current File State (`multimodal_knowledge.py`)**:
  - `transcribe_media_high_precision` is **missing** from `multimodal_knowledge.py`.
  - Line 24: `get_whisper_model(model_size: str = "tiny", device: str = "cpu", compute_type: str = "int8")` uses `"tiny"` by default.
  - Line 153: `transcribe_and_chunk_media` calls `get_whisper_model("tiny", device="cpu", compute_type="int8")` and `model.transcribe(file_path, beam_size=1)` without `vad_filter`, `language="ru"`, text normalization, or hallucination filtering.
  - Line 70-72: Audio extension check handles `.mp3`, `.oga`, `.m4a`, `.ogg`, `.wav`, `.flac`, but non-media files or unreadable streams need clean error handling.
- **Environment Verification**:
  - Task execution confirmed `faster_whisper` 1.2.1, `torch` 2.13.0+cpu, and `openvino` 2026.2.1 are installed in `C:\vazus\.venv`.

---

## 2. Logic Chain

1. **Observation**: `transcribe_media_high_precision` is required by `PROJECT.md` contract for Milestone 1, but is not defined in `vazus_core/multimodal_knowledge.py`.
   - **Inference**: Implementer must add `transcribe_media_high_precision` as the top-level high-precision function, while maintaining `transcribe_and_chunk_media` as a wrapper.
2. **Observation**: Currently, Whisper model defaults to `"tiny"` with `beam_size=1` and `vad_filter=False`.
   - **Inference**: Timestamp accuracy and word boundaries suffer from silence drift and low model capacity. Upgrading to `"large-v3-turbo"`/`"medium"` with `vad_filter=True` and `vad_parameters=dict(min_silence_duration_ms=500)` will eliminate silence timestamps and improve segment `start_sec` and `end_sec` alignment.
3. **Observation**: No text cleaning or hallucination checks are applied to segment text.
   - **Inference**: Implementer must add `normalize_russian_text()` to strip bracketed noise tags (`[МУЗЫКА]`) and `is_garbage_transcript()` to filter repetitive hallucinated phrases (`"Субтитры создал..."`, `"да да да..."`).
4. **Observation**: Model loading hardcodes a single size without automatic memory/download failure handling.
   - **Inference**: Implement `get_whisper_model_with_fallback(preferred_model="large-v3-turbo")` to seamlessly attempt `"large-v3-turbo"` -> `"medium"` -> `"small"` -> `"tiny"`.

---

## 3. Caveats

- **Model Download**: First invocation of `"large-v3-turbo"` will trigger `faster_whisper` downloading the model weights (~1.5 GB) from HuggingFace to local cache (`~/.cache/huggingface/hub`). Ensure network connectivity or rely on fallback cascade if offline.
- **CPU Speed**: On low-core CPUs, `large-v3-turbo` with `beam_size=5` can take longer per audio minute than `beam_size=1`. Implementer should allow `beam_size` parameter configuration.

---

## 4. Conclusion

`multimodal_knowledge.py` requires an upgrade to implement `transcribe_media_high_precision` matching the master contract spec. This upgrade requires:
1. Adding `normalize_russian_text()` and `is_garbage_transcript()`.
2. Implementing cascading model fallback (`large-v3-turbo` -> `medium` -> `small` -> `tiny`).
3. Adding `transcribe_media_high_precision()` with `vad_filter=True`, `compute_type="int8"`, `cpu_threads=4`, and `language="ru"`.
4. Updating `transcribe_and_chunk_media()` to route through `transcribe_media_high_precision()` for backward compatibility.

---

## 5. Verification Method

To verify the implementation once applied:

1. **Contract Signature & Imports**:
   ```cmd
   C:\vazus\.venv\Scripts\python.exe -c "from vazus_core.multimodal_knowledge import transcribe_media_high_precision, transcribe_and_chunk_media; print('Import successful!')"
   ```
2. **High-Precision Transcription Test**:
   ```cmd
   C:\vazus\.venv\Scripts\python.exe -c "from vazus_core.multimodal_knowledge import transcribe_media_high_precision; res = transcribe_media_high_precision(r'C:\vazus\knowledge\telegram_courses\Курс _Покоритель Наташек 6_0_\media_174.oga', model_name='large-v3-turbo'); print(f'Generated {len(res)} scenes'); print(res[0] if res else 'No scenes')"
   ```
3. **Validation Invalidation Criteria**:
   - If `transcribe_media_high_precision` fails to return scenes or throws `AttributeError`/`ImportError`.
   - If hallucinated subtitle lines are preserved in the final transcript.
