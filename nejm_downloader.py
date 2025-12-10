"""
NEJM Downloader - Unified class for downloading questions and images from NEJM challenges.
Requires: pip install cloudscraper beautifulsoup4
"""

import re
import os
import zipfile
import json
import cloudscraper
from bs4 import BeautifulSoup
from typing import Tuple, List, Optional, Dict, Any
from datetime import datetime


class NEJMDownloader:
    """
    Unified downloader for NEJM image challenges.
    Handles downloading and extracting both questions/options and images.
    """

    def __init__(self, challenge_id: str, output_dir: str = "."):
        """
        Initialize the NEJM downloader.

        Args:
            challenge_id: The challenge ID (e.g., "123456")
            output_dir: Base output directory for downloads
        """
        self.challenge_id = challenge_id
        self.output_dir = output_dir
        self.images_dir = os.path.join(output_dir, "images")
        self.pptx_path = os.path.join(output_dir, "nejm_image_challenge.pptx")
        self.date_str = datetime.now().strftime("%Y%m%d")

        # Data storage
        self.question: Optional[str] = None
        self.options: Dict[str, str] = {}
        self.image_path: Optional[str] = None

        # Create scraper to bypass Cloudflare
        self.scraper = cloudscraper.create_scraper()
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Referer": "https://www.nejm.org/",
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.9",
            "X-Requested-With": "XMLHttpRequest"
        }

    def _fetch_page_soup(self, url: str, timeout: int = 15) -> BeautifulSoup:
        """
        Fetch a page and return BeautifulSoup object.

        Args:
            url: URL to fetch
            timeout: Request timeout in seconds

        Returns:
            BeautifulSoup parsed page
        """
        resp = self.scraper.get(url, timeout=timeout)
        soup = BeautifulSoup(resp.text, "html.parser")

        # Remove script/style elements
        for s in soup(["script", "style", "noscript", "header", "footer", "nav", "svg"]):
            s.decompose()

        return soup

    def _fetch_visible_text(self, url: str, timeout: int = 15) -> str:
        """
        Fetch and extract visible text from a page.

        Args:
            url: URL to fetch
            timeout: Request timeout in seconds

        Returns:
            Visible text from the page
        """
        soup = self._fetch_page_soup(url, timeout)
        # Get the visible text
        text = soup.get_text(separator="\n")
        # Collapse repeated blank lines
        text = re.sub(r"\n\s*\n+", "\n\n", text).strip()
        return text

    def _extract_question_and_options_html(self, soup: BeautifulSoup) -> Tuple[Optional[str], Dict[str, str]]:
        """
        Extract question and options using HTML structure.

        Args:
            soup: BeautifulSoup object of the page

        Returns:
            Tuple of (question_text, options_dict)
        """
        # Find the main challenge content area
        challenge_content = soup.find('div', class_='image-challenge-qa_content')
        if not challenge_content:
            return None, {}

        right_area = challenge_content.find('div', class_='image-challenge-qa_right')
        if not right_area:
            return None, {}

        # Try to find question in dedicated 'image-challenge-qa_question' div (works for old & new)
        question_div = right_area.find('div', class_='image-challenge-qa_question')
        question_text = None

        if question_div:
            question_text = question_div.get_text().strip()
        else:
            # Fallback: look in second div (index 1) of right area
            divs = [d for d in right_area.find_all('div', recursive=False) if d.get('class')]
            if len(divs) >= 2:
                question_text = divs[1].get_text().strip()

        if not question_text or len(question_text) < 5:
            return None, {}

        # Find the answers container (has class 'image-challenge-qa_answers')
        answers_container = right_area.find('div', class_='image-challenge-qa_answers')
        if not answers_container:
            return None, {}

        # Extract options from radio button labels
        options = {}
        option_spans = answers_container.find_all('span', class_='radio--primary-label-text')

        option_keys = ['A', 'B', 'C', 'D', 'E', 'F']
        for idx, span in enumerate(option_spans):
            if idx >= len(option_keys):
                break
            option_text = span.get_text().strip()
            if option_text and len(option_text) > 5:
                if option_text not in options.values():  # Avoid duplicates
                    options[option_keys[idx]] = option_text

        return question_text, options

    def _extract_question_and_options_text(self, full_text: str) -> Tuple[Optional[str], Dict[str, str]]:
        """
        Extract question and options using text-based analysis.

        Args:
            full_text: Full visible text from the page

        Returns:
            Tuple of (question_text, options_dict)
        """
        normalized = full_text.replace('\r', '\n')

        # Split into paragraphs
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n+", normalized) if p.strip()]

        if not paragraphs:
            return None, {}

        # Find the clinical vignette (first substantial paragraph)
        question_text = None
        q_start_idx = 0

        clinical_keywords = ['patient', 'presented', 'symptoms', 'diagnosed', 'examination', 'year', 'old', 'woman', 'man', 'history']

        for i, para in enumerate(paragraphs):
            # Look for a paragraph with medical content and reasonable length (>50 chars)
            if len(para) > 50 and any(keyword.lower() in para.lower() for keyword in clinical_keywords):
                question_text = para
                q_start_idx = i
                break

        if not question_text:
            # Fallback: use first substantial paragraph
            for para in paragraphs:
                if len(para) > 50:
                    question_text = para
                    break

        if not question_text:
            return None, {}

        # Extract options from paragraphs after the question
        remaining_text = '\n\n'.join(paragraphs[q_start_idx + 1:])

        # Split into lines and look for repeated patterns
        lines = [line.strip() for line in remaining_text.splitlines() if line.strip()]

        # Track line frequency and order of first appearance
        line_counts = {}
        line_order = []

        for line in lines:
            # Skip noise lines
            if (line.endswith('%') or
                line.lower() in ['try again!', 'submit', 'back to image challenge', 'see how others chose', 'next challenge'] or
                len(line) < 5):
                continue

            # Skip explanation indicators (these come after options)
            if any(phrase in line.lower() for phrase in ['this is', 'this type', 'characterized by', 'is an', 'is a', 'can be', 'may be', 'results in']):
                break

            # Stop at navigation sections
            if any(word in line.lower() for word in ['more image challenges', 'total responses', 'see how others']):
                break

            if line not in line_counts:
                line_counts[line] = 0
                line_order.append(line)
            line_counts[line] += 1

        # Extract options: lines that appear 2+ times (answer options are typically repeated)
        options = {}
        option_keys = ['A', 'B', 'C', 'D', 'E', 'F']
        option_idx = 0

        for line in line_order:
            if option_idx >= len(option_keys):
                break
            count = line_counts.get(line, 0)
            # Include if appears 2+ times (answer option repeated)
            if count >= 2 and len(line) > 15:
                if not any(phrase in line.lower() for phrase in ['try again', 'that is not', 'correct answer']):
                    options[option_keys[option_idx]] = line
                    option_idx += 1

        return question_text, options

    def download_questions(self) -> Tuple[Optional[str], Dict[str, str]]:
        """
        Download and extract question and options from a challenge.

        Returns:
            Tuple of (question_text, options_dict)
        """
        url = f"https://www.nejm.org/image-challenge?ci={self.challenge_id}&startFrom=41&startPage=3"
        soup = self._fetch_page_soup(url)

        # Try HTML-based extraction first (more reliable)
        question, options = self._extract_question_and_options_html(soup)

        # Fall back to text-based extraction if HTML method fails
        if not question or not options:
            text = self._fetch_visible_text(url)
            question, options = self._extract_question_and_options_text(text)

        # Store in instance variables
        self.question = question
        self.options = options

        return question, options

    def download_images(self) -> None:
        """
        Download and extract images from a challenge.
        Saves PPTX file and extracts images to the images directory.
        Renames the second image to image_{challenge_id}.jpg
        """
        # Ensure output directory exists
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.images_dir, exist_ok=True)

        # Download PPTX
        pptx_url = f"https://csvc.nejm.org/ContentServer/images?id=IC{self.challenge_id}&format=pptx"
        pptx_response = self.scraper.get(pptx_url, headers=self.headers)
        pptx_response.raise_for_status()

        # Write PPTX to file
        with open(self.pptx_path, 'wb') as f:
            f.write(pptx_response.content)

        # Extract images from PPTX
        extracted_files = []
        with zipfile.ZipFile(self.pptx_path, "r") as z:
            for file in z.namelist():
                if file.startswith("ppt/media/"):
                    img_data = z.read(file)
                    img_name = os.path.basename(file)
                    img_path = os.path.join(self.images_dir, img_name)
                    with open(img_path, "wb") as img_file:
                        img_file.write(img_data)
                    extracted_files.append((img_name, img_path))

        # Rename second image to nejm_{challenge_id}.jpg
        if len(extracted_files) >= 2:
            second_img_name, second_img_path = extracted_files[1]
            new_img_name = f"nejm_{self.challenge_id}.jpg"
            new_img_path = os.path.join(self.images_dir, new_img_name)
            os.rename(second_img_path, new_img_path)
            # Store relative path
            self.image_path = os.path.join("images", new_img_name)

    def get_json(self) -> Dict[str, Any]:
        """
        Get downloaded data as a JSON-serializable dictionary.

        Returns:
            Dictionary containing id, question, options, and image
        """
        return {
            "id": self.challenge_id,
            "question": self.question,
            "options": self.options,
            "image": self.image_path
        }

    def download_question(self) -> Dict[str, Any]:
        """
        Download both questions and images.

        Returns:
            Dictionary with JSON output
        """

        # Download questions
        self.download_questions()

        # Download images
        self.download_images()

        return self.get_json()


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python nejm_downloader.py <challenge_id> [output_dir]")
        sys.exit(1)

    challenge_id = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "."

    downloader = NEJMDownloader(challenge_id, output_dir)

    # Download everything
    result = downloader.download_question()

    # Print JSON output
    print("\n" + "=" * 60)
    print("JSON Output:")
    print("=" * 60)
    print(json.dumps(result, indent=2))
