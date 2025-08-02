import json
from replies import generate_reply

# Test post text
test_post_text = "Dreamfolks IPO has dropped 5% today with significant selling from Motilal Oswal and Bajaj Finance."

# Test persona that might generate markdown formatting
test_persona = {
    "name": "betaice961",
    "style": "cynical bear",
    "bio": "Market's going down. Always has been.",
    "replyTone": "sarcastic",
    "signatureMoves": ["uses sarcasm", "predicts doom"]
}

print("Testing reply generation...")
print(f"Post text: {test_post_text}")
print(f"Persona: {test_persona['name']} ({test_persona['style']})")

# Generate reply
reply = generate_reply(test_post_text, test_persona)

print("\nGenerated Reply:")
print(reply)

# Check if reply contains markdown formatting
if "*" in reply or "_" in reply or "#" in reply:
    print("\nWARNING: Reply contains markdown formatting characters!")
else:
    print("\nSUCCESS: Reply is in plain text format.")