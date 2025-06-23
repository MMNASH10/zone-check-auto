import streamlit as st
import pandas as pd
import geopandas as gpd
from huggingface_hub import hf_hub_download
import pydeck as pdk
import folium
from streamlit_folium import st_folium
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
    # Merge eligibility data
    result = pd.merge(joined, eligibility_df, on="GEOID", how="left")
    # Select output columns (NAMELSAD???)
    return result[["latitude", "longitude", "GEOID", "NAMELSAD", "NMTC_Eligibility", "Opportunity_Zone"]]

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
                    results = process_coords(df)
                    st.success(f"Processed {len(results)} coordinates.")
                    st.dataframe(results)
                    st.download_button("Download Results as CSV", results.to_csv(index=False), "eligibility_results.csv")
                else:
                    st.error("Please include 'latitude' and 'longitude' columns in your file.")
            except Exception as e:
                st.error(f"Error processing file: {e}")


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
    # minx, miny, maxx, maxy = eligibility_polygons.total_bounds
    # center_lat = (miny + maxy) / 2
    # center_lon = (minx + maxx) / 2

    # Create the map centered on your data
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
    #folium.GeoJson(
    #    simplified_polygons,
    #    name = "Census Tracts",
    #    style_function=lambda feature: {
    #        "fillColor": get_color(feature["properties"].get("NMTC_Eligibility", None)),
    #        "color" : "black",
    #        "weight": 0.5,
    #        "fillOpacity": 0.7,
    #    },
    #    tooltip=folium.GeoJsonTooltip(fields=["GEOID", "NMTC_Eligibility"])
    #).add_to(m)

    #folium.Marker(
    #    location=[results_gdf.iloc[0]["latitude"], results_gdf.iloc[0]["longitude"]],
    #    popup="Test Marker"
    #).add_to(m)

    # Show map
    # st_data = st_folium(m, width=1000, height=700)
