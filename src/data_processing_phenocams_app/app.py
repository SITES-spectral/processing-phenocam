import streamlit as st
import cv2
from sstc_core.sites.spectral import utils
from data_processing_phenocams_app.utils import session_state, get_records_by_year_and_day_of_year, update_flags
from data_processing_phenocams_app.components import side_menu_options, show_title, show_record, quality_flags_management
from sstc_core.sites.spectral.utils import extract_keys_with_prefix   # solar_illumination_conditions
from sstc_core.sites.spectral import image_quality
from sstc_core.sites.spectral.stations import get_stations_names_dict, Station  # get_station_platform_geolocation_point
from sstc_core.sites.spectral.data_products.qflags import get_solar_elevation_class, compute_qflag



st.set_page_config(layout="wide")


def open_image(image_path: str):
    """
    Opens an image using OpenCV and returns the image object.
    
    Parameters:
        image_path (str): The path to the image file.
        
    Returns:
        image: The image object loaded by OpenCV.
    """
    # Load the image from the specified file
    image = cv2.imread(image_path)
    
    # Check if the image was successfully loaded
    if image is None:
        print(f"Error: Unable to open image file at {image_path}")
        return None
    
    return image


def detect_snow_in_image(image_path: str, snow_detection_function, **kwargs) -> bool:
    """
    Opens an image, uses a provided function to detect snow with optional parameters, and closes the image window.
    
    Parameters:
        image_path (str): The path to the image file.
        snow_detection_function (function): A function that takes an image object as input and returns a bool.
        **kwargs: Optional parameters to pass to the snow_detection_function.
        
    Returns:
        bool: True if snow is detected, False otherwise.
    """
    # Open the image
    image = open_image(image_path)
    
    # If the image couldn't be loaded, return False
    if image is None:
        return False
    
    # Use the provided snow detection function with optional parameters
    snow_detected = snow_detection_function(image, **kwargs)
    
    # Close all OpenCV windows
    cv2.destroyAllWindows()
    



def get_station_platform_geolocation_point(station: Station, platforms_type: str, platform_id: str) -> tuple:
    """
    Retrieves the geolocation (latitude and longitude) of a specific platform for a given station.

    Parameters:
        station (Station): An instance of the Station class that contains metadata about the station and its platforms.
        platforms_type (str): The type of platform (e.g., 'PhenoCams', 'UAVs', 'FixedSensors', 'Satellites').
        platform_id (str): The identifier for the specific platform.

    Returns:
        tuple: A tuple containing the latitude and longitude of the platform in decimal degrees, in the format (latitude_dd, longitude_dd).

    Example:
        ```python
        # Assuming you have an instance of Station
        station = Station(db_dirpath="/path/to/db/dir", station_name="StationName")

        # Retrieve the geolocation for a specific platform
        platforms_type = 'PhenoCams'
        platform_id = 'P_BTH_1'
        latitude_dd, longitude_dd = get_station_platform_geolocation_point(station, platforms_type, platform_id)

        print(f"Latitude: {latitude_dd}, Longitude: {longitude_dd}")
        ```

    Raises:
        KeyError: If the specified platform type or platform ID does not exist in the station's metadata, or if the geolocation information is incomplete.

    Note:
        This function assumes that the geolocation information is available in the station's metadata under the specified platform type and platform ID. 
        The geolocation should be stored in the format:
            station.platforms[platforms_type][platform_id]['geolocation']['point']['latitude_dd']
            station.platforms[platforms_type][platform_id]['geolocation']['point']['longitude_dd']
    """
    latitude_dd = station.platforms[platforms_type][platform_id]['geolocation']['point']['latitude_dd']
    longitude_dd = station.platforms[platforms_type][platform_id]['geolocation']['point']['longitude_dd']
    return latitude_dd, longitude_dd



def solar_illumination_conditions(
    latitude_dd:float,
    longitude_dd:float,
    record:dict,
    timezone_str: str ='Europe/Stockholm' ):
    
    creation_date = record['creation_date'] 
    sun_position = utils.calculate_sun_position(
        datetime_str= creation_date,
        latitude_dd=latitude_dd, 
        longitude_dd=longitude_dd, 
        timezone_str=timezone_str)
    
    sun_elevation_angle = sun_position['sun_elevation_angle']
    sun_azimuth_angle = sun_position['sun_azimuth_angle']  
    
    
    
    solar_elevation_class = get_solar_elevation_class(sun_elevation=sun_elevation_angle)
    
    return {
        'sun_elevation_angle': sun_elevation_angle,
        'sun_azimuth_angle': sun_azimuth_angle,
        'solar_elevation_class': solar_elevation_class
        } 


