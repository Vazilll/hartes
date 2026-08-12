# Detailed Analysis & Architectural Proposal: High-Precision ASR Upgrade (Milestone 1)

**Agent**: Explorer 2  
**Working Directory**: `C:\vazus\.agents\teamwork_preview_explorer_m1_2`  
**Target Module**: `C:\vazus\vazus_core\multimodal_knowledge.py`  
**Master Spec**: `C:\vazus\.agents\orchestrator\PROJECT.md`  

---

## Executive Summary

`vazus_core/multimodal_knowledge.py` is the core ASR, hybrid semantic scene chunking, and SuperGraph 768D vector indexing module for `vazus`. Currently, it uses a basic `"tiny"` Whisper model with `beam_size=1`, lacks voice activity detection (VAD), has no Russian speech normalization or hallucination transcript filtering, and lacks the explicit `transcribe_media_high_precision` entry point specified in `PROJECT.md`.

This analysis provides a comprehensive review across the 4 required focus areas and presents a detailed, production-ready implementation plan for the Implementer.

---

## 1. Focus Area Analysis

### 1.1 Timestamp Alignment & Scene Segmentation
- **Current State**:
  - `transcribe_and_chunk_media` invokes `model.transcribe(file_path, beam_size=1)` without VAD filtering.
  - Raw segment timestamps (`seg.start`, `seg.end`) are aggregated by the hybrid semantic chunking algorithm into 1–3 minute scene chunks (`MIN_DURATION_SEC = 60.0`, `TARGET_DURATION_SEC = 120.0`, `MAX_DURATION_SEC = 180.0`).
  - Without VAD filtering, long silences or ambient noise at the beginning/end of speech segments cause timestamp drift in `start_sec` and `end_sec`.
- **High-Precision Recommendations**:
  - **Model Upgrade**: Upgrading from `"tiny"` to `"large-v3-turbo"` or `"medium"` significantly reduces boundary jitter and misaligned word timings.
  - **VAD Filter Integration**: Enable `vad_filter=True` with `vad_parameters=dict(min_silence_duration_ms=500, threshold=0.5)` in `faster_whisper.WhisperModel.transcribe()`. This trims non-speech audio, ensuring `start_sec` and `end_sec` strictly encompass spoken content.
  - **Scene Timestamp Preservation**: The hybrid scene chunker calculates `start_sec` from the first segment's `start` and `end_sec` from the cut segment's `end`. Midpoint calculation (`midpoint_sec = round(st_sec + (duration / 2.0), 2)`) for keyframe thumbnail rendering remains exact.

### 1.2 Performance Optimization (CPU Execution Parameters)
- **Environment Context**:
  - Python virtual environment: `C:\vazus\.venv` (PyTorch 2.6.0+cpu, OpenVINO 2024.6.0, `faster_whisper` 1.1.1 installed).
  - CPU execution is required.
- **Optimal CPU Parameter Selection**:
  - `compute_type="int8"`: Provides 2x–4x CPU speedup with negligible precision loss. Supported natively by CTranslate2 on x86_64 CPUs with AVX2/AVX-512.
  - `cpu_threads`: Explicitly set to `4` (or `min(8, os.cpu_count() or 4)`) to maximize multi-threading performance without thread thrashing.
  - `beam_size`: Default to `5` for high-precision transcription (`large-v3-turbo`). For fast-mode batch runs, expose `beam_size=1` or `2`.
  - `vad_filter=True`: Skipping non-speech frames speeds up processing by 20–40% on typical lecture/media files.
  - `language="ru"`: Explicitly specifying Russian avoids language detection overhead (saving ~1-2 seconds per file) and prevents misidentifying Russian dialects.
  - `condition_on_previous_text=False`: Prevents hallucination repetition loops across quiet or noisy segments, accelerating inference.

