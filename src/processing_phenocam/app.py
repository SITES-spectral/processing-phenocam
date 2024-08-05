import streamlit as st
from processing_phenocam.utils import session_state, get_records_by_year_and_day_of_year, update_flags
from processing_phenocam.components import side_menu_options, show_title, show_record, quality_flags_management
from sstc_core.sites.spectral.utils import extract_keys_with_prefix
from sstc_core.sites.spectral import image_quality

st.set_page_config(layout="wide")



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

