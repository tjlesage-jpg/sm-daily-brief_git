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

# Initialize Google GenAI client (picks up GEMINI_API_KEY from environment)
client = genai.Client()

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(DOWNLOAD_DIR, exist_ok=True)


def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
    return {}


def save_cache(cache):
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2)


def fetch_meeting_links():
    """Scrapes the AgendaCenter page for PDF minutes and agendas."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    response = requests.get(AGENDA_CENTER_URL, headers=headers)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    found_docs = []

    # Target table rows and download links in CivicPlus AgendaCenter
    for link in soup.find_all("a", href=True):
        href = link["href"]
        text = link.get_text(strip=True)

        if "/AgendaCenter/ViewFile/" in href:
            full_url = urljoin(BASE_URL, href)
            
            # Determine document label and surrounding row text
            parent_row = link.find_parent("tr") or link.find_parent("div")
            row_text = parent_row.get_text(" ", strip=True) if parent_row else text

            found_docs.append({
                "url": full_url,
                "title": text or "Document",
                "context": row_text
            })

    return found_docs


def summarize_pdf_with_gemini(pdf_path, meeting_context):
    """Uploads the PDF to Gemini and extracts a structured local briefing."""
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

    Maintain a neutral, factual, and scannable tone. Do not include introductory fluff.
    """

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[uploaded_file, prompt],
        config=types.GenerateContentConfig(
            temperature=0.2,
        )
    )

    # Clean up the file from Gemini cloud storage after generation
    client.files.delete(name=uploaded_file.name)

    return response.text


def main():
    cache = load_cache()
    docs = fetch_meeting_links()
    print(f"Discovered {len(docs)} documents on AgendaCenter.")

    for item in docs:
        doc_url = item["url"]
        
        # Extract unique document ID from CivicPlus URL to prevent duplicate work
        doc_id = doc_url.split("ViewFile/")[-1].replace("/", "_").replace("?", "_")

        if doc_id in cache:
            continue

        print(f"\nProcessing new document: {item['context']}")
        pdf_path = os.path.join(DOWNLOAD_DIR, f"{doc_id}.pdf")

        # Download the PDF
        res = requests.get(doc_url, stream=True)
        if res.status_code == 200 and "application/pdf" in res.headers.get("Content-Type", ""):
            with open(pdf_path, "wb") as f:
                for chunk in res.iter_content(chunk_size=8192):
                    f.write(chunk)

            # Summarize via Gemini
            try:
                summary_md = summarize_pdf_with_gemini(pdf_path, item["context"])
                
                # Save briefing markdown
                output_filename = os.path.join(OUTPUT_DIR, f"{doc_id}_briefing.md")
                with open(output_filename, "w", encoding="utf-8") as out:
                    out.write(summary_md)

                print(f"Saved briefing to: {output_filename}")
                
                # Mark as processed in cache
                cache[doc_id] = {
                    "url": doc_url,
                    "title": item["title"],
                    "context": item["context"],
                    "output_file": output_filename
                }
                save_cache(cache)

            except Exception as e:
                print(f"Error processing {doc_id}: {e}")
        else:
            print(f"Skipping non-PDF link: {doc_url}")


if __name__ == "__main__":
    main()
