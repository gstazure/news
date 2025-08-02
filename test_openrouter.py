import os
import json
import argparse
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "deepseek/deepseek-r1-0528-qwen3-8b:free"

def main():
    parser = argparse.ArgumentParser(description="Test OpenRouter JSON-mode response for blog post generation")
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL, help="OpenRouter model id")
    parser.add_argument("--title", type=str, default="Sanity Title", help="Title input to send in the prompt")
    parser.add_argument("--text", type=str, default="Respond ONLY with JSON: {\"title\":\"t\",\"content\":\"c\"}", help="Body text to send in the prompt")
    parser.add_argument("--timeout", type=int, default=30, help="HTTP timeout in seconds (default: 30)")
    args = parser.parse_args()

    if not OPENROUTER_API_KEY:
        raise ValueError("OPENROUTER_API_KEY not found in environment variables")

    model = args.model
    title = args.title
    text = args.text
    timeout = args.timeout

    print("Testing OpenRouter API connection...")
    print(f"API Key found: {OPENROUTER_API_KEY is not None}")
    if OPENROUTER_API_KEY:
        print(f"API Key length: {len(OPENROUTER_API_KEY)}")
    print(f"API URL: {OPENROUTER_API_URL}")
    print(f"Model: {model}")

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost",
        "X-Title": "OpenRouter JSON Sanity Test"
    }
    print("Headers: {'Authorization': 'Bearer ****', 'Content-Type': 'application/json'}")

    json_schema_tooltip = (
        "Respond ONLY with a JSON object of the form "
        "{\"title\":\"...\",\"content\":\"...\"} with no extra text. "
        "STRICTLY PROHIBITED in title: any HTML/markup or angle brackets. "
        "Title must be plain text and <= 150 characters."
    )
    preamble = "You are a helpful assistant that always returns strict JSON when asked."
    user_prompt = (
        f"TITLE: {title}\n"
        f"TEXT: {text}\n\n"
        "Return only a single JSON object: {\"title\":\"...\",\"content\":\"...\"}."
    )

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": preamble},
            {"role": "user", "content": f"{json_schema_tooltip}\n\n{user_prompt}"}
        ],
        "temperature": 0.7,
        "response_format": {"type": "json_object"}
    }

    try:
        print("\nMaking request to OpenRouter...")
        response = requests.post(
            OPENROUTER_API_URL,
            headers=headers,
            data=json.dumps(payload),
            timeout=timeout
        )

        print(f"Response status code: {response.status_code}")
        print(f"Response headers: {dict(response.headers)}")

        response.raise_for_status()
        data = response.json()
        print("Success! Response received:")
        print(json.dumps(data, indent=2))

        content = ""
        if isinstance(data, dict) and "choices" in data and len(data["choices"]) > 0:
            content = data["choices"][0].get("message", {}).get("content", "") or ""

        print("\nResponse content:")
        print(content or "<empty>")

        print("\nAttempting to parse assistant content as JSON...")
        try:
            parsed = json.loads(content) if content else None
            if not isinstance(parsed, dict) or "title" not in parsed or "content" not in parsed:
                print("Parsed content is not the expected JSON object with 'title' and 'content' keys.")
            else:
                print("JSON parse OK:")
                print(json.dumps(parsed, indent=2))
        except json.JSONDecodeError as e:
            print(f"JSON parse FAILED: {e}")

    except requests.exceptions.RequestException as e:
        print(f"Request error: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")

    print("\nTest completed.")

if __name__ == "__main__":
    main()