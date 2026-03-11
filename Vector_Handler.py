
import os
import shutil
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings.ollama import OllamaEmbeddings
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
# from langchain.embeddings import Em
from chromadb import PersistentClient
from chromadb.config import Settings
import requests
import hashlib

CHROMA_PATH = "chroma"

class VectorHandler:
    def __init__(self):
        pass

    def clear_db(self):
        if os.path.exists(CHROMA_PATH):
            shutil.rmtree(CHROMA_PATH)

    def get_embedding_function(self):
        # embeddings = OllamaEmbeddings(model="nomic-embed-text")
        embeddings = DefaultEmbeddingFunction()
        return embeddings

    def populate_vector_db(self, vehicle_report_list):
        # # Load the existing database.
        print("Inside Populate_vector_DB")
        embedding_function=self.get_embedding_function()
        client = PersistentClient(path=CHROMA_PATH)

        collection = client.get_or_create_collection(name = "Vehicle_Report", embedding_function = embedding_function)
        print("Collection Created")
        # Calculate Row IDs.
        ids = [self.calculate_chunk_ids(report) for report in vehicle_report_list]
        report_chunks = []
        for report in vehicle_report_list:
            report_chunks.append(report.__repr__())
        
        metadatas = [{"unit" : report.unit,
                     "month" : report.month,
                     "year" : report.year,
                     "category" : report.category}
                     for report in vehicle_report_list]
        
        print(f"Created {str(len(ids))} Ids, {str(len(report_chunks))} report_chunks and {str(len(metadatas))} metadatas")
        try:
            collection.add(documents = report_chunks, metadatas = metadatas, ids = ids, embeddings = embedding_function(report_chunks))
        except Exception:
            print("Error Occured")
        finally:
            print(collection.count())
        


    def calculate_chunk_ids(self, report):
        # for report in report_list:
        unit_category = str(report.unit) + " " + str(report.category)
        month_year = str(report.month) + " " + str(report.year)
        current_row_id = f"{unit_category}:{month_year}"
           
        hash = hashlib.md5(current_row_id.encode()).hexdigest()

        return hash

    def read_chunks(self, query_text, n, unit, month, year, category=None):
        client = PersistentClient(path=CHROMA_PATH)
        embedding_function=self.get_embedding_function()
        collection = client.get_or_create_collection(name = "Vehicle_Report", embedding_function = embedding_function)
        print("Quering Vector DB")
        # results = collection.query(
        #     query_texts=[f"{query_text}"],
        #     n_results=n
        # )
        # print(results)
        all_records = collection.get()
        print(all_records)

    def get_vector(self):
        res =requests.post(url = 'http://localhost:11434/api/embeddings',
                           json={
                               'model': 'nomic-embed-text',
                               'prompt': 'I am Suman Biswas'
                           })
        
        print(res.json()['embedding'])
        print(len(res.json()['embedding']))


if __name__ == '__main__':
    vh = VectorHandler()
    vh.get_vector()