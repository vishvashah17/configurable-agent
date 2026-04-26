import csv
import json
import logging

# Set up logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class Customerinsightsagent:
    def __init__(self, csv_file_path: str, json_file_path: str):
        """
        Initialize the Customerinsightsagent class.

        Args:
        - csv_file_path (str): The path to the CSV file.
        - json_file_path (str): The path to the JSON file.
        """
        self.csv_file_path = csv_file_path
        self.json_file_path = json_file_path
        self.customer_data = []
        self.total_purchases = 0
        self.average_order_value = 0
        self.most_frequent_buyers = {}

    def read_csv_file(self) -> list:
        """
        Read the CSV file and extract customer data.

        Returns:
        - list: A list of dictionaries containing customer data.
        """
        try:
            with open(self.csv_file_path, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    self.customer_data.append(row)
            return self.customer_data
        except FileNotFoundError:
            logging.error(f"File {self.csv_file_path} not found.")
            return []
        except csv.Error as e:
            logging.error(f"Error reading CSV file: {e}")
            return []

    def extract_total_purchases(self) -> int:
        """
        Extract the total purchases from the customer data.

        Returns:
        - int: The total number of purchases.
        """
        try:
            self.total_purchases = sum(int(row['purchase_amount']) for row in self.customer_data)
            return self.total_purchases
        except KeyError:
            logging.error("Invalid CSV file format. 'purchase_amount' column not found.")
            return 0

    def extract_average_order_value(self) -> float:
        """
        Extract the average order value from the customer data.

        Returns:
        - float: The average order value.
        """
        try:
            if self.total_purchases == 0:
                return 0
            self.average_order_value = self.total_purchases / len(self.customer_data)
            return self.average_order_value
        except ZeroDivisionError:
            logging.error("Cannot calculate average order value. No customer data available.")
            return 0

    def extract_most_frequent_buyers(self) -> dict:
        """
        Extract the most frequent buyers from the customer data.

        Returns:
        - dict: A dictionary containing the most frequent buyers and their purchase counts.
        """
        try:
            for row in self.customer_data:
                buyer = row['buyer_name']
                if buyer in self.most_frequent_buyers:
                    self.most_frequent_buyers[buyer] += 1
                else:
                    self.most_frequent_buyers[buyer] = 1
            return self.most_frequent_buyers
        except KeyError:
            logging.error("Invalid CSV file format. 'buyer_name' column not found.")
            return {}

    def run(self) -> None:
        """
        Run the Customerinsightsagent class and execute all capability methods.
        """
        self.read_csv_file()
        self.extract_total_purchases()
        self.extract_average_order_value()
        self.extract_most_frequent_buyers()
        logging.info(f"Total purchases: {self.total_purchases}")
        logging.info(f"Average order value: {self.average_order_value}")
        logging.info(f"Most frequent buyers: {self.most_frequent_buyers}")
        with open(self.json_file_path, 'w') as f:
            json.dump({
                'total_purchases': self.total_purchases,
                'average_order_value': self.average_order_value,
                'most_frequent_buyers': self.most_frequent_buyers
            }, f)

if __name__ == '__main__':
    agent = Customerinsightsagent('customer_data.csv', 'customer_insights.json')
    agent.run()
