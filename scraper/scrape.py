from playwright.sync_api import sync_playwright
import json
import re
import time
import os

BASE_URL = "https://catalog.registrar.ucla.edu"

SUBJECT_NORMALIZATION = {
    "Mathematics": "MATH",
    "Computer Science": "COM SCI",
    "Philosophy": "PHIL",
    "Linguistics": "LING",
    "Chemistry": "CHEM",
    "Physics": "PHYSICS",
    "Psychology": "PSYCH",
    "Political Science": "POL SCI",
    "Sociology": "SOC",
    "Statistics": "STATS",
    "Program in Computing": "PIC",
}

def extract_course_links(page):
    links = []
    course_cards = page.query_selector_all("a[href^='/course/']")
    for card in course_cards:
        href = card.get_attribute("href")
        if href:
            links.append(BASE_URL + href)
    return links

def extract_course_details(page):
    course = {}

    h5_elements = page.query_selector_all("h5")
    course_code = h5_elements[0].inner_text().strip()
    units = h5_elements[1].inner_text().strip()
    course["course_code"] = course_code
    course["units"] = re.sub(r"[^\d]", "", units)

    title_element = page.query_selector("h2")
    title = title_element.inner_text().strip()
    course["title"] = title

    desc_block = page.query_selector("div.readmore-content-wrapper p")
    desc = desc_block.inner_text().strip() if desc_block else ""

    requirement_elements = page.query_selector('[id="UniversityandCollege/SchoolRequirements"]')
    if requirement_elements:
        req_text = requirement_elements.inner_text().strip()
        req_lines = req_text.splitlines()

        for i, line in enumerate(req_lines):
            if "this course satisfies the following requirements:" in line.lower():
                req_lines = req_lines[i+1:] 
                break

        requirements = [
            line.replace("\u2014", "-").strip()
            for line in req_lines
            if line.strip()
        ]
        
        if requirements:
            course["satisfies"] = requirements

    prereq = re.search(r"(Enforced )?requisite[s]?: (.+?)(\.|;|$)", desc, re.IGNORECASE)
    if prereq:
        prereq_text = prereq.group(2).strip()
        course["prerequisites"] = normalize_text(prereq_text, course_code)

    coreq = re.search(r"(Enforced )?corequisite[s]?: (.+?)(\.|;|$)", desc, re.IGNORECASE)
    if coreq:
        coreq_text = coreq.group(2).strip()
        course["corequisites"] = normalize_text(coreq_text, course_code)
    
    credit_excl_block = page.query_selector("#CreditExclusions")
    if credit_excl_block:
        credit_text = credit_excl_block.inner_text().strip()
        credit_lines = credit_text.splitlines()
        if credit_lines and credit_lines[0].lower().startswith("credit exclusions"):
            credit_lines = credit_lines[1:]
        cleaned_text = "\n".join(credit_lines).strip()
        course["credit_exclusions"] = normalize_text(cleaned_text, course_code)

    equivalent_block = page.query_selector("#EquivalentCourses")
    if equivalent_block:
        equivalent_text = equivalent_block.inner_text().strip()
        equivalent_lines = equivalent_text.splitlines()
        if equivalent_lines and equivalent_lines[0].lower().startswith("equivalent courses"):
            equivalent_lines = equivalent_lines[1:]
        cleaned_text = "\n".join(equivalent_lines).strip()
        print(f"📘 Equivalent courses raw: {cleaned_text}")
        course["equivalent_courses"] = normalize_text(cleaned_text, course_code)

    return course

def normalize_text(text, course_code=None):
    fallback_subject = None

    if course_code:
        match = re.match(r"([A-Z ]+)\s+\d+", course_code)
        if match:
            fallback_subject = match.group(1).strip()

    matches = re.findall(r"([A-Z][A-Z ]+)?\s?(\d+[A-Z]?)", text)
    normalized = []

    for subject, number in matches:
        subject = subject.strip() if subject else fallback_subject
        if subject in SUBJECT_NORMALIZATION:
            subject = SUBJECT_NORMALIZATION[subject]
        normalized.append(f"{subject} {number}")

    return normalized

def scrape_department_courses(page, dept_code):
    print(f"\n=== Scraping department: {dept_code} ===")
    clean_dept_code = re.sub(r"[^\w]", "", dept_code)
    start_url = f"{BASE_URL}/browse/Subject%20Areas/{clean_dept_code}"
    page.goto(start_url)
    time.sleep(2)

    all_links = []

    while True:
        links = extract_course_links(page)
        all_links.extend(links)

        next_button = page.query_selector("button[aria-label='Go forward 1 page in results']")
        if next_button and not next_button.is_disabled():
            next_button.click()
            time.sleep(1.5)
        else:
            break

    print(f"Found {len(all_links)} course links for {dept_code}.")

    course_data = []
    for url in all_links:
        try:
            page.goto(url)
            time.sleep(1.5)
            details = extract_course_details(page)
            details["url"] = url
            course_data.append(details)
        except Exception as e:
            print(f"Failed to scrape {url}: {e}")

    return course_data

def main():
    departments = ["ARCH&UD", "ARMENIA", "ART", ] 

    os.makedirs("data", exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        for dept in departments:
            data = scrape_department_courses(page, dept)
            filename = f"data/{dept.lower().replace(' ', '')}.json"
            with open(filename, "w") as f:
                json.dump(data, f, indent=2)
            print(f"Saved {len(data)} courses to {filename}")

        browser.close()
        print("\n✅ All departments scraped.")

if __name__ == "__main__":
    main()
