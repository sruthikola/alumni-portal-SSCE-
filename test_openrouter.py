import requests

api_key = "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"

headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json",
    "HTTP-Referer": "http://localhost:5000/",
    "X-Title": "Test"
}

payload = {
    "model": "openai/gpt-3.5-turbo",
    "messages": [{"role": "user", "content": "Hello!"}],
    "temperature": 0.7
}

try:
    response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
    print("Status Code:", response.status_code)
    print(response.json())
except Exception as e:
    print("ERROR:", e)
