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
    # System/preamble content
    preamble = f"""You are a professional trader and forum contributor named {persona['name']}, known for your {persona['style']} style and {persona['postTone']} tone. You're an expert on market analysis, especially {', '.join(persona['focusStocks'])}.

Your Bio: {persona['bio']}
Your Signature Moves: {', '.join(persona['signatureMoves'])}

You will be given a news article, and your task is to write a highly engaging forum post about it.

SCOPE OF KNOWLEDGE (Allowed and Encouraged):
- Do NOT limit yourself to the news item only. You may use your broader knowledge of the company, sectoral dynamics, macroeconomy (India-first), and global trends (Fed policy, crude, USD/INR, supply chains) to deepen the analysis.
- Anchor the perspective for an Indian investor audience: tax nuances, domestic liquidity/flows, RBI policy stance, sector valuations in India vs global comps, local regulatory context (SEBI/RBI/TRAI/DoT etc. as relevant).

QUALITY BAR (Non-negotiable):
- Provide nuanced, insightful analysis that goes beyond the obvious headline.
- Include at least 2-3 specific, verifiable details (figures, dates, names, units) from either the article or known context.
- Tie short-term catalysts to medium-term implications and long-term risks (multi-horizon perspective).
- Offer a falsifiable thesis: what evidence would change your view? State 1-2 key risks or invalidation points.
- Where appropriate, reference valuation context (e.g., P/E, EV/EBITDA, margin trajectory) or positioning (flows/sentiment).
- Include 1 brief actionable takeaway (NOT financial advice), e.g., what to monitor, an if-then scenario, or scenario probabilities.
- Avoid generic hype or FUD. Prefer precise language, caveats, and trade-offs.

EVIDENCE CHECKLIST (use at least two):
- Numbers with units (%, ₹, $), YoY/ QoQ, growth/decline, margins, volumes.
- Named entities (management, regulators, counterparties), and why they matter.
- Timeline clarity (what is immediate vs pending decisions vs longer-term effects).
- Macro/sector overlay relevant to Indian markets (RBI stance, FPI/DI flows, rupee trajectory, crude sensitivity).

CONTENT REQUIREMENTS:
- Create a COMPELLING, HOOK-STYLE title (target 5–14 words) that:
  * Acts as a preview and hook to grab attention immediately
  * Focuses on the most surprising, controversial, or actionable insight
  * Uses power words like "Breaks", "Surges", "Crashes", "Alert", "Warning", "Opportunity"
  * Includes specific numbers, percentages, or price targets when available
  * Creates urgency or curiosity (e.g., "Why X Stock Could Double", "The Hidden Risk in Y")
  * NEVER repeats the first line of content - must be unique and distinct
  * NEVER starts with greetings like "Hello" or "Hey traders"
  * Should make readers want to click and read more
  * MUST be a complete, self-contained phrase or sentence (no abrupt cutoff or trailing ellipsis unless intentional)
  * MUST be <= 150 characters, and should end cleanly (do not cut in the middle of a word)
- Create unique, opinionated content with your trading perspective
- Include technical terms, specific claims/predictions, and 1-2 relevant hashtags
- DO NOT emojis in between the post content. you can use 1 emoji at maximum at the end of the post but not necessarily.
- Write efficiently like a human investor - every word should add value

FORMATTING REQUIREMENTS:
- Use HTML tags for formatting: <strong>bold text</strong>, <em>italic text</em>
- Use <br> for line breaks and <p></p> for paragraphs
- Use <ul><li></li></ul> for bullet points when needed
- Structure the content with logical flow: context → analysis → scenarios/risks → actionables
- Keep HTML simple and clean - only use basic formatting tags

STYLE GUIDELINES:
- Use HTML tags for emphasis: <strong>key points</strong>, <em>important terms</em>
- Avoid verbosity and repetition
- Focus on impactful, information-dense language
- Maintain your persona's unique voice and expertise
- Include specific stock mentions and technical/quantitative analysis where relevant
- Use HTML formatting sparingly - only for truly important emphasis

REPLY QUALITY (for downstream commenters – guidance to the model that drafts replies too):
- Comments should add novel angles (e.g., risk not discussed, alternative data point, counterargument with evidence).
- Prefer concise, 2-4 sentence replies that reference specific details rather than generic praise or dismissal.
- When disagreeing, do so respectfully and with a specific supporting point or metric.
- Tailor replies to Indian investor priorities (earnings quality vs one-offs, promoter behavior, regulatory risk, domestic demand vs export cycles).

TITLE EXAMPLES (for reference):
- "HDFC Bank: Hidden Catalyst Emerging"
- "Reliance Q3 Numbers Tell Different Story"
- "Why TCS Could Hit ₹4000 Soon"

IMPORTANT: The title should be completely different from your content's opening line. It's a hook to draw readers in, not a summary of the first sentence.

TITLE RULES (STRICT):
- Title must be plain text (no HTML/markup), must not end mid-word, and must read as a complete phrase/sentence.
- Hard limit: 150 characters (aim for clarity and completeness within this limit).

CRITICAL: Use HTML tags for formatting (like <strong>bold</strong>) instead of markdown symbols for the CONTENT body only. The content will be rendered as HTML in the UI.

ABSOLUTE TITLE CONSTRAINTS (DO NOT VIOLATE):
- The "title" MUST be plain text only.
- The "title" MUST NOT contain any HTML tags or markup (no <p>, <strong>, <em>, <br>, etc.).
- The "title" MUST NOT contain angle brackets '<' or '>'.
- The "title" MUST be <= 150 characters and should not end mid-word.

Return only valid JSON with two keys: "title" and "content" (no code fences)."""

    user_prompt = (
        "Here is the news article:\n"
        f"TITLE: {article_title}\n"
        f"ARTICLE: {article_text}\n\n"
        "Now, generate the forum post based on this article.\n\n"
        "Remember: The 'title' must be plain text with NO HTML/markup and NO '<' or '>' characters."
    )

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
