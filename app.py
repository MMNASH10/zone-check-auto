import streamlit as st
import pandas as pd
import geopandas as gpd
import os
from huggingface_hub import hf_hub_download
import openpyxl

st.set_page_config(page_title="Eligibility Lookup Tool", page_icon="🌲", layout="wide")
st.title("Census Tract Eligibility Lookup Tool")

STATE_FIPS = {
    "Alabama": "01", "Alaska": "02", "American Samoa": "60", "Arizona": "04", "Arkansas": "05",
    "California": "06", "Colorado": "08", "Connecticut": "09", "Delaware": "10", "District of Columbia": "11",
    "Florida": "12", "Georgia": "13", "Guam": "66", "Hawaii": "15", "Idaho": "16",
    "Illinois": "17", "Indiana": "18", "Iowa": "19", "Kansas": "20",
    "Kentucky": "21", "Louisiana": "22", "Maine": "23", "Maryland": "24", "Massachusetts": "25",
    "Michigan": "26", "Minnesota": "27", "Mississippi": "28", "Missouri": "29",
    "Montana": "30", "Nebraska": "31", "Nevada": "32", "New Hampshire": "33",
    "New Jersey": "34", "New Mexico": "35", "New York": "36", "North Carolina": "37",
    "North Dakota": "38", "North Mariana Islands": "69", "Ohio": "39", "Oklahoma": "40", "Oregon": "41",
    "Pennsylvania": "42", "Puerto Rico": "72", "Rhode Island": "44", "South Carolina": "45", "South Dakota": "46", "Tennessee": "47",
    "Texas": "48", "Utah": "49", "Vermont": "50", "Virgin Islands": "78", "Virginia": "51", "Washington": "53",
    "West Virginia": "54", "Wisconsin": "55", "Wyoming": "56",
}

# prompt user to select states
selected_states = st.multiselect(
    "Select the states you want to check:",
    options = list(STATE_FIPS.keys()),
)


# Load census tract parquet from DropBox
#@st.cache_data(show_spinner="Downloading and extracting geospatial data...")
#def load_parquet_from_huggingface():
 #   parquet_path =  hf_hub_download(
  #      repo_id = "MMNASH10/my-parquet-dataset",
   #     filename = "national_tracts_2020.parquet",
    #    repo_type = "dataset"
    #)
    #return gpd.read_parquet(parquet_path)

# Load selected states' files
@st.cache_data(show_spinner="Loading geospatial data...")
def load_states_tracts(fips_codes):
    gdf_list = []
    for fips in fips_codes:
        parquet_path = hf_hub_download(
            repo_id = "MMNASH10/my-parquet-dataset",
            filename = f"tl_2024_{fips}_tract.parquet",
            repo_type = "dataset",
        )
        gdf = gpd.read_parquet(parquet_path)
        gdf_list.append(gdf)
    return pd.concat(gdf_list).reset_index(drop=True)

# Load tracts only if states are selected
tracts_gdf = None
if selected_states:
    selected_fips = [STATE_FIPS[state] for state in selected_states]
    try:
        tracts_gdf = load_states_tracts(selected_fips)
        st.success(f"Loaded {len(tracts_gdf)} census tracts from {len(selected_states)} state(s).")
    except Exception as e:
        st.error(f"Error loading census tracts: {e}")
        st.stop()
        

# Load eligibility flags CSV
@st.cache_data
def load_eligibility_data():
    # read docs if needed
    return pd.read_csv("eligibility_flags.csv", dtype={"GEOID": str})

eligibility_df = load_eligibility_data()

# Choose input method (Excel/CSV or Manual Input)
st.subheader("Coordinates Input")
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
    # convert gdf to crs 4269
    gdf = gdf.to_crs(tracts_gdf.crs)
    # Spatial join with census tracts
    joined = gpd.sjoin(gdf, tracts_gdf, how="left", predicate="within")
    # Merge eligibility data
    result = pd.merge(joined, eligibility_df, on="GEOID", how="left")
    # Select output columns (NAMELSAD???)
    return result[["latitude", "longitude", "GEOID", "NAMELSAD", "NMTC_Eligibility"]]

# Excel/CSV Upload Method
if tracts_gdf is not None:
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