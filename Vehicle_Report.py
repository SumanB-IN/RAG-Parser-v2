from pydantic import BaseModel
from typing import Optional
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, Boolean, DateTime, ARRAY
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector

Base = declarative_base()

class Vehicle_Report_Metadata(Base):

    __tablename__ = 'vehicle_report_metadata'

    id = Column(Integer, primary_key = True, nullable = False)
    formation = Column(String)
    year = Column(String)
    month = Column(String)
    component_type = Column(String)
    record_count = Column(Integer)
    deleted = Column(Integer, default = 0)
    insert_datetime = Column(DateTime, server_default=func.now())
    last_activity = Column(String, default = "Added")
    last_activity_datetime = Column(DateTime, server_default=func.now(), onupdate=func.now())

class Vehicle_Report(Base):
    
    __tablename__ = 'vehicle_report'

    id = Column(Integer, primary_key = True, nullable = False)
    formation = Column(String)
    year = Column(String)
    month = Column(String)
    category = Column(String)
    sub_category = Column(String)
    dependency_auth = Column(String)
    dependancy_held = Column(String)
    mnc_due_to_mua = Column(String)
    mnc_due_to_oh = Column(String)
    mnc_due_to_r4 = Column(String)
    mnc_due_to_total = Column(String)
    fmc = Column(String)
    remarks = Column(ARRAY(String))
    chunk_metadata = Column(String)
    vector_embedding = Column(Vector(768))

    def create_tables(engine):
        print("Creating Tables")
        Base.metadata.create_all(engine)

    def to_dict(self):
        """
        Return a dictionary representation of the model's columns.
        """
        return {field.name: getattr(self, field.name) for field in self.__table__.c}

    def __str__(self):
        return super().__str__()
    
    def __repr__(self):

        chunk = f"""The Column Category (Make & Type) with value {self.category} represent Specifies the manufacturer (e.g., Tata, Ashok Leyland) and the specific model or capacity (e.g., 2.5 Ton, 4x4, Gypsy) and 
        the column Auth (UE) with value {self.dependency_auth} represent The number of vehicles the unit is officially permitted to have according to its organizational structure. and
        the column Held (UH) with value {self.dependancy_held} represent The actual number of vehicles currently physically present or assigned to the unit's inventory. and
        the column {self.dependancy_held} represent Vehicles undergoing minor repairs or routine maintenance that can be finished quickly at the unit level. and
        the column MUA with value {self.mnc_due_to_mua} represent Vehicles undergoing major strip-down repairs or reconditioning, usually at a central workshop or depot. and
        the column OH with value {self.mnc_due_to_oh} represent Vehicles undergoing major strip-down repairs or reconditioning, usually at a central workshop or depot. and
        the column R4 with value {self.mnc_due_to_r4} represent Refers to heavy repairs that cannot be done at the unit level and require specialized field or base workshops. and
        the column Total (Under Repair) with value {self.mnc_due_to_total} represent The sum of MUA + OH + R4; the total number of vehicles currently out of service. and 
        the column FMC with value {self.fmc} represent The number of vehicles that are 100% fit for immediate operational deployment.
        the column Remarks with value {self.remarks} Specific notes, including the EOA (Equipment On Account) or the current physical location of the asset."""

        chunk_new = f"""The following information is regarding readiness of unit {self.unit} for month of {self.month} and year {self.year} for vehicle {self.category}, it specifies the manufacturer (e.g., Tata, Ashok Leyland) and the specific model or capacity (e.g., 2.5 Ton, 4x4, Gypsy) and 
        {self.dependency_auth} is the number of vehicles the unit is officially permitted to have according to its organizational structure but
        {self.dependancy_held} is the actual number of vehicles currently physically present or assigned to the unit's inventory.
        {self.dependancy_held} is the number of vehicles undergoing minor repairs or routine maintenance that can be finished quickly at the unit level. and
        All the vehicles held are not avaiable for combact some of them are under repair and this repair can be categorised into MUA, OH and R4 depending on the level or repair.

        Details of the above mentioned Category are given as following and vehicle under is category is not available for Combat:

            1. MUA stands for Minor Under Activity, this is for vehicles undergoing major strip-down repairs or reconditioning, usually at a central workshop or depot.
            2. OH stands for Overhaul, this is for Vehicles undergoing major strip-down repairs or reconditioning, usually at a central workshop or depot.
            3. R4 stands for Repair Level 4, this is for vehicles that needs heavy repairs which cannot be done at the unit level and require specialized field or base workshops.

        For this vehicle type {self.mnc_due_to_mua} is under MUA category, {self.mnc_due_to_oh} is under OH category and {self.mnc_due_to_r4} is under R4 category. 
        The sum of MUA + OH + R4 which is {self.mnc_due_to_total} for this category is the total number of vehicles currently out of service. 

        {self.fmc} is the number of vehicles that are 100% fit for immediate operational deployment.

        {self.remarks} Specific notes, including the EOA (Equipment On Account) or the current physical location of the asset."""

        return chunk_new
    

