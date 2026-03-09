"""
Snowflake Connection Utility for Client-Voice-Data
Provides connection and query execution functions.

Forked from: capim-meta-ontology/src/utils/snowflake_connection.py @ 2026-02-12
Reason: Project emancipation — remove hard dependency on meta-ontology filesystem.
"""

import os
from pathlib import Path

import snowflake.connector
import pandas as pd
from dotenv import load_dotenv

# Load environment variables from .env file
# Look for .env in project root first, then fall back to parent dirs
_project_root = Path(__file__).parent.parent.parent
_env_path = _project_root / ".env"
if _env_path.exists():
    load_dotenv(_env_path)
else:
    # Fallback: try to find .env in parent directories (backwards compatibility)
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


if __name__ == "__main__":
    print("Testing Snowflake connection...")
    test_df = run_query("SELECT CURRENT_VERSION() as version")
    if test_df is not None:
        print(f"Snowflake Version: {test_df.iloc[0, 0]}")
    else:
        print("Connection test failed.")
