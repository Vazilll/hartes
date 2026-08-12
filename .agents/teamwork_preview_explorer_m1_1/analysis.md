# Architectural & Technical Analysis: High-Precision ASR Upgrade (Milestone 1 / R1)

**Author**: Explorer 1  
**Target Module**: `C:\vazus\vazus_core\multimodal_knowledge.py`  
**Date**: 2026-07-24  
**Project Spec**: `C:\vazus\.agents\orchestrator\PROJECT.md`  

---

## 1. Executive Summary

Milestone 1 upgrades `vazus_core/multimodal_knowledge.py` from a baseline `tiny` Whisper model to a **High-Precision ASR Engine** supporting `large-v3-turbo` with `medium` fallback, optimized for PyTorch CPU and OpenVINO 2026.2.1 execution. The upgrade introduces Russian speech text normalization, multi-layered hallucination filtering (n-gram repetition detection, low-confidence scores, subtitle loop suppression), and implements the required `transcribe_media_high_precision` interface contract.

---

## 2. Current Codebase Investigation (`vazus_core/multimodal_knowledge.py`)

### 2.1 Model Initialization & Transcribe Call
- **Current State**:
  - `get_whisper_model` in lines 24–34 lazy-loads `faster_whisper.WhisperModel(model_size, device=device, compute_type=compute_type)`.
  - `transcribe_and_chunk_media` (line 153) hardcodes:
    ```python
    model = get_whisper_model("tiny", device="cpu", compute_type="int8")
    ```
  - Fallback ASR (lines 168–202) utilizes `av` (PyAV) + `transformers.pipeline('automatic-speech-recognition', model='openai/whisper-tiny')`.

### 2.2 Critical Gaps
1. **Hardcoded Model**: Uses `tiny` (poor accuracy for complex Russian speech/technical terms).
2. **Missing Interface Contract**: Missing `transcribe_media_high_precision(file_path: str, model_name: str = "large-v3-turbo") -> List[Dict]` specified in `PROJECT.md` (line 25).
3. **No Text Normalization**: Transcripts preserve raw Whisper artifacts (`[музыка]`, `(смех)`, `ё`/`е` inconsistency, double punctuation).
4. **No Hallucination/Garbage Filtering**: No detection of subtitle loops ("Спасибо за просмотр", "Субтитры"), high `no_speech_prob`, or repetitive n-gram loops.
5. **No OpenVINO / Optimum Intel Utilization**: Installed OpenVINO 2026.2.1 and Optimum Intel are idle during transcription.

---

## 3. Environment & Hardware Capabilities (`C:\vazus\.venv`)

Verified via diagnostic script executions:

| Component / Library | Version | Status | Device Support / Notes |
|---------------------|---------|--------|------------------------|
| **faster-whisper** | `1.2.1` | Verified | CTranslate2 4.8.1 backend (`int8` CPU verified: successfully downloaded & loaded `large-v3-turbo`) |
| **OpenVINO** | `2026.2.1` | Installed | Devices detected: `['CPU', 'GPU', 'NPU']` |
| **Optimum Intel** | Installed | Installed | `optimum.intel.openvino.OVModelForSpeechSeq2Seq` available |
| **PyTorch** | `2.13.0+cpu` | Installed | PyTorch CPU fallback backend |
| **torchaudio** | `2.11.0+cpu` | Installed | Audio decoding / tensor processing |
| **transformers** | `5.0.0` | Installed | HuggingFace ASR pipeline |
| **av (PyAV)** | `18.0.0` | Installed | Container audio stream resampling (16kHz mono) |
| **whisper (openai-whisper)** | N/A | Not Installed | Rely on `faster_whisper` and `optimum.intel` |

---

## 4. High-Precision Model Selection & Fallback Strategy

### 4.1 Recommended Strategy Hierarchy
1. **Primary High-Precision Model**: `large-v3-turbo`
   - *Rationale*: ~8x speedup over `large-v3` with equivalent WER on Russian speech.
   - *Cache Directory*: Store in `C:/vazus/knowledge/.whisper_cache` to prevent re-downloads.
2. **Secondary Fallback Model**: `medium`
   - Triggered if `large-v3-turbo` load fails due to memory allocation or download issues.
3. **Micro Fallback Model**: `small` or `tiny`
   - Final safety net for constrained RAM environments (< 4GB free).

### 4.2 Engine Fallback Cascade
```
Rank 1: faster-whisper (CTranslate2 int8 / int8_float32 on CPU)
   └─► Failure? Rank 2: Optimum Intel OpenVINO (OVModelForSpeechSeq2Seq on CPU/NPU)
          └─► Failure? Rank 3: PyTorch Transformers Pipeline (openai/whisper-large-v3-turbo on CPU)
```

---

## 5. Russian Speech Text Normalization

### 5.1 Normalization Pipeline Rules
1. **Hallucinated Tag Removal**:
   - Regex: `r'\[.*?\]|\(.*?\)|<.*?>'`
   - Replaces noise markers (`[Музыка]`, `(смех)`, `<|nospeech|>`) with whitespace.
