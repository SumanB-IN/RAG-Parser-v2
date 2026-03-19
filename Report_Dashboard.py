import torch
torch.classes.__path__ = []

import plotly.express as px
import pandas as pd
import asyncio
import streamlit as st
import json
import tempfile
from pathlib import Path

from Vehicle_Handler import VehicleHandler
from LLM_Handler import LLMHandler

st.set_page_config(
    layout="wide",
    page_title="DEMO APP"
)

st.title("Formation Readiness Analytics")

st.markdown(
    """
    <style>
    .main .block-container {
        padding-top: 1.2rem;
        padding-bottom: 1.5rem;
        max-width: 95rem;
    }

    h1, h2, h3 {
        letter-spacing: 0.2px;
    }

    [data-baseweb="tab-list"] {
        gap: 0.35rem;
        margin-bottom: 0.5rem;
    }

    button[data-baseweb="tab"] {
        border-radius: 0.65rem;
        padding: 0.45rem 0.9rem;
        font-weight: 600;
    }

    div[data-testid="stForm"] {
        border: 1px solid var(--secondary-background-color);
        border-radius: 0.75rem;
        padding: 0.75rem 0.9rem 0.35rem 0.9rem;
    }

    div[data-testid="stDataFrame"] {
        border-radius: 0.7rem;
        overflow: hidden;
    }

    div.stButton > button {
        border-radius: 0.6rem;
        font-weight: 600;
    }

    div[data-testid="stMetric"] {
        border-radius: 0.7rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

vehicle_handler = VehicleHandler()
llm_handler = LLMHandler()
available_models = llm_handler.get_local_ollama_models()

# Display in Streamlit
tab1, tab2, tab3, tab4 = st.tabs(["📤 File Upload", "📄 Historical Report", "📊 Dashboard", "❓ Q&A"])

# Add content to the first tab
with tab1:
    st.header("File Uploader")
    with st.form("import_form"):
            input_path_text = st.text_input("Input path (file or directory)", value="", placeholder=r"C:\path\to\file.xlsx or C:\path\to\folder")
            submitted = st.form_submit_button("Import Data")

    if submitted:
        try:
            with st.spinner("Processing..."):
                processed_files = 0
                total_written = 0

                if input_path_text.strip():
                    input_path = Path(input_path_text.strip())
                    if input_path.is_file():
                        processed_files, total_written = vehicle_handler.import_data(
                            file_path=input_path,
                            folder_path=None
                        )
                    elif input_path.is_dir():
                        processed_files, total_written = vehicle_handler.import_data(
                            file_path=None,
                            folder_path=input_path
                        )
                    else:
                        st.error("Provided path does not exist.")
                else:
                    st.error("Provide a path, or browse a file/folder to import.")

            if processed_files > 0 or total_written > 0:
                st.success(
                    f"Done. Processed {processed_files} .xlsx file(s); wrote {total_written} JSON file(s)."
                )
        except Exception as exc:
            st.error(str(exc))

    st.divider()

    col1, col2, col3 = st.columns(3)
    with col1:
        input_frm = st.text_input("Formation", value=None)
    with col2: 
        input_month = st.text_input("Month", value=None)
    with col3:
        input_year = st.text_input("Year", value=None)
    if input_frm == "":
        input_frm = None
    if input_month == "":
        input_month = None
    if input_year == "":
        input_year = None
    
    df = vehicle_handler.get_vehicle_record_metadata(input_frm, input_month, input_year)
    
    event = st.dataframe(df, on_select='rerun', selection_mode='multi-row')

    selected_indices = event.selection.rows
    selected_rows = []
    if selected_indices:
        if len(selected_indices) > 2:
            st.warning("You can only select up to 2 rows.")
        elif len(selected_indices) == 1:
            st.info("Only 1 row selected. Please select another row of the same formation to generate a report.")
        elif len(selected_indices) == 2 and df.iloc[selected_indices[0]]['formation'] != df.iloc[selected_indices[1]]['formation']:
            st.warning("Selected rows are from different formations. Please select rows from the same formation.")
        elif len(selected_indices) == 2 and df.iloc[selected_indices[0]]['formation'] == df.iloc[selected_indices[1]]['formation']:
            filtered_df = df.iloc[selected_indices]
            filtered_df.sort_values(by='month', ascending=False, inplace=True)

            for index, row in filtered_df.iterrows():
                selected_rows.append(f"{row['formation']}-{row['month']}-{row['year']}")

            action_col, option_col, name_col, model_col = st.columns([1, 2, 3, 4])
            with option_col:
                generate_new_report = st.checkbox("Generate new report", value=False, key="tab1_generate_new_report")
            with model_col:
                current_model = llm_handler.model_name
                if current_model and current_model not in available_models:
                    available_models = [current_model] + available_models
                if not available_models:
                    available_models = [current_model]

                selected_model = st.selectbox(
                    "Select Model",
                    options=available_models,
                    index=available_models.index(current_model) if current_model in available_models else 0,
                    key="tab1_ollama_model",
                    label_visibility="collapsed"
                )
                if selected_model and selected_model != vehicle_handler.llm_handler.model_name:
                    vehicle_handler.set_model(selected_model)
            with name_col:
                pass
        
            with action_col:
                generate_or_load = st.button("Generate Report", type="primary")

            if generate_or_load:
                question = """From the two dictionary in the list extract the set of remarks aand then you have to compare the second sets of remarks with the first and 
                                get back with a report about the progess made by the formation in terms of how many component came out of the Non-Mission Capable list. 
                                As thoes component will get added to the FMC list that is the component are ready and are full mission capable.
                    
                                You have to red flag conditions where no status changed or no progress made by the formation
                    
                                The report has to be concise with only Conclusion and Recommendations"""

                empty_component = []
                report_dict = None
                elapsed_time = None
                loaded_report_path = None

                if generate_new_report:
                    with st.spinner("Generating Report..."):
                        empty_component, elapsed_time, report_dict = vehicle_handler.generate_report(selected_rows[0], selected_rows[1], question)
                else:
                    report_dir = Path("generated_report")
                    matching_files = []
                    if report_dir.exists() and report_dir.is_dir():
                        for report_file in report_dir.glob("report_*.json"):
                            parts = report_file.stem.split("_")
                            if len(parts) > 4 and parts[2] == selected_rows[0] and parts[3] == selected_rows[1] and parts[1] == llm_handler.model_name.replace(":", "-"):
                                matching_files.append(report_file)

                    if matching_files:
                        loaded_report_path = max(matching_files, key=lambda path: path.stat().st_mtime)
                        with st.spinner("Loading pre-generated report..."):
                            with open(loaded_report_path, "r", encoding="utf-8") as file:
                                report_dict = json.load(file)
                    else:
                        st.warning("No pre-generated report found for selected rows in generated_report.")
                
                if report_dict is not None:
                    st.divider()
                    if generate_new_report and elapsed_time is not None:
                        st.info(f"Report generated in {elapsed_time:.2f} seconds")
                    elif loaded_report_path is not None:
                        st.info(f"Loaded pre-generated report: {loaded_report_path.name}")

                    st.subheader(f"Progress Report for Formation {selected_rows[1].split('-')[0]} for {selected_rows[0].split('-')[1]}{selected_rows[0].split('-')[2]} vs {selected_rows[1].split('-')[1]} {selected_rows[1].split('-')[2]}")

                    if isinstance(report_dict, dict):
                        for key, markdown_content in report_dict.items():
                            st.markdown(f"### **Equipment: {key}**")
                            st.markdown(markdown_content)
                            st.divider()
                    else:
                        st.markdown(report_dict)
                        st.divider()

                    if generate_new_report:
                        if empty_component:
                            st.info(f"Remarks not found for {len(empty_component)} equipment(s)")
                        else:
                            st.success("All components have remarks")
 

    else:
        st.info("Select 2 rows of Same formation to generate a report.")

with tab2:
    st.subheader("Previous Generated Reports")
    browse_path = "generated_report"
    available_files = []
    if browse_path.strip():
        browse_path = Path(browse_path.strip())
        if not browse_path.exists():
            st.warning("Provided folder path does not exist.")
        elif not browse_path.is_dir():
            st.warning("Provided path is not a directory.")
        else:
            available_files = sorted(
                path for path in browse_path.rglob("*")
                if path.is_file() and path.suffix.casefold() == ".json"
            )

            if available_files:
                st.caption(f"Found {len(available_files)} .json file(s)")
                file_name_map = {path.stem: str(path) for path in available_files}
                file_names = sorted(file_name_map.keys())

                split_parts = [file_name.split("_") for file_name in file_names]
                previous_values = [parts[2] if len(parts) > 2 else "" for parts in split_parts]
                current_values = [parts[3] if len(parts) > 3 else "" for parts in split_parts]
                previous_split = [value.split("-") for value in previous_values]
                current_split = [value.split("-") for value in current_values]
                selection_df = pd.DataFrame(
                    {
                        "Select": [False] * len(file_names),
                        "file_name": file_names,
                        "model_name": [parts[1] if len(parts) > 0 else "" for parts in split_parts],
                        "previous_month": [parts[1] if len(parts) > 1 else "" for parts in previous_split],
                        "previous_year": [parts[2] if len(parts) > 2 else "" for parts in previous_split],
                        "current_formation": [parts[0] if len(parts) > 0 else "" for parts in current_split],
                        "current_month": [parts[1] if len(parts) > 1 else "" for parts in current_split],
                        "current_year": [parts[2] if len(parts) > 2 else "" for parts in current_split],
                        "timestamp": [parts[4] if len(parts) > 3 else "" for parts in split_parts],
                    }
                )

                edited_selection_df = st.data_editor(
                    selection_df,
                    use_container_width=True,
                    hide_index=True,
                    disabled=[
                        "file_name", "model_name", "previous_month", "previous_year",
                       "current_formation", "current_month", "current_year", "timestamp"
                    ],
                    column_order=[
                        "Select", "model_name",
                        "previous_month", "previous_year",
                        "current_formation", "current_month", "current_year",
                        "timestamp"
                    ],
                    column_config={
                        "Select": st.column_config.CheckboxColumn("Select"),
                        "model_name": st.column_config.TextColumn("Model Name"),
                        "previous_month": st.column_config.TextColumn("Previous Month"),
                        "previous_year": st.column_config.TextColumn("Previous Year"),
                        "current_formation": st.column_config.TextColumn("Formation"),
                        "current_month": st.column_config.TextColumn("Current Month"),
                        "current_year": st.column_config.TextColumn("Current Year"),
                        "timestamp": st.column_config.TextColumn("Timestamp"),
                    },
                    key="report_file_selector"
                )

                if st.button("Load Selected Report", type="secondary"):
                    try:
                        selected_rows = edited_selection_df[edited_selection_df["Select"] == True]
                        if len(selected_rows) != 1:
                            st.warning("Please select exactly one file to load.")
                        else:
                            selected_file = selected_rows.iloc[0]["file_name"]
                            selected_file_path = file_name_map[selected_file]
                            with st.spinner("Loading selected JSON file..."):
                                with open(selected_file_path, "r", encoding="utf-8") as file:
                                    loaded_json = json.load(file)
                            st.success(f"Loaded JSON file: {selected_file}")
                            print(current_split)
                            print(current_split[0])
                            st.subheader(f"Progress Report of Formation {current_split[0][0]} for {previous_split[0][1]} {previous_split[0][2]} vs {current_split[0][1]} {current_split[0][2]}")

                            if isinstance(loaded_json, dict):
                                # If report_dict is a dictionary, render each section
                                for key, markdown_content in loaded_json.items():
                                    st.markdown(f"### **Equipment: {key}**")
                                    st.markdown(markdown_content)
                                    st.divider()
                            else:
                                # If it's a string, render it directly
                                st.markdown(loaded_json)
                                st.divider()
                    except Exception as exc:
                        st.error(str(exc))
            else:
                st.info("No .json files found in the provided folder.")
       
with tab3:
    st.header("Dashboard")

    col1, col2, col3 = st.columns(3)
    with col1:
        d_input_frm = st.selectbox('Select a formation', vehicle_handler.get_data_for_combo_box('formation'))
    with col2: 
        d_input_month = st.selectbox('Select a month', vehicle_handler.get_data_for_combo_box('month'))
    with col3:
        d_input_year = st.selectbox('Select a year', vehicle_handler.get_data_for_combo_box('year'))
    if d_input_frm == "":
        d_input_frm = None
    if d_input_month == "":
        d_input_month = None
    if d_input_year == "":
        d_input_year = None

    st.divider()

    vehicle_data = vehicle_handler.get_vehicle_records(d_input_frm, d_input_year, d_input_month)

    vehicle_data['dependency_auth'] = pd.to_numeric(vehicle_data['dependency_auth'], errors='ignore')
    vehicle_data['dependancy_held'] = pd.to_numeric(vehicle_data['dependancy_held'], errors='ignore')
    vehicle_data['mnc_due_to_mua'] = pd.to_numeric(vehicle_data['mnc_due_to_mua'], errors='ignore')
    vehicle_data['mnc_due_to_oh'] = pd.to_numeric(vehicle_data['mnc_due_to_oh'], errors='ignore')
    vehicle_data['mnc_due_to_r4'] = pd.to_numeric(vehicle_data['mnc_due_to_r4'], errors='ignore')
    vehicle_data['mnc_due_to_total'] = pd.to_numeric(vehicle_data['mnc_due_to_total'], errors='ignore')
    vehicle_data['fmc'] = pd.to_numeric(vehicle_data['fmc'], errors='ignore')
    
    data_sub_category_wise = vehicle_data.groupby('sub_category', as_index = False).sum()
    
    data_category_wise = vehicle_data.groupby('category', as_index = False).sum()
    
    # Create Bar Chart
    Bar_Chart_Category_Wise = px.bar(data_category_wise.drop(columns=['id', 'formation', 'year', 'month', 'sub_category', 'dependency_auth', 'dependancy_held', 'fmc', 'remarks']), 
                                    x="category", 
                                    y=['category', 'mnc_due_to_mua', 'mnc_due_to_oh', 'mnc_due_to_r4', 'mnc_due_to_total'], 
                                    title="Total non Combact Category Wise")

    Bar_Chart_Sub_Category_Wise = px.bar(data_sub_category_wise.drop(columns=['id', 'formation', 'year', 'month', 'category', 'dependency_auth', 'dependancy_held', 'fmc', 'remarks']), 
                                        x="sub_category", 
                                        y=['sub_category', 'mnc_due_to_mua', 'mnc_due_to_oh', 'mnc_due_to_r4', 'mnc_due_to_total'], 
                                        title="Total non Combact Sub-Category Wise")

    Line_Chart_Sub_Category_Wise_Combact_Readiness = px.line(data_sub_category_wise.drop(columns=['id', 'formation', 'year', 'month', 'category', 'dependency_auth', 'dependancy_held', 'mnc_due_to_mua', 'mnc_due_to_oh', 'mnc_due_to_r4', 'remarks']),
                                                            x = "sub_category",
                                                            y = ['mnc_due_to_total', 'fmc'],
                                                            title = "Combact Readiness Level Sub Category Wise")

    data_sub_category_wise_combact_readiness_in_percentage = data_sub_category_wise.drop(columns=['id', 'formation', 'year', 'month', 'category', 'dependency_auth', 'dependancy_held', 'mnc_due_to_mua', 'mnc_due_to_oh', 'mnc_due_to_r4', 'remarks'])
    data_sub_category_wise_combact_readiness_in_percentage['percentage'] = (data_sub_category_wise_combact_readiness_in_percentage['fmc'].astype(int) / data_sub_category_wise_combact_readiness_in_percentage['fmc'].astype(int).sum()) * 100

    Pie_Chart_formation_Readiness_in_Percentage = px.pie(data_sub_category_wise_combact_readiness_in_percentage.drop(columns = ['mnc_due_to_total', 'fmc']),
                                                    values='percentage', 
                                                    names='sub_category',
                                                    title="Combact Readiness Chart Sub-Category Wise")

    col1, col2 = st.columns(2)

    with col1:
        st.plotly_chart(Bar_Chart_Category_Wise)
        st.plotly_chart(Bar_Chart_Sub_Category_Wise)

    with col2:
        st.plotly_chart(Line_Chart_Sub_Category_Wise_Combact_Readiness)
        st.plotly_chart(Pie_Chart_formation_Readiness_in_Percentage)

with tab4:
    st.header("Q&A Section")
    if "qa_question" not in st.session_state:
        st.session_state.qa_question = ""
    if "qa_answer" not in st.session_state:
        st.session_state.qa_answer = None
    if "qa_elapsed_time" not in st.session_state:
        st.session_state.qa_elapsed_time = None

    with st.form("question_form"):
        question = st.text_input("Enter your Question")
        path_to_JSON_file = "Output_JSON"
        submitted = st.form_submit_button("Get the Answer")
    if submitted:  
        with st.spinner("Processing..."):
            elapsed_time, llm_response = loop.run_until_complete(llm_handler.get_answer_from_db(question=question))

        st.session_state.qa_question = question
        st.session_state.qa_answer = llm_response
        st.session_state.qa_elapsed_time = elapsed_time

    if st.session_state.qa_answer is not None:
        st.divider()
        st.subheader("Answer")
        if st.session_state.qa_elapsed_time is not None and st.session_state.qa_elapsed_time != "":
            st.info(f"Query processed in {st.session_state.qa_elapsed_time:.2f} seconds")
        st.markdown(st.session_state.qa_answer.get("output", ""))
        st.divider()

        if st.button("Summarize the Answer", key="summarize_answer_button"):
            with st.spinner("Summarizing..."):
                summary_elapsed_time, summary_text = vehicle_handler.summarize_answer(
                    context=st.session_state.qa_answer.get("output", ""),
                    question=st.session_state.qa_question
                )
            st.divider()
            st.info(f"Summarization processed in {summary_elapsed_time:.2f} seconds")
            st.markdown(summary_text)


# Run Command : streamlit run Report_Dashboard.py --server.port 10056
