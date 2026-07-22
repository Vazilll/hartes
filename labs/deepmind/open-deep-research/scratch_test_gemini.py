from langchain.chat_models import init_chat_model
from pydantic import BaseModel

class Test(BaseModel):
    value: str

try:
    m = init_chat_model('gemini-2.5-flash', model_provider='google_genai')
    structured_m = m.with_structured_output(Test)
    result = structured_m.invoke('hello')
    print("SUCCESS:", result)
except Exception as e:
    print("FAILED:", e)
