# AutoAgent
The AutoAgent is a Python-based web scraping agent that extracts product details from an online store and saves the results to a CSV file. It utilizes a JSON file as its database to store configuration and other relevant data.

## Features
* Web scraping capabilities to extract product details from online stores
* Saves extracted data to a CSV file for further analysis
* Utilizes a JSON file as its database for configuration and data storage

## Prerequisites
* Python 3.8 or higher
* `requests` and `beautifulsoup4` libraries for web scraping
* `csv` library for saving data to a CSV file
* `json` library for interacting with the JSON database

## Installation
To install the AutoAgent, follow these steps:
1. Clone the repository to your local machine using `git clone https://github.com/your-repo/autagent.git`
2. Navigate to the project directory using `cd autagent`
3. Create a virtual environment using `python -m venv venv` (optional but recommended)
4. Activate the virtual environment using `source venv/bin/activate` (on Linux/Mac) or `venv\Scripts\activate` (on Windows)
5. Install the required libraries using `pip install requests beautifulsoup4`

## How to Run
To run the AutoAgent, follow these exact steps:
1. **Create a virtual environment**: If you haven't already, create a virtual environment using `python -m venv venv`
2. **Activate the virtual environment**: Activate the virtual environment using `source venv/bin/activate` (on Linux/Mac) or `venv\Scripts\activate` (on Windows)
3. **Install dependencies**: Install the required libraries using `pip install requests beautifulsoup4`
4. **Set environment variables**: Set the `OUTPUT_FILE` environment variable to specify the output CSV file name, e.g., `export OUTPUT_FILE="product_details.csv"` (on Linux/Mac) or `set OUTPUT_FILE="product_details.csv"` (on Windows)
5. **Run the agent**: Run the AutoAgent using `python main.py`
6. **Verify success**: The agent will extract product details from the online store and save the results to the specified CSV file. You can verify the success by checking the output CSV file for the extracted data.
7. **Stop the service/process**: To stop the AutoAgent, simply press `Ctrl+C` in the terminal where the agent is running.

Example output:
Extracting product details from online store...
Saving data to product_details.csv...
Extraction complete.
Note: Make sure to replace `your-repo` with the actual repository URL and adjust the `OUTPUT_FILE` environment variable as needed.
