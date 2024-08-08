import streamlit as st
from typing import Any
from sstc_core.sites.spectral.stations import Station


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
