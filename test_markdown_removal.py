import re

def remove_markdown(text):
    # Remove bold (**text** or __text__)
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'__(.*?)__', r'\1', text)
    # Remove italic (*text* or _text_)
    text = re.sub(r'\*(.*?)\*', r'\1', text)
    text = re.sub(r'_(.*?)_', r'\1', text)
    # Remove inline code (`code`)
    text = re.sub(r'`(.*?)`', r'\1', text)
    # Remove headings (# Heading)
    text = re.sub(r'^\s*#+\s*(.*?)\s*$', r'\1', text, flags=re.MULTILINE)
    # Remove other common markdown patterns
    text = re.sub(r'~~(.*?)~~', r'\1', text)  # strikethrough
    return text

# Test cases with markdown formatting
test_cases = [
    "Oh, *another* market crash? Color me shocked.",
    "OMG! This is *amazing* DD! Are you guys ALL IN?",
    "This is **bold** text and this is *italic* text.",
    "Here's some `inline code` in the text.",
    "# This is a heading",
    "This is ~~strikethrough~~ text.",
    "This is __bold__ text and this is _italic_ text."
]

print("Testing markdown removal:")
for i, test_case in enumerate(test_cases, 1):
    result = remove_markdown(test_case)
    print(f"{i}. Original: {test_case}")
    print(f"   Result:   {result}")
    print()