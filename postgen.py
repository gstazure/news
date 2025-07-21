import os
import cohere
import json
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables from .env file
env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path)

api_key = os.getenv("COHERE_API_KEY")
if not api_key:
    raise ValueError("COHERE_API_KEY not found in environment variables")

co = cohere.Client(api_key)  # Initialize Cohere client

def generate_post(article_title, article_text, persona):
    """
    Generates a forum post using Cohere's chat endpoint with JSON mode for reliable output.
    """
    
    preamble = f"""You are a professional trader and forum contributor named {persona['name']}, known for your {persona['style']} style and {persona['postTone']} tone. You're an expert on market analysis, especially {', '.join(persona['focusStocks'])}.

Your Bio: {persona['bio']}
Your Signature Moves: {', '.join(persona['signatureMoves'])}

You will be given a news article, and your task is to write a highly engaging forum post about it.

CONTENT REQUIREMENTS:
- Create a SHORT, IMPACTFUL title (5-8 words maximum) that:
  * Focuses on the key insight or prediction
  * Uses strong action verbs or market terminology
  * NEVER starts with greetings like "Hello" or "Hey traders"
  * Includes the stock name when relevant
  * Is direct, concise, and provocative
- Create unique, opinionated content with your trading perspective
- Include technical terms, specific claims/predictions, and 1-2 relevant hashtags
- Use emojis VERY RARELY - maximum 1 emoji in the entire post, or preferably none
- Write efficiently like a human investor - every word should add value

FORMATTING REQUIREMENTS:
- Use **bold text** for key points and subheadings
- Break content into clear paragraphs for readability
- Use bullet points or numbered lists when presenting multiple points
- Add line breaks between different sections/topics
- Structure the content with logical flow: analysis → opinion → prediction/action

STYLE GUIDELINES:
- Avoid verbosity and repetition
- Focus on impactful, information-dense language
- Maintain your persona's unique voice and expertise
- Include specific stock mentions and technical analysis

You MUST return the output in a valid JSON format with two keys: "title" and "content"."""

    prompt = f"Here is the news article:\nTITLE: {article_title}\nARTICLE: {article_text}\n\nNow, generate the forum post based on this article."

    try:
        # Using the Chat endpoint with a defined response format for reliable JSON output
        response = co.chat(
            message=prompt,
            preamble=preamble,
            model='command-r',  # command-r is well-suited for this kind of structured output task
            temperature=0.8,
            response_format={
                "type": "json_schema",
                "schema": {
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": "A punchy, attention-grabbing title for the forum post."
                        },
                        "content": {
                            "type": "string",
                            "description": "The full content of the forum post, including analysis, persona, and hashtags."
                        }
                    },
                    "required": ["title", "content"]
                }
            }
        )
        
        json_response_text = response.text
        
        # Parse the JSON string into a Python dictionary
        formatted_output = json.loads(json_response_text)
        
        # Basic validation
        if not isinstance(formatted_output, dict) or "title" not in formatted_output or "content" not in formatted_output:
            print(f"Cohere Error: JSON output is not in the expected format. Raw output: {json_response_text}")
            return None

        if not formatted_output.get("title") or not formatted_output.get("content"):
             print(f"Cohere Warning: Generated empty title or content. Raw output: {json_response_text}")
             return None

        return formatted_output

    except json.JSONDecodeError as e:
        print(f"JSON Decode Error: Failed to parse response from Cohere. Raw text: '{response.text}'. Error: {e}")
        return None
    except Exception as e:
        print(f"Cohere API Error: An unexpected error occurred: {e}")
        return None
