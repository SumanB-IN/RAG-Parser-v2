from langchain_ollama import ChatOllama
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
import asyncio
import json
import time
import requests
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_community.agent_toolkits.sql.base import create_sql_agent

from Persist_Handler import Persist_Handler


class LLMHandler:
    def __init__(self):
        self.ollama_base_url = "http://192.168.19.21:11434"
        self.model_name = "qwen2.5-coder:32b"
        self.llm_qwen = ChatOllama(base_url=self.ollama_base_url, model = self.model_name)
        self.llm_lama = ChatOllama(base_url=self.ollama_base_url, model = "codellama:7b-instruct")
        # self.llm = ChatOllama(base_url="http://localhost:11434", model = "llama3.1")
        self.template_overall = """Each row containing imformation about equipment status under different condition in an army formation for a month. 
                            The source field in each row can be used to identify the nonth, year and formation name respectively. 
                            Please do a side by side comparison of the two rows given in the context and generate a concise report of the delta.

                            Context: {context}

                            Consider the below dictionary to indentify the meaning of the field and the data.

                            1. "Dependency/Auth (UE)" is the number of authorized vehicles for the formation.
                            2. "Dependency/Held (UH)" is the actual number of vehicles held by the formation.
                            3. "MUA" stands for Maintenance‑Under‑Action, these vehicles are under maintainanace.
                            4. "OH" (Overhaul vehicles) 
                            5. "R4" (Repair Category 4), these vehicle are under repair in Army Base Workshop level.
                            6. Total vehicle under (MUA + OH + R4) are considered Non-mission Capable.
                            6. FMC stands for Fully Mission Capable, these are the vehicles that are available to the formation for use.
                            7. Please check that "Held" - ("MUA" + "OH" + "R4") IS EQUAL TO "FMC".

                            Then we have the remark section that contains further details of vehicles that are listed under MUA or OH or R4 category
                            You will have to analyze the Remarks and audit them with respect to the rest of the status and append to the report generated.

                            
                            Question: {question}
                            Answer"""
        
        self.template_remarks = """The dictionary key is the concatination of formation name, month, year and the component name. And the value is a list of string in which,
                                    each item is a remarks that contains the details about component that are in NMC mode, that is Non Mission Capable, 
                                    which includes "MUA","OH" and "R4".

                                    Each remarks should have a date that specify when the component was added to the NMC list, if there is no date then it's a red flag.

                                    Consider the following dictionary and information to infer the meaning of each remarks. 

                                    1. assy means assembly of any sub component of the component like for vehicle assembly can be engine, transfer-case, etc. These component comes under MUA category
                                    2. CL means classification of component the level of damage or repair required and the classifications are numbers in Roman. These component comes under R4 category.
                                    3. r/o means Respect of and will be followed by name of a workshop or location where the component is present right now for repair. These component comes under R4 category.

                                    If the remark list is empty then there is no component under Non Mission Capable category.

                            Context: {context}
                            Question: {question}
                            Answer"""
        self.template_summarize = """You are a military analyst. You have to summarize the information in the context about the equipment and their status and generate a concise report in a markdown format.
                            The information in the context is about the equipment status of an army formation for a month. Each row in the context contains information about a specific component of the equipment and its status under different category like MUA, OH and R4.

                            The data will be mostly in tabuler format and the column name will be the same as the field name in the database. You have to understand the meaning of each field and then summarize the information in a concise report.
                            Consider the below dictionary to indentify the meaning of the field and the data.

                            1. "Dependency/Auth (UE)" is the number of authorized vehicles for the formation.
                            2. "Dependency/Held (UH)" is the actual number of vehicles held by the formation.
                            3. "MUA" stands for Maintenance‑Under‑Action, these vehicles are under maintainanace.
                            4. "OH" (Overhaul vehicles) 
                            5. "R4" (Repair Category 4), these vehicle are under repair in Army Base Workshop level.
                            6. Total vehicle under (MUA + OH + R4) are considered Non-mission Capable.
                            6. FMC stands for Fully Mission Capable, these are the vehicles that are available to the formation for use.
                            7. Please check that "Held" - ("MUA" + "OH" + "R4") IS EQUAL TO "FMC".

                            Context: {context}
                            Question: {question}
                            """
        
        self.output_parser = StrOutputParser()

    def set_model(self, model_name: str):
        self.model_name = model_name
        self.llm_qwen = ChatOllama(base_url=self.ollama_base_url, model=self.model_name)

    def get_local_ollama_models(self):
        try:
            response = requests.get(f"{self.ollama_base_url.rstrip('/')}/api/tags", timeout=3)
            response.raise_for_status()
            models = response.json().get("models", [])
            # print(f"Available models from Ollama: {[model.get('name', '') for model in models if model.get('name')]}")
            return sorted([model.get("name", "") for model in models if model.get("name")])
        except Exception:
            return []

    async def interact_with_llm(self, context, question, scope):
        response = None
        if scope == "overall":
            prompt = PromptTemplate.from_template(self.template_overall)
            chain = prompt | self.llm_qwen | self.output_parser
            response = await chain.ainvoke({"context" : context, "question" : question})
        elif scope == "remarks":
            prompt = PromptTemplate.from_template(self.template_remarks)
            chain = prompt | self.llm_qwen | self.output_parser
            response = await chain.ainvoke({"context" : context, "question" : question})
        elif scope == "summarize":
            prompt = PromptTemplate.from_template(self.template_summarize)
            chain = prompt | self.llm_qwen | self.output_parser
            response = await chain.ainvoke({"context" : context, "question" : question})    
        return response

    async def get_answer_from_db(self, question):
        persist_handler = Persist_Handler()
        db = SQLDatabase(persist_handler.engine)
        toolkit = SQLDatabaseToolkit(db=db, llm=self.llm_qwen)

        agent = create_sql_agent(
            llm=self.llm_qwen,
            toolkit=toolkit,
            agent_type="zero-shot-react-description",
            verbose=True,
            agent_executor_kwargs={
                "handle_parsing_errors": "Parsing error detected. Reflect on the error, correct the action format/SQL, and try again."
            },
            system_message="""You are an assistant for querying a SQL database. You are given a question and you have to generate a SQL query to get the answer from the database.

                            Abbreviations in the question and their meaning:
                            1. MUA stands for Maintenance‑Under‑Action, these vehicles are under maintainanace.
                            2. OH (Overhaul vehicles)   
                            3. R4 (Repair Category 4), these vehicle are under repair in Army Base Workshop level.
                            4. Total vehicle under (MUA + OH + R4) are considered Non-mission Capable, which is denoted by NMC.
                            5. FMC stands for Fully Mission Capable, these are the vehicles that are available to the formation for use.   
                            6. Please check that "Held" - ("MUA" + "OH" + "R4") IS EQUAL TO "FMC".      

                            The database has the following tables and columns:
                            1. vehicle_report: id, formation, year, month, category, sub_category, dependency_auth, dependancy_held, mnc_due_to_mua, mnc_due_to_oh, mnc_due_to_r4, mnc_due_to_total, fmc, remarks, chunk_metadata, vector_embedding
                            2. vehicle_report_metadata: id, formation, year, month, component_type, record_count, insert_datetime, last_activity, last_activity_datetime

                            You have to generate a SQL query to get the answer from the database and then execute the query to get the answer. 
                            
                            If you are not sure about the table or column name then you can use the following SQL query to get the table and column names:
                            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';" to get the table names and "SELECT column_name FROM information_schema.columns WHERE table_name = 'table_name';" to get the column names of a specific table.
                            Always try to use the most specific table for querying the data. For example if the question is about vehicle report then try to use vehicle_report table instead of vehicle_report_metadata table.
                            
                            Use the following column mapping to understand the meaning of the column and to generate the SQL query:
                            1. "formation" is the name of the army formation.
                            2. "year" is the year of the report.
                            3. "month" is the month of the report. 
                            4. "category" is the category of the vehicle, which includes the make and type of the vehicle.
                            5. "sub_category" is the sub-category of the vehicle, which includes the specific model or capacity of the vehicle.
                            6. "dependency_auth" is the number of vehicles the unit is officially permitted to have according to its organizational structure.
                            7. "dependancy_held" is the actual number of vehicles currently physically present or assigned to the unit's inventory.
                            8. "mnc_due_to_mua" is the number of vehicles that are under maintenance action and are non-mission capable due to MUA.
                            9. "mnc_due_to_oh" is the number of vehicles that are under overhaul and are non-mission capable due to OH.
                            10. "mnc_due_to_r4" is the number of vehicles that are under repair category 4 and are non-mission capable due to R4.
                            11. "mnc_due_to_total" is the total number of vehicles that are non-mission capable that is NMC due to MUA, OH and R4.
                            12. "fmc" is the number of vehicles that are fully mission capable and are available for use by the formation.
                            13. "remarks" is the list of remarks that contains the details about the vehicles that are under MUA, OH and R4 category.
                            14. "chunk_metadata" is the metadata that is used to identify the chunk of the report that is used to generate the vector embedding.
                            15. "vector_embedding" is the vector embedding of the chunk of the report that is used to generate the answer from the database."""
        )

        try:
            start_time = time.perf_counter()
            response = await agent.ainvoke({"input": question})
            end_time = time.perf_counter()
            elapsed_time = end_time - start_time
            return elapsed_time, response
        except Exception as exc:
            error_message = f"SQL agent execution failed: {type(exc).__name__}: {exc}"
            return "",{
                "output": error_message,
                "error": error_message,
                "status": "failed"
            }
    
    # async def run_calls_async(self):
    #     # Use abatch for a list of prompts
    #     results = await self.llm.abatch(prompts)
    #     for prompt, result in zip(prompts, results):
    #         print(f"Prompt: {prompt}\nResult: {result}\n---")

