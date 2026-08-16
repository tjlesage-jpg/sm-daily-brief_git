import os
import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from google import genai
from google.genai import types

# Configuration
BASE_URL = "https://www.southmilwaukee.gov"
AGENDA_CENTER_URL = f"{BASE_URL}/AgendaCenter"
CACHE_FILE = "processed_meetings.json"
OUTPUT_DIR = "briefings"
DOWNLOAD_DIR = "downloads"

# Initialize Google GenAI client
client = genai.Client()

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(DOWNLOAD_DIR, exist_ok=True)


def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_cache(cache):
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2)


def fetch_meeting_links():
    """Scrapes AgendaCenter for minutes and agenda PDF links."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    print(f"Fetching {AGENDA_CENTER_URL}...")
    response = requests.get(AGENDA_CENTER_URL, headers=headers, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    found_docs = []

    # Search for all links containing 'ViewFile' or ending with '.pdf'
    for link in soup.find_all("a", href=True):
        href = link["href"]
        text = link.get_text(strip=True)

        if "viewfile" in href.lower() or href.lower().endswith(".pdf"):
            full_url = urljoin(BASE_URL, href)
            
            # Find surrounding row or category context
            parent_row = link.find_parent("tr") or link.find_parent("div")
            row_text = parent_row.get_text(" ", strip=True) if parent_row else text

            # Prefer Common Council items if context is present
            found_docs.append({
                "url": full_url,
                "title": text or "Document",
                "context": row_text
            })

    print(f"Total matching document links identified: {len(found_docs)}")
    return found_docs


def is_pdf(response_bytes):
    """Checks if the downloaded content starts with PDF header bytes."""
    return response_bytes.startswith(b"%PDF")


def summarize_pdf_with_gemini(pdf_path, meeting_context):
    """Uploads PDF to Gemini and produces a markdown briefing."""
    print(f"Uploading {pdf_path} to Gemini...")
    uploaded_file = client.files.upload(file=pdf_path)

    prompt = f"""
    You are an objective, hyper-local civic reporter for South Milwaukee, WI.
    Analyze this municipal meeting document and write a clean, structured recap for residents.

    Context: {meeting_context}

    Format the output in Markdown with the following sections:
    - **Headline & Date**
    - **Key Decisions & Votes Passed** (List exact roll calls, ordinances, and dollar amounts if present)
    - **Public Works & Infrastructure Updates**
    - **Permits, Licenses & Local Businesses**
    - **Citizen Impact / What Residents Should Know**

    Maintain a neutral, factual, and scannable tone. Do not include conversational introductory fluff.
    """

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[uploaded_file, prompt],
        config=types.GenerateContentConfig(
            temperature=0.2,
        )
    )

    # Clean up uploaded file
    try:
        client.files.delete(name=uploaded_file.name)
    except Exception:
        pass

    return response.text


def main():
    cache = load_cache()
    docs = fetch_meeting_links()

    # Process up to 5 newest unread items per run to stay well within rate/time limits
    processed_this_run = 0
    max_items_per_run = 5

    for item in docs:
        if processed_this_run >= max_items_per_run:
            print(f"Reached batch limit of {max_items_per_run} files for this run.")
            break

        doc_url = item["url"]
        
        # Clean unique ID
        clean_id = doc_url.split("ViewFile/")[-1].replace("/", "_").replace("?", "_").replace("&", "_")

        if clean_id in cache:
            continue

        print(f"\nDownloading: {item['title']} | Context: {item['context'][:80]}...")
        headers = {"User-Agent": "Mozilla/5.0"}
        
        try:
            res = requests.get(doc_url, headers=headers, timeout=45)
            if res.status_code == 200 and (is_pdf(res.content) or "pdf" in res.headers.get("Content-Type", "").lower()):
                pdf_path = os.path.join(DOWNLOAD_DIR, f"{clean_id}.pdf")
                with open(pdf_path, "wb") as f:
                    f.write(res.content)

                summary_md = summarize_pdf_with_gemini(pdf_path, item["context"])
                
                output_filename = os.path.join(OUTPUT_DIR, f"{clean_id}_briefing.md")
                with open(output_filename, "w", encoding="utf-8") as out:
                    out.write(summary_md)

                print(f"Successfully generated briefing: {output_filename}")
                
                cache[clean_id] = {
                    "url": doc_url,
                    "title": item["title"],
                    "context": item["context"],
                    "output_file": output_filename
                }
                save_cache(cache)
                processed_this_run += 1
            else:
                print(f"Skipping: Content at {doc_url} is not a valid PDF (Status: {res.status_code})")
        except Exception as e:
            print(f"Error processing {doc_url}: {e}")

    print(f"\nRun complete. Processed {processed_this_run} new document(s).")


if __name__ == "__main__":
    main()
