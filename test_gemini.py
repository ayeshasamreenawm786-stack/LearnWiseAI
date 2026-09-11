import os
from google import genai


client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

response = client.models.generate_content(
    model="gemini-3.7-flash",
    contents="Hello! Introduce yourself in one sentence."
)

print(response.text)