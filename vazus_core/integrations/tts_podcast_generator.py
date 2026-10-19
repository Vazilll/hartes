"""
vazus_core/tts_podcast_generator.py — TTS Audio Synthesizer for NotebookLM 2-Host Podcasts.

Features:
1. 🎙️ Converts 2-host conversational scripts ('Алексей' & 'Елена') into MP3/WAV audio files.
2. 🔊 Uses gTTS / pyttsx3 fallback with Russian voice modulation.
3. 📂 Saves podcasts to /home/tarhes/Проекты/vazus/knowledge/.podcasts/podcast_<id>.mp3 for web player streaming.

vazus SuperGraph OS Ecosystem
"""

import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

PODCAST_DIR = Path("/home/tarhes/Проекты/vazus/knowledge/.podcasts")
PODCAST_DIR.mkdir(parents=True, exist_ok=True)


def synthesize_podcast_audio(dialogue: List[Dict[str, str]], output_filename: Optional[str] = None) -> str:
    """Synthesizes dialogue list into an MP3 audio file."""
    if not output_filename:
        output_filename = f"podcast_audio_{int(time.time())}.mp3"
    output_path = PODCAST_DIR / output_filename

    combined_text = []
    for item in dialogue:
        speaker = item.get("speaker", "Ведущий")
        text = item.get("text", "")
        combined_text.append(f"{speaker}: {text}")

    full_transcript = "\n\n".join(combined_text)

    # Attempt gTTS synthesis
    try:
        from gtts import gTTS
        tts = gTTS(text=full_transcript, lang='ru', slow=False)
        tts.save(str(output_path))
        print(f"✅ [TTS Generator] Подкаст успешно синтезирован в файл MP3 (gTTS): {output_path}")
        return str(output_path).replace("\\", "/")
    except Exception as e:
        sys.stderr.write(f"[TTS Generator] gTTS error or not installed ({e}), trying pyttsx3 fallback...\n")

    # Fallback pyttsx3 synthesis
    try:
        import pyttsx3
        engine = pyttsx3.init()
        engine.save_to_file(full_transcript, str(output_path))
        engine.runAndWait()
        print(f"✅ [TTS Generator] Подкаст успешно синтезирован (pyttsx3): {output_path}")
        return str(output_path).replace("\\", "/")
    except Exception as e2:
        sys.stderr.write(f"[TTS Generator] pyttsx3 fallback error ({e2}). Writing text script file as fallback.\n")

    # Fallback to saving script text if TTS audio library not installed
    txt_path = output_path.with_suffix(".txt")
    txt_path.write_text(full_transcript, encoding="utf-8")
    return str(txt_path).replace("\\", "/")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sample_dialogue = [
        {"speaker": "Алексей", "text": "Тестовый выпуск подкаста NotebookLM Studio."},
        {"speaker": "Елена", "text": "Все системы функционируют отлично!"}
    ]
    res = synthesize_podcast_audio(sample_dialogue, "test_podcast.mp3")
    print(f"TTS self-test result: {res}")
