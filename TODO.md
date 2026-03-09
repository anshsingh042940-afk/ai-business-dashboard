# AI Dashboard - CSV Upload Fix

## Problem
The system was only supporting uploading CSV files with the exact same structure as `insurance_claims.csv`. When users tried to upload different CSV files, it failed because:
1. The database table schema was hardcoded for insurance claims
2. SQL queries were hardcoded to work only with insurance-specific columns

## Solution Implemented
Made the system support ANY CSV upload by:

1. **Backend (backend/main.py)**:
   - Made `load_csv_to_db` function dynamically create tables based on CSV columns
   - Added `get_table_info` function to retrieve current table columns
   - Added `/table-info` endpoint to expose table structure
   - Added `generate_dynamic_sql` function to generate SQL queries based on uploaded CSV columns
   - Updated `/query` endpoint to use dynamic SQL generation

2. **Frontend (frontend/src/App.js)**:
   - Added `useEffect` to fetch table columns on app mount
   - Added `tableColumns` state to store current columns
   - Updated `handleFileUpload` to fetch columns after successful upload
   - Added dynamic `getSuggestedQueries` function to generate relevant query suggestions based on table columns

## How It Works Now
1. User uploads any CSV file
2. Backend dynamically creates a database table with columns from the CSV
3. Frontend fetches the updated column information
4. Query suggestions are dynamically generated based on the available columns
5. SQL queries are dynamically generated to work with any column structure

## Testing
To test:
1. Start the backend server: `cd backend && uvicorn main:app --reload --port 8001`
2. Start the frontend: `cd frontend && npm start`
3. Upload any CSV file (not just insurance data)
4. Try queries like "Show by year", "Show total by name", etc.

