from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, TimeoutException, StaleElementReferenceException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium_stealth import stealth
import rich
import csv
from urllib.parse import urljoin, urlparse, parse_qs, quote_plus
import time
import random
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()
import os
BRIGHTDATA_API_KEY = os.getenv("BRIGHTDATA_API_KEY")

# Logging setup
import logging
logging.basicConfig(level=logging.INFO, format='%(message)s')

# ---------------- Config ----------------
BASE = "https://uk.indeed.com"   # match the domain you are scraping
QUERY = "AI Engineer"
LOCATION = "London, Greater London"
RADIUS = 25
PAGES = 20 # how many pages to fetch
RESULTS_STEP = 10    # Indeed pages usually use step=10



# Bright Data API config
BRIGHTDATA_API_URL = "https://api.brightdata.com/request"
BRIGHTDATA_HEADERS = {
    "Authorization": f"Bearer {BRIGHTDATA_API_KEY}",
    "Content-Type": "application/json"
}
BRIGHTDATA_ZONE = "web_unlocker1"

# ---------------- Driver ----------------
# (Removed: Selenium/Chrome driver setup, not needed for Bright Data/requests scraping)

def build_search_url(page_index: int) -> str:
    start = page_index * RESULTS_STEP
    return f"{BASE}/jobs?q={quote_plus(QUERY)}&l={quote_plus(LOCATION)}&radius={RADIUS}&start={start}"

def fetch_with_brightdata(url: str) -> str:
    data = {
        "zone": BRIGHTDATA_ZONE,
        "url": url,
        "format": "raw"
    }
    try:
        response = requests.post(BRIGHTDATA_API_URL, json=data, headers=BRIGHTDATA_HEADERS, timeout=30)
        response.raise_for_status()
        return response.text
    except Exception as e:
        logging.error(f"Bright Data API error for {url}: {e}")
        return None

def canonical_indeed_url(a_tag) -> str:
    """Return a stable /viewjob?jk=... link instead of tracking URLs."""
    jk = a_tag.get_attribute("data-jk")
    if jk:
        return f"{BASE}/viewjob?jk={jk}"
    href = a_tag.get_attribute("href") or ""
    qs = parse_qs(urlparse(href).query)
    if "jk" in qs and qs["jk"]:
        return f"{BASE}/viewjob?jk={qs['jk'][0]}"
    return urljoin(BASE, href)

def canonical_indeed_url_bs4(a_tag) -> str:
    jk = a_tag.get("data-jk")
    if jk:
        return f"{BASE}/viewjob?jk={jk}"
    href = a_tag.get("href") or ""
    qs = parse_qs(urlparse(href).query)
    if "jk" in qs and qs["jk"]:
        return f"{BASE}/viewjob?jk={qs['jk'][0]}"
    return urljoin(BASE, href)

# (Removed: parse_current_page, not used)

def parse_current_page_bs4(html):
    """Parse all jobs from a page's HTML using BeautifulSoup."""
    jobs = []
    soup = BeautifulSoup(html, "html.parser")
    container = soup.select_one("#mosaic-provider-jobcards")
    if not container:
        logging.warning("No jobcards container found in HTML.")
        return jobs
    cards = container.select("[data-testid='slider_item']")
    for job_element in cards:
        # title and url
        title, url, jk = None, None, None
        a = job_element.select_one("h2.jobTitle a")
        if not a:
            a = job_element.find("a", attrs={"data-jk": True})
        if a:
            url = canonical_indeed_url_bs4(a)
            jk = a.get("data-jk")
            if not jk:
                qs = parse_qs(urlparse(url).query)
                jk = (qs.get("jk") or [None])[0]
            title = (a.get_text() or "").strip()
            if not title:
                label = (a.get("aria-label") or "").strip()
                if label.lower().startswith("full details of"):
                    label = label.split("full details of", 1)[1].strip()
                title = label or title
            if not title:
                span = job_element.select_one("h2.jobTitle [id^='jobTitle-'], h2.jobTitle span")
                if span:
                    title = span.get_text(strip=True) or None
        # company
        company = None
        company_tag = job_element.select_one("[data-testid='company-name']")
        if company_tag:
            company = company_tag.get_text(strip=True)
        # location
        location = None
        location_tag = job_element.select_one("[data-testid='text-location']")
        if location_tag:
            location = location_tag.get_text(strip=True)
        # tags
        tags = [li.get_text(strip=True) for li in job_element.select("ul.metadataContainer li") if li.get_text(strip=True)]
        # Indeed Apply
        easily_apply = bool(job_element.select_one("[data-testid='indeedApply']"))
        # description bullets
        description = []
        slider_container = job_element.find_parent("div", attrs={"data-testid": "slider_container"})
        if slider_container:
            ul_node = slider_container.select_one("[data-testid='slider_sub_item'] [data-testid='belowJobSnippet'] ul")
            if ul_node:
                description = [li.get_text(strip=True) for li in ul_node.select("li") if li.get_text(strip=True)]
        jobs.append({
            "jk": jk,
            "title": title,
            "url": url,
            "company": company,
            "location": location,
            "tags": tags,
            "easily_apply": easily_apply,
            "description": description,
        })
    return jobs

# ---------------- Crawl across pages ----------------
all_jobs = []
seen = set()  # de-dupe by jk or url

for i in range(PAGES):
    page_url = build_search_url(i)
    logging.info(f"Scraping page {i + 1} | Jobs collected so far: {len(all_jobs)}")
    # Always use Bright Data/BeautifulSoup method for all pages
    html = fetch_with_brightdata(page_url)
    if html:
        page_jobs = parse_current_page_bs4(html)
    else:
        page_jobs = []
    if len(page_jobs) == 0:
        logging.warning(f"No jobs found on page {i + 1} (URL: {page_url})")
    else:
        logging.info(f"Found {len(page_jobs)} jobs on page {i + 1}")
    for j in page_jobs:
        key = j.get("jk") or j.get("url")
        if key and key not in seen:
            seen.add(key)
            j["page"] = i + 1  # Add page info
            all_jobs.append(j)
    time.sleep(random.uniform(1.0, 2.0))

# ---------------- Save CSV ----------------
csv_file = "scraped_jobs.csv"
csv_headers = ["title", "url", "company", "location", "tags", "easily_apply", "description", "page"]

with open(csv_file, mode="w", newline="", encoding="utf-8") as file:
    writer = csv.DictWriter(file, fieldnames=csv_headers)
    writer.writeheader()
    for job in all_jobs:
        writer.writerow({
            "title": job["title"],
            "url": job["url"],
            "company": job["company"],
            "location": job["location"],
            "tags": ";".join(job["tags"]),
            "easily_apply": "Yes" if job["easily_apply"] else "No",
            "description": ";".join(job["description"]),
            "page": job.get("page", "")
        })

rich.print(f"Collected {len(all_jobs)} jobs across {PAGES} pages")
rich.print(all_jobs)
# (Removed: driver.quit(), not needed)
