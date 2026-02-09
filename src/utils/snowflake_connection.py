"""
Snowflake Connection Utility for Capim Meta-Ontology
Provides connection and query execution functions.
"""

import os
import snowflake.connector
import pandas as pd
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


def get_snowflake_connection():
    """
    Establishes a connection to Snowflake using credentials from .env file.
    Returns the connection object, or None if it fails.
    """
    required_credentials = {
        "user": os.getenv("SNOWFLAKE_USER"),
        "password": os.getenv("SNOWFLAKE_PASSWORD"),
        "account": os.getenv("SNOWFLAKE_ACCOUNT"),
    }

    optional_credentials = {
        "warehouse": os.getenv("SNOWFLAKE_WAREHOUSE"),
        "database": os.getenv("SNOWFLAKE_DATABASE"),
        "role": os.getenv("SNOWFLAKE_ROLE"),
    }

    missing_creds = [key for key, value in required_credentials.items() if value is None]
    if missing_creds:
        print(f"Error: Missing required environment variables: {', '.join(missing_creds)}")
        print("Make sure you have a '.env' file with user, password, and account values.")
        return None

    try:
        connect_args = {
            **required_credentials,
            **{k: v for k, v in optional_credentials.items() if v is not None}
        }
        
        conn = snowflake.connector.connect(**connect_args)
        print("Snowflake connection established successfully!")
        return conn
    except Exception as e:
        print(f"Error connecting to Snowflake: {e}")
        return None


def run_query(query: str) -> pd.DataFrame:
    """
    Executes a SQL query on Snowflake and returns results as a Pandas DataFrame.
    
    Args:
        query: SQL query string
        
    Returns:
        DataFrame with results, or None if error
    """
    conn = get_snowflake_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute(query)
            if cur.description is None:
                return pd.DataFrame()
            return cur.fetch_pandas_all()
        except Exception as e:
            print(f"Error executing query: {e}")
            return None
        finally:
            conn.close()
    return None


def validate_axiom(axiom_id: str, validation_query: str) -> dict:
    """
    Runs an axiom validation query and returns the result.
    
    Args:
        axiom_id: The ID of the axiom being validated
        validation_query: SQL query that should return 0 for PASS
        
    Returns:
        dict with {axiom_id, status, count, message}
    """
    result = run_query(validation_query)
    if result is None:
        return {
            "axiom_id": axiom_id,
            "status": "ERROR",
            "count": -1,
            "message": "Failed to execute query"
        }
    
    count = result.iloc[0, 0] if len(result) > 0 else 0
    status = "PASS" if count == 0 else "FAIL"
    
    return {
        "axiom_id": axiom_id,
        "status": status,
        "count": int(count),
        "message": f"Found {count} violations" if count > 0 else "No violations"
    }


if __name__ == "__main__":
    print("Testing Snowflake connection...")
    test_df = run_query("SELECT CURRENT_VERSION() as version")
    if test_df is not None:
        print(f"Snowflake Version: {test_df.iloc[0, 0]}")
    else:
        print("Connection test failed.")
