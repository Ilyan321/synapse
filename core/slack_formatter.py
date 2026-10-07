import re

def markdown_to_slack(text: str) -> str:
    """
    Converts standard GitHub/LLM Markdown into clean, native Slack mrkdwn.
    - Converts **bold** to *bold* (fixing double asterisk artifacts)
    - Converts ### Headers into *HEADER*
    - Cleans up excessive horizontal rules and markdown formatting
    """
    if not text:
        return ""

    # 1. Convert bold: **text** -> *text*
    text = re.sub(r'\*\*(.*?)\*\*', r'*\1*', text)

    # 2. Convert headers: # Header, ## Header, ### Header -> *HEADER*
    text = re.sub(r'^#{1,6}\s*(.*?)$', r'*\1*', text, flags=re.MULTILINE)

    # 3. Clean up horizontal rules: --- or ___
    text = re.sub(r'^\s*[-*_]{3,}\s*$', '', text, flags=re.MULTILINE)

    # 4. Fix double bullet points: * * item -> • item
    text = re.sub(r'^\s*[\*\-]\s+', r'• ', text, flags=re.MULTILINE)

    # 5. Remove multiple consecutive blank lines
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()
