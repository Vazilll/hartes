import sys
import os
import wave
import struct
import math
import json

sys.path.insert(0, r"C:\vazus")
sys.stdout.reconfigure(encoding='utf-8')

wav_path = r"C:\vazus\.agents\teamwork_preview_auditor_m1_1\synth_test.wav"
sample_rate = 16000
duration = 3.0
num_samples = int(sample_rate * duration)

with wave.open(wav_path, 'w') as f:
    f.setnchannels(1)
    f.setsampwidth(2)
    f.setframerate(sample_rate)
    samples = [int(10000 * math.sin(2 * math.pi * 440 * i / sample_rate)) for i in range(num_samples)]
    f.writeframes(struct.pack('<' + 'h' * num_samples, *samples))

print("Synthetic WAV created:", wav_path)

from vazus_core.multimodal_knowledge import transcribe_media_high_precision

scenes = transcribe_media_high_precision(wav_path, model_name="tiny")
print("Synthetic audio transcribed scenes count:", len(scenes))
print("Scenes result:", json.dumps(scenes, indent=2, ensure_ascii=False))
