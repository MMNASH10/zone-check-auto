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

# -- Colorado --
st.cache_data(show_spinner="Loading CO Enterprise zones...")
@retry_loader(max_attempts=3, delay=2)
def load_co_ez_data():
    url = "https://gis.colorado.gov/public/rest/services/OEDIT/Enterprise_Zones/MapServer/2/query"
    params = {
        "where": "1=1",
        "outFields": "*",
        "f": "geojson"
    }
    resp = requests.get(url, params=params)
    resp.raise_for_status()
    gdf = gpd.read_file(BytesIO(resp.content), driver="geojson")
    return gdf

st.cache_data(show_spinner="Loading CO Enhanced Rural Enterprise zones...")
@retry_loader(max_attempts=3, delay=2)
def load_co_erez_data():
    url = "https://gis.colorado.gov/public/rest/services/OEDIT/Enterprise_Zones/MapServer/1/query"
    params = {
        "where": "1=1",
        "outFields": "*",
        "f": "geojson"
    }
    resp = requests.get(url, params=params)
    resp.raise_for_status()
    gdf = gpd.read_file(BytesIO(resp.content), driver="geojson")
    return gdf

# -- Florida --
    # Rural Job Tax Credit
def is_fl_rjtc(geoid):
    county_fips = {"12003","12045","12079","12099","12047","12089","12007","12049","12093","12013","12051","12099","12023",
                   "12055","12107","12027","12059","12099","12029","12021","12121","12035","12063","12123","12037","12065",
                   "12125","12039","12067","12129","12041","12075", "12131","12043","12077","12133"}

    return str(geoid)[:5] in county_fips

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

# -- Hawaii --
@st.cache_data(show_spinner="Loading HI Enterprise zones...")
@retry_loader(max_attempts=3, delay=2)
def load_hi_ez_data():
    url = "https://geodata.hawaii.gov/arcgis/rest/services/BusinessEconomy/MapServer/4/query"
    params = {
        "where": "1=1",
        "outFields": "*",
        "f": "geojson"
    }
    resp = requests.get(url, params=params)
    resp.raise_for_status()
    gdf = gpd.read_file(BytesIO(resp.content), driver="geojson")
    return gdf

# -- Illinois --
@st.cache_data(show_spinner="Loading IL Enterprise zones...")
@retry_loader(max_attempts=3, delay=2)
def load_il_ez_data():
    url = "https://aglomaps.revenue.illinois.gov/arcgis/rest/services/EZ_Zone_Admin_2025/MapServer/0/query"
    params = {
        "where": "1=1",
        "outFields": "*",
        "f": "geojson"
    }
    resp = requests.get(url, params=params)
    resp.raise_for_status()
    gdf = gpd.read_file(BytesIO(resp.content), driver="geojson")
    return gdf

# -- Illinois --
@st.cache_data(show_spinner="Loading MD Enterprise zones...")
@retry_loader(max_attempts=3, delay=2)
def load_md_ez_data():
    url = "https://mdgeodata.md.gov/imap/rest/services/BusinessEconomy/MD_IncentiveZones/FeatureServer/5/query"
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
def load_tx_ez_data():
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
def load_va_ez_data():
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

