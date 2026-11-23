import truststore
truststore.inject_into_ssl()

import urllib.error
import urllib.request

URLS = [
    "https://api.groq.com",
    "https://generativelanguage.googleapis.com",
    "https://api.smith.langchain.com/info",
    "https://api.openai.com",
]

for url in URLS:
    try:
        body = urllib.request.urlopen(url, timeout=10).read(2000).decode(errors="ignore")
        print("BLOCKED " if "netfree" in body else "OPEN    ", url)
    except urllib.error.HTTPError as e:
        body = e.read(2000).decode(errors="ignore")
        print("BLOCKED " if "netfree" in body else "OPEN    ", url, f"({e.code})")
    except Exception as e:
        print("ERROR   ", url, type(e).__name__, e)