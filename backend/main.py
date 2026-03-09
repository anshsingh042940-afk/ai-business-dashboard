from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pandas as pd
import sqlite3
import os
import re
import json
import google.genai as genai
from typing import List

# Configure Google Gemini API
GEMINI_API_KEY = "AIzaSyDF31T7RD3A3Fa0hAIOBD-dc7XSCdStQW4"
gemini_client = None
if GEMINI_API_KEY:
    gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    print(f"Google Gemini API configured successfully")

app = FastAPI()

# Configure CORS
origins = ["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:3001", "http://127.0.0.1:3001", "http://localhost:3002", "http://localhost:3003"]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database.db')
conversation_history: List[dict] = []
script_dir = os.path.dirname(os.path.abspath(__file__))
csv_path = os.path.join(script_dir, '..', 'data', 'data', 'insurance_claims.csv')

def init_db():
    """Initialize database with the default insurance claims CSV"""
    # Use the dynamic load function to ensure consistent table structure
    load_csv_to_db(csv_path, "insurance_claims")
    print("Database initialized successfully")

def load_csv_to_db(csv_file_path: str, table_name: str = "insurance_claims"):
    """Load CSV into database - creates table dynamically based on CSV columns"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Read CSV to get columns
    df = pd.read_csv(csv_file_path)
    columns = df.columns.tolist()
    
    # Sanitize column names for SQL
    column_definitions = []
    for col in columns:
        # Replace spaces and special chars with underscores
        safe_col = re.sub(r'[^a-zA-Z0-9_]', '_', col.lower())
        # Ensure column name starts with letter
        if not safe_col[0].isalpha():
            safe_col = 'col_' + safe_col
        column_definitions.append(f'"{col}" TEXT')
    
    # Drop existing table and create new one with dynamic columns
    cursor.execute(f'DROP TABLE IF EXISTS {table_name}')
    
    create_table_sql = f'CREATE TABLE {table_name} (id INTEGER PRIMARY KEY AUTOINCREMENT, {", ".join(column_definitions)})'
    cursor.execute(create_table_sql)
    
    # Insert data
    placeholders = ', '.join(['?'] * len(columns))
    insert_sql = f'INSERT INTO {table_name} ({", ".join(columns)}) VALUES ({placeholders})'
    
    for _, row in df.iterrows():
        values = [None if pd.isna(val) else val for val in row]
        cursor.execute(insert_sql, values)
    
    conn.commit()
    
    # Store table info for dynamic queries
    with open(os.path.join(script_dir, 'table_info.json'), 'w') as f:
        json.dump({'table_name': table_name, 'columns': columns}, f)
    
    conn.close()
    print(f"Loaded CSV from {csv_file_path} into table {table_name} with {len(columns)} columns")

def generate_sql_with_pattern_matching(question: str) -> str:
    """Generate SQL using pattern matching - works without API key"""
    question_lower = question.lower()
    
    # Define query patterns
    patterns = [
        # Claims paid by company
        (r'claims\s+paid\s+by\s+company|claims\s+paid\s+by\s+(life\s+)?insurer', 
         "SELECT life_insurer, SUM(claims_paid_no) as total_claims_paid FROM insurance_claims WHERE life_insurer NOT IN ('Industry', 'Industry Total', 'PVT.', 'Private Total', '') AND life_insurer IS NOT NULL GROUP BY life_insurer ORDER BY total_claims_paid DESC LIMIT 15"),
        
        # Claims paid by year
        (r'claims\s+paid\s+by\s+year', 
         "SELECT year, SUM(claims_paid_no) as total_claims_paid FROM insurance_claims WHERE year IS NOT NULL AND year != '' GROUP BY year ORDER BY year"),
        
        # Total claims intimated by insurer
        (r'total\s+claims\s+intimated\s+by\s+insurer|claims\s+intimated\s+by\s+(life\s+)?insurer', 
         "SELECT life_insurer, SUM(claims_intimated_no) as total_intimated FROM insurance_claims WHERE life_insurer NOT IN ('Industry', 'Industry Total', 'PVT.', 'Private Total', '') AND life_insurer IS NOT NULL GROUP BY life_insurer ORDER BY total_intimated DESC LIMIT 15"),
        
        # Claims intimated by year
        (r'claims\s+intimated\s+by\s+year', 
         "SELECT year, SUM(claims_intimated_no) as total_intimated FROM insurance_claims WHERE year IS NOT NULL AND year != '' GROUP BY year ORDER BY year"),
        
        # Average claims paid ratio by year
        (r'average\s+claims\s+paid\s+ratio\s+by\s+year|claims\s+paid\s+ratio\s+by\s+year', 
         "SELECT year, AVG(claims_paid_ratio_no) as avg_paid_ratio FROM insurance_claims WHERE year IS NOT NULL AND year != '' GROUP BY year ORDER BY year"),
        
        # Claims repudiated by company
        (r'claims\s+repudiated\s+by\s+company|claims\s+repudiated\s+by\s+(life\s+)?insurer', 
         "SELECT life_insurer, SUM(claims_repudiated_no) as total_repudiated FROM insurance_claims WHERE life_insurer NOT IN ('Industry', 'Industry Total', 'PVT.', 'Private Total', '') AND life_insurer IS NOT NULL GROUP BY life_insurer ORDER BY total_repudiated DESC LIMIT 15"),
        
        # Claims repudiated by year
        (r'claims\s+repudiated\s+by\s+year', 
         "SELECT year, SUM(claims_repudiated_no) as total_repudiated FROM insurance_claims WHERE year IS NOT NULL AND year != '' GROUP BY year ORDER BY year"),
        
        # Total claims by company
        (r'total\s+claims\s+by\s+company|total\s+claims\s+by\s+(life\s+)?insurer', 
         "SELECT life_insurer, SUM(total_claims_no) as total_claims FROM insurance_claims WHERE life_insurer NOT IN ('Industry', 'Industry Total', 'PVT.', 'Private Total', '') AND life_insurer IS NOT NULL GROUP BY life_insurer ORDER BY total_claims DESC LIMIT 15"),
        
        # Claims pending by company
        (r'claims\s+pending\s+by\s+company|claims\s+pending\s+by\s+(life\s+)?insurer', 
         "SELECT life_insurer, SUM(claims_pending_end_no) as total_pending FROM insurance_claims WHERE life_insurer NOT IN ('Industry', 'Industry Total', 'PVT.', 'Private Total', '') AND life_insurer IS NOT NULL GROUP BY life_insurer ORDER BY total_pending DESC LIMIT 15"),
        
        # Claims rejected by company
        (r'claims\s+rejected\s+by\s+company|claims\s+rejected\s+by\s+(life\s+)?insurer', 
         "SELECT life_insurer, SUM(claims_rejected_no) as total_rejected FROM insurance_claims WHERE life_insurer NOT IN ('Industry', 'Industry Total', 'PVT.', 'Private Total', '') AND life_insurer IS NOT NULL GROUP BY life_insurer ORDER BY total_rejected DESC LIMIT 15"),
    ]
    
    # Try to match patterns
    for pattern, sql in patterns:
        if re.search(pattern, question_lower):
            return sql
    
    # Default: return claims paid by company
    return "SELECT life_insurer, SUM(claims_paid_no) as total_claims_paid FROM insurance_claims WHERE life_insurer NOT IN ('Industry', 'Industry Total', 'PVT.', 'Private Total', '') AND life_insurer IS NOT NULL GROUP BY life_insurer ORDER BY total_claims_paid DESC LIMIT 15"

def execute_sql(sql_query: str) -> dict:
    """Execute SQL query and return results"""
    conn = sqlite3.connect(DB_PATH)
    
    try:
        # Execute the query
        result_df = pd.read_sql_query(sql_query, conn)
        conn.close()
        
        if result_df.empty:
            return {'labels': [], 'data': [], 'chartType': 'bar', 'error': 'No results found'}
        
        # Determine chart type based on data
        num_rows = len(result_df)
        
        # Get label and data columns
        columns = result_df.columns.tolist()
        label_col = columns[0]
        data_col = columns[1] if len(columns) > 1 else columns[0]
        
        labels = result_df[label_col].astype(str).tolist()
        data = result_df[data_col].round(2).tolist()
        
        # Detect chart type
        chart_type = 'bar'
        if num_rows <= 6:
            chart_type = 'pie'
        elif 'year' in label_col.lower():
            chart_type = 'line'
        
        return {
            'labels': labels,
            'data': data,
            'chartType': chart_type,
            'column': data_col,
            'labelColumn': label_col,
            'sql': sql_query
        }
    except Exception as e:
        conn.close()
        return {'labels': [], 'data': [], 'chartType': 'bar', 'error': str(e)}

def generate_conclusion(data: dict) -> str:
    """Generate an AI-like conclusion based on the chart data"""
    if not data or not data.get('labels') or not data.get('data'):
        return "Unable to generate conclusion. Please try a different query."
    
    labels = data['labels']
    values = data['data']
    column = data.get('column', 'value')
    label_column = data.get('labelColumn', 'category')
    
    if len(labels) == 0 or len(values) == 0:
        return "Unable to generate conclusion. Please try a different query."
    
    # Find highest and lowest values
    max_idx = values.index(max(values))
    min_idx = values.index(min(values))
    highest_label = labels[max_idx]
    lowest_label = labels[min_idx]
    highest_value = values[max_idx]
    lowest_value = values[min_idx]
    
    # Determine trend (if we have multiple data points over time)
    trend = "stable"
    if len(values) >= 2:
        # Check if it's year-based data
        is_year_data = 'year' in label_column.lower()
        
        if is_year_data:
            # Compare first and last values
            first_val = values[0]
            last_val = values[-1]
            
            if last_val > first_val * 1.1:
                trend = "increasing"
            elif last_val < first_val * 0.9:
                trend = "decreasing"
            else:
                trend = "relatively stable"
                
            # Check for year-over-year growth
            if len(values) >= 3:
                recent_avg = sum(values[-2:]) / 2
                early_avg = sum(values[:2]) / 2
                if recent_avg > early_avg * 1.1:
                    trend = "consistently increasing"
                elif recent_avg < early_avg * 0.9:
                    trend = "consistently decreasing"
        else:
            # For non-time series, compare first and last
            first_val = values[0]
            last_val = values[-1]
            if last_val > first_val * 1.1:
                trend = "increasing"
            elif last_val < first_val * 0.9:
                trend = "decreasing"
    
    # Calculate some statistics
    avg_value = sum(values) / len(values)
    total_value = sum(values)
    
    # Format column name for display
    column_display = column.replace('_', ' ').replace('total ', '').replace('avg ', 'average ')
    
    # Generate conclusion based on the column type
    conclusion_parts = []
    
    # Overall trend
    if trend == "increasing" or trend == "consistently increasing":
        conclusion_parts.append(f"{column_display.title()} has shown an increasing trend over the analyzed period.")
    elif trend == "decreasing" or trend == "consistently decreasing":
        conclusion_parts.append(f"{column_display.title()} has shown a decreasing trend over the analyzed period.")
    else:
        conclusion_parts.append(f"{column_display.title()} has remained relatively stable over the analyzed period.")
    
    # Highest and lowest
    conclusion_parts.append(f"{highest_label} has the highest {column_display} with {highest_value:,.2f}, while {lowest_label} has the lowest with {lowest_value:,.2f}.")
    
    # Key insight - range
    range_val = highest_value - lowest_value
    if highest_value > 0:
        variation_pct = (range_val / highest_value) * 100
        conclusion_parts.append(f"There is a {variation_pct:.1f}% variation between the highest and lowest values, indicating significant differences across {label_column.lower()}s.")
    
    # Business takeaway
    if 'claims_paid' in column.lower():
        if trend == "increasing" or trend == "consistently increasing":
            conclusion_parts.append("This trend suggests increasing insurance activity and higher claim volumes in recent years, indicating business growth.")
        elif trend == "decreasing" or trend == "consistently decreasing":
            conclusion_parts.append("This declining trend may indicate reduced claim processing or changes in policyholder behavior.")
        else:
            conclusion_parts.append("The stable trend suggests consistent claim processing over the analyzed period.")
    elif 'claims_intimated' in column.lower():
        if trend == "increasing" or trend == "consistently increasing":
            conclusion_parts.append("This indicates growing customer engagement and insurance uptake over the period.")
        else:
            conclusion_parts.append("The intimated claims pattern suggests stable market conditions.")
    elif 'claims_repudiated' in column.lower():
        if trend == "increasing":
            conclusion_parts.append("Higher repudiations may require review of underwriting practices or policy terms.")
        else:
            conclusion_parts.append("Repudiation rates appear controlled, suggesting effective claims management.")
    elif 'ratio' in column.lower():
        conclusion_parts.append("This ratio metric provides insights into operational efficiency and claims processing performance.")
    else:
        conclusion_parts.append(f"This data provides valuable insights for business decision-making and strategic planning.")
    
    return " ".join(conclusion_parts)

# Initialize database on startup
init_db()

def get_table_info():
    """Get current table information"""
    table_info_path = os.path.join(script_dir, 'table_info.json')
    if os.path.exists(table_info_path):
        with open(table_info_path, 'r') as f:
            return json.load(f)
    # Return default insurance claims columns
    return {
        'table_name': 'insurance_claims',
        'columns': ['life_insurer', 'year', 'claims_pending_start_no', 'claims_pending_start_amt',
                   'claims_intimated_no', 'claims_intimated_amt', 'total_claims_no', 'total_claims_amt',
                   'claims_paid_no', 'claims_paid_amt', 'claims_repudiated_no', 'claims_repudiated_amt',
                   'claims_rejected_no', 'claims_rejected_amt', 'claims_unclaimed_no', 'claims_unclaimed_amt',
                   'claims_pending_end_no', 'claims_pending_end_amt', 'claims_paid_ratio_no', 'claims_paid_ratio_amt',
                   'claims_repudiated_rejected_ratio_no', 'claims_repudiated_rejected_ratio_amt',
                   'claims_pending_ratio_no', 'claims_pending_ratio_amt', 'category']
    }

def generate_dynamic_sql(question: str, table_info: dict) -> str:
    """Generate dynamic SQL based on the uploaded CSV columns"""
    question_lower = question.lower()
    columns = table_info.get('columns', [])
    table_name = table_info.get('table_name', 'insurance_claims')
    
    # Find potential numeric columns (for aggregation)
    numeric_keywords = ['amount', 'no', 'count', 'total', 'sum', 'value', 'revenue', 'sales', 'profit', 'quantity']
    
    # Find potential label/category columns
    label_keywords = ['name', 'company', 'insurer', 'category', 'type', 'product', 'region', 'city', 'state', 'country']
    
    # Find year/date column
    year_col = None
    for col in columns:
        if 'year' in col.lower() or 'date' in col.lower():
            year_col = col
            break
    
    # Find category/name column
    category_col = None
    for col in columns:
        col_lower = col.lower()
        if any(kw in col_lower for kw in label_keywords):
            category_col = col
            break
    
    if not category_col and columns:
        category_col = columns[0]
    
    # Find numeric column
    numeric_col = None
    for col in columns:
        col_lower = col.lower()
        if any(kw in col_lower for kw in numeric_keywords):
            numeric_col = col
            break
    
    if not numeric_col and len(columns) > 1:
        numeric_col = columns[1]
    
    # Try to match patterns in the question
    if 'by year' in question_lower or 'by date' in question_lower:
        if year_col and numeric_col:
            return f"SELECT {year_col}, SUM({numeric_col}) as total_value FROM {table_name} WHERE {year_col} IS NOT NULL AND {year_col} != '' GROUP BY {year_col} ORDER BY {year_col}"
    
    if 'by company' in question_lower or 'by insurer' in question_lower or 'by name' in question_lower:
        if category_col and numeric_col:
            return f"SELECT {category_col}, SUM({numeric_col}) as total_value FROM {table_name} WHERE {category_col} IS NOT NULL AND {category_col} != '' GROUP BY {category_col} ORDER BY total_value DESC LIMIT 15"
    
    # Default: group by first column with sum of numeric column
    if category_col and numeric_col:
        return f"SELECT {category_col}, SUM({numeric_col}) as total_value FROM {table_name} WHERE {category_col} IS NOT NULL GROUP BY {category_col} ORDER BY total_value DESC LIMIT 15"
    
    # Fallback: just return first two columns
    if len(columns) >= 2:
        return f"SELECT {columns[0]}, {columns[1]} FROM {table_name} LIMIT 20"
    
    return f"SELECT * FROM {table_name} LIMIT 20"

class QueryRequest(BaseModel):
    query: str

@app.get("/")
def home():
    return {"message": "AI Dashboard backend running"}

@app.get("/data")
def get_data():
    """Get sample data from the database"""
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT * FROM insurance_claims LIMIT 20", conn)
    conn.close()
    return df.to_dict()

@app.get("/table-info")
def get_table_info_endpoint():
    """Get current table columns info"""
    return get_table_info()

@app.post("/query")
def query_data(request: QueryRequest):
    """Process natural language query and return chart data"""
    global conversation_history
    
    try:
        # Get table info 
        table_info = get_table_info()
        
        # First try insurance-specific patterns, then fall back to dynamic
        sql_query = generate_sql_with_pattern_matching(request.query)
        
        # If the SQL returns insurance-specific columns that don't exist, use dynamic
        if 'claims_paid_no' in sql_query or 'life_insurer' in sql_query:
            # Check if these columns exist in current table
            if 'claims_paid_no' not in table_info.get('columns', []):
                sql_query = generate_dynamic_sql(request.query, table_info)
        
        # Execute the SQL query
        result = execute_sql(sql_query)
        
        if 'error' in result:
            conversation_history.append({
                'question': request.query,
                'sql': sql_query,
                'error': result['error']
            })
            return result
        
        # Add to conversation history
        conversation_history.append({
            'question': request.query,
            'sql': sql_query,
            'result_summary': f"Returned {len(result['labels'])} rows"
        })

        # Keep only last 10 conversations
        if len(conversation_history) > 10:
            conversation_history = conversation_history[-10:]
        
        # Add title
        result['title'] = f"Query: {request.query}"
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/upload")
async def upload_csv(file: UploadFile = File(...)):
    """Upload a new CSV file to replace the dataset"""
    try:
        # Save uploaded file temporarily
        upload_dir = os.path.join(script_dir, '..', 'data', 'data')
        os.makedirs(upload_dir, exist_ok=True)
        temp_path = os.path.join(upload_dir, 'uploaded.csv')
        
        # Write uploaded file
        content = await file.read()
        with open(temp_path, 'wb') as f:
            f.write(content)
        
        # Load into database
        load_csv_to_db(temp_path)
        
        # Clean up temp file
        os.remove(temp_path)
        
        return {"message": "CSV uploaded successfully", "filename": file.filename}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/history")
def get_history():
    """Get conversation history"""
    return {"history": conversation_history}


@app.post("/history/clear")
def clear_history():
    """Clear conversation history"""
    global conversation_history
    conversation_history = []
    return {"message": "History cleared"}


@app.post("/conclusion")
def get_conclusion(request: QueryRequest):
    """Generate AI conclusion based on query results using Google Gemini"""
    try:
        # Get table info
        table_info = get_table_info()
        
        # Generate SQL for the query - use dynamic if not insurance data
        sql_query = generate_sql_with_pattern_matching(request.query)
        
        # If the SQL returns insurance-specific columns that don't exist, use dynamic
        if 'claims_paid_no' in sql_query or 'life_insurer' in sql_query:
            # Check if these columns exist in current table
            if 'claims_paid_no' not in table_info.get('columns', []):
                sql_query = generate_dynamic_sql(request.query, table_info)
        
        # Execute the SQL query
        result = execute_sql(sql_query)
        
        if 'error' in result or not result.get('labels'):
            return {"conclusion": "Unable to generate conclusion. Please try a different query.", "sql": sql_query}
        
        # Prepare data for Gemini
        labels = result.get('labels', [])
        values = result.get('data', [])
        column = result.get('column', 'data')
        label_column = result.get('labelColumn', 'category')
        
        # Format data for the prompt
        data_str = f"Category/Year: {', '.join(str(l) for l in labels)}\nValues ({column}): {', '.join(str(v) for v in values)}"
        
        # Check if Gemini API is configured
        if gemini_client:
            try:
                # Use Gemini to generate conclusion with new API
                prompt = f"""You are a business analyst. Based on the following data from an insurance claims database, provide a short but insightful business conclusion (2-3 sentences max):

