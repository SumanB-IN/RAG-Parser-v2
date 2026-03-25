import pandas as pd
import numpy as np
from pathlib import Path

class ReadFileSB:
# Define the file path for your Excel file\
    def __init__(self):
        pass
    
    def readEXCEL(self, path, sheet_name=None):
        sheet_data = None 
        excel_file_path = Path(path)
        try:
            # Read all sheets into a dictionary of DataFrames
            # sheet_data = pd.read_excel(excel_file_path, sheet_name=None, header=[0, 3], na_values=['-']).fillna(0)
            sheet_data = pd.read_excel(excel_file_path, sheet_name=sheet_name, header=[0, 4], dtype=str)
            # self.sheet_data.columns = ['_'.join(col).strip() for col in self.sheet_data.columns.values]
            print(f"Successfully read sheet '{sheet_name}' from '{excel_file_path}'.")
            
            # print(f"Successfully read all sheets from '{excel_file_path}'.")
            # print(f"Sheets found: {list(sheet_data.keys())}\n")

        except FileNotFoundError:
            print(f"Error: The file '{excel_file_path}' was not found.")
        except Exception as e:
            print(f"An error occurred: {e}")
        finally:    
            return sheet_data