import os

# Pop env variables to force ADC / Vertex AI authentication
os.environ.pop("GEMINI_API_KEY", None)
os.environ.pop("GOOGLE_API_KEY", None)

from google import genai
from google.genai import types

try:
    # Initialize client for Vertex AI
    client = genai.Client(vertexai=True)
    print("Client initialized successfully for Vertex AI!")
    
    # Try calling a model with Google Search Tool
    google_search_tool = types.Tool(
        google_search=types.GoogleSearch()
    )
    
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents="What is the current status of the weather in Stockholm?",
        config=types.GenerateContentConfig(
            tools=[google_search_tool]
        )
    )
    print("RESPONSE TEXT:", response.text)
    if response.candidates and response.candidates[0].grounding_metadata:
        print("GROUNDING METADATA:", response.candidates[0].grounding_metadata)
except Exception as e:
    print("ERROR:", e)
