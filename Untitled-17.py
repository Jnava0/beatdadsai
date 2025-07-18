# File: backend/tools/web_scraper_tool.py
# Author: Gemini
# Date: July 17, 2025
# Description: A tool that allows an agent to scrape text content from a webpage.

import requests
from bs4 import BeautifulSoup
import logging
from typing import Any

# Import the base class
from tools.base_tool import Tool

logger = logging.getLogger(__name__)

class WebScraperTool(Tool):
    """
    A tool for scraping the textual content of a given URL.
    """
    
    @property
    def name(self) -> str:
        return "web_scraper"

    @property
    def description(self) -> str:
        return (
            "Fetches the content of a URL and returns its main text. "
            "Use this to get information from websites, read articles, or access documentation. "
            "Input must be a single valid URL. For example: {'url': 'https://example.com'}"
        )

    def execute(self, url: str) -> str:
        """
        Executes the web scraping process.

        Args:
            url (str): The full URL of the webpage to scrape.

        Returns:
            str: The extracted and cleaned text content of the page, or an error message.
        """
        if not url:
            return "Error: URL cannot be empty."
        
        logger.info(f"Executing web_scraper tool for URL: {url}")
        
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)

            # Use BeautifulSoup to parse the HTML content
            soup = BeautifulSoup(response.text, 'html.parser')

            # Remove script and style elements
            for script_or_style in soup(['script', 'style']):
                script_or_style.decompose()

            # Get text and clean it up
            text = soup.get_text()
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            cleaned_text = '\n'.join(chunk for chunk in chunks if chunk)

            # Limit the output size to prevent overwhelming the LLM context
            max_length = 8000 # Roughly 2000 tokens
            if len(cleaned_text) > max_length:
                cleaned_text = cleaned_text[:max_length] + "\n\n[Content truncated]"

            logger.info(f"Successfully scraped content from {url}.")
            return cleaned_text if cleaned_text else "No text content found on the page."

        except requests.exceptions.RequestException as e:
            error_message = f"Error during web request: {e}"
            logger.error(error_message)
            return error_message
        except Exception as e:
            error_message = f"An unexpected error occurred during scraping: {e}"
            logger.error(error_message, exc_info=True)
            return error_message

# --- Example Usage ---
if __name__ == '__main__':
    from logging_config import setup_logging
    setup_logging()

    scraper = WebScraperTool()
    print(f"Tool Name: {scraper.name}")
    print(f"Tool Description: {scraper.description}")
    
    # Test with a live URL
    test_url = "https://en.wikipedia.org/wiki/Artificial_intelligence"
    print(f"\n--- Scraping {test_url} ---")
    content = scraper.execute(url=test_url)
    print(content[:500] + "...") # Print first 500 characters