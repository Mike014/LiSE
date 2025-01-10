import sqlite3
import pandas as pd
import os

def get_tables(db_path):
    """
    Retrieves the names of all tables in the specified SQLite database.

    Parameters:
    db_path (str): The file path to the SQLite database.

    Returns:
    pd.DataFrame: A DataFrame containing the names of all tables in the database.
                  Returns None if the database file does not exist or is empty.
    """
    if os.path.exists(db_path) and os.path.getsize(db_path) > 0:
        conn = sqlite3.connect(db_path)
        tables = pd.read_sql_query("SELECT name FROM sqlite_master WHERE type='table';", conn)
        conn.close()
        return tables
    else:
        print(f"The file {db_path} does not exist or is empty.")
        return None

# Example usage of the function
base_dir = 'C:/Users/DELL/Desktop/OpenSourceProjects/Lise/LiSE'
db_path = os.path.join(base_dir, 'world.db')
tables = get_tables(db_path)
print("Available tables:", tables)