Query: {request.query}
Data:
{data_str}

Include:
1. Overall trend (increasing/decreasing/stable)
2. Highest and lowest values with labels
3. A key business insight

Format your response as a natural paragraph, not bullet points. Start with "Conclusion:" """

                response = gemini_client.models.generate_content(
                    model='gemini-2.5-flash-lite',
                    contents=prompt
                )
                gemini_conclusion = response.text.strip()
                
                # Also calculate basic stats for display
                analysis = {
                    "highest": {"label": result['labels'][result['data'].index(max(result['data']))], "value": max(result['data'])},
                    "lowest": {"label": result['labels'][result['data'].index(min(result['data']))], "value": min(result['data'])},
                    "average": sum(result['data']) / len(result['data']),
                    "total": sum(result['data'])
                }
                
                return {
                    "conclusion": gemini_conclusion,
                    "sql": sql_query,
                    "analysis": analysis
                }
            except Exception as gemini_err:
                print(f"Gemini API error: {gemini_err}")
                # Fall back to rule-based conclusion
        
        # Fallback to rule-based conclusion if Gemini not available
        conclusion = generate_conclusion(result)
        
        return {
            "conclusion": conclusion,
            "sql": sql_query,
            "analysis": {
                "highest": {"label": result['labels'][result['data'].index(max(result['data']))], "value": max(result['data'])},
                "lowest": {"label": result['labels'][result['data'].index(min(result['data']))], "value": min(result['data'])},
                "average": sum(result['data']) / len(result['data']),
                "total": sum(result['data'])
            }
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

