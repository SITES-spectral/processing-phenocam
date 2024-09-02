import os
import streamlit as st
import pandas as pd
from typing import Tuple
from sstc_core.sites.spectral.stations import Station
from sstc_core.sites.spectral.config import catalog_filepaths
from sstc_core.sites.spectral.utils import day_of_year_to_month_day, extract_keys_with_prefix, have_values_changed
from data_processing_phenocams_app.utils import session_state, update_flags, build_flags_dataframe, dataframe_to_flags_dict



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
        #station_acronym = stations_names_list[station_name]['station_acronym'] 
        #session_state['station_acronym', station_acronym] 
        
        db_filepath = catalog_filepaths.get(station_name, None)
        
        if not db_filepath:
            st.sidebar.error("Database file path not found.")
            return None, None, None, None
        
        station = Station(db_dirpath=os.path.dirname(db_filepath), station_name=station_name)
        session_state('station_name', station_name)
    
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
            session_state('platforms_type', platforms_type)
    
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
        
        session_state('platform_id', platform_id)
        
        if is_platform_table:
            table_name = f"{station.platforms[platforms_type][platform_id]['platform_type']}_{station.platforms[platforms_type][platform_id]['location_id']}_{platform_id}"
        else:
            #TODO: create new table. Now it defaults to platforms table
            table_name = f"{station.platforms[platforms_type][platform_id]['platform_type']}_{station.platforms[platforms_type][platform_id]['location_id']}_{platform_id}"
            
        records_count = station.get_record_count(table_name=table_name)
        
        session_state('table_name', table_name)
        session_state('records_count', records_count)
        
        st.sidebar.text_input('Table Name', value=table_name, disabled=False)
        
        tc1, tc2, tc3 = st.sidebar.columns(3)
        
        with tc1:
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
            session_state('year', year)
        
        with tc2:
            count_L1_records = station.count_records_by_year_with_filters(
                table_name=table_name,
                year=year,
                filters={'is_L1':True} 
                 )
            st.metric('L1 records', value=count_L1_records)
            
        with tc3:
            count_record_is_ready = station.count_records_by_year_with_filters(
                table_name=table_name,
                year=year,
                filters={'is_ready_for_products_use':True} 
                 )
            st.metric('records ready', value=count_record_is_ready)
            
        
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
            
            session_state('doy', _doy)
        
        return station, table_name, platforms_type, platform_id,  year, _doy

    return None, None, None, None, None, None

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
    flags_dict = extract_keys_with_prefix(input_dict=record, starts_with='ROI_')
    
    df = build_flags_dataframe(flags_dict=flags_dict)
    #df = pd.DataFrame(list(flags_dict.items()), columns=['Flag', 'Status'])
    #df['Status'] = df['Status'].apply(lambda x: True if x else False if x is not None else False)
    edited_df = st.data_editor(df, num_rows='fixed', use_container_width=True)

    session_state('flags_confirmed', record['flags_confirmed'])
    
    updated_flags=  dataframe_to_flags_dict(pd.DataFrame(edited_df), original_dict=flags_dict)
    
    if st.button('Confirm'):
        #updated_flags_dict = dict(zip(edited_df['Flag'], edited_df['Status']))
        #updated_flags = have_values_changed(flags_dict, updated_flags_dict)
                    
        updated_flags['flags_confirmed'] = True    

        session_state('flags_confirmed', updated_flags['flags_confirmed'])
    
        if len(updated_flags) >= 1:
            flags_confirmed = station.update_record_by_catalog_guid(table_name=table_name, catalog_guid=catalog_guid, updates=updated_flags)
            #has_updated = update_flags(station, table_name, catalog_guid, updated_flags)
            if flags_confirmed:
                st.toast('Flags values confirmed and saved')
                session_state('flags_dict', updated_flags)                
            else:
                st.warning('Flags not updated')
                
    st.write(updated_flags)

