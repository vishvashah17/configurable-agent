import PyPDF2
import json
import logging
from typing import List

# Module-level constants/variables
LOG_FILE = 'agent.log'
PDF_FILE = 'example.pdf'
JSON_FILE = 'summary.json'

class PDFSummarizer:
    def __init__(self, pdf_file: str, json_file: str):
        """
        Initialize the PDF Summarizer agent.

        Args:
        - pdf_file (str): The path to the PDF file to summarize.
        - json_file (str): The path to the JSON file to store the summary.
        """
        self.pdf_file = pdf_file
        self.json_file = json_file
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        self.handler = logging.FileHandler(LOG_FILE)
        self.handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        self.logger.addHandler(self.handler)

    def extract_text(self) -> str:
        """
        Extract text from the PDF file.

        Returns:
        - str: The extracted text.
        """
        try:
            pdf_reader = PyPDF2.PdfReader(self.pdf_file)
            text = ''
            for page in pdf_reader.pages:
                text += page.extract_text()
            return text
        except Exception as e:
            self.logger.error(f'Error extracting text: {e}')
            return ''

    def natural_language_processing(self, text: str) -> List[str]:
        """
        Perform natural language processing on the extracted text.

        Args:
        - text (str): The extracted text.

        Returns:
        - List[str]: A list of sentences.
        """
        try:
            sentences = text.split('. ')
            return sentences
        except Exception as e:
            self.logger.error(f'Error performing NLP: {e}')
            return []

    def information_extraction(self, sentences: List[str]) -> List[str]:
        """
        Extract relevant information from the sentences.

        Args:
        - sentences (List[str]): A list of sentences.

        Returns:
        - List[str]: A list of extracted information.
        """
        try:
            extracted_info = []
            for sentence in sentences:
                if sentence:
                    extracted_info.append(sentence)
            return extracted_info
        except Exception as e:
            self.logger.error(f'Error extracting information: {e}')
            return []

    def run(self) -> None:
        """
        Run the PDF Summarizer agent.
        """
        text = self.extract_text()
        sentences = self.natural_language_processing(text)
        extracted_info = self.information_extraction(sentences)
        with open(self.json_file, 'w') as f:
            json.dump(extracted_info, f)
        self.logger.info('Summary saved to JSON file')

if __name__ == '__main__':
    agent = PDFSummarizer(PDF_FILE, JSON_FILE)
    agent.run()
