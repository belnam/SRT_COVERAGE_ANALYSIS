SRT-Coverage-Analysis

SRT-Coverage-Analysis is an API-based application designed to upload SRT data, process it, and categorize the data based on the following classifications:

AAP (Amazon Asset Program)

Bought

Leased

Non-Amazon

Additionally, the application further verifies bought assets to check if they are in interoperable accounts checking against, and those that are not covered are set aside.

Features

Upload and process SRT files.

Categorization into AAP, Bought, Leased, and Non-Amazon.

Verification of bought assets for interoperability.

WebSocket support for real-time updates.

Weekly reports and data archiving.

REST API endpoints for data retrieval and downloading reports.

Technologies Used

FastAPI (for API development)

Pandas (for data processing)

GraphQL (for Amazon-related queries)

WebSockets (for real-time updates)

AsyncIO (for handling async tasks)

Multiprocessing (for parallel data processing)

Tenacity (for API retry mechanisms)

Installation

Prerequisites

Ensure you have Python 3.8+ installed.

Clone the repository:

git clone https://github.com/your-repo/srt-coverage-analysis.git
cd srt-coverage-analysis

Create a virtual environment (optional but recommended):

python -m venv venv
source venv/bin/activate  # On Windows use `venv\Scripts\activate`

Install dependencies:

pip install -r requirements.txt

Create a .env file and set up the required environment variables:

INNOVATIVE_USERNAME=your_username
INNOVATIVE_PASSWORD=your_password

Running the Application

Start the FastAPI server:

uvicorn main:app --host 0.0.0.0 --port 8000 --reload

API Endpoints

1. Upload SRT File

Endpoint: POST /upload/

Uploads and processes an SRT file.

2. List Available Reports

Endpoint: GET /list-reports/

Returns a list of available reports.

3. Download Report

Endpoint: GET /download/{report_type}

Available types: InAAP_Bought, NotInAAP, InAAP_Leased, LPs_to_be_added_to_account

4. Weekly Statistics Graph

Endpoint: GET /weekly-stats-graph/

Returns weekly data categorized by AAP, Bought, and Leased assets.

5. WebSocket for Real-time Updates

Endpoint: ws://localhost:8000/ws/weekly-stats/

Provides real-time updates on weekly stats.

Contributing

Feel free to fork this repository and contribute by submitting a pull request.