2. **Cyrillic Character Standardization**:
   - Replace `Ё` -> `Е` and `ё` -> `е`. Ensures search uniformity and consistent vector embeddings across Russian texts.
3. **Control & Zero-Width Character Strip**:
   - Regex: `r'[\u200b\ufeff\u200e\u200f]'` -> `""`.
4. **Punctuation & Quote Normalization**:
   - Quotes: `«` `»` `“` `”` -> `"`.
   - Dashes: `—` `–` -> `-`.
   - Repetitive Punctuation: `\.{2,}` -> `.`, `!{2,}` -> `!`, `\?{2,}` -> `?`.
5. **Whitespace Collapsing**:
   - Regex: `r'\s+'` -> `' '`, `.strip()`.

### 5.2 Python Implementation Code Snippet
```python
import re

def normalize_russian_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r'\[.*?\]|\(.*?\)|<.*?>', ' ', text)
    text = text.replace('Ё', 'Е').replace('ё', 'е')
    text = re.sub(r'[\u200b\ufeff\u200e\u200f]', '', text)
    text = re.sub(r'[«»“”]', '"', text)
    text = re.sub(r'[—–]', '-', text)
    text = re.sub(r'\.{2,}', '.', text)
    text = re.sub(r'!{2,}', '!', text)
    text = re.sub(r'\?{2,}', '?', text)
    return re.sub(r'\s+', ' ', text).strip()
```

---

## 6. Garbage & Hallucination Transcript Filtering

Whisper models on quiet audio or music segments frequently hallucinate repetitive phrases or standard YouTube subtitle closing credits.

### 6.1 Multi-Layer Filtering Algorithm
1. **Known Subtitle Hallucination Regex**:
   - Matches phrases (case-insensitive):
     `спасибо за просмотр`, `субтитры`, `подписывайтесь на канал`, `до скорой встречи`, `продолжение следует`, `редактор субтитров`, `переводчик`, `ставьте лайк`, `сообщество`, `бай бай`, `thank you for watching`, `subscribe`, `amara\.org`.
2. **Repetitive N-Gram Loop Detector**:
   - Single word count > 50% of total segment words (for word count >= 6).
   - 2-word phrase count >= 3 occurring in >= 40% of bigrams (e.g. "да да да да да").
3. **Whisper Metadata Quality Score Thresholds**:
   - `no_speech_prob > 0.6`
   - `avg_logprob < -1.2`
   - `compression_ratio > 2.4`
4. **Noise / Short Character Filter**:
   - Transcripts with fewer than 3 alphanumeric characters after normalization.

---

## 7. Interface Contract Specification & Implementation Plan

### 7.1 Interface Contract
`vazus_core/multimodal_knowledge.py` must export:
```python
def transcribe_media_high_precision(
    file_path: str,
    model_name: str = "large-v3-turbo",
    device: str = "cpu",
    compute_type: str = "int8"
) -> List[Dict[str, Any]]
```

### 7.2 Return Schema
Returns list of scene dicts, where each transcript is normalized and filtered:
```json
{
  "scene_id": "scene_a1b2c3d4e5f6",
  "source_file": "C:/vazus/knowledge/media.mp4",
  "start_sec": 0.0,
  "end_sec": 120.0,
  "duration": 120.0,
  "transcript": "Привет всем, сегодня мы обсудим архитектуру vazus SuperGraph OS.",
  "thumbnail_path": "C:/vazus/knowledge/.thumbnails/thumb_scene_a1b2c3d4e5f6.jpg",
  "chunk_index": 0,
  "media_type": "video",
  "whisper_segment_count": 5,
  "words_count": 9,
  "char_count": 65,
  "prev_scene_id": null,
  "next_scene_id": "scene_b2c3d4e5f6g7"
}
```

---

## 8. Proposed Patch Sketch for Implementer

```python
# Proposed addition to vazus_core/multimodal_knowledge.py

def transcribe_media_high_precision(
    file_path: str,
    model_name: str = "large-v3-turbo",
    output_thumbnail_dir: str = "C:/vazus/knowledge/.thumbnails"
) -> List[Dict[str, Any]]:
    """
    High-precision ASR entrypoint with large-v3-turbo/medium model fallback,
    Russian speech text normalization, and hallucination filtering.
    """
    return transcribe_and_chunk_media(
        file_path=file_path,
        output_thumbnail_dir=output_thumbnail_dir,
        model_name=model_name
    )
```

---

## 9. Verification Plan

1. **Syntax Check**: `C:\vazus\.venv\Scripts\python.exe -m py_compile C:\vazus\vazus_core\multimodal_knowledge.py`
2. **Function Verification**: Execute test script asserting:
   - `transcribe_media_high_precision` exists and runs without error.
   - Text normalization strips tags and converts `ё` -> `е`.
   - Garbage filtering rejects "Спасибо за просмотр" and "да да да да".