if __name__ == "__main__":

    llmhandler = LLMHandler()

    # context = [
    #             {
    #             "sheet": "(B veh)",
    #             "ser_no": 2,
    #             "equipment_name": "B2",
    #             "file_name": "FRS\\Nov\\Fmn A Nov\\Nov 2025.xlsx",
    #             "data": [
    #             {
    #             "cell_name": "Ser No",
    #             "cell_contents": 2
    #             },
    #             {
    #             "cell_name": "Category (Make & Type)",
    #             "cell_contents": "B2"
    #             },
    #             {
    #             "cell_name": "Dependency/Auth (UE)",
    #             "cell_contents": 1718
    #             },
    #             {
    #             "cell_name": "Dependency/Held (UH)",
    #             "cell_contents": 1577
    #             },
    #             {
    #             "cell_name": "MUA",
    #             "cell_contents": 9
    #             },
    #             {
    #             "cell_name": "OH",
    #             "cell_contents": 0
    #             },
    #             {
    #             "cell_name": "R4",
    #             "cell_contents": 13
    #             },
    #             {
    #             "cell_name": "Total",
    #             "cell_contents": 22
    #             },
    #             {
    #             "cell_name": "FMC",
    #             "cell_contents": 1555
    #             },
    #             {
    #             "cell_name": "Remarks (To incl present loc of eqpt EOA)",
    #             "cell_contents": "\nMUAs-08\n04 X Eng assy demanded\n01 x Wind Shield Glass Deamded\n01 x Axle assy demanded \n02 x Chassis cracked (Chassis of Tata B2 in r/o 5 DOGRA fitment under progress at OEM Duliajan & 01 x B2 in r/o U10, chassis crack, followup report raised on 16 Oct 2025.)\n12 x CL V\n02 x CL VI"
    #             }
    #             ]
    #             },
    #             {
    #             "sheet": "Appx A (B veh)",
    #             "ser_no": 2,
    #             "equipment_name": "B2",
    #             "file_name": "FRS\\Dec\\Fmn A Dec\\Dec 2025 A.xlsx",
    #             "data": [
    #                 {
    #                 "cell_name": "Ser No",
    #                 "cell_contents": 2
    #                 },
    #                 {
    #                 "cell_name": "Category (Make & Type)",
    #                 "cell_contents": "B2"
    #                 },
    #                 {
    #                 "cell_name": "Dependency/Auth (UE)",
    #                 "cell_contents": 1718
    #                 },
    #                 {
    #                 "cell_name": "Dependency/Held (UH)",
    #                 "cell_contents": 1583
    #                 },
    #                 {
    #                 "cell_name": "MUA",
    #                 "cell_contents": 10
    #                 },
    #                 {
    #                 "cell_name": "OH",
    #                 "cell_contents": 0
    #                 },
    #                 {
    #                 "cell_name": "R4",
    #                 "cell_contents": 13
    #                 },
    #                 {
    #                 "cell_name": "Total",
    #                 "cell_contents": 23
    #                 },
    #                 {
    #                 "cell_name": "FMC",
    #                 "cell_contents": 1560
    #                 },
    #                 {
    #                 "cell_name": "Remarks (To incl present loc of eqpt EOA)",
    #                 "cell_contents": "\nMUAs-10\n06 X Eng assy demanded\n01 x Wind Shield Glass Deamded\n01 x Axle assy demanded \n02 x Chassis cracked \n12 x CL V\n01 x Newly collected "
    #                 }
    #               ]
    #             }
    #           ]
    # question = "Give me the difference in vehicle condition between the two JSON row"
    # llmhandler.interact_with_llm(context = context, question = question, scope = "overall")

    context = {"B Dec 2025 B1":["MUAS-04","03 x Eng assy demanded","01 x Case assy Transmission Demanded","23 x CL V","01 x Veh deposited ","01 x MG Veh BA No 11B 110882L  decl  CL-V in r/o 132 SR on 30 Oct 2025.  Veh deposited and the RV not yet recd."],
                "B Nov 2025 B1":["MUAS-04","04 x Eng assy demanded ","23 x CL V"]}
    print(type(json.dumps(context)))
    print(json.dumps(context))
    question = """From the two dictionary in the list extract the set of remarks aand then you have to compare the second sets of remarks with the first and 
                    get back with a report about the progess made by the formation in terms of how many component came out of the Non-Mission Capable list. 
                    As thoes component will get added to the FMC list that is the component are ready and are full mission capable.
                
                You have to red flag conditions where no status changed or no progress made by the formation
                
                The report has to be concise with only Conclusion and Recommendations in a markdown format"""
    asyncio.run(llmhandler.interact_with_llm(context = json.dumps(context), question = question, scope = "remarks"))
