import json

# Test the JSON parsing logic with markdown code fences
def test_json_parsing():
    # Simulate what Gemini returns
    gemini_response = '''```json
{
  "summary": "This is a SELL signal for XAGUSD on the 30-minute timeframe, targeting 43.345 with a stop-loss at 44.014, resulting in a risk-reward ratio of approximately 4.7. The signal is based on a short-term and ultra-term alignment near a pivot low, suggesting a high probability of a price drop.",
  "confidence": 85
}
```'''

    print("Testing Gemini response parsing...")
    print(f"Raw response: {gemini_response}")
    print()
    
    ai_summary = None
    ai_conf = None
    txt = gemini_response.strip()
    
    if txt:
        try:
            # First try to parse as direct JSON
            parsed = json.loads(txt)
            ai_summary = parsed.get("summary")
            ai_conf = parsed.get("confidence")
            print(f"✓ Parsed direct JSON - Summary: {ai_summary}, Confidence: {ai_conf}")
        except Exception as e:
            print(f"✗ Direct JSON parsing failed: {e}")
            try:
                # Try to extract JSON from markdown code fences
                if "```json" in txt:
                    # Extract content between ```json and ```
                    start = txt.find("```json") + 7
                    end = txt.find("```", start)
                    if end != -1:
                        json_text = txt[start:end].strip()
                    else:
                        json_text = txt[start:].strip()
                    print(f"Extracted JSON text: {json_text}")
                    parsed = json.loads(json_text)
                    ai_summary = parsed.get("summary")
                    ai_conf = parsed.get("confidence")
                    print(f"✓ Parsed JSON from code fence - Summary: {ai_summary}, Confidence: {ai_conf}")
                else:
                    raise ValueError("No JSON found")
            except Exception as e2:
                print(f"✗ Code fence parsing also failed: {e2}")
                # Final fallback: use raw text as summary
                ai_summary = txt[:250]  # Truncate if too long
                ai_conf = None
                print(f"Using raw text as summary: {ai_summary}")
    
    print(f"\nFinal result:")
    print(f"Summary: {ai_summary}")
    print(f"Confidence: {ai_conf}")

if __name__ == "__main__":
    test_json_parsing()