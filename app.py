import tempfile

import streamlit as st
import pandas as pd
import geopandas as gpd
from huggingface_hub import hf_hub_download
import pydeck as pdk
import folium
from streamlit_folium import st_folium
import openpyxl
import requests
from io import BytesIO
from shapely import wkt
import numpy as np

import EZ_loaders

st.set_page_config(page_title="Zone Eligibility Check Tool", page_icon="🌲", layout="wide")
st.title("Zone Eligibility Check Tool")

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
selected_fips = None
if selected_states:
    selected_fips = [STATE_FIPS[state] for state in selected_states]
    try:
        tracts_gdf = load_states_tracts(selected_fips)
        st.success(f"Loaded {len(tracts_gdf)} census tracts from {len(selected_states)} state(s).")
    except Exception as e:
        st.error(f"Error loading census tracts: {e}")
        st.stop()

# Load USDA eligibility parquet
@st.cache_data(show_spinner="Loading USDA service...")
@EZ_loaders.retry_loader(max_attempts=3, delay=2)
def load_USDA_data():
    url = "https://rdgdwe.sc.egov.usda.gov/arcgis/rest/services/Eligibility/Eligibility/MapServer/2/query"
    # https://rdgdwe.sc.egov.usda.gov/arcgis/rest/services/Eligibility/RD_RHS_AK_OFFROAD/MapServer
    params = {
        "where": "1=1",
        "outFields": "*",
        "f": "geojson"
    }
    resp = requests.get(url, params=params)
    resp.raise_for_status()
    gdf = gpd.read_file(BytesIO(resp.content), driver="geojson")
    return gdf

# TOO MUCH FOR STREAMLIT TO HANDLE
# Load DOZ eligibility parquet
# @st.cache_data(show_spinner="Loading DOZ service...")
# def load_DOZ_data():
#     url = "https://cimsprodprep.cdfifund.gov/arcgis/rest/services/PN/CIMS3_PN_View/MapServer/43/query"
#     params = {
#         "where": "1=1",
#         "outFields": "*",
#         "f": "geojson"
#     }
#     headers = {
#         "User-Agent": "Mozilla/5.0 (compatible; MyApp/1.0; +https://cimsprodprep.cdfifund.gov/arcgis/rest/services/PN/CIMS3_PN_View/MapServer/43/query)"
#     }
#     resp = requests.get(url, params=params, headers=headers)
#     resp.raise_for_status()
#     gdf = gpd.read_file(BytesIO(resp.content), driver="geojson")
#
#     print(gdf.columns)
#     gdf.head()
#
#     # Index(['OBJECTID', 'GEOID10', 'STATE', 'COUNTY', 'TRACT', 'STUSAB',
#     #        'STATE_NAME', 'Shape__Area', 'Shape__Length', 'geometry'],
#     #       dtype='object')
#
#     return gdf

# Load eligibility flags CSV
@st.cache_data
def load_eligibility_data():
    # read docs if needed
    return pd.read_csv("eligibility_flags.csv", dtype={"GEOID": str})


usda_gdf = load_USDA_data()
eligibility_df = load_eligibility_data()

