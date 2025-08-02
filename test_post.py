from postgen import generate_post

# Test article
test_article_title = "RBI Announces New Digital Banking Guidelines for 2025"
test_article_text = """The Reserve Bank of India (RBI) today unveiled comprehensive guidelines for digital banking operations, setting new standards for cybersecurity, customer protection, and technological infrastructure. The framework requires banks to maintain a 99.99% uptime for critical digital services and implement advanced AI-based fraud detection systems. The guidelines also introduce a new category of 'Digital First' banking licenses, potentially opening doors for fintech companies to enter the banking sector."""

# Test persona
test_persona = {
    "name": "TechFinAnalyst",
    "style": "analytical",
    "postTone": "professional",
    "focusStocks": ["HDFC Bank", "ICICI Bank", "SBI"],
    "bio": "Former fintech executive turned market analyst. Specialized in banking technology and digital transformation.",
    "signatureMoves": ["Deep dive into technical implications", "Forward-looking impact analysis"]
}

# Generate and print the post
result = generate_post(test_article_title, test_article_text, test_persona)
print("\nGenerated Post:\n")
print(result)
