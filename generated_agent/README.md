# PDF Summarizer
The PDF Summarizer is a Python-based agent designed to summarize PDF documents into concise bullet points, leveraging text extraction, natural language processing, and information extraction capabilities.

## Features
* Text extraction from PDF documents
* Natural Language Processing (NLP) for summarization
* Information Extraction to identify key points
* Storage of summarized data in a json file

## Prerequisites
To run the PDF Summarizer, you will need to have the following installed:
* Python 3.8 or higher
* Required libraries (listed in requirements.txt)

## Installation
To set up the PDF Summarizer, follow these steps:
git clone https://github.com/your-repo/pdf-summarizer.git
cd pdf-summarizer
pip install -r requirements.txt

## Running the PDF Summarizer
To run the PDF Summarizer, navigate to the project directory and execute the following command:
python pdf_summarizer.py -f path/to/input.pdf
Replace `path/to/input.pdf` with the path to the PDF file you want to summarize.

## Capabilities
The PDF Summarizer has the following capabilities:
* **Text Extraction**: Extracts text from PDF documents
* **Natural Language Processing**: Applies NLP techniques to summarize the extracted text
* **Information Extraction**: Identifies key points and phrases in the text

## Example Usage
To summarize a PDF document, run the following command:
python pdf_summarizer.py -f example.pdf
This will generate a json file containing the summarized text in bullet points. You can then view the summarized text by opening the json file.

Note: Make sure to replace `example.pdf` with the path to your actual PDF file. The summarized data will be stored in a json file named `summary.json` in the same directory as the input PDF file.
