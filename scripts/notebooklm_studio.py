#!/usr/bin/env python3
"""
scripts/notebooklm_studio.py — CLI NotebookLM Synthesis Studio for vazus SuperGraph OS.

Features:
1. 📚 Multi-Source Knowledge Aggregation across video courses, Telegram, MIREA, and Zettelkasten notes.
2. 📄 `--study-guide`: Generates a master Markdown Study Guide.
3. 🎙️ `--podcast`: Generates a 2-host conversational Audio Podcast episode.

vazus SuperGraph OS Ecosystem
"""

import sys
import argparse
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from vazus_core.notebook_synthesis_engine import NotebookSynthesisEngine
from vazus_core.tts_podcast_generator import synthesize_podcast_audio


def main():
    print("=" * 75)
    print("🎙️ РАЙТСИСТЕМ / NOTEBOOKLM SYNTHESIS STUDIO & PODCAST GENERATOR")
    print("=" * 75)

    parser = argparse.ArgumentParser(description="NotebookLM Synthesis Studio")
    parser.add_argument("--study-guide", action="store_true", help="Generate Master Markdown Study Guide")
    parser.add_argument("--podcast", action="store_true", help="Generate 2-Host Conversational Audio Podcast")
    parser.add_argument("--title", type=str, default="Общий Сводный Обзор Базы Знаний", help="Title / Topic of the synthesis")
    args = parser.parse_args()

    engine = NotebookSynthesisEngine()

    if not args.study_guide and not args.podcast:
        # Default: generate both
        args.study_guide = True
        args.podcast = True

    if args.study_guide:
        print(f"\n📄 [1/2] Генерация Учебного Гида (Study Guide) по теме: '{args.title}'...")
        guide_res = engine.generate_study_guide(title=args.title)
        print(f"   -> Учебный гид сохранен: {guide_res['filepath']}")

    if args.podcast:
        print(f"\n🎙️ [2/2] Генерация 2-спикерного аудиоподкаста (Алексей & Елена)...")
        podcast_script = engine.generate_audio_podcast_script(topic=args.title)
        audio_path = synthesize_podcast_audio(podcast_script["dialogue"])
        print(f"   -> Аудиоподкаст сохранен: {audio_path}")

    print("\n" + "=" * 75)
    print("🎉 ГЕНЕРАЦИЯ NOTEBOOKLM STUDIO УСПЕШНО ЗАВЕРШЕНА!")
    print("=" * 75)


if __name__ == "__main__":
    main()
