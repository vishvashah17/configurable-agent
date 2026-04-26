# CustomerInsightsAgent
The CustomerInsightsAgent is a Python-based agent designed to extract valuable customer insights from CSV files, providing key metrics such as total purchases, average order value, and most frequent buyers. The agent utilizes a JSON file as its database for storing and retrieving insights.

## Features
* Read CSV files containing customer purchase data
* Extract total purchases from the CSV files
* Extract average order value from the CSV files
* Extract most frequent buyers from the CSV files
* Store and retrieve insights from a JSON file database

## Prerequisites
To run the CustomerInsightsAgent, you will need to have the following installed:
* Python 3.8 or later
* A compatible operating system (Windows, macOS, or Linux)

## Installation
To install the CustomerInsightsAgent, follow these steps:
1. Clone the CustomerInsightsAgent repository to your local machine using `git clone`.
2. Navigate to the cloned repository using `cd CustomerInsightsAgent`.
3. Create a virtual environment using `python -m venv venv` (optional but recommended).
4. Activate the virtual environment using `source venv/bin/activate` (on Linux/macOS) or `venv\Scripts\activate` (on Windows).
5. Install the required dependencies using `pip install -r requirements.txt` (if available) or `pip install pandas` (as the agent uses pandas for CSV processing).

## How to Run
To run the CustomerInsightsAgent, follow these exact steps:
1. **Create a virtual environment**: Open a terminal and navigate to the CustomerInsightsAgent repository. Run `python -m venv venv` to create a new virtual environment.
2. **Activate the virtual environment**: Run `source venv/bin/activate` (on Linux/macOS) or `venv\Scripts\activate` (on Windows) to activate the virtual environment.
3. **Install dependencies**: Run `pip install pandas` to install the required pandas library.
4. **Set environment variables**: No environment variables need to be set for this agent.
5. **Run the agent**: Run `python main.py` to start the CustomerInsightsAgent.
6. **Verify success**: The agent will read the CSV files, extract insights, and store them in the JSON file database. You can verify the success by checking the JSON file for the extracted insights. The output will look similar to:
{
    "total_purchases": 100,
    "average_order_value": 50.0,
    "most_frequent_buyers": ["John Doe", "Jane Doe"]
}
7. **Stop the service/process**: To stop the CustomerInsightsAgent, simply press `Ctrl+C` in the terminal where the agent is running.

Note: Make sure to replace `main.py` with the actual entry point of your agent if it's different. Also, ensure that the CSV files are in the correct location and format for the agent to process them correctly.
