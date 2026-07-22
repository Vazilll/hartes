import os
from google import genai
from google.genai import types

try:
    # Use standard AI Studio Client (uses GEMINI_API_KEY from environment)
    client = genai.Client()
    print("Client initialized successfully for Google AI Studio!")
    
    google_search_tool = types.Tool(
        google_search=types.GoogleSearch()
    )
    
    # We use gemini-2.0-flash or gemini-2.5-flash as the search agent
    response = client.models.generate_content(
        model="gemini-2.5-flash",
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