def run():
    """
    Main function to run the Streamlit app.
    """
    stations_dict = get_stations_names_dict()
    stations_names_list = sorted(list(stations_dict.keys()))
    
    station, table_name, platforms_type, platform_id,  year, _doy = side_menu_options( stations_names_list=stations_names_list, is_platform_table = True)
    if not all([station, table_name, year, _doy]):
        st.error("Please select all required options.")
        return

    show_title(year, _doy)
    doy = f'{_doy:03}'
    records = get_records_by_year_and_day_of_year(station, table_name, year, doy)

    if not records:
        st.error("No records found for the selected day of the year.")
        return

    images_name_and_guid = {records[k]["L0_name"]: k for k, v in records.items()}
    image_name = st.sidebar.radio('Available Images', options=images_name_and_guid.keys())
    catalog_guid = images_name_and_guid[image_name]
    session_state('catalog_guid', catalog_guid)
    record = records[catalog_guid]
    
    
    flags_dict = extract_keys_with_prefix(input_dict=record, starts_with='flag_')
    session_state('flags_dict', flags_dict)

    t1, t2 = st.columns([2, 1])
    with t1:
        st.write(f'**Image Name:** {image_name}')
        if st.button("Show DB Record"):
            show_record(record=record)
        
    with t2:
        
        if st.button(label='overlay ROIs'):
            rois = station.platforms[platforms_type][platform_id]['phenocam_rois']  
            st.write(rois)
        
        latitude_dd, longitude_dd = get_station_platform_geolocation_point(
            station=station,
            platforms_type=platforms_type,
            platform_id=platform_id,
            )
        solar_conditions = solar_illumination_conditions(
            latitude_dd=latitude_dd,
            longitude_dd=longitude_dd,
            record=record, 
            timezone_str='Europe/Stockholm')
    
        sun_elevation_angle = solar_conditions['sun_elevation_angle'] 
        sun_azimuth_angle = solar_conditions['sun_azimuth_angle'] 
        solar_elevation_class = solar_conditions['solar_elevation_class'] 
        
        


    c1, c2 = st.columns([3, 1])
    with c2:
        
        has_snow_presence = st.toggle(
            label='has snow presence', 
            value= st.session_state.get(
                'has_snow_presence',
                False))
        
        session_state('has_snow_presence', has_snow_presence)
  
        
        QFLAG_image = compute_qflag(
            latitude_dd=latitude_dd,
            longitude_dd=longitude_dd,
            has_snow_presence=has_snow_presence,
            records_dict={catalog_guid:record},
            timezone_str= 'Europe/Stockholm'
            )
        
        updates = {} 
        updates['has_snow_presence'] = record['has_snow_presence'] = has_snow_presence
        updates['sun_elevation_angle'] = record['sun_elevation_angle'] = sun_elevation_angle
        updates['sun_azimuth_angle'] = record['sun_azimuth_angle'] = sun_azimuth_angle
        updates['solar_elevation_class'] = record['solar_elevation_class']  = solar_elevation_class
        updates["QFLAG_image"] = record["QFLAG_image"] = QFLAG_image
        

        st.markdown(f'**sun azimuth angle**: {sun_azimuth_angle:.2f}') 
        sol1, sol2 = st.columns(2)
        with sol1:
            st.metric(label='sun elevation angle', value= f'{sun_elevation_angle:.2f}')
        with sol2:
            st.metric(label= 'solar class',  value=solar_elevation_class)
        
        
        m1, m2 = st.columns(2)
        with m1:
            st.metric(label='QFLAG image', value=QFLAG_image)
        with m2:
                
            weights = image_quality.load_weights_from_yaml(station.phenocam_quality_weights_filepath)
            normalized_quality_index, quality_index_weights_version = image_quality.calculate_normalized_quality_index(
                quality_flags_dict=st.session_state['flags_dict'], weights=weights)
            st.metric(label='normalized quality index', value=f'{normalized_quality_index:.2f}')

        if st.button('Confirm/Update Flags'):
           
            quality_flags_management(station, table_name, catalog_guid, record)

        
        is_ready_for_products_use = st.checkbox('Selected for Products Use', value=record['is_ready_for_products_use'])
        confirm_ready = st.button(label='Confirm', key='is_ready_for_products_use_key')
        if confirm_ready:
            updates['normalized_quality_index'] = normalized_quality_index
            updates['is_ready_for_products_use'] = is_ready_for_products_use
            is_saved = station.update_record_by_catalog_guid(
                table_name=table_name,
                catalog_guid=catalog_guid, 
                updates=updates)
            st.toast(f'updates saved: {is_saved}')
                

    with c1:
        st.image(record["catalog_filepath"], use_column_width='auto')

if __name__ == '__main__':

    run()

