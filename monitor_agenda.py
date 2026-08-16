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

client = genai.Client()

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(DOWNLOAD_DIR, exist_ok=True)


def get_available_model():
    """Dynamically queries the API to select the best active model."""
    try:
        models = list(client.models.list())
        supported = [
            m.name
            for m in models
            if (hasattr(m, "supported_actions") and "generateContent" in m.supported_actions)
            or hasattr(m, "name")
        ]
        # Priority order for active, high-quota Gemini models
        for candidate in [
            "gemini-3.7-flash",
            "gemini-2.0-flash",
            "gemini-flash",
        ]:
            for m in supported:
                if candidate in m:
                    model_name = m.replace("models/", "")
                    print(f"Selected active Gemini model: {model_name}")
                    return model_name
        if supported:
            return supported[0].replace("models/", "")
    except Exception as e:
        print(f"Model lookup fallback: {e}")
    return "gemini-3.7-flash"


ACTIVE_MODEL = get_available_model()


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
  """Scrapes AgendaCenter specifically targeting Common Council documents."""
  headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
  print(f"Fetching {AGENDA_CENTER_URL}...")
  response = requests.get(AGENDA_CENTER_URL, headers=headers, timeout=30)
  response.raise_for_status()

  soup = BeautifulSoup(response.text, "html.parser")
  found_docs = []

  for link in soup.find_all("a", href=True):
    href = link["href"]
    text = link.get_text(strip=True)

    if "/AgendaCenter/ViewFile/" in href:
      full_url = urljoin(BASE_URL, href)
      parent_row = link.find_parent("tr") or link.find_parent("div")
      row_text = parent_row.get_text(" ", strip=True) if parent_row else text

      # Filter: Focus on Common Council (or include Plan Commission / Public Works if desired)
      is_common_council = "common council" in row_text.lower() or "common council" in text.lower()
      
      # Determine if document is Minutes or Agenda
      doc_type = "Minutes" if "minutes" in href.lower() or "minutes" in text.lower() else "Agenda"

      if is_common_council:
        found_docs.append({
            "url": full_url,
            "title": f"Common Council {doc_type} - {text}",
            "doc_type": doc_type,
            "context": row_text,
        })

  print(f"Identified {len(found_docs)} Common Council document links.")
  # Prioritize Minutes over Agendas
  found_docs.sort(key=lambda x: 0 if x["doc_type"] == "Minutes" else 1)
  return found_docs


def is_pdf(content):
  return content.startswith(b"%PDF")


def summarize_pdf_with_gemini(pdf_path, meeting_context):
  """Uploads PDF to Gemini and produces a structured briefing with Jekyll frontmatter."""
  print(f"Uploading {pdf_path} to Gemini...")
  uploaded_file = client.files.upload(file=pdf_path)

  headline = meeting_context.split("—")[0].strip() if "—" in meeting_context else "Common Council Meeting"

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

  response = client.models.generate_content(
      model=ACTIVE_MODEL,
      contents=[uploaded_file, prompt],
      config=types.GenerateContentConfig(
          temperature=0.2,
      ),
  )

  try:
    client.files.delete(name=uploaded_file.name)
  except Exception:
    pass

  return response.text


def main():
  cache = load_cache()
  docs = fetch_meeting_links()

  processed_count = 0
  # Increased to 10 to capture all recent council meetings
  max_per_run = 10

  for item in docs:
    if processed_count >= max_per_run:
      print(f"Reached batch limit of {max_per_run} files for this run.")
      break

    doc_url = item["url"]
    
    # Construct a unique ID that includes doc type (Minutes vs Agenda)
    raw_id = doc_url.split("ViewFile/")[-1].replace("/", "_").replace("?", "_").replace("&", "_")
    clean_id = f"{item['doc_type']}_{raw_id}"

    if clean_id in cache:
      continue

    print(f"\nProcessing [{processed_count + 1}/{max_per_run}]: {item['title']}...")
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
      res = requests.get(doc_url, headers=headers, timeout=45)
      if res.status_code == 200 and (is_pdf(res.content) or "pdf" in res.headers.get("Content-Type", "").lower()):
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

        # 12-second throttle to respect Gemini Free Tier rate limits (5 RPM)
        time.sleep(12)

      else:
        print(f"Skipping non-PDF link: {doc_url}")
    except Exception as e:
      print(f"Error processing {doc_url}: {e}")

  print(f"\nBatch complete. Successfully summarized {processed_count} Common Council document(s).")


if __name__ == "__main__":
  main()
