import streamlit as st
import os
import gc
from firecrawl import FirecrawlApp
from dotenv import load_dotenv
import time
import pandas as pd
from typing import Dict, Any
import base64
from pydantic import BaseModel, Field

# Load environment variables (optional fallback)
load_dotenv()

# --- Config & Setup ---
st.set_page_config(page_title="Firecrawl Website to API", layout="wide")

@st.cache_resource
def get_firecrawl_app(api_key):
    return FirecrawlApp(api_key=api_key)

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []

if "schema_fields" not in st.session_state:
    st.session_state.schema_fields = [{"name": "", "type": "str"}]

def reset_chat():
    st.session_state.messages = []
    gc.collect()

# --- Helper Functions ---

def create_dynamic_model(fields):
    """Create a dynamic Pydantic model from schema fields."""
    field_annotations = {}
    for field in fields:
        if field["name"]:
            type_mapping = {
                "str": str,
                "bool": bool,
                "int": int,
                "float": float
            }
            field_annotations[field["name"]] = type_mapping[field["type"]]
    
    return type(
        "ExtractSchema",
        (BaseModel,),
        {
            "__annotations__": field_annotations
        }
    )

def create_schema_from_fields(fields):
    """Create schema using Pydantic model."""
    if not any(field["name"] for field in fields):
        return None
    
    model_class = create_dynamic_model(fields)
    return model_class.model_json_schema()

def convert_to_table(data):
    """Convert a list of dictionaries to a markdown table."""
    if not data:
        return ""
    # Convert only the data field to a pandas DataFrame
    df = pd.DataFrame(data)
    # Convert DataFrame to markdown table
    return df.to_markdown(index=False)

def stream_text(text: str, delay: float = 0.001) -> None:
    """Stream text with a typing effect."""
    placeholder = st.empty()
    displayed_text = ""
    for char in text:
        displayed_text += char
        placeholder.markdown(displayed_text)
        time.sleep(delay)
    return placeholder

# --- Main App Layout ---

st.title("Convert ANY website into an API using Firecrawl")

# --- Sidebar Configuration ---
with st.sidebar:
    st.header("🔑 API Configuration")
    
    # 1. Ask for API Key here
    user_api_key = st.text_input(
        "Firecrawl API Key",
        value=os.getenv("FIRECRAWL_API_KEY") or "", # Defaults to .env if available
        type="password",
        placeholder="fc-..."
    )
    
    st.divider()
    st.header("⚙️ Scraper Settings")
    
    # Website URL input
    website_url = st.text_input("Enter Website URL", placeholder="https://example.com")
    
    st.divider()
    
    # Schema Builder
    st.subheader("Schema Builder (Optional)")
    
    for i, field in enumerate(st.session_state.schema_fields):
        col1, col2 = st.columns([2, 1])
        with col1:
            field["name"] = st.text_input(
                "Field Name",
                value=field["name"],
                key=f"name_{i}",
                placeholder="e.g. price"
            )
        with col2:
            field["type"] = st.selectbox(
                "Type",
                options=["str", "bool", "int", "float"],
                key=f"type_{i}",
                index=0 if field["type"] == "str" else ["str", "bool", "int", "float"].index(field["type"])
            )

    if len(st.session_state.schema_fields) < 5:
        if st.button("Add Field ➕"):
            st.session_state.schema_fields.append({"name": "", "type": "str"})

# --- Chat Interface ---

# Display previous messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Chat Input
if prompt := st.chat_input("Ask about the website..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    
    with st.chat_message("assistant"):
        # Validation Checks
        if not user_api_key:
            st.error("🚨 Please enter your Firecrawl API Key in the sidebar to continue.")
        elif not website_url:
            st.error("Please enter a website URL first!")
        else:
            try:
                with st.spinner("Extracting data from website..."):
                    # Initialize app with the key provided in UI
                    app = get_firecrawl_app(user_api_key)
                    
                    schema = create_schema_from_fields(st.session_state.schema_fields)
                    
                    extract_params = {
                        'prompt': prompt
                    }
                    if schema:
                        extract_params['schema'] = schema
                        
                    data = app.extract(
                        [website_url],
                        extract_params
                    )
                    
                    # Handle Data Output
                    if isinstance(data.get('data'), list):
                        table = convert_to_table(data['data'])
                    elif isinstance(data.get('data'), dict):
                        # If data is a single dict, try to find a list inside or display the dict
                        first_key = list(data['data'].keys())[0]
                        if isinstance(data['data'][first_key], list):
                             table = convert_to_table(data['data'][first_key])
                        else:
                             # Fallback for single object
                             table = convert_to_table([data['data']])
                    else:
                        table = str(data)

                    placeholder = stream_text(table)
                    st.session_state.messages.append({"role": "assistant", "content": table})
            
            except Exception as e:
                st.error(f"An error occurred: {str(e)}")

# Footer
st.markdown("---")
st.markdown("Built with Firecrawl and Streamlit")
