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
    """Scrapes AgendaCenter focusing on Common Council and board minutes/agendas."""
    headers = {"User-Agent": "Mozilla/5.0"}
    print(f"Fetching {AGENDA_CENTER_URL}...")
    response = requests.get(AGENDA_CENTER_URL, headers=headers, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    found_docs = []

    for link in soup.find_all("a", href=True):
        href = link["href"]
        text = link.get_text(strip=True)

        if "viewfile" in href.lower() or href.lower().endswith(".pdf"):
            full_url = urljoin(BASE_URL, href)
            parent_row = link.find_parent("tr") or link.find_parent("div")
            row_text = parent_row.get_text(" ", strip=True) if parent_row else text

            found_docs.append({
                "url": full_url,
                "title": text or "Document",
                "context": row_text
            })

    print(f"Total matching document links identified: {len(found_docs)}")
    return found_docs


def is_pdf(content):
    return content.startswith(b"%PDF")


def summarize_pdf_with_gemini(pdf_path, meeting_context):
    """Uploads PDF to Gemini and produces a structured briefing."""
    print(f"Uploading {pdf_path} to Gemini...")
    uploaded_file = client.files.upload(file=pdf_path)

    prompt = f"""
    You are an objective, hyper-local civic reporter for South Milwaukee, WI.
    Analyze this municipal meeting document and write a clean, structured recap for residents.

    Context / Header: {meeting_context}

    Format the output in clean Markdown with the following structure:
    # {meeting_context.split('—')[0].strip() if '—' in meeting_context else 'South Milwaukee Municipal Briefing'}

    **Document:** {meeting_context}

    ### Executive Summary
    Brief 2-3 sentence overview of the meeting's primary focus.

    ### Key Decisions & Roll Call Votes
    - List passed resolutions, ordinances, appointments, or approvals.
    - Include specific roll call tallies (e.g. 7-0) and dollar amounts where present.

    ### Infrastructure, Utilities & Public Works
    - Highlight contracts, bids, road work, water/wastewater items.

    ### Business, Licensing & Community
    - Note licenses granted, events approved, or public hearings held.

    ### Citizen Impact / Takeaways
    - Plain-language summary of what this means for local residents and taxpayers.
    """

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[uploaded_file, prompt],
        config=types.GenerateContentConfig(
            temperature=0.2,
        )
    )

    try:
        client.files.delete(name=uploaded_file.name)
    except Exception:
        pass

    return response.text


def main():
    cache = load_cache()
    docs = fetch_meeting_links()

    # Process up to 5 documents per run
    processed_count = 0
    max_per_run = 5

    for item in docs:
        if processed_count >= max_per_run:
            print(f"Reached batch limit of {max_per_run} files for this run.")
            break

        doc_url = item["url"]
        clean_id = doc_url.split("ViewFile/")[-1].replace("/", "_").replace("?", "_").replace("&", "_")

        if clean_id in cache:
            continue

        print(f"\nProcessing [{processed_count + 1}/{max_per_run}]: {item['context'][:70]}...")
        headers = {"User-Agent": "Mozilla/5.0"}
        
        try:
            res = requests.get(doc_url, headers=headers, timeout=45)
            if res.status_code == 200 and (is_pdf(res.content) or "pdf" in res.headers.get("Content-Type", "").lower()):
                pdf_path = os.path.join(DOWNLOAD_DIR, f"{clean_id}.pdf")
                with open(pdf_path, "wb") as f:
                    f.write(res.content)

                # Generate summary
                summary_md = summarize_pdf_with_gemini(pdf_path, item["context"])
                
                output_filename = os.path.join(OUTPUT_DIR, f"{clean_id}.md")
                with open(output_filename, "w", encoding="utf-8") as out:
                    out.write(summary_md)

                print(f"Saved briefing to {output_filename}")
                
                cache[clean_id] = {
                    "url": doc_url,
                    "title": item["title"],
                    "context": item["context"],
                    "output_file": output_filename
                }
                save_cache(cache)
                processed_count += 1

                # Clean up local PDF file to save disk space
                if os.path.exists(pdf_path):
                    os.remove(pdf_path)

            else:
                print(f"Skipping non-PDF link: {doc_url}")
        except Exception as e:
            print(f"Error processing {doc_url}: {e}")

    print(f"\nBatch complete. Successfully summarized {processed_count} new document(s).")


if __name__ == "__main__":
    main()
