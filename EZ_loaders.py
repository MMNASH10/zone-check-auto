import requests
from huggingface_hub import hf_hub_download
import geopandas as gpd
from io import BytesIO
import streamlit as st
import time
from functools import wraps

def retry_loader(max_attempts=3, delay=2):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    time.sleep(delay)
            raise last_exception
        return wrapper
    return decorator

# -- Florida --
    # Rural Job Tax Credit
def is_fl_rjtc(geoid):
    county_fips = {"003","045","079","099","047","089","007","049","093","013","051","099","023","055","107","027",
    "059","099","029","021","121","035","063","123","037","065","125","039","067","129","041","075", "131","043","077","133"}

    return str(geoid)[2:5] in county_fips

    # Rural Area Opportunity
@st.cache_data(show_spinner="Loading FL RAO zones...")
@retry_loader(max_attempts=3, delay=2)
def load_fl_rao_data():
    url = "https://services1.arcgis.com/nRHtyn3uE1kyzoYc/ArcGIS/rest/services/Rural_Areas_of_Opportunity/FeatureServer/0/query"
    params = {
        "where": "1=1",
        "outFields": "*",
        "f": "geojson"
    }
    resp = requests.get(url, params=params)
    resp.raise_for_status()
    gdf = gpd.read_file(BytesIO(resp.content), driver="geojson")
    return gdf

# -- Texas --
@st.cache_data(show_spinner="Loading TX Enterprise zones...")
@retry_loader(max_attempts=3, delay=2)
def load_tez_data():
    parquet_path = hf_hub_download(
        repo_id="MMNASH10/my-parquet-dataset",
        filename="TEZ_2020_complete.parquet",
        repo_type="dataset",
    )
    gdf = gpd.read_parquet(parquet_path)
    return gdf

# -- Virginia --
@st.cache_data(show_spinner="Loading VA Enterprise zones...")
@retry_loader(max_attempts=3, delay=2)
def load_vez_data():
    url = "https://maps.vedp.org/arcgis/rest/services/OpenData/OpenDataLayers/MapServer/3/query"
    params = {
        "where": "1=1",
        "outFields": "*",
        "f": "geojson"
    }
    resp = requests.get(url, params=params)
    resp.raise_for_status()
    gdf = gpd.read_file(BytesIO(resp.content), driver="geojson")
    return gdf

