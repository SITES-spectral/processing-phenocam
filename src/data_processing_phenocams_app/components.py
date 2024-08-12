import os
import streamlit as st
import pandas as pd
from typing import Tuple
from sstc_core.sites.spectral.stations import Station
from sstc_core.sites.spectral.config import catalog_filepaths
from data_processing_phenocams_app import utils as app_utils
from sstc_core.sites.spectral.data_products import phenocams
from sstc_core.sites.spectral import utils



def side_menu_options(stations_names_list:list, is_platform_table: True) -> Tuple[Station, str, int, int]:
    """
    Display side menu options for selecting station, platform type, platform ID, year, and day of year.

    Returns:
        Tuple[Station, str, int, int]: The selected station, table name, year, and day of year.
    """
    
    
    sc1, sc2 = st.sidebar.columns(2)
        
    try:
        idx_station = stations_names_list.index(st.session_state.get('station_name', 0))
    except:
        idx_station = 0 
    
    with sc1:
        station_name = st.selectbox(
            '**Stations**', 
            options=stations_names_list,
            index=idx_station 
            )
        
        db_filepath = catalog_filepaths.get(station_name, None)
        
        if not db_filepath:
            st.sidebar.error("Database file path not found.")
            return None, None, None, None
        
        station = Station(db_dirpath=os.path.dirname(db_filepath), station_name=station_name)
        app_utils.session_state('station_name', station_name)
    
    with sc2:
        if station:
            platforms_types_dict = station.platforms
            platforms_types = sorted(list(platforms_types_dict.keys()))
            try:
                idx_platforms_type = platforms_types.index(st.session_state.get('platforms_type', 0))
            except:
                idx_platforms_type = 0
                 
            platforms_type = st.selectbox(
                '**Platforms Type**', 
                options=platforms_types,
                index=idx_platforms_type
                )
            app_utils.session_state('platforms_type', platforms_type)
    
    if platforms_type:
        
        platform_ids = sorted(list(platforms_types_dict[platforms_type].keys()))
        try:
            idx_platform_id = platform_ids.index(st.session_state.get('platform_id', 0))
        except:
            idx_platform_id = 0
             
        
        platform_id = st.sidebar.selectbox(
            '**Platform ID**',
            options=platform_ids, 
            index=idx_platform_id)
        
        app_utils.session_state('platform_id', platform_id)
        
        if is_platform_table:
            table_name = f"{station.platforms[platforms_type][platform_id]['platform_type']}_{station.platforms[platforms_type][platform_id]['location_id']}_{platform_id}"
        else:
            #TODO: create new table. Now it defaults to platforms table
            table_name = f"{station.platforms[platforms_type][platform_id]['platform_type']}_{station.platforms[platforms_type][platform_id]['location_id']}_{platform_id}"
            
        records_count = station.get_record_count(table_name=table_name)
        app_utils.session_state('table_name', table_name)
        app_utils.session_state('records_count', records_count)
        
        tc1, tc2 = st.sidebar.columns([3,1])
        
        with tc1:
            st.text_input('Table Name', value=table_name)
        with tc2:
            st.metric('Number of Records', value=records_count)
        
        years = sorted(station.get_unique_years(table_name=table_name), reverse=True)
        d1c, d2c = st.sidebar.columns(2)
        
        try:
            idx_year = years.index(st.session_state.get('year', 0))
        except:
            idx_year= 0
        
        with d1c:
            
            sorted(years, reverse=True)
            year = st.selectbox('Year', options=years, index=idx_year)
            app_utils.session_state('year', year)
        
        _doys = station.get_day_of_year_min_max(table_name=table_name, year=year)
        min_doy = _doys['min']
        max_doy = _doys['max']
        
        doys = sorted(list(range(min_doy, max_doy+1, 1 )))
        with d2c:
            try:
                value = doys.index(st.session_state.get('doy', min_doy))
                if value < min_doy:
                    value = min_doy
            except:
                value = min_doy
                
            _doy = st.number_input(
                label='Day of Year', 
                min_value=min_doy, 
                max_value=max_doy, 
                step=1,
                value=value
                 
                )
            
            app_utils.session_state('doy', _doy)
        
        return station, table_name, platforms_type, platform_id,  year, _doy

    return None, None, None, None, None, None

def show_title(year: int, _doy: int):
    """
    Display the title with the month and day for a given year and day of the year.

    Args:
        year (int): The year.
        _doy (int): The day of the year.
    """
    month_day_string = utils.day_of_year_to_month_day(year, _doy)
    st.subheader(f'{year},  {month_day_string} | DOY: {_doy:03}')

