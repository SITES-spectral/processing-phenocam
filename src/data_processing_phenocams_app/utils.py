import streamlit as st
from typing import Any
from sstc_core.sites.spectral.stations import Station
import pandas as pd


def session_state(key: str, value: Any):
    """
    Set a session state value.

    Args:
        key (str): The key for the session state.
        value (Any): The value to be set.
    """
    st.session_state[key] = value

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


def build_flags_dataframe(flags_dict:dict)->pd.DataFrame:
    """
    Converts a dictionary of ROI flags into a DataFrame where rows represent flag names 
    and columns represent different ROIs.
    
    Parameters
    ----------
    flags_dict : dict
        A dictionary where keys are in the format 'ROI_XX_iflag_name' and values are the corresponding flag values.
    
    Returns
    -------
    pd.DataFrame
        A DataFrame with the flag names as rows and ROIs as columns.
    
    Examples
    --------
    >>> flags_dict = {
    ...     'ROI_01_iflag_disable_for_processing': False,
    ...     'ROI_02_iflag_disable_for_processing': True,
    ...     'ROI_01_iflag_shadows': False,
    ...     'ROI_02_iflag_shadows': True,
    ... }
    >>> df = build_flags_dataframe(flags_dict)
    >>> print(df)
                         ROI_01  ROI_02
    flag_disable_for_processing   False    True
    flag_shadows                  False    True
    """
    
    structured_data = {}
    
    for key, value in flags_dict.items():
        # Split the key into ROI identifier and flag name
        roi, flag_name = key.split('_iflag_', 1)
        
        # If the flag_name is not yet in the structured_data dictionary, initialize it
        if flag_name not in structured_data:
            structured_data[flag_name] = {}
        
        # Add the value to the corresponding ROI column
        structured_data[flag_name][roi] = bool(value)
    
    # Convert the structured data into a DataFrame
    df = pd.DataFrame.from_dict(structured_data, orient='index')
    
    # Sort the DataFrame columns to ensure consistent order
    df = df.sort_index(axis=1)
    
    return df

def dataframe_to_flags_dict(df, original_dict):
    """
    Converts a DataFrame of edited flags back into a dictionary, including only the flags that have been edited.
    
    Parameters
    ----------
    df : pd.DataFrame
        A DataFrame where rows are flag names and columns are ROIs, representing the edited flag values.
    
    original_dict : dict
        The original dictionary of ROI flags before any edits were made.
    
    Returns
    -------
    dict
        A dictionary containing only the flags that have been edited, with keys in the format 'ROI_XX_iflag_name'.
    
    Examples
    --------
    >>> original_dict = {
    ...     'ROI_01_iflag_disable_for_processing': False,
    ...     'ROI_02_iflag_disable_for_processing': True,
    ...     'ROI_01_iflag_shadows': False,
    ...     'ROI_02_iflag_shadows': True,
    ... }
    >>> edited_df = pd.DataFrame({
    ...     'ROI_01': [True, False],
    ...     'ROI_02': [True, False]
    ... }, index=['flag_disable_for_processing', 'flag_shadows'])
    >>> new_flags_dict = dataframe_to_flags_dict(edited_df, original_dict)
    >>> print(new_flags_dict)
    {'ROI_01_iflag_disable_for_processing': True}
    """
    
    edited_flags = {}
    
    # Iterate over the DataFrame to compare each value with the original dictionary
    for flag_name in df.index:
        for roi in df.columns:
            dict_key = f"{roi}_iflag_{flag_name}"
            
            # Compare the DataFrame value with the original dictionary value
            if dict_key in original_dict and bool(df.at[flag_name, roi]) != bool(original_dict[dict_key]):
                # Only include the key-value pair if the value has changed
                edited_flags[dict_key] = bool(df.at[flag_name, roi])
    
    return edited_flags