import requests
import json

def analyze_text_with_ollama(text):
    url = "http://localhost:11434/api/generate"
    
    # 1. تعریف پرامپت سیستم (دستورالعمل اصلی)
    system_instruction = """
    You are an AI analyst. Analyze the employee's chat message.
    Output ONLY strictly valid JSON with keys: 
    "sentiment_score" (1-10), 
    "category" (Technical/HR/Casual/Security), 
    "is_risky" (boolean), 
    "summary" (Translate intent to Persian).
    """

    full_prompt = f"{system_instruction}\n\nUser Message to Analyze: \"{text}\""

    payload = {
        "model": "llama3",  
        "prompt": full_prompt,
        "stream": False,
        "format": "json",    
        "options": {
            "temperature": 0.1  
        }
    }
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        if response.status_code == 200:
            data = response.json()
            return json.loads(data['response'])
        else:
            print(f"Ollama Error: {response.text}")
            return None
    except Exception as e:
        print(f"Connection Error: {e}")
        return None