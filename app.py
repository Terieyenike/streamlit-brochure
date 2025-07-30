import streamlit as st
import os
import requests
import json
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from openai import OpenAI

# Initialize and constants

load_dotenv(override=True)
api_key = os.getenv('OPENAI_API_KEY')

# Validate API key
if not api_key or not api_key.startswith('sk-proj-'):
    st.error("Invalid or missing OpenAI API key. Please check your environment settings.")
else:
    openai = OpenAI(api_key=api_key)

MODEL = 'gpt-4o-mini'

# User-Agent headers to mimic a real browser
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36"
}

class Website:
    def __init__(self, url):
        self.url = url
        try:
            response = requests.get(url, headers=HEADERS, timeout=10)
            response.raise_for_status()
        except requests.RequestException as e:
            st.error(f"Error fetching the website: {e}")
            return

        soup = BeautifulSoup(response.content, 'html.parser')
        self.title = soup.title.string if soup.title else "No title found"

        if soup.body:
            for tag in soup.body(["script", "style", "img", "input"]):
                tag.decompose()
            self.text = soup.body.get_text(separator="\n", strip=True)

        self.links = [
            link.get('href') for link in soup.find_all('a', href=True)
        ]

    def get_contents(self):
        return f"Webpage Title:\n{self.title}\n\nWebpage Contents:\n{self.text}\n"

link_system_prompt = "You are provided with a list of links found on a webpage. \
You are able to decide which of the links would be most relevant to include in a brochure about the company, \
such as links to an About page, or a Company page, or Careers/Jobs pages.\n"
link_system_prompt += "You should respond in JSON as in this example:"
link_system_prompt += """
{
    "links": [
        {"type": "about page", "url": "https://full.url/goes/here/about"},
        {"type": "careers page", "url": "https://another.full.url/careers"}
    ]
}
"""

def get_links_user_prompt(website):
    return (
        f"Here is the list of links on the website of {website.url} - "
        "please decide which of these are relevant web links for a brochure about the company, "
        "respond with the full https URL in JSON format. "
        "Do not include Terms of Service, Privacy, email links.\n"
        "Links (some might be relative links):\n" +
        "\n".join(website.links)
    )

def get_links(url):
    website = Website(url)
    response = openai.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": link_system_prompt},
            {"role": "user", "content": get_links_user_prompt(website)}
      ],
        response_format={"type": "json_object"}
    )
    result = response.choices[0].message.content
    if result is None:
        raise ValueError("OpenAI response content is None")
    return json.loads(result)

# make the brochure
def get_brochure_user_prompt(company_name, url):
    content = f"Landing page:\n{Website(url).get_contents()}\n"
    for link in get_links(url).get("links", []):
        page = Website(link["url"]).get_contents()
        content += f"\n\n{link['type']}\n{page}"
    return (
        f"You have to create a brochure for the company: {company_name}.\n"
        f"Use the following content from the website to create a short company brochure in markdown:\n\n{content[:5000]}"
    )

def create_brochure(company_name, url):
    system_prompt = "You are an assistant that analyzes the contents of several relevant pages from a company website \
        and creates a short brochure about the company for prospective customers, investors and recruits. Respond in markdown.\
            Include details of company culture, customers and careers/jobs only if you have the information. otherwise leave it out."
    response = openai.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": get_brochure_user_prompt(company_name, url)}
          ],
    )
    result = response.choices[0].message.content
    st.markdown(result)

def main():
    st.title("Brochure Generator")

    company_name = st.text_input("Name of company", placeholder="AWS")
    site_url = st.text_input("Enter website URL", placeholder="https://example.com")

    if site_url.strip() and company_name.strip():
        with st.spinner("Processing website..."):
            try:
                create_brochure(company_name, site_url)
            except Exception as e:
                st.error(f"Failed to extract relevant links: {e}")


if __name__ == "__main__":
    main()
