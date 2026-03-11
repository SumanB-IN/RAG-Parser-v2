from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
import asyncio

import pandas as pd

from Vehicle_Report import Vehicle_Report, Vehicle_Report_Metadata

class Persist_Handler:
    def __init__(self):
        # self.engine = create_engine('postgresql+psycopg2://postgres:password@192.168.19.27:5432/Report_DB', echo = False)
        self.engine = create_engine('postgresql+psycopg2://postgres:postgres@localhost:5432/reportdb', echo = False)
        self.SessionMaker = sessionmaker(bind = self.engine)

        # Tables will be created if they didn't already exist.
        # Vehicle_Report.create_tables(self.engine)
        
    def _add_record_sync(self, vehicle_report_list: list[Vehicle_Report]):
        record_added = 0
        session = self.SessionMaker()
        try:
            for vehicle_report in vehicle_report_list:
                session.add(vehicle_report)
                try:
                    session.commit()
                    record_added += 1
                except IntegrityError as e:
                    session.rollback()
                    print(f"Integrity Error: {e.orig}")
                except SQLAlchemyError as e:
                    session.rollback()
                    print(f"An unexpected SQLAlchemy error occurred: {e}")
        finally:
            session.close()
        return record_added

    async def add_record(self, vehicle_report_list : list[Vehicle_Report]):
        return await asyncio.to_thread(self._add_record_sync, vehicle_report_list)

    def _add_record_metadata_sync(self, vehicle_report_metadata: Vehicle_Report_Metadata):
        session = self.SessionMaker()
        try:
            session.add(vehicle_report_metadata)
            try:
                session.commit()
                print("Metadata updated")
            except IntegrityError as e:
                session.rollback()
                print(f"Integrity Error: {e.orig}")
            except SQLAlchemyError as e:
                session.rollback()
                print(f"An unexpected SQLAlchemy error occurred: {e}")
        finally:
            session.close()

    async def add_record_metadata(self, vehicle_report_metadata: Vehicle_Report_Metadata):
        await asyncio.to_thread(self._add_record_metadata_sync, vehicle_report_metadata)

    def _get_record_sync(self, formation, year, month):
        # print(f"select * from vehicle_report where formation = '{formation}' and year = '{year}' and month = '{month}'")
        df = pd.read_sql_query(f"select * from vehicle_report where formation = '{formation}' and year = '{year}' and month = '{month}'", con=self.engine)
        return df

    async def get_record(self, formation, year, month):
        return await asyncio.to_thread(self._get_record_sync, formation, year, month)
    
    def _get_record_by_chunk_sync(self, chuck_metadata):
        formation, month, year = chuck_metadata.split("-")
        # print(f"select formation, month, year, category, mnc_due_to_mua, mnc_due_to_oh, mnc_due_to_r4, mnc_due_to_total, remarks from vehicle_report where formation = '{formation}' and year = '{year}' and month = '{month}'")
        df = pd.read_sql_query(f"select formation, month, year, category, mnc_due_to_mua, mnc_due_to_oh, mnc_due_to_r4, mnc_due_to_total, remarks from vehicle_report where formation = '{formation}' and year = '{year}' and month = '{month}'", con=self.engine)
        return df

    async def get_record_by_chunk(self, chuck_metadata):
        return await asyncio.to_thread(self._get_record_by_chunk_sync, chuck_metadata)
    
    def _get_data_for_combo_box_sync(self, column_name):
        df = pd.read_sql_query(f"select distinct {column_name} from vehicle_report", con=self.engine)
        return df[column_name].tolist()

    async def get_data_for_combo_box(self, column_name):
        return await asyncio.to_thread(self._get_data_for_combo_box_sync, column_name)
    
    def _get_record_metadata_sync(self, formation=None, year=None, month=None):

        sql_query = "select formation, year, month, component_type, record_count, insert_datetime, last_activity, last_activity_datetime from vehicle_report_metadata where deleted = 0"

        if formation is not None :
            sql_query = sql_query + f" and formation = '{formation}'"
        if year is not None :
            sql_query = sql_query + f" and year = '{year}'"
        if month is not None:
            sql_query = sql_query + f" and month = '{month}'"


        # print("Quering : " + sql_query)

        df = pd.read_sql_query(sql_query, con=self.engine)
        return df

    async def get_record_metadata(self, formation = None, year = None, month = None):
        return await asyncio.to_thread(self._get_record_metadata_sync, formation, year, month)

    def update_record_metadata(self, formation, year, month):
        pass

    async def populate_vector(self, formation, month, year):
        df = await self.get_record(formation, month, year)
        print(df.count)
        return df

