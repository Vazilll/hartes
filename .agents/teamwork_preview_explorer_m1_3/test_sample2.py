import sys, os
from faster_whisper import WhisperModel

sys.stdout.reconfigure(encoding='utf-8')

sample_audio = None
for root, dirs, files in os.walk(r"C:\vazus\knowledge\telegram_courses"):
    for f in files:
        if f.endswith('.oga') and f != 'media_174.oga':
            sample_audio = os.path.join(root, f)
            break
    if sample_audio:
        break

print("Testing file:", sample_audio)

model_tiny = WhisperModel("tiny", device="cpu", compute_type="int8")
segs_tiny, _ = model_tiny.transcribe(sample_audio, language="ru")
text_tiny = " ".join([s.text.strip() for s in segs_tiny])

model_turbo = WhisperModel("large-v3-turbo", device="cpu", compute_type="int8")
segs_turbo, _ = model_turbo.transcribe(sample_audio, language="ru", beam_size=5, vad_filter=True)
text_turbo = " ".join([s.text.strip() for s in segs_turbo])

print("\n--- TINY RESULT ---")
print(text_tiny)

print("\n--- LARGE-V3-TURBO RESULT ---")
print(text_turbo)