@st.dialog('Record')
def show_record(record: dict):
    """
    Display the database record.

    Args:
        record (dict): The record to display.
    """
    st.write(record)

@st.dialog('PhenoCam quality flags')
def quality_flags_management(station: Station, table_name: str, catalog_guid: str, record: dict):
    """
    Manage quality flags.

    Args:
        station (Station): The station instance.
        table_name (str): The table name.
        catalog_guid (str): The catalog GUID.
        record (dict): The record to manage flags for.
    """
    flags_dict = utils.extract_keys_with_prefix(input_dict=record, starts_with='flag_')
    df = pd.DataFrame(list(flags_dict.items()), columns=['Flag', 'Status'])
    df['Status'] = df['Status'].apply(lambda x: True if x else False if x is not None else False)
    edited_df = st.data_editor(df, hide_index=True, num_rows='fixed', use_container_width=True)

    app_utils.session_state('flags_confirmed', record['flags_confirmed'])
    
    if st.button('Confirm'):
        updated_flags_dict = dict(zip(edited_df['Flag'], edited_df['Status']))
        updated_flags = utils.have_values_changed(flags_dict, updated_flags_dict)
        updated_flags['flags_confirmed'] = True

        app_utils.session_state('flags_confirmed', updated_flags['flags_confirmed'])
    
        if updated_flags:
            has_updated = app_utils.update_flags(station, table_name, catalog_guid, updated_flags)
            if has_updated:
                st.toast('Flags values updated and saved')
                app_utils.session_state('flags_dict', updated_flags_dict)                
            else:
                st.warning('Flags not updated')


def load_rois(station, platforms_type, platform_id):
    # Load the ROIs for the selected platform
    return station.phenocam_rois(platform_id=platform_id, platforms_type=platforms_type)

def get_records_by_year_and_day(station, table_name, year, doy):
    # Fetch records based on the year and day of the year
    return station.get_records_by_year_and_day_of_year(table_name, year, doy)

def initialize_rois_dict(records, phenocam_rois):
    # Initialize the ROIs dictionary with default snow presence flags
    return {
        record['catalog_guid']: {
            f'L2_{roi_name}_has_snow_presence': record[f'L2_{roi_name}_has_snow_presence']  
            for roi_name in phenocam_rois.keys()
        } 
        for record in records.values()
    }

def show_record(record):
    # Display the selected record in the app
    st.write(record)


def get_user_inputs(st, phenocam_rois, record, catalog_guid):
    # Handle user inputs such as snow presence and ROI overlay toggle
    show_overlay_rois = st.toggle('Show ROI Overlays', value=True)
    has_snow_presence = st.toggle('Has Snow Presence', value=record['has_snow_presence'])
    
    # Handle per-ROI snow presence toggles
    for roi_name in phenocam_rois.keys():
        st.session_state[f'{catalog_guid}_L2_{roi_name}_has_snow_presence'] = st.checkbox(
            roi_name, value=record[f'L2_{roi_name}_has_snow_presence']
        )
    
    return show_overlay_rois, has_snow_presence


def prepare_updates(record, sun_position, QFLAG_image, has_snow_presence):
    # Prepare updates to be saved to the database
    return {
        'has_snow_presence': has_snow_presence,
        'sun_elevation_angle': sun_position['sun_elevation_angle'],
        'sun_azimuth_angle': sun_position['sun_azimuth_angle'],
        'solar_elevation_class': sun_position['solar_elevation_class'],
        'QFLAG_image': QFLAG_image
    }

def display_solar_metrics(st, sun_elevation_angle, solar_elevation_class, QFLAG_image):
    # Display solar metrics and quality flag in the UI
    st.metric('Sun Elevation Angle', f'{sun_elevation_angle:.2f}')
    st.metric('Solar Elevation Class', solar_elevation_class)
    st.metric('QFLAG Image', QFLAG_image)

def save_updates(st, station, table_name, catalog_guid, updates, rois_dict, l2_data_prep):
    # Save updates to the database
    updates = {**updates, **rois_dict[catalog_guid], **l2_data_prep}
    station.update_record_by_catalog_guid(table_name, catalog_guid, updates)

def get_image_with_rois(st, record, phenocam_rois, show_overlay_rois):
    # Get the image with optional ROI overlays
    if show_overlay_rois:
        return phenocams.overlay_polygons(record['catalog_filepath'], phenocam_rois, show_names=True, font_scale=2.0)
    return record['catalog_filepath']