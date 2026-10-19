import os
import sys
import argparse
from PIL import Image
from dotenv import load_dotenv

# Reconfigure stdout to UTF-8 for Windows CLI compatibility
sys.stdout.reconfigure(encoding='utf-8')

def analyze_image(image_path: str, prompt: str = "Подробно опиши всё, что находится на этом скриншоте: визуальный контекст, интерфейсы, текст, объекты, события.") -> None:
    # Load environment variables from /home/tarhes/Проекты/vazus/.env
    load_dotenv(r'/home/tarhes/Проекты/vazus/.env')
    
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        print("ERROR: GEMINI_API_KEY not found in /home/tarhes/Проекты/vazus/.env")
        sys.exit(1)
        
    try:
        from google import genai
    except ImportError:
        print("ERROR: google-genai package not installed in environment")
        sys.exit(1)
        
    if not os.path.exists(image_path):
        print(f"ERROR: Image file not found: {image_path}")
        sys.exit(1)
        
    client = genai.Client(api_key=api_key)
    img = Image.open(image_path)
    
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=[img, prompt]
    )
    
    print(response.text)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Vazus Multimodal Vision Analysis')
    parser.add_argument('image_path', help='Path to target image file')
    parser.add_argument('--prompt', default="Подробно опиши всё, что находится на этом скриншоте: визуальный контекст, интерфейсы, текст, объекты, события.", help='Custom analysis prompt')
    args = parser.parse_args()
    
    analyze_image(args.image_path, args.prompt)
