import os
import streamlit as st
import cv2
from sstc_core.sites.spectral import utils
from data_processing_phenocams_app.utils import session_state
from data_processing_phenocams_app.components import side_menu_options, show_title, show_record, quality_flags_management
from sstc_core.sites.spectral.stations import get_stations_names_dict, get_station_platform_geolocation_point
from sstc_core.sites.spectral.data_products.qflags import compute_qflag
from sstc_core.sites.spectral.data_products import phenocams
from sstc_core.sites.spectral.utils import select_dataframe_columns_by_strings
import pandas as pd
from pathlib import Path
from sstc_core.sites.spectral import plots 

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
    

    
def plot_time_series_streamlit(
    df: pd.DataFrame, 
    title:str,    
    plot_options: dict = None, 
    width: int = 600, 
    height: int = 400, 
    interactive: bool = True,
    substrings: list = None,
    exclude_columns: list = ['QFLAG_value', 'QFLAG_default_temporal_resolution', 'QFLAG_is_per_image'],
    group_by: str = None,
    facet: bool = False,
    rois_list: list = None,
    show_legend: bool = True,
    legend_position: str = 'right', 
    ):
    
    """
    Streamlit app to plot a time series from a pandas DataFrame.

    Parameters:
    df (pd.DataFrame): DataFrame containing the data.
    """
    st.title("Time Series Plot")

    # Dropdown to select columns for plotting
    columns_to_plot = st.multiselect(
        "Select columns to plot",
        options=df.columns.drop('day_of_year'),
        help="Select one or more columns to plot"
    )
    
    #if plot_options is None:
        

    # Ensure that some columns are selected
    if columns_to_plot:
        st.write(f"Plotting: {', '.join(columns_to_plot)}")
        
        # Use the plot_time_series function to generate the chart
        chart = plots.plot_time_series_by_doy(
            df=df, 
            columns_to_plot=columns_to_plot, 
            title=title, 
            plot_options = plot_options, 
            width = width, 
            height = height, 
            interactive = interactive,
            substrings = substrings,
            exclude_columns = exclude_columns,
            group_by = group_by,
            facet = facet,
            rois_list = rois_list,
            show_legend = show_legend,
            legend_position = legend_position,
            )
        
        # Display the Altair chart using Streamlit
        st.altair_chart(chart, use_container_width=True)
    else:
        st.warning("Please select at least one column to plot.")        
    


 
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
    
    tab1, tab3 = st.tabs([ 'Phenocam data-prep',  'Time Series table'] )   #'time series plots'
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
        #session_state('catalog_guid', catalog_guid)
        record = records[catalog_guid]
            
        with p3:
            if st.button("Show DB Record"):
                show_record(record=record)    
            
        rois_flags_dict = utils.extract_keys_with_prefix(input_dict=record, starts_with='ROI_')   
        

        
        #session_state('flags_dict', rois_flags_dict)
        
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
                
                #session_state('has_snow_presence', has_snow_presence)
                
            
                _enable_all = st.session_state[station_name].get('enable_all', False) 
                if has_snow_presence:
                    
                    enable_all = st.checkbox(
                        label='enable all',
                        value= _enable_all
                        )
                    
                    
                    st.session_state[station_name]['enable_all'] = enable_all
                     
                            
                    rois_snow_cols = st.columns(len(rois_list))
                    for i, roi_name in enumerate(rois_list):
                        
                        with rois_snow_cols[i]:
                            roi_has_snow_presence =  records[catalog_guid][f'L3_{roi_name}_has_snow_presence'] 
                            snow_in_roi = st.checkbox(
                                label=roi_name,
                                value= roi_has_snow_presence if not _enable_all else True,
                                label_visibility='visible',
                                key=f'{catalog_guid}_L3_{roi_name}_has_snow_presence'
                                )
                            if not _enable_all:
                                rois_dict[catalog_guid][f'L3_{roi_name}_has_snow_presence'] = snow_in_roi
                            else:
                                rois_dict[catalog_guid][f'L3_{roi_name}_has_snow_presence'] = True
            
            #
            with c1:        
                st.image(image_obj, use_column_width='auto')

            #######        
            # QFLAG
            records_list = [ record for i, record in records.items()]
            r_list = [{'creation_date': record['creation_date']} for record in records_list]
            meantime_resolution = utils.calculate_mean_time_resolution(records_list=r_list)
            if len(r_list) > 1 and (meantime_resolution.get('hours',0) > 0 or meantime_resolution.get('minutes', 30) > 30):
                default_temporal_resolution = False
            else:
                default_temporal_resolution = True
            
            #session_state('meantime_resolution', meantime_resolution)
            #session_state('default_temporal_resolution', default_temporal_resolution)     
            
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
            updates['meantime_resolution'] = record['meantime_resolution'] = f"{str( meantime_resolution['hours']).zfill(2)}:{str(meantime_resolution['minutes']).zfill(2)}:00"  
                    
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
                    st.checkbox(label='iflags confirmed', value= record['iflags_confirmed'], disabled=True )
                with z2:
                    if st.button('Confirm Flags'):
                        quality_flags_management(station, table_name, catalog_guid, record)

            
            
            with st.container(border=True):
                
                w1, w2 = st.columns(2)
                with w1:                
                    is_ready_for_products_use = st.checkbox('Ready for L2 & L3', value=record['is_ready_for_products_use'])
                    #session_state('is_ready_for_products_use', is_ready_for_products_use)
                        
                        
                        
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

        
    with tab3:
        apply_weights = st.toggle(label='Apply penalties for weighting', value=True)
    
        iflags_penalties_dict = get_phenocams_flags_dict()
        
        if not apply_weights:
            iflags_penalties_dict = {k:{'value': v['value'], 'penality_value': 0 }  for k, v in iflags_penalties_dict.items()}            
        
        
        
        #doy_dict_with_records_list = station.get_records_ready_for_products_by_year(
        #    table_name=table_name, 
        #    year=year,                    
        #    )
        
        
        
        minmax_dates_dict =  station.get_min_max_dates_with_filters(
            year=year,
            table_name=table_name            
            )
        
        #session_state('minmax_dates_dict', minmax_dates_dict)
        
        #########################
        filtered_records = station.get_filtered_records(table_name=table_name, filters={"is_ready_for_products_use": True, "year":year})
        available_days_list = sorted({ record['day_of_year']: None for record in filtered_records})
        doy_dict_with_records_list = {doy: [ record for record in filtered_records if record['day_of_year'] == str(doy)] for doy in available_days_list }
        
        l2_results_dict = phenocams.calculate_roi_weighted_means_and_stds_per_record(        
            doy_dict_with_records_list=doy_dict_with_records_list,                       
            iflags_penalties_dict = iflags_penalties_dict,
            rois_list=rois_list,
            overwrite_weight=False,
        )
        
        skip_iflags_list = [
                'iflag_sunny', 
                'iflag_cloudy',
                'iflag_full_overcast', 
                'iflag_initial_green_up',
                'iflag_initial_peek_greeness',
                'iflag_initial_lead_discoloration',
                'iflag_initial_leaf_fall', 
                ]
        
        #----------------------------
        ## SNOW PRESENCE

        rois_dict = {}
        QFLAG_dict = {}

        timezone_str = 'Europe/Stockholm'
        is_per_image = False 
        default_temporal_resolution = False


        for k, _records in doy_dict_with_records_list.items():
            rois_dict[k] = {}
            QFLAG_dict[k] = {}
            for roi_name in rois_list:
                rois_dict[k][roi_name]  = {}
                ##########
                datetime_list = [record['creation_date'] for record in _records]
            
                mean_datetime_str = utils.mean_datetime_str(datetime_list=datetime_list)
                sun_position = utils.calculate_sun_position(
                    datetime_str=mean_datetime_str, 
                    latitude_dd=latitude_dd, 
                    longitude_dd=longitude_dd, 
                    timezone_str=timezone_str
                )
                
                sun_elevation_angle = sun_position['sun_elevation_angle']
                solar_elevation_class = utils.get_solar_elevation_class(sun_elevation=sun_elevation_angle)
            
                n_records = len(_records)
                    
                if (n_records < (3 if default_temporal_resolution else 2)) and (solar_elevation_class == 1):
                    QFLAG = 11
                    weight = 0.1 if not is_per_image else 0.5
                    
                elif (n_records < (3 if default_temporal_resolution else 2)) and (solar_elevation_class == 2):
                    QFLAG = 12
                    weight = 0.75 if not is_per_image else 0.75
                        
                elif (n_records < (3 if default_temporal_resolution else 2)) and (solar_elevation_class == 3):
                    QFLAG = 13
                    weight = 0.75 if not is_per_image else 1.0
                        
                elif ((n_records >= (3 if default_temporal_resolution else 2)) and 
                    (n_records < (6 if default_temporal_resolution else 4))) and (solar_elevation_class == 1):
                    QFLAG = 21
                    weight = 0.5
                    
                elif ((n_records >= (3 if default_temporal_resolution else 2)) and 
                    (n_records < (6 if default_temporal_resolution else 4))) and (solar_elevation_class == 2):
                    QFLAG = 22
                    weight = 0.75
            
                elif ((n_records >= (3 if default_temporal_resolution else 2)) and 
                    (n_records < (6 if default_temporal_resolution else 4))) and (solar_elevation_class == 3):
                    QFLAG = 23
                    weight = 1
            
                elif (n_records >= (6 if default_temporal_resolution else 4)) and (solar_elevation_class == 1):
                    QFLAG = 31
                    weight = 0.75
                    
                elif (n_records >= (6 if default_temporal_resolution else 4)) and (solar_elevation_class == 2):
                    QFLAG = 32
                    weight = 1.0
                    
                elif (n_records >= (6 if default_temporal_resolution else 4)) and (solar_elevation_class == 3):
                    QFLAG = 33
                    weight = 1
                    
                else:
                    raise ValueError("Invalid input combination for n_records and solar_elevation_class")
            




                #################################
                QFLAG_dict[k][roi_name] = {'QFLAG_value': QFLAG,
                                    'QFLAG_weight': weight,
                                    'QFLAG_default_temporal_resolution': default_temporal_resolution,
                                    'QFLAG_is_per_image': is_per_image
                }
                
                for record in _records:
                    rois_flags_dict = utils.extract_keys_with_prefix(input_dict=record, starts_with=roi_name)
                    has_flags = any([ v for k, v in rois_flags_dict.items()])
                    rois_dict[k][roi_name][record['catalog_guid']]= {
                                'has_flags' : has_flags,
                                'has_snow_precence': record['has_snow_presence'],                        
                                f'L3_{roi_name}_has_snow_presence': record[f'L3_{roi_name}_has_snow_presence']                          
                            }        
        
        # ---------------------------
        
        results = {}

        for doy in available_days_list:
            if doy not in results:
                results[doy] = {}
                records = doy_dict_with_records_list[doy]
            for roi in rois_list:
                results[doy][roi]= {
                    **phenocams.process_records_for_roi(
                        iflags_penalties_dict= iflags_penalties_dict,
                        skip_iflags_list=skip_iflags_list,
                        overwrite_weight=False,
                        rois_list=rois_list, 
                        records=records,
                        roi=roi), 
                    **QFLAG_dict[doy][roi]}
        
        
        ##########################
        # Determine the number of days in the year (considering leap years)
        days_in_year = 366 if (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)) else 365    
        # Initialize an empty dictionary to store data
        roi_ts_dict = {day: {} for day in range(1, days_in_year + 1)}

        # Iterate through the data dictionary
        for doy, rois in results.items():
            doy = int(doy)
            for roi in rois.keys():
                parameters = rois[roi]
                for param_name, param_value in parameters.items():            
                    # Store the parameter value in the data dictionary
                    if 'QFLAG_' in param_name and param_name not in ['QFLAG_weight']:
                        column_name = param_name
                        roi_ts_dict[doy][param_name] = param_value
                    elif param_name not in ['weights_used', 'QFLAG_weight', 'iflag_disable_for_processing']:
                        column_name = f"L3_{roi}_{param_name}"
                        roi_ts_dict[doy][column_name] = param_value
                if roi_ts_dict[doy][f"L3_{roi}_GCC_value"]== 0:
                    for field in parameters.keys():
                        if 'QFLAG_' in field and field not in ['QFLAG_weight']:
                            # column_name = field
                            pass
                        elif field not in ['weights_used', 'QFLAG_weight', 'iflag_disable_for_processing']:
                            column_name = f"L3_{roi}_{field}"
                        #
                        roi_ts_dict[doy][column_name] = None
                        #    
        
        # Create a DataFrame from the dictionary
        df = pd.DataFrame.from_dict(roi_ts_dict, orient='index')
        # Sort the DataFrame by the index (days of the year)
        if len(df)>0:
            
            df.sort_index(inplace=True)
            df['year'] = str(year)
            df['day_of_year'] = df.index
            xcols = [
                'year',
                'day_of_year',
                'QFLAG_value',
                'QFLAG_default_temporal_resolution',
                'QFLAG_is_per_image']
            columns = [c for c in df.columns if c not in xcols]
            ordered_columns = xcols + columns


            # Fill missing values with pd.NA (a proper placeholder for missing data)
            df = df[ordered_columns].reindex(range(1, days_in_year + 1)).fillna(pd.NA)
            df['year'] = str(year)
            df['day_of_year'] = df.index
            # Replace numpy.NA with None
            df = df.replace({pd.NA: None})
            
            # -------------------
            mindate = minmax_dates_dict['min'].replace(':', '').replace('-','').split(' ')[0] 
            maxdate = minmax_dates_dict['max'].replace(':', '').replace('-','').split(' ')[0] 
            backup_dirpath = 'aurora02_dirpath'
            local_dirpath = station.platforms[platforms_type][platform_id]['backups'][backup_dirpath]
            products_dirpath = os.path.join(local_dirpath, "products")
            l3_dirpath = Path(products_dirpath) / 'L3_ROI_TS' / str(year)
            os.makedirs(l3_dirpath, exist_ok=True)
            l3_filename = f'SITES_ROI-TS_{station_acronym.replace('_', '-')}_{platform_id.replace('_', '-')}_{mindate}-{maxdate}_L3_DAILY.csv'
            l3_filepath = l3_dirpath / l3_filename
            
            # TODO: add a button to save 
            
            
            st.subheader(l3_filename)

            if st.toggle(label='show level 3 results', value=True):
                with st.expander(label=f'{year} level 3 results'):
                    with st.spinner(text='preparing time series'):
                        st.dataframe(df)
                filtered_df = select_dataframe_columns_by_strings(
                    
                    df=df, 
                    substrings =['mean_red', 'mean_blue', 'mean_green', 'year'],
                    exclude_columns =['QFLAG_value', 'QFLAG_default_temporal_resolution', 'QFLAG_is_per_image'])
                
                plot_options = plots.assign_hue_colors_to_columns(
                    rois_list=rois_list, 
                    columns_list = filtered_df.columns.to_list(),                
                    )
                
                plot_options ={key:{'color': f'{value}'} for key, value in plot_options.items()}  
                
                plot_time_series_streamlit(
                    df=filtered_df, 
                    title=str(year),                
                    interactive=True,               
                    #plot_options=plot_options,
                    show_legend=True,
                    #facet=True, 
                    #group_by='year',
                    rois_list=rois_list,
                    )
        
    
if __name__ == '__main__':

    run()

