import json
import os
import re
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
  """Discovers active text-generation models for this API key in priority order."""
  valid_models = []
  try:
    models = list(client.models.list())
    for m in models:
      name = m.name.replace("models/", "")
      # Filter out non-text endpoints
      if any(
          bad in name
          for bad in ["tts", "image", "clip", "robotics", "computer-use"]
      ):
        continue
      valid_models.append(name)

    priority_order = [
        "gemini-3.7-flash",
        "gemma-4-26b-a4b-it",
        "gemma-4-31b-it",
        "gemini-flash-latest",
        "gemini-3-flash-preview",
        "gemini-3.6-flash",
        "gemini-3.5-flash",
        "gemini-pro-latest",
    ]
    sorted_models = [m for m in priority_order if m in valid_models]
    for m in valid_models:
      if m not in sorted_models:
        sorted_models.append(m)

    print(
        f"Configured {len(sorted_models)} active text model(s):"
        f" {sorted_models[:6]}"
    )
    return sorted_models if sorted_models else ["gemini-3.7-flash"]
  except Exception as e:
    print(f"Error querying model list: {e}")
    return ["gemini-3.7-flash", "gemma-4-26b-a4b-it"]


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


def parse_iso_date(href):
  """Extracts MMDDYYYY from CivicPlus URL and converts to YYYY-MM-DD."""
  match = re.search(r"(\d{2})(\d{2})(\d{4})", href)
  if match:
    month, day, year = match.groups()
    return f"{year}-{month}-{day}"
  return "1970-01-01"


def get_clean_id(href, doc_type):
  iso_date = parse_iso_date(href)
  raw_id = (
      href.split("ViewFile/")[-1]
      .replace("/", "_")
      .replace("?", "_")
      .replace("&", "_")
  )
  return f"{iso_date}_{doc_type}_{raw_id}"


def fetch_new_meeting_links(cache):
  """Scrapes AgendaCenter and extracts only unprocessed Common Council documents."""
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
      iso_date = parse_iso_date(href)

      expected_md = os.path.join(OUTPUT_DIR, f"{clean_id}.md")
      if clean_id in cache and os.path.exists(expected_md):
        continue

      full_url = urljoin(BASE_URL, href)

      new_docs.append({
          "id": clean_id,
          "url": full_url,
          "title": f"Common Council {doc_type} - {text}",
          "doc_type": doc_type,
          "iso_date": iso_date,
          "context": row_text,
      })

  print(
      f"Identified {total_council_docs} total Common Council documents. Found"
      f" {len(new_docs)} new/unprocessed item(s)."
  )
  # Sort strictly descending (newest calendar date first)
  new_docs.sort(key=lambda x: x["iso_date"], reverse=True)
  return new_docs


def extract_text_from_pdf(pdf_path):
  """Extracts plain text locally from the PDF."""
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


def summarize_content_with_gemini(
    text_content, pdf_path, meeting_context, iso_date, doc_type
):
  """Generates briefing with YAML frontmatter containing executive summary."""
  headline = (
      meeting_context.split("—")[0].strip()
      if "—" in meeting_context
      else f"Common Council {doc_type}"
  )

  prompt = f"""
    You are an objective, hyper-local civic reporter for South Milwaukee, WI.
    Analyze this municipal meeting document and write a clean, structured recap for residents.

    Context / Header: {meeting_context}

    Your output MUST begin with YAML frontmatter at the very top. 
    Crucial: Provide a concise 2-sentence overview in the 'summary' frontmatter field without linebreaks or raw quotes.

    ---
    title: "{iso_date} - {headline}"
    date: {iso_date}
    doc_type: "{doc_type}"
    summary: "Brief 2-sentence summary of the main decisions and discussions from this meeting."
    layout: default
    ---

    # {headline} ({iso_date})

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
          config=types.GenerateContentConfig(temperature=0.2),
      )
      summary_result = response.text
      quota_exhausted_all = False
      print(f"Successfully generated summary with {model_name}.")
      break
    except Exception as e:
      err_str = str(e)
      if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
        print(f"Model {model_name} quota reached. Trying next model...")
      elif "503" in err_str or "UNAVAILABLE" in err_str:
        print(f"Model {model_name} high demand. Trying next model...")
      else:
        print(f"Model {model_name} error: {e}")
      time.sleep(1)

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

  max_per_run = 10
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
            text_content,
            pdf_path,
            item["context"],
            item["iso_date"],
            item["doc_type"],
        )

        if summary_md:
          output_filename = os.path.join(OUTPUT_DIR, f"{clean_id}.md")
          with open(output_filename, "w", encoding="utf-8") as out:
            out.write(summary_md)

          print(f"Saved briefing to {output_filename}")

          cache[clean_id] = {
              "url": doc_url,
              "title": item["title"],
              "iso_date": item["iso_date"],
              "doc_type": item["doc_type"],
              "output_file": output_filename,
          }
          save_cache(cache)
          processed_count += 1

        if os.path.exists(pdf_path):
          os.remove(pdf_path)

        if quota_exhausted:
          print("\nAll models currently busy or at quota limit.")
          break

        time.sleep(5)
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