# Choose input method (Excel/CSV or Manual Input)
st.subheader("Coordinates Input")
method = st.radio("Choose coordinates input method:",
                  ["Upload Excel/CSV", "Enter coordinates manually (not functional yet)"],
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

    unmatched = joined[joined["GEOID"].isna()]
    if not unmatched.empty:
        st.warning(f"{len(unmatched)} coordinate(s) did not fall within any census tract. Check your coordinates and make sure you selected the correct states.")
        st.dataframe(unmatched[["latitude", "longitude"]])


    # Merge eligibility data
    results = pd.merge(joined, eligibility_df, on="GEOID", how="left")

    # USDA eligibility check: join with ineligible areas
    gdf_usda = gdf.to_crs(usda_gdf.crs)
    usda_join = gpd.sjoin(gdf_usda, usda_gdf, how="left", predicate="within")

    # If point joins with ineligible area, mark as not eligible
    results["USDA Eligible"] = usda_join.index_right.isna()
    results["USDA Eligible"] = results["USDA Eligible"].map({True: "Yes", False: "No"})

    fips_reversed = {v: k for k, v in STATE_FIPS.items()}
    results["State FIPS"] = results["GEOID"].str[:2]
    results["State"] = results["State FIPS"].map(fips_reversed)

    # Columns to be return regardless of selected states
    base_cols = ["latitude", "longitude", "GEOID", "State", "NMTC Eligibility", "Opportunity Zone", "USDA Eligible"]

    # Map of state fip codes to their Enterprise Zone loaders
    state_zone_loaders = {
        "08": [("CO Enterprise Zone", EZ_loaders.load_co_ez_data),
               ("CO Enhanced Rural Enterprise Zone", EZ_loaders.load_co_erez_data)],
        "12": [("FL Rural Area Opportunity Zone", EZ_loaders.load_fl_rao_data)],
        "15": [("HI Enterprise Zone", EZ_loaders.load_hi_ez_data)],
        "17": [("IL Enterprise Zone", EZ_loaders.load_il_ez_data)],
        "24": [("MD Enterprise Zone", EZ_loaders.load_md_ez_data)],
        # "29": [("MO Enhanced Enterprise Zone", EZ_loaders.load_mo_ez_data)],
        "31": [("NE Innovation Hub", EZ_loaders.load_ne_ihub_data),
               ("NE Enterprise Zone", EZ_loaders.load_ne_ez_data)],
        "48": [("TX Enterprise Zone", EZ_loaders.load_tx_ez_data)],
        "51": [("VA Enterprise Zone", EZ_loaders.load_va_ez_data)],
    }

    # Add EZ columns based on selected states
    for fip in selected_fips:
        if fip in state_zone_loaders:
            for col_name, loader_func in state_zone_loaders[fip]:
                try:
                    zone_gdf = loader_func()

                    if zone_gdf is not None:
                        gdf_zone = gdf.to_crs(zone_gdf.crs)
                        zone_join = gpd.sjoin(gdf_zone, zone_gdf, how="left", predicate="within")
                        in_zone = zone_join.index_right.isna().map({True: "No", False: "Yes"})

                        # N/A if coordinate is not in corresponding State
                        point_states = results["GEOID"].str[:2] # First 2 digits = state FIPS
                        results[col_name] = np.where(
                            point_states == fip,
                            in_zone, # Yes or No if point is in the same state
                            np.nan # N/A otherwise
                        )
                    else:
                        st.warning(f"{col_name} data is empty or could not be loaded")
                except Exception as e:
                    st.warning(f"Failed to load {col_name}: {e}")

    # Build state column list
    state_cols = [col_name
                  for fip in selected_fips
                  if fip in state_zone_loaders
                  for col_name, _ in state_zone_loaders[fip]]

    # Have to separately add FL Rural Job Tax Credit since it is a boolean based on GEOID
    if "12" in selected_fips:
        results["FL Rural Job Tax Credit Zone"] = results["GEOID"].apply(EZ_loaders.is_fl_rjtc).map({True: "Yes", False: "No"})
        state_cols.extend(["FL Rural Job Tax Credit Zone"])

    if "01" in selected_fips:
        results["AL Enterprise Zone"] = results["GEOID"].apply(EZ_loaders.is_al_ez).map({True: "Yes", False: "No"})
        state_cols.extend(["AL Enterprise Zone"])

    return results[base_cols + state_cols]

#def eligibility_polygons_gdf(tracts, eligibility):
    #joined = pd.merge(tracts, eligibility, on="GEOID", how="left")

    # Clean up
    #joined["GEOID"] = joined["GEOID"].astype(str).str.zfill(11)
    #joined = gpd.GeoDataFrame(joined, geometry="geometry", crs="EPSG:4326")
    #joined = joined[joined.geometry.notnull() & joined.geometry.is_valid & ~joined.geometry.is_empty]

    #return joined

results = None

# Excel/CSV Upload Method
if tracts_gdf is not None:
    if method == "Upload Excel/CSV":
        uploaded_file = st.file_uploader("Upload a file with 'latitude' and 'longitude' columns",
                                         type=["csv", "xlsx"])
        if uploaded_file is not None:
            try:
                df = pd.read_excel(uploaded_file) if uploaded_file.name.endswith(".xlsx") else pd.read_csv(uploaded_file)
                if "latitude" in df.columns and "longitude" in df.columns:
                    # Strip whitespace
                    df["latitude"] = df["latitude"].astype(str).str.strip()
                    df["longitude"] = df["longitude"].astype(str).str.strip()

                    # Convert to numeric -> invalids become NaN
                    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
                    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")

                    # Drop rows with invalid coordinates
                    df = df.dropna(subset=["latitude", "longitude"])

                    results = process_coords(df)
                    st.success(f"Processed {len(results)} coordinates.")
                    st.dataframe(results)
                    st.download_button("Download Results as CSV", results.to_csv(index=False), "eligibility_results.csv")
                else:
                    st.error("Please include 'latitude' and 'longitude' columns in your file.")
            except Exception as e:
                st.error(f"Error processing file: {e}")

#bruh

# Display the coordinates on a map
# if results is not None:

    # Create eligibility polygons
    # eligibility_polygons = eligibility_polygons_gdf(tracts_gdf, eligibility_df)

    # Merge in tract geometries
    # results_with_geom = pd.merge(results, tracts_gdf[["GEOID", "geometry"]], on="GEOID", how="left")

    # Convert to GeoDataFrame
    # Only re-wrap if it's not already a GeoDataFrame
    # if not isinstance(results_with_geom, gpd.GeoDataFrame):
        # results_gdf = gpd.GeoDataFrame(results_with_geom, geometry="geometry", crs="EPSG:4326")
    # else:
        # results_gdf = results_with_geom.to_crs(epsg=4326)

    # results_gdf = results_gdf[results_gdf.geometry.is_valid]
    # results_gdf = results_gdf[~results_gdf.geometry.is_empty]

    # eligibility_polygons = eligibility_polygons[eligibility_polygons.geometry.is_valid]
    # eligibility_polygons = eligibility_polygons[~eligibility_polygons.geometry.is_empty]

    # results_gdf["geometry"] = results_gdf["geometry"].simplify(tolerance=0.0001, preserve_topology=True)

    # Get center of bounding box
    # minx, miny, maxx, maxy = usda_gdf.total_bounds
    # center_lat = (miny + maxy) / 2
    # center_lon = (minx + maxx) / 2
    # #
    # # Create the map centered on your data
    # m = folium.Map(location=[center_lat, center_lon], zoom_start=7, tiles="CartoDB positron")

    # Function to assign colors
    # def get_color(status):
        # if status == "Eligible":
            # return "yellow"
        # elif status == "Not Eligible":
            # return "gray"
        # elif status in ["Severe Distress", "Non-Metropolitan"]:
            # return "red"  # light red
        # elif status in ["Deep Distress", "High Migration Rural County"]:
            # return "purple"
        # else:
            # return "white"


    # Replace NaNs with safe values
    # results_gdf = results_gdf.fillna("")
    # eligibility_polygons = eligibility_polygons.fillna("")

    # Create a simplified copy — DO NOT modify in place if you're using the original elsewhere
    # simplified_polygons = eligibility_polygons[["GEOID", "geometry", "NMTC_Eligibility"]].copy()
    # simplified_polygons["geometry"] = simplified_polygons["geometry"].simplify(0.001, preserve_topology=True)

    # Optional: drop any rows that were mangled or became invalid
    # simplified_polygons = simplified_polygons[simplified_polygons.geometry.is_valid & ~simplified_polygons.geometry.is_empty]

    # Add census tracts as shaded polygons
    # folium.GeoJson(
    #     tez_gdf, #simplified_polygons
    #     name = "Qualified OZs", #    name = "Census Tracts",
    #    # style_function=lambda feature: {
    #    #     "fillColor": get_color(feature["properties"].get("NMTC_Eligibility", None)),
    #    #     "color" : "black",
    #    #     "weight": 0.5,
    #    #     "fillOpacity": 0.7,
    #    # },
    #    # tooltip=folium.GeoJsonTooltip(fields=["GEOID", "NMTC_Eligibility"])
    # ).add_to(m)

    # for _, rows in results.iterrows():
    #     folium.Marker(
    #         location=[rows.latitude, rows.longitude],
    #         popup=rows.NAMELSAD,
    #         icon=folium.Icon(color="blue", icon="map-marker")
    #     ).add_to(m)
    #
    # #folium.Marker(
    # #    location=[results_gdf.iloc[0]["latitude"], results_gdf.iloc[0]["longitude"]],
    # #    popup="Test Marker"
    # #).add_to(m)
    #
    # Show map
    # st_data = st_folium(m, width=1000, height=700)
