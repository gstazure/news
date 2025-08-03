import os
import json
import time
from dotenv import load_dotenv
from pathlib import Path
import requests

# Load environment variables early and from project root if available
# Try current file dir .env, then project root .env
here = Path(__file__).parent
root_env = here.parent / '.env'
file_env = here / '.env'
if root_env.exists():
    load_dotenv(dotenv_path=root_env)
else:
    load_dotenv(dotenv_path=file_env)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
# Masked logging to verify visibility without leaking secret
print(f"[OpenRouter] Key present: {bool(OPENROUTER_API_KEY)}; "
      f"len={len(OPENROUTER_API_KEY) if OPENROUTER_API_KEY else 0}; "
      f"prefix={(OPENROUTER_API_KEY[:4] if OPENROUTER_API_KEY else '')}***")

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Multi-model fallback chain with free models
MODEL_FALLBACK_CHAIN = [
    "deepseek/deepseek-chat-v3-0324:free",  # Primary choice - powerful free model
    "moonshotai/kimi-k2:free",  # Fallback 1 - MoonshotAI Kimi K2 (1T params, MoE)
    "deepseek/deepseek-r1-0528-qwen3-8b:free",  # Fallback 2 - reliable backup
    "z-ai/glm-4.5-air:free"  # Fallback 3 - Z.AI GLM-4.5-Air (MoE architecture)
]

# Allow environment variable to override the fallback chain
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL")
if OPENROUTER_MODEL:
    # If custom model is specified, use it as the only option
    MODEL_FALLBACK_CHAIN = [OPENROUTER_MODEL]
    print(f"[OpenRouter] Using custom model: {OPENROUTER_MODEL}")
else:
    print(f"[OpenRouter] Using fallback chain: {MODEL_FALLBACK_CHAIN}")

