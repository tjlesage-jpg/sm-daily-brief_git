import json
import os
import time
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from google import genai
from google.genai import types
import requests

# Configuration
BASE_URL = "https://www.southmilwaukee.gov"
AGENDA_CENTER_URL = f"{BASE_URL}/AgendaCenter"
CACHE_FILE = "processed_meetings.json"
OUTPUT_DIR = "briefings"
DOWNLOAD_DIR = "downloads"

# Candidate models in order of preference
FALLBACK_MODELS = [
    "gemini-2.0-flash",
    "gemini-2.5-flash",
    "gemini-flash",
    "gemini-3.7-flash",
]

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


def get_clean_id(href, doc_type):
  """Generates a stable unique ID string from the CivicPlus URL."""
  raw_id = (
      href.split("ViewFile/")[-1]
      .replace("/", "_")
      .replace("?", "_")
      .replace("&", "_")
  )
  return f"{doc_type}_{raw_id}"


def fetch_new_meeting_links(cache):
  """Scrapes AgendaCenter and IMMEDIATELY filters out already processed files."""
  headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
  print(f"Checking {AGENDA_CENTER_URL} for new Common Council documents...")
  response = requests.get(AGENDA_CENTER_URL, headers=headers, timeout=30)
  response.raise_for_status()

  soup = BeautifulSoup(response.text, "html.parser")
  new_docs = []
  total_council_docs = 0

  for link in soup.find_all("a", href=True):
    href = link["href"]
    text = link.get_text(strip=True)

    if "/AgendaCenter/ViewFile/" in href:
      parent_row = link.find_parent("tr") or link.find_parent("div")
      row_text = parent_row.get_text(" ", strip=True) if parent_row else text

      # Filter exclusively for Common Council
      is_common_council = (
          "common council" in row_text.lower()
          or "common council" in text.lower()
      )
      if not is_common_council:
        continue

      total_council_docs += 1
      doc_type = (
          "Minutes"
          if "minutes" in href.lower() or "minutes" in text.lower()
          else "Agenda"
      )
      clean_id = get_clean_id(href, doc_type)

      # Fast Pre-Filter: check if already in cache and markdown file exists
      expected_md = os.path.join(OUTPUT_DIR, f"{clean_id}.md")
      if clean_id in cache and os.path.exists(expected_md):
        continue

      full_url = urljoin(BASE_URL, href)
      new_docs.append({
          "id": clean_id,
          "url": full_url,
          "title": f"Common Council {doc_type} - {text}",
          "doc_type": doc_type,
          "context": row_text,
      })

  print(
      f"Identified {total_council_docs} total Common Council documents. Found"
      f" {len(new_docs)} new/unprocessed item(s)."
  )

  # Prioritize Minutes over Agendas
  new_docs.sort(key=lambda x: 0 if x["doc_type"] == "Minutes" else 1)
  return new_docs


def is_pdf(content):
  return content.startswith(b"%PDF")


def summarize_pdf_with_gemini(pdf_path, meeting_context):
  """Uploads PDF and tries models in fallback sequence until successful."""
  print(f"Uploading {pdf_path} to Gemini...")
  uploaded_file = client.files.upload(file=pdf_path)

  headline = (
      meeting_context.split("—")[0].strip()
      if "—" in meeting_context
      else "Common Council Meeting"
  )

  prompt = f"""
    You are an objective, hyper-local civic reporter for South Milwaukee, WI.
    Analyze this municipal meeting document and write a clean, structured recap for residents.

    Context / Header: {meeting_context}

    Your output MUST begin with YAML frontmatter at the very top:
    ---
    title: "{headline}"
    layout: default
    ---

    # {headline}

    **Document Context:** {meeting_context}

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

  last_error = None
  response_text = None

  for model_name in FALLBACK_MODELS:
    try:
      print(f"Attempting generation with model: {model_name}...")
      response = client.models.generate_content(
          model=model_name,
          contents=[uploaded_file, prompt],
          config=types.GenerateContentConfig(
              temperature=0.2,
          ),
      )
      response_text = response.text
      print(f"Successfully generated summary with {model_name}.")
      break
    except Exception as e:
      print(f"Model {model_name} failed ({e}). Trying next fallback...")
      last_error = e
      time.sleep(3)

  try:
    client.files.delete(name=uploaded_file.name)
  except Exception:
    pass

  if response_text:
    return response_text
  raise last_error


def main():
  cache = load_cache()
  new_docs = fetch_new_meeting_links(cache)

  if not new_docs:
    print("All Common Council meetings are up to date. Nothing to do.")
    return

  # Process in batches of 5 to stay safely within free-tier burst limits
  max_per_run = 5
  processed_count = 0

  for item in new_docs[:max_per_run]:
    doc_url = item["url"]
    clean_id = item["id"]

    print(
        f"\nProcessing [{processed_count + 1}/{min(len(new_docs), max_per_run)}]:"
        f" {item['title']}..."
    )
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
      res = requests.get(doc_url, headers=headers, timeout=45)
      if res.status_code == 200 and (
          is_pdf(res.content)
          or "pdf" in res.headers.get("Content-Type", "").lower()
      ):
        pdf_path = os.path.join(DOWNLOAD_DIR, f"{clean_id}.pdf")
        with open(pdf_path, "wb") as f:
          f.write(res.content)

        summary_md = summarize_pdf_with_gemini(pdf_path, item["context"])

        output_filename = os.path.join(OUTPUT_DIR, f"{clean_id}.md")
        with open(output_filename, "w", encoding="utf-8") as out:
          out.write(summary_md)

        print(f"Saved briefing to {output_filename}")

        cache[clean_id] = {
            "url": doc_url,
            "title": item["title"],
            "doc_type": item["doc_type"],
            "context": item["context"],
            "output_file": output_filename,
        }
        save_cache(cache)
        processed_count += 1

        if os.path.exists(pdf_path):
          os.remove(pdf_path)

      else:
        print(f"Skipping non-PDF link: {doc_url}")
    except Exception as e:
      print(f"Error processing {doc_url}: {e}")

    # Mandatory cooldown between attempts to stay well below rate limits
    time.sleep(10)

  print(
      f"\nBatch complete. Successfully summarized {processed_count} new Common"
      " Council document(s)."
  )


if __name__ == "__main__":
  main()
