from explore_data import get_tables
import matplotlib.pyplot as plt
import seaborn as sns
import os
import sqlite3
import pandas as pd

def view_table_data(db_path, table_name, column_name):
    """
    Visualizes the distribution of a specific column in a table from the SQLite database.

    Parameters:
    db_path (str): The file path to the SQLite database.
    table_name (str): The name of the table to visualize.
    column_name (str): The name of the column to visualize.

    Returns:
    pd.DataFrame: A DataFrame containing the first few rows of the table.
    """
    conn = sqlite3.connect(db_path)
    query = f"SELECT {column_name} FROM {table_name}"
    data = pd.read_sql_query(query, conn)
    conn.close()

    if column_name in data.columns:
        sns.histplot(data[column_name], kde=True)
        plt.title(f"Distribution of {column_name}")
        plt.show()
        return data.head()
    else:
        print(f"Column {column_name} does not exist in the table {table_name}.")
        return None

# Example usage of the function
base_dir = 'C:/Users/DELL/Desktop/OpenSourceProjects/Lise/LiSE'
db_path = os.path.join(base_dir, 'world.db')
tables = get_tables(db_path)
print("Available tables:", tables)

# Assuming 'nome_tabella' is the name of the table you want to explore
table_name = 'turns'  # Replace with the actual table name
column_name = '2'  # Replace with the actual column name

if table_name in tables['name'].values:
    print(view_table_data(db_path, table_name, column_name))
else:
    print(f"Table {table_name} does not exist in the database.")