### 1.3 Error Handling & Fallbacks
- **Non-Audio & Corrupted File Handling**:
  - Add explicit file validation: check file existence (`os.path.exists`), extension verification (`.mp3`, `.oga`, `.m4a`, `.ogg`, `.wav`, `.flac`, `.mp4`, `.mkv`, `.mov`, `.avi`, `.webm`).
  - Catch decoding/media errors (`av.AVError`, `RuntimeError`, `cv2.error`, `ffmpeg` errors) gracefully. If decoding fails, log a warning and return an empty scene list `[]` instead of raising an unhandled exception.
- **Model Fallback Cascade**:
  - Implement `get_whisper_model_with_fallback(preferred_model="large-v3-turbo", ...)` with fallback order:
    `"large-v3-turbo"` -> `"medium"` -> `"small"` -> `"tiny"`.
  - If loading a larger model fails due to memory constraints or missing local weights, log a warning and automatically fall back to the next model size.
  - Secondary ASR Fallback: Preserve the existing PyAV + HuggingFace `transformers` pipeline (`openai/whisper-tiny` or `openai/whisper-medium`) if `faster_whisper` fails entirely.
- **Russian Speech Normalization & Garbage Transcript Filtering**:
  - Implement `normalize_russian_text(text: str) -> str`: strips noise tags (`[МУЗЫКА]`, `(аплодисменты)`), standardizes punctuation, and removes double spaces.
  - Implement `is_garbage_transcript(text: str) -> bool`: filters common Whisper hallucination phrases (e.g. *"Субтитры создал..."*, *"Продолжение следует..."*, *"Спасибо за просмотр"*) and detects low-entropy repetitive word loops (e.g. *"да да да да да"*).

### 1.4 Interface Contract Verification (`PROJECT.md`)
- **Master Spec Requirements**:
  - `transcribe_media_high_precision(file_path: str, model_name: str = "large-v3-turbo") -> List[Dict]`
  - Includes Russian speech normalization and garbage/hallucination transcript filtering.
- **Contract Alignment**:
  - `transcribe_media_high_precision` is currently missing in `multimodal_knowledge.py`.
  - Resolution: Add `transcribe_media_high_precision(file_path: str, model_name: str = "large-v3-turbo", ...)` as the primary entry point.
  - Update `transcribe_and_chunk_media` to call `transcribe_media_high_precision` under the hood to ensure full backward compatibility with existing scripts (e.g., `telegram_indexer.py`).

---

## 2. Recommended Implementation Blueprint

The Implementer should apply the following additions and modifications to `C:\vazus\vazus_core\multimodal_knowledge.py`:

