#!/usr/bin/env python3
"""
Test script to evaluate all 4 models in the fallback chain with a sample news article.
"""

import os
import json
import time
import requests
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables
here = Path(__file__).parent
root_env = here.parent / '.env'
file_env = here / '.env'
if root_env.exists():
    load_dotenv(dotenv_path=root_env)
else:
    load_dotenv(dotenv_path=file_env)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Multi-model fallback chain (same as postgen.py)
MODEL_FALLBACK_CHAIN = [
    "deepseek/deepseek-chat-v3-0324:free",  # Primary choice
    "moonshotai/kimi-k2:free",  # Fallback 1 - MoonshotAI Kimi K2 (1T params, MoE)
    "deepseek/deepseek-r1-0528-qwen3-8b:free",  # Fallback 2 - reliable backup
    "z-ai/glm-4.5-air:free"  # Fallback 3 - Z.AI GLM-4.5-Air (MoE architecture)
]

# Sample news article for testing
SAMPLE_NEWS = {
    "title": "Adani Power Announces 1:1 Stock Split - Shares Surge 15%",
    "text": """
    Adani Power Limited has announced a 1:1 stock split, sending its shares soaring by 15% in early trading. 
    The company's board of directors approved the split during a meeting held on Monday, with the record date 
    set for September 15, 2024.
    
    The stock split will see each existing share of face value ₹10 split into two shares of face value ₹5 each. 
    This move is expected to improve liquidity and make the stock more accessible to retail investors.
    
    "This stock split reflects our confidence in the company's growth prospects and our commitment to creating 
    value for all stakeholders," said Gautam Adani, Chairman of Adani Group. "The improved liquidity will 
    benefit both existing and potential investors."
    
    The announcement comes on the heels of strong quarterly results, with Adani Power reporting a 45% increase 
    in net profit for the quarter ended June 2024. The company's revenue grew by 28% year-on-year, driven by 
    higher power generation and improved operational efficiency.
    
    Market analysts have welcomed the move, with several brokerages upgrading their target prices for the stock. 
    "The stock split, combined with strong fundamentals and the government's focus on renewable energy, makes 
    Adani Power an attractive investment opportunity," said Rajesh Kumar, Senior Analyst at ICICI Securities.
    
    The stock closed at ₹1,850 on the BSE, up from ₹1,610 at the previous close. Trading volumes were 
    significantly higher than the 30-day average, indicating strong investor interest.
    
    The company has also announced plans to invest ₹25,000 crore over the next three years to expand its 
    renewable energy portfolio and modernize existing thermal power plants. This investment is expected to 
    further strengthen the company's position in the Indian power sector.
    """
}

# Sample persona for testing
SAMPLE_PERSONA = {
    "name": "QuantumTrader",
    "style": "analytical",
    "postTone": "professional",
    "focusStocks": ["ADANIPOWER", "RELIANCE", "TCS"],
    "bio": "Expert technical analyst with 15+ years in Indian markets. Specializes in power sector and infrastructure stocks.",
    "signatureMoves": ["Technical breakout analysis", "Sector rotation insights", "Risk-reward assessment"]
}

def test_model_generation(model, article_title, article_text, persona):
    """
    Test a specific model with the sample news article.
    Returns (success, response_data, error_message)
    """
    if not OPENROUTER_API_KEY:
        return False, None, "API key not found"
    
    # System prompt (same as postgen.py)
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

TITLE EXAMPLES (for reference):
- "HDFC Bank: Hidden Catalyst Emerging"
- "Reliance Q3 Numbers Tell Different Story"
- "Why TCS Could Hit ₹4000 Soon"

IMPORTANT: The title should be completely different from your content's opening line. It's a hook to draw readers in, not a summary of the first sentence.

Respond ONLY with a single JSON object with exactly two keys: {{"title": "...", "content": "..."}}.
Do not include code fences, explanations, greetings, or any extra text before or after the JSON.
"""

    user_prompt = f"""
NEWS ARTICLE:
Title: {article_title}
Content: {article_text}

