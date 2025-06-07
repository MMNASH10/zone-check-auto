import streamlit as st
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
import os

st.set_page_config(page_title="Eligibility Lookup Tool", page_icon="🌲", layout="wide")
st.title("Census Tract Eligibility Lookup Tool")

# Load census tract shapefiles
@st.cache_resource
def load_tract_shapefile():
    return gpd.read_file("tracts_shapefile/national_tracts_2020.shp").to_crs("EPSG:4326")

# Load eligibility flags CSV
@st.cache_data
def load_eligibility_data():
    # read docs if needed
    return pd.read_csv("eligibility_flags.csv", dtype={"GEOID": str})

tracts_gdf = load_tract_shapefile()
eligibility_df = load_eligibility_data()

# Choose input method (Excel/CSV or Manual Input)
method = st.radio("Choose coordinates input method:", ["Upload Excel/CSV", "Enter coordinates manually"])
