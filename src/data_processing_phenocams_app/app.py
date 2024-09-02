import streamlit as st
import cv2
from sstc_core.sites.spectral import utils
from data_processing_phenocams_app.utils import session_state, get_records_by_year_and_day_of_year, update_flags
from data_processing_phenocams_app.components import side_menu_options, show_title, show_record, quality_flags_management
from sstc_core.sites.spectral.stations import get_stations_names_dict, get_station_platform_geolocation_point
from sstc_core.sites.spectral.data_products.qflags import compute_qflag
from sstc_core.sites.spectral.data_products import phenocams
import matplotlib.pyplot as plt
from datetime import datetime

st.set_page_config(layout="wide")

@st.cache_data()
def get_phenocams_flags_dict():    
    return  phenocams.get_default_phenocam_flags(flags_yaml_filepath= phenocams.config_flags_yaml_filepath)
    

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
    
    station_name = st.session_state.get('station_name')
    station_acronym = stations_dict[station_name]['station_acronym'] 
    
    phenocam_rois = station.phenocam_rois(
        platforms_type=platforms_type,
        platform_id=platform_id
        )
    
    rois_list = sorted(list(phenocam_rois.keys()))
    
    tab1, tab2, tab3 = st.tabs([ 'Phenocam data-prep', 'time series plots', 'Time Series table'] )
    ##
    with tab1:
            
        p1, _, p3 = st.columns([ 2,1,1] )
        
        with p1:
            show_title(year, _doy)


        
        doy = f'{_doy:03}'
        records = station.get_records_by_year_and_day_of_year(
            table_name=table_name, 
            year=year,
            day_of_year=doy,
            filters={"is_L1": True})

        
        if not records:
            st.error("No records found for the selected day of the year.")
            return
        
        rois_dict = {
                        record['catalog_guid']: {
                            f'L3_{roi_name}_has_snow_presence': record[f'L3_{roi_name}_has_snow_presence']  
                            for roi_name in phenocam_rois.keys()
                        } 
                        for k, record in records.items()
                    }
        
            

        images_name_and_guid = {records[k]["L0_name"]: k for k, v in records.items()}
        image_name = st.sidebar.radio(
            'Available Images', 
            options=images_name_and_guid.keys())
        catalog_guid = images_name_and_guid[image_name]
        session_state('catalog_guid', catalog_guid)
        record = records[catalog_guid]
            
        with p3:
            if st.button("Show DB Record"):
                show_record(record=record)    
            
        rois_flags_dict = utils.extract_keys_with_prefix(input_dict=record, starts_with='ROI_')   
        

        
        session_state('flags_dict', rois_flags_dict)
        
        p1.write(f'**Image Name:** {image_name}')
        
        latitude_dd, longitude_dd = get_station_platform_geolocation_point(
                station=station,
                platforms_type=platforms_type,
                platform_id=platform_id,
                )
        
        ############################################
            
        sun_position = utils.calculate_sun_position(
            datetime_str= record['creation_date'], 
            latitude_dd=latitude_dd, 
            longitude_dd=longitude_dd, 
            timezone_str='Europe/Stockholm')
        
        sun_elevation_angle = sun_position['sun_elevation_angle']
        sun_azimuth_angle = sun_position['sun_azimuth_angle'] 
        solar_elevation_class = utils.get_solar_elevation_class(sun_elevation=sun_elevation_angle)

        ################
        rois_sums_dict = phenocams.rois_mask_and_sum(image_path=record['catalog_filepath'], phenocam_rois=phenocam_rois)
        
        l2_data_prep = phenocams.convert_rois_sums_to_single_dict(rois_sums_dict=rois_sums_dict)
        
        if 'l3_results_dict' not in st.session_state:
            l3_results_dict ={} 
        
        with st.sidebar.expander(label='L2 dataprep', expanded=False):
            st.write(l2_data_prep)
        #################
        
        c1, c2 = st.columns([3, 1])
        with c2:
            st.markdown('')
            show_overlay_rois = st.toggle(
                label= f'Showing **{len(phenocam_rois)}** ROI(s)',
                value=True)
            
            if show_overlay_rois:
                image_obj = phenocams.overlay_polygons(
                    image_path= record['catalog_filepath'],
                    phenocam_rois=phenocam_rois,
                    show_names=True,
                    font_scale=2.0    
                )
            else:
                image_obj = record['catalog_filepath'] 
                

            
            with st.container(border=True):
                    
                has_snow_presence = st.toggle(
                    label='has snow presence', 
                    value= record.get('has_snow_presence', False))
                
                session_state('has_snow_presence', has_snow_presence)
                
            
                if has_snow_presence:
                            
                    rois_snow_cols = st.columns(len(rois_list))
                    for i, roi_name in enumerate(rois_list):
                        
                        with rois_snow_cols[i]:
                            roi_has_snow_presence =  records[catalog_guid][f'L3_{roi_name}_has_snow_presence'] 
                            snow_in_roi = st.checkbox(
                                label=roi_name,
                                value= roi_has_snow_presence,
                                label_visibility='visible',
                                key=f'{catalog_guid}_L3_{roi_name}_has_snow_presence'
                                )
                            rois_dict[catalog_guid][f'L3_{roi_name}_has_snow_presence'] = snow_in_roi
            
            #
            with c1:        
                st.image(image_obj, use_column_width='auto')

            #######        
            # QFLAG
            records_list = [ record for i, record in records.items()]
            r_list = [{'creation_date': record['creation_date']} for record in records_list]
            meantime_resolution = utils.calculate_mean_time_resolution(records_list=r_list)
            if len(r_list) > 1 and (meantime_resolution.get('hours',0) > 0 or meantime_resolution.get('minutes', 30)) > 30:
                default_temporal_resolution = False
            else:
                default_temporal_resolution = True
                 
            
            qflag_dict = compute_qflag(
                latitude_dd=latitude_dd,
                longitude_dd=longitude_dd,
                records_dict={catalog_guid:record},
                timezone_str= 'Europe/Stockholm',
                default_temporal_resolution=default_temporal_resolution,
                is_per_image=True,
                )
            
            updates = {} 
            updates['has_snow_presence'] = record['has_snow_presence'] = has_snow_presence
            updates['sun_elevation_angle'] = record['sun_elevation_angle'] = sun_elevation_angle
            updates['sun_azimuth_angle'] = record['sun_azimuth_angle'] = sun_azimuth_angle
            updates['solar_elevation_class'] = record['solar_elevation_class']  = solar_elevation_class
            updates["QFLAG_image_value"] = record["QFLAG_image_value"] = qflag_dict['QFLAG']
            updates["QFLAG_image_weight"] = record["QFLAG_image_weight"] = qflag_dict['weight']
            updates['default_temporal_resolution'] = record['default_temporal_resolution'] = qflag_dict['default_temporal_resolution']
            updates['meantime_resolution'] = record['meantime_resolution'] = f"{meantime_resolution['hours']}:{meantime_resolution['minutes']}:00"  
                    
            st.markdown(f'**sun azimuth angle**: {sun_azimuth_angle:.2f}') 
            sol1, sol2 = st.columns(2)
            with sol1:
                st.metric(label='sun elevation angle', value= f'{sun_elevation_angle:.2f}')
            with sol2:
                st.metric(label= 'solar class',  value=solar_elevation_class)
            
            
            m1, m2 = st.columns(2)
            with m1:
                st.write(f'**TIME RESOLUTION [HH:MM]**: {str(meantime_resolution["hours"]).zfill(2)}:{str(meantime_resolution["hours"]).zfill(2)}')
            # TODO: show the has flags isntead
            # swith m2:
            #    pass
                    
                #st.metric(label='QFLAG image weight', value=QFLAG_image['weight'])
            
            
            with st.container(border=True):
                    
                z1, z2 = st.columns(2)
                with z1:
                    st.checkbox(label='flags confirmed', value= record['flags_confirmed'], disabled=True )
                with z2:
                    if st.button('Confirm Flags'):
                        quality_flags_management(station, table_name, catalog_guid, record)

            
            
            with st.container(border=True):
                
                w1, w2 = st.columns(2)
                with w1:                
                    is_ready_for_products_use = st.checkbox('Ready for L2 & L3', value=record['is_ready_for_products_use'])
                    session_state('is_ready_for_products_use', is_ready_for_products_use)
                        
                        
                        
                with w2:
                    
                    confirm_ready = st.button(label='SAVE Record', key='is_ready_for_products_use_key')
                if confirm_ready:

                    updates['is_ready_for_products_use'] = is_ready_for_products_use
                    
                    
                    update_rois ={**updates,**rois_dict[catalog_guid],  **l2_data_prep}   
                    
                    is_saved = station.update_record_by_catalog_guid(
                        table_name=table_name,
                        catalog_guid=catalog_guid, 
                        updates=update_rois)
                    st.toast(f'updates saved: {is_saved}')
    
    with tab2:
                
        #r1, r2 = st.columns(2)
        #with r1:
        #    with st.expander(label='L2 Results'):
        #        l2_df = phenocams.create_l2_parameters_dataframe(data_dict=l2_results_dict, year=year)
        #        st.dataframe(l2_df)
        #with r2:
       
            
        apply_weights = st.toggle(label='Apply penalties for weighting', value=True)
        
        iflags_penalties_dict = get_phenocams_flags_dict()
        
        if not apply_weights:
            iflags_penalties_dict = {k:{'value': v['value'], 'penality_value': 0 }  for k, v in iflags_penalties_dict.items()}            
        
        
        records_dict = station.get_records_ready_for_products_by_year(
            table_name=table_name, 
            year=year,                    
            )
        
        
        minmax_dates_dict =  station.get_min_max_dates_with_filters(
            year=year,
            table_name=table_name            
            )
        
        session_state('minmax_dates_dict', minmax_dates_dict)
                                                
        l2_results_dict = phenocams.calculate_roi_weighted_means_and_stds_per_record(
            records_dict=records_dict,                        
            iflags_penalties_dict=iflags_penalties_dict,
            rois_list=rois_list,
            overwrite_weight=False,

        )
        
                            
        l3_results_dict = phenocams.calculate_roi_weighted_means_and_stds(
            records_dict=records_dict,                        
            iflags_penalties_dict=iflags_penalties_dict,
            rois_list=rois_list,
            latitude_dd=latitude_dd,
            longitude_dd=longitude_dd,
            overwrite_weight=False,
            )
        session_state('l3_results_dict', l3_results_dict)
        
        if st.session_state.get('l3_results_dict', False):
            
            l3_df = phenocams.create_l3_parameters_dataframe(data_dict=l3_results_dict, year=year)
            options_plot = list(l3_df.columns)
            index_plot = options_plot.index(st.session_state.get('selected_l3_field_to_plot', options_plot[0] ))
            selected_l3_field_to_plot = st.selectbox(
                label='Select parameter to plot', 
                options=options_plot,
                index=index_plot
                )
            
            session_state('l3_df', l3_df)
            session_state('selected_l3_field_to_plot', selected_l3_field_to_plot)
            
            selected_df = l3_df[selected_l3_field_to_plot]
            # Plot the data
            fig, ax = plt.subplots()
            ax.plot(selected_df.index, selected_df, label=selected_l3_field_to_plot)
            ax.scatter(selected_df.index, selected_df, label='Value', color='blue', s=10)  # s controls the size of the points
            ax.set_xlabel('Day of Year')
            ax.set_ylabel('Value')
            ax.set_title(selected_l3_field_to_plot) # 'Data by Day of Year')
            ax.grid(True)
            #ax.legend()

            # Display the plot in Streamlit
            st.pyplot(fig)
            #st.pyplot(selected_df)
    

        
    with tab3:
        l3_df = st.session_state.get('l3_df', None)
         
        if l3_df is not None:
            station_name = st.session_state.get(station_name)
            minmax_dates_dict = st.session_state.get('minmax_dates_dict',{})
            mindate = minmax_dates_dict['min'].replace(':', '').replace('-','').split(' ')[0] 
            maxdate = minmax_dates_dict['max'].replace(':', '').replace('-','').split(' ')[0] 
                       
        
            st.subheader(f'SITES-L3_ROI_TS-{station_acronym}-{platform_id}-{mindate}-{maxdate}')
            st.write(l3_df)
    
    
if __name__ == '__main__':

    run()

