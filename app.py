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
method = st.radio("Choose coordinates input method:",
                  ["Upload Excel/CSV", "Enter coordinates manually"],
                  help="For uploading an Excel or CSV file,  make sure you have the first column as latitudes"
                       " and the second column as longitudes.\n\nIf you are inputting the coordinates manually,"
                        " enter each latitude and longitude pair seperated by ___"
                  )

# Function to do spatial join + merge eligibility flags
def process_coords(df):
    # Make GeoDataFrame frame from lat/lon
    gdf = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.longitude, df.latitude), crs="EPSG:4326")
    # Spatial join with census tracts
    joined = gpd.sjoin(gdf, tracts_gdf, how="left", predicate="within")
    # Merge eligibility data
    result = pd.merge(joined, eligibility_df, on="GEOID", how="left")
    # Select output columns (NAMELSAD???)
    return result[["latitude", "longitude", "GEOID", "NAMELSAD", "NCMT_Eligibility"]]

# Excel/CSV Upload Method
if method == "Upload Excel/CSV":
    uploaded_file = st.file_uploader("Upload a file with 'latitude' and 'longitude' columns",
                                     type=["csv", "xlsx"])
    if uploaded_file is not None:
        try:
            df = pd.read_excel(uploaded_file) if uploaded_file.name.endswith(".xlsx") else pd.read_csv(uploaded_file)
            if "latitude" in df.columns and "longitude" in df.columns:
                results = process_coords(df)
                st.success(f"Processed {len(results)} coordinates.")
                st.dataframe(results)
                st.download_button("Download Results as CSV", results.to_csv(index=False), "eligibility_results.csv")
            else:
                st.error("Please include 'latitude' and 'longitude' columns in your file.")
        except Exception as e:
            st.error(f"Error processing file: {e}")