Write a compelling forum post about this news article. Focus on the most important insights for Indian investors.
"""

    messages = [
        {"role": "system", "content": preamble},
        {"role": "user", "content": user_prompt}
    ]
    
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://forum-bot-engine.com",
        "X-Title": "Forum Bot Engine - Multi-Model Test"
    }
    
    data = {
        "model": model,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 2000,
        "response_format": {"type": "json_object"}
    }
    
    try:
        print(f"\n[Testing Model] {model}")
        print(f"[Request] Making API call...")
        
        start_time = time.time()
        response = requests.post(
            OPENROUTER_API_URL, 
            headers=headers, 
            json=data, 
            timeout=60
        )
        end_time = time.time()
        
        print(f"[Response] Status: {response.status_code}, Time: {end_time - start_time:.2f}s")
        
        if response.status_code == 200:
            result = response.json()
            content = result['choices'][0]['message']['content']
            
            # Try to parse JSON response
            try:
                parsed = json.loads(content)
                if isinstance(parsed, dict) and "title" in parsed and "content" in parsed:
                    return True, parsed, None
                else:
                    return False, None, "Invalid JSON structure"
            except json.JSONDecodeError as e:
                return False, None, f"JSON parse error: {e}"
        else:
            error_text = response.text[:200] if response.text else "No error details"
            return False, None, f"HTTP {response.status_code}: {error_text}"
            
    except requests.exceptions.Timeout:
        return False, None, "Request timeout (60s)"
    except requests.exceptions.RequestException as e:
        return False, None, f"Request error: {str(e)}"
    except Exception as e:
        return False, None, f"Unexpected error: {str(e)}"

def main():
    """Test all models in the fallback chain"""
    print("=" * 80)
    print("MULTI-MODEL FALLBACK CHAIN TEST")
    print("=" * 80)
    print(f"Testing {len(MODEL_FALLBACK_CHAIN)} models with sample news article")
    print(f"API Key present: {bool(OPENROUTER_API_KEY)}")
    print()
    
    print("SAMPLE NEWS ARTICLE:")
    print(f"Title: {SAMPLE_NEWS['title']}")
    print(f"Content: {SAMPLE_NEWS['text'][:200]}...")
    print()
    
    results = {}
    
    for i, model in enumerate(MODEL_FALLBACK_CHAIN, 1):
        print(f"\n{'='*60}")
        print(f"TEST {i}/{len(MODEL_FALLBACK_CHAIN)}: {model}")
        print(f"{'='*60}")
        
        success, data, error = test_model_generation(
            model, 
            SAMPLE_NEWS['title'], 
            SAMPLE_NEWS['text'], 
            SAMPLE_PERSONA
        )
        
        results[model] = {
            'success': success,
            'data': data,
            'error': error
        }
        
        if success:
            print(f"\n✅ SUCCESS with {model}")
            print(f"Title: {data['title']}")
            print(f"Content preview: {data['content'][:200]}...")
        else:
            print(f"\n❌ FAILED with {model}")
            print(f"Error: {error}")
        
        # Small pause between tests
        if i < len(MODEL_FALLBACK_CHAIN):
            print("\nWaiting 2 seconds before next test...")
            time.sleep(2)
    
    # Summary
    print(f"\n{'='*80}")
    print("TEST SUMMARY")
    print(f"{'='*80}")
    
    successful_models = []
    failed_models = []
    
    for model, result in results.items():
        if result['success']:
            successful_models.append(model)
            print(f"✅ {model}: SUCCESS")
        else:
            failed_models.append(model)
            print(f"❌ {model}: FAILED - {result['error']}")
    
    print(f"\nResults: {len(successful_models)}/{len(MODEL_FALLBACK_CHAIN)} models successful")
    
    if successful_models:
        print(f"\n✅ Working models: {', '.join(successful_models)}")
    if failed_models:
        print(f"\n❌ Failed models: {', '.join(failed_models)}")
    
    print(f"\n{'='*80}")
    print("DETAILED RESULTS")
    print(f"{'='*80}")
    
    for model, result in results.items():
        print(f"\n{model}:")
        if result['success']:
            print(f"  Title: {result['data']['title']}")
            print(f"  Content: {result['data']['content'][:300]}...")
        else:
            print(f"  Error: {result['error']}")

if __name__ == "__main__":
    main() 