import streamlit as st
import os
import pandas as pd
from typing import Any, Tuple
from sstc_core.sites.spectral.stations import Station, stations_names
from sstc_core.sites.spectral.config import catalog_filepaths
from sstc_core.sites.spectral.utils import day_of_year_to_month_day, extract_keys_with_prefix, have_values_changed
from sstc_core.sites.spectral import image_quality
from datetime import datetime, timedelta


st.set_page_config(layout="wide")




def session_state(key: str, value: Any):
    """
    Set a session state value.

    Args:
        key (str): The key for the session state.
        value (Any): The value to be set.
    """
    st.session_state[key] = value

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

@st.cache_data()
def get_days_of_year(yearly_records: dict) -> list:
    """
    Get a sorted list of days of the year from yearly records.

    Args:
        yearly_records (dict): Yearly records dictionary.

    Returns:
        list: Sorted list of days of the year.
    """
    return sorted([int(r) for r in yearly_records.keys()], reverse=True)



def display_flags_with_data_editor(flags_dict: dict) -> dict:
    """
    Displays the quality flags dictionary using Streamlit's data_editor with checkboxes.

    Args:
        flags_dict (dict): The dictionary containing quality flags.

    Returns:
        dict: The updated dictionary after user interaction.
    """
    df = pd.DataFrame(list(flags_dict.items()), columns=['Flag', 'Status'])
    df['Status'] = df['Status'].apply(lambda x: True if x else False if x is not None else False)
    edited_df = st.data_editor(df, hide_index=True, num_rows='fixed', use_container_width=True)
    return dict(zip(edited_df['Flag'], edited_df['Status']))

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

def get_records_by_year_and_day_of_year(station: Station, table_name: str, year: int, day_of_year: str) -> dict:
    """
    Get records by year and day of year.

    Args:
        station (Station): The station instance.
        table_name (str): The table name.
        year (int): The year.
        day_of_year (str): The day of the year.

    Returns:
        dict: Records dictionary.
    """
    return station.get_records_by_year_and_day_of_year(table_name=table_name, year=year, day_of_year=day_of_year)


def update_flags(station: Station, table_name: str, catalog_guid: str, update_dict: dict) -> bool:
    """
    Update flags in the database.

    Args:
        station (Station): The station instance.
        table_name (str): The table name.
        catalog_guid (str): The catalog GUID.
        update_dict (dict): Dictionary with updated flags.

    Returns:
        bool: Flag indicating if the update was successful.
    """
    return station.update_record_by_catalog_guid(table_name=table_name, catalog_guid=catalog_guid, updates=update_dict)

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

def run():
    """
    Main function to run the Streamlit app.
    """
    station, table_name, year, _doy = side_menu_options()
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
    record = records[catalog_guid]
    flags_dict = extract_keys_with_prefix(input_dict=record, starts_with='flag_')
    session_state('flags_dict', flags_dict)

    t1, t2 = st.columns([2, 1])
    with t1:
        st.write(f'**Image Name:** {image_name}')
    with t2:
        if st.button("Show DB Record"):
            show_record(record=record)

    c1, c2 = st.columns([3, 1])
    with c2:
        weights = image_quality.load_weights_from_yaml(station.phenocam_quality_weights_filepath)
        normalized_quality_index, quality_index_weights_version = image_quality.calculate_normalized_quality_index(
            quality_flags_dict=st.session_state['flags_dict'], weights=weights)
        st.metric(label='Quality Index', value=f'{normalized_quality_index:.2f}')

        if st.button('Confirm/Update Flags'):
            quality_flags_management(station, table_name, catalog_guid, record)

        with st.form(key='is_ready_for_products_use_form'):
            is_ready_for_products_use = st.checkbox('Selected for Products Use', value=record['is_ready_for_products_use'])
            confirm_ready = st.form_submit_button(label='Confirm')
            if confirm_ready:
                station.update_is_ready_for_products_use(table_name=table_name, catalog_guid=catalog_guid, is_ready_for_products_use=is_ready_for_products_use)
                station.update_record_by_catalog_guid(table_name=table_name, catalog_guid=catalog_guid, updates={'normalized_quality_index': normalized_quality_index})

    with c1:
        st.image(record["catalog_filepath"], use_column_width='auto')

if __name__ == '__main__':
    run()
    st.write()
