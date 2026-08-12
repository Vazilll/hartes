import sys, time
from faster_whisper import WhisperModel

sys.stdout.reconfigure(encoding='utf-8')

sample_audio = r"C:\vazus\knowledge\telegram_courses\Курс _Покоритель Наташек 6_0_\media_174.oga"

print(f"Testing transcription on sample file: {sample_audio}")

# Test 1: Tiny model (existing baseline)
print("\n--- Running Whisper 'tiny' ---")
t0 = time.time()
model_tiny = WhisperModel("tiny", device="cpu", compute_type="int8")
segs_tiny, _ = model_tiny.transcribe(sample_audio, language="ru", beam_size=1)
text_tiny = " ".join([s.text.strip() for s in segs_tiny])
t_tiny = time.time() - t0
print(f"Tiny Time: {t_tiny:.2f}s | Result:\n\"{text_tiny}\"")

# Test 2: Large-v3-turbo model (upgraded target)
print("\n--- Running Whisper 'large-v3-turbo' ---")
t0 = time.time()
model_turbo = WhisperModel("large-v3-turbo", device="cpu", compute_type="int8")
segs_turbo, _ = model_turbo.transcribe(sample_audio, language="ru", beam_size=5, vad_filter=True)
text_turbo = " ".join([s.text.strip() for s in segs_turbo])
t_turbo = time.time() - t0
print(f"Large-v3-turbo Time: {t_turbo:.2f}s | Result:\n\"{text_turbo}\"")
