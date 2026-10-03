import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from faster_whisper import WhisperModel

def transcribe_and_append():
    model = WhisperModel("tiny", device="cpu", compute_type="int8")
    
    files = [
        ("3868", r"C:\vazus\data\voice_notes\media_msg_3868"),
        ("3869", r"C:\vazus\data\voice_notes\media_msg_3869"),
    ]
    
    out_file = r"C:\vazus\data\voice_notes\pavel_inakov_2026_09_20_transcription.md"
    
    lines = []
    for msg_id, file_path in files:
        if not os.path.exists(file_path):
            continue
        segments, info = model.transcribe(file_path, beam_size=5, language="ru")
        text = " ".join([seg.text.strip() for seg in segments])
        duration = round(info.duration, 1)
        lines.append(f"\n## media_msg_{msg_id} ({duration} сек)\n{text}\n")
        print(f"Transcribed {msg_id} ({duration}s): length {len(text)} chars")
        
    with open(out_file, "a", encoding="utf-8") as f:
        f.writelines(lines)
    print("DONE_ALL")

if __name__ == "__main__":
    transcribe_and_append()