```python
# --- Russian Text Normalization & Hallucination Filter ---

RUSSIAN_HALLUCINATION_PATTERNS = [
    r"субтитры\s+создал.*",
    r"продолжение\s+следует.*",
    r"спасибо\s+за\s+просмотр.*",
    r"ставите\s+лайки.*",
    r"подписывайтесь\s+на\s+канал.*",
    r"перевод\s+и\s+озвучка.*",
    r"создано\s+в\s+сообществе.*",
]

def normalize_russian_text(text: str) -> str:
    """Normalizes Russian transcript text by cleaning noise tags and whitespace."""
    if not text:
        return ""
    text = re.sub(r'\[.*?\]|\(.*?\)', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def is_garbage_transcript(text: str) -> bool:
    """Identifies hallucinated or low-quality Whisper transcript lines."""
    if not text or len(text.strip()) < 2:
        return True
    text_lower = text.lower().strip()
    for pat in RUSSIAN_HALLUCINATION_PATTERNS:
        if re.search(pat, text_lower):
            return True
    words = text_lower.split()
    if len(words) >= 5:
        unique_words = set(words)
        if len(unique_words) / len(words) < 0.2:
            return True
    return False

# --- Model Loading with Cascading Fallback ---

MODEL_FALLBACK_ORDER = ["large-v3-turbo", "medium", "small", "tiny"]

def get_whisper_model_with_fallback(
    preferred_model: str = "large-v3-turbo",
    device: str = "cpu",
    compute_type: str = "int8",
    cpu_threads: int = 4
) -> Tuple[Optional[Any], str]:
    """Loads faster_whisper WhisperModel with automatic fallback cascade."""
    candidates = [preferred_model] + [m for m in MODEL_FALLBACK_ORDER if m != preferred_model]
    for model_name in candidates:
        key = f"{model_name}_{device}_{compute_type}_{cpu_threads}"
        if key in _WHISPER_MODEL_CACHE and _WHISPER_MODEL_CACHE[key] is not None:
            return _WHISPER_MODEL_CACHE[key], model_name
        try:
            from faster_whisper import WhisperModel
            model = WhisperModel(
                model_name,
                device=device,
                compute_type=compute_type,
                cpu_threads=cpu_threads
            )
            _WHISPER_MODEL_CACHE[key] = model
            return model, model_name
        except Exception as e:
            sys.stderr.write(f"[MultimodalKnowledge] Warning: failed to load '{model_name}' ({e}), trying fallback...\n")
            _WHISPER_MODEL_CACHE[key] = None
    return None, ""

# --- Primary High-Precision Entry Point ---

def transcribe_media_high_precision(
    file_path: str,
    model_name: str = "large-v3-turbo",
    device: str = "cpu",
    compute_type: str = "int8",
    cpu_threads: int = 4,
    beam_size: int = 5,
    vad_filter: bool = True,
    language: str = "ru",
    output_thumbnail_dir: str = "C:/vazus/knowledge/.thumbnails"
) -> List[Dict[str, Any]]:
    """
    High-Precision ASR Transcription matching PROJECT.md interface contract.
    """
    # 1. File & Media Extension Validation
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Media file not found: {file_path}")
    
    file_ext = os.path.splitext(file_path)[1].lower()
    supported_exts = ('.mp3', '.oga', '.m4a', '.ogg', '.wav', '.flac', '.mp4', '.mkv', '.mov', '.avi', '.webm')
    if file_ext not in supported_exts:
        sys.stderr.write(f"[MultimodalKnowledge] Warning: Unsupported media extension '{file_ext}' for file {file_path}\n")
        return []

    # 2. Load Model with Fallback
    model, loaded_model_name = get_whisper_model_with_fallback(
        preferred_model=model_name,
        device=device,
        compute_type=compute_type,
        cpu_threads=cpu_threads
    )

    raw_segments = []

    # 3. Execute faster-whisper Transcription
    if model is not None:
        try:
            segments_iter, info = model.transcribe(
                file_path,
                beam_size=beam_size,
                vad_filter=vad_filter,
                vad_parameters=dict(min_silence_duration_ms=500),
                language=language,
                condition_on_previous_text=False
            )
            for seg in segments_iter:
                norm_text = normalize_russian_text(seg.text)
                if not is_garbage_transcript(norm_text):
                    raw_segments.append({
                        "start": float(seg.start),
                        "end": float(seg.end),
                        "text": norm_text
                    })
        except Exception as e:
            sys.stderr.write(f"[MultimodalKnowledge] faster-whisper error on {file_path} ({e}), trying PyAV fallback\n")

    # 4. Fallback ASR Execution (PyAV + Transformers)
    if not raw_segments:
        # Fallback ASR logic with normalize_russian_text and is_garbage_transcript check
        ...

    if not raw_segments:
        return []

    # 5. Hybrid Semantic Scene Chunking & Metadata Building
    # ... (existing scene chunking and generate_thumbnail logic) ...
```

---

## 3. Risk Assessment & Verification Strategy

1. **Memory / CPU Load**: `large-v3-turbo` model in `int8` requires ~1.5 GB RAM. `medium` in `int8` requires ~1.0 GB RAM. The fallback mechanism prevents crashes if memory allocation fails.
2. **Backward Compatibility**: `transcribe_and_chunk_media` wraps `transcribe_media_high_precision`, ensuring all callers remain fully functional without code breaking.
3. **Verification**: Executing `python -c "from vazus_core.multimodal_knowledge import transcribe_media_high_precision"` and verifying scene output on test `.oga`/`.mp3` media files.