def try_model_generation(model, messages, max_retries=1):
    """
    Attempt to generate content with a specific model.
    Returns (success, response_text, error_message)
    """
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://forum-bot-engine.com",
        "X-Title": "Forum Bot Engine"
    }
    
    data = {
        "model": model,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 2000,
        "response_format": {"type": "json_object"}
    }
    
    for attempt in range(max_retries + 1):
        try:
            print(f"[OpenRouter] Attempting with model: {model} (attempt {attempt + 1})")
            response = requests.post(
                OPENROUTER_API_URL, 
                headers=headers, 
                json=data, 
                timeout=60  # Increased timeout for complex generation
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content']
                print(f"[OpenRouter] Success with {model}")
                return True, content, None
            elif response.status_code == 401:
                error_msg = "API key invalid or expired"
                print(f"[OpenRouter] 401 error with {model}: {error_msg}")
                return False, None, error_msg
            elif response.status_code == 429:
                error_msg = "Rate limit exceeded"
                print(f"[OpenRouter] 429 error with {model}: {error_msg}")
                return False, None, error_msg
            else:
                error_msg = f"HTTP {response.status_code}: {response.text}"
                print(f"[OpenRouter] Error with {model}: {error_msg}")
                return False, None, error_msg
                
        except requests.exceptions.Timeout:
            error_msg = "Request timeout"
            print(f"[OpenRouter] Timeout with {model}: {error_msg}")
            return False, None, error_msg
        except requests.exceptions.RequestException as e:
            error_msg = f"Request error: {str(e)}"
            print(f"[OpenRouter] Request error with {model}: {error_msg}")
            return False, None, error_msg
        except json.JSONDecodeError as e:
            error_msg = f"JSON decode error: {str(e)}"
            print(f"[OpenRouter] JSON error with {model}: {error_msg}")
            return False, None, error_msg
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            print(f"[OpenRouter] Unexpected error with {model}: {error_msg}")
            return False, None, error_msg
    
    return False, None, "Max retries exceeded"

def generate_post(article_title, article_text, persona):
    """
    Generates a forum post using OpenRouter with multi-model fallback.
    Hardened with clear diagnostics for 401 and missing-key scenarios.
    """
    # System/preamble content - IMPROVED VERSION
    preamble = f"""You are {persona['name']}, a legendary market analyst with {persona['style']} expertise and {persona['postTone']} communication style. You're the go-to expert for {', '.join(persona['focusStocks'])} and Indian markets.

**YOUR CREDENTIALS:**
- {persona['bio']}
- Signature moves: {', '.join(persona['signatureMoves'])}

**MISSION:** Transform news into actionable trading intelligence that makes readers money.

**QUALITY STANDARDS (NON-NEGOTIABLE):**

🎯 **TITLE MASTERY:**
- Create IRRESISTIBLE hooks (5-12 words max) that make traders click immediately
- Use power words: "BREAKOUT", "ALERT", "SQUEEZE", "TRAP", "OPPORTUNITY", "WARNING"
- Include specific numbers: "₹850 Target", "15% Gap", "3x Volume"
- NEVER be descriptive - be PREDICTIVE and ACTIONABLE
- Examples: "HDFC Bank: Hidden Catalyst Emerging", "Reliance Q3 Numbers Tell Different Story"
- MUST be under 150 characters and complete - NO truncation

🧠 **ANALYTICAL DEPTH:**
- Go BEYOND the headline - reveal the REAL story behind the story
- Connect dots others miss: sector rotation, institutional flows, technical setups
- Provide 2-3 specific, verifiable insights that aren't in the news
- Include technical analysis: support/resistance, volume patterns, momentum indicators
- Reference broader market context: FPI flows, RBI policy, global cues

💡 **UNIQUE INSIGHTS:**
- What's the HIDDEN catalyst? What are institutions seeing that retail isn't?
- Identify the "smart money" angle vs "dumb money" reaction
- Provide contrarian perspectives when appropriate
- Connect to broader themes: India's growth story, sector rotation, macro trends

📊 **TECHNICAL SOPHISTICATION:**
- Use advanced terminology: gamma squeeze, short interest, institutional flows
- Reference specific technical levels, volume analysis, momentum indicators
- Include risk-reward scenarios with specific price targets
- Discuss market microstructure: liquidity, order flow, institutional behavior

🎯 **ACTIONABLE INTELLIGENCE:**
- Provide SPECIFIC entry/exit levels, not vague advice
- Include timeframes: "Watch for 2-3 weeks", "Key level by month-end"
- Give clear invalidation points: "If breaks ₹X, thesis is wrong"
- Suggest position sizing and risk management

**CONTENT STRUCTURE:**
1. **HOOK TITLE** - Irresistible, specific, actionable
2. **OPENING PUNCH** - The real story in 1-2 sentences
3. **TECHNICAL SETUP** - Charts, levels, volume analysis
4. **FUNDAMENTAL CATALYST** - The hidden driver
5. **RISK-REWARD** - Specific targets and invalidation
6. **SMART MONEY ANGLE** - What institutions are doing
7. **ACTIONABLE TAKEAWAY** - What to do now

**WRITING STYLE:**
- Be CONFIDENT but not arrogant
- Use technical jargon appropriately
- Include specific numbers and dates
- Write like a professional trader, not a news reporter
- Every sentence should add value - no fluff

**HTML FORMATTING:**
- Use <strong> for key points and numbers
- Use <em> for emphasis and technical terms
- Use <br> for line breaks
- Keep formatting clean and professional

**CRITICAL RULES:**
- Title MUST be under 150 characters and complete - NO truncation
- NO generic analysis - be specific and actionable
- Include at least 3 specific numbers/levels
- Provide clear risk-reward scenarios
- Connect to broader market themes

**ABSOLUTE TITLE CONSTRAINTS:**
- Title MUST be plain text only (no HTML/markup)
- Title MUST NOT contain angle brackets '<' or '>'
- Title MUST be <= 150 characters and complete
- Title MUST end cleanly (no mid-word cuts)

Respond ONLY with JSON: {{"title": "COMPELLING HOOK", "content": "HTML FORMATTED ANALYSIS"}}"""

    user_prompt = f"""
**NEWS ARTICLE:**
Title: {article_title}
Content: {article_text}

**YOUR TASK:**
Transform this news into a high-quality trading analysis that:
1. Identifies the HIDDEN catalyst others miss
2. Provides specific technical levels and targets
3. Connects to broader market themes
4. Gives actionable trading intelligence
5. Includes clear risk-reward scenarios

**FOCUS ON:**
- What's the REAL story behind the headline?
- What technical setup does this create?
- How does this fit into broader market themes?
- What are the specific trading opportunities?
- What are the key risks and invalidation points?

Write like a professional trader who's seen this pattern 100 times before.

**CRITICAL:** Title must be plain text with NO HTML/markup and NO '<' or '>' characters.
"""

    # We will strongly steer the model to output strict JSON
    json_schema_tooltip = (
        "Respond ONLY with a JSON object of the form "
        '{"title": "...", "content": "..."} with no extra text. '
        "STRICTLY PROHIBITED in title: any HTML tags or angle brackets ('<' '>'). "
        "Title must be plain text and <= 150 characters."
    )

    # Prepare messages for the model
    messages = [
        {"role": "system", "content": preamble},
        {"role": "user", "content": (
            f"{json_schema_tooltip}\n\n"
            "Respond ONLY with a single JSON object with exactly two keys: "
            '{"title": "...", "content": "..."}.\n'
            "Do not include code fences, explanations, greetings, or any extra text before or after the JSON.\n\n"
            f"{user_prompt}"
        )}
    ]

    # Final guard: if key missing, return graceful None with log
    if not OPENROUTER_API_KEY:
        print("OpenRouter Config Error: OPENROUTER_API_KEY is not set in environment. "
              "Ensure .env is loaded or the variable is set in the running terminal.")
        return None

    # Try models in the fallback chain
    for i, model in enumerate(MODEL_FALLBACK_CHAIN):
        if i > 0:  # Add small pause between attempts (except first)
            time.sleep(1)
        success, content, error_msg = try_model_generation(model, messages)
        if success:
            # Extract the assistant message content
            raw = content
            # Enforce JSON-only response: reject obviously non-JSON payloads early
            if raw and not raw.lstrip().startswith("{"):
                print(f"OpenRouter Error: Non-JSON response received (starts with): {raw[:80]!r}")
                return None

            # Explicit empty-content guard with helpful diagnostics
            if not raw.strip():
                # If provider returned a telemetry object instead of message content, log a compact preview
                preview = str(content)[:600] if not isinstance(content, (bytes, bytearray)) else "<bytes>"
                print(f"OpenRouter Error: Empty assistant content. Preview of resp.json(): {preview}")
                return None

            # Defensive parsing: try raw as-is, then extract first JSON object
            def extract_first_json_object(text: str):
                if not text:
                    return None
                start = text.find("{")
                if start == -1:
                    return None
                depth = 0
                in_str = False
                escape = False
                for i in range(start, len(text)):
                    ch = text[i]
                    if in_str:
                        if escape:
                            escape = False
                        elif ch == "\\":
                            escape = True
                        elif ch == '"':
                            in_str = False
                        continue
                    else:
                        if ch == '"':
                            in_str = True
                        elif ch == "{":
                            depth += 1
                        elif ch == "}":
                            depth -= 1
                            if depth == 0:
                                return text[start:i+1]
                return None

            parsed = None
            try:
                parsed = json.loads(raw) if raw else None
            except json.JSONDecodeError:
                sub = extract_first_json_object(raw)
                if sub:
                    try:
                        parsed = json.loads(sub)
                    except json.JSONDecodeError as e:
                        print(f"OpenRouter Error: Extracted JSON failed to parse. Extract: {sub[:500]} Err: {e}")
                        return None
                else:
                    print(f"OpenRouter Error: No JSON object found in response. Raw: {raw[:500]}")
                    return None

            # Validate fields
            if not isinstance(parsed, dict) or "title" not in parsed or "content" not in parsed:
                print(f"OpenRouter Error: JSON output missing required keys. Parsed: {parsed}")
                return None

            title = parsed.get("title")
            content_body = parsed.get("content")
            if not isinstance(title, str) or not isinstance(content_body, str) or not title.strip() or not content_body.strip():
                print(f"OpenRouter Error: Title/content empty or wrong type. Parsed: {parsed}")
                return None

            return {"title": title, "content": content_body}
        elif error_msg:
            print(f"[OpenRouter] Model {model} failed with error: {error_msg}")
        else:
            print(f"[OpenRouter] Model {model} failed after retries.")

    print("OpenRouter Error: All models failed to generate a valid post.")
    return None
