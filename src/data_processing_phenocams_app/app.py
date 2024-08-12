import streamlit as st
from sstc_core.sites.spectral import utils
from data_processing_phenocams_app import utils as app_utils
from data_processing_phenocams_app import components
from sstc_core.sites.spectral.stations import get_stations_names_dict, get_station_platform_geolocation_point
from sstc_core.sites.spectral.data_products import phenocams
from sstc_core.sites.spectral.data_products import qflags

st.set_page_config(layout="wide")


 # run.py in the main app module

def run():
    """
    Main function to run the Streamlit app, providing an interactive interface for exploring and updating PhenoCam data.
    """
    stations_dict = get_stations_names_dict()
    stations_names_list = sorted(list(stations_dict.keys()))

    station, table_name, platforms_type, platform_id, year, _doy = components.side_menu_options(
        stations_names_list=stations_names_list, 
        is_platform_table=True
    )
    
    if not all([station, table_name, year, _doy]):
        st.error("Please select all required options.")
        return
    
    phenocam_rois = components.load_rois(station, platforms_type, platform_id)
    display_ui(year, _doy, phenocam_rois, station, table_name, platforms_type, platform_id)


def display_ui(year, doy, phenocam_rois, station, table_name, platforms_type, platform_id):
    """
    Display the user interface components for the selected year, day of year, and platform.
    """
    p1, _, p3 = st.columns([2, 1, 1])
    with p1:
        components.show_title(year, doy)

    records = components.get_records_by_year_and_day(station, table_name, year, doy)

    if not records:
        st.error("No records found for the selected day of the year.")
        return

    rois_dict = components.initialize_rois_dict(records, phenocam_rois)
    images_name_and_guid = {records[k]["L0_name"]: k for k, v in records.items()}
    
    image_name = st.sidebar.radio('Available Images', options=images_name_and_guid.keys())
    catalog_guid = images_name_and_guid[image_name]
    app_utils.session_state('catalog_guid', catalog_guid)
    record = records[catalog_guid]

    with p3:
        if st.button("Show DB Record"):
            components.show_record(record)

    flags_dict = utils.extract_keys_with_prefix(record, 'flag_')
    app_utils.session_state('flags_dict', flags_dict)

    p1.write(f'**Image Name:** {image_name}')

    latitude_dd, longitude_dd = get_station_platform_geolocation_point(
        station=station,
        platforms_type=platforms_type,
        platform_id=platform_id 
        )
    
    app_utils.session_state('latitude_dd', latitude_dd)
    app_utils.session_state('longitude_dd', longitude_dd)
    
        
    sun_position = utils.calculate_sun_position(
        datetime_str=record['creation_date'], 
        latitude_dd=latitude_dd, 
        longitude_dd=longitude_dd, 
        timezone_str='Europe/Stockholm'
    )

    process_image_data(st, record, sun_position, rois_dict, station, table_name, phenocam_rois, catalog_guid)


def process_image_data(st, record, sun_position, rois_dict, station, table_name, phenocam_rois, catalog_guid):
    """
    Process image data and interactively update quality flags and other attributes.
    """
    sun_elevation_angle = sun_position['sun_elevation_angle']
    sun_azimuth_angle = sun_position['sun_azimuth_angle']
    solar_elevation_class = utils.get_solar_elevation_class(sun_elevation_angle)

    rois_sums_dict = phenocams.rois_mask_and_sum(record['catalog_filepath'], phenocam_rois)
    l2_data_prep = phenocams.convert_rois_sums_to_single_dict(rois_sums_dict)

    c1, c2 = st.columns([3, 1])
    with c2:
        show_overlay_rois, has_snow_presence = components.get_user_inputs(st, phenocam_rois, record, catalog_guid)
        
        QFLAG_image = qflags.compute_qflag(
            latitude_dd=st.session_state['latitude_dd'],
            longitude_dd= st.session_state['longitude_dd'],
            records_dict={record['catalog_guid']: record},
            has_snow_presence=has_snow_presence,
            default_temporal_resolution=True,
            timezone_str='Europe/Stockholm'                                                       
            )
        
        updates = components.prepare_updates(record, sun_position, QFLAG_image, has_snow_presence)
        
        st.markdown(f'**Sun Azimuth Angle:** {sun_azimuth_angle:.2f}')
        components.display_solar_metrics(st, sun_elevation_angle, solar_elevation_class, QFLAG_image)

        if st.button('Confirm/Update Flags'):
            components.quality_flags_management(station, table_name, catalog_guid, record)

        is_ready_for_products_use = st.checkbox('Selected for Products Use', value=record['is_ready_for_products_use'])
        confirm_ready = st.button(label='Confirm', key='is_ready_for_products_use_key')
        
        if confirm_ready:
            updates['is_ready_for_products_use'] = is_ready_for_products_use
            components.save_updates(st, station, table_name, catalog_guid, updates, rois_dict, l2_data_prep)

    with c1:
        image_obj = components.get_image_with_rois(st, record, phenocam_rois, show_overlay_rois)
        st.image(image_obj, use_column_width='auto')



if __name__ == '__main__':

    run()

