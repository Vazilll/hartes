import os
import sys
import json

sys.stdout.reconfigure(encoding='utf-8')

# Check git log in mirea_study_os or transcripts
study_dir = r"C:\Users\Vaz\Documents\mirea_study_os"
print("Checking mirea_study_os...")
for f in os.listdir(study_dir):
    if f.endswith('.md'):
        print(f, os.path.getsize(os.path.join(study_dir, f)))
