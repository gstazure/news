import os
import random
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
model = genai.GenerativeModel("models/gemini-1.5-flash-latest")  # fast and cheap


def generate_reply(post_text, persona):
    prompt = f"""
Act as a forum member with this persona:
Name: {persona['name']}
Style: {persona['style']}
Bio: {persona['bio']}
Reply tone: {persona['replyTone']}
Signature moves: {', '.join(persona['signatureMoves'])}

Another user has posted this:
\"\"\"
{post_text}
\"\"\"

Write a reply that:
1. Maintains your unique persona and style
2. Uses your signature moves
3. Keeps your typical {persona['replyTone']} tone
4. Is brief (2-3 sentences)
5. Adds value through insight or a different perspective
6. Stays authentic to your character
7. Avoids simply agreeing or repeating
8. Uses plain text formatting only - DO NOT use markdown formatting like *bold*, _italic_, or other markup

Remember: You are {persona['name']}, known for {persona['style']} style and {persona['replyTone']} tone.
"""
    try:
        response = model.generate_content(prompt)
        reply = response.text.strip()
        # Strip markdown formatting characters
        # Remove markdown formatting
        import re
        # Remove bold (**text** or __text__)
        reply = re.sub(r'\*\*(.*?)\*\*', r'\1', reply)
        reply = re.sub(r'__(.*?)__', r'\1', reply)
        # Remove italic (*text* or _text_)
        reply = re.sub(r'\*(.*?)\*', r'\1', reply)
        reply = re.sub(r'_(.*?)_', r'\1', reply)
        # Remove inline code (`code`)
        reply = re.sub(r'`(.*?)`', r'\1', reply)
        # Remove headings (# Heading)
        reply = re.sub(r'^\s*#+\s*(.*?)\s*$', r'\1', reply, flags=re.MULTILINE)
        # Remove other common markdown patterns
        reply = re.sub(r'~~(.*?)~~', r'\1', reply)  # strikethrough
        return reply
    except Exception as e:
        print(f"Error generating reply: {e}")
        return ""
