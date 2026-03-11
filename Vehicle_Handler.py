import pandas as pd
import time, datetime
from read_file_SB import ReadFileSB
from read_file_TC import ReadFileTC
from Vehicle_Report import Vehicle_Report, Vehicle_Report_Metadata
from Persist_Handler import Persist_Handler
from Vector_Handler import VectorHandler
from LLM_Handler import LLMHandler

import json
import asyncio
import os
from pathlib import Path
# from typing import Dict, Any
# from openpyxl import load_workbook
# from pandas.api.types import is_float_dtype

import warnings
warnings.filterwarnings("ignore", category=FutureWarning)

class VehicleHandler:
    def __init__(self):
        self.persist_handler = Persist_Handler()
        self.vector_handler = VectorHandler()
        self.llm_handler = LLMHandler()

    def _run_async(self, coro):
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(coro)

    def process_data_TC(self, excel_path: Path, output_dir: Path, include_summary: bool = False) -> int:
        """Read all sheets and write one JSON file per equipment row."""
        readfileTC = ReadFileTC()
        sheets, workbook, backend = readfileTC.load_sheets_and_workbook(excel_path)
        written = 0
        frs_hierarchy = readfileTC.get_frs_hierarchy_path(excel_path)
        target_output_dir = output_dir / frs_hierarchy.parent
        target_output_dir.mkdir(parents=True, exist_ok=True)

        for sheet_name, raw_df in sheets.items():

            if "veh" not in sheet_name.lower(): # we are considering only vehicle
                continue

            if backend == "openpyxl":
                if sheet_name not in workbook.sheetnames:
                    print(f"Skipping sheet '{sheet_name}': sheet not found in workbook")
                    continue
                ws = workbook[sheet_name]
            else:
                if sheet_name not in workbook.sheet_names():
                    print(f"Skipping sheet '{sheet_name}': sheet not found in workbook")
                    continue
                ws = workbook.sheet_by_name(sheet_name)

            location = readfileTC.find_ser_no_location(raw_df)
            if location is None:
                print(f"Skipping sheet '{sheet_name}': 'Ser No'/'Ser'/'S No' not found in rows 1-6")
                continue

            header_row_idx, ser_no_col_idx = location
            if header_row_idx + 1 >= len(raw_df):
                print(f"Skipping sheet '{sheet_name}': missing second header row below 'Ser No'")
                continue

            equipment_name_col_idx = ser_no_col_idx + 1
            if equipment_name_col_idx >= raw_df.shape[1]:
                print(f"Skipping sheet '{sheet_name}': equipment name column not found")
                continue

            cell_names = readfileTC.build_cell_names(raw_df, ws, header_row_idx, backend)
            data_rows = raw_df.iloc[header_row_idx + 2 :].reset_index(drop=True)

            for _, row in data_rows.iterrows():
                ser_no_value = row.iloc[ser_no_col_idx]
                if not readfileTC.is_natural_number(ser_no_value):
                    continue

                equipment_name = readfileTC.normalized_text(row.iloc[equipment_name_col_idx])
                if equipment_name == "":
                    continue

                filename = readfileTC.sanitize_filename(excel_path, equipment_name)
                output_path = target_output_dir / f"{filename}.json"

                named_values = readfileTC.row_to_named_values(row, cell_names)
                payload = {
                    "sheet": sheet_name,
                    "source_file": str(frs_hierarchy),
                    "columns": named_values,
                }
                if include_summary:
                    payload.update(
                        readfileTC.build_flat_payload(
                            sheet_name=sheet_name,
                            ser_no_value=ser_no_value,
                            equipment_name=equipment_name,
                            frs_hierarchy=frs_hierarchy,
                            named_values=named_values,
                        )
                    )

                output_path.write_text(
                    json.dumps(payload, indent=2, ensure_ascii=False, default=str),
                    encoding="utf-8",
                )
                written += 1

        return written

    def process_data_SB(self, excel_file_path, report_metadata):
        file_name = Path(excel_file_path).stem
        month, year, formation = file_name.split(" ")
        report_metadata.formation = formation
        report_metadata.month = month
        report_metadata.year = year
        report_metadata.component_type = "Vehicle"
        sub_category = ""
        vehicle_report_list = []

        readfileSB = ReadFileSB()
        data = readfileSB.readEXCEL(excel_file_path)

        # Iterate through each sheet and work with its DataFrame
        for sheet_name, df in data.items():
            if "veh" in sheet_name.lower():
                print(f"--- Data from sheet: {sheet_name} ---")
                df.iloc[:, 8] = df.iloc[:, 8].replace(['-', '0'], 0)
                # df.columns = df.columns.str.replace(r'[^a-zA-Z0-9_]', ' ', regex=True)

                # You can now process each DataFrame (df) as needed
                for index, row in df.iterrows():
                    try:
                        if not pd.isna(row.iloc[2]) and str(int(row.iloc[2])).isdigit():
                            vehicle_report = Vehicle_Report(
                                formation = formation, 
                                year = year, 
                                month = month, 
                                category = df.iloc[index][1],
                                sub_category = sub_category,
                                dependency_auth = df.iloc[index][2], 
                                dependancy_held = df.iloc[index][3],
                                mnc_due_to_mua = df.iloc[index][4],
                                mnc_due_to_oh = df.iloc[index][5],
                                mnc_due_to_r4 = df.iloc[index][6],
                                mnc_due_to_total = df.iloc[index][7],
                                fmc = df.iloc[index][8],
                                remarks = df.iloc[index][9].splitlines() if (not pd.isna(df.iloc[index][9]) and isinstance(df.iloc[index][9].splitlines(), list)) else [],
                                chunk_metadata = f"{formation}-{month}-{year}")
                            
                            vehicle_report_list.append(vehicle_report)
                        else:
                            sub_category = row.iloc[0]
                            continue

                    except Exception as e:
                        print("Ignoring Row")

        print("Total Reports found : " + str(len(vehicle_report_list)))
        row_added = self._run_async(self.persist_handler.add_record(vehicle_report_list = vehicle_report_list))
        report_metadata.record_count = row_added

        return report_metadata
 
    def import_data(self, file_path: Path, folder_path: Path, output_dir: Path = None, include_summary:bool = None, storage_type: str = "database"):
        processed_files = 0
        total_handled = 0
        
        if file_path is not None and folder_path is None:
            print(f"Reading from File")
            report_metadata = Vehicle_Report_Metadata()
            if storage_type == "file":
                total_handled = self.process_data_TC(file_path, output_dir, include_summary=include_summary)
            else:
                report_metadata = self.process_data_SB(file_path, report_metadata)
                total_handled = report_metadata.record_count
                self._run_async(self.persist_handler.add_record_metadata(report_metadata))
            processed_files = 1

        elif folder_path is not None and file_path is None:
            print("Reading from Folder")
            xlsx_files = sorted(path for path in Path(folder_path).rglob("*") if path.is_file() and path.suffix.casefold() == ".xlsx")

            if not xlsx_files:
                raise FileNotFoundError(f"No .xlsx files found under directory: {folder_path}")
            else:
                print(f"{len(xlsx_files)} No of Files found")
            
            for xlsx_file in xlsx_files:
                print(f"Processing: {xlsx_file}")
                report_metadata = Vehicle_Report_Metadata()
                if storage_type == "file":
                    written_count = self.process_data_TC(xlsx_file, output_dir, include_summary=include_summary)
                    total_handled += written_count
                elif storage_type == "database":
                    report_metadata = self.process_data_SB(xlsx_file, report_metadata)
                    total_handled += report_metadata.record_count
                    self._run_async(self.persist_handler.add_record_metadata(report_metadata))
                    self._run_async(self.persist_handler.get_record_metadata(year="2025"))

            processed_files = len(xlsx_files)

            print(f"Done. Processed {len(xlsx_files)} .xlsx file(s); "f"wrote {total_handled} Components")
            
        else:
            print("Exiting")

        return processed_files, total_handled

    def get_vehicle_records(self, formation, year, month):
        df = self._run_async(self.persist_handler.get_record(formation, year, month))
        return df

    def get_data_for_combo_box(self, column_name):
        return self._run_async(self.persist_handler.get_data_for_combo_box(column_name))

    def get_vehicle_record_metadata(self, formation, year, month):
        df = self._run_async(self.persist_handler.get_record_metadata(formation, year, month))
        return df
            
    def generate_report(self, chunk_metadata_previous, chunk_metadata_current, question):
        df_previous = self._run_async(self.persist_handler.get_record_by_chunk(chunk_metadata_previous))
        df_current = self._run_async(self.persist_handler.get_record_by_chunk(chunk_metadata_current))
        report = {}
        remark_absent = []
        start_time = time.perf_counter()
        for p, c in zip(df_previous.itertuples(), df_current.itertuples()):
            if len(p.remarks) > 0 and len(c.remarks) > 0:
                context = {f"{p.formation} {p.month} {p.year} {p.category}" : p.remarks,
                        f"{c.formation} {c.month} {c.year} {c.category}" : c.remarks,}
                r = self._run_async(self.llm_handler.interact_with_llm(context = json.dumps(context), question = question, scope = "remarks"))
                report[f"{c.category}"] = r
            else:
                remark_absent.append(p.category)

        end_time = time.perf_counter()
        elapsed_time = end_time - start_time

        print("Report Generation Complete")
        print(f"Elapsed time: {elapsed_time:.2f} seconds")
        file_path = os.path.join("generated_report", f"report_{self.llm_handler.model_name.replace(':','-').replace('/','-')}_{chunk_metadata_previous}_{chunk_metadata_current}_{datetime.datetime.now().strftime('%Y-%m-%d-%H-%M-%S')}.json")
        with open(file_path, 'w') as json_file:
            json.dump(report, json_file, indent=4)
        print("Report saved to: " + str(file_path))
        return remark_absent, elapsed_time, report

    def summarize_answer(self, context, question):
        start_time = time.perf_counter()
        r = self._run_async(self.llm_handler.interact_with_llm(context = context, question = question, scope = "summarize"))
        end_time = time.perf_counter()
        elapsed_time = end_time - start_time
        return elapsed_time, r

if __name__ == "__main__":
    # path = "E:\LLM_Project\RAG-Parser-v2\FRS_filtered\\Dec\\Fmn A Dec\\Dec 2025 A.xlsx"
    # VehicleHandler().import_data(file_path = path, folder_path = None, output_dir = "Output_JSON", include_summary = False, storage_type = "database")
    # path = "E:\\LLM_Project\\RAG-Parser-v2\\FRS_filtered\\Dec"
    # VehicleHandler().import_data(file_path = None, folder_path = path, output_dir = "Output_JSON", include_summary = False, storage_type = "database")
    # VehicleHandler().get_vehicle_records("D", "2025", "Dec")
    question = """From the two dictionary in the list extract the set of remarks aand then you have to compare the second sets of remarks with the first and 
                    get back with a report about the progess made by the formation in terms of how many component came out of the Non-Mission Capable list. 
                    As thoes component will get added to the FMC list that is the component are ready and are full mission capable.
                
                You have to red flag conditions where no status changed or no progress made by the formation
                
                The report has to be concise with only Conclusion and Recommendations"""
    VehicleHandler().generate_report("A-Nov-2025", "A-Dec-2025", question)
        