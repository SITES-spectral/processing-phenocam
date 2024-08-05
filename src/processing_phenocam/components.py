import os
import streamlit as st
import pandas as pd
from typing import Tuple
from sstc_core.sites.spectral.stations import Station, stations_names
from sstc_core.sites.spectral.config import catalog_filepaths
from sstc_core.sites.spectral.utils import day_of_year_to_month_day, extract_keys_with_prefix, have_values_changed
from processing_phenocam.utils import session_state, update_flags


def side_menu_options() -> Tuple[Station, str, int, int]:
    """
    Display side menu options for selecting station, platform type, platform ID, year, and day of year.

    Returns:
        Tuple[Station, str, int, int]: The selected station, table name, year, and day of year.
    """
    stations_dict = stations_names()
    
    sc1, sc2 = st.sidebar.columns(2)
    
    with sc1:
        station_name = st.selectbox('**Stations**', options=stations_dict)
        db_filepath = catalog_filepaths.get(station_name, None)
        
        if not db_filepath:
            st.sidebar.error("Database file path not found.")
            return None, None, None, None
        
        station = Station(db_dirpath=os.path.dirname(db_filepath), station_name=station_name)
        session_state('station_name', station_name)
    
    with sc2:
        if station:
            platforms = station.platforms
            platforms_type = st.selectbox('**Platforms Type**', options=platforms.keys())
            session_state('platforms_type', platforms_type)
    
    if platforms_type:
        platform_id = st.sidebar.selectbox('**Platform ID**', options=platforms[platforms_type])
        session_state('platform_id', platform_id)
        
        table_name = f"{station.platforms[platforms_type][platform_id]['platform_type']}_{station.platforms[platforms_type][platform_id]['location_id']}_{platform_id}"
        records_count = station.get_record_count(table_name=table_name)
        session_state('table_name', table_name)
        session_state('records_count', records_count)
        
        tc1, tc2 = st.sidebar.columns([3,1])
        
        with tc1:
            st.text_input('Table Name', value=table_name)
        with tc2:
            st.metric('Number of Records', value=records_count)
        
        years = station.get_unique_years(table_name=table_name)
        d1c, d2c = st.sidebar.columns(2)
        
        with d1c:
            year = st.selectbox('Year', options=years)
            session_state('year', year)
        
        _doys = station.get_day_of_year_min_max(table_name=table_name, year=year)
        min_doy = _doys['min']
        max_doy = _doys['max']
        
        with d2c:
            _doy = st.number_input('Day of Year', min_value=min_doy, max_value=max_doy, step=1)
        
        return station, table_name, year, _doy

    return None, None, None, None

def show_title(year: int, _doy: int):
    """
    Display the title with the month and day for a given year and day of the year.

    Args:
        year (int): The year.
        _doy (int): The day of the year.
    """
    month_day_string = day_of_year_to_month_day(year, _doy)
    st.subheader(f'{month_day_string} | DOY: {_doy}')

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
    flags_dict = extract_keys_with_prefix(input_dict=record, starts_with='flag_')
    df = pd.DataFrame(list(flags_dict.items()), columns=['Flag', 'Status'])
    df['Status'] = df['Status'].apply(lambda x: True if x else False if x is not None else False)
    edited_df = st.data_editor(df, hide_index=True, num_rows='fixed', use_container_width=True)

    if st.button('Confirm'):
        updated_flags_dict = dict(zip(edited_df['Flag'], edited_df['Status']))
        updated_flags = have_values_changed(flags_dict, updated_flags_dict)
        updated_flags['flags_confirmed'] = True

        if updated_flags:
            has_updated = update_flags(station, table_name, catalog_guid, updated_flags)
            if has_updated:
                st.toast('Flags values updated and saved')
                session_state('flags_dict', updated_flags_dict)
            else:
                st.warning('Flags not updated')
