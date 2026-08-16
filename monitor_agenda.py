import json
import os
import time
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from google import genai
from google.genai import types
from pypdf import PdfReader
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


def get_active_models():
  """Discovers all currently supported generateContent models for this API key."""
  valid_models = []
  try:
    models = list(client.models.list())
    for m in models:
      name = m.name.replace("models/", "")
      # Look for models capable of text generation
      if hasattr(m, "supported_actions") and (
          "generateContent" in m.supported_actions or not m.supported_actions
      ):
        valid_models.append(name)
      elif not hasattr(m, "supported_actions"):
        valid_models.append(name)

    # Sort so flash/fast models are attempted first
    preferred_order = [
        "gemini-3.7-flash",
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-1.5-flash",
        "gemini-1.5-pro",
    ]
    sorted_models = []
    for pref in preferred_order:
      for vm in valid_models:
        if pref in vm and vm not in sorted_models:
          sorted_models.append(vm)

    for vm in valid_models:
      if vm not in sorted_models:
        sorted_models.append(vm)

    print(f"Discovered {len(sorted_models)} active model(s): {sorted_models}")
    return sorted_models if sorted_models else ["gemini-3.7-flash"]
  except Exception as e:
    print(f"Error querying model list: {e}")
    return ["gemini-3.7-flash"]


AVAILABLE_MODELS = get_active_models()


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
  raw_id = (
      href.split("ViewFile/")[-1]
      .replace("/", "_")
      .replace("?", "_")
      .replace("&", "_")
  )
  return f"{doc_type}_{raw_id}"


def fetch_new_meeting_links(cache):
  """Scrapes AgendaCenter and extracts only new Common Council documents."""
  headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
  print(f"Checking {AGENDA_CENTER_URL} for Common Council documents...")
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

      if not (
          "common council" in row_text.lower()
          or "common council" in text.lower()
      ):
        continue

      total_council_docs += 1
      doc_type = (
          "Minutes"
          if "minutes" in href.lower() or "minutes" in text.lower()
          else "Agenda"
      )
      clean_id = get_clean_id(href, doc_type)

      # Skip if already recorded and markdown file exists
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


def extract_text_from_pdf(pdf_path):
  """Extracts clean text directly from PDF without uploading to Files API."""
  try:
    reader = PdfReader(pdf_path)
    text = ""
    for page in reader.pages:
      page_text = page.extract_text()
      if page_text:
        text += page_text + "\n"
    return text.strip()
  except Exception as e:
    print(f"Local PDF text extraction failed for {pdf_path}: {e}")
    return ""


def summarize_content_with_gemini(text_content, pdf_path, meeting_context):
  """Summarizes meeting content with dynamic model fallback and rate limit handling."""
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

  # Prepare payload: use local text if available, fallback to file upload
  uploaded_file = None
  if text_content and len(text_content) > 100:
    contents = [text_content, prompt]
  else:
    print(
        f"PDF does not contain plain text; uploading {pdf_path} to Gemini..."
    )
    uploaded_file = client.files.upload(file=pdf_path)
    contents = [uploaded_file, prompt]

  summary_result = None
  quota_exhausted_all = True

  for model_name in AVAILABLE_MODELS:
    try:
      print(f"Calling Gemini model: {model_name}...")
      response = client.models.generate_content(
          model=model_name,
          contents=contents,
          config=types.GenerateContentConfig(
              temperature=0.2,
          ),
      )
      summary_result = response.text
      quota_exhausted_all = False
      print(f"Successfully generated summary with {model_name}.")
      break
    except Exception as e:
      err_str = str(e)
      if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
        print(f"Model {model_name} hit daily/rate quota. Trying next model...")
      elif "503" in err_str or "UNAVAILABLE" in err_str:
        print(
            f"Model {model_name} temporarily high demand. Trying next model..."
        )
      else:
        print(f"Model {model_name} error: {e}")
      time.sleep(2)

  if uploaded_file:
    try:
      client.files.delete(name=uploaded_file.name)
    except Exception:
      pass

  return summary_result, quota_exhausted_all


def main():
  cache = load_cache()
  new_docs = fetch_new_meeting_links(cache)

  if not new_docs:
    print("All Common Council meetings are up to date. Nothing to do.")
    return

  # Process up to 5 documents per daily run to stay well within free tier limits
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
          res.content.startswith(b"%PDF")
          or "pdf" in res.headers.get("Content-Type", "").lower()
      ):
        pdf_path = os.path.join(DOWNLOAD_DIR, f"{clean_id}.pdf")
        with open(pdf_path, "wb") as f:
          f.write(res.content)

        text_content = extract_text_from_pdf(pdf_path)
        summary_md, quota_exhausted = summarize_content_with_gemini(
            text_content, pdf_path, item["context"]
        )

        if summary_md:
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

        if quota_exhausted:
          print(
              "\nAll available models have exhausted their free-tier quota for"
              " today."
          )
          print(
              "Saved completed items. The remaining backlog will automatically"
              " continue on the next scheduled run."
          )
          break

        # Throttling to prevent burst-rate spikes
        time.sleep(10)

      else:
        print(f"Skipping non-PDF link: {doc_url}")
    except Exception as e:
      print(f"Error processing {doc_url}: {e}")

  print(
      f"\nRun complete. Successfully generated {processed_count} new"
      " briefing(s)."
  )


if __name__ == "__main__":
  main()
