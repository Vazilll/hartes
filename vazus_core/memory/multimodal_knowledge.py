"""
vazus_core/multimodal_knowledge.py
Multimodal Knowledge Engine — High-Precision Transcriber, Text Normalizer, Hallucination Filter & SuperGraph 768D Vector Indexer.
"""

import os
import sys
import re
import json
import math
import hashlib
import sqlite3
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

# Lazy model singletons
_WHISPER_MODEL_CACHE: Dict[str, Any] = {}
_EMBEDDING_MANAGER_CACHE: Optional[Any] = None

__all__ = [
    "hybrid_semantic_chunking",
    "get_whisper_model_with_fallback",
    "normalize_russian_text",
    "is_garbage_transcript",
    "transcribe_media_high_precision",
    "transcribe_and_chunk_media",
    "generate_thumbnail",
    "index_scenes_to_supergraph",
    "format_timestamp",
    "get_media_type",
    "get_whisper_model",
    "get_embedding_manager",
]


def format_timestamp(seconds: float) -> str:
    """Formats timestamp in seconds to MM:SS or HH:MM:SS format."""
    total_sec = int(seconds)
    hours = total_sec // 3600
    minutes = (total_sec % 3600) // 60
    secs = total_sec % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes:02d}:{secs:02d}"


def get_media_type(filename: str) -> str:
    """Returns 'audio' or 'video' based on file extension."""
    ext = os.path.splitext(filename)[1].lower()
    audio_extensions = ('.mp3', '.oga', '.m4a', '.ogg', '.wav', '.flac', '.aac', '.opus')
    return "audio" if ext in audio_extensions else "video"


class _WhisperSegment:
    """Lightweight segment duck-type container for Whisper ASR outputs."""
    def __init__(self, start: float, end: float, text: str):
        self.start = float(start)
        self.end = float(end)
        self.text = text


class OpenVINOWhisperWrapper:
    """Wrapper around OpenVINO / optimum.intel.openvino models exposing .transcribe()."""
    def __init__(self, model: Any, processor: Any = None):
        self.model = model
        self.processor = processor

    def transcribe(
        self,
        file_path: Any,
        language: str = "ru",
        vad_filter: bool = True,
        vad_parameters: Optional[Dict[str, Any]] = None,
        beam_size: int = 5
    ) -> Tuple[List[_WhisperSegment], Dict[str, Any]]:
        if isinstance(file_path, np.ndarray):
            audio = file_path
        else:
            audio = load_audio_16k_mono(file_path)
        sr = 16000
        if len(audio) == 0:
            return [], {"language": language}
        if self.processor is not None:
            inputs = self.processor(audio, sampling_rate=sr, return_tensors="pt")
            generated_ids = self.model.generate(**inputs, max_new_tokens=448)
            transcription = self.processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
        else:
            transcription = ""
        duration_sec = float(len(audio) / sr)
        segments = [_WhisperSegment(0.0, duration_sec, transcription)]
        return segments, {"language": language}


