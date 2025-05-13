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
    "Sociology": "SOCIOL",
    "Statistics": "STATS",
    "Program in Computing": "PIC",
    "Honors Collegium": "HNRS",
    "Ethnomusicology": "ETHNMUS",
    "English Composition": "ENGCOMP",
    "Education": "EDUC",
    "Architecture and Urban Design": "ARCH&UD",
    "Anthropology": "ANTHRO",
    "Classics": "CLASSIC",
    "Archaeology": "ARCHEOL",
    "Life Sciences": "LIFESCI",
    "Aerospace Studies": "AERO ST",
    "African American Studies": "AF AMER",
    "African Studies": "AFRC ST",
    "American Indian Studies": "AM IND",
    "American Sign Language": "ASL",
    "Ancient Near East": "AN N EA",
    "Semitics": "SEMITIC",
    "Anesthesiology": "ANES",
    "Applied Chemical Sciences": "APP CHM",
    "Applied Linguistics": "APPLING",
    "Arabic": "ARABIC",
    "English as a Second Language": "ESL",
    "Hebrew": "HEBREW",
    "Armenian": "ARMENIA",
    "Art": "ART",
    "Art History": "ART HIS",
    "Arts and Architecture": "ART&ARC",
    "Arts Education": "ARTS ED",
    "Asian": "ASIAN",
    "Asian American Studies": "ASIA AM",
    "Astronomy": "ASTR",
    "Atmospheric and Oceanic Sciences": "A&O SCI",
    "History": "HIST",
    "Chinese": "CHIN",
    "Japanese": "JAPAN",
    "Korean": "KOREA",
    "Religion": "RELIGN",
    "Filipino": "FILIPNO",
    "Earth, Planetary, and Space Sciences": "EPS SCI",
    "Bioengineering": "BIOENGR",
    "Biological Chemistry": "BIOL CH",
    "Biomathematics": "BIOMATH",
    "Biomedical Research": "BMD RES",
    "Biostatistics": "BIOSTAT",
    "Bulgarian": "BULGR",
    "Civil and Environmental Engineering": "C&EE",
    "Civil Engineering": "C&EE",
    "Mechanical and Aerospace Engineering": "MECH&AE",
    "Electrical and Computer Engineering": "EC ENGR",
    "Chemical Engineering": "CH ENGR",
    "Materials Science": "MAT SCI",
    "Computational and Systems Biology": "C&S BIO",
    "Physics and Biology in Medicine": "PBMED",
    "Molecular, Cell, and Developmental Biology": "MCD BIO",
    "Ecology and Evolutionary Biology": "EE BIOL",
    "Bioinformatics": "BIOINFO",
    "Epidemiology": "EPIDEM",
    "Central and East European Studies": "C&EE ST",
    "Chemistry and Biochemistry": "CHEM",
    "Chemistry": "CHEM",
    "Chicana/o and Central American Studies": "CCAS",
    "Communication": "COMM",
    "Community Health Sciences": "COM HLT",
    "Comparative Literature": "COM LIT",
    "Conservation of Cultural Heritage": "CLT HTG",
    "Czech": "CZCH",
    "Engineering": "ENGR",
    "Economics": "ECON",
    "Public Policy": "PUB PLC",
    "Urban Planning": "URBN PL",
    "Gender Studies": "GENDER",
    "Spanish": "SPAN",
    "Science Education": "SCI EDU",
    "Electrical Engineering": "EC ENGR",
    "GE Clusters": "CLUSTER",
    "Greek": "GREEK",
    "Latin": "LATIN",
    "Public Health": "PUB HLT",
    "Health Policy": "HLT POL",

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
    units_raw = h5_elements[1].inner_text().strip()
    units_match = re.search(r"\d+", units_raw)
    units = int(units_match.group()) if units_match else None
    course["course_code"] = course_code
    course["units"] = units

    title_element = page.query_selector("h2")
    title = title_element.inner_text().strip()
    course["title"] = title

    desc_block = page.query_selector("div.readmore-content-wrapper p")
    desc = desc_block.inner_text().strip() if desc_block else ""
    course["description"] = desc

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
        course["equivalent_courses"] = normalize_text(cleaned_text, course_code)
    
    multiple_block = page.query_selector("#Multiple-ListedCourses")
    if multiple_block:
        multiple_text = multiple_block.inner_text().strip()
        multiple_lines = multiple_text.splitlines()
        if multiple_lines and multiple_lines[0].lower().startswith("multiple-listed courses"):
            multiple_lines = multiple_lines[1:]
        cleaned_text = "\n".join(multiple_lines).strip()
        course["cross_listed"] = normalize_text(cleaned_text, course_code)

    return course

def normalize_text(text, course_code=None):
    fallback_subject = None

    if course_code:
        match = re.match(r"([A-Z& ]+)\s+[A-Z]{0,2}\d+[A-Z]?", course_code)
        if match:
            fallback_subject = match.group(1).strip()

    text = re.sub(r"\b[Cc]ourse\s+([A-Z]{0,2}\d+[A-Z]?)", lambda m: f"{fallback_subject} {m.group(1)}", text)

    matches = re.findall(r"([A-Z][A-Za-z,&' ]+)?\s+([A-Z]{0,2})?(\d+[A-Z]*)", text)
    normalized = []
    current_subject = fallback_subject

    for subject, prefix, number in matches:
        subject = subject.strip() if subject else current_subject

        if not subject or subject.lower() == "none":
            continue

        subject_key = subject.strip()
        if subject_key in SUBJECT_NORMALIZATION:
            subject = SUBJECT_NORMALIZATION[subject_key]

        current_subject = subject

        course_num = f"{prefix}{number}".strip()
        normalized.append(f"{subject} {course_num}")

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
            time.sleep(1)
        else:
            break

    print(f"Found {len(all_links)} course links for {dept_code}.")

    course_data = []
    for url in all_links:
        try:
            page.goto(url)
            time.sleep(1)
            details = extract_course_details(page)
            details["url"] = url
            course_data.append(details)
        except Exception as e:
            print(f"Failed to scrape {url}: {e}")

    return course_data

def main():
    departments = ["C&EE ST", "CH ENGR", "CHEM", "CCAS", "CHIN", "C&EE", "CLASSIC", "CLUSTER", "COMM", "CESC", "COM HLT", "COM LIT", "C&S BIO", "COM SCI", "CLT HTG", "CZCH" ] 

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
        print("\nAll departments scraped.")

if __name__ == "__main__":
    main()
