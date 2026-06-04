import logging
import requests
from bs4 import BeautifulSoup
import csv
import json

# Module-level constants/variables
LOG_FILE = 'autoagent.log'
CSV_FILE = 'product_details.csv'
JSON_FILE = 'product_details.json'

class Autoagent:
    def __init__(self, url: str, csv_file: str = CSV_FILE, json_file: str = JSON_FILE):
        """
        Initialize the Autoagent instance.

        Args:
        - url (str): The URL of the online store to scrape.
        - csv_file (str): The file path to save the scraped product details in CSV format. Defaults to 'product_details.csv'.
        - json_file (str): The file path to save the scraped product details in JSON format. Defaults to 'product_details.json'.
        """
        self.url = url
        self.csv_file = csv_file
        self.json_file = json_file
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        handler = logging.FileHandler(LOG_FILE)
        handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        self.logger.addHandler(handler)

    def web_scraping(self) -> None:
        """
        Extract product details from the online store using web scraping.

        Returns:
        - None
        """
        try:
            resp = requests.get(self.url)
            soup = BeautifulSoup(resp.content, 'html.parser')
            product_details = []
            for product in soup.find_all('div', class_='product'):
                name = product.find('h2', class_='product-name').text.strip()
                price = product.find('span', class_='product-price').text.strip()
                product_details.append({'name': name, 'price': price})
            self.logger.info('Scraped product details: %s', product_details)
            self.save_to_csv(product_details)
            self.save_to_json(product_details)
        except requests.exceptions.RequestException as e:
            self.logger.error('Error scraping product details: %s', e)
        except Exception as e:
            self.logger.error('Error processing product details: %s', e)

    def save_to_csv(self, product_details: list) -> None:
        """
        Save the scraped product details to a CSV file.

        Args:
        - product_details (list): A list of dictionaries containing the product details.

        Returns:
        - None
        """
        try:
            with open(self.csv_file, 'w', newline='') as csvfile:
                fieldnames = ['name', 'price']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                for product in product_details:
                    writer.writerow(product)
            self.logger.info('Saved product details to CSV file: %s', self.csv_file)
        except Exception as e:
            self.logger.error('Error saving product details to CSV file: %s', e)

    def save_to_json(self, product_details: list) -> None:
        """
        Save the scraped product details to a JSON file.

        Args:
        - product_details (list): A list of dictionaries containing the product details.

        Returns:
        - None
        """
        try:
            with open(self.json_file, 'w') as jsonfile:
                json.dump(product_details, jsonfile, indent=4)
            self.logger.info('Saved product details to JSON file: %s', self.json_file)
        except Exception as e:
            self.logger.error('Error saving product details to JSON file: %s', e)

    def run(self) -> None:
        """
        Run the Autoagent instance.

        Returns:
        - None
        """
        self.web_scraping()

if __name__ == '__main__':
    url = 'https://example.com/products'
    agent = Autoagent(url)
    agent.run()