def get_whisper_model_with_fallback(
    preferred_model: str = "large-v3-turbo",
    device: str = "cpu",
    compute_type: str = "int8"
) -> Tuple[Optional[Any], str]:
    """
    Attempts to load Whisper model with OpenVINO support (via optimum.intel.openvino or openvino)
    falling back through faster-whisper candidates ('large-v3-turbo', 'medium', 'small', 'tiny')
    and PyTorch CPU. Returns (model_instance, loaded_model_name).
    """
    candidates = [preferred_model, "large-v3-turbo", "medium", "small", "tiny"]
    unique_candidates = []
    for cand in candidates:
        if cand not in unique_candidates:
            unique_candidates.append(cand)

    # Pass 1: In-memory cache check
    for model_name in unique_candidates:
        cache_key = f"{model_name}_{device}_{compute_type}"
        if cache_key in _WHISPER_MODEL_CACHE and _WHISPER_MODEL_CACHE[cache_key] is not None:
            return _WHISPER_MODEL_CACHE[cache_key], model_name

    # Pass 2: faster_whisper local disk cache check (local_files_only=True) for instant C++ execution
    try:
        from faster_whisper import WhisperModel
        for model_name in unique_candidates:
            cache_key = f"{model_name}_{device}_{compute_type}"
            try:
                sys.stderr.write(f"[MultimodalKnowledge] Checking local cache for Whisper model '{model_name}'...\n")
                model = WhisperModel(model_name, device=device, compute_type=compute_type, cpu_threads=4, local_files_only=True)
                _WHISPER_MODEL_CACHE[cache_key] = model
                sys.stderr.write(f"[MultimodalKnowledge] Successfully loaded local Whisper model '{model_name}'.\n")
                return model, model_name
            except Exception:
                pass
    except Exception:
        pass

    # Pass 3: OpenVINO backend attempt via optimum.intel.openvino
    try:
        from optimum.intel.openvino import OVModelForSpeechSeq2Seq
        from transformers import AutoProcessor
        for model_name in unique_candidates:
            ov_cache_key = f"ov_{model_name}_{device}"
            if ov_cache_key in _WHISPER_MODEL_CACHE and _WHISPER_MODEL_CACHE[ov_cache_key] is not None:
                return _WHISPER_MODEL_CACHE[ov_cache_key], f"openvino_{model_name}"
            hf_repo = f"openai/whisper-{model_name}"
            try:
                ov_model = OVModelForSpeechSeq2Seq.from_pretrained(hf_repo, export=False, local_files_only=True)
                processor = AutoProcessor.from_pretrained(hf_repo, local_files_only=True)
                wrapper = OpenVINOWhisperWrapper(ov_model, processor)
                _WHISPER_MODEL_CACHE[ov_cache_key] = wrapper
                sys.stderr.write(f"[MultimodalKnowledge] Successfully loaded OpenVINO model '{hf_repo}'.\n")
                return wrapper, f"openvino_{model_name}"
            except Exception:
                pass
    except Exception:
        pass

    # Pass 4: Network download/load fallback
    for model_name in unique_candidates:
        cache_key = f"{model_name}_{device}_{compute_type}"
        try:
            sys.stderr.write(f"[MultimodalKnowledge] Downloading/loading Whisper model '{model_name}' ({device}, {compute_type})...\n")
            model = WhisperModel(model_name, device=device, compute_type=compute_type, cpu_threads=4)
            _WHISPER_MODEL_CACHE[cache_key] = model
            sys.stderr.write(f"[MultimodalKnowledge] Successfully loaded Whisper model '{model_name}'.\n")
            return model, model_name
        except Exception as e:
            sys.stderr.write(f"[MultimodalKnowledge] Warning: Failed to load Whisper model '{model_name}': {e}.\n")
            _WHISPER_MODEL_CACHE[cache_key] = None

    sys.stderr.write("[MultimodalKnowledge] Error: All Whisper fallback models failed to load.\n")
    return None, "none"


def get_whisper_model(model_size: str = "tiny", device: str = "cpu", compute_type: str = "int8"):
    """Legacy loader wrapper for faster-whisper WhisperModel instance."""
    model, _ = get_whisper_model_with_fallback(preferred_model=model_size, device=device, compute_type=compute_type)
    return model


def get_embedding_manager():
    """Lazy loader for UnifiedEmbeddingManager instance."""
    global _EMBEDDING_MANAGER_CACHE
    if _EMBEDDING_MANAGER_CACHE is None:
        try:
            from vazus_core.embeddings import UnifiedEmbeddingManager
        except ImportError:
            from embeddings import UnifiedEmbeddingManager
        _EMBEDDING_MANAGER_CACHE = UnifiedEmbeddingManager()
    return _EMBEDDING_MANAGER_CACHE


def normalize_russian_text(text: str) -> str:
    """
    Cleans noise tags ([МУЗЫКА], [АПЛОДИСМЕНТЫ], etc.),
    preserves parenthetical spoken text like '(инерции)' or '(Пятигорск)',
    removes noise parentheses like '(смех)', '(музыка)', '(аплодисменты)', '(шум)',
    normalizes whitespace and formatting for Russian speech transcripts.
    """
    if not text:
        return ""

    # 1. Remove bracketed noise tags [МУЗЫКА], [АПЛОДИСМЕНТЫ], [LAUGHTER], etc.
    text = re.sub(r'\[[^\]]*\]', ' ', text)

    # 2. Remove parenthetical noise tags ONLY (e.g. (смех), (музыка), (аплодисменты), (шум), (кашель), (вздох), (пауза), (тишина), (laughter), (music), (applause))
    noise_paren_pattern = r'\(\s*(?:музыка|смех|аплодисменты|шум|кашель|вздох|пауза|тишина|laughter|music|applause)\s*\)'
    text = re.sub(noise_paren_pattern, ' ', text, flags=re.IGNORECASE)

    # 3. Replace non-breaking spaces and zero-width spaces
    text = text.replace('\xa0', ' ').replace('\u200b', '')

    # 4. Normalize multiple spaces and newlines to a single space
    text = re.sub(r'\s+', ' ', text).strip()

    return text


def is_garbage_transcript(text: str) -> bool:
    """
    Detects Whisper hallucination loops (e.g. 'Субтитры', 'Субтитры сделал Dima', 'Перевод: Alex',
    repetitive n-grams, 3+ word phrase loops, or empty transcripts).
    """
    if not text or not text.strip():
        return True

    norm = text.strip().lower()
    if len(norm) < 2:
        return True

    # Regex patterns for subtitle credits, translators, voiceovers, and Whisper ASR hallucinations
    garbage_patterns = [
        r'\bсубтитры\b',
        r'\bперевод\b',
        r'\bозвучка\b',
        r'\bредактор\s+субтитров\b',
        r'\bспасибо\s+за\s+просмотр\b',
        r'\bпродолжение\s+следует\b',
        r'\bподпишитесь\b',
        r'\bставьте\s+лайк',
        r'\bдо\s+новых\s+встреч\b',
        r'\bблагодарю\s+за\s+внимание\b',
        r'\bкопирайт\b',
        r'\bamara\.org\b',
        r'\bdima\b',
        r'\bсообщество\s+vk\b',
        r'\byandex\b',
        r'^\s*название\s+фильма',
        r'^\s*конец\s+фильма',
    ]

    for pat in garbage_patterns:
        if re.search(pat, norm):
            return True

    # Extract words for n-gram and loop analysis
    words = [w for w in re.split(r'\W+', norm) if w]
    if not words:
        return True

    n_words = len(words)

    # 1-gram repetition (e.g. "да да да да")
    if n_words >= 4:
        from collections import Counter
        counts = Counter(words)
        most_common_word, max_count = counts.most_common(1)[0]
        if max_count / n_words >= 0.60 or (max_count >= 4 and len(counts) <= 2):
            return True

    # 2-gram repetition (e.g. "так так так так")
    if n_words >= 4:
        from collections import Counter
        bigrams = [f"{words[i]} {words[i+1]}" for i in range(n_words - 1)]
        bigram_counts = Counter(bigrams)
        top_bigram, top_count = bigram_counts.most_common(1)[0]
        if top_count >= 3 and (top_count * 2) / n_words >= 0.50:
            return True

    # 3-gram repetition
    if n_words >= 6:
        from collections import Counter
        trigrams = [f"{words[i]} {words[i+1]} {words[i+2]}" for i in range(n_words - 2)]
        trigram_counts = Counter(trigrams)
        top_trigram, top_count = trigram_counts.most_common(1)[0]
        if top_count >= 3 and (top_count * 3) / n_words >= 0.50:
            return True

    # 4-gram repetition
    if n_words >= 8:
        from collections import Counter
        quadgrams = [f"{words[i]} {words[i+1]} {words[i+2]} {words[i+3]}" for i in range(n_words - 3)]
        quad_counts = Counter(quadgrams)
        top_quad, top_count = quad_counts.most_common(1)[0]
        if top_count >= 2 and (top_count * 4) / n_words >= 0.45:
            return True

    # Multi-word phrase loop detection (e.g. 3+ word repeated phrases)
    if n_words >= 6:
        for k in range(3, min(12, n_words // 2 + 1)):
            phrase_str = " ".join(words[:k])
            rest_str = " ".join(words)
            pattern = rf'({re.escape(phrase_str)}\s*){{2,}}'
            match = re.search(pattern, rest_str)
            if match and len(match.group(0).split()) / n_words >= 0.45:
                return True

    return False


def generate_thumbnail(
    video_path: str,
    timestamp_sec: float,
    output_path: str = ""
) -> str:
    """
    Extracts keyframe at timestamp_sec from video_path or renders dark-mode preview card for audio/corrupt video.
    Saves image as JPEG to output_path and returns the absolute file path string.
    """
    default_thumb_dir = "C:/vazus/knowledge/.thumbnails"
    os.makedirs(default_thumb_dir, exist_ok=True)

    if not output_path or os.path.isdir(output_path):
        target_dir = output_path if (output_path and os.path.isdir(output_path)) else default_thumb_dir
        hash_key = hashlib.sha256(f"{video_path}:{timestamp_sec:.2f}".encode("utf-8")).hexdigest()[:12]
        output_path = os.path.join(target_dir, f"thumb_{hash_key}.jpg")

    parent_dir = os.path.dirname(output_path)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)

    file_ext = os.path.splitext(video_path)[1].lower()
    is_audio = file_ext in ('.mp3', '.oga', '.m4a', '.ogg', '.wav', '.flac', '.aac', '.opus')

    # Audio Media Card Rendering
    if is_audio:
        img = Image.new('RGB', (320, 180), color='#181C24')
        draw = ImageDraw.Draw(img)
        bars = [20, 45, 75, 110, 85, 130, 95, 60, 40, 90, 120, 70, 30]
        start_x = 45
        for i, h in enumerate(bars):
            x0 = start_x + i * 18
            y1 = 140
            y0 = y1 - h
            color = '#6366F1' if i % 2 == 0 else '#818CF8'
            draw.rectangle([x0, y0, x0 + 10, y1], fill=color)
        
        # Audio Tag Badge
        draw.rectangle([10, 10, 75, 30], fill='#4F46E5')
        draw.text((16, 13), "AUDIO", fill='#FFFFFF')
        img.save(output_path, 'JPEG', quality=85)
        return os.path.abspath(output_path).replace('\\', '/')

    # Video Media Frame Seeking via OpenCV
    frame_read_success = False
    rgb_frame = None

    try:
        cap = cv2.VideoCapture(video_path)
        if cap.isOpened():
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            if total_frames > 0:
                target_msec = float(timestamp_sec * 1000.0)
                cap.set(cv2.CAP_PROP_POS_MSEC, target_msec)
                ret, frame = cap.read()
                if not ret or frame is None:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    ret, frame = cap.read()
                if ret and frame is not None:
                    frame_read_success = True
                    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            cap.release()
    except Exception as e:
        sys.stderr.write(f"[MultimodalKnowledge] OpenCV frame read note on {video_path}: {e}\n")

    if frame_read_success and rgb_frame is not None:
        img = Image.fromarray(rgb_frame)
        canvas = Image.new('RGB', (320, 180), color='#121218')
        img.thumbnail((320, 180), Image.Resampling.LANCZOS)
        x = (320 - img.width) // 2
        y = (180 - img.height) // 2
        canvas.paste(img, (x, y))
        canvas.save(output_path, 'JPEG', quality=85)
    else:
        # Fallback dark-mode preview card for corrupt/unreadable videos
        img = Image.new('RGB', (320, 180), color='#1F1B24')
        draw = ImageDraw.Draw(img)
        draw.rectangle([10, 10, 140, 30], fill='#9333EA')
        draw.text((16, 13), "VIDEO PREVIEW", fill='#FFFFFF')
        file_name = os.path.basename(video_path)
        draw.text((15, 90), f"File: {file_name[:30]}", fill='#E9D5FF')
        draw.text((15, 110), f"Timestamp: {timestamp_sec:.1f}s", fill='#C084FC')
        img.save(output_path, 'JPEG', quality=85)

    return os.path.abspath(output_path).replace('\\', '/')


def hybrid_semantic_chunking(
    segments: List[Dict[str, Any]],
    source_file: str,
    output_thumbnail_dir: str = "C:/vazus/knowledge/.thumbnails"
) -> List[Dict[str, Any]]:
    """
    Applies hybrid semantic chunking boundary decision matrix and tail merging logic to ASR segments,
    generating scene metadata dictionaries with preview thumbnails.
    """
    if not segments:
        return []

    MIN_DURATION_SEC = 60.0
    TARGET_DURATION_SEC = 120.0
    MAX_DURATION_SEC = 180.0
    STRONG_PAUSE_SEC = 1.2
    SOFT_PAUSE_SEC = 0.8
    TAIL_MERGE_THRESHOLD_SEC = 30.0

    scene_groups = []
    current_segments = []
    chunk_start = float(segments[0]["start"])

    for idx, seg in enumerate(segments):
        current_segments.append(seg)
        chunk_end = float(seg["end"])
        duration = chunk_end - chunk_start

        if idx + 1 < len(segments):
            next_seg = segments[idx + 1]
            pause_gap = max(0.0, float(next_seg["start"]) - float(seg["end"]))
        else:
            pause_gap = 999.0

        text_trim = str(seg.get("text", "")).strip()
        has_punctuation = text_trim.endswith(('.', '!', '?', '…', '\n'))
        should_cut = False

        if duration >= MAX_DURATION_SEC:
            should_cut = True
        elif MIN_DURATION_SEC <= duration < TARGET_DURATION_SEC:
            if has_punctuation and pause_gap >= STRONG_PAUSE_SEC:
                should_cut = True
            elif pause_gap >= 2.0:
                should_cut = True
        elif duration >= TARGET_DURATION_SEC:
            if has_punctuation or pause_gap >= SOFT_PAUSE_SEC:
                should_cut = True

        if should_cut:
            scene_groups.append({
                "start_sec": chunk_start,
                "end_sec": chunk_end,
                "segments": current_segments
            })
            current_segments = []
            if idx + 1 < len(segments):
                chunk_start = float(segments[idx + 1]["start"])

    # Tail uncommitted segments handling
    if current_segments:
        tail_start = float(current_segments[0]["start"])
        tail_end = float(current_segments[-1]["end"])
        tail_duration = tail_end - tail_start

        if tail_duration < TAIL_MERGE_THRESHOLD_SEC and scene_groups:
            last_group = scene_groups[-1]
            last_group["segments"].extend(current_segments)
            last_group["end_sec"] = tail_end
        else:
            scene_groups.append({
                "start_sec": tail_start,
                "end_sec": tail_end,
                "segments": current_segments
            })

    # Build metadata dictionaries
    file_rel_path = source_file.replace('\\', '/')
    media_type = get_media_type(source_file)
    os.makedirs(output_thumbnail_dir, exist_ok=True)
    scenes = []
    total_scenes = len(scene_groups)

    scene_ids = []
    for grp in scene_groups:
        st = grp["start_sec"]
        en = grp["end_sec"]
        hash_id = hashlib.sha256(f"{file_rel_path}:{st:.2f}:{en:.2f}".encode("utf-8")).hexdigest()[:12]
        scene_ids.append(f"scene_{hash_id}")

    for idx, grp in enumerate(scene_groups):
        st_sec = round(grp["start_sec"], 2)
        en_sec = round(grp["end_sec"], 2)
        duration = round(en_sec - st_sec, 2)
        segs = grp["segments"]

        raw_transcript = " ".join([str(s.get("text", "")) for s in segs if s.get("text")]).strip()
        transcript = normalize_russian_text(raw_transcript)

        midpoint_sec = round(st_sec + (duration / 2.0), 2)
        scene_id = scene_ids[idx]
        prev_scene_id = scene_ids[idx - 1] if idx > 0 else None
        next_scene_id = scene_ids[idx + 1] if idx + 1 < total_scenes else None

        thumb_filename = f"thumb_{scene_id}.jpg"
        thumb_output_path = os.path.join(output_thumbnail_dir, thumb_filename)
        actual_thumb_path = generate_thumbnail(source_file, midpoint_sec, thumb_output_path)

        scene_meta = {
            "scene_id": scene_id,
            "source_file": file_rel_path,
            "start_sec": st_sec,
            "end_sec": en_sec,
            "duration": duration,
            "transcript": transcript,
            "thumbnail_path": actual_thumb_path.replace('\\', '/'),
            "chunk_index": idx,
            "media_type": media_type,
            "whisper_segment_count": len(segs),
            "words_count": len(transcript.split()),
            "char_count": len(transcript),
            "thumbnail_timestamp_sec": midpoint_sec,
            "prev_scene_id": prev_scene_id,
            "next_scene_id": next_scene_id,
        }
        scenes.append(scene_meta)

    return scenes


def load_audio_16k_mono(file_path: str) -> np.ndarray:
    """Decodes media audio track to 16kHz mono float32 numpy array using PyAV."""
    try:
        import av
        container = av.open(file_path)
        if not container.streams.audio:
            return np.array([], dtype=np.float32)
        stream = container.streams.audio[0]
        resampler = av.AudioResampler(format='flt', layout='mono', rate=16000)
        audio_data = []
        for frame in container.decode(stream):
            resampled_frames = resampler.resample(frame)
            if resampled_frames:
                for rf in resampled_frames:
                    audio_data.append(rf.to_ndarray().squeeze())
        flushed = resampler.resample(None)
        if flushed:
            for rf in flushed:
                audio_data.append(rf.to_ndarray().squeeze())
        container.close()
        if audio_data:
            return np.concatenate(audio_data).astype(np.float32)
    except Exception as e:
        sys.stderr.write(f"[MultimodalKnowledge] PyAV audio load note: {e}\n")
    return np.array([], dtype=np.float32)


def transcribe_media_high_precision(
    file_path: str,
    model_name: str = "large-v3-turbo",
    output_thumbnail_dir: str = "C:/vazus/knowledge/.thumbnails"
) -> List[Dict[str, Any]]:
    """
    High-precision ASR pipeline with language='ru', vad_filter=True, compute_type='int8',
    Russian text normalization, hallucination garbage filtering, and hybrid semantic chunking.
    Returns scene dictionaries: [scene_id, source_file, start_sec, end_sec, transcript, thumbnail_path, ...]
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Media file not found: {file_path}")

    os.makedirs(output_thumbnail_dir, exist_ok=True)
    file_ext = os.path.splitext(file_path)[1].lower()

    # Step 1: Run Whisper ASR with fallback support
    model, loaded_model_name = get_whisper_model_with_fallback(preferred_model=model_name, device="cpu", compute_type="int8")
    raw_segments = []

    if model is not None:
        try:
            audio_np = load_audio_16k_mono(file_path)
            audio_input = audio_np if len(audio_np) > 0 else file_path

            segments_iter, info = model.transcribe(
                audio_input,
                language="ru",
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=500),
                beam_size=1
            )
            for seg in segments_iter:
                norm_text = normalize_russian_text(seg.text)
                if norm_text and not is_garbage_transcript(norm_text):
                    raw_segments.append({
                        "start": float(seg.start),
                        "end": float(seg.end),
                        "text": norm_text
                    })
        except Exception as e:
            sys.stderr.write(f"[MultimodalKnowledge] faster-whisper transcribe error ({e}), trying fallback ASR\n")

    # Step 1 Fallback: PyAV + Transformers ASR Pipeline
    if not raw_segments:
        try:
            import av
            from transformers import pipeline
            container = av.open(file_path)
            if container.streams.audio:
                stream = container.streams.audio[0]
                resampler = av.AudioResampler(format='flt', layout='mono', rate=16000)
                audio_data = []
                for frame in container.decode(stream):
                    resampled = resampler.resample(frame)
                    if resampled:
                        if isinstance(resampled, (list, tuple)):
                            for r in resampled:
                                audio_data.append(r.to_ndarray())
                        else:
                            audio_data.append(resampled.to_ndarray())
                flushed = resampler.resample(None)
                if flushed:
                    if isinstance(flushed, (list, tuple)):
                        for r in flushed:
                            audio_data.append(r.to_ndarray())
                    else:
                        audio_data.append(flushed.to_ndarray())
                container.close()

                if audio_data:
                    audio_np = np.concatenate(audio_data, axis=1).squeeze()
                    asr = pipeline('automatic-speech-recognition', model='openai/whisper-tiny', return_timestamps=True)
                    res = asr(audio_np, generate_kwargs={'language': 'russian'}, return_timestamps=True)
                    chunks = res.get('chunks', [])
                    for ch in chunks:
                        t_start, t_end = ch.get('timestamp', (0.0, 0.0))
                        norm_text = normalize_russian_text(ch.get('text', ''))
                        if norm_text and not is_garbage_transcript(norm_text):
                            raw_segments.append({
                                "start": float(t_start or 0.0),
                                "end": float(t_end or t_start or 0.0),
                                "text": norm_text
                            })
        except Exception as fallback_e:
            sys.stderr.write(f"[MultimodalKnowledge] Fallback ASR error: {fallback_e}\n")

    if not raw_segments:
        return []

    # Step 2 & 3: Delegate to hybrid_semantic_chunking
    return hybrid_semantic_chunking(raw_segments, file_path, output_thumbnail_dir=output_thumbnail_dir)


def transcribe_and_chunk_media(
    file_path: str,
    output_thumbnail_dir: str = "C:/vazus/knowledge/.thumbnails"
) -> List[Dict[str, Any]]:
    """
    Transcribes audio/video file using high-precision ASR, applies hybrid semantic
    chunking into 1-3 minute scenes, generates thumbnail previews, and returns list
    of scene dictionaries.
    """
    return transcribe_media_high_precision(file_path, model_name="large-v3-turbo", output_thumbnail_dir=output_thumbnail_dir)


def index_scenes_to_supergraph(
    scenes: List[Dict[str, Any]],
    db_path: str = "C:/vazus/services/memory/vazus.db"
) -> int:
    """
    Generates 768D vector embeddings using UnifiedEmbeddingManager and persists
    kg_nodes and kg_edges into SQLite databases.
    """
    if not scenes:
        return 0

    embedder = get_embedding_manager()

    # Pre-compute 768D vector embeddings for each scene transcript
    embeddings = []
    for sc in scenes:
        emb = embedder.get_embedding(sc["transcript"])
        embeddings.append(emb)

    target_dbs = list(dict.fromkeys([db_path, "C:/vazus/services/memory/vazus.db", "C:/vazus/services/memory/vazus.db"]))

    for target_db in target_dbs:
        db_dir = os.path.dirname(target_db)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

        from vazus_core.memory.db import get_db_connection
        conn = get_db_connection(target_db)
        cursor = conn.cursor()

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS kg_nodes (
            id TEXT PRIMARY KEY,
            name TEXT,
            domain TEXT,
            node_type TEXT,
            description TEXT,
            tags TEXT,
            properties TEXT,
            embedding_json TEXT
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS kg_edges (
            source_id TEXT,
            target_id TEXT,
            relation TEXT,
            strength REAL,
            properties TEXT,
            PRIMARY KEY (source_id, target_id, relation)
        );
        """)

        for sc, emb in zip(scenes, embeddings):
            file_name = os.path.basename(sc["source_file"])
            st_m, st_s = divmod(int(sc["start_sec"]), 60)
            en_m, en_s = divmod(int(sc["end_sec"]), 60)
            time_range_str = f"{st_m:02d}:{st_s:02d} - {en_m:02d}:{en_s:02d}"
            node_name = f"Scene {sc['chunk_index'] + 1} ({time_range_str}) - {file_name}"
            
            description_snippet = sc["transcript"][:500]
            tags = f"multimodal,{sc['media_type']},telegram_course,scene"
            properties_json = json.dumps(sc, ensure_ascii=False)
            embedding_json = json.dumps(emb)

            # Insert/Replace MediaScene Node
            cursor.execute("""
            INSERT OR REPLACE INTO kg_nodes (
                id, name, domain, node_type, description, tags, properties, embedding_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                sc["scene_id"],
                node_name,
                "multimodal_av",
                "MediaScene",
                description_snippet,
                tags,
                properties_json,
                embedding_json
            ))

            # Insert BELONGS_TO Graph Edge
            media_node_id = f"media:{file_name}"
            cursor.execute("""
            INSERT OR REPLACE INTO kg_edges (
                source_id, target_id, relation, strength, properties
            ) VALUES (?, ?, ?, ?, ?)
            """, (
                sc["scene_id"],
                media_node_id,
                "BELONGS_TO",
                1.0,
                "{}"
            ))

            # Insert NEXT_SCENE Graph Edge if sequential scene exists
            if sc.get("next_scene_id"):
                cursor.execute("""
                INSERT OR REPLACE INTO kg_edges (
                    source_id, target_id, relation, strength, properties
                ) VALUES (?, ?, ?, ?, ?)
                """, (
                    sc["scene_id"],
                    sc["next_scene_id"],
                    "NEXT_SCENE",
                    1.0,
                    "{}"
                ))

        conn.commit()
        conn.close()

    return len(scenes)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding='utf-8')
    print("Testing Multimodal Knowledge Engine...")
    sample_file = r"C:\vazus\knowledge\telegram_courses\Курс _Покоритель Наташек 6_0_\media_174.oga"
    if os.path.exists(sample_file):
        print(f"Transcribing and chunking: {sample_file}")
        scenes_data = transcribe_and_chunk_media(sample_file)
        print(f"Generated {len(scenes_data)} scene chunks:")
        for sc in scenes_data:
            print(f" - [{sc['scene_id']}] ({sc['start_sec']}s -> {sc['end_sec']}s): {sc['transcript'][:80]}...")
            print(f"   Thumbnail: {sc['thumbnail_path']}")
        indexed_count = index_scenes_to_supergraph(scenes_data)
        print(f"Indexed {indexed_count} scenes into SuperGraph databases!")
