# -*- coding: utf-8 -*-
###############################################################################
# RVE_Builder_UDFRPs.py
# -----------------------------------------------------------------------------
# Kernel module of the "RVE Builder (UDFRPs)" Abaqus plugin.
# Implements the operations triggered from each tab of the GUI dialog
# (RVE_Builder_UDFRPsDB):
#   * CreateRVE     — generate the RVE geometry (Monte-Carlo / RSE / CSV)
#   * MeshControl   — assign mesh seeds, element types and partitioning
#   * Material      — set fiber / matrix materials and section assignments
#   * Void          — insert voids in the matrix (random or controlled)
#   * Interface     — insert a zero-thickness cohesive seam (COH3D8) at the
#                     fiber/matrix interface (built inline: see Interface() and
#                     insert_cohesive_seam())
#   * Analysis      — dispatch to the appropriate PBC_UDFRP_* analyzer for
#                     elastic/CTE, viscoelastic, elastoplastic or thermal-
#                     conductivity homogenization
###############################################################################

#Import Abaqus-related (Python) Object files ================================== 
from abaqus import * 
from abaqusConstants import * 
from sketch import *
from material import createMaterialFromDataString
from collections import deque
import time
import os
import csv
import math
import random
import sympy as sp
import shutil
import __main__ 
import section 
import regionToolset 
import displayGroupMdbToolset as dgm 
import step 
import interaction 
import load 
import mesh 
import job 
import visualization 
import xyPlot 
import displayGroupOdbToolset as dgo 
import connectorBehavior
import re
import sys
import importlib
import glob
import numpy as np
import subprocess


###############################################################################
# Constants and helpers for the Analysis tab (ported from RVE_Builder_fillers).
# - Celsius validation, temperature sweep loop, defensive output naming.
# - ELASTOPLASTIC_LOAD_DEFINITIONS / _BIAXIAL_OPTIONS are the catalogue of
#   uniaxial / biaxial cases the GUI exposes.
###############################################################################
EPSILON = 1.0e-12
ABSOLUTE_ZERO_C = -273.15
SAFE_ANALYSIS_PATH_LENGTH = 240

ELASTOPLASTIC_LOAD_DEFINITIONS = (
    ('Strain11', 'epsilon_x', 'epUseStrain11', 'epStrainX', 'E11'),
    ('Strain22', 'epsilon_y', 'epUseStrain22', 'epStrainY', 'E22'),
    ('Strain33', 'epsilon_z', 'epUseStrain33', 'epStrainZ', 'E33'),
    ('Shear12',  'gamma_xy',  'epUseShear12',  'epShearXY', 'G12'),
    ('Shear13',  'gamma_zx',  'epUseShear13',  'epShearZX', 'G13'),
    ('Shear23',  'gamma_yz',  'epUseShear23',  'epShearYZ', 'G23'),
)

ELASTOPLASTIC_BIAXIAL_OPTIONS = (
    ('Strain11-Strain22', 'Strain11', 'Strain22'),
    ('Strain11-Strain33', 'Strain11', 'Strain33'),
    ('Strain11-Shear12',  'Strain11', 'Shear12'),
    ('Strain11-Shear13',  'Strain11', 'Shear13'),
    ('Strain11-Shear23',  'Strain11', 'Shear23'),
    ('Strain22-Strain33', 'Strain22', 'Strain33'),
    ('Strain22-Shear12',  'Strain22', 'Shear12'),
    ('Strain22-Shear13',  'Strain22', 'Shear13'),
    ('Strain22-Shear23',  'Strain22', 'Shear23'),
    ('Strain33-Shear12',  'Strain33', 'Shear12'),
    ('Strain33-Shear13',  'Strain33', 'Shear13'),
    ('Strain33-Shear23',  'Strain33', 'Shear23'),
    ('Shear12-Shear13',   'Shear12',  'Shear13'),
    ('Shear12-Shear23',   'Shear12',  'Shear23'),
    ('Shear13-Shear23',   'Shear13',  'Shear23'),
)


def parse_temperature_points_input(temperature_points_text):
    """Accept a list/tuple, or a comma-separated Celsius string, return a list of floats."""
    if temperature_points_text is None:
        return []
    if isinstance(temperature_points_text, (list, tuple)):
        return [float(value) for value in temperature_points_text]
    text_value = str(temperature_points_text).strip()
    if text_value == '':
        return []
    text_value = text_value.replace(u'，', ',')  # Chinese comma
    out = []
    for item in text_value.split(','):
        item = item.strip()
        if item == '':
            continue
        out.append(float(item))
    return out


def show_analysis_warning(title, message):
    """Pop a Windows message box when possible; always print to console."""
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, message, title, 0x30 | 0x0)
    except Exception:
        pass
    print('{}: {}'.format(title, message))


def validate_celsius_temperature_value(value, context_label):
    """Reject values below absolute zero."""
    temperature_value = float(value)
    if temperature_value < (ABSOLUTE_ZERO_C - EPSILON):
        raise ValueError('{} cannot be lower than -273.15 C.'.format(context_label))
    return temperature_value


def validate_celsius_temperature_points(values, context_label):
    validated = []
    for index, value in enumerate(values):
        validated.append(validate_celsius_temperature_value(value, '{} #{}'.format(context_label, index + 1)))
    return validated


def format_temperature_file_label(temperature_value):
    """Build a filesystem-safe label such as Temp_025 or Temp_m050p5."""
    if temperature_value is None:
        return ''
    numeric_value = float(temperature_value)
    sign_prefix = 'm' if numeric_value < 0.0 else ''
    absolute_text = ('{:.6f}'.format(abs(numeric_value))).rstrip('0').rstrip('.')
    if absolute_text == '':
        absolute_text = '0'
    if '.' in absolute_text:
        integer_part, fractional_part = absolute_text.split('.', 1)
        return 'Temp_{}{}p{}'.format(sign_prefix, integer_part.zfill(3), fractional_part)
    return 'Temp_{}{}'.format(sign_prefix, absolute_text.zfill(3))


def format_temperature_range_file_label(start_temp_c, end_temp_c):
    start_label = format_temperature_file_label(start_temp_c)
    end_label = format_temperature_file_label(end_temp_c)
    if start_label == '' and end_label == '':
        return ''
    return '{}_to_{}'.format(start_label, end_label)


def sanitize_case_label(label_text):
    text_value = str(label_text or '').strip()
    if text_value == '':
        return 'Case'
    sanitized = []
    for char in text_value:
        if char.isalnum() or char in ('_', '-'):
            sanitized.append(char)
        else:
            sanitized.append('_')
    sanitized_text = ''.join(sanitized)
    while '__' in sanitized_text:
        sanitized_text = sanitized_text.replace('__', '_')
    return sanitized_text.strip('_') or 'Case'


def format_elastoplastic_load_value_label(value):
    numeric_value = float(value)
    sign_prefix = 'm' if numeric_value < 0.0 else ''
    absolute_text = ('{:.6f}'.format(abs(numeric_value))).rstrip('0').rstrip('.')
    if absolute_text == '':
        absolute_text = '0'
    return '{}{}'.format(sign_prefix, absolute_text.replace('.', 'p'))


def parse_elastoplastic_uniaxial_values(raw_value, load_label):
    text_value = str(raw_value).strip().replace(u'，', ',')
    if text_value == '':
        text_value = '0.0'
    values = []
    for item in text_value.split(','):
        item = item.strip()
        if item == '':
            continue
        values.append(float(item))
    if not values:
        values = [0.0]
    is_normal_load = load_label in ('Strain11', 'Strain22', 'Strain33')
    if is_normal_load:
        if len(values) > 2:
            raise ValueError('{} accepts at most two values, for example 0.1,-0.2.'.format(load_label))
    elif len(values) > 1:
        raise ValueError('{} accepts only one value.'.format(load_label))
    return values


def build_analysis_timestamp():
    return time.strftime('%Y%m%d_%H%M%S')


def ensure_output_path_is_safe(root_dir, subdirectory_name, sample_file_name):
    """Refuse paths longer than 240 chars (a common Abaqus failure mode on Windows)."""
    if subdirectory_name:
        absolute_path = os.path.abspath(os.path.join(root_dir, subdirectory_name, sample_file_name))
    else:
        absolute_path = os.path.abspath(os.path.join(root_dir, sample_file_name))
    if len(absolute_path) > SAFE_ANALYSIS_PATH_LENGTH:
        raise ValueError(
            'Planned output path is too long ({} characters). Please shorten the working directory path before running the analysis.\n{}'.format(
                len(absolute_path), absolute_path
            )
        )
    return absolute_path


def build_case_output_subdirectory(model_name, analysis_name, case_label, temperature_value, timestamp_text):
    name_parts = [sanitize_case_label(model_name), sanitize_case_label(analysis_name), sanitize_case_label(case_label)]
    temperature_label = format_temperature_file_label(temperature_value)
    if temperature_label != '':
        name_parts.append(temperature_label)
    name_parts.append(timestamp_text)
    return '_'.join(name_parts)


def run_callable_in_directory(work_directory, func, *args, **kwargs):
    """Run func inside work_directory, returning to cwd afterwards."""
    if work_directory is None:
        return func(*args, **kwargs)
    original_directory = os.getcwd()
    if not os.path.exists(work_directory):
        os.makedirs(work_directory)
    os.chdir(work_directory)
    try:
        return func(*args, **kwargs)
    finally:
        os.chdir(original_directory)


def write_single_row_csv(csv_path, fieldnames, row_data):
    with open(csv_path, 'w') as file_obj:
        writer = csv.DictWriter(file_obj, fieldnames=fieldnames, lineterminator='\n')
        writer.writeheader()
        writer.writerow(row_data)


def write_temperature_sweep_results(csv_path, fieldnames, rows):
    with open(csv_path, 'w') as file_obj:
        writer = csv.DictWriter(file_obj, fieldnames=fieldnames, lineterminator='\n')
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def read_easycopy_results(file_path, key_names):
    if not os.path.exists(file_path):
        raise IOError('Result file was not found: {}'.format(file_path))
    with open(file_path, 'r') as file_obj:
        values = [line.strip() for line in file_obj.readlines()]
    result = {}
    for index, key_name in enumerate(key_names):
        result[key_name] = values[index] if index < len(values) else 'N/A'
    return result


def build_elastoplastic_single_axis_cases(kw):
    """Read epUseStrainXX/ShearYY flags and matching value keywords to build a list of cases."""
    case_list = []
    for load_label, component_key, use_keyword_name, value_keyword_name, legacy_label in ELASTOPLASTIC_LOAD_DEFINITIONS:
        if kw.get(use_keyword_name, False):
            load_values = parse_elastoplastic_uniaxial_values(kw.get(value_keyword_name, 0.0), load_label)
            for load_value in load_values:
                case_values = {
                    'epsilon_x': 0.0, 'epsilon_y': 0.0, 'epsilon_z': 0.0,
                    'gamma_xy': 0.0, 'gamma_yz': 0.0, 'gamma_zx': 0.0
                }
                case_values[component_key] = load_value
                if len(load_values) > 1:
                    case_values['case_label'] = '{}_{}'.format(load_label, format_elastoplastic_load_value_label(load_value))
                else:
                    case_values['case_label'] = load_label
                case_values['legacy_loading_type'] = legacy_label
                case_list.append(case_values)
    return case_list


def build_elastoplastic_biaxial_case(kw):
    """Read the epBiaxialCombo string + the two value keywords to build a single biaxial case."""
    selected_combo = str(kw.get('epBiaxialCombo', '') or '').strip()
    if selected_combo == '':
        return []
    component_lookup = {}
    legacy_lookup = {}
    for load_label, component_key, use_keyword_name, value_keyword_name, legacy_label in ELASTOPLASTIC_LOAD_DEFINITIONS:
        component_lookup[load_label] = component_key
        legacy_lookup[load_label] = legacy_label
    for combo_label, first_label, second_label in ELASTOPLASTIC_BIAXIAL_OPTIONS:
        if combo_label == selected_combo:
            case_values = {
                'epsilon_x': 0.0, 'epsilon_y': 0.0, 'epsilon_z': 0.0,
                'gamma_xy': 0.0, 'gamma_yz': 0.0, 'gamma_zx': 0.0
            }
            case_values[component_lookup[first_label]] = float(kw.get('epBiaxialValue1', 0.0) or 0.0)
            case_values[component_lookup[second_label]] = float(kw.get('epBiaxialValue2', 0.0) or 0.0)
            case_values['case_label'] = combo_label
            case_values['legacy_loading_type'] = '{}-{}'.format(legacy_lookup[first_label], legacy_lookup[second_label])
            return [case_values]
    return []


def run_elastic_temperature_sweep(model_name, instance_name, meshsens, CPU,
                                  E11, E22, E33, G12, G13, G23,
                                  onlyPBC, temperature_points, umatName, feasypbc,
                                  result_timestamp, output_root_dir=None,
                                  keep_all_outputs=False, case_label='Elastic'):
    """Run feasypbc once per Celsius point; write per-point + aggregate CSVs."""
    temperature_points = validate_celsius_temperature_points(list(temperature_points or []), 'Elastic temperature point')
    if not temperature_points or onlyPBC:
        return None

    output_root_dir = output_root_dir or os.getcwd()
    result_keys = ['E11', 'E22', 'E33', 'G12', 'G13', 'G23',
                   'V12', 'V13', 'V21', 'V23', 'V31', 'V32',
                   'CTE_X', 'CTE_Y', 'CTE_Z', 'Mass', 'Density', 'Duration']
    fieldnames = ['Temperature (C)'] + result_keys
    result_rows = []

    for temperature_value in temperature_points:
        work_directory = None
        if keep_all_outputs:
            subdir_name = build_case_output_subdirectory(model_name, 'Elastic', case_label, temperature_value, result_timestamp)
            ensure_output_path_is_safe(
                output_root_dir, subdir_name,
                '{}_elastic_properties_{}_{}.csv'.format(model_name, format_temperature_file_label(temperature_value), result_timestamp)
            )
            work_directory = os.path.join(output_root_dir, subdir_name)
        run_callable_in_directory(
            work_directory,
            feasypbc,
            model_name, instance_name, meshsens,
            E11, E22, E33, G12, G13, G23, False, CPU, onlyPBC,
            temperature_value, temperature_value, 1, umatName
        )
        result_directory = work_directory or os.getcwd()
        easycopy_path = os.path.join(result_directory, '{}_elastic_properties(easycopy).txt'.format(model_name))
        row = {'Temperature (C)': temperature_value}
        try:
            row.update(read_easycopy_results(easycopy_path, result_keys))
        except IOError:
            for k in result_keys:
                row[k] = 'N/A'
        result_rows.append(row)
        per_temp_csv = os.path.join(
            result_directory,
            '{}_elastic_properties_{}_{}.csv'.format(model_name, format_temperature_file_label(temperature_value), result_timestamp)
        )
        write_single_row_csv(per_temp_csv, fieldnames, row)

    aggregate_csv = os.path.join(output_root_dir, '{}_elastic_temperature_sweep_{}.csv'.format(model_name, result_timestamp))
    ensure_output_path_is_safe(output_root_dir, '', os.path.basename(aggregate_csv))
    write_temperature_sweep_results(aggregate_csv, fieldnames, result_rows)
    print('Elastic temperature sweep results saved to {}'.format(aggregate_csv))
    return aggregate_csv


def run_thermal_temperature_sweep(model_name, instance_name, meshsens, CPU,
                                  K11, K22, K33, onlyPBC, temperature_points, feasypbc,
                                  result_timestamp, output_root_dir=None,
                                  keep_all_outputs=False, case_label='ThermalConductivity'):
    temperature_points = validate_celsius_temperature_points(list(temperature_points or []), 'Thermal temperature point')
    if not temperature_points or onlyPBC:
        return None

    output_root_dir = output_root_dir or os.getcwd()
    result_keys = ['K11', 'K22', 'K33', 'K12', 'K21', 'K13', 'K31', 'K23', 'K32',
                   'Mass', 'Density', 'Duration']
    fieldnames = ['Temperature (C)'] + result_keys
    result_rows = []

    for temperature_value in temperature_points:
        work_directory = None
        if keep_all_outputs:
            subdir_name = build_case_output_subdirectory(model_name, 'ThermalConductivity', case_label, temperature_value, result_timestamp)
            ensure_output_path_is_safe(
                output_root_dir, subdir_name,
                '{}_thermal_properties_{}_{}.csv'.format(model_name, format_temperature_file_label(temperature_value), result_timestamp)
            )
            work_directory = os.path.join(output_root_dir, subdir_name)
        run_callable_in_directory(
            work_directory,
            feasypbc,
            model_name, instance_name, meshsens,
            K11, K22, K33, CPU, onlyPBC,
            temperature_value, temperature_value
        )
        result_directory = work_directory or os.getcwd()
        easycopy_path = os.path.join(result_directory, '{}_thermal_properties(easycopy).txt'.format(model_name))
        row = {'Temperature (C)': temperature_value}
        try:
            row.update(read_easycopy_results(easycopy_path, result_keys))
        except IOError:
            for k in result_keys:
                row[k] = 'N/A'
        result_rows.append(row)
        per_temp_csv = os.path.join(
            result_directory,
            '{}_thermal_properties_{}_{}.csv'.format(model_name, format_temperature_file_label(temperature_value), result_timestamp)
        )
        write_single_row_csv(per_temp_csv, fieldnames, row)

    aggregate_csv = os.path.join(output_root_dir, '{}_thermal_temperature_sweep_{}.csv'.format(model_name, result_timestamp))
    ensure_output_path_is_safe(output_root_dir, '', os.path.basename(aggregate_csv))
    write_temperature_sweep_results(aggregate_csv, fieldnames, result_rows)
    print('Thermal temperature sweep results saved to {}'.format(aggregate_csv))
    return aggregate_csv

## Plugin main GUI function
###############################################################################
################################# for Create RVE ##############################
###############################################################################
def CreateRVE(myModel,file_suffix_range_Set,df,vf,a,b,t,algorithm,control_options,Basefolder, **kwargs):           
    start_time_CreateRVE = time.time()
    ## Checking the validity of required parameters
    check_the_validity_of_required_parameters(myModel,file_suffix_range_Set,df,vf,a,b,t,algorithm,control_options,Basefolder)
    ## calculate geometory parameter
    radius = df * 0.5                                                 # radius of unidirectional fiber, μm
    vf0 = (math.pi * (radius**2)) / (a * b)                           # volume fraction of a single fiber
    vf0 = 100 * vf0                                                   # unified unit
    area_fiber_single = math.pi * (radius**2.0)                       # area of individual fibre circle
    area_RVE = a * b                                                  # set 2D RVE area
    N = int((vf * 0.01 * area_RVE) / area_fiber_single)               # calculate the number of fiber branches
    ## use to create Section
    circle_data = None
    ## use for Print
    separator = "-" * 100
    
    ## Select fiber coordinates generation method
    if algorithm == 1:  # Monte Carlo algorithm
        l_safe = kwargs.get('l_safe')
        if l_safe is None:
            raise ValueError("Please provide a value for the 'Safe distance between fibers' field!")
        if l_safe <= 0.0:
            raise ValueError("Error: The 'Safe distance' must be a positive value!")
        if l_safe > math.sqrt(a**2 + b**2):
            raise ValueError("Error: The 'Safe distance' exceeds the diagonal length of the RVE!")
        
        from Generate_UDFRPs_MonteCarlo import Monte_Carlo_algorithm
        circle_data = Monte_Carlo_algorithm(Basefolder, vf, df, a, b, file_suffix_range_Set, l_safe, control_options)

    elif algorithm == 2:  # RSE algorithm
        lmin = kwargs.get('lmin')
        lmax = kwargs.get('lmax')
        
        if lmin is None:
            raise ValueError("Please provide a value for the 'Minimum distance between fibers' field!")
        if lmax is None:
            raise ValueError("Please provide a value for the 'Maximum distance between fibers' field!")
        if lmax < lmin:
            raise ValueError("Error: The 'Maximum distance' must be greater than the 'Minimum distance'!")
        if lmin <= 0.0:
            raise ValueError("Error: The 'Minimum distance' must be a positive value!")
        if lmax <= 0.0:
            raise ValueError("Error: The 'Maximum distance' must be a positive value!")
        from Generate_UDFRPs_RSE import RSE_algorithm
        
        circle_data = RSE_algorithm(Basefolder, vf, df, a, b, file_suffix_range_Set, lmax, lmin, control_options)
        
    elif algorithm == 3:  # User coordinates files
        readcsv = kwargs.get('readcsv')
        
        if readcsv:
            # Read the coordinates from the user-provided CSV files
            all_coordinates_per_file, file_count = read_coordinates_from_multiple_files(readcsv, file_suffix_range_Set)
            
            # Check if the number of CSV files matches the expected number of models
            if file_count != file_suffix_range_Set:
                raise ValueError("Error: Expected {} models, but only {} CSV file(s) were provided.".format(file_suffix_range_Set, file_count))
            
            # Adjust the RVE size or volume fraction based on control options
            if control_options == 1:
                scale_factor = math.sqrt(N * math.pi * (radius**2.0) / (vf * 0.01) / (a * b))
                a *= scale_factor
                b *= scale_factor
                print("RVE dimensions adjusted to a = {:.2f}, b = {:.2f} to match the desired volume fraction.".format(a, b))
            elif control_options == 2:
                vf = (N * math.pi * (radius**2.0) / (a * b)) * 100
                print("Volume fraction adjusted to vf = {:.4f}% to match the RVE size.".format(vf))
            
            total_elapsed_time = 0
            for suffix in range(file_suffix_range_Set):
                start_time_single_model_user = time.time()
                coordinates_for_this_model = all_coordinates_per_file[suffix]
                if isinstance(df, float) and df.is_integer():
                    df_str = str(int(df))
                else:
                    df_str = str(df).replace('.', '_')
                
                model_name = '{}_Df{}_Vf{:03d}_N{}_Model_{}'.format(myModel, df_str, int(vf + 0.5), N, suffix + 1)
                mdb.Model(name=model_name)
                model = mdb.models[model_name]
                full_circle_center = create_full_circle_inside(radius, a, b, coordinates_for_this_model)
                Arcs, new_part, midpoints_lengths_Matrix_all, midpoints_lengths_Fiber_all = create_sketch_and_extrude(model, radius, a, b, coordinates_for_this_model, full_circle_center, t)
                assemble_and_merge(radius, a, b, model, full_circle_center, coordinates_for_this_model, t)
                Set_findAt(model, full_circle_center, radius, t, coordinates_for_this_model, a, b, Arcs, new_part, midpoints_lengths_Matrix_all, midpoints_lengths_Fiber_all)
                
                end_time_single_model_user = time.time()
                elapsed_time_single_model_user = end_time_single_model_user - start_time_single_model_user
                print("==> It took {:.04f} seconds to complete.".format(elapsed_time_single_model_user))
                total_elapsed_time += elapsed_time_single_model_user
                elapsed_time_single_model_user = 0
            
            average_elapsed_time = total_elapsed_time / file_suffix_range_Set
            print("Successfully created {} models using User Coordinates files.".format(file_count))
            
            if control_options == 1:
                control_options_name = "vf"
            elif control_options == 2:
                control_options_name = "RVE width and height"
            
            ## Save information at txt
            txt_name = "RVE2D_parameters_output_Vf_{:03d}_xy_{}units_{}fiber.txt".format(int(vf + 0.5), file_suffix_range_Set, N)
            folder_name = "RVE_UDFibers{}_Vf{:03d}_xy_{}units_copy_user_files".format(N, int(vf + 0.5), file_suffix_range_Set)
            folder_path = os.path.join(Basefolder, folder_name)
            txt_save_path = os.path.join(folder_path, txt_name)
            if not os.path.exists(folder_path):
                os.makedirs(folder_path)
            # Writing the details to a text file
            with open(txt_save_path, "w") as file:
                file.write('Using the user coordinates file(s), {} set(s) of random fiber circle center coordinates have been successfully generated.\n'.format(file_suffix_range_Set))
                file.write('----------------------------------------------------------------------\n')
                file.write('Fixed parameter: {}\n'.format(control_options_name))
                file.write('----------------------------------------------------------------------\n')
                file.write('User input parameters\n')
                file.write(' - Volume Fraction of Fiber:                    {:.4f}%\n'.format(vf))
                file.write(' - Diameter of fiber:                           {}\n'.format(df))
                file.write(' - Number of fibers:                            {}\n'.format(N))
                file.write(' - RVE width:                                   {:.2f}\n'.format(a))
                file.write(' - RVE height:                                  {:.2f}\n'.format(b))
                file.write('----------------------------------------------------------------------\n')
                file.write('Average time per set of coordinates created:     {:.2f} seconds\n'.format(average_elapsed_time))
                file.write('Total time for {:02d} set(s) of coordinates:     {:.2f} seconds\n'.format(file_suffix_range_Set, total_elapsed_time))
                file.write('----------------------------------------------------------------------\n')
                file.write('The folder containing the model information and the coordinates of {} set(s) of random fiber centers has been saved at:\n'.format(file_suffix_range_Set))
                file.write('==> {}\n'.format(folder_path))

            # Info output for console
            print(' ')
            print(' ')
            print('-------------------------------------- Create RVE Information --------------------------------------')
            print(' ')
            print('Fixed parameter: {}\n'.format(control_options_name))
            print('Using the user coordinates file(s), {} set(s) of random fiber circle center coordinates have been successfully generated.\n'.format(file_count))
            print(' - Volume Fraction of Fiber:                    {:.4f}%'.format(vf))
            print(' - Diameter of fiber:                           {}'.format(df))
            print(' - Number of fibers:                            {}'.format(N))
            print(' - RVE width:                                   {:.2f}'.format(a))
            print(' - RVE height:                                  {:.2f}'.format(b))
            print(' - RVE thickness:                                   {:.2f}'.format(t))
            print(' ')
        else:
            raise ValueError("No CSV file provided for User coordinates algorithm!")
    
    elif algorithm == 0:
        raise ValueError("Please select a fibers random coordinates generation method!")
    
    ## Ensure that circle_data is not None before proceeding
    if not circle_data and algorithm != 3:
        raise ValueError("Invalid coordinates data, failed to generate circle data!")
    
    # Adjust the RVE size or volume fraction based on control options
    if control_options == 1:
        scale_factor = math.sqrt(N * math.pi * (radius**2.0) / (vf * 0.01) / (a * b))
        a *= scale_factor
        b *= scale_factor
        print("RVE dimensions adjusted to a = {}, b = {} to match the desired volume fraction.".format(a, b))
    elif control_options == 2:
        vf = (N * math.pi * (radius**2.0) / (a * b)) * 100
        print("Volume fraction adjusted to vf = {:.4f}% to match the RVE size.".format(vf))
        
    ## main function of creating models for Monte Carlo and RSE
    if algorithm == 1 or algorithm == 2:
        for suffix in range(file_suffix_range_Set):
            start_time_single_model = time.time()
            
            circles = circle_data[suffix]
            #circle_data_list = list(circle_data)
            #circles = circle_data_list[suffix]
            
            if isinstance(df, float) and df.is_integer():
                df_str = str(int(df))
            else:
                df_str = str(df).replace('.', '_')
            
            model_name = '{}_Df{}_Vf{:03d}_N{}_Model_{}'.format(myModel, df_str, int(vf), N, suffix + 1)
            mdb.Model(name=model_name)
            model = mdb.models[model_name]
            # Adjust the RVE size or volume fraction based on control options
            if control_options == 1:
                scale_factor = math.sqrt(N * math.pi * (radius**2.0) / (vf * 0.01) / (a * b))
                a *= scale_factor
                b *= scale_factor
                #print("RVE dimensions adjusted to a = {}, b = {} to match the desired volume fraction.".format(a, b))
            elif control_options == 2:
                vf = (N * math.pi * (radius**2.0) / (a * b)) * 100
                #print("Volume fraction adjusted to vf = {:.4f}% to match the RVE size.".format(vf))
            full_circle_center = create_full_circle_inside(radius, a, b, circles)
            Arcs, new_part, midpoints_lengths_Matrix_all, midpoints_lengths_Fiber_all = create_sketch_and_extrude(model, radius, a, b, circles, full_circle_center, t) 
            assemble_and_merge(radius, a, b, model, full_circle_center, circles, t)
            Set_findAt(model, full_circle_center, radius, t, circles, a, b, Arcs, new_part, midpoints_lengths_Matrix_all, midpoints_lengths_Fiber_all)
            end_time_single_model = time.time()
            elapsed_time_single_model = end_time_single_model - start_time_single_model
            print("==> It took {:.04f} seconds to complete.".format(elapsed_time_single_model))
    
    end_time_CreateRVE = time.time()
    elapsed_time_CreateRVE = end_time_CreateRVE - start_time_CreateRVE
    average_time_CreateRVE = elapsed_time_CreateRVE / file_suffix_range_Set
    
    print (separator)
    print (' ')
    print ("==> Number of RVE models generated:              {}".format(file_suffix_range_Set))
    print ("==> Total time for generating all models:        {:.4f} seconds".format(elapsed_time_CreateRVE))
    print ("==> Average time per model:                      {:.4f} seconds".format(average_time_CreateRVE))
    print (' ')
    print (separator)
    print ("-------------------------------- All RVE Models Created Successfully -------------------------------")
    print (separator)
    print (' ')

#### Define function
# Feedback on Errors
def check_the_validity_of_required_parameters(myModel,file_suffix_range_Set,df,vf,a,b,t,algorithm,control_options,Basefolder):
    if not myModel:
        raise ValueError("Please fill in the 'Model Name' field!")
    if not file_suffix_range_Set:
        raise ValueError("Please fill in the 'File Suffix Range' field!")
    if not df:
        raise ValueError("Please fill in the 'Fiber Diameter' field!")
    if not vf:
        raise ValueError("Please fill in the 'Fiber Volume Fraction' field!")
    elif vf < 0.0 or vf > 100.0:
        raise ValueError("Error: The value of “vf” is in percentage!")
    if 0.0 < vf < 1.0:
        print("Warning", "The value of “vf” is in percentage!")
    if not a:
        raise ValueError("Please fill in the 'RVE Width' field!")
    elif a < df:
        raise ValueError("Error: RVE width is less than fiber diameter!")
    if not b:
        raise ValueError("Please fill in the 'RVE Height' field!")
    elif b < df:
        raise ValueError("Error: RVE height is less than fiber diameter!")
    if not t:
        raise ValueError("Please fill in the 'RVE thickness' field!")
    if t <= 0.0:
        raise ValueError("Please enter a positive value for RVE thickness!")
    if not algorithm:
        raise ValueError("Please select an 'Algorithm'!")
    if not control_options:
        raise ValueError("Please select a 'Control Option'!")
    if not Basefolder:
        raise ValueError("Please provide a 'Base Folder Directory'!")
    ## Checking volume fraction input values against the way fiber coordinates are created
    if algorithm == 1:
        algorithm_name = "Monte Carlo"
        max_vf = 45
    elif algorithm == 2:
        algorithm_name = "RSE"
        max_vf = 68
    elif algorithm == 3:
        algorithm_name = "User coordinates files"
        max_vf = 100
    else:
        raise ValueError("Error: Please select an algorithm!")
    if vf < 0 or vf > max_vf:
        raise ValueError("Error: Volume fraction (vf) must be between 0 and {}% for {}".format(max_vf, algorithm_name))
    
    return

# Determine the coordinates of the center of the circle -----------------------
def find_csv_files(base_folder, file_prefix, file_suffix_range):
    csv_files = []
    if not os.path.exists(base_folder):
        raise ValueError("Base folder not found: {}".format(base_folder))
    for suffix in file_suffix_range:
        file_name = "{}{}.csv".format(file_prefix, suffix)
        file_path = os.path.join(base_folder, file_name)
        file_path = os.path.normpath(file_path)
        ##print("Looking for file: {}".format(file_path))  
        if os.path.exists(file_path):
            csv_files.append((suffix, file_path))
        else:
            print("File not found: {}".format(file_path))  
    return csv_files

def extract_circle_data(base_folder, file_prefix, file_suffix_range):
    circle_data = {}
    csv_files = find_csv_files(base_folder, file_prefix, file_suffix_range)
    for suffix, file_path in csv_files:
        if suffix not in circle_data:
            circle_data[suffix] = []
        coordinates = read_coordinates_from_csv(file_path)
        circle_data[suffix].extend(coordinates)
    return circle_data

# read csv file to get the cooedinates of fibers-------------------------------
def read_coordinates_from_csv(file_path):
    coordinates = []
    try:
        with open(file_path, 'r') as csvfile:
            csv_reader = csv.reader(csvfile, delimiter=',')
            next(csv_reader, None)
            for row in csv_reader:
                if len(row) >= 2:
                    try:
                        x, y = float(row[0]), float(row[1])
                        coordinates.append((x, y))
                    except ValueError:
                        print("Invalid row, could not convert to float: {}".format(row))
                else:
                    print("Invalid row in CSV: {}".format(row))
    except Exception as e:
        print("Error reading CSV file {}: {}".format(file_path, e))
    return coordinates

def read_coordinates_from_multiple_files(file_paths, file_suffix_range_Set):
    if isinstance(file_paths, str):
        # If the path contains multiple file paths separated by commas or semicolons, it is split into a list
        if ',' in file_paths:
            file_paths = file_paths.split(',')
        elif ';' in file_paths:
            file_paths = file_paths.split(';')
        else:
            file_paths = [file_paths]
    
    all_coordinates_per_file = []
    file_count = len(file_paths)
    ##print("{} file(s) has/have been read.".format(file_count))
    ##print("{} model(s) is/are being created".format(file_suffix_range_Set))
    
    if file_count == file_suffix_range_Set:
        for file_path in file_paths:
            ##print("Reading coordinates from file: {}".format(file_path))
            file_coordinates = read_coordinates_from_csv(file_path)
            all_coordinates_per_file.append(file_coordinates)
    else:
        raise ValueError("Error: The number of 'Select File' and 'Generate Model' are not equal!")
    
    return all_coordinates_per_file, file_count

# Use to Create Sketch --------------------------------------------------------
# Calculate intersections of Square and circle, use to create Straightness ----
def calculate_intersections(radius, a, b, circles):
    # Get the coordinates of the intersection of the fibre circle and the matrix square
    all_intersections = []
    intersections_left_list, intersections_right_list = [], []
    intersections_bottom_list, intersections_top_list = [], []
    effective_decimal = 14
    for center in circles:
        # Check for intersections with each boundary
        if center[0] - radius < 0:                                           # Left edge, x = 0
            y1 = round(center[1] + (radius**2 - center[0]**2)**0.5, effective_decimal)
            y2 = round(center[1] - (radius**2 - center[0]**2)**0.5, effective_decimal)
            # confirm at lease one intersection on the edge of square
            if 0 <= y1 <= b or 0 <= y2 <= b:
                y1 = min(b, max(0, y1))
                y2 = min(b, max(0, y2))
                all_intersections.extend([(0, y1), (0, y2)])
                intersections_left_list.extend([y1, y2])
            else:
                pass
        if center[0] + radius > a:                                           # Right edge, x = a
            y3 = round(center[1] + (radius**2 - (a - center[0])**2)**0.5, effective_decimal)
            y4 = round(center[1] - (radius**2 - (a - center[0])**2)**0.5, effective_decimal)
            if 0 <= y3 <= b or 0 <= y4 <= b:
                y3 = min(b, max(0, y3))
                y4 = min(b, max(0, y4))
                all_intersections.extend([(a, y3), (a, y4)])
                intersections_right_list.extend([y3, y4])
            else:
                pass
        if center[1] - radius < 0:                                           # Bottom edge y = 0
            x1 = round(center[0] + (radius**2 - center[1]**2)**0.5, effective_decimal)
            x2 = round(center[0] - (radius**2 - center[1]**2)**0.5, effective_decimal)
            if 0 <= x1 <= a or 0 <= x2 <= a:
                x1 = min(a, max(0, x1))
                x2 = min(a, max(0, x2))
                all_intersections.extend([(x1, 0), (x2, 0)])
                intersections_bottom_list.extend([x1, x2])
            else:
                pass
        if center[1] + radius > b:                                       # Top edge y = b
            x3 = round(center[0] + (radius**2 - (b - center[1])**2)**0.5, effective_decimal)
            x4 = round(center[0] - (radius**2 - (b - center[1])**2)**0.5, effective_decimal)
            if 0 <= x3 <= a or 0 <= x4 <= a:
                x3 = min(a, max(0, x3))
                x4 = min(a, max(0, x4))
                all_intersections.extend([(x3, b), (x4, b)])                 # use to create Straightness for Fiber
                intersections_top_list.extend([x3, x4])                      # use to create Straightness for Matrix
            else:
                pass
    
    intersections_left_list = sorted(set(intersections_left_list))
    intersections_right_list = sorted(set(intersections_right_list))
    intersections_bottom_list = sorted(set(intersections_bottom_list))
    intersections_top_list = sorted(set(intersections_top_list))
    all_intersections = []
    # Enforce symmetry on opposite boundaries
    if len(intersections_left_list) == len(intersections_right_list):
        intersections_left_list, intersections_right_list = enforce_symmetry(intersections_left_list, intersections_right_list, effective_decimal)
    if len(intersections_bottom_list) == len(intersections_top_list):
        intersections_bottom_list, intersections_top_list = enforce_symmetry(intersections_bottom_list, intersections_top_list, effective_decimal)
    
    all_intersections = ([(0, y) for y in intersections_left_list] + [(a, y) for y in intersections_right_list] +
                         [(x, 0) for x in intersections_bottom_list] + [(x, b) for x in intersections_top_list])
    
    return all_intersections, intersections_left_list, intersections_right_list, intersections_bottom_list, intersections_top_list

def enforce_symmetry(list1, list2, effective_decimal):
    symmetric_list1, symmetric_list2 = [], []
    for val1, val2 in zip(list1, list2):
        avg_val = round((val1 + val2) / 2, effective_decimal)
        symmetric_list1.append(avg_val)
        symmetric_list2.append(avg_val)
    return symmetric_list1, symmetric_list2

def calculate_arc_properties(p1, p2, center, radius, a, b):
    def is_point_within_boundary(point, a, b):
        x, y = point
        return 0 <= x <= a and 0 <= y <= b

    # Calculate the angle between two points connected to the center
    angle1 = math.atan2(p1[1] - center[1], p1[0] - center[0])
    angle2 = math.atan2(p2[1] - center[1], p2[0] - center[0])
    # Calculate the arc length and use the shortest angle difference
    delta_angle = abs(angle2 - angle1)
    if delta_angle > math.pi:
        delta_angle = 2 * math.pi - delta_angle
    arc_length = delta_angle * radius
    # Calculate the midpoint angle of an arc
    midpoint_angle = (angle1 + angle2) / 2
    # Handling of angles spanning π
    if abs(angle2 - angle1) > math.pi:
        midpoint_angle += math.pi
    # Ensure that the angle is within [-π, π].
    midpoint_angle = (midpoint_angle + math.pi) % (2 * math.pi) - math.pi
    arc_midpoint = (center[0] + radius * math.cos(midpoint_angle), center[1] + radius * math.sin(midpoint_angle))
    if not is_point_within_boundary(arc_midpoint, a, b):
        arc_length = 2*math.pi*radius - delta_angle * radius
        midpoint_angle = midpoint_angle + math.pi
        arc_midpoint = (center[0] + radius * math.cos(midpoint_angle), center[1] + radius * math.sin(midpoint_angle))
    
    return arc_length, arc_midpoint, angle1, angle2

def create_arc_segment(sketch, radius, a, b, circles):
    #Define the four boundary equations of the rectangle
    x, y = sp.symbols('x y')
    left_edge = x - 0.0
    right_edge = x - a
    bottom_edge = y - 0.0
    top_edge = y - b
    
    effective_decimal = 14
    arcs = []
    arc_set = set()
    for center in circles:
        intersections = []
        unique_points = set()
        circle_eq = (x - center[0])**2.0 + (y - center[1])**2.0 - radius**2.0
        # Process the four sides and calculate the intersection
        edges = [('left', left_edge), ('right', right_edge), ('bottom', bottom_edge), ('top', top_edge)]
        if radius < center[0] < a - radius and radius < center[1] < b - radius:
            pass
        else:
            for edge_name, edge_eq in edges:
                solution = sp.solve([circle_eq, edge_eq], (x, y), dict=True)
                for sol in solution:
                    if sol[x].is_real and sol[y].is_real:
                        real_x = round(float(sol[x].evalf()), effective_decimal)
                        real_y = round(float(sol[y].evalf()), effective_decimal)
                        # Check if the intersection point is within the rectangle
                        if 0 <= real_x <= a + 1E-10 and 0 <= real_y <= b + 1E-10:
                            real_sol = (real_x, real_y)
                            if real_sol not in unique_points:
                                unique_points.add(real_sol)
                                intersections.append((real_sol, edge_name))
            # Processed according to the number of intersections
            if len(intersections) == 0:
                pass
            elif len(intersections) == 2:
                (pt1, edge1), (pt2, edge2) = intersections
                if edge1 == edge2:
                    if edge1 == 'left':
                        if pt1[1] < pt2[1]:
                            selected_arc = (center, pt1, pt2)
                        else:
                            selected_arc = (center, pt2, pt1)
                    elif edge1 == 'right':
                        if pt1[1] > pt2[1]:
                            selected_arc = (center, pt1, pt2)
                        else:
                            selected_arc = (center, pt2, pt1)
                    elif edge1 == 'bottom':
                        if pt1[0] > pt2[0]:
                            selected_arc = (center, pt1, pt2)
                        else:
                            selected_arc = (center, pt2, pt1)
                    elif edge1 == 'top':
                        if pt1[0] < pt2[0]:
                            selected_arc = (center, pt1, pt2)
                        else:
                            selected_arc = (center, pt2, pt1)
                else:
                    # Two intersections on adjacent sides
                    if ('left' in [edge1, edge2] and 'bottom' in [edge1, edge2]):
                        # Lower left corner, from lower border to left border
                        if edge1 == 'bottom':
                            selected_arc = (center, pt1, pt2)
                        else:
                            selected_arc = (center, pt2, pt1)
                    elif ('left' in [edge1, edge2] and 'top' in [edge1, edge2]):
                        # Upper left corner, from the left border to the upper border
                        if edge1 == 'left':
                            selected_arc = (center, pt1, pt2)
                        else:
                            selected_arc = (center, pt2, pt1)
                    elif ('right' in [edge1, edge2] and 'bottom' in [edge1, edge2]):
                        # Lower right corner, from the right border to the lower border
                        if edge1 == 'right':
                            selected_arc = (center, pt1, pt2)
                        else:
                            selected_arc = (center, pt2, pt1)
                    elif ('right' in [edge1, edge2] and 'top' in [edge1, edge2]):
                        # Upper right corner, from the upper border to the right border
                        if edge1 == 'top':
                            selected_arc = (center, pt1, pt2)
                        else:
                            selected_arc = (center, pt2, pt1)
                    else:
                        selected_arc = (center, pt1, pt2)
    
                # Uniqueness detection: by checking whether a combination of the start and end points of an arc already exists
                arc_id = (tuple(sorted([selected_arc[1], selected_arc[2]])))
                if arc_id not in arc_set:
                    # Calculate the properties of an arc and store
                    arc_length, Arc_midpoint, angle1, angle2 = calculate_arc_properties(selected_arc[1], selected_arc[2], center, radius, a, b)
                    arc_data = (center, selected_arc[1], selected_arc[2], arc_length, Arc_midpoint)
                    arcs.append(arc_data)
                    arc_set.add(arc_id)
                    
            elif len(intersections) == 4 and not check_if_near_corner(center, a, b, radius):
                selected_arcs = process_corner_intersections(a, b, center, [pt for pt, edge in intersections], radius, arc_set)
                arcs.extend(selected_arcs)
            elif len(intersections) == 4 and check_if_near_corner(center, a, b, radius):
                selected_arcs = process_corner_intersections(a, b, center, [pt for pt, edge in intersections], radius, arc_set)
                arcs.extend(selected_arcs)
    #print(f"arcs,{arcs}")
    return arcs

# Check that the center of the circle is close to the four vertices
def check_if_near_corner(center, a, b, radius):
    corners = [(0, 0), (0, b), (a, 0), (a, b)]
    for corner in corners:
        if (distance(center, corner) > radius and
            abs(center[0] - corner[0]) < radius and
            abs(center[1] - corner[1]) < radius and
            0 <= center[0] <= a and
            0 <= center[1] <= b):
            return True
    return False

def distance(point1, point2):
    return ((point1[0] - point2[0]) ** 2 + (point1[1] - point2[1]) ** 2) ** 0.5

# Deals with the case of being located at four corners with four intersections
def process_corner_intersections(a, b, center, intersections, radius, arc_set):
    ## print("a && b", a, b)
    left_points = [pt for pt in intersections if pt[0] == 0.0]
    right_points = [pt for pt in intersections if abs(a - pt[0]) <= 1E-4]
    bottom_points = [pt for pt in intersections if pt[1] == 0.0]
    top_points = [pt for pt in intersections if abs(b - pt[1]) <= 1E-4]
    arcs = []

    # Print statements to check the filtered corner points
    ##print("Left points:", left_points)
    ##print("Right points:", right_points)
    ##print("Bottom points:", bottom_points)
    ##print("Top points:", top_points)

    # Lower left corner (0, 0)
    if left_points and bottom_points:
        ##print("Processing lower left corner")
        arcs.extend(handle_single_corner(center, left_points, bottom_points, (0, 0), radius, arc_set, a, b, "left_bottom"))
    
    # Upper left corner (0, b)
    if left_points and top_points:
        ##print("Processing upper left corner")
        arcs.extend(handle_single_corner(center, left_points, top_points, (0, b), radius, arc_set, a, b, "left_top"))
    
    # Lower right corner (a, 0)
    if right_points and bottom_points:
        ##print("Processing lower right corner")
        arcs.extend(handle_single_corner(center, right_points, bottom_points, (a, 0), radius, arc_set, a, b, "right_bottom"))
    
    # Upper right corner (a, b)
    if right_points and top_points:
        ##print("Processing upper right corner")
        arcs.extend(handle_single_corner(center, right_points, top_points, (a, b), radius, arc_set, a, b, "right_top"))

    # Print the final arcs for debugging
    ##print("Generated arcs:", arcs)
    
    return arcs

# Handling individual corners, drawing arcs at near and far points
def handle_single_corner(center, points1, points2, corner, radius, arc_set, a, b, corner_type):
    points1_sorted = sorted(points1, key=lambda p: distance(p, corner))
    points2_sorted = sorted(points2, key=lambda p: distance(p, corner))
    arcs = []
    # close arc
    arcs.extend(process_arc(center, points1_sorted[0], points2_sorted[0], radius, arc_set, corner, True, corner_type, a, b))
    # far arc
    arcs.extend(process_arc(center, points1_sorted[-1], points2_sorted[-1], radius, arc_set, corner, False, corner_type, a, b))

    return arcs

def get_polar_angle(point, center):
    dx = point[0] - center[0]
    dy = point[1] - center[1]
    angle = math.atan2(dy, dx)
    return angle

# Handling arcs and checking the size of the arcs
def process_arc(center, pt1, pt2, radius, arc_set, corner, close_arc, corner_type, a, b):
    arcs = []
    arc_length, Arc_midpoint, angle1, angle2 = calculate_arc_properties(pt1, pt2, center, radius, a, b)
    # Calculate the radian delta_angle
    delta_angle = abs(angle2 - angle1)
    if delta_angle > math.pi:
        delta_angle = 2 * math.pi - delta_angle
    # Orientation and size are handled separately for different corner types
    if corner_type in ["left_bottom", "right_top"]:
        if (close_arc and delta_angle >= math.pi) or (not close_arc and delta_angle <= math.pi):
            pt1, pt2 = pt2, pt1
    elif corner_type in ["left_top", "right_bottom"]:
        if (close_arc and delta_angle <= math.pi) or (not close_arc and delta_angle >= math.pi):
            pt1, pt2 = pt2, pt1
    # Generate unique arc IDs and check if they have already been drawn
    arc_id = tuple(sorted([pt1, pt2]))
    if arc_id not in arc_set:
        arcs.append((center, pt1, pt2, arc_length, Arc_midpoint))
        arc_set.add(arc_id)

    return arcs

# Create Straightness ---------------------------------------------------------
# For Matrix ------------------------------------------------------------------
def draw_Straightness_matrix(sketch, points, edge, a, b):
    decimal_places = 18
    points = sorted(points)
    midpoints_lengths_Matrix = []
    
    if edge == 'left' or edge == 'right':
        start = 0.0
        end = float(b)
    elif edge == 'bottom' or edge == 'top':
        start = 0.0
        end = float(a)
    
    if len(points) == 0:
        if edge == 'left':
            sketch.Line(point1=(0.0, start), point2=(0.0, end))
            mid_x = 0.0
            mid_y = (start + end) / 2.0
            segment_length = end - start
            # Retain the result to the specified number of decimal places.
            mid_x = round(mid_x, decimal_places)
            mid_y = round(mid_y, decimal_places)
            segment_length = round(segment_length, decimal_places)
            midpoints_lengths_Matrix.append(((mid_x, mid_y), segment_length))
        elif edge == 'right':
            sketch.Line(point1=(a, start), point2=(a, end))
            mid_x = float(a)
            mid_y = (start + end) / 2.0
            segment_length = end - start
            mid_x = round(mid_x, decimal_places)
            mid_y = round(mid_y, decimal_places)
            segment_length = round(segment_length, decimal_places)
            midpoints_lengths_Matrix.append(((mid_x, mid_y), segment_length))
        elif edge == 'bottom':
            sketch.Line(point1=(start, 0.0), point2=(end, 0.0))
            mid_x = (start + end) / 2.0
            mid_y = 0.0
            segment_length = end - start
            mid_x = round(mid_x, decimal_places)
            mid_y = round(mid_y, decimal_places)
            segment_length = round(segment_length, decimal_places)
            midpoints_lengths_Matrix.append(((mid_x, mid_y), segment_length))
        elif edge == 'top':
            sketch.Line(point1=(start, b), point2=(end, b))
            mid_x = (start + end) / 2.0
            mid_y = float(b)
            segment_length = end - start
            mid_x = round(mid_x, decimal_places)
            mid_y = round(mid_y, decimal_places)
            segment_length = round(segment_length, decimal_places)
            midpoints_lengths_Matrix.append(((mid_x, mid_y), segment_length))
        return midpoints_lengths_Matrix

    in_matrix = True
    current = start

    for p in points:
        if in_matrix:
            segment_length = p - current
            if segment_length > 0:
                if edge == 'left':
                    sketch.Line(point1=(0.0, current), point2=(0.0, p))
                    mid_x = 0.0
                    mid_y = (current + p) / 2.0
                elif edge == 'right':
                    sketch.Line(point1=(a, current), point2=(a, p))
                    mid_x = float(a)
                    mid_y = (current + p) / 2.0
                elif edge == 'bottom':
                    sketch.Line(point1=(current, 0.0), point2=(p, 0.0))
                    mid_x = (current + p) / 2.0
                    mid_y = 0.0
                elif edge == 'top':
                    sketch.Line(point1=(current, b), point2=(p, b))
                    mid_x = (current + p) / 2.0
                    mid_y = float(b)
                # Retain the result to the specified number of decimal places.
                mid_x = round(mid_x, decimal_places)
                mid_y = round(mid_y, decimal_places)
                segment_length = round(segment_length, decimal_places)
                midpoints_lengths_Matrix.append(((mid_x, mid_y), segment_length))
        current = p
        in_matrix = not in_matrix

    if in_matrix and current < end:
        segment_length = end - current
        if segment_length > 0:
            if edge == 'left':
                sketch.Line(point1=(0.0, current), point2=(0.0, end))
                mid_x = 0.0
                mid_y = (current + end) / 2.0
            elif edge == 'right':
                sketch.Line(point1=(a, current), point2=(a, end))
                mid_x = float(a)
                mid_y = (current + end) / 2.0
            elif edge == 'bottom':
                sketch.Line(point1=(current, 0.0), point2=(end, 0.0))
                mid_x = (current + end) / 2.0
                mid_y = 0.0
            elif edge == 'top':
                sketch.Line(point1=(current, b), point2=(end, b))
                mid_x = (current + end) / 2.0
                mid_y = float(b)
            # Retain the result to the specified number of decimal places.
            mid_x = round(mid_x, decimal_places)
            mid_y = round(mid_y, decimal_places)
            segment_length = round(segment_length, decimal_places)
            midpoints_lengths_Matrix.append(((mid_x, mid_y), segment_length))

    return midpoints_lengths_Matrix

# For Fiber -------------------------------------------------------------------
def draw_Straightness_Fiber(sketch, points, edge, a, b):
    effective_decimal = 18
    # For fiber ===============================================================
    # arrange in order---------------------------------------------------------
    points = sorted(points)
    midpoints_lengths_Fiber = []
    if len(points) < 2:
        if edge == 'left':
            segment_length = b
            ##print("fiber have no interections with left edge")
        if edge == 'right':
            segment_length = b
            ##print("fiber have no interections with right edge")
        if edge == 'bottom':
            segment_length = a
            ##print("fiber have no interections with bottom edge")
        if edge == 'top':
            segment_length = a
            ##print("fiber have no interections with top edge")
    else:
        points = points
    for i in range(0, len(points), 2):
        segment_length = points[i+1] - points[i]  
        if edge == 'left':
            sketch.Line(point1=(0, points[i]), point2=(0, points[i+1]))
            mid_x = 0
            mid_y = round(float((points[i] + points[i+1]) / 2), effective_decimal)
        if edge == 'right':
            sketch.Line(point1=(a, points[i]), point2=(a, points[i+1]))
            mid_x = a
            mid_y = round(float((points[i] + points[i+1]) / 2), effective_decimal)
        if edge == 'bottom':
            sketch.Line(point1=(points[i], 0), point2=(points[i+1], 0))
            mid_x = round(float((points[i] + points[i+1]) / 2), effective_decimal)
            mid_y = 0
        if edge == 'top':
            sketch.Line(point1=(points[i], b), point2=(points[i+1], b))
            mid_x = round(float((points[i] + points[i+1]) / 2), effective_decimal)
            mid_y = b
            
        midpoints_lengths_Fiber.append(((mid_x, mid_y), segment_length))
            
    return midpoints_lengths_Fiber

# Create Curve ----------------------------------------------------------------
def create_full_circle_inside(radius, a, b, circles):
    full_circle_center_point = []
    for center in circles:
        if center[0] + radius <= a and center[1] + radius <= b and center[0] - radius >= 0 and center[1] - radius >= 0:
            full_circle_center_point.append(center)
            ##print("Full circles need to be created")
        else:
            ##print("No full circle inside")
            pass
    if full_circle_center_point:
        ##print("full_circle_center_point")
        pass
    return full_circle_center_point

# Create Sketch ---------------------------------------------------------------  
def create_sketch_and_extrude(model, radius, a, b, circles, full_circle_center, t):
    midpoints_lengths_Matrix_all = []
    midpoints_lengths_Fiber_all = []
    # Input Sketch Parameters =================================================
    Straightness_point, intersections_left_list, intersections_right_list, intersections_bottom_list, intersections_top_list = calculate_intersections(radius, a, b, circles)
# Create Matrix Sketch ========================================================
    # Create Viewport
    #Sketch RVE Rectangle for the matrix part
    s1 = model.ConstrainedSketch(name='__profile__', sheetSize=100) 
    s1.setPrimaryObject(option=STANDALONE) 
    # Create Straightness for Matrix ======================================
    ##print("midpoints_lengths_Matrix_test")
    midpoints_lengths_Matrix_left = draw_Straightness_matrix(s1, intersections_left_list, 'left', a, b)
    midpoints_lengths_Matrix_right = draw_Straightness_matrix(s1, intersections_right_list, 'right', a, b)
    midpoints_lengths_Matrix_bottom = draw_Straightness_matrix(s1, intersections_bottom_list, 'bottom', a, b)
    midpoints_lengths_Matrix_top = draw_Straightness_matrix(s1, intersections_top_list, 'top', a, b)
    midpoints_lengths_Matrix_all = midpoints_lengths_Matrix_left + midpoints_lengths_Matrix_right + midpoints_lengths_Matrix_bottom + midpoints_lengths_Matrix_top
    ##print("midpoints_lengths_Matrix_all", midpoints_lengths_Matrix_all)
    # Create Curve ========================================================
    # Create Circle: Center and Perimeter
    Arcs = create_arc_segment(s1, radius, a, b, circles)
    ##print("full_circle_center", full_circle_center)
    if full_circle_center:
        ##print("************create full circle inside*************")
        for value_full_circle_center in full_circle_center:
            s1.CircleByCenterPerimeter(center=(value_full_circle_center[0], value_full_circle_center[1]), point1=(value_full_circle_center[0] + radius, value_full_circle_center[1]))
            ##print("==========Draw Circle full inside Successful=============")
    # Create Arc: Center and 2 Endpoints
    if Arcs:
        ##print("************create Curve in the Sketch of Matrix*************")
        for arc in Arcs:
            ##print("==> arc:", arc)
            s1.ArcByCenterEnds(center=(arc[0][0], arc[0][1]), point1=arc[1], point2=arc[2], direction=COUNTERCLOCKWISE)
            ##print("==========Draw Arc Successful=============")
    # Name the part model and associate it
    p = model.Part(name='Matrix', dimensionality=THREE_D, type=DEFORMABLE_BODY) 
    p = model.parts['Matrix']
    # Matrix Extrusion
    p.BaseSolidExtrude(sketch=s1, depth=t) 
    s1.unsetPrimaryObject() 
    p = model.parts['Matrix'] 
    del model.sketches['__profile__'] 
    new_part = len(p.cells)
# Create Unidirectional Fiber Sketch ==========================================
    #Create Viewport
    s2 = model.ConstrainedSketch(name='__profile__', sheetSize=100) 
    s2.setPrimaryObject(option=STANDALONE) 
    # Create Straightness for Fiber =======================================
    midpoints_lengths_Fiber_left = draw_Straightness_Fiber(s2, intersections_left_list, 'left', a, b)
    midpoints_lengths_Fiber_right = draw_Straightness_Fiber(s2, intersections_right_list, 'right', a, b)
    midpoints_lengths_Fiber_bottom = draw_Straightness_Fiber(s2, intersections_bottom_list, 'bottom', a, b)
    midpoints_lengths_Fiber_top = draw_Straightness_Fiber(s2, intersections_top_list, 'top', a, b)
    midpoints_lengths_Fiber_all = midpoints_lengths_Fiber_left + midpoints_lengths_Fiber_right + midpoints_lengths_Fiber_bottom + midpoints_lengths_Fiber_top
    ##print("midpoints_lengths_Fiber_all", midpoints_lengths_Fiber_all)
    # Create Curve ========================================================
    # Create Circle: Center and Perimeter
    if full_circle_center:
        ##print("create full circle inside", full_circle_center)
        for value_full_circle_center in full_circle_center:
            ##print("value_full_circle_center", value_full_circle_center)
            s2.CircleByCenterPerimeter(center=(value_full_circle_center[0], value_full_circle_center[1]), point1=(value_full_circle_center[0] + radius, value_full_circle_center[1]))
    # Create Arc: Center and 2 Endpoints
    Arcs = create_arc_segment(s2, radius, a, b, circles)
    if Arcs:
        ##print("create Curve in the Sketch of Matrix", Arcs)
        for arc in Arcs:
            s2.ArcByCenterEnds(center=(arc[0][0], arc[0][1]), point1=arc[1], point2=arc[2], direction=COUNTERCLOCKWISE)
    # Name the part model and associate it
    p = model.Part(name='Fiber', dimensionality=THREE_D, type=DEFORMABLE_BODY) 
    p = model.parts['Fiber'] 
    # Fibre Extrusion
    p.BaseSolidExtrude(sketch=s2, depth=t) 
    s2.unsetPrimaryObject() 
    p = model.parts['Fiber']
    del model.sketches['__profile__']
    
    ##print(f"Arcs in Create Sketch,{Arcs}")
    return Arcs, new_part, midpoints_lengths_Matrix_all, midpoints_lengths_Fiber_all

# Assembly and Merge the Matrix-Part and Fiber-Part ---------------------------
def assemble_and_merge(radius, a, b, model, full_circle_center, circles, t):
    a = model.rootAssembly
    a.DatumCsysByDefault(CARTESIAN)
    a.Instance(name='Fiber-1', part=model.parts['Fiber'], dependent=ON)
    a.Instance(name='Matrix-1', part=model.parts['Matrix'], dependent=ON)
    a.rotate(instanceList=('Fiber-1',), axisPoint=(0.0, 0.0, 0.0), axisDirection=(0.0, 1.0, 0.0), angle=90.0)
    a.rotate(instanceList=('Matrix-1',), axisPoint=(0.0, 0.0, 0.0), axisDirection=(0.0, 1.0, 0.0), angle=90.0)
    a.InstanceFromBooleanMerge(name='UDComposite', instances=(a.instances['Fiber-1'], a.instances['Matrix-1']), keepIntersections=ON, originalInstances=SUPPRESS, domain=GEOMETRY)
    del a.features['Fiber-1']
    del a.features['Matrix-1']
    
    p = model.parts['UDComposite'] 
    session.viewports['Viewport: 1'].setValues(displayedObject=p)

# Converts coordinates from 2D to 3D for subsequent meshing modules
def set_to_mesh(t, circles, radius, a, b):
    # all 2D intersections ----------------------------------------------------
    all_intersections_2D, e, f, g, h = calculate_intersections(radius, a, b, circles)
    vertices = [(0.0, 0.0), (0.0, b), (a, 0.0), (a, b)]
    all_intersections_2D_set = set(all_intersections_2D)
    vertices_set = set(vertices)
    all_intersections_2D = list(all_intersections_2D_set.union(vertices_set))
    
    # change from 2D intersections to 3D --------------------------------------
    all_intersections_3D_norotation = [(x, y, 0) for (x, y) in all_intersections_2D]
    all_intersections_3D = [(t/2, y, -x) for (x, y, z) in all_intersections_3D_norotation]
    ##print("all_intersections_2D", all_intersections_2D)
    # combine all 3D points which are used for findAt -------------------------
    set_z_points = all_intersections_3D
    ##print("set_z_points", set_z_points)
    
    return set_z_points

# Create collections for subsequent meshing modules
def Set_findAt(model, full_circle_center, radius, t, circles, a, b, Arcs, new_part, midpoints_lengths_Matrix_all, midpoints_lengths_Fiber_all):
    # use for seeds
    pickedEdges_Arc = []
    pickedEdges_full_circle = []
    pickedEdges_thickness_Straightness = []
    pickedEdges_Matrix_Straightness = []
    pickedEdges_Fiber_Straightness = []
    
    # use for interface
    pickedFaces_Arc = []
    pickedFaces_full_circle = []
    
    p = model.parts['UDComposite']
    total_fibers = len(circles)
    ##print("total fibers", total_fibers)
    # create Set-Fiber and Set-Matrix
    if new_part == 1:
        p.Set(cells=p.cells[0: total_fibers], name='Set-Fiber')
        p.Set(cells=p.cells[total_fibers: total_fibers + new_part], name='Set-Matrix')
    
    elif new_part == 2:  
        ##print("Processing new_part == 2")
        part_Fiber = model.parts["Fiber"]
        points = [(0, 0), (0, b), (a, 0), (a, b)]
        cell_masks = []
        On_Fiber_point = []
        corner_id = []
        find_circle_outside_corner = False
        ''' This strategy is required when and only when the fiber is close to (0,0). ''' 
        for circle in circles:
            if circle not in full_circle_center:
                try:
                    ##print("Processing circle: {}".format(circle))
                    if circle[0] < 0 and circle[1] < 0:
                        find_point_x = (radius / (2 * math.sqrt(circle[0]**2 + circle[1]**2)) - 0.5) * abs(circle[0]) 
                        find_point_y = (radius / (2 * math.sqrt(circle[0]**2 + circle[1]**2)) - 0.5) * abs(circle[1]) 
                        find_point = (find_point_x, find_point_y)
                        ##print("Find point near (0,0):  {find_point}")
                        On_Fiber_point.append(find_point)
                        corner_id = 0                      ## left bottom
                        find_circle_outside_corner = True
                        break
                    elif circle[0] < 0 and circle[1] > b:
                        find_point_x = (radius / (2 * math.sqrt(circle[0]**2 + (circle[1] - b)**2)) - 0.5) * abs(circle[0]) 
                        find_point_y = b - (radius / (2 * math.sqrt(circle[0]**2 + (circle[1] - b)**2)) - 0.5) * abs(circle[1] - b) 
                        find_point = (find_point_x, find_point_y)
                        ##print("Find point near (0,b): {find_point}")
                        On_Fiber_point.append(find_point)
                        corner_id = 1                      ## left top
                        find_circle_outside_corner = True
                        break
                    elif circle[0] > a and circle[1] < 0:
                        find_point_x = a - (radius / (2 * math.sqrt((circle[0] - a)**2 + circle[1]**2)) - 0.5) * abs(circle[0] - a) 
                        find_point_y = (radius / (2 * math.sqrt((circle[0] - a)**2 + circle[1]**2)) - 0.5) * abs(circle[1]) 
                        find_point = (find_point_x, find_point_y)
                        ##print("Find point near (a,0): {find_point}")
                        On_Fiber_point.append(find_point)
                        corner_id = 2                      ## right bottom
                        find_circle_outside_corner = True
                        break
                    elif circle[0] > a and circle[1] > b:
                        find_point_x = a - (radius / (2 * math.sqrt((circle[0] - a)**2 + (circle[1] - b)**2)) - 0.5) * abs(circle[0] - a) 
                        find_point_y = b - (radius / (2 * math.sqrt((circle[0] - a)**2 + (circle[1] - b)**2)) - 0.5) * abs(circle[1] - b) 
                        find_point = (find_point_x, find_point_y)
                        ##print(f"Find point near (a,b): {find_point}")
                        On_Fiber_point.append(find_point)
                        corner_id = 3                      ## right top
                        find_circle_outside_corner = True
                        break
                    
                except Exception as e:
                    print("Error processing circle {}: {}".format(circle, e))
                    find_circle_outside_corner = False
            
        if On_Fiber_point:
            ##print("On_Fiber_point found: {}".format(On_Fiber_point))
            for point in On_Fiber_point:
                try:
                    ##print("Finding cell at point: {}".format(point))
                    cell = part_Fiber.cells.findAt(((point[0], point[1], 0),))
                    cell_real = p.cells.findAt(((0, point[1], -point[0]),))
                    cell_masks.append(cell_real.getMask())
                except Exception as e:
                    print("Error finding cell at point {}: {}".format(point, e))
                    continue
        
        numeric_cell_indices = []
        if cell_masks:
            for mask in cell_masks:
                cells_from_mask = p.cells.getSequenceFromMask(mask=mask)
                numeric_cell_indices.extend([cell.index for cell in cells_from_mask])
            
            ##print("Numeric cell indices: {}".format(numeric_cell_indices))
            min_cell_index = min(numeric_cell_indices)
            ##print("Minimum cell index: {}".format(min_cell_index))
        
        if find_circle_outside_corner:
            ##print("Executing method 1")
            if corner_id == 0:  ## left bottom
                p.Set(cells=p.cells[0: min_cell_index + 1] + p.cells[min_cell_index + 2: total_fibers + 1], name='Set-Fiber')
                p.Set(cells=p.cells[min_cell_index + 1: min_cell_index + 2] + p.cells[total_fibers + 1: total_fibers + 2], name='Set-Matrix')
            elif corner_id == 1 or corner_id == 2 or corner_id == 3:  ## left top & right top & right bottom
                p.Set(cells=p.cells[0: total_fibers], name='Set-Fiber')
                p.Set(cells=p.cells[total_fibers: total_fibers + new_part], name='Set-Matrix')
        else:
            ##print("Executing method 2")
            p.Set(cells=p.cells[0: total_fibers], name='Set-Fiber')
            p.Set(cells=p.cells[total_fibers: total_fibers + new_part], name='Set-Matrix')

    
    elif new_part == 3:
        part_Fiber = model.parts["Fiber"]
        points = [(0, 0), (0, b), (a, 0), (a, b)]
        no_corners_on_Fiber = True
        cell_masks = []
        for point in points:
            try:
                cell = part_Fiber.cells.findAt((point,))
                no_corners_on_Fiber = False
            except:
                cell_real = p.cells.findAt(((0, point[1], -point[0]),))
                cell_masks.append(cell_real.getMask())
        
        numeric_cell_indices = []
        if cell_masks:
            for mask in cell_masks:
                cells_from_mask = p.cells.getSequenceFromMask(mask=mask)
                numeric_cell_indices.extend([cell.index for cell in cells_from_mask])
        
            min_cell_index = min(numeric_cell_indices)
            ##print("min_cell_index", min_cell_index)
            if no_corners_on_Fiber:
                p.Set(cells=p.cells[0: min_cell_index] + p.cells[min_cell_index + 1: total_fibers + 1], name='Set-Fiber')
                p.Set(cells=p.cells[min_cell_index: min_cell_index + 1] + p.cells[total_fibers + 1: total_fibers + 3], name='Set-Matrix')
        
    ## Create Set-thickness-Straightness
    set_z_points = set_to_mesh(t, circles, radius, a, b)
    # use findAt to get all edges on z-axial
    # deal with the first element
    pickedEdges_thickness_Straightness = p.edges.findAt((set_z_points[0],))
    # deal with others element
    for point in set_z_points[1:]:
        pickedEdges_thickness_Straightness += p.edges.findAt((point,))
    
    p.Set(edges=pickedEdges_thickness_Straightness, name='Set-thickness-Straightness')
    
    ## Create Set-Matrix-Straightness
    # deal with the first element
    pickedEdges_Matrix_Straightness = p.edges.findAt(((t, midpoints_lengths_Matrix_all[0][0][1], -midpoints_lengths_Matrix_all[0][0][0]),))
    pickedEdges = p.edges.findAt(((0, midpoints_lengths_Matrix_all[0][0][1], -midpoints_lengths_Matrix_all[0][0][0]),))
    pickedEdges_Matrix_Straightness += pickedEdges
    # deal with others element
    for midpoint, seg_length in midpoints_lengths_Matrix_all[1:]:
        pickedEdges = p.edges.findAt(((t, midpoint[1], -midpoint[0]),))
        pickedEdges_Matrix_Straightness += pickedEdges
        pickedEdges = p.edges.findAt(((0, midpoint[1], -midpoint[0]),))
        pickedEdges_Matrix_Straightness += pickedEdges
    p.Set(edges=pickedEdges_Matrix_Straightness, name='Set-Matrix-Straightness')
            
    
    # initialization
    pickedEdges = None
    
    ## Create Set-Fiber-Straightness
    # deal with the first element
    pickedEdges_Fiber_Straightness = p.edges.findAt(((t, midpoints_lengths_Fiber_all[0][0][1], -midpoints_lengths_Fiber_all[0][0][0]),))
    pickedEdges = p.edges.findAt(((0, midpoints_lengths_Fiber_all[0][0][1], -midpoints_lengths_Fiber_all[0][0][0]),))
    pickedEdges_Fiber_Straightness += pickedEdges
    # deal with others element
    for midpoint, seg_length in midpoints_lengths_Fiber_all[1:]:
        pickedEdges = p.edges.findAt(((t, midpoint[1], -midpoint[0]),))
        pickedEdges_Fiber_Straightness += pickedEdges
        pickedEdges = p.edges.findAt(((0, midpoint[1], -midpoint[0]),))
        pickedEdges_Fiber_Straightness += pickedEdges
    p.Set(edges=pickedEdges_Fiber_Straightness, name='Set-Fiber-Straightness')
    
    # initialization
    pickedEdges = None
    
    ## Create Set-Arc
    if Arcs:
        ##print(f"Arcs in FindAt,{Arcs}")
        # deal with the first element
        pickedEdges_Arc = p.edges.findAt(((0.0, Arcs[0][4][1], -Arcs[0][4][0]),))
        pickedEdges = p.edges.findAt(((t, Arcs[0][4][1], -Arcs[0][4][0]),))
        pickedEdges_Arc += pickedEdges
        # deal with others element
        for center, intersection_start, intersection_end, arc_length, Arc_midpoint_2D in Arcs[1:]:
            pickedEdges = p.edges.findAt(((0.0, Arc_midpoint_2D[1], -Arc_midpoint_2D[0]),))
            pickedEdges_Arc += pickedEdges
            pickedEdges = p.edges.findAt(((t, Arc_midpoint_2D[1], -Arc_midpoint_2D[0]),))
            pickedEdges_Arc += pickedEdges
        p.Set(edges=pickedEdges_Arc, name='Set-Arc')
        
    ## Create Set-Interface-Arc
        # deal with the first element
        pickedFaces_Arc = p.faces.findAt(((t/2, Arcs[0][4][1], -Arcs[0][4][0]),))
        pickedFaces = p.faces.findAt(((t/2, Arcs[0][4][1], -Arcs[0][4][0]),))
        pickedFaces_Arc += pickedFaces
        # deal with others element
        for center, intersection_start, intersection_end, arc_length, Arc_midpoint_2D, in Arcs[1:]:
            pickedFaces = p.faces.findAt(((t/2, Arc_midpoint_2D[1], -Arc_midpoint_2D[0]),))
            pickedFaces_Arc += pickedFaces
        
        p.Set(faces=pickedFaces_Arc, name='Set-Interface-Arc')
    
    ## Create Set-full-circle
    if full_circle_center:
        # deal with the first element
        value_full_circle_center = full_circle_center[0]
        point1 = (0.0, value_full_circle_center[1], -value_full_circle_center[0] - radius)
        point2 = (t, value_full_circle_center[1], -value_full_circle_center[0] - radius)
        pickedEdges_full_circle = p.edges.findAt((point1,), (point2,))
        # deal with others element
        for value_full_circle_center in full_circle_center[1:]:
            point1 = (0.0, value_full_circle_center[1], -value_full_circle_center[0] - radius)
            point2 = (t, value_full_circle_center[1], -value_full_circle_center[0] - radius)
            pickedEdges_full_circle += p.edges.findAt((point1,), (point2,))
        
        p.Set(edges=pickedEdges_full_circle, name='Set-full-circle')
        
    ## Create Set-Interface-full-circle
        # deal with the first element
        value_full_circle_center = full_circle_center[0]
        pointOnInterface_full_circle = (t/2, value_full_circle_center[1], -value_full_circle_center[0] - radius)
        pickedFaces_full_circle = p.faces.findAt((pointOnInterface_full_circle,))
        # deal with others element
        for value_full_circle_center in full_circle_center[1:]:
            pointOnInterface_full_circle = (t/2, value_full_circle_center[1], -value_full_circle_center[0] - radius)
            pickedFaces_full_circle += p.faces.findAt((pointOnInterface_full_circle,))
        p.Set(faces=pickedFaces_full_circle, name='Set-Interface-full-circle')

    # use for seeds
    pickedEdges_Arc = []
    pickedEdges_full_circle = []
    pickedEdges_thickness_Straightness = []
    
    pickedEdges_Matrix_Straightness = []
    pickedEdges_Matrix_Straightness_vertical = []
    pickedEdges_Matrix_Straightness_horizontal = []
    
    pickedEdges_Fiber_Straightness = []
    pickedEdges_Fiber_Straightness_vertical = []
    pickedEdges_Fiber_Straightness_horizontal = []
    
    # use for interface
    pickedFaces_Arc = []
    pickedFaces_full_circle = []
    
    p = model.parts['UDComposite']
    total_fibers = len(circles)
    
    ## Create Set-Matrix-Straightness
    midpoints_vertical = []
    midpoints_horizontal = []

    for midpoint, seg_length in midpoints_lengths_Matrix_all:
        if midpoint[0] == 0 or midpoint[0] == a:
            midpoints_vertical.append(midpoint)
        if midpoint[1] == 0 or midpoint[1] == b:
            midpoints_horizontal.append(midpoint)
    
    if midpoints_vertical:
        pickedEdges_Matrix_Straightness_vertical = p.edges.findAt(((t, midpoints_vertical[0][1], -midpoints_vertical[0][0]),))
        pickedEdges_vertical = p.edges.findAt(((0, midpoints_vertical[0][1], -midpoints_vertical[0][0]),))
        pickedEdges_Matrix_Straightness_vertical += pickedEdges_vertical
        for midpoint in midpoints_vertical[1:]:
            pickedEdges_vertical = p.edges.findAt(((t, midpoint[1], -midpoint[0]),))
            pickedEdges_Matrix_Straightness_vertical += pickedEdges_vertical
            pickedEdges_vertical = p.edges.findAt(((0, midpoint[1], -midpoint[0]),))
            pickedEdges_Matrix_Straightness_vertical += pickedEdges_vertical
        
        p.Set(edges=pickedEdges_Matrix_Straightness_vertical, name='Set-Matrix-Straightness-vertical')

    if midpoints_horizontal:
        pickedEdges_Matrix_Straightness_horizontal = p.edges.findAt(((t, midpoints_horizontal[0][1], -midpoints_horizontal[0][0]),))
        pickedEdges_horizontal = p.edges.findAt(((0, midpoints_horizontal[0][1], -midpoints_horizontal[0][0]),))
        pickedEdges_Matrix_Straightness_horizontal += pickedEdges_horizontal
        for midpoint in midpoints_horizontal[1:]:
            pickedEdges_horizontal = p.edges.findAt(((t, midpoint[1], -midpoint[0]),))
            pickedEdges_Matrix_Straightness_horizontal += pickedEdges_horizontal
            pickedEdges_horizontal = p.edges.findAt(((0, midpoint[1], -midpoint[0]),))
            pickedEdges_Matrix_Straightness_horizontal += pickedEdges_horizontal
        
        p.Set(edges=pickedEdges_Matrix_Straightness_horizontal, name='Set-Matrix-Straightness-horizontal')
    
    pickedEdges_Matrix_Straightness = pickedEdges_Matrix_Straightness_vertical + pickedEdges_Matrix_Straightness_horizontal
    p.Set(edges=pickedEdges_Matrix_Straightness, name='Set-Matrix-Straightness')
    
    # initialization
    pickedEdges = None
    pickedEdges_vertical = None
    pickedEdges_horizontal = None
    midpoints_Fiber_vertical = []
    midpoints_Fiber_horizontal = []
    
    # Create Set-Fiber-Straightness
    if Arcs:
        for midpoint, seg_length in midpoints_lengths_Fiber_all:
            if midpoint[0] == 0 or midpoint[0] == a:
                midpoints_Fiber_vertical.append(midpoint)
            if midpoint[1] == 0 or midpoint[1] == b:
                midpoints_Fiber_horizontal.append(midpoint)
                
        if midpoints_Fiber_vertical:
            pickedEdges_Fiber_Straightness_vertical = p.edges.findAt(((t, midpoints_Fiber_vertical[0][1], -midpoints_Fiber_vertical[0][0]),))
            pickedEdges_vertical = p.edges.findAt(((0, midpoints_Fiber_vertical[0][1], -midpoints_Fiber_vertical[0][0]),))
            pickedEdges_Fiber_Straightness_vertical += pickedEdges_vertical
            for midpoint in midpoints_Fiber_vertical[1:]:
                pickedEdges_vertical = p.edges.findAt(((t, midpoint[1], -midpoint[0]),))
                pickedEdges_Fiber_Straightness_vertical += pickedEdges_vertical
                pickedEdges_vertical = p.edges.findAt(((0, midpoint[1], -midpoint[0]),))
                pickedEdges_Fiber_Straightness_vertical += pickedEdges_vertical
            
            p.Set(edges=pickedEdges_Fiber_Straightness_vertical, name='Set-Fiber-Straightness-vertical')
        
        if midpoints_Fiber_horizontal:
            pickedEdges_Fiber_Straightness_horizontal = p.edges.findAt(((t, midpoints_Fiber_horizontal[0][1], -midpoints_Fiber_horizontal[0][0]),))
            pickedEdges_horizontal = p.edges.findAt(((0, midpoints_Fiber_horizontal[0][1], -midpoints_Fiber_horizontal[0][0]),))
            pickedEdges_Fiber_Straightness_horizontal += pickedEdges_horizontal
            for midpoint in midpoints_Fiber_horizontal[1:]:
                pickedEdges_horizontal = p.edges.findAt(((t, midpoint[1], -midpoint[0]),))
                pickedEdges_Fiber_Straightness_horizontal += pickedEdges_horizontal
                pickedEdges_horizontal = p.edges.findAt(((0, midpoint[1], -midpoint[0]),))
                pickedEdges_Fiber_Straightness_horizontal += pickedEdges_horizontal
            
            p.Set(edges=pickedEdges_Fiber_Straightness_horizontal, name='Set-Fiber-Straightness-horizontal')
        
        if midpoints_Fiber_vertical and midpoints_Fiber_horizontal:
            pickedEdges_Fiber_Straightness = pickedEdges_Fiber_Straightness_vertical + pickedEdges_Fiber_Straightness_horizontal
            p.Set(edges=pickedEdges_Fiber_Straightness, name='Set-Fiber-Straightness')
        elif midpoints_Fiber_vertical and not midpoints_Fiber_horizontal:
            pickedEdges_Fiber_Straightness = pickedEdges_Fiber_Straightness_vertical
            p.Set(edges=pickedEdges_Fiber_Straightness, name='Set-Fiber-Straightness')
        elif not midpoints_Fiber_vertical and midpoints_Fiber_horizontal:
            pickedEdges_Fiber_Straightness = pickedEdges_Fiber_Straightness_horizontal
            p.Set(edges=pickedEdges_Fiber_Straightness, name='Set-Fiber-Straightness')
    
    # initialization
    pickedEdges = None
    
    ## Create Set-Arc
    if Arcs:
        # deal with the first element
        pickedEdges_Arc = p.edges.findAt(((0.0, Arcs[0][4][1], -Arcs[0][4][0]),))
        pickedEdges = p.edges.findAt(((t, Arcs[0][4][1], -Arcs[0][4][0]),))
        pickedEdges_Arc += pickedEdges
        # deal with others element
        for center, intersection_start, intersection_end, arc_length, Arc_midpoint_2D in Arcs[1:]:
            pickedEdges = p.edges.findAt(((0.0, Arc_midpoint_2D[1], -Arc_midpoint_2D[0]),))
            pickedEdges_Arc += pickedEdges
            pickedEdges = p.edges.findAt(((t, Arc_midpoint_2D[1], -Arc_midpoint_2D[0]),))
            pickedEdges_Arc += pickedEdges
        
        p.Set(edges=pickedEdges_Arc, name='Set-Arc')
        
    ## Create Set-Interface-Arc
        # deal with the first element
        pickedFaces_Arc = p.faces.findAt(((t/2, Arcs[0][4][1], -Arcs[0][4][0]),))
        pickedFaces = p.faces.findAt(((t/2, Arcs[0][4][1], -Arcs[0][4][0]),))
        pickedFaces_Arc += pickedFaces
        # deal with others element
        for center, intersection_start, intersection_end, arc_length, Arc_midpoint_2D, in Arcs[1:]:
            pickedFaces = p.faces.findAt(((t/2, Arc_midpoint_2D[1], -Arc_midpoint_2D[0]),))
            pickedFaces_Arc += pickedFaces
        
        p.Set(faces=pickedFaces_Arc, name='Set-Interface-Arc')
    
    ## Create Set-full-circle
    if full_circle_center:
        # deal with the first element
        value_full_circle_center = full_circle_center[0]
        point1 = (0.0, value_full_circle_center[1], -value_full_circle_center[0] - radius)
        point2 = (t, value_full_circle_center[1], -value_full_circle_center[0] - radius)
        pickedEdges_full_circle = p.edges.findAt((point1,), (point2,))
        # deal with others element
        for value_full_circle_center in full_circle_center[1:]:
            point1 = (0.0, value_full_circle_center[1], -value_full_circle_center[0] - radius)
            point2 = (t, value_full_circle_center[1], -value_full_circle_center[0] - radius)
            pickedEdges_full_circle += p.edges.findAt((point1,), (point2,))
        
        p.Set(edges=pickedEdges_full_circle, name='Set-full-circle')
        
    ## Create Set-Interface-full-circle
        # deal with the first element
        value_full_circle_center = full_circle_center[0]
        pointOnInterface_full_circle = (t/2, value_full_circle_center[1], -value_full_circle_center[0] - radius)
        pickedFaces_full_circle = p.faces.findAt((pointOnInterface_full_circle,))
        # deal with others element
        for value_full_circle_center in full_circle_center[1:]:
            pointOnInterface_full_circle = (t/2, value_full_circle_center[1], -value_full_circle_center[0] - radius)
            pickedFaces_full_circle += p.faces.findAt((pointOnInterface_full_circle,))
        p.Set(faces=pickedFaces_full_circle, name='Set-Interface-full-circle')
    
    ## Create Set-Interface
    if Arcs and full_circle_center:
        p.Set(faces=pickedFaces_Arc + pickedFaces_full_circle, name='Set-Interface')
    elif Arcs and not full_circle_center:
        p.Set(faces=pickedFaces_Arc, name='Set-Interface')
    elif full_circle_center and not Arcs:
        p.Set(faces=pickedFaces_full_circle, name='Set-Interface')
    else:
        pass

###############################################################################
############################ for Mesh Control #################################
###############################################################################
def MeshControl(modelName, mesh_seed_size_curve, mesh_seed_number, seeds_number_Z_line, 
                minSizeFactor_control, meshType, Model_range,
                useQuadratic=False, useReduced=False, useHybrid=False,
                useThermalQuadratic=False, useThermalReduced=False,
                useConvection=False, useDispersion=False, **kwargs):
    partName = 'UDComposite'
    # check input parameter
    check_mesh_parameters(modelName, mesh_seed_size_curve, mesh_seed_number, seeds_number_Z_line, minSizeFactor_control, meshType, Model_range)
    # Info output for console
    separator = "-" * 100
    # Mesh selected model only
    if Model_range == 1:
        meshPart = mdb.models[modelName].parts[partName]
        p = meshPart
        seed_by_Number(meshPart, seeds_number_Z_line, mesh_seed_size_curve, mesh_seed_number, minSizeFactor_control)
        elemType = getElementType(meshType, useQuadratic, useReduced, useHybrid,
                          useThermalQuadratic, useThermalReduced,
                          useConvection, useDispersion)
        c = p.cells
        pickedRegions = c[0:len(c)]
        applyMeshControls(p, meshType)
        p.setElementType(regions=(pickedRegions,), elemTypes=(elemType,))
        p.generateMesh()
        session.viewports['Viewport: 1'].partDisplay.setValues(mesh=ON)
        session.viewports['Viewport: 1'].setValues(displayedObject=p)
        # Print Information
        print(' ')
        print(separator)
        print('------------------------------------- Mesh Control Information -------------------------------------')
        print(separator)
        print("Successfully completed mesh generation for the model:")
        print("==> {}{}".format(modelName, partName))
        print(' ')
    # Mesh all models with the same name
    elif Model_range == 2:
        # recognise the last ‘_’ and extract the main name
        model_name_prefix = modelName.rsplit('_', 1)[0] + '_'
        ## print("Main name recognised: {}".format(model_name_prefix))
        mesh_count = 0
        # Iterate over all models and process
        for model_name in mdb.models.keys():
            if model_name.startswith(model_name_prefix):
                ## print("model_name:", model_name)
                model = mdb.models[model_name]
                p = model.parts[partName]
                seed_by_Number(p, seeds_number_Z_line, mesh_seed_size_curve, mesh_seed_number, minSizeFactor_control)
                elemType = getElementType(meshType, useQuadratic, useReduced, useHybrid,
                                  useThermalQuadratic, useThermalReduced,
                                  useConvection, useDispersion)
                c = p.cells
                pickedRegions = c[0:len(c)]
                applyMeshControls(p, meshType)
                p.setElementType(regions=(pickedRegions,), elemTypes=(elemType,))
                p.generateMesh()
                session.viewports['Viewport: 1'].partDisplay.setValues(mesh=ON)
                session.viewports['Viewport: 1'].setValues(displayedObject=p)
                ## print("Mesh generation for {} has been completed.".format(model_name))
                mesh_count += 1
        # Print Information
        print(' ')
        print(separator)
        print('------------------------------------- Mesh Control Information -------------------------------------')
        print(separator)
        print("Successfully completed mesh generation for all models with main name:")
        print("==> {}".format(model_name_prefix))
        print(' ')
    # Mesh user-selected models
    elif Model_range == 3:
        user_input = kwargs.get('someTextField')
        model_name_prefix = modelName.rsplit('_', 1)[0] + '_'
        ## print("Main name recognised: {}".format(model_name_prefix))
        # Parsing user input
        valid_selected_model_names = parse_user_input(user_input, model_name_prefix)
        # Generate model name list
        for model_name in mdb.models.keys():
            if model_name in valid_selected_model_names:
                model = mdb.models[model_name]
                p = model.parts[partName]
                seed_by_Number(p, seeds_number_Z_line, mesh_seed_size_curve, mesh_seed_number, minSizeFactor_control)
                elemType = getElementType(meshType, useQuadratic, useReduced, useHybrid,
                                  useThermalQuadratic, useThermalReduced,
                                  useConvection, useDispersion)
                c = p.cells
                pickedRegions = c[0:len(c)]
                applyMeshControls(p, meshType)
                p.setElementType(regions=(pickedRegions,), elemTypes=(elemType,))
                p.generateMesh()
                session.viewports['Viewport: 1'].partDisplay.setValues(mesh=ON)
                session.viewports['Viewport: 1'].setValues(displayedObject=p)
        # Print Information
        print(' ')
        print(separator)
        print('------------------------------------- Mesh Control Information -------------------------------------')
        print(separator)
        print("Successfully completed mesh generation for the user-selected model(s):")
        print("\n".join(["==> {}.".format(name) for name in valid_selected_model_names]))
        print(' ')
    # Information output
    print (' ')
    print ("Number of seeds for fiber circle:                             {}".format(mesh_seed_size_curve))
    print ("Number of seeds for the matrix rectangular cross-section:     Auto-calculated from fiber circle seeds")
    print ("Number of seeds along the matrix edge in fiber direction:     {}".format(seeds_number_Z_line))
    # Map meshType integer to a descriptive label for output
    meshType_label = {1: 'Thermal (DC3D8)', 2: 'Mechanical (C3D8)', 3: 'Thermo-Mechanical Coupled (C3D8T)'}
    print ("Element type used for mesh generation:                        {}".format(meshType_label.get(meshType, 'Unknown')))
    print (separator)
    print ("---------------------------- All Selected RVE Models Meshed Successfully ---------------------------")
    print (separator)
    print (' ')

# Feedback on Errors
def check_mesh_parameters(modelName, mesh_seed_size_curve, mesh_seed_number, seeds_number_Z_line, minSizeFactor_control, meshType, Model_range):
    if not modelName:
        raise ValueError("Please select a valid 'Model Name' from the dropdown!")
    if meshType not in [1, 2, 3]:
        raise ValueError("Please select a valid 'Mesh Type'! (1=Thermal, 2=Mechanical, 3=Coupled)")
    if Model_range not in [1, 2, 3]:
        raise ValueError("Please select model range for meshing!")
    return

# Mesh seed control -----------------------------------------------------------
def seed_by_Number(meshPart, seeds_number_Z_line, mesh_seed_size_curve, mesh_seed_number, minSizeFactor_control):
    global_seed_size = calculate_global_seed_size_from_curve_edges(meshPart, mesh_seed_size_curve)
    mesh_seed_size_horizontal = global_seed_size
    mesh_seed_size_vertical = global_seed_size
    ## print("Mesh Seed Size Horizontal: {}".format(mesh_seed_size_horizontal))
    ## print("Mesh Seed Size Vertical: {}".format(mesh_seed_size_vertical))
    
    # Seeding the edges in sets
    for set_name in meshPart.sets.keys():
        ## print("Processing set: {}".format(set_name))
        # Identifying sets, edges
        p = meshPart
        meshSet = p.sets[set_name]
        meshEdges = meshSet.edges
        # Seeds for straightness
        if set_name == 'Set-thickness-Straightness':
            ## print("Seeding thickness direction with number of seeds: {}".format(seeds_number_Z_line))
            p.seedEdgeByNumber(edges=meshEdges, number=seeds_number_Z_line, constraint=FIXED)
            ## print("thickness direction seeding has been completed.")
        elif set_name == 'Set-Matrix-Straightness-vertical':
            for edge_Matrix in meshEdges:
                segment_length = calculate_segment_length(meshPart, edge_Matrix)
                seeds_number_Matrix_vertical = calculate_N_Matrix(segment_length, mesh_seed_size_vertical, minSizeFactor_control)
                ## print("Matrix vertical segment length: {}, seeds number: {}".format(segment_length, seeds_number_Matrix_vertical))
                p.seedEdgeByNumber(edges=(edge_Matrix,), number=int(seeds_number_Matrix_vertical), constraint=FIXED)
        elif set_name == 'Set-Fiber-Straightness-vertical':
            for edge_Fiber in meshEdges:
                segment_length = calculate_segment_length(meshPart, edge_Fiber)
                seeds_number_Fiber_vertical = calculate_N_Fiber(segment_length, mesh_seed_size_vertical, minSizeFactor_control)
                ## print("Fiber vertical segment length: {}, seeds number: {}".format(segment_length, seeds_number_Fiber_vertical))
                p.seedEdgeByNumber(edges=(edge_Fiber,), number=int(seeds_number_Fiber_vertical), constraint=FIXED)
        elif set_name == 'Set-Matrix-Straightness-horizontal':  
            for edge_Matrix in meshEdges:
                segment_length = calculate_segment_length(meshPart, edge_Matrix)
                seeds_number_Matrix_horizontal = calculate_N_Matrix(segment_length, mesh_seed_size_horizontal, minSizeFactor_control)
                ## print("Matrix horizontal segment length: {}, seeds number: {}".format(segment_length, seeds_number_Matrix_horizontal))
                p.seedEdgeByNumber(edges=(edge_Matrix,), number=int(seeds_number_Matrix_horizontal), constraint=FIXED)
        elif set_name == 'Set-Fiber-Straightness-horizontal':
            for edge_Fiber in meshEdges:
                segment_length = calculate_segment_length(meshPart, edge_Fiber)
                seeds_number_Fiber_horizontal = calculate_N_Fiber(segment_length, mesh_seed_size_horizontal, minSizeFactor_control)
                ## print("Fiber horizontal segment length: {}, seeds number: {}".format(segment_length, seeds_number_Fiber_horizontal))
                p.seedEdgeByNumber(edges=(edge_Fiber,), number=int(seeds_number_Fiber_horizontal), constraint=FIXED)
        # Seeds for full circle
        elif set_name == 'Set-full-circle':
            for edge in meshEdges:
                p.seedEdgeByNumber(edges=meshEdges, number=mesh_seed_size_curve, constraint=FIXED)
                ## print("Full circles seeding have been completed with a seed count of {}.".format(mesh_seed_size_curve))
        
        # Seeds for Arc
        elif set_name == 'Set-Arc':
            for edge_arc in meshEdges:
                vertices = edge_arc.getVertices()
                vertex1_coords = meshPart.vertices[vertices[0]].pointOn[0]
                vertex2_coords = meshPart.vertices[vertices[1]].pointOn[0]
                midpoint_coords = edge_arc.pointOn[0]
                x1, y1, z1 = vertex1_coords
                x2, y2, z2 = vertex2_coords
                xm, ym, zm = midpoint_coords
                # Calculating the center and radius of a circle
                center, radius, angle_rad = calculate_circle_center_and_radius_in_YZ(x1, y1, z1, x2, y2, z2, xm, ym, zm)
                ## print("Arc center: {}, radius: {}, angle in radians: {}".format(center, radius, angle_rad))
                # Calculate the number of seeds on the arc
                #seeds_number_arc = int(mesh_seed_size_curve * (angle_rad / (2 * math.pi)) + 0.5)
                seeds_number_arc = max(int(mesh_seed_size_curve * (angle_rad / (2 * math.pi))) + 1, 2)
                ## print("Arc segment length, seeds number: {}".format(seeds_number_arc))
                # Seeds for the arc
                p.seedEdgeByNumber(edges=(edge_arc,), number=seeds_number_arc, constraint=FIXED)
    
    return

def calculate_global_seed_size_from_curve_edges(meshPart, mesh_seed_size_curve):
    if mesh_seed_size_curve <= 0:
        raise ValueError("Circle-dominant and Arc seed number must be greater than 0.")

    if 'Set-full-circle' in meshPart.sets.keys():
        for edge in meshPart.sets['Set-full-circle'].edges:
            try:
                circumference = edge.getSize()
                if circumference > 0:
                    return circumference / float(mesh_seed_size_curve)
            except:
                pass

    if 'Set-Arc' in meshPart.sets.keys():
        for edge_arc in meshPart.sets['Set-Arc'].edges:
            vertices = edge_arc.getVertices()
            vertex1_coords = meshPart.vertices[vertices[0]].pointOn[0]
            vertex2_coords = meshPart.vertices[vertices[1]].pointOn[0]
            midpoint_coords = edge_arc.pointOn[0]
            x1, y1, z1 = vertex1_coords
            x2, y2, z2 = vertex2_coords
            xm, ym, zm = midpoint_coords
            center, radius, angle_rad = calculate_circle_center_and_radius_in_YZ(x1, y1, z1, x2, y2, z2, xm, ym, zm)
            if radius > 0:
                return (2.0 * math.pi * radius) / float(mesh_seed_size_curve)

    raise ValueError("Unable to calculate global mesh size from Set-full-circle or Set-Arc.")

# Calculate the length of a line segment
def calculate_segment_length(meshPart, edge):
    segment_length = []
    # Get the vertices of an edge
    vertices = edge.getVertices()
    vertex1_coords = meshPart.vertices[vertices[0]].pointOn
    vertex2_coords = meshPart.vertices[vertices[1]].pointOn
    # Calculate the length of an edge
    x1, y1, z1 = vertex1_coords[0]
    x2, y2, z2 = vertex2_coords[0]
    segment_length = ((x2 - x1)**2 + (y2 - y1)**2 + (z2 - z1)**2)**0.5
    return segment_length

def calculate_segment_length_manually(meshPart, edge):
    vertices = edge.getVertices()
    vertex1_coords = meshPart.vertices[vertices[0]].pointOn
    vertex2_coords = meshPart.vertices[vertices[1]].pointOn
    x1, y1, z1 = vertex1_coords[0]
    x2, y2, z2 = vertex2_coords[0]
    segment_length = ((x2 - x1)**2 + (y2 - y1)**2 + (z2 - z1)**2)**0.5
    return segment_length

# Calculate arc geometry information
def calculate_circle_center_and_radius_in_YZ(x1, y1, z1, x2, y2, z2, xm, ym, zm):
    mid_y = (y1 + y2) / 2
    mid_z = (z1 + z2) / 2
    d_mid_to_arc = math.sqrt((ym - mid_y)**2 + (zm - mid_z)**2)
    chord_length = math.sqrt((y2 - y1)**2 + (z2 - z1)**2)
    # R = (h/2) + (l^2/8h)
    if d_mid_to_arc != 0:
        radius = (chord_length**2) / (8 * d_mid_to_arc) + d_mid_to_arc / 2
    else:
        radius = chord_length / 2
    # Calculate the center of the circle
    dy = ym - mid_y
    dz = zm - mid_z
    # Calculate the length of the direction vector
    direction_magnitude = math.sqrt(dy**2 + dz**2)
    
    if direction_magnitude == 0:
        return (x1, mid_y, mid_z), radius, math.pi
    # circle center
    yc = mid_y + (radius * dy / direction_magnitude)
    zc = mid_z + (radius * dz / direction_magnitude)
    # Automatic recognition of X-coordinates
    if x1 == 0:
        xc = 0
    else:
        xc = x1
    
    angle_rad = 2 * math.asin(chord_length / (2 * radius))
    vector_to_midpoint = (ym - yc, zm - zc)
    vector_to_vertex1 = (y1 - yc, z1 - zc)
    dot_product = vector_to_midpoint[0] * vector_to_vertex1[0] + vector_to_midpoint[1] * vector_to_vertex1[1]
    # small or large arc
    if dot_product > 0:
        # positive, small arc
        angle_rad = angle_rad
    else:
        # negative, great arc
        angle_rad = 2 * math.pi - angle_rad
    
    return (xc, yc, zc), radius, angle_rad
 
# Calculate the number of seeds
def calculate_N_Fiber(segment_length, mesh_seed_size_length, minSizeFactor_control):
    result_A = int(segment_length / mesh_seed_size_length + 0.5 + 1)
    result_B = int(segment_length / (mesh_seed_size_length * minSizeFactor_control) + 0.5 + 1)
    return (min(result_A, result_B))

def calculate_N_Matrix(segment_length, mesh_seed_size_length, minSizeFactor_control):
    result_A = int(segment_length / mesh_seed_size_length + 0.5 + 1)
    result_B = int(segment_length / (mesh_seed_size_length * minSizeFactor_control) + 0.5 + 1)
    return min(result_A, result_B)

# Processing model range
# Extracts the user-entered model serial number
def parse_user_input(user_input, model_name_prefix, model_name_suffix=''):
    if user_input is None:
        raise ValueError("Input is empty, please provide valid input.")
    selected_indices = []
    parts = user_input.split(',')
    for part in parts:
        part = part.strip()
        if '-' in part:
            try:
                start, end = map(int, part.split('-'))
                if start > end:
                    raise ValueError("Invalid range: {} > {}.".format(start, end))
                selected_indices.extend(range(start, end + 1))
            except ValueError:
                raise ValueError("Invalid range format: '{}'. Expected integer 'start-end'.".format(part))
        else:
            try:
                selected_indices.append(int(part))
            except ValueError:
                raise ValueError("Invalid number format: '{}' is not a valid input.".format(part))
    selected_model_names = ["{}{}{}".format(model_name_prefix, i, model_name_suffix) for i in selected_indices]
    valid_selected_model_names = []
    for model_name in selected_model_names:
        if model_name not in mdb.models.keys():
            print("Model not retrieved: {}".format(model_name))
        else:
            valid_selected_model_names.append(model_name) 
    if not valid_selected_model_names:
        raise ValueError("No valid models found based on the 'Selected numbers' input.")
    return valid_selected_model_names

def ensure_model_name_ends_with_numeric_suffix(model_name, context_label):
    try:
        suffix = model_name.rsplit('_', 1)[1]
    except Exception:
        raise ValueError("{} requires the selected model name to end with '_<number>'.".format(context_label))
    if not suffix.isdigit():
        raise ValueError("{} requires the selected model name to end with '_<number>'. Current model: {}".format(
            context_label, model_name))
    return

def split_model_index(model_name):
    """Split a model name into (prefix, number, suffix) around its model index.

    Handles two naming schemes:
      * plain models               '<base>_<N>'                 -> ('<base>_', N, '')
      * interface models           '<base>_cohesive_<N>_<lbl>'  -> ('<base>_cohesive_', N, '_<lbl>')
                                   '<base>_thermal_<N>_<lbl>'   -> ('<base>_thermal_',  N, '_<lbl>')

    For interface models the numeric model index sits BEFORE a trailing
    interface label (e.g. the debonding tag '_D000'), so a plain rsplit('_')
    would wrongly treat the label as the index. Returns None when no model
    index can be located.
    """
    import re
    m = re.match(r'^(?P<prefix>.*_(?:cohesive|thermal)_)(?P<num>\d+)(?P<suffix>_.*)?$', model_name)
    if m:
        return m.group('prefix'), m.group('num'), m.group('suffix') or ''
    m = re.match(r'^(?P<prefix>.*_)(?P<num>\d+)$', model_name)
    if m:
        return m.group('prefix'), m.group('num'), ''
    return None

# Generate model name
def generate_model_names(indices, prefix):
    return ['{}{}'.format(prefix, i) for i in indices]

def getElementType(meshType, useQuadratic=False, useReduced=False, useHybrid=False,
                   useThermalQuadratic=False, useThermalReduced=False, 
                   useConvection=False, useDispersion=False):
    """Get element type based on selections with correct thermal element naming
    
    Thermal elements in Abaqus:
    - DC3D8: Basic 8-node thermal element
    - DC3D8R: Reduced integration
    - DCC3D8: Convection/diffusion
    - DCC3D8D: Convection/diffusion with dispersion control
    - DC3D20: 20-node quadratic (no modifiers allowed)
    """
    
    import abaqusConstants  # Ensure module is imported
    
    if meshType == 1:  # Thermal analysis
        if useThermalQuadratic:
            # Quadratic thermal element - no modifiers allowed
            elemCode_str = 'DC3D20'
        else:
            # Linear thermal elements
            if useThermalReduced:
                # Reduced integration - cannot have C or D
                elemCode_str = 'DC3D8R'
            elif useConvection:
                # Convection/diffusion
                if useDispersion:
                    # Both C and D
                    elemCode_str = 'DCC3D8D'
                else:
                    # Only C
                    elemCode_str = 'DCC3D8'
            else:
                # Basic element
                elemCode_str = 'DC3D8'
        
        # Get element code from abaqusConstants
        try:
            elemCode = getattr(abaqusConstants, elemCode_str)
            print("Using thermal element type: {}".format(elemCode_str))
        except AttributeError:
            # Fallback to basic element if not found
            print("Warning: Element type {} not found, using DC3D8".format(elemCode_str))
            elemCode = getattr(abaqusConstants, 'DC3D8')
            
    elif meshType == 2:  # Mechanical analysis
        # Base element selection
        if useQuadratic:
            # Quadratic mechanical elements
            base_code = 'C3D20'
        else:
            # Linear mechanical elements
            base_code = 'C3D8'
        
        # Add modifiers for mechanical elements
        modifiers = ''
        if useReduced:
            modifiers += 'R'
        if useHybrid:
            modifiers += 'H'
        
        # Construct final element code
        elemCode_str = base_code + modifiers
        
        # Get element code from abaqusConstants
        try:
            elemCode = getattr(abaqusConstants, elemCode_str)
            print("Using mechanical element type: {}".format(elemCode_str))
        except AttributeError:
            # Fallback to base element if combination not valid
            print("Warning: Element type {} not found, using {}".format(elemCode_str, base_code))
            elemCode = getattr(abaqusConstants, base_code)
            
    else:  # Thermo-mechanical coupled (meshType == 3)
        # Base element selection
        if useQuadratic:
            # Quadratic coupled elements
            base_code = 'C3D20'
        else:
            # Linear coupled elements
            base_code = 'C3D8'
        
        # Add modifiers for coupled elements
        modifiers = ''
        if useReduced:
            modifiers += 'R'
        if useHybrid:
            modifiers += 'H'
        # Add T for temperature coupling
        modifiers += 'T'
        
        # Construct final element code
        elemCode_str = base_code + modifiers
        
        # Get element code from abaqusConstants
        try:
            elemCode = getattr(abaqusConstants, elemCode_str)
            print("Using coupled element type: {}".format(elemCode_str))
        except AttributeError:
            # Fallback to base coupled element if combination not valid
            print("Warning: Element type {} not found, using {}T".format(elemCode_str, base_code))
            elemCode = getattr(abaqusConstants, base_code + 'T')
    
    # Create element type object
    elemType = mesh.ElemType(elemCode=elemCode, elemLibrary=STANDARD)
    return elemType

def applyMeshControls(p, meshType):
    """Apply mesh controls (sweep technique and element shape) based on mesh type.
    All types use HEX_DOMINATED sweep, matching the original element_type behavior."""
    c = p.cells
    pickedRegions = c[0:len(c)]
    if meshType == 1:  # Thermal - use HEX_DOMINATED sweep like DC3D8+DC3D6 in old version
        p.setMeshControls(regions=pickedRegions, elemShape=HEX_DOMINATED,
                          technique=SWEEP, allowMapped=False, sizeGrowthRate=1.0)
    elif meshType == 2:  # Mechanical - HEX_DOMINATED sweep
        p.setMeshControls(regions=pickedRegions, elemShape=HEX_DOMINATED,
                          technique=SWEEP, allowMapped=False, sizeGrowthRate=1.0)
    else:  # Coupled - HEX_DOMINATED sweep
        p.setMeshControls(regions=pickedRegions, elemShape=HEX_DOMINATED,
                          technique=SWEEP, allowMapped=False, sizeGrowthRate=1.0)




###############################################################################
################################ for Material #################################
###############################################################################
def Material(model_for_material, fiber_material, matrix_material, Model_range_material, **kwargs):
    separator = "-" * 100
    # Set material selected model only
    if Model_range_material == 1:
        model = mdb.models[model_for_material]
        set_material_orientation_and_section(model, fiber_material, matrix_material)
        # Print Information
        print(' ')
        print(separator)
        print('------------------------------------- Set Material Information -------------------------------------')
        print(separator)
        print("Successfully completed set material for the model:")
        print("==> {}".format(model_for_material))
        # Information show
        print(' ')
        print(separator)
        print("---------------------- Selected RVE Model Materials have been Successfully Set ---------------------")
        print(separator)
        print(' ')
    # Set all material with the same name
    elif Model_range_material == 2:
        # create Section for the selected model
        model = mdb.models[model_for_material]
        set_material_orientation_and_section(model, fiber_material, matrix_material)
        # for other models
        model_name_prefix = model_for_material.rsplit('_', 1)[0] + '_'
        ## print("Main name recognised: {}".format(model_name_prefix))
        material_count = 1
        select_model = mdb.models[model_for_material]
        material_names = select_model.materials.keys()
        # Extracting material from existing models
        # Create a job to generate an odb file containing material information
        odb_file_name = export_materials_to_odb(model_for_material)
        # Reading material from the generated ODB file
        for model_name in mdb.models.keys():
            if model_name.startswith(model_name_prefix) and model_name != model_for_material:
                model = mdb.models[model_name]
                for material_name in material_names:
                    if material_name not in model.materials.keys():
                        # Creation of materials with the same name
                        # Reading material from the generated ODB file
                        ##material_list = mdb.models[model_name].materialsFromOdb(fileName=odb_file_name)
                        mdb.models[model_name].materialsFromOdb(fileName=odb_file_name)
                        # Print the name of the imported material
                        ##for material in material_list:
                        ##    print("Material imported from ODB: {}".format(material.name))
                        ##print("Material has been successfully imported into the model {}.".format(model_name))
                set_material_orientation_and_section(model, fiber_material, matrix_material)

                material_count += 1
        # Print Information
        print(' ')
        print(separator)
        print('------------------------------------- Set Material Information -------------------------------------')
        print(separator)
        print("Successfully completed set material for {} model with main name:".format(material_count))
        print("==> {}".format(model_name_prefix))
        # Information show
        print(' ')
        print(separator)
        print("------------------- All Selected RVE Models Materials have been Successfully Set -------------------")
        print(separator)
        print(' ')
        print("########## Error messages can be ignored. Just run the job to obtain material properties. ##########")
        print(' ')
    # Set material in user-selected models
    elif Model_range_material == 3:
        # create Section for the selected model
        model = mdb.models[model_for_material]
        set_material_orientation_and_section(model, fiber_material, matrix_material)
        material_count = 1
        # for other selected models
        user_input = kwargs.get('user_input')
        model_name_prefix = model_for_material.rsplit('_', 1)[0] + '_'
        ## print("Main name recognised: {}".format(model_name_prefix))
        select_model = mdb.models[model_for_material]
        material_names = select_model.materials.keys()
        odb_file_name = export_materials_to_odb(model_for_material)
        # Parsing user input
        valid_selected_model_names_material = parse_user_input(user_input, model_name_prefix)
        # Generate model name list
        for model_name in mdb.models.keys():
            if model_name in valid_selected_model_names_material and model_name != model_for_material:
                model = mdb.models[model_name]
                for material_name in material_names:
                    if material_name not in model.materials.keys():
                        # Creation of materials with the same name
                        mdb.models[model_name].materialsFromOdb(fileName=odb_file_name)   
                set_material_orientation_and_section(model, fiber_material, matrix_material)
                material_count += 1
        # Print Information
        print(' ')
        print(separator)
        print('------------------------------------- Set Material Information -------------------------------------')
        print(separator)
        print("Successfully completed set material for {} user-selected model(s):".format(material_count))
        print("\n".join(["==> {}.".format(name) for name in valid_selected_model_names_material]))
        # Information show
        print(' ')
        print(separator)
        print("------------------- All Selected RVE Models Materials have been Successfully Set -------------------")
        print(separator)
        print(' ')
        print("########## Error messages can be ignored. Just run the job to obtain material properties. ##########")
        print(' ')

def set_material_orientation_and_section(model, fiber_material, matrix_material):
    p = model.parts['UDComposite']
    region_fiber = regionToolset.Region(cells=p.sets['Set-Fiber'].cells)
    region_matrix = regionToolset.Region(cells=p.sets['Set-Matrix'].cells)
    region_material = regionToolset.Region(cells=region_fiber.cells + region_matrix.cells)
    # Set section
    model.HomogeneousSolidSection(name='FiberSection', material=fiber_material, thickness=None)
    model.HomogeneousSolidSection(name='MatrixSection', material=matrix_material, thickness=None)
    # Define material orientation
    p.MaterialOrientation(region=region_material, orientationType=GLOBAL, axis=AXIS_1, additionalRotationType=ROTATION_NONE, localCsys=None, fieldName='', stackDirection=STACK_3)
    # Assign sections to fiber
    p.SectionAssignment(region=region_fiber, sectionName='FiberSection', offset=0.0, offsetType=MIDDLE_SURFACE, offsetField='', thicknessAssignment=FROM_SECTION)
    # Assign sections to matrix
    p.SectionAssignment(region=region_matrix, sectionName='MatrixSection', offset=0.0, offsetType=MIDDLE_SURFACE, offsetField='', thicknessAssignment=FROM_SECTION)
    session.viewports['Viewport: 1'].setValues(displayedObject=p)
    session.viewports['Viewport: 1'].partDisplay.setValues(mesh=ON)
    cmap=session.viewports['Viewport: 1'].colorMappings['Material']
    session.viewports['Viewport: 1'].setColor(colorMapping=cmap)
    session.viewports['Viewport: 1'].disableMultipleColors()

# Extraction of material from selected models
def export_materials_to_odb(model_for_material):
    odb_file = os.path.join(os.getcwd(), f'UsetoCopyMaterial_{model_for_material}.odb')
    odb_file = odb_file.replace('\\', '/')
    job_for_material = f'UsetoCopyMaterial_{model_for_material}'
    mdb.Job(name=job_for_material, model=model_for_material, type=ANALYSIS)
    mdb.jobs[job_for_material].submit()
    mdb.jobs[job_for_material].waitForCompletion()
    del mdb.jobs[job_for_material]
    return odb_file

###############################################################################
#################################### for Void #################################
###############################################################################
def Void(model_for_void, part_for_void, target_vf_void, Model_range_void, **kwargs):
    separator = "-" * 100
    model_name_prefix = model_for_void.rsplit('_', 1)[0] + '_'
    
    # void distribution parameter
    void_distribution_method = kwargs.get('void_distribution_method', 1)
    void_distribution_value = kwargs.get('void_distribution_value', 0.5)
    
    # void size parameter ()
    void_size_method = kwargs.get('void_size_method', 1)
    void_theta_value = kwargs.get('void_theta_value', 5)
    
    # void priority parameter ()
    void_priority = kwargs.get('void_priority', 3)

    # ---- Void shape factor (beta) -- Phase 4 Step 1 ----
    void_beta_active      = kwargs.get('void_beta_active', False)
    void_beta_unified     = kwargs.get('void_beta_unified', 1)
    void_beta_value       = kwargs.get('void_beta_value', 1.0)
    void_beta_value_fiber = kwargs.get('void_beta_value_fiber', 1.0)
    void_beta_value_matrix= kwargs.get('void_beta_value_matrix', 1.0)
    void_beta_orientation = kwargs.get('void_beta_orientation', 1)
    void_theta_star_active= kwargs.get('void_theta_star_active', False)
    void_theta_star       = kwargs.get('void_theta_star', 0.0)

    # If unified-beta is selected, both fiber/matrix betas are set from the single value.
    if void_beta_active and int(void_beta_unified) == 1:
        void_beta_value_fiber  = float(void_beta_value)
        void_beta_value_matrix = float(void_beta_value)

    # Validate beta strictly positive when active.
    if void_beta_active:
        for _name, _val in (('beta', void_beta_value),
                            ('beta(fiber)', void_beta_value_fiber),
                            ('beta(matrix)', void_beta_value_matrix)):
            if _val is None or float(_val) <= 0.0:
                raise ValueError("ERROR: {} must be strictly positive, got {}.".format(_name, _val))

    # Bundle shape-factor kwargs so we forward them in one place.
    beta_kwargs = dict(
        void_beta_active       = void_beta_active,
        void_beta_value_fiber  = void_beta_value_fiber,
        void_beta_value_matrix = void_beta_value_matrix,
        void_beta_orientation  = void_beta_orientation,
        void_theta_star_active = void_theta_star_active,
        void_theta_star        = void_theta_star,
    )

    # theta=1w
    if void_size_method == 2 and void_theta_value == 1:
        if void_distribution_method == 2:  # Custom w
            if void_distribution_value != 0.0 and void_distribution_value != 1.0:
                raise ValueError(
                    "ERROR: When theta=1, w must be set to 0, 1, or Random.\n"
                    "Current w value: {:.2f}\n"
                    "Please set w to 0.0, 1.0, or choose Random distribution method.".format(
                        void_distribution_value))
    
    # Set void for selected model only
    if Model_range_void == 1:
        create_void_set(model_for_void, part_for_void, target_vf_void,
                       void_distribution_method, void_distribution_value,
                       void_size_method, void_theta_value, void_priority,
                       **beta_kwargs)

        print(' ')
        print(separator)
        print('------------------------------------- Set Void Information -------------------------------------')
        print(separator)
        print("Successfully completed inserting voids for the model:")
        print("==> {}".format(model_for_void))
    # Set void for all models with the same prefix
    elif Model_range_void == 2:
        void_count = 0
        for model_name in mdb.models.keys():
            if model_name.startswith(model_name_prefix):
                create_void_set(model_name, part_for_void, target_vf_void,
                              void_distribution_method, void_distribution_value,
                              void_size_method, void_theta_value, void_priority,
                              **beta_kwargs)
                void_count += 1

        print(' ')
        print(separator)
        print('------------------------------------- Set Void Information -------------------------------------')
        print(separator)
        print("Successfully completed inserting voids for {} models with main name:".format(void_count))
        print("==> {}".format(model_name_prefix))
    # Set void in user-selected models
    elif Model_range_void == 3:
        void_count = 0
        user_input_void = kwargs.get('user_input_void')

        valid_selected_model_names_void = parse_user_input(user_input_void, model_name_prefix)

        for model_name in mdb.models.keys():
            if model_name in valid_selected_model_names_void:
                create_void_set(model_name, part_for_void, target_vf_void,
                              void_distribution_method, void_distribution_value,
                              void_size_method, void_theta_value, void_priority,
                              **beta_kwargs)
                void_count += 1
        
        print(' ')
        print(separator)
        print('------------------------------------- Set Void Information -------------------------------------')
        print(separator)
        print("Successfully completed inserting voids for {} user-selected model(s):".format(void_count))
        print("\n".join(["==> {}.".format(name) for name in valid_selected_model_names_void]))
    
    print(' ')
    print(separator)
    print("--------------------------- Voids have been inserted for all selected models ---------------------------")
    print(separator)
    print(' ')

def create_void_set(model_for_void, part_for_void, target_vf_void,
                   void_distribution_method=1, void_distribution_value=0.5,
                   void_size_method=1, void_theta_value=5, void_priority=3,
                   fiber_coords=None, fiber_radius=None,
                   void_beta_active=False, void_beta_value_fiber=1.0,
                   void_beta_value_matrix=1.0, void_beta_orientation=1,
                   void_theta_star_active=False, void_theta_star=0.0):
    """
    Build the void set for one model. The optional void_beta_* arguments
    enable a non-spherical envelope bias for void growth (Phase 4 Step 1);
    when void_beta_active=False the legacy distance-only rule is used.
    """

    # Register the per-call beta context so the growth helpers can read it.
    set_active_void_beta_ctx(void_beta_active,
                             void_beta_value_fiber,
                             void_beta_value_matrix,
                             void_beta_orientation)
    try:
        return _create_void_set_impl(
            model_for_void, part_for_void, target_vf_void,
            void_distribution_method, void_distribution_value,
            void_size_method, void_theta_value, void_priority,
            fiber_coords, fiber_radius,
            void_beta_active, void_beta_value_fiber, void_beta_value_matrix,
            void_beta_orientation, void_theta_star_active, void_theta_star,
        )
    finally:
        clear_active_void_beta_ctx()


def _abaqus_label_tuple(labels):
    if labels is None:
        return ()
    if isinstance(labels, (str, bytes)):
        return (int(labels),)
    try:
        iterator = iter(labels)
    except TypeError:
        return (int(labels),)
    return tuple([int(label) for label in iterator if label is not None])


def _abaqus_label_list(labels):
    return list(_abaqus_label_tuple(labels))


def _normalize_void_element_lists(all_voids):
    for void_info in all_voids:
        void_info['elements'] = _abaqus_label_list(void_info.get('elements', []))
    return all_voids


def _cluster_has_near_fiber(cluster, is_elem_near_fiber):
    for element_label in cluster:
        if is_elem_near_fiber.get(element_label, False):
            return True
    return False


def _cluster_volume(cluster, elem_volumes):
    total = 0.0
    for element_label in cluster:
        total += elem_volumes.get(element_label, 0.0)
    return total


def _create_void_set_impl(model_for_void, part_for_void, target_vf_void,
                          void_distribution_method, void_distribution_value,
                          void_size_method, void_theta_value, void_priority,
                          fiber_coords, fiber_radius,
                          void_beta_active, void_beta_value_fiber,
                          void_beta_value_matrix, void_beta_orientation,
                          void_theta_star_active, void_theta_star):
    print("\n========== VOID INSERTION START ==========")
    print("Model: {}".format(model_for_void))
    if void_beta_active:
        print("  Beta shape factor: ACTIVE")
        print("    fiber-adjacent beta = {:.4f}".format(void_beta_value_fiber))
        print("    inter-matrix   beta = {:.4f}".format(void_beta_value_matrix))
        print("    orientation         = {}".format(
            'random SO(3)' if int(void_beta_orientation) == 1 else 'orthogonal'))
    if void_theta_star_active:
        print("  theta*: {:.4f} (mean voids per fiber)".format(void_theta_star))
    
    target_vf_void = target_vf_void / 100.0
    model = mdb.models[model_for_void]
    part = model.parts[part_for_void]
    
    # ==========  ==========
    work_dir = os.getcwd()  # 
    try:
        fiber_coords = extract_fiber_centers(
            part, 
            model_name=model_for_void, 
            work_dir=work_dir
        )
    except ValueError as e:
        print("\n" + "!" * 60)
        print("CRITICAL ERROR: {}".format(e))
        print("!" * 60)
        fiber_coords = None  # 
    
    # ========== 1.  ==========
    print("\n[Step 1] Creating element sets...")
    set_matrix_region = part.sets['Set-Matrix'].cells
    element_labels = []
    for cell in set_matrix_region:
        elements_in_cell = cell.getElements()
        for elem in elements_in_cell:
            element_labels.append(elem.label)
    
    if not element_labels:
        raise ValueError("No matrix elements found!")
    
    set_matrix_element = part.SetFromElementLabels(
        name='Set-Matrix-element',
        elementLabels=_abaqus_label_tuple(element_labels))
    #print("  Matrix elements: {}".format(len(element_labels)))
    
    set_fiber_region = part.sets['Set-Fiber'].cells
    fiber_element_labels = []
    for cell in set_fiber_region:
        elements_in_cell = cell.getElements()
        for elem in elements_in_cell:
            fiber_element_labels.append(elem.label)
    set_fiber_element = part.SetFromElementLabels(
        name='Set-Fiber-element',
        elementLabels=_abaqus_label_tuple(fiber_element_labels))
    #print("  Fiber elements: {}".format(len(fiber_element_labels)))
    
    # ========== 2.  ==========
    print("\n[Step 2] Creating air material...")
    if 'air' not in model.materials.keys():
        air_material = model.Material(name='air')
        air_material.Density(table=((1.0e-10, ),))
        air_material.Elastic(table=((0.101, 0.49),))
        air_material.Conductivity(table=((0.026, ), ))
    if 'air' not in model.sections.keys():
        model.HomogeneousSolidSection(name='air', material='air', thickness=None)
    #print("  Air material and section created.")
    
    # ========== 3.  ==========
    print("\n[Step 3] Calculating volumes...")
    matrix_element_labels = [element.label for element in set_matrix_element.elements]
    rve_volume = part.getVolume()
    matrix_volume = model.parts['Matrix'].getVolume()
    matrix_vf = matrix_volume / rve_volume
    
    #print("  RVE volume: {:.6e}".format(rve_volume))
    #print("  Matrix volume: {:.6e}".format(matrix_volume))
    #print("  Matrix Vf: {:.2f}%".format(matrix_vf * 100))
    
    if target_vf_void > matrix_vf:
        raise ValueError("Target void Vf ({:.2f}%) exceeds matrix Vf ({:.2f}%).".format(
            target_vf_void * 100, matrix_vf * 100))
    
    target_volume = rve_volume * target_vf_void
    #print("  Target void volume: {:.6e}".format(target_volume))
    
    # ========== 4.  +  ==========
    print("\n[Step 4] Classifying elements and calculating exact volumes...")
    # --- (1) Cache ALL node coordinates once: O(N_nodes) API cost ---
    # Avoid per-element sequenceFromLabels((n,))[0].coordinates calls.
    near_fiber_candidates = []
    inter_matrix_candidates = []
    element_volume_dict   = {}
    element_centroid_dict = {}
    element_nodes_dict    = {}
    
    node_coord_dict = {}
    for n in part.nodes:
        node_coord_dict[n.label] = np.array(n.coordinates)
    
    # --- (2) Cache fiber element node labels in one pass ---
    fiber_elements = part.sets['Set-Fiber-element'].elements
    fiber_nodes = set()
    
    # IMPORTANT: Also populate element_nodes_dict for fiber elements, so that
    # downstream code (CASE 1 classification at line ~3761) can look up each
    # fiber element's node set instead of getting a default empty set.
    for elem in fiber_elements:
        elem_node_labels = set([node.label for node in elem.getNodes()])
        element_nodes_dict[elem.label] = elem_node_labels   # <-- NEW
        fiber_nodes |= elem_node_labels                      # keep the flat union as before
    
    # --- (3) Fetch ALL matrix elements in ONE call (not one-by-one) ---
    matrix_elems_seq = part.elements.sequenceFromLabels(_abaqus_label_tuple(matrix_element_labels))
    

    
    for element in matrix_elems_seq:         # direct iteration — no repeated API lookup
        label     = element.label
        node_objs = element.getNodes()
        elem_node_labels = tuple([n.label for n in node_objs])
        elem_node_set    = set(elem_node_labels)
        element_nodes_dict[label] = elem_node_set
    
        # coords via pre-cached dict — pure Python dict lookups
        coords = np.array([node_coord_dict[nl] for nl in elem_node_labels])
        element_centroid_dict[label] = coords.mean(axis=0)
    
        # Geometric volume — C3D4 (4 nodes), C3D8 (8 nodes).
        # For C3D4: V = |det([v1-v0, v2-v0, v3-v0])| / 6
        # For C3D8: decompose into 6 tetrahedra from centroid, sum |det|/6
        # (see helper below)
        try:
            element_volume_dict[label] = _tet_or_hex_volume(coords)
        except NotImplementedError:
            # Fallback to Abaqus API for unusual element types (rare)
            elements_seq = part.elements.sequenceFromLabels(labels=_abaqus_label_tuple((label,)))
            select_region = regionToolset.Region(elements=elements_seq)
            element_volume_dict[label] = part.getMassProperties(regions=select_region)['volume']
            
        if elem_node_set & fiber_nodes:
            near_fiber_candidates.append(label)
        else:
            inter_matrix_candidates.append(label)
    
    #print("  Element volumes calculated: {} elements".format(len(element_volume_dict)))
    #print("  Near-fiber candidates: {}".format(len(near_fiber_candidates)))
    #print("  Inter-matrix candidates: {}".format(len(inter_matrix_candidates)))
    
    # ========== 5. ==========
    print("\n[Step 5] Building face-based element adjacency...")
    element_neighbors_dict = build_element_adjacency_by_face(part, matrix_element_labels, element_nodes_dict)
    print("  Adjacency built for {} elements.".format(len(element_neighbors_dict)))

    # ========== 6.  ==========
    print("\n[Step 6] Calculating void parameters...")
    volume_list = list(element_volume_dict.values())  # list
    avg_element_volume = np.mean(volume_list)
    print("  Average element volume: {:.6e}".format(avg_element_volume))
    
    if void_size_method == 1:  # 
        num_voids = max(1, int(target_volume / avg_element_volume / 3))
        target_single_void_volume = target_volume / num_voids
        void_theta_value = 'Random'  # ← 
    else:  #  (theta)
        num_voids = void_theta_value
        target_single_void_volume = target_volume / num_voids
    
    target_elements_per_void = max(1, int(target_single_void_volume / avg_element_volume + 0.5))
    
    #print("  Target number of voids: {}".format(num_voids))
    #print("  Target elements per void: {}".format(target_elements_per_void))
    #print("  Target single void volume: {:.6e}".format(target_single_void_volume))
    
    if void_distribution_method == 1:  # 
        target_near_ratio = None
        void_distribution_value = 'Random'  # ← 
        #print("  Distribution: Random")
    else:  # 
        target_near_ratio = void_distribution_value
        #print("  Distribution: Custom, w = {}".format(target_near_ratio))
    
    # ========== 7. Void Generation ==========
    print("\n[Step 7] Generating voids with seed growth algorithm...")
    _void_gen_start = time.time()

    all_voids, void_statistics = seed_growth_void_generation(
        part=part,
        matrix_element_labels=matrix_element_labels,
        near_fiber_candidates=near_fiber_candidates,
        inter_matrix_candidates=inter_matrix_candidates,
        element_volume_dict=element_volume_dict,
        element_centroid_dict=element_centroid_dict,
        element_neighbors_dict=element_neighbors_dict,
        fiber_nodes=fiber_nodes,
        fiber_element_labels=fiber_element_labels,
        target_volume=target_volume,
        num_voids=num_voids,
        target_elements_per_void=target_elements_per_void,
        target_near_ratio=target_near_ratio,
        void_distribution_value=void_distribution_value,
        void_theta_value=void_theta_value,
        void_priority=void_priority,
        avg_element_volume=avg_element_volume,
        element_nodes_dict=element_nodes_dict
    )

    _void_gen_elapsed = time.time() - _void_gen_start
    print("\n[Void Generation Time] {:.1f} s ({:.1f} min)".format(
        _void_gen_elapsed, _void_gen_elapsed / 60.0))
    
    # ========== 8.  ==========
    print("\n[Step 8] Creating void sets...")
    all_void_labels = []
    near_fiber_void_labels = []
    inter_matrix_void_labels = []
    
    all_voids = _normalize_void_element_lists(all_voids)
    all_voids = [v for v in all_voids if v['elements']]
    
    for void_info in all_voids:
        
        # 
        if not void_info['elements']:
            continue
        
        void_labels = void_info['elements']
        void_type = void_info['type']
        all_void_labels.extend(void_labels)
        
        if void_type == 'near_fiber':
            near_fiber_void_labels.extend(void_labels)
        else:
            inter_matrix_void_labels.extend(void_labels)
    
    #print("  Total void elements: {}".format(len(all_void_labels)))
    #print("  Near-fiber void elements: {}".format(len(near_fiber_void_labels)))
    #print("  Inter-matrix void elements: {}".format(len(inter_matrix_void_labels)))
    # 
    # 
    num_valid = void_statistics.get('num_valid_voids', void_statistics.get('num_voids', 0))
    num_total = void_statistics.get('num_voids', 0)
    
    if num_valid < num_total:
        print("  WARNING: Expected {} voids, but only {} are valid".format(
            num_total, num_valid))
    '''
    if void_statistics['num_valid_voids'] < void_statistics['num_voids']:
        print("  WARNING: Expected {} voids, but only {} are valid".format(
            void_statistics['num_voids'], void_statistics['num_valid_voids']))
    '''
    
    if all_void_labels:
        part.Set(elements=part.elements.sequenceFromLabels(_abaqus_label_tuple(all_void_labels)), name='Set-void')
        part.SectionAssignment(region=part.sets['Set-void'], sectionName='air')
        #print("  Set-void created and section assigned.")
        
        # 
        non_void_element_labels = list(set(matrix_element_labels) - set(all_void_labels))
        part.Set(elements=part.elements.sequenceFromLabels(labels=_abaqus_label_tuple(non_void_element_labels)), 
                 name='Set-Matrix-element-novoid')
        
        if near_fiber_void_labels:
            part.Set(elements=part.elements.sequenceFromLabels(_abaqus_label_tuple(near_fiber_void_labels)), 
                     name='Set-near-fiber-void')
            #print("  Set-near-fiber-void created.")
        
        if inter_matrix_void_labels:
            part.Set(elements=part.elements.sequenceFromLabels(_abaqus_label_tuple(inter_matrix_void_labels)), 
                     name='Set-inter-matrix-void')
            #print("  Set-inter-matrix-void created.")
            # ========== Create individual void sets ==========
        for void_idx, void_info in enumerate(all_voids):
            if not void_info['elements']:
                continue
            void_set_name = 'Set-void-{}'.format(void_idx + 1)
            part.Set(
                elements=part.elements.sequenceFromLabels(_abaqus_label_tuple(void_info['elements'])),
                name=void_set_name)
        #print("  Created {} individual void sets (Set-void-1 .. Set-void-{})".format(len(all_voids), len(all_voids)))
            
    else:
        print("  WARNING: No void elements generated!")
    
    # ========== RVE2D ==========
    bbox = part.queryGeometry()
    # 3D
    rve_x_3d = bbox['boundingBox'][1][0] - bbox['boundingBox'][0][0]  # X
    rve_y_3d = bbox['boundingBox'][1][1] - bbox['boundingBox'][0][1]  # Y
    rve_z_3d = bbox['boundingBox'][1][2] - bbox['boundingBox'][0][2]  # Z
    
    # ========== 2D ==========
    # 2Dx3D-Z2Dy3DY
    rve_a = rve_z_3d  # 2D = 3DZ
    rve_b = rve_y_3d  # 2D = 3DY
    rve_c = rve_x_3d  #  = 3DX
    
    if all_voids:
        if fiber_coords is not None:  # ←
            output_void_statistics(model_for_void, part, all_voids, void_statistics,
                              rve_volume, target_vf_void, element_volume_dict,
                              element_centroid_dict, near_fiber_candidates,
                              rve_a, rve_b, rve_c,  # ← 2D
                              void_distribution_method, void_distribution_value,
                              void_size_method, void_theta_value, void_priority,
                              fiber_coords,
                              element_nodes_dict=element_nodes_dict,
                              fiber_radius=fiber_radius)
        else:
            print("\n  Skipping detailed statistics (no fiber coordinates available)")
    
    # 
    if all_voids:
        actual_near_ratio = len(near_fiber_void_labels) / len(all_void_labels) if all_void_labels else 0
        
        #  sum(v['volume'] for v in all_voids)
        total_void_vol = 0.0
        for v in all_voids:
            total_void_vol += v['volume']
        actual_void_vf = total_void_vol / rve_volume * 100
        
        print("\n========== VOID INSERTION COMPLETE ==========")
        print("  Number of voids (theta): {}".format(len(all_voids)))
        print("  Actual void Vf: {:.4f}%".format(actual_void_vf))
        print("  Near-fiber ratio: {:.2f}%".format(actual_near_ratio * 100))
        print("  Inter-matrix ratio: {:.2f}%".format((1 - actual_near_ratio) * 100))
    print("=" * 50 + "\n")

def calculate_periodic_distance_3d(point1, point2, a, b, c):
    """
    3D
    
    Args:
        point1, point2:  (x, y, z)
        a, b, c: RVEx, y, z
    
    Returns:
        
    """
    dx = abs(point1[0] - point2[0])
    dy = abs(point1[1] - point2[1])
    dz = abs(point1[2] - point2[2])
    
    # 
    dx = min(dx, a - dx)
    dy = min(dy, b - dy)
    dz = min(dz, c - dz)
    
    return math.sqrt(dx**2 + dy**2 + dz**2)

def _tet_or_hex_volume(coords):
    """
    Fast geometric volume. coords: np.ndarray of shape (n_nodes, 3).
    Supports C3D4/C3D10 (tet), C3D6/C3D15 (wedge), C3D8 (hex).
    Quadratic elements use corner nodes only (adequate for near-straight edges).
    """
    n = len(coords)

    if n == 4:   # C3D4 linear tet
        v1, v2, v3 = coords[1] - coords[0], coords[2] - coords[0], coords[3] - coords[0]
        return abs(np.dot(v1, np.cross(v2, v3))) / 6.0

    if n == 10:  # C3D10 quadratic tet -- use 4 corner nodes (0,1,2,3)
        v1, v2, v3 = coords[1] - coords[0], coords[2] - coords[0], coords[3] - coords[0]
        return abs(np.dot(v1, np.cross(v2, v3))) / 6.0

    if n == 6:   # C3D6 linear wedge -- 3 tetrahedra decomposition
        # Abaqus C3D6 node order: 0-1-2 bottom triangle, 3-4-5 top triangle
        tets = ((0, 1, 2, 3), (1, 2, 3, 4), (2, 3, 4, 5))
        vol = 0.0
        for a, b, c, d in tets:
            v1, v2, v3 = coords[b] - coords[a], coords[c] - coords[a], coords[d] - coords[a]
            vol += abs(np.dot(v1, np.cross(v2, v3))) / 6.0
        return vol

    if n == 15:  # C3D15 quadratic wedge -- use 6 corner nodes (0..5)
        corners = coords[:6]
        tets = ((0, 1, 2, 3), (1, 2, 3, 4), (2, 3, 4, 5))
        vol = 0.0
        for a, b, c, d in tets:
            v1, v2, v3 = corners[b] - corners[a], corners[c] - corners[a], corners[d] - corners[a]
            vol += abs(np.dot(v1, np.cross(v2, v3))) / 6.0
        return vol

    if n == 8:   # C3D8 linear hex -- 6 tetrahedra decomposition
        tets = ((0,1,3,4),(1,2,3,6),(1,3,4,6),(3,4,6,7),(1,4,5,6),(3,4,7,6))
        vol = 0.0
        for a, b, c, d in tets:
            v1, v2, v3 = coords[b] - coords[a], coords[c] - coords[a], coords[d] - coords[a]
            vol += abs(np.dot(v1, np.cross(v2, v3))) / 6.0
        return vol

    if n == 20:  # C3D20 quadratic hex -- use 8 corner nodes (0..7)
        corners = coords[:8]
        tets = ((0,1,3,4),(1,2,3,6),(1,3,4,6),(3,4,6,7),(1,4,5,6),(3,4,7,6))
        vol = 0.0
        for a, b, c, d in tets:
            v1, v2, v3 = corners[b] - corners[a], corners[c] - corners[a], corners[d] - corners[a]
            vol += abs(np.dot(v1, np.cross(v2, v3))) / 6.0
        return vol

    # Last-resort fallback: Abaqus API for truly unknown element types.
    # This should rarely fire; if it does, the caller may log a warning.
    raise NotImplementedError("Unsupported element type with {} nodes".format(n))

# 
def will_create_island(new_element, current_void_elements, element_neighbors_dict,
                       matrix_element_labels):
    """"""
    test_void = set(current_void_elements) | {new_element}
    matrix_set = set(matrix_element_labels)
    non_void_matrix = matrix_set - test_void
    
    if len(non_void_matrix) == 0:
        return []  # 
    
    # BFS
    start = next(iter(non_void_matrix))
    visited = {start}
    queue = deque([start])
    
    while queue:
        current = queue.popleft()
        neighbors = element_neighbors_dict.get(current, set())
        
        for neighbor in neighbors:
            if neighbor in non_void_matrix and neighbor not in visited:
                visited.add(neighbor)
                queue.append(neighbor)
    
    # ****
    isolated = non_void_matrix - visited
    return list(isolated)

###
def will_isolate_fiber(new_element, current_void_elements, element_neighbors_dict,
                       fiber_elements, matrix_element_labels):
    """"""
    test_void = set(current_void_elements) | {new_element}
    matrix_set = set(matrix_element_labels)
    new_elem_neighbors = element_neighbors_dict.get(new_element, set())
    
    for neighbor in new_elem_neighbors:
        if neighbor in fiber_elements:
            fiber_neighbors = element_neighbors_dict.get(neighbor, set())
            matrix_neighbor_count = 0
            for fn in fiber_neighbors:
                if fn in matrix_set and fn not in test_void:
                    matrix_neighbor_count += 1
            if matrix_neighbor_count == 0:
                return True  # 
    return False  # 

### 
def build_element_adjacency_by_face(part, element_labels, element_nodes_dict):
    """
    Pure-Python adjacency build using a pre-cached {label: set(node_labels)} dict.
    No Abaqus API calls inside the loop — runs ~10-100x faster on large meshes.
    
    Adjacency rule: two elements are neighbors if they share >= 3 nodes
    (i.e. a full face for linear tet/hex elements).
    """
    label_set = set(element_labels)
    element_neighbors = {label: set() for label in element_labels}

    # Build node -> set(element labels) in one pass over the cached dict.
    node_to_elements = {}
    for label, node_set in element_nodes_dict.items():
        for nl in node_set:
            node_to_elements.setdefault(nl, set()).add(label)

    # For each element, find candidates that share any node, then test face contact.
    for label in element_labels:
        node_set = element_nodes_dict[label]
        potential = set()
        for nl in node_set:
            potential.update(node_to_elements.get(nl, ()))
        potential.discard(label)
        for nb in potential:
            if nb not in label_set:
                continue
            if len(node_set & element_nodes_dict[nb]) >= 3:
                element_neighbors[label].add(nb)
    return element_neighbors


def grow_single_void_with_face_check(seed_label, seed_type, element_volume_dict,
                                     element_centroid_dict, element_neighbors_dict,
                                     used_elements, target_elements, avg_element_volume,
                                     available_near_fiber, available_inter_matrix,
                                     void_priority, target_near_ratio, part, used_void_nodes,
                                     fiber_nodes, element_nodes_dict):
    """
    Grow a single void cluster from a seed element. When a beta shape factor
    is active (registered via set_active_void_beta_ctx), candidate weighting
    is biased by an ellipsoid envelope; otherwise the legacy distance-only
    rule is used.
    """
    
    void_elements = {seed_label}
    void_type = seed_type
    seed_centroid = element_centroid_dict[seed_label]
    
    target_volume = target_elements * avg_element_volume
    current_volume = element_volume_dict[seed_label]
    
    max_growth_iterations = int(target_elements) * 5
    
    # 
    strict_distribution = False
    if target_near_ratio is not None:
        if target_near_ratio == 0.0 or target_near_ratio == 1.0:
            strict_distribution = True
    
    # void
    current_void_nodes = set(element_nodes_dict.get(seed_label, set()))
    current_void_nodes |= element_nodes_dict.get(seed_label, set())

    # ---- Resolve the per-void envelope (beta shape factor) ----
    _beta_ctx = get_active_void_beta_ctx()
    if _beta_ctx is not None and _beta_ctx.get('active', False):
        if seed_type == 'near_fiber':
            beta_for_this_void = _beta_ctx['beta_fiber']
        else:
            beta_for_this_void = _beta_ctx['beta_matrix']
        envelope_axes   = _envelope_axes_for_beta(beta_for_this_void)
        rotation_matrix = _resolve_void_rotation(_beta_ctx.get('orientation_mode', 1),
                                                 beta_for_this_void)
        _use_beta_here  = True
    else:
        envelope_axes   = None
        rotation_matrix = None
        _use_beta_here  = False

    for grow_iter in range(max_growth_iterations):
        if current_volume >= target_volume:
            break
        
        rejected_in_this_growth = set()
        
        # 
        boundary_neighbors = set()
        for elem_label in void_elements:
            neighbors = element_neighbors_dict.get(elem_label, set())
            for neighbor in neighbors:
                if neighbor in void_elements or neighbor in used_elements:
                    continue
                
                # Use pre-cached node dict to check shared nodes with other voids
                neighbor_nodes = element_nodes_dict.get(neighbor, set())
                other_voids_nodes = used_void_nodes - current_void_nodes
                if neighbor_nodes & other_voids_nodes:
                    continue
                
                boundary_neighbors.add(neighbor)
        
        if not boundary_neighbors:
            break
        
        # 
        valid_candidates = []
        
        for neighbor in boundary_neighbors:
            is_near_fiber = neighbor in available_near_fiber
            
            if strict_distribution:
                if void_type == 'near_fiber' and not is_near_fiber:
                    continue
                elif void_type == 'inter_matrix' and is_near_fiber:
                    continue
                valid_candidates.append(neighbor)
            else:
                if void_priority == 1:
                    # Allow near-fiber voids to grow into inter-matrix elements freely.
                    # Void type is determined after growth by fiber contact, not during growth.
                    # Only restrict inter-matrix voids from touching near-fiber elements
                    # when strict_distribution is not active.
                    if void_type == 'inter_matrix' and is_near_fiber and target_near_ratio == 0.0:
                        # w=0: pure inter-matrix, strictly exclude fiber-adjacent elements
                        continue
                    valid_candidates.append(neighbor)
                elif void_priority == 2:
                    valid_candidates.append(neighbor)
                else:
                    valid_candidates.append(neighbor)
        
        if not valid_candidates:
            if void_priority == 2 and not strict_distribution:
                valid_candidates = list(boundary_neighbors)
            else:
                break
        
        if not valid_candidates:
            break
        
        available_candidates = [c for c in valid_candidates if c not in rejected_in_this_growth]
        
        if not available_candidates:
            break
        
        if _use_beta_here and envelope_axes is not None and rotation_matrix is not None:
            selected = beta_weighted_selection(
                valid_candidates, seed_centroid, element_centroid_dict,
                rotation_matrix, envelope_axes
            )
        else:
            selected = distance_weighted_selection_debug(
                valid_candidates, seed_centroid, element_centroid_dict
            )
        
        if selected is None:
            break
        
        # ==========  ==========
        if will_isolate_fiber(selected, void_elements, element_neighbors_dict,
                             fiber_nodes, set(element_volume_dict.keys())):
            rejected_in_this_growth.add(selected)
            continue
        
        new_volume = current_volume + element_volume_dict[selected]
        
        if new_volume > target_volume:
            diff_with = abs(new_volume - target_volume)
            diff_without = abs(current_volume - target_volume)
            if diff_with <= diff_without:
                # 
                if not will_isolate_fiber(selected, void_elements, element_neighbors_dict,
                                      fiber_nodes, set(element_volume_dict.keys())):
                    void_elements.add(selected)
                    current_volume = new_volume
                    
                    # 
                    try:
                        current_void_nodes.update(element_nodes_dict.get(selected, set()))
                        for node in sel_elem.getNodes():
                            current_void_nodes.add(node.label)
                    except:
                        pass
            break
        
        void_elements.add(selected)
        current_volume = new_volume
        
        # 
        try:
            current_void_nodes.update(element_nodes_dict.get(selected, set()))
            for node in sel_elem.getNodes():
                current_void_nodes.add(node.label)
        except:
            pass
        
        if void_priority == 2 and not strict_distribution:
            if selected in available_near_fiber:
                void_type = 'near_fiber'
    
    return void_elements, void_type

def _initialize_void_generation(near_fiber_candidates, inter_matrix_candidates, 
                                num_voids, target_near_ratio, void_size_method, void_theta_value):
    """"""
    all_voids = []
    used_elements = set()
    used_void_nodes = set()
    
    # 
    if target_near_ratio is not None:
        target_near_voids = int(num_voids * target_near_ratio + 0.5)
        target_inter_voids = num_voids - target_near_voids
    else:
        target_near_voids = None
        target_inter_voids = None
    
    current_near_voids = 0
    current_inter_voids = 0
    current_total_volume = 0.0
    
    available_near_fiber = set(near_fiber_candidates)
    available_inter_matrix = set(inter_matrix_candidates)
    
    # 
    strict_count_control = (void_size_method == 2)
    
    return {
        'all_voids': all_voids,
        'used_elements': used_elements,
        'used_void_nodes': used_void_nodes,
        'target_near_voids': target_near_voids,
        'target_inter_voids': target_inter_voids,
        'current_near_voids': current_near_voids,
        'current_inter_voids': current_inter_voids,
        'current_total_volume': current_total_volume,
        'available_near_fiber': available_near_fiber,
        'available_inter_matrix': available_inter_matrix,
        'strict_count_control': strict_count_control
    }

def _finalize_void_statistics(all_voids, element_neighbors_dict=None, element_volume_dict=None, element_centroid_dict=None):
    """
    voids
    
    
        valid_voids: voids
        void_statistics: 
    """
    # voids
    valid_voids = [v for v in all_voids if v['elements']]
    
    if not valid_voids:
        # voids
        void_statistics = {
            'num_voids': 0,
            'num_valid_voids': 0,
            'num_near_fiber': 0,
            'num_inter_matrix': 0,
            'total_volume': 0.0,
            'near_fiber_volume': 0.0,
            'inter_matrix_volume': 0.0,
            'realized_w': 0.0,
            'volumes': [],
            'centroids': []
        }
        return valid_voids, void_statistics
    
    # ========== voids ==========
    # ========== Separate connected voids instead of merging ==========
    if element_neighbors_dict is not None:
        print("\n--- Checking and separating connected voids ---")
        
        max_separation_rounds = 30
        for sep_round in range(max_separation_rounds):
            # Build element -> void index mapping
            all_void_elements = set()
            elem_to_void_idx = {}
            for idx, v in enumerate(valid_voids):
                for elem in v['elements']:
                    all_void_elements.add(elem)
                    elem_to_void_idx[elem] = idx
            
            # Find bridge elements: elements face-adjacent to a different void
            bridges = []  # (void_idx, elem_id, neighbor_void_idx)
            for idx, v in enumerate(valid_voids):
                for elem in v['elements']:
                    for nb in element_neighbors_dict.get(elem, set()):
                        if nb in all_void_elements:
                            nb_idx = elem_to_void_idx[nb]
                            if nb_idx != idx:
                                bridges.append((idx, elem, nb_idx))
            
            if not bridges:
                print("   No connected voids detected (round {})".format(sep_round + 1))
                break
            
            # Group bridges by void pair
            pair_bridges = {}
            for v_idx, elem, nb_idx in bridges:
                pair_key = (min(v_idx, nb_idx), max(v_idx, nb_idx))
                if pair_key not in pair_bridges:
                    pair_bridges[pair_key] = []
                pair_bridges[pair_key].append((v_idx, elem))
            
            print("   Round {}: found {} connected void pairs".format(
                sep_round + 1, len(pair_bridges)))
            
            # Compute target volume per void for balanced separation
            total_vol = sum([v['volume'] for v in valid_voids if v['elements']])
            num_valid = len([v for v in valid_voids if v['elements']])
            avg_vol = total_vol / max(num_valid, 1)
            
            removed_any = False
            for (idx_a, idx_b), bridge_list in pair_bridges.items():
                va = valid_voids[idx_a]
                vb = valid_voids[idx_b]
                
                # Remove from whichever is MORE above average (or less below)
                # This pushes both voids toward the average size
                dev_a = va['volume'] - avg_vol
                dev_b = vb['volume'] - avg_vol
                if dev_a >= dev_b:
                    remove_from_idx = idx_a
                else:
                    remove_from_idx = idx_b
                
                remove_void = valid_voids[remove_from_idx]
                remove_set = set(remove_void['elements'])
                
                # Find elements in remove_void that are face-adjacent to the other void
                elems_to_remove = set()
                for v_idx, elem in bridge_list:
                    if v_idx == remove_from_idx:
                        elems_to_remove.add(elem)
                
                if not elems_to_remove:
                    # Bridge is on the other side; collect from the other direction
                    other_idx = idx_b if remove_from_idx == idx_a else idx_a
                    other_set = set(valid_voids[other_idx]['elements'])
                    for elem in remove_void['elements']:
                        for nb in element_neighbors_dict.get(elem, set()):
                            if nb in other_set:
                                elems_to_remove.add(elem)
                                break
                
                # Remove bridge elements one by one, checking connectivity
                for elem in list(elems_to_remove):
                    remaining = remove_set - {elem}
                    if not remaining:
                        continue  # Don't empty the void
                    if _is_connected(remaining, element_neighbors_dict):
                        remove_void['elements'].remove(elem)
                        remove_set = remaining
                        removed_any = True
                
                # Recalculate volume and centroid
                if remove_void['elements']:
                    remove_void['volume'] = sum(
                        [element_volume_dict.get(e, 0.0) for e in remove_void['elements']])
                    remove_void['centroid'] = np.mean(
                        [element_centroid_dict[e] for e in remove_void['elements']], axis=0)
            
            if not removed_any:
                print("   Cannot separate further — accepting result")
                break
        
        # Remove any voids that became empty
        valid_voids = [v for v in valid_voids if v['elements']]
        print("   Final void count after separation: {}".format(len(valid_voids)))
    
    # ==========  ==========
    num_near_fiber = 0
    num_inter_matrix = 0
    near_fiber_volume = 0.0
    inter_matrix_volume = 0.0
    total_volume = 0.0
    volumes = []
    centroids = []
    
    for v in valid_voids:
        # 
        if v['type'] == 'near_fiber':
            num_near_fiber += 1
            near_fiber_volume += v['volume']
        else:
            num_inter_matrix += 1
            inter_matrix_volume += v['volume']
        
        # 
        total_volume += v['volume']
        volumes.append(v['volume'])
        centroids.append(v['centroid'])
    
    # ========== w ==========
    if total_volume > 0:
        realized_w = near_fiber_volume / total_volume
    else:
        realized_w = 0.0
    
    # ==========  ==========
    void_statistics = {
        'num_voids': len(valid_voids),
        'num_valid_voids': len(valid_voids),
        'num_near_fiber': num_near_fiber,
        'num_inter_matrix': num_inter_matrix,
        'total_volume': total_volume,
        'near_fiber_volume': near_fiber_volume,
        'inter_matrix_volume': inter_matrix_volume,
        'realized_w': realized_w,  # ← w
        'volumes': volumes,
        'centroids': centroids
    }
    
    return valid_voids, void_statistics

#==============================================================================
# 
#==============================================================================
def cluster_adjacent_void_elements(void_set, elem_neighbors):
    """
    clusters
    
    
        void_set: set of void element IDs
        elem_neighbors: dict {elem_id: set of neighbor IDs}
    
    
        clusters: list of sets, setcluster
                 : [{1,2,3}, {5,6}, {10}]
    """
    visited = set()
    clusters = []
    
    for void_elem in void_set:
        if void_elem in visited:
            continue
        
        # BFSvoid
        cluster = set()
        queue = deque([void_elem])
        
        while queue:
            current = queue.popleft()   # O(1)
            if current in visited:
                continue
            
            visited.add(current)
            cluster.add(current)
            
            # void
            if current in elem_neighbors:
                for neighbor in elem_neighbors[current]:
                    if neighbor in void_set and neighbor not in visited:
                        queue.append(neighbor)
        
        clusters.append(cluster)
    
    return clusters

# ========== voids ==========
def try_remove_elements_from_voids(all_voids, element_volume_dict, element_centroid_dict,
                                   element_neighbors_dict, used_elements, used_void_nodes, part):
    """
    voids
    
    voidtheta
    
    TrueFalse
    """
    # void
    all_voids.sort(key=lambda v: v['volume'], reverse=True)
    
    for void_info in all_voids:
        if len(void_info['elements']) <= 1:
            continue  # 
        
        void_elements = set(void_info['elements'])
        
        # void
        edge_elements = []
        for elem_id in void_elements:
            neighbors = element_neighbors_dict.get(elem_id, set())
            neighbors_in_void = neighbors & void_elements
            neighbors_outside_void = neighbors - void_elements
            
            if len(neighbors_outside_void) > 0:
                edge_elements.append(elem_id)
        
        if not edge_elements:
            continue
        
        # 
        edge_elements.sort(key=lambda e: element_volume_dict.get(e, 0.0), reverse=True)
        
        for candidate in edge_elements:
            # void
            remaining_void = void_elements - {candidate}
            
            if not _is_connected(remaining_void, element_neighbors_dict):
                continue  # 
            
            # 
            # 
            
            # 
            void_info['elements'].remove(candidate)
            void_info['volume'] -= element_volume_dict.get(candidate, 0.0)
            
            # used_elements
            used_elements.discard(candidate)
            
            # used_void_nodes
            elem_nodes = element_nodes_dict.get(candidate, set())
            
            # void
            for node_label in elem_nodes:
                still_used = False
                for other_void in all_voids:
                    for other_elem_id in other_void['elements']:
                        if other_elem_id == candidate:
                            continue
                        try:
                            other_nodes = element_nodes_dict.get(other_elem_id, set())
                            if node_label in other_nodes:
                                still_used = True
                                break
                        except:
                            continue
                    if still_used:
                        break
                
                if not still_used:
                    used_void_nodes.discard(node_label)
            
            # 
            if len(void_info['elements']) > 0:
                void_info['centroid'] = np.mean(
                    [element_centroid_dict[e] for e in void_info['elements']], axis=0)
            
            return True  # 
    
    return False  # 

# ======================================================================
#  - 2829
# ======================================================================

def post_process_islands_and_volume(all_voids, element_neighbors_dict, element_volume_dict,
                                    element_centroid_dict, matrix_element_labels, part,
                                    target_volume, used_elements, fiber_nodes, fiber_element_labels, element_nodes_dict=None):
    """
    99%-101%
    """
    
    #print("\n========== POST-PROCESSING: ISLAND DETECTION & VOLUME ADJUSTMENT ==========")
    
    volume_lower = target_volume * 0.99
    volume_upper = target_volume * 1.01
    
    max_iterations = 100
    consecutive_no_islands = 0
    
    all_matrix_elements = set(matrix_element_labels) if isinstance(matrix_element_labels, list) else matrix_element_labels
    all_fiber_elements = set(fiber_element_labels) if isinstance(fiber_element_labels, list) else fiber_element_labels
    
    # ========== A ==========
    #print("\n--- Phase A: Aggressive Island Elimination ---")
    
    for iteration in range(80):
        #print("\n  === Iteration {} / 30 (Aggressive) ===".format(iteration + 1))
        
        islands = _detect_islands(all_voids, element_neighbors_dict, 
                                 all_matrix_elements, all_fiber_elements)
        
        if not islands:
            consecutive_no_islands += 1
            #print("    No islands detected (consecutive: {})".format(consecutive_no_islands))
            
            if consecutive_no_islands >= 5:
                #print("\n    Phase A complete: No islands!")
                break
        else:
            consecutive_no_islands = 0
            # ==========  ==========
            total_island_elements = 0
            for isl in islands:
                total_island_elements += len(isl)
            
            island_sizes = []
            for isl in islands:
                island_sizes.append(len(isl))
            
            #print("    Found {} island(s), total {} elements".format(
            #    len(islands), total_island_elements))
            #print("    Sizes: {}".format(island_sizes))
            
            for idx, island in enumerate(islands):
                # Skip fake islands: regions where all elements are already void
                # (caused by fiber regions splitting the matrix into sub-domains)
                real_island = [e for e in island if e not in used_elements]
                if not real_island:
                    continue
                _fill_island(island, all_voids, element_volume_dict, element_centroid_dict,
                            used_elements, element_neighbors_dict, fiber_nodes, all_matrix_elements, element_nodes_dict)
            
            # ==========  ==========
            for void_info in all_voids:
                if void_info['elements']:
                    volume_list = []
                    for e in void_info['elements']:
                        volume_list.append(element_volume_dict.get(e, 0.0))
                    void_info['volume'] = sum(volume_list)
                    
                    centroid_list = []
                    for e in void_info['elements']:
                        centroid_list.append(element_centroid_dict[e])
                    void_info['centroid'] = np.mean(centroid_list, axis=0)
    
    # ========== Phase B: Final island check only — volume deferred to Phase 3 ==========
    final_islands = _detect_islands(all_voids, element_neighbors_dict,
                                   all_matrix_elements, all_fiber_elements)

    if final_islands:
        for idx, island in enumerate(final_islands):
            real_island = [e for e in island if e not in used_elements]
            if not real_island:
                continue
            _fill_island(island, all_voids, element_volume_dict, element_centroid_dict,
                        used_elements, element_neighbors_dict, fiber_nodes, all_matrix_elements, element_nodes_dict)
        for void_info in all_voids:
            if void_info['elements']:
                void_info['volume'] = sum([element_volume_dict.get(e, 0.0) for e in void_info['elements']])
                void_info['centroid'] = np.mean(
                    [element_centroid_dict[e] for e in void_info['elements']], axis=0)
    else:
        print("    SUCCESS: No islands detected")
    
    # ==========  ==========
    #print("\n========== FINAL VERIFICATION ==========")
    
    final_islands = _detect_islands(all_voids, element_neighbors_dict,
                                   all_matrix_elements, all_fiber_elements)
    
    volume_list = []
    for v in all_voids:
        if v['elements']:
            volume_list.append(v['volume'])
    final_volume = sum(volume_list)
    
    final_vf_pct = (final_volume / target_volume) * 100
    
    #print("  Final volume: {:.2f}% of target".format(final_vf_pct))
    
    if final_islands:
        total_island_elem = 0
        for isl in final_islands:
            total_island_elem += len(isl)
        
        island_sizes = []
        for isl in final_islands:
            island_sizes.append(len(isl))
        
        #print("    CRITICAL: {} island(s) remain after 50 iterations!".format(len(final_islands)))
        #print("    Island sizes: {}".format(island_sizes))
        #print("    Total island elements: {}".format(total_island_elem))
    else:
        print("    SUCCESS: No islands detected")
    
    if final_volume >= volume_lower and final_volume <= volume_upper:
        print("    SUCCESS: Volume within tolerance")
    else:
        print("    WARNING: Volume outside tolerance")
    
    print("=" * 70 + "\n")
    
    return all_voids

def post_process_volume_only(all_voids, element_neighbors_dict, element_volume_dict,
                             element_centroid_dict, matrix_element_labels,
                             target_volume, used_elements):
    """
    Lightweight post-processing for pure inter-matrix voids (w~0).
    Skips island BFS entirely. Volume convergence is handled by Phase 3.
    """
    # Just report current state — no adjustment needed here.
    total_volume = sum([v['volume'] for v in all_voids if v['elements']])
    volume_lower = target_volume * 0.99
    volume_upper = target_volume * 1.01

    print("    Current volume: {:.2f}% of target (fine-tuning deferred to Phase 3)".format(
        total_volume / target_volume * 100))

    if total_volume >= volume_lower and total_volume <= volume_upper:
        print("    Volume already within tolerance")
    print("=" * 70 + "\n")

    return all_voids

def _detect_islands(all_voids, element_neighbors_dict, all_matrix_elements, all_fiber_elements):
    """
    will_create_island
    
    voidfibermatrix
    """
    all_void_elements = set()
    for v in all_voids:
        all_void_elements.update(v['elements'])
    
    # void
    non_void_matrix = all_matrix_elements - all_void_elements
    
    if len(non_void_matrix) == 0:
        return []
    
    # ========== will_create_islandBFS ==========
    visited = set()
    regions = []
    
    for start_elem in non_void_matrix:
        if start_elem in visited:
            continue
        
        # BFS
        region = set()
        queue = deque([start_elem])
        
        while queue:
            current = queue.popleft()
            if current in visited:
                continue
            
            visited.add(current)
            region.add(current)
            
            # 
            neighbors = element_neighbors_dict.get(current, set())
            
            for neighbor in neighbors:
                # voidmatrix
                # fibervoid
                if (neighbor in non_void_matrix and 
                    neighbor not in visited and
                    neighbor not in all_fiber_elements):  # fiber
                    queue.append(neighbor)
        
        if region:
            regions.append(region)
    
    if not regions:
        return []
    
    # ==========  ==========
    regions.sort(key=len, reverse=True)
    
    # RVE
    main_region = regions[0]
    
    # 
    # 
    has_boundary_contact = False
    for elem_id in list(main_region)[:100]:  # 
        try:
            elem = None
            # part
            # 
            has_boundary_contact = True
            break
        except:
            has_boundary_contact = True
            break
    
    # 
    islands = regions[1:] if len(regions) > 1 else []
    
    # ==========  ==========
    verified_islands = []
    for island in islands:
        # voidfiber
        is_truly_isolated = True
        
        for elem_id in island:
            neighbors = element_neighbors_dict.get(elem_id, set())
            
            # 
            if neighbors & main_region:
                is_truly_isolated = False
                break
        
        if is_truly_isolated and len(island) > 0:
            verified_islands.append(island)
    
    return verified_islands

def _fill_island(island, all_voids, element_volume_dict, element_centroid_dict, 
                 used_elements, element_neighbors_dict, fiber_nodes, all_matrix_elements,
                 element_nodes_dict=None):
    """
    void
    """
    if not island:
        return
    
    #print("      Island size: {} elements".format(len(island)))
    
    # 
    island_centroids = []
    for elem_id in island:
        if elem_id in element_centroid_dict:
            island_centroids.append(element_centroid_dict[elem_id])
    
    if not island_centroids:
        #print("        WARNING: Cannot compute island centroid")
        return
    
    island_centroid = np.mean(island_centroids, axis=0)
    
    # void
    min_dist = float('inf')
    closest_idx = 0
    
    for idx, void_info in enumerate(all_voids):
        if not void_info['elements']:
            continue
        
        dist = np.linalg.norm(island_centroid - void_info['centroid'])
        if dist < min_dist:
            min_dist = dist
            closest_idx = idx
    
    if not all_voids[closest_idx]['elements']:
        #print("        WARNING: Closest void is empty")
        return
    
    # 
    filled_count = 0
    skipped_count = 0
    
    # Build set of all current void elements and nodes for isolation check
    all_void_elements_now = set()
    all_void_nodes_now = set()
    for idx, vi in enumerate(all_voids):
        if idx != closest_idx:
            all_void_elements_now.update(vi['elements'])
            for oe in vi['elements']:
                all_void_nodes_now.update(element_nodes_dict.get(oe, set()))

    for elem_id in island:
        if elem_id in used_elements:
            skipped_count += 1
            continue

        # Skip if this element is face-adjacent to any OTHER void
        elem_neighbors = element_neighbors_dict.get(elem_id, set())
        if elem_neighbors & all_void_elements_now:
            skipped_count += 1
            continue

        # Skip if this element shares any node with any OTHER void
        elem_nodes = element_nodes_dict.get(elem_id, set())
        if elem_nodes & all_void_nodes_now:
            skipped_count += 1
            continue

        all_voids[closest_idx]['elements'].append(elem_id)
        used_elements.add(elem_id)
        # Keep all_void_elements_now updated so subsequent elements in same island
        # are also checked correctly
        all_void_elements_now.add(elem_id)
        filled_count += 1
    
    if filled_count > 0:
        # ==========  ==========
        volume_list = []
        for e in all_voids[closest_idx]['elements']:
            volume_list.append(element_volume_dict.get(e, 0.0))
        all_voids[closest_idx]['volume'] = sum(volume_list)
        
        if all_voids[closest_idx]['elements']:
            centroid_list = []
            for e in all_voids[closest_idx]['elements']:
                centroid_list.append(element_centroid_dict[e])
            all_voids[closest_idx]['centroid'] = np.mean(centroid_list, axis=0)
        
        #print("          Filled {} elements into void {}".format(filled_count, closest_idx))
    
    if skipped_count > 0:
        print("        - Skipped {} already-used elements".format(skipped_count))

def _remove_edge_element(all_voids, element_neighbors_dict, element_volume_dict, all_matrix_elements):
    """"""
    all_voids.sort(key=lambda v: v['volume'], reverse=True)
    
    for void_info in all_voids:
        if len(void_info['elements']) <= 1:
            continue
        
        void_elements = set(void_info['elements'])
        
        # 
        edge_elements = []
        for elem_id in void_elements:
            neighbors = element_neighbors_dict.get(elem_id, set())
            if neighbors - void_elements:
                edge_elements.append(elem_id)
        
        if not edge_elements:
            continue
        
        edge_elements.sort(key=lambda e: element_volume_dict.get(e, 0.0), reverse=True)
        
        for candidate in edge_elements:
            remaining = void_elements - {candidate}
            
            # 
            if not _is_connected(remaining, element_neighbors_dict):
                continue
            
            # 
            if _would_create_island(candidate, void_elements, element_neighbors_dict, all_matrix_elements):
                continue
            
            # 
            void_info['elements'].remove(candidate)
            void_info['volume'] -= element_volume_dict.get(candidate, 0.0)
            return True
    
    return False

def _add_edge_element(all_voids, element_neighbors_dict, element_volume_dict,
                     element_centroid_dict, all_matrix_elements, used_elements,
                     element_nodes_dict=None):
    """"""
    all_voids.sort(key=lambda v: v['volume'])
    
    all_void_elements = set()
    for v in all_voids:
        all_void_elements.update(v['elements'])
    
    for void_info in all_voids:
        void_elements = set(void_info['elements'])
        
        # 
        boundary = set()
        for elem_id in void_elements:
            neighbors = element_neighbors_dict.get(elem_id, set())
            for neighbor in neighbors:
                if neighbor in all_matrix_elements and neighbor not in all_void_elements and neighbor not in used_elements:
                    boundary.add(neighbor)
        
        if not boundary:
            continue
        
        candidates = list(boundary)
        random.shuffle(candidates)
        
        # Build other-void node set for strict isolation
        other_void_nodes = set()
        if element_nodes_dict is not None:
            for ov in all_voids:
                if set(ov['elements']) != void_elements:
                    for oe in ov['elements']:
                        other_void_nodes.update(element_nodes_dict.get(oe, set()))

        for candidate in candidates:
            # Check candidate is not face-adjacent to any OTHER void
            candidate_neighbors = element_neighbors_dict.get(candidate, set())
            touches_other_void = False
            for nb in candidate_neighbors:
                if nb in all_void_elements and nb not in void_elements:
                    touches_other_void = True
                    break
            if touches_other_void:
                continue
            
            # Check candidate shares no node with any OTHER void
            if element_nodes_dict is not None:
                candidate_nodes = element_nodes_dict.get(candidate, set())
                if candidate_nodes & other_void_nodes:
                    continue

            void_info['elements'].append(candidate)
            void_info['volume'] += element_volume_dict.get(candidate, 0.0)
            used_elements.add(candidate)
            all_void_elements.add(candidate)

            centroid_list = []
            for e in void_info['elements']:
                centroid_list.append(element_centroid_dict[e])
            void_info['centroid'] = np.mean(centroid_list, axis=0)

            return True
    
    return False

def _is_connected(element_set, element_neighbors_dict):
    """"""
    if not element_set:
        return True
    
    visited = set()
    queue = deque([next(iter(element_set))])
    
    while queue:
        current = queue.popleft()
        if current in visited:
            continue
        visited.add(current)
        
        neighbors = element_neighbors_dict.get(current, set())
        for neighbor in neighbors:
            if neighbor in element_set and neighbor not in visited:
                queue.append(neighbor)
    
    return len(visited) == len(element_set)


def _would_create_island(elem_to_remove, current_void, element_neighbors_dict, all_matrix_elements):
    """"""
    neighbors = element_neighbors_dict.get(elem_to_remove, set())
    matrix_neighbors = [n for n in neighbors if n in all_matrix_elements]
    
    if len(matrix_neighbors) <= 1:
        return False
    
    void_after = current_void - {elem_to_remove}
    
    start = matrix_neighbors[0]
    visited = set()
    queue = deque([start])
    
    while queue:
        current = queue.popleft()
        if current in visited:
            continue
        visited.add(current)
        
        neighbors = element_neighbors_dict.get(current, set())
        for neighbor in neighbors:
            if neighbor in all_matrix_elements and neighbor not in void_after and neighbor not in visited:
                queue.append(neighbor)
    
    for matrix_neighbor in matrix_neighbors:
        if matrix_neighbor not in visited:
            return True
    
    return False

######################
def generate_voids_random_w_random_theta(target_vf, all_matrix_elements, 
                                         all_fiber_elements, elem_neighbors,
                                         elem_volumes, total_volume,
                                         matrix_elem_nodes, fiber_elem_nodes):
    """
    1wtheta - +
    
    
    1. 
    2. clusters
    3. 
    
    
    - 
    
    
        target_vf: float, RVE
        all_matrix_elements: set of matrix element IDs
        all_fiber_elements: set of fiber element IDs
        elem_neighbors: dict {elem_id: set of neighbor IDs}
        elem_volumes: dict {elem_id: volume}
        total_volume: float, RVE
        matrix_elem_nodes: dict {elem_id: set of node labels}
        fiber_elem_nodes: dict {elem_id: set of node labels}
    
    
        void_elements: set of void element IDs
        statistics: dict with detailed info
    """
    print("\n" + "="*70)
    print("CASE 1: Random w, Random theta (Pure Random Selection)")
    print("="*70)
    
    # Build near-fiber lookup ONCE to avoid O(N_fiber) per-element classification later.
    # Rule: an element is "near-fiber" iff it shares >=1 node with any fiber element.
    all_fiber_nodes = set()
    for fib_nodes in fiber_elem_nodes.values():
        all_fiber_nodes |= fib_nodes
    
    is_elem_near_fiber = {e: bool(matrix_elem_nodes.get(e, set()) & all_fiber_nodes)
                          for e in all_matrix_elements}
    
    # void
    target_void_volume = (target_vf / 100.0) * total_volume
    print("Target void volume: {:.6e}".format(target_void_volume))
    print("Target Vf:          {:.4f}%".format(target_vf))
    
    # 
    void_set = set()
    current_volume = 0.0
    available_elements = list(all_matrix_elements.copy())
    random.shuffle(available_elements)
    
    print("\nRandomly selecting void elements...")
    for elem_id in available_elements:
        if current_volume >= target_void_volume:
            break
        
        void_set.add(elem_id)
        current_volume += elem_volumes.get(elem_id, 0.0)
    
    print("Selected {} void elements".format(len(void_set)))
    
    # 
    final_volume = sum([elem_volumes.get(e, 0.0) for e in void_set])
    final_vf = (final_volume / total_volume) * 100
    
    print("\nChecking final volume fraction...")
    print("  Current Vf: {:.4f}%".format(final_vf))
    print("  Target Vf:  {:.4f}%".format(target_vf))
    
    # 99%-101%
    print("\nAdjusting volume to meet strict tolerance (99%-101%)...")
    
    final_volume = sum([elem_volumes.get(e, 0.0) for e in void_set])
    final_vf = (final_volume / total_volume) * 100
    target_lower = target_vf * 0.99
    target_upper = target_vf * 1.01
    
    print("  Current Vf: {:.4f}%".format(final_vf))
    print("  Target range: {:.4f}% - {:.4f}%".format(target_lower, target_upper))
    
    # 
    if final_vf < target_lower:
        print("  Volume too low, adding elements...")
        remaining_elements = [e for e in available_elements if e not in void_set]
        
        for elem_id in remaining_elements:
            if elem_id in void_set:
                continue
            
            # 
            predicted_volume = final_volume + elem_volumes.get(elem_id, 0.0)
            predicted_vf = (predicted_volume / total_volume) * 100
            
            # 
            if predicted_vf > target_upper:
                continue
            
            # 
            void_set.add(elem_id)
            final_volume = predicted_volume
            final_vf = predicted_vf
            
            # 
            if final_vf >= target_lower:
                print("  Volume adjusted: {:.4f}%".format(final_vf))
                break
    
    # 
    elif final_vf > target_upper:
        print("  Volume too high, removing elements...")
        void_list = list(void_set)
        
        # 
        void_list_sorted = [(e, elem_volumes.get(e, 0.0)) for e in void_list]
        void_list_sorted.sort(key=lambda x: x[1], reverse=True)
        
        for elem_id, elem_vol in void_list_sorted:
            # 
            predicted_volume = final_volume - elem_vol
            predicted_vf = (predicted_volume / total_volume) * 100
            
            # 
            if predicted_vf < target_lower:
                continue
            
            # 
            void_set.discard(elem_id)
            final_volume = predicted_volume
            final_vf = predicted_vf
            
            # 
            if final_vf <= target_upper:
                print("  Volume adjusted: {:.4f}%".format(final_vf))
                break
    
    # 
    final_volume = sum([elem_volumes.get(e, 0.0) for e in void_set])
    final_vf = (final_volume / total_volume) * 100
    
    if final_vf < target_lower or final_vf > target_upper:
        print("\n" + "!"*70)
        print("ERROR: Cannot achieve target volume within 99%-101% tolerance!")
        print("  Current Vf: {:.4f}%".format(final_vf))
        print("  Target range: {:.4f}% - {:.4f}%".format(target_lower, target_upper))
        print("  This may be due to element size constraints.")
        print("!"*70)
    
    # 
    print("\n" + "-"*70)
    print("FINAL STATISTICS")
    print("-"*70)
    
    # 
    final_volume = sum([elem_volumes.get(e, 0.0) for e in void_set])
    final_vf = (final_volume / total_volume) * 100
    
    # clusters
    final_clusters = cluster_adjacent_void_elements(void_set, elem_neighbors)
    
    # wtypecluster
    near_fiber_volume = 0.0
    inter_matrix_volume = 0.0
    near_fiber_count = 0
    inter_matrix_count = 0
    clusters_with_type = []
    
    for cluster in final_clusters:
        # an element is 'near-fiber' if it shares >= 1 node with any fiber element.
        is_near_fiber = _cluster_has_near_fiber(cluster, is_elem_near_fiber)
        
        cluster_volume = sum([elem_volumes.get(e, 0.0) for e in cluster])
        
        if is_near_fiber:
            near_fiber_volume += cluster_volume
            near_fiber_count += 1
        else:
            inter_matrix_volume += cluster_volume
            inter_matrix_count += 1
        
        # typecluster
        clusters_with_type.append({
            'cluster': cluster,
            'type': 'near_fiber' if is_near_fiber else 'inter_matrix',
            'volume': cluster_volume
        })
    
    total_void_volume = near_fiber_volume + inter_matrix_volume
    w_value = near_fiber_volume / total_void_volume if total_void_volume > 0 else 0.0
    
    # 
    print("Total voids (clusters): {}".format(len(final_clusters)))
    if len(final_clusters) > 0:
        print("  Near-fiber voids:     {} ({:.1f}%)".format(
            near_fiber_count, near_fiber_count*100.0/len(final_clusters)))
        print("  Inter-matrix voids:   {} ({:.1f}%)".format(
            inter_matrix_count, inter_matrix_count*100.0/len(final_clusters)))
    
    print("\nTotal void volume:      {:.6e}".format(total_void_volume))
    print("  Near-fiber volume:    {:.6e}".format(near_fiber_volume))
    print("  Inter-matrix volume:  {:.6e}".format(inter_matrix_volume))
    
    print("\nRealized Vf:            {:.4f}%".format(final_vf))
    print("Target Vf:              {:.4f}%".format(target_vf))
    print("Deviation:              {:.4f}%".format(abs(final_vf - target_vf)))
    
    if abs(final_vf - target_vf) > 1.0:
        print("\n" + "!"*70)
        print("WARNING: Volume fraction deviation > 1%!")
        print("This may indicate insufficient matrix elements.")
        print("!"*70)
    
    print("\nRealized w value:       {:.4f}".format(w_value))
    print("="*70 + "\n")
    
    # 
    statistics = {
        'num_voids': len(final_clusters),
        'num_valid_voids': len(final_clusters),
        'near_fiber_count': near_fiber_count,
        'inter_matrix_count': inter_matrix_count,
        'total_void_volume': total_void_volume,
        'near_fiber_volume': near_fiber_volume,
        'inter_matrix_volume': inter_matrix_volume,
        'realized_vf': final_vf,
        'target_vf': target_vf,
        'realized_w': w_value,
        'target_w': None,
        'void_elements': void_set,
        'clusters': final_clusters,
        'clusters_with_type': clusters_with_type
    }
    
    return void_set, statistics

def generate_voids_custom_w_random_theta(target_vf, target_w, all_matrix_elements,
                                         all_fiber_elements, elem_neighbors,
                                         elem_volumes, total_volume,
                                         matrix_elem_nodes, fiber_elem_nodes):
    """
    2wtheta - w
    
    
    1. near_fiber / inter_matrix
    2. 
    3. cluster>=2
    4. w
    5. w
    6. w
    
    
    -  AND w
    
    
        target_vf: float, RVE
        target_w: float, w [0,1]
        all_matrix_elements: set of matrix element IDs
        all_fiber_elements: set of fiber element IDs
        elem_neighbors: dict {elem_id: set of neighbor IDs}
        elem_volumes: dict {elem_id: volume}
        total_volume: float, RVE
        matrix_elem_nodes: dict {elem_id: set of node labels}
        fiber_elem_nodes: dict {elem_id: set of node labels}
    
    
        void_elements: set of void element IDs
        statistics: dict
    """
    print("\n" + "="*70)
    print("CASE 2: Custom w, Random theta (w-Controlled Random Selection)")
    print("="*70)
    print("Target w = {:.4f}".format(target_w))
    print("Target Vf = {:.4f}%".format(target_vf))
    
    # void
    target_void_volume = (target_vf / 100.0) * total_volume
    print("Target void volume: {:.6e}".format(target_void_volume))
    
    # 
    # Pre-compute the union of all fiber node labels ONCE.
    # Classification aligned with Step 4 convention (>=1 shared node).
    all_fiber_nodes = set()
    for fib_nodes in fiber_elem_nodes.values():
        all_fiber_nodes |= fib_nodes
    
    near_fiber_candidates = set()
    inter_matrix_candidates = set()
    for elem_id in all_matrix_elements:
        if matrix_elem_nodes.get(elem_id, set()) & all_fiber_nodes:
            near_fiber_candidates.add(elem_id)
        else:
            inter_matrix_candidates.add(elem_id)
    
    is_elem_near_fiber = {e: (e in near_fiber_candidates) for e in all_matrix_elements}
    
    print("Near-fiber candidates:   {} elements".format(len(near_fiber_candidates)))
    print("Inter-matrix candidates: {} elements".format(len(inter_matrix_candidates)))
    
    # 
    near_fiber_list = list(near_fiber_candidates)
    inter_matrix_list = list(inter_matrix_candidates)
    random.shuffle(near_fiber_list)
    random.shuffle(inter_matrix_list)
    
    # 
    void_set = set()
    near_fiber_idx = 0
    inter_matrix_idx = 0
    
    print("\nSelecting elements with real-time w-value control...")
    
    # 
    max_iterations = len(all_matrix_elements)
    iteration = 0
    w_adjustment_phase = False
    
    while iteration < max_iterations:
        iteration += 1
        
        # 
        current_clusters = cluster_adjacent_void_elements(void_set, elem_neighbors)
        
        current_near_fiber_volume = 0.0
        current_inter_matrix_volume = 0.0
        near_fiber_clusters = []
        inter_matrix_clusters = []
        
        for cluster in current_clusters:
            is_near_fiber = _cluster_has_near_fiber(cluster, is_elem_near_fiber)
            
            cluster_volume = sum([elem_volumes.get(e, 0.0) for e in cluster])
            
            if is_near_fiber:
                current_near_fiber_volume += cluster_volume
                near_fiber_clusters.append(cluster)
            else:
                current_inter_matrix_volume += cluster_volume
                inter_matrix_clusters.append(cluster)
        
        current_total_volume = current_near_fiber_volume + current_inter_matrix_volume
        current_vf = (current_total_volume / total_volume) * 100.0
        current_w = current_near_fiber_volume / current_total_volume if current_total_volume > 0 else 0.0
        
        # 
        volume_ok = current_vf >= target_vf * 0.99
        w_ok = abs(current_w - target_w) <= 0.01
        
        if volume_ok and w_ok:
            print("\nTarget reached!")
            print("  Final Vf: {:.4f}% (target: {:.4f}%)".format(current_vf, target_vf))
            print("  Final w:  {:.4f} (target: {:.4f})".format(current_w, target_w))
            break
        
        # w
        if volume_ok and not w_ok:
            if not w_adjustment_phase:
                print("\nVolume reached, adjusting w value...")
                w_adjustment_phase = True
            
            # w
            if current_w < target_w:
                inter_matrix_elems_in_voids = set()
                for cluster in inter_matrix_clusters:
                    inter_matrix_elems_in_voids.update(cluster)
                
                if len(inter_matrix_elems_in_voids) > 0 and near_fiber_idx < len(near_fiber_list):
                    elem_volumes_list = [(e, elem_volumes.get(e, 0.0)) for e in inter_matrix_elems_in_voids]
                    elem_volumes_list.sort(key=lambda x: x[1])
                    to_remove = elem_volumes_list[0][0]
                    to_add = near_fiber_list[near_fiber_idx]
                    
                    void_set.discard(to_remove)
                    void_set.add(to_add)
                    near_fiber_idx += 1
                else:
                    print("\nCannot adjust w further (no elements available).")
                    break
            
            elif current_w > target_w:
                near_fiber_elems_in_voids = set()
                for cluster in near_fiber_clusters:
                    near_fiber_elems_in_voids.update(cluster)
                
                if len(near_fiber_elems_in_voids) > 0 and inter_matrix_idx < len(inter_matrix_list):
                    elem_volumes_list = [(e, elem_volumes.get(e, 0.0)) for e in near_fiber_elems_in_voids]
                    elem_volumes_list.sort(key=lambda x: x[1])
                    to_remove = elem_volumes_list[0][0]
                    to_add = inter_matrix_list[inter_matrix_idx]
                    
                    void_set.discard(to_remove)
                    void_set.add(to_add)
                    inter_matrix_idx += 1
                else:
                    print("\nCannot adjust w further (no elements available).")
                    break
        
        else:
            # 
            if current_w < target_w:
                if near_fiber_idx < len(near_fiber_list):
                    void_set.add(near_fiber_list[near_fiber_idx])
                    near_fiber_idx += 1
                elif inter_matrix_idx < len(inter_matrix_list):
                    void_set.add(inter_matrix_list[inter_matrix_idx])
                    inter_matrix_idx += 1
                else:
                    print("\nNo more elements available.")
                    break
            else:
                if inter_matrix_idx < len(inter_matrix_list):
                    void_set.add(inter_matrix_list[inter_matrix_idx])
                    inter_matrix_idx += 1
                elif near_fiber_idx < len(near_fiber_list):
                    void_set.add(near_fiber_list[near_fiber_idx])
                    near_fiber_idx += 1
                else:
                    print("\nNo more elements available.")
                    break
        
        if iteration % 100 == 0:
            print("  Iteration {}: Vf={:.4f}%, w={:.4f}".format(
                iteration, current_vf, current_w))
    
    # w
    print("\nFinal volume check and replenishment...")
    
    # cluster
    final_clusters = cluster_adjacent_void_elements(void_set, elem_neighbors)
    
    near_fiber_volume = 0.0
    inter_matrix_volume = 0.0
    
    for cluster in final_clusters:
        is_near_fiber = _cluster_has_near_fiber(cluster, is_elem_near_fiber)
        cluster_volume = _cluster_volume(cluster, elem_volumes)
        
        if is_near_fiber:
            near_fiber_volume += cluster_volume
        else:
            inter_matrix_volume += cluster_volume
    
    total_void_volume = near_fiber_volume + inter_matrix_volume
    final_vf = (total_void_volume / total_volume) * 100.0
    final_w = near_fiber_volume / total_void_volume if total_void_volume > 0 else 0.0
    
    print("  Before replenishment: Vf={:.4f}%, w={:.4f}".format(final_vf, final_w))
    
    # 99%-101%w
    print("\nAdjusting volume to meet strict tolerance (99%-101%)...")
    
    target_lower = target_vf * 0.99
    target_upper = target_vf * 1.01
    target_void_volume_lower = (target_lower / 100.0) * total_volume
    target_void_volume_upper = (target_upper / 100.0) * total_volume
    
    print("  Before adjustment: Vf={:.4f}%, w={:.4f}".format(final_vf, final_w))
    print("  Target range: {:.4f}% - {:.4f}%".format(target_lower, target_upper))
    
    # w
    if final_vf < target_lower:
        print("  Volume too low, adding elements while maintaining w...")
        
        remaining_near = [e for e in near_fiber_list[near_fiber_idx:] if e not in void_set]
        remaining_inter = [e for e in inter_matrix_list[inter_matrix_idx:] if e not in void_set]
        
        # near_fiberinter_matrixw
        near_idx = 0
        inter_idx = 0
        
        while (near_idx < len(remaining_near) or inter_idx < len(remaining_inter)):
            current_vf = (total_void_volume / total_volume) * 100.0
            
            # 
            if current_vf >= target_lower:
                break
            
            # 
            if current_vf > target_upper:
                break
            
            # w
            current_w = near_fiber_volume / total_void_volume if total_void_volume > 0 else 0.0
            
            if current_w < target_w and near_idx < len(remaining_near):
                # wnear_fiber
                elem_id = remaining_near[near_idx]
                near_idx += 1
                
                if elem_id not in void_set:
                    elem_vol = elem_volumes.get(elem_id, 0.0)
                    
                    # 
                    predicted_vf = ((total_void_volume + elem_vol) / total_volume) * 100.0
                    if predicted_vf <= target_upper:
                        void_set.add(elem_id)
                        total_void_volume += elem_vol
                        near_fiber_volume += elem_vol
            
            elif inter_idx < len(remaining_inter):
                # winter_matrix
                elem_id = remaining_inter[inter_idx]
                inter_idx += 1
                
                if elem_id not in void_set:
                    elem_vol = elem_volumes.get(elem_id, 0.0)
                    
                    # 
                    predicted_vf = ((total_void_volume + elem_vol) / total_volume) * 100.0
                    if predicted_vf <= target_upper:
                        void_set.add(elem_id)
                        total_void_volume += elem_vol
                        inter_matrix_volume += elem_vol
            else:
                # 
                break
        
        final_vf = (total_void_volume / total_volume) * 100.0
        final_w = near_fiber_volume / total_void_volume if total_void_volume > 0 else 0.0
        print("  After adding: Vf={:.4f}%, w={:.4f}".format(final_vf, final_w))
    
    # w
    elif final_vf > target_upper:
        print("  Volume too high, removing elements while maintaining w...")
        
        # cluster
        current_clusters = cluster_adjacent_void_elements(void_set, elem_neighbors)
        
        near_fiber_elems = set()
        inter_matrix_elems = set()
        
        for cluster in current_clusters:
            is_near_fiber = _cluster_has_near_fiber(cluster, is_elem_near_fiber)
            
            if is_near_fiber:
                near_fiber_elems.update(cluster)
            else:
                inter_matrix_elems.update(cluster)
        
        # 
        near_sorted = [(e, elem_volumes.get(e, 0.0)) for e in near_fiber_elems]
        inter_sorted = [(e, elem_volumes.get(e, 0.0)) for e in inter_matrix_elems]
        near_sorted.sort(key=lambda x: x[1], reverse=True)
        inter_sorted.sort(key=lambda x: x[1], reverse=True)
        
        near_idx = 0
        inter_idx = 0
        
        while (near_idx < len(near_sorted) or inter_idx < len(inter_sorted)):
            current_vf = (total_void_volume / total_volume) * 100.0
            
            # 
            if current_vf <= target_upper:
                break
            
            # 
            if current_vf < target_lower:
                break
            
            # w
            current_w = near_fiber_volume / total_void_volume if total_void_volume > 0 else 0.0
            
            if current_w > target_w and near_idx < len(near_sorted):
                # wnear_fiber
                elem_id, elem_vol = near_sorted[near_idx]
                near_idx += 1
                
                # 
                predicted_vf = ((total_void_volume - elem_vol) / total_volume) * 100.0
                if predicted_vf >= target_lower:
                    void_set.discard(elem_id)
                    total_void_volume -= elem_vol
                    near_fiber_volume -= elem_vol
            
            elif inter_idx < len(inter_sorted):
                # winter_matrix
                elem_id, elem_vol = inter_sorted[inter_idx]
                inter_idx += 1
                
                # 
                predicted_vf = ((total_void_volume - elem_vol) / total_volume) * 100.0
                if predicted_vf >= target_lower:
                    void_set.discard(elem_id)
                    total_void_volume -= elem_vol
                    inter_matrix_volume -= elem_vol
            else:
                # 
                break
        
        final_vf = (total_void_volume / total_volume) * 100.0
        final_w = near_fiber_volume / total_void_volume if total_void_volume > 0 else 0.0
        print("  After removing: Vf={:.4f}%, w={:.4f}".format(final_vf, final_w))
    
    # 
    if final_vf < target_lower or final_vf > target_upper:
        print("\n" + "!"*70)
        print("ERROR: Cannot achieve target volume within 99%-101% tolerance!")
        print("  Current Vf: {:.4f}%".format(final_vf))
        print("  Target range: {:.4f}% - {:.4f}%".format(target_lower, target_upper))
        print("  This may be due to element size constraints.")
        print("!"*70)
    
    # 
    print("\n" + "-"*70)
    print("FINAL STATISTICS")
    print("-"*70)
    
    # clustertype
    final_clusters = cluster_adjacent_void_elements(void_set, elem_neighbors)
    
    near_fiber_volume = 0.0
    inter_matrix_volume = 0.0
    near_fiber_count = 0
    inter_matrix_count = 0
    clusters_with_type = []
    
    for cluster in final_clusters:
        is_near_fiber = _cluster_has_near_fiber(cluster, is_elem_near_fiber)
        
        cluster_volume = _cluster_volume(cluster, elem_volumes)
        
        if is_near_fiber:
            near_fiber_volume += cluster_volume
            near_fiber_count += 1
        else:
            inter_matrix_volume += cluster_volume
            inter_matrix_count += 1
        
        # typecluster
        clusters_with_type.append({
            'cluster': cluster,
            'type': 'near_fiber' if is_near_fiber else 'inter_matrix',
            'volume': cluster_volume
        })
    
    total_void_volume = near_fiber_volume + inter_matrix_volume
    final_vf = (total_void_volume / total_volume) * 100.0
    final_w = near_fiber_volume / total_void_volume if total_void_volume > 0 else 0.0
    
    print("Total voids (clusters): {}".format(len(final_clusters)))
    print("  Near-fiber:     {}".format(near_fiber_count))
    print("  Inter-matrix:   {}".format(inter_matrix_count))
    
    print("\nVolume breakdown:")
    print("  Near-fiber:     {:.6e}".format(near_fiber_volume))
    print("  Inter-matrix:   {:.6e}".format(inter_matrix_volume))
    print("  Total:          {:.6e}".format(total_void_volume))
    
    print("\nRealized Vf:      {:.4f}%".format(final_vf))
    print("Target Vf:        {:.4f}%".format(target_vf))
    print("Deviation:        {:.4f}%".format(abs(final_vf - target_vf)))
    print("Realized w:       {:.4f}".format(final_w))
    print("Target w:         {:.4f}".format(target_w))
    print("w Deviation:      {:.4f}".format(abs(final_w - target_w)))
    
    if abs(final_vf - target_vf) > 1.0:
        print("\n" + "!"*70)
        print("ERROR: Volume fraction deviation > 1%!")
        print("Cannot proceed with this configuration.")
        print("!"*70)
    
    print("="*70 + "\n")
    
    statistics = {
        'num_voids': len(final_clusters),
        'num_valid_voids': len(final_clusters),
        'near_fiber_count': near_fiber_count,
        'inter_matrix_count': inter_matrix_count,
        'total_void_volume': total_void_volume,
        'near_fiber_volume': near_fiber_volume,
        'inter_matrix_volume': inter_matrix_volume,
        'realized_vf': final_vf,
        'target_vf': target_vf,
        'realized_w': final_w,
        'target_w': target_w,
        'void_elements': void_set,
        'clusters': final_clusters,
        'clusters_with_type': clusters_with_type
    }
    
    return void_set, statistics

def generate_voids_random_w_custom_theta(
        part, matrix_element_labels, near_fiber_candidates, inter_matrix_candidates, 
        element_volume_dict, element_centroid_dict, element_neighbors_dict,
        fiber_nodes, target_volume, num_voids, target_elements_per_void, 
        void_theta_value, avg_element_volume, fiber_element_labels,
        element_nodes_dict):
    """
    3: w=Random, theta=Custom (Seed-Grow v7)
    
    Key fix: NO permanent blacklist during normal growth.
    Fiber-enclosure and island checks use per-round skip sets
    (matching original grow_single_void_with_face_check behavior).
    Permanent blacklist only used for single-void restart scenario.
    """
    
    print("\n  ========== GENERATION MODE: Random w + Custom theta (Seed-Grow v7) ==========")
    print("  Target void count (theta): {}".format(num_voids))
    print("  Target void volume: {:.6e}".format(target_volume))
    
    all_fiber_elements = set(fiber_element_labels)
    all_matrix_elements = set(matrix_element_labels)
    
    theta_target = num_voids
    volume_lower = target_volume * 0.99
    volume_upper = target_volume * 1.01
    
    state = _initialize_void_generation(
        near_fiber_candidates, inter_matrix_candidates,
        num_voids, None, 2, void_theta_value)
    
    used_elements = state['used_elements']
    used_void_nodes = state['used_void_nodes']
    available_near_fiber = state['available_near_fiber']
    available_inter_matrix = state['available_inter_matrix']
    
    # Permanent blacklist ONLY for single-void restart
    permanent_blacklist = set()
    
    # ==================== Helpers ====================
    
    def _get_elem_nodes(label):
        return element_nodes_dict.get(label, set())
    
    def _get_elements_nodes(elem_set):
        nodes = set()
        for lbl in elem_set:
            nodes = nodes | _get_elem_nodes(lbl)
        return nodes
    
    def _all_void_nodes_from_seeds(seed_list):
        nodes = set()
        for s in seed_list:
            nodes = nodes | s['nodes']
        return nodes
    
    def _register_elem(lbl):
        used_elements.add(lbl)
        available_near_fiber.discard(lbl)
        available_inter_matrix.discard(lbl)
        for nl in _get_elem_nodes(lbl):
            used_void_nodes.add(nl)
    
    def _unregister_elem(lbl):
        used_elements.discard(lbl)
        if lbl in near_fiber_candidates:
            available_near_fiber.add(lbl)
        elif lbl in inter_matrix_candidates:
            available_inter_matrix.add(lbl)
    
    def _pick_seed(existing_void_nodes_set, bl_set):
        cands = []
        for c in available_near_fiber:
            if c not in used_elements and c not in bl_set:
                cands.append(c)
        for c in available_inter_matrix:
            if c not in used_elements and c not in bl_set:
                cands.append(c)
        random.shuffle(cands)
        for c in cands:
            c_nodes = _get_elem_nodes(c)
            if len(c_nodes & existing_void_nodes_set) == 0:
                return c
        return None
    
    def _compute_total_volume(seed_list):
        vol = 0.0
        for s in seed_list:
            for e in s['elements']:
                vol += element_volume_dict.get(e, 0.0)
        return vol
    
    def _collect_all_void_elems(seed_list):
        s = set()
        for sd in seed_list:
            s = s | sd['elements']
        return s
    
    def _local_will_create_island(candidate, all_void_elems_set):
        """Incremental local island check with bounded BFS."""
        test_void = all_void_elems_set | set([candidate])
        cand_neighbors = element_neighbors_dict.get(candidate, set())
        matrix_neighbors = []
        for nb in cand_neighbors:
            if nb in all_matrix_elements and nb not in test_void:
                matrix_neighbors.append(nb)
        if len(matrix_neighbors) <= 1:
            return False
        start = matrix_neighbors[0]
        visited = set([start])
        queue = deque([start])
        max_visit = 500
        visit_count = 0
        while queue and visit_count < max_visit:
            current = queue.popleft()
            visit_count += 1
            for nb in element_neighbors_dict.get(current, set()):
                if nb in all_matrix_elements and nb not in test_void and nb not in visited:
                    visited.add(nb)
                    queue.append(nb)
        for mn in matrix_neighbors:
            if mn not in visited:
                return True
        return False
    
    def _try_grow_one(seed, seeds_list):
        """
        Try to grow a seed by one element.
        Uses a PER-CALL skip set for rejected candidates (not permanent blacklist).
        This matches the original grow_single_void_with_face_check behavior.
        """
        void_elems = seed['elements']
        all_void_set = _collect_all_void_elems(seeds_list)
        
        # Collect boundary
        boundary = set()
        for el in void_elems:
            for nb in element_neighbors_dict.get(el, set()):
                if nb not in used_elements and nb not in permanent_blacklist:
                    boundary.add(nb)
        
        if len(boundary) == 0:
            return False
        
        # Distance-weighted first, then shuffled rest
        cent_list = []
        for e in void_elems:
            cent_list.append(element_centroid_dict[e])
        seed_centroid = np.mean(cent_list, axis=0)
        best = distance_weighted_selection_debug(list(boundary), seed_centroid, element_centroid_dict)
        
        ordered = []
        if best is not None:
            ordered.append(best)
        rest = list(boundary)
        random.shuffle(rest)
        for r in rest:
            if r != best:
                ordered.append(r)
        
        # Per-call skip set (temporary, like rejected_in_this_growth in original)
        skipped_this_call = set()
        
        for selected in ordered:
            if selected in skipped_this_call:
                continue
            if selected in permanent_blacklist:
                continue
            
            # Check 1: Fiber enclosure => skip THIS CALL only (not permanent)
            if will_isolate_fiber(selected, void_elems, element_neighbors_dict,
                                  fiber_nodes, set(element_volume_dict.keys())):
                skipped_this_call.add(selected)
                continue
            
            # Check 2: Local island => skip THIS CALL only
            if _local_will_create_island(selected, all_void_set):
                skipped_this_call.add(selected)
                continue
            
            # Accept
            seed['elements'].add(selected)
            seed['nodes'] = seed['nodes'] | _get_elem_nodes(selected)
            _register_elem(selected)
            return True
        
        return False
    
    # ==================== Step 1: Place initial seeds ====================
    print("\n  Step 1: Selecting {} initial seed elements...".format(theta_target))
    
    seeds = []
    for i in range(theta_target):
        all_vn = _all_void_nodes_from_seeds(seeds)
        seed_label = _pick_seed(all_vn, permanent_blacklist)
        if seed_label is None:
            print("    WARNING: Could only place {} seeds (target: {})".format(
                len(seeds), theta_target))
            break
        seed_nodes = _get_elem_nodes(seed_label)
        seeds.append({
            'elements': set([seed_label]),
            'nodes': set(seed_nodes),
        })
        _register_elem(seed_label)
    
    print("    Placed {} seeds".format(len(seeds)))
    
    # ==================== Main growth loop ====================
    max_global_iterations = 10000
    global_iter = 0
    stall_counter = 0
    max_stall = 1000
    generation_success = False
    
    while global_iter < max_global_iterations:
        global_iter += 1
        
        cur_vol = _compute_total_volume(seeds)
        cur_count = len(seeds)
        
        # ===== ONLY normal exit: both theta and volume satisfied =====
        if cur_count == theta_target and volume_lower <= cur_vol <= volume_upper:
            print("\n  SUCCESS at iteration {}: {} voids, {:.4f}% volume".format(
                global_iter, cur_count, cur_vol / target_volume * 100))
            generation_success = True
            break
        
        if cur_vol > target_volume * 1.5:
            print("\n  SAFETY STOP: volume exceeded 150%")
            break
        
        if stall_counter >= max_stall:
            print("\n  STALL after {} iterations".format(max_stall))
            break
        
        growth_happened = False
        
        # ===== Step 2: Grow ALL seeds by one element each =====
        if cur_vol < volume_upper:
            for s_idx in range(len(seeds)):
                if _compute_total_volume(seeds) >= volume_upper:
                    break
                if _try_grow_one(seeds[s_idx], seeds):
                    growth_happened = True
        
        # ===== Step 3: Merging (face contact: >= 3 shared nodes) =====
        merged_indices = set()
        i = 0
        while i < len(seeds):
            if i in merged_indices:
                i += 1
                continue
            j = i + 1
            while j < len(seeds):
                if j in merged_indices:
                    j += 1
                    continue
                shared_n = len(seeds[i]['nodes'] & seeds[j]['nodes'])
                if shared_n >= 3:
                    seeds[i]['elements'] = seeds[i]['elements'] | seeds[j]['elements']
                    seeds[i]['nodes'] = seeds[i]['nodes'] | seeds[j]['nodes']
                    merged_indices.add(j)
                    print("    Iter {}: Merged seed {} into {} ({} shared, {} elems)".format(
                        global_iter, j, i, shared_n, len(seeds[i]['elements'])))
                    j = i + 1
                    continue
                j += 1
            i += 1
        
        if len(merged_indices) > 0:
            new_seeds = []
            for idx in range(len(seeds)):
                if idx not in merged_indices:
                    new_seeds.append(seeds[idx])
            seeds = new_seeds
        
        # ===== Step 4: Replenish seeds if count dropped =====
        while len(seeds) < theta_target:
            all_vn = _all_void_nodes_from_seeds(seeds)
            new_label = _pick_seed(all_vn, permanent_blacklist)
            if new_label is None:
                print("    Iter {}: Cannot replenish".format(global_iter))
                break
            new_nodes = _get_elem_nodes(new_label)
            seeds.append({
                'elements': set([new_label]),
                'nodes': set(new_nodes),
            })
            _register_elem(new_label)
            print("    Iter {}: Replenished, now {} seeds".format(global_iter, len(seeds)))
        
        # ===== Step 5: Single-void restart =====
        if theta_target == 1 and len(seeds) == 1:
            cur_vol_s = _compute_total_volume(seeds)
            void_elems = seeds[0]['elements']
            has_boundary = False
            for el in void_elems:
                for nb in element_neighbors_dict.get(el, set()):
                    if nb not in used_elements and nb not in permanent_blacklist:
                        has_boundary = True
                        break
                if has_boundary:
                    break
            
            if not has_boundary and cur_vol_s < volume_lower:
                print("    Single void stuck at {:.4f}%, restarting...".format(
                    cur_vol_s / target_volume * 100))
                for lbl in list(seeds[0]['elements']):
                    permanent_blacklist.add(lbl)
                    _unregister_elem(lbl)
                seeds = []
                new_label = _pick_seed(set(), permanent_blacklist)
                if new_label is None:
                    print("    All elements blacklisted, stopping.")
                    break
                seeds.append({
                    'elements': set([new_label]),
                    'nodes': set(_get_elem_nodes(new_label)),
                })
                _register_elem(new_label)
                stall_counter = 0
                continue
        
        # ===== Step 6: Volume fine-tune when theta OK =====
        cur_count = len(seeds)
        cur_vol = _compute_total_volume(seeds)
        
        if cur_count == theta_target and cur_vol < volume_lower:
            for si in range(len(seeds)):
                if _compute_total_volume(seeds) >= volume_lower:
                    break
                if _try_grow_one(seeds[si], seeds):
                    growth_happened = True
        
        elif cur_count == theta_target and cur_vol > volume_upper:
            sorted_desc = sorted(range(len(seeds)),
                                  key=lambda k: len(seeds[k]['elements']), reverse=True)
            for si in sorted_desc:
                if _compute_total_volume(seeds) <= volume_upper:
                    break
                sd = seeds[si]
                if len(sd['elements']) <= 1:
                    continue
                void_set = sd['elements']
                edge = []
                for el in void_set:
                    nbs = element_neighbors_dict.get(el, set())
                    if len(nbs - void_set) > 0:
                        edge.append(el)
                if not edge:
                    continue
                edge.sort(key=lambda e: element_volume_dict.get(e, 0.0), reverse=True)
                for candidate in edge:
                    remaining = void_set - set([candidate])
                    if not _is_connected(remaining, element_neighbors_dict):
                        continue
                    sd['elements'].discard(candidate)
                    sd['nodes'] = _get_elements_nodes(sd['elements'])
                    _unregister_elem(candidate)
                    growth_happened = True
                    break
        
        # Stall tracking
        if growth_happened:
            stall_counter = 0
        else:
            stall_counter += 1
        
        # Progress
        if global_iter % 200 == 0:
            cur_vol = _compute_total_volume(seeds)
            print("  Iter {}: {} seeds, vol={:.4f}%, stall={}".format(
                global_iter, len(seeds), cur_vol / target_volume * 100, stall_counter))
    
    # ==================== Build all_voids ====================
    all_voids = []
    for seed in seeds:
        if len(seed['elements']) == 0:
            continue
        has_fc = False
        for el in seed['elements']:
            if el in near_fiber_candidates:
                has_fc = True
                break
        vtype = 'near_fiber' if has_fc else 'inter_matrix'
        vol_list = []
        for e in seed['elements']:
            vol_list.append(element_volume_dict.get(e, 0.0))
        void_vol = sum(vol_list)
        cent_list = []
        for e in seed['elements']:
            cent_list.append(element_centroid_dict[e])
        void_cent = np.mean(cent_list, axis=0)
        all_voids.append({
            'elements': list(seed['elements']),
            'type': vtype,
            'centroid': void_cent,
            'volume': void_vol
        })
    
    final_count = len(all_voids)
    final_volume = 0.0
    for v in all_voids:
        final_volume += v['volume']
    
    theta_ok = (final_count == theta_target)
    volume_ok = (volume_lower <= final_volume <= volume_upper)
    
    print("\n  ==================== Final Result ====================")
    print("    Voids  : {} / {} ==> theta_ok={}".format(
        final_count, num_voids, theta_ok))
    print("    Volume : {:.6e} ({:.4f}%) ==> volume_ok={}".format(
        final_volume, final_volume / target_volume * 100, volume_ok))
    
    if not generation_success:
        print("\n  *** GENERATION FAILED ***")
        if not theta_ok:
            print("    - Void count mismatch: generated {} / target {}".format(
                final_count, theta_target))
        if not volume_ok:
            print("    - Volume fraction mismatch: {:.4f}% / target {:.4f}%".format(
                final_volume / target_volume * 100, 100.0))
        print("    The result does NOT meet the specified targets.")
        print("    Suggestion: try adjusting mesh density or void parameters.")
    else:
        print("\n  Generation completed successfully.")
    
    return _finalize_void_statistics(all_voids, element_neighbors_dict,
                                    element_volume_dict, element_centroid_dict)

def generate_voids_custom_w_custom_theta(
        part, matrix_element_labels, near_fiber_candidates, inter_matrix_candidates, 
        element_volume_dict, element_centroid_dict, element_neighbors_dict,
        fiber_nodes, target_volume, num_voids, target_elements_per_void, 
        target_near_ratio, void_distribution_value, void_theta_value,
        avg_element_volume, fiber_element_labels, element_nodes_dict,
        void_priority=1):
    """
    Case 4: w=Custom, theta=Custom (Unified)
    
    All three targets are treated equally during normal convergence.
    Priority (void_priority) only affects which tolerance to relax
    when truly stuck:
      void_priority=1: relax theta first (preserve w)
      void_priority=2: relax w first (preserve theta)
    
    Targets:
    - Volume: 99%-101% (never relaxed)
    - theta: exact match when <=10
    - w: +/-1% strict, +/-5% relaxed
    """
    
    priority_label = 'w (Distribution)' if void_priority == 1 else 'theta (Size)'
    
    print("\n" + "="*70)
    print("CASE 4: Custom w + Custom theta")
    print("="*70)
    print("  Target w:     {:.4f} (+/-1%)".format(target_near_ratio))
    print("  Target theta: {}".format(num_voids))
    print("  Target Vf:    {:.2f}% (+/-1%)".format((target_volume / part.getVolume()) * 100))
    print("  Fallback priority: {} (only used when stuck)".format(priority_label))
    print("="*70)
    
    # ========== Initialization ==========
    state = _initialize_void_generation(
        near_fiber_candidates, inter_matrix_candidates, 
        num_voids, target_near_ratio, 1, void_theta_value)
    
    all_voids = state['all_voids']
    used_elements = state['used_elements']
    used_void_nodes = state['used_void_nodes']
    available_near_fiber = state['available_near_fiber']
    available_inter_matrix = state['available_inter_matrix']
    current_total_volume = state['current_total_volume']
    current_near_voids = state['current_near_voids']
    current_inter_voids = state['current_inter_voids']
    target_near_voids = state['target_near_voids']
    target_inter_voids = state['target_inter_voids']
    
    max_iterations = num_voids * 200
    iteration = 0
    consecutive_failures = 0
    max_consecutive_failures = 200 if (target_near_ratio is not None and target_near_ratio < 0.05) else 100

    # ========== Phase 1: Seed Growth (to ~95% volume) ==========
    # Helper: pick a random element from a set without building a full list.
    def _random_from_set(s):
        i = random.randrange(len(s))
        it = iter(s)
        for _ in range(i):
            next(it)
        return next(it)
    
    print("\n--- Phase 1: Seed Growth ---")

    volume_lower = target_volume * 0.99
    volume_upper = target_volume * 1.01
    target_phase1_volume = target_volume * 0.95

    current_near_volume = 0.0
    current_inter_volume = 0.0

    while len(all_voids) < num_voids and iteration < max_iterations:
        iteration += 1

        if current_total_volume >= target_phase1_volume:
            break

        if consecutive_failures >= max_consecutive_failures:
            print("  WARNING: Max consecutive failures reached")
            break

        seed_type = select_seed_type(
            target_near_ratio, target_near_voids, target_inter_voids,
            current_near_voids, current_inter_voids,
            available_near_fiber, available_inter_matrix,
            1, current_total_volume, target_volume,
            2, target_near_ratio,
            current_near_volume, current_inter_volume)

        if seed_type == 'near_fiber':
            if not available_near_fiber:
                consecutive_failures += 1
                continue
            seed_label = _random_from_set(available_near_fiber)
        else:
            if not available_inter_matrix:
                consecutive_failures += 1
                continue
            seed_label = _random_from_set(available_inter_matrix)   # <-- changed

        if seed_label in used_elements:
            available_near_fiber.discard(seed_label)
            available_inter_matrix.discard(seed_label)
            consecutive_failures += 1
            continue

        free_neighbors = [nb for nb in element_neighbors_dict.get(seed_label, set())
                          if nb not in used_elements]
        if not free_neighbors:
            available_near_fiber.discard(seed_label)
            available_inter_matrix.discard(seed_label)
            consecutive_failures += 1
            continue

        void_elements, void_type = grow_single_void_with_face_check(
            seed_label, seed_type, element_volume_dict, element_centroid_dict,
            element_neighbors_dict, used_elements,
            target_elements_per_void, avg_element_volume,
            available_near_fiber, available_inter_matrix,
            1, target_near_ratio, part, used_void_nodes, fiber_nodes, element_nodes_dict)

        if void_elements:
            has_fiber_contact = False
            for elem_label in void_elements:
                if elem_label in near_fiber_candidates:
                    has_fiber_contact = True
                    break
            void_type = 'near_fiber' if has_fiber_contact else 'inter_matrix'

            consecutive_failures = 0

            for label in void_elements:
                used_elements.add(label)
                available_near_fiber.discard(label)
                available_inter_matrix.discard(label)
                used_void_nodes.update(element_nodes_dict.get(label, set()))

            void_volume = 0.0
            for label in void_elements:
                void_volume += element_volume_dict[label]

            centroid_list = []
            for label in void_elements:
                centroid_list.append(element_centroid_dict[label])
            void_centroid = np.mean(centroid_list, axis=0)

            void_info = {
                'elements': list(void_elements),
                'type': void_type,
                'centroid': void_centroid,
                'volume': void_volume
            }
            all_voids.append(void_info)
            current_total_volume += void_volume

            if void_type == 'near_fiber':
                current_near_voids += 1
                current_near_volume += void_volume
            else:
                current_inter_voids += 1
                current_inter_volume += void_volume

            if len(all_voids) % 10 == 0:
                print("  Generated {} / {} voids, Vf={:.2f}%".format(
                    len(all_voids), num_voids,
                    current_total_volume / target_volume * 100))
        else:
            consecutive_failures += 1

    print("  Phase 1 complete: {} voids, {:.2f}% volume".format(
        len(all_voids), current_total_volume / target_volume * 100))
    
    # ========== Phase 2: Post-processing (Islands + Volume) ==========
    print("\n--- Phase 2: Post-processing (Islands + Volume) ---")

    all_matrix_elements = set(matrix_element_labels)
    all_fiber_elements = set(fiber_element_labels)

    if target_near_ratio is not None and target_near_ratio < 0.05:
        all_voids = post_process_volume_only(
            all_voids, element_neighbors_dict, element_volume_dict,
            element_centroid_dict, all_matrix_elements,
            target_volume, used_elements)
    else:
        all_voids = post_process_islands_and_volume(
            all_voids, element_neighbors_dict, element_volume_dict,
            element_centroid_dict, all_matrix_elements, part,
            target_volume, used_elements, fiber_nodes, all_fiber_elements, element_nodes_dict)

    print("  Phase 2 complete: {} voids".format(len([v for v in all_voids if v['elements']])))
    
    # ========== Phase 3: Triple-Target Correction (Equal Treatment) ==========
    print("\n--- Phase 3: Triple-Target Correction (Equal Treatment) ---")
    
    theta_strict_always = (num_voids <= 10)

    # Strict tolerances
    theta_tolerance_strict = 0 if theta_strict_always else max(1, int(num_voids * 0.01))
    theta_lower_strict = num_voids - theta_tolerance_strict
    theta_upper_strict = num_voids + theta_tolerance_strict
    w_tolerance_strict = 0.01  # +/-1%

    # Relaxed tolerances (only used when truly stuck)
    theta_tolerance_relaxed = max(1, int(num_voids * 0.10))
    theta_lower_relaxed = num_voids - theta_tolerance_relaxed
    theta_upper_relaxed = num_voids + theta_tolerance_relaxed
    w_tolerance_relaxed = 0.05  # +/-5%

    # Current active tolerances (start strict)
    theta_relaxed = False
    w_relaxed = False

    print("  Targets (all STRICT initially):")
    print("    theta: {} (strict_always={})".format(num_voids, theta_strict_always))
    print("    w:     {:.4f} +/-1%".format(target_near_ratio))
    print("    Vf:    99%-101%")
    print("    Fallback priority: {}".format(priority_label))

    max_final_iterations = 2000
    final_iter = 0
    consecutive_success = 0
    consecutive_no_progress = 0
    max_no_progress = 50

    while final_iter < max_final_iterations:
        final_iter += 1

        near_volume = 0.0
        inter_volume = 0.0
        valid_void_count = 0

        for v in all_voids:
            if v['elements']:
                valid_void_count += 1
                if v['type'] == 'near_fiber':
                    near_volume += v['volume']
                else:
                    inter_volume += v['volume']

        total_volume_current = near_volume + inter_volume
        current_w = near_volume / max(total_volume_current, 1e-20)
        volume_ratio = total_volume_current / target_volume

        # Determine pass/fail with current tolerances
        theta_lower = theta_lower_relaxed if theta_relaxed else theta_lower_strict
        theta_upper = theta_upper_relaxed if theta_relaxed else theta_upper_strict
        w_tol = w_tolerance_relaxed if w_relaxed else w_tolerance_strict

        theta_ok = (valid_void_count >= theta_lower and valid_void_count <= theta_upper)
        w_ok = (abs(current_w - target_near_ratio) <= w_tol)
        volume_ok = (volume_ratio >= 0.99 and volume_ratio <= 1.01)

        if final_iter % 10 == 1:
            mode_parts = []
            if theta_relaxed:
                mode_parts.append("theta-RELAXED")
            if w_relaxed:
                mode_parts.append("w-RELAXED")
            mode_str = ", ".join(mode_parts) if mode_parts else "STRICT"
            print("  Iter {} [{}]: theta={}/{}, Vf={:.2f}%, w={:.4f}".format(
                final_iter, mode_str, valid_void_count, num_voids, volume_ratio * 100, current_w))

        if theta_ok and volume_ok and w_ok:
            if volume_ratio >= 1.00:
                # Fully converged: volume at or above 100%
                consecutive_success += 1
                if consecutive_success >= 3:
                    print("  SUCCESS: Converged at iter {}".format(final_iter))
                    break
            else:
                # In 99-100% band: acceptable but keep trying to reach 100%
                consecutive_success = 0
            consecutive_no_progress = 0
        else:
            consecutive_success = 0
            consecutive_no_progress += 1

        # ========== Stuck detection: relax based on priority ==========
        if consecutive_no_progress >= max_no_progress:
            if void_priority == 1 and not theta_relaxed and not theta_strict_always:
                # w is more important => relax theta first
                print("\n  Stuck {} iters => relaxing THETA tolerance (w priority)".format(max_no_progress))
                print("  Theta range: [{}, {}]".format(theta_lower_relaxed, theta_upper_relaxed))
                theta_relaxed = True
                consecutive_no_progress = 0
                consecutive_success = 0
                continue
            elif void_priority == 2 and not w_relaxed:
                # theta is more important => relax w first
                print("\n  Stuck {} iters => relaxing W tolerance (theta priority)".format(max_no_progress))
                print("  W tolerance: +/-5%")
                w_relaxed = True
                consecutive_no_progress = 0
                consecutive_success = 0
                continue
            elif not theta_relaxed and not theta_strict_always:
                # Second fallback: relax theta
                print("\n  Stuck {} iters => relaxing THETA tolerance (second fallback)".format(max_no_progress))
                theta_relaxed = True
                consecutive_no_progress = 0
                consecutive_success = 0
                continue
            elif not w_relaxed:
                # Second fallback: relax w
                print("\n  Stuck {} iters => relaxing W tolerance (second fallback)".format(max_no_progress))
                w_relaxed = True
                consecutive_no_progress = 0
                consecutive_success = 0
                continue
            else:
                # All relaxed, check if volume is at least OK
                if volume_ok:
                    print("\n  All tolerances relaxed, volume OK => accepting result.")
                    break
                else:
                    print("\n  WARNING: Still stuck, continuing to fix volume...")
                    consecutive_no_progress = 0

        # ========== Equal treatment: volume -> theta -> w ==========
        
        if not volume_ok or volume_ratio < 1.00:
            # --- Adjust Volume (target center: 100%, accept 99-101%) ---
            if volume_ratio > 1.01:
                
                if total_volume_current > 0:
                    near_ratio = near_volume / total_volume_current
                else:
                    near_ratio = 0.5
                
                # Remove from whichever type is over-represented
                if near_ratio > target_near_ratio:
                    shrink_voids = [v for v in all_voids if v['type'] == 'near_fiber' and len(v['elements']) > 2]
                else:
                    shrink_voids = [v for v in all_voids if v['type'] == 'inter_matrix' and len(v['elements']) > 1]
                
                if not shrink_voids:
                    shrink_voids = [v for v in all_voids if len(v['elements']) > 1]
                
                if shrink_voids:
                    shrink_voids.sort(key=lambda v: v['volume'], reverse=True)
                    v = shrink_voids[0]
                    void_set = set(v['elements'])
                    
                    # Find safe boundary element (won't disconnect void, won't touch other void)
                    other_void_elems = set()
                    for ov in all_voids:
                        if ov is not v:
                            other_void_elems.update(ov['elements'])
                    
                    safe_boundary = []
                    for e in v['elements']:
                        nb_set = element_neighbors_dict.get(e, set())
                        is_boundary = bool(nb_set - void_set)
                        touches_other = bool(nb_set & other_void_elems)
                        if is_boundary and not touches_other:
                            remaining = void_set - {e}
                            if remaining and _is_connected(remaining, element_neighbors_dict):
                                safe_boundary.append(e)
                    
                    if safe_boundary:
                        safe_boundary.sort(key=lambda e: element_volume_dict.get(e, 0.0))
                        elem_to_remove = safe_boundary[0]
                        v['elements'].remove(elem_to_remove)
                        used_elements.discard(elem_to_remove)
                        if elem_to_remove in near_fiber_candidates:
                            available_near_fiber.add(elem_to_remove)
                        elif elem_to_remove in inter_matrix_candidates:
                            available_inter_matrix.add(elem_to_remove)
                        v['volume'] -= element_volume_dict.get(elem_to_remove, 0.0)
                        if v['elements']:
                            centroid_list = [element_centroid_dict[e] for e in v['elements']]
                            v['centroid'] = np.mean(centroid_list, axis=0)
                        removed = True
                
                if not removed:
                    consecutive_no_progress += 1
            
            else:  # volume_ratio < 0.99
                added = False
                
                if total_volume_current > 0:
                    near_ratio = near_volume / total_volume_current
                else:
                    near_ratio = target_near_ratio
                
                # Add to whichever type is under-represented
                if near_ratio < target_near_ratio:
                    target_voids = [v for v in all_voids if v['type'] == 'near_fiber' and v['elements']]
                    if not target_voids:
                        target_voids = [v for v in all_voids if v['elements']]
                else:
                    target_voids = [v for v in all_voids if v['type'] == 'inter_matrix' and v['elements']]
                    if not target_voids:
                        target_voids = [v for v in all_voids if v['elements']]
                
                for v in target_voids:
                    candidate_neighbors = set()
                    void_elem_set = set(v['elements'])
                    
                    other_void_elems = set()
                    for other_v in all_voids:
                        if other_v is not v:
                            other_void_elems.update(other_v['elements'])
                    
                    # Build other-void node set for strict node isolation
                    other_void_nodes = set()
                    for other_v in all_voids:
                        if other_v is not v:
                            for oe in other_v['elements']:
                                other_void_nodes.update(element_nodes_dict.get(oe, set()))
                    
                    for elem_label in v['elements']:
                        for neighbor in element_neighbors_dict.get(elem_label, set()):
                            if neighbor in used_elements:
                                continue
                            if neighbor not in available_near_fiber and neighbor not in available_inter_matrix:
                                continue
                            # Respect distribution constraint
                            if target_near_ratio == 0.0 and neighbor in available_near_fiber:
                                continue
                            if target_near_ratio == 1.0 and neighbor in available_inter_matrix:
                                continue
                            # Strict node isolation: no shared nodes with other voids
                            neighbor_nodes = element_nodes_dict.get(neighbor, set())
                            if neighbor_nodes & other_void_nodes:
                                continue
                            candidate_neighbors.add(neighbor)
                    
                    if candidate_neighbors:
                        candidates = list(candidate_neighbors)
                        random.shuffle(candidates)
                        for neighbor_to_add in candidates:
                            void_elements_test = set(v['elements'])
                            if will_isolate_fiber(neighbor_to_add, void_elements_test, element_neighbors_dict,
                                                fiber_element_labels, matrix_element_labels):
                                continue
                            
                            v['elements'].append(neighbor_to_add)
                            used_elements.add(neighbor_to_add)
                            available_near_fiber.discard(neighbor_to_add)
                            available_inter_matrix.discard(neighbor_to_add)
                            v['volume'] += element_volume_dict.get(neighbor_to_add, 0.0)
                            cent_list = [element_centroid_dict[e] for e in v['elements']]
                            v['centroid'] = np.mean(cent_list, axis=0)
                            added = True
                            break
                    if added:
                        break
                
                if not added:
                    consecutive_no_progress += 1
        
        elif not theta_ok:
            # --- Adjust Theta ---
            if valid_void_count < theta_lower:
                # Need more voids
                if target_near_ratio == 0.0:
                    candidate_pool = list(available_inter_matrix)
                elif target_near_ratio == 1.0:
                    candidate_pool = list(available_near_fiber)
                else:
                    candidate_pool = list(available_near_fiber) + list(available_inter_matrix)
                if not candidate_pool:
                    consecutive_no_progress += 1
                    continue
                
                seed_label = random.choice(candidate_pool)
                seed_type = 'near_fiber' if seed_label in available_near_fiber else 'inter_matrix'
                small_target = max(2, int(avg_element_volume * 2 / avg_element_volume))
                
                new_void_elements, new_void_type = grow_single_void_with_face_check(
                    seed_label, seed_type, element_volume_dict, element_centroid_dict,
                    element_neighbors_dict, used_elements,
                    small_target, avg_element_volume,
                    available_near_fiber, available_inter_matrix, 
                    1, target_near_ratio, part, used_void_nodes, fiber_nodes, element_nodes_dict)
                
                if new_void_elements:
                    # Check connectivity with existing voids
                    all_existing_void_nodes = set()
                    for existing_v in all_voids:
                        if existing_v['elements']:
                            for existing_elem in existing_v['elements']:
                                all_existing_void_nodes |= element_nodes_dict.get(existing_elem, set())
                    
                    would_connect = False
                    max_shared = 0
                    for new_elem in new_void_elements:
                        try:
                            new_elem_nodes = element_nodes_dict.get(new_elem, set())
                            shared = new_elem_nodes & all_existing_void_nodes
                            if len(shared) > max_shared:
                                max_shared = len(shared)
                            if shared:
                                would_connect = True
                                break
                        except:
                            pass
                    
                    if would_connect:
                        print("    New void shares {} nodes with existing void, skipped".format(max_shared))
                        for label in new_void_elements:
                            used_elements.discard(label)
                            if label in near_fiber_candidates:
                                available_near_fiber.add(label)
                            elif label in inter_matrix_candidates:
                                available_inter_matrix.add(label)
                            try:
                                used_void_nodes.update(element_nodes_dict.get(label, set()))
                                for node in element.getNodes():
                                    used_void_nodes.discard(node.label)
                            except:
                                pass
                    else:
                        has_fiber_contact = False
                        for elem_label in new_void_elements:
                            if elem_label in near_fiber_candidates:
                                has_fiber_contact = True
                                break
                        actual_type = 'near_fiber' if has_fiber_contact else 'inter_matrix'
                        
                        for label in new_void_elements:
                            used_elements.add(label)
                            available_near_fiber.discard(label)
                            available_inter_matrix.discard(label)
                            try:
                                used_void_nodes.update(element_nodes_dict.get(label, set()))
                                for node in element.getNodes():
                                    used_void_nodes.add(node.label)
                            except:
                                pass
                        
                        new_void_volume = sum([element_volume_dict.get(e, 0.0) for e in new_void_elements])
                        centroid_list = [element_centroid_dict[e] for e in new_void_elements]
                        new_centroid = np.mean(centroid_list, axis=0)
                        
                        all_voids.append({
                            'elements': list(new_void_elements),
                            'type': actual_type,
                            'centroid': new_centroid,
                            'volume': new_void_volume
                        })
                        print("    Added void (theta: {} -> {})".format(valid_void_count, valid_void_count + 1))
                else:
                    print("    Failed to generate void")
            
            elif valid_void_count > theta_upper:
                # Too many voids: remove smallest
                non_empty_voids = [v for v in all_voids if v['elements']]
                if non_empty_voids:
                    non_empty_voids.sort(key=lambda v: v['volume'])
                    void_to_remove = non_empty_voids[0]
                    all_voids.remove(void_to_remove)
                    for elem_label in void_to_remove['elements']:
                        used_elements.discard(elem_label)
                        if elem_label in near_fiber_candidates:
                            available_near_fiber.add(elem_label)
                        elif elem_label in inter_matrix_candidates:
                            available_inter_matrix.add(elem_label)
                        for node_label in element_nodes_dict.get(elem_label, set()):
                            used_void_nodes.discard(node_label)
                    print("    Removed smallest void (theta: {} -> {})".format(valid_void_count, valid_void_count - 1))
                else:
                    consecutive_no_progress += 1
        
        elif not w_ok:
            # --- Adjust w (shrink-grow, never transfer) ---
            if current_w > target_near_ratio + w_tol:
                # w too high: shrink near_fiber void, grow inter_matrix void
                near_voids = [v for v in all_voids if v['type'] == 'near_fiber' and len(v['elements']) > 2]
                inter_voids = [v for v in all_voids if v['type'] == 'inter_matrix' and v['elements']]
                donor_voids = near_voids
                grow_voids = inter_voids
            elif current_w < target_near_ratio - w_tol:
                # w too low: shrink inter_matrix void, grow near_fiber void
                inter_voids = [v for v in all_voids if v['type'] == 'inter_matrix' and len(v['elements']) > 1]
                near_voids = [v for v in all_voids if v['type'] == 'near_fiber' and v['elements']]
                donor_voids = inter_voids
                grow_voids = near_voids
            else:
                donor_voids = []
                grow_voids = []
            
            w_adjusted = False
            
            if donor_voids and grow_voids:
                # Step 1: remove safe boundary element from donor
                donor_voids.sort(key=lambda v: v['volume'], reverse=True)
                donor_void = donor_voids[0]
                donor_set = set(donor_void['elements'])
                
                other_void_elems = set()
                for ov in all_voids:
                    if ov is not donor_void:
                        other_void_elems.update(ov['elements'])
                
                safe_boundary = []
                for e in donor_void['elements']:
                    nb_set = element_neighbors_dict.get(e, set())
                    is_boundary = bool(nb_set - donor_set)
                    touches_other = bool(nb_set & other_void_elems)
                    if is_boundary and not touches_other:
                        remaining = donor_set - {e}
                        if remaining and _is_connected(remaining, element_neighbors_dict):
                            safe_boundary.append(e)
                
                if safe_boundary:
                    safe_boundary.sort(key=lambda e: element_volume_dict.get(e, 0.0))
                    elem_to_remove = safe_boundary[0]
                    donor_void['elements'].remove(elem_to_remove)
                    donor_void['volume'] -= element_volume_dict.get(elem_to_remove, 0.0)
                    used_elements.discard(elem_to_remove)
                    if elem_to_remove in near_fiber_candidates:
                        available_near_fiber.add(elem_to_remove)
                    elif elem_to_remove in inter_matrix_candidates:
                        available_inter_matrix.add(elem_to_remove)
                    if donor_void['elements']:
                        centroid_list = [element_centroid_dict[e] for e in donor_void['elements']]
                        donor_void['centroid'] = np.mean(centroid_list, axis=0)
                    
                    # Step 2: grow edge element on recipient
                    for rv in grow_voids:
                        rv_set = set(rv['elements'])
                        other_rv_elems = set()
                        for ov in all_voids:
                            if ov is not rv:
                                other_rv_elems.update(ov['elements'])
                        
                        for elem_label in rv['elements']:
                            for neighbor in element_neighbors_dict.get(elem_label, set()):
                                if neighbor in used_elements:
                                    continue
                                if neighbor not in available_near_fiber and neighbor not in available_inter_matrix:
                                    continue
                                if target_near_ratio == 0.0 and neighbor in available_near_fiber:
                                    continue
                                if target_near_ratio == 1.0 and neighbor in available_inter_matrix:
                                    continue
                                nb_neighbors = element_neighbors_dict.get(neighbor, set())
                                if nb_neighbors & other_rv_elems:
                                    continue
                                # Strict node isolation
                                neighbor_nodes = element_nodes_dict.get(neighbor, set())
                                other_rv_nodes = set()
                                for ov in all_voids:
                                    if ov is not rv:
                                        for oe in ov['elements']:
                                            other_rv_nodes.update(element_nodes_dict.get(oe, set()))
                                if neighbor_nodes & other_rv_nodes:
                                    continue
                                
                                rv['elements'].append(neighbor)
                                rv['volume'] += element_volume_dict.get(neighbor, 0.0)
                                used_elements.add(neighbor)
                                available_near_fiber.discard(neighbor)
                                available_inter_matrix.discard(neighbor)
                                centroid_list = [element_centroid_dict[e] for e in rv['elements']]
                                rv['centroid'] = np.mean(centroid_list, axis=0)
                                w_adjusted = True
                                break
                        if w_adjusted:
                            break
            
            if not w_adjusted:
                print("    Cannot adjust w this iteration")
                consecutive_no_progress += 1
            
            elif current_w < target_near_ratio - w_tol:
                # w too low: transfer from inter_matrix to near_fiber
                inter_voids = [v for v in all_voids if v['type'] == 'inter_matrix' and len(v['elements']) > 1]
                near_voids = [v for v in all_voids if v['type'] == 'near_fiber' and v['elements']]
                
                if inter_voids and near_voids:
                    inter_voids.sort(key=lambda v: v['volume'], reverse=True)
                    donor_void = inter_voids[0]
                    elem_to_transfer = donor_void['elements'][-1]
                    
                    elem_centroid = element_centroid_dict[elem_to_transfer]
                    min_dist = float('inf')
                    recipient_void = near_voids[0]
                    for v in near_voids:
                        dist = np.linalg.norm(elem_centroid - v['centroid'])
                        if dist < min_dist:
                            min_dist = dist
                            recipient_void = v
                    
                    elem_neighbors_set = element_neighbors_dict.get(elem_to_transfer, set())
                    other_void_elems = set()
                    for ov in all_voids:
                        if ov is not donor_void and ov is not recipient_void:
                            other_void_elems.update(ov['elements'])
                    
                    if elem_neighbors_set & other_void_elems:
                        print("    Skipped transfer - would touch a third void")
                    else:
                        donor_void['elements'].remove(elem_to_transfer)
                        recipient_void['elements'].append(elem_to_transfer)
                        
                        elem_vol = element_volume_dict.get(elem_to_transfer, 0.0)
                        donor_void['volume'] -= elem_vol
                        recipient_void['volume'] += elem_vol
                        
                        if donor_void['elements']:
                            centroid_list = [element_centroid_dict[e] for e in donor_void['elements']]
                            donor_void['centroid'] = np.mean(centroid_list, axis=0)
                        centroid_list = [element_centroid_dict[e] for e in recipient_void['elements']]
                        recipient_void['centroid'] = np.mean(centroid_list, axis=0)
                else:
                    print("    Cannot adjust w (no suitable voids)")
    
    # ========== Final Verification ==========
    print("\n" + "="*70)
    print("FINAL VERIFICATION - CASE 4")
    print("="*70)
    
    near_volume = 0.0
    inter_volume = 0.0
    final_void_count = 0
    
    for v in all_voids:
        if v['elements']:
            final_void_count += 1
            if v['type'] == 'near_fiber':
                near_volume += v['volume']
            else:
                inter_volume += v['volume']
    
    final_total_volume = near_volume + inter_volume
    final_w = near_volume / max(final_total_volume, 1e-20)
    final_volume_ratio = final_total_volume / target_volume
    
    w_tol_final = w_tolerance_relaxed if w_relaxed else w_tolerance_strict
    theta_tol_final = theta_tolerance_relaxed if theta_relaxed else theta_tolerance_strict
    theta_lower_final = theta_lower_relaxed if theta_relaxed else theta_lower_strict
    theta_upper_final = theta_upper_relaxed if theta_relaxed else theta_upper_strict
    
    print("  Final theta:  {} (target: {} +/-{}, range: [{}, {}])".format(
        final_void_count, num_voids, theta_tol_final, theta_lower_final, theta_upper_final))
    print("  Final Vf:     {:.2f}% (target: 99-101%)".format(final_volume_ratio * 100))
    print("  Final w:      {:.4f} (target: {:.4f} +/-{:.1f}%)".format(
        final_w, target_near_ratio, w_tol_final * 100))
    
    theta_ok = (final_void_count >= theta_lower_final and final_void_count <= theta_upper_final)
    volume_ok = (final_volume_ratio >= 0.99 and final_volume_ratio <= 1.01)
    w_ok = (abs(final_w - target_near_ratio) <= w_tol_final)
    
    print("\n  Results:")
    print("      Theta: {}".format("PASS" if theta_ok else "FAIL (deviation: {})".format(final_void_count - num_voids)))
    print("      Volume: {}".format("PASS" if volume_ok else "FAIL (ratio: {:.2f}%)".format(final_volume_ratio * 100)))
    print("      w-value: {}".format("PASS" if w_ok else "FAIL (deviation: {:.4f})".format(abs(final_w - target_near_ratio))))
    
    relaxed_parts = []
    if theta_relaxed:
        relaxed_parts.append("theta")
    if w_relaxed:
        relaxed_parts.append("w")
    if relaxed_parts:
        print("\n  Note: Converged with RELAXED tolerances for: {}".format(", ".join(relaxed_parts)))
    else:
        print("\n  Note: Converged in STRICT mode (all tolerances met)")
    
    print("="*70 + "\n")
    
    # ========== Pre-finalize connectivity check (warning only) ==========
    print("\n  Pre-finalize connectivity check...")
    all_void_elems_check = set()
    elem_to_idx = {}
    valid_now = [v for v in all_voids if v['elements']]
    for idx, v in enumerate(valid_now):
        for e in v['elements']:
            all_void_elems_check.add(e)
            elem_to_idx[e] = idx
    connected_found = False
    for v in valid_now:
        for e in v['elements']:
            for nb in element_neighbors_dict.get(e, set()):
                if nb in all_void_elems_check and elem_to_idx.get(nb) != valid_now.index(v):
                    connected_found = True
                    break
            if connected_found:
                break
        if connected_found:
            break
    if connected_found:
        print("  WARNING: Connected voids detected — adjacency check may need review.")
    else:
        print("  Pre-finalize: no connected voids detected.")

    return _finalize_void_statistics(all_voids, element_neighbors_dict, element_volume_dict, element_centroid_dict)

########################################
def seed_growth_void_generation(part, matrix_element_labels, near_fiber_candidates, 
                                inter_matrix_candidates, element_volume_dict, 
                                element_centroid_dict, element_neighbors_dict,
                                fiber_nodes, fiber_element_labels, target_volume, 
                                num_voids, target_elements_per_void, target_near_ratio,
                                void_distribution_value, void_theta_value, void_priority,
                                avg_element_volume, element_nodes_dict):
    """
    5
    
    
    - void_distribution_value == 'Random' ==> w_is_random = True
    - void_theta_value == 'Random' ==> theta_is_random = True
    - void_priority: 1=(w), 2=(theta), 3=
    
    5
    1. w=Random, theta=Random
    2. w=Custom, theta=Random
    3. w=Random, theta=Custom
    4. w=Custom, theta=Custom, Distribution Priority (w)
    5. w=Custom, theta=Custom, Size Priority (theta)
    """
    
    # ==========  ==========
    w_is_random = (void_distribution_value == 'Random')
    theta_is_random = (void_theta_value == 'Random')
    
    print("\n" + "="*70)
    print("SEED GROWTH VOID GENERATION - MAIN DISPATCHER")
    print("="*70)
    
    # 
    if w_is_random:
        print("  w (distribution):  Random")
    else:
        if target_near_ratio is not None:
            print("  w (distribution):  Custom ({:.2f})".format(target_near_ratio))
        else:
            print("  w (distribution):  Custom (value: {})".format(void_distribution_value))
    
    if theta_is_random:
        print("  theta (size):      Random")
    else:
        print("  theta (size):      Custom ({})".format(num_voids))
    
    if not w_is_random and not theta_is_random:
        print("  Priority:          {}".format('Distribution (w)' if void_priority == 1 else 'Size (theta)'))
    
    print("="*70 + "\n")
    
    # ========== 12 ==========
    if w_is_random or (not w_is_random and theta_is_random):
        # 
        print("Preparing parameters for legacy functions...")
        
        # 1. RVEVf
        rve_volume = part.getVolume()
        target_vf = (target_volume / rve_volume) * 100.0  # 
        
        # 2. set
        all_matrix_elements = set(matrix_element_labels)
        all_fiber_elements = set(fiber_element_labels)
        
        # 3. 
        elem_neighbors = element_neighbors_dict
        elem_volumes = element_volume_dict
        total_volume = rve_volume
        
        # 4. matrix_elem_nodes and fiber_elem_nodes from pre-cached dict
        matrix_elem_nodes = {}
        for label in matrix_element_labels:
            matrix_elem_nodes[label] = element_nodes_dict.get(label, set())
        
        fiber_elem_nodes = {}
        for label in fiber_element_labels:
            fiber_elem_nodes[label] = element_nodes_dict.get(label, set())
        
        print("  RVE volume: {:.6e}".format(rve_volume))
        print("  Target Vf: {:.4f}%".format(target_vf))
        print("  Matrix elements: {}".format(len(all_matrix_elements)))
        print("  Fiber elements: {}".format(len(all_fiber_elements)))
    
    # ========== 5 ==========
    
    if w_is_random and theta_is_random:
        # ========== 1: w=Random, theta=Random ==========
        print(">>> Routing to CASE 1: Random w + Random theta")
        void_set, statistics = generate_voids_random_w_random_theta(
            target_vf, all_matrix_elements, all_fiber_elements,
            elem_neighbors, elem_volumes, total_volume,
            matrix_elem_nodes, fiber_elem_nodes)
        
        # 
        print("\nConverting to unified format...")
        all_voids = []
        
        # statisticsclusters
        if 'clusters_with_type' in statistics:
            for cluster_info in statistics['clusters_with_type']:
                element_list = list(cluster_info['cluster'])
                
                void_info = {
                    'elements': element_list,
                    'type': cluster_info['type'],
                    'volume': cluster_info['volume'],
                    'centroid': np.array([0.0, 0.0, 0.0])  # 
                }
                # 
                if void_info['elements']:
                    centroid_list = []
                    for e in void_info['elements']:
                        centroid_list.append(element_centroid_dict[e])
                    void_info['centroid'] = np.mean(centroid_list, axis=0)
                
                all_voids.append(void_info)
        
        print("  Converted {} clusters to void_info format".format(len(all_voids)))
        return all_voids, statistics
    
    elif not w_is_random and theta_is_random:
        # ========== 2: w=Custom, theta=Random ==========
        print(">>> Routing to CASE 2: Custom w + Random theta")
        target_w = target_near_ratio if target_near_ratio is not None else void_distribution_value
        void_set, statistics = generate_voids_custom_w_random_theta(
            target_vf, target_w, all_matrix_elements, all_fiber_elements,
            elem_neighbors, elem_volumes, total_volume,
            matrix_elem_nodes, fiber_elem_nodes)
        
        # 
        print("\nConverting to unified format...")
        all_voids = []
        
        # statisticsclusters
        if 'clusters_with_type' in statistics:
            for cluster_info in statistics['clusters_with_type']:
                element_list = list(cluster_info['cluster'])
                
                void_info = {
                    'elements': element_list,
                    'type': cluster_info['type'],
                    'volume': cluster_info['volume'],
                    'centroid': np.array([0.0, 0.0, 0.0])  # 
                }
                # 
                if void_info['elements']:
                    centroid_list = []
                    for e in void_info['elements']:
                        centroid_list.append(element_centroid_dict[e])
                    void_info['centroid'] = np.mean(centroid_list, axis=0)
                
                all_voids.append(void_info)
        
        print("  Converted {} clusters to void_info format".format(len(all_voids)))
        return all_voids, statistics
    
    elif w_is_random and not theta_is_random:
        # ========== 3: w=Random, theta=Custom ==========
        print(">>> Routing to CASE 3: Random w + Custom theta")
        return generate_voids_random_w_custom_theta(
            part, matrix_element_labels, near_fiber_candidates, inter_matrix_candidates,
            element_volume_dict, element_centroid_dict, element_neighbors_dict,
            fiber_nodes, target_volume, num_voids, target_elements_per_void,
            void_theta_value, avg_element_volume, fiber_element_labels, element_nodes_dict)
    
    else:
        # both w and theta are Custom — unified Case 4
        print(">>> Routing to CASE 4: Custom w + Custom theta")
        return generate_voids_custom_w_custom_theta(
            part, matrix_element_labels, near_fiber_candidates, inter_matrix_candidates,
            element_volume_dict, element_centroid_dict, element_neighbors_dict,
            fiber_nodes, target_volume, num_voids, target_elements_per_void,
            target_near_ratio, void_distribution_value, void_theta_value,
            avg_element_volume, fiber_element_labels, element_nodes_dict,
            void_priority=void_priority)


def select_seed_type(target_near_ratio, target_near_voids, target_inter_voids,
                     current_near_voids, current_inter_voids,
                     available_near_fiber, available_inter_matrix,
                     void_priority, current_volume, target_volume,
                     void_distribution_method, void_distribution_value,
                     current_near_volume=0.0, current_inter_volume=0.0):  # ← 
    """
    
    """
    # ==========  ==========
    if target_near_ratio is not None:
        if target_near_ratio == 0.0:
            return 'inter_matrix' if available_inter_matrix else None
        elif target_near_ratio == 1.0:
            return 'near_fiber' if available_near_fiber else None
    
    # ==========  ==========
    total_void_volume = current_near_volume + current_inter_volume
    current_ratio = current_near_volume / total_void_volume if total_void_volume > 0 else 0.0
    
    # ==========  ==========
    if void_priority == 1:  # w
        deviation = current_ratio - target_near_ratio
        
        # ±0.5%
        if deviation < -0.005:
            return 'near_fiber' if available_near_fiber else ('inter_matrix' if available_inter_matrix else None)
        elif deviation > 0.005:
            return 'inter_matrix' if available_inter_matrix else ('near_fiber' if available_near_fiber else None)
        else:
            # ±0.5%
            if available_near_fiber and available_inter_matrix:
                return 'near_fiber' if random.random() < target_near_ratio else 'inter_matrix'
            return 'near_fiber' if available_near_fiber else ('inter_matrix' if available_inter_matrix else None)
    elif void_priority == 2:
        # 
        if available_near_fiber and available_inter_matrix:
            return random.choice(['near_fiber', 'inter_matrix'])
        return 'near_fiber' if available_near_fiber else 'inter_matrix'
    
    else:  # void_priority == 3 
        # 
        if available_near_fiber and available_inter_matrix:
            return random.choice(['near_fiber', 'inter_matrix'])
        return 'near_fiber' if available_near_fiber else (
            'inter_matrix' if available_inter_matrix else None)

# ---------------------------------------------------------------------------
# Void shape factor (beta) helpers -- Phase 4 Step 1
# ---------------------------------------------------------------------------
# Module-level context used by the growth functions so we do not need to
# thread beta-related kwargs through every helper. set_active_void_beta_ctx()
# is called once at the start of create_void_set(); clear_active_void_beta_ctx()
# is called in a finally clause to guarantee state is reset even on error.
_VOID_BETA_CTX = None


def set_active_void_beta_ctx(beta_active, beta_value_fiber, beta_value_matrix, beta_orientation):
    global _VOID_BETA_CTX
    _VOID_BETA_CTX = {
        'active'           : bool(beta_active),
        'beta_fiber'       : float(beta_value_fiber),
        'beta_matrix'      : float(beta_value_matrix),
        'orientation_mode' : int(beta_orientation),
    }


def clear_active_void_beta_ctx():
    global _VOID_BETA_CTX
    _VOID_BETA_CTX = None


def get_active_void_beta_ctx():
    return _VOID_BETA_CTX


def _random_so3_rotation():
    """
    Uniformly random rotation matrix in SO(3) using a unit quaternion.
    """
    u1, u2, u3 = np.random.random(), np.random.random(), np.random.random()
    q = np.array([
        np.sqrt(1.0 - u1) * np.sin(2.0 * np.pi * u2),
        np.sqrt(1.0 - u1) * np.cos(2.0 * np.pi * u2),
        np.sqrt(u1)       * np.sin(2.0 * np.pi * u3),
        np.sqrt(u1)       * np.cos(2.0 * np.pi * u3),
    ])
    x, y, z, w = q
    R = np.array([
        [1.0 - 2.0*(y*y + z*z),       2.0*(x*y - z*w),       2.0*(x*z + y*w)],
        [      2.0*(x*y + z*w), 1.0 - 2.0*(x*x + z*z),       2.0*(y*z - x*w)],
        [      2.0*(x*z - y*w),       2.0*(y*z + x*w), 1.0 - 2.0*(x*x + y*y)],
    ])
    return R


def _orthogonal_rotation_for_beta(beta):
    """
    Axis-aligned envelope orientation. Prolate (beta > 1) aligns along X
    (the fiber axis); oblate (beta < 1) is naturally compressed along Z
    so identity is sufficient. Sphere (beta == 1) -- identity.
    """
    return np.eye(3)


def _envelope_axes_for_beta(beta):
    """
    Map beta to the envelope ellipsoid semi-axes (a, b, c).
    beta = 1.0 -> sphere   (1, 1, 1)
    beta > 1.0 -> prolate (beta, 1, 1) along the principal axis
    beta < 1.0 -> oblate  (1, 1, beta) along the compressed axis
    """
    if beta is None or beta <= 0.0:
        return (1.0, 1.0, 1.0)
    if abs(beta - 1.0) < 1e-9:
        return (1.0, 1.0, 1.0)
    if beta > 1.0:
        return (float(beta), 1.0, 1.0)
    return (1.0, 1.0, float(beta))


def _resolve_void_rotation(orientation_mode, beta):
    """
    Pick a rotation matrix for the envelope ellipsoid given the orientation
    mode (1 = random SO(3), 2 = orthogonal/axis-aligned) and beta value.
    """
    if orientation_mode == 2:
        return _orthogonal_rotation_for_beta(beta)
    # default = random SO(3)
    return _random_so3_rotation()


def beta_weighted_selection(candidates, seed_centroid, element_centroid_dict,
                            rotation_matrix, envelope_axes):
    """
    Same purpose as distance_weighted_selection_debug, but distances are
    measured in the local frame of an ellipsoid envelope. The envelope axes
    (a, b, c) come from the beta shape factor; the rotation matrix orients
    the envelope (random SO(3) or axis-aligned).
    """
    if not candidates:
        return None

    seed_centroid = np.array(seed_centroid, dtype=float)
    R = np.array(rotation_matrix, dtype=float)
    a, b, c = envelope_axes
    inv_axes = np.array([
        1.0 / max(a, 1e-9),
        1.0 / max(b, 1e-9),
        1.0 / max(c, 1e-9),
    ])

    metric = []
    for label in candidates:
        centroid = np.array(element_centroid_dict[label], dtype=float)
        # Express the offset in the local frame of the envelope.
        local = R.T.dot(centroid - seed_centroid)
        scaled = local * inv_axes
        d = np.linalg.norm(scaled)
        metric.append(d)

    metric = np.array(metric)
    metric = np.maximum(metric, 1e-10)
    weights = 1.0 / metric
    weights = weights / np.sum(weights)

    selected_idx = np.random.choice(len(candidates), p=weights)
    return candidates[selected_idx]


def distance_weighted_selection_debug(candidates, seed_centroid, element_centroid_dict):
    """
     ()
    """
    
    if not candidates:
        return None
    
    distances = []
    for i, label in enumerate(candidates):
        centroid = element_centroid_dict[label]
        
        # numpy
        if not isinstance(seed_centroid, np.ndarray):
            seed_centroid = np.array(seed_centroid)
        if not isinstance(centroid, np.ndarray):
            centroid = np.array(centroid)
        
        dist = np.linalg.norm(centroid - seed_centroid)
        distances.append(dist)
    
    distances = np.array(distances)
    distances = np.maximum(distances, 1e-10)
    
    weights = 1.0 / distances
    weights = weights / np.sum(weights)
    
    selected_idx = np.random.choice(len(candidates), p=weights)
    
    return candidates[selected_idx]


###################################################

# ---------------------------------------------------------------------------
# Per-void PCA envelope + fiber-surface destruction metrics -- Phase 4 Step 1
# ---------------------------------------------------------------------------
def compute_void_envelope(element_labels, element_centroid_dict):
    """
    Run a PCA on the centroids of the constituent elements of one void
    and return (half_axes, direction_cosines, similarity_to_envelope).

    half_axes: (h1, h2, h3) sorted descending — 1-sigma half-extents
               (= sqrt of eigenvalues of the centroid covariance).
    direction_cosines: 3x3 matrix [e1, e2, e3] as columns; each column is a
                       unit eigenvector in global (X, Y, Z) coordinates.
    similarity_to_envelope: cosine similarity between the principal axis
                            (e1) and the global X (fiber) axis. Always
                            non-negative (we take abs).
    """
    centroids = []
    for lbl in element_labels:
        if lbl in element_centroid_dict:
            centroids.append(element_centroid_dict[lbl])
    if len(centroids) < 2:
        return ((0.0, 0.0, 0.0),
                np.eye(3).tolist(),
                0.0)
    arr = np.array(centroids, dtype=float)
    # np.cov expects features in rows; arr is N x 3 -> transpose.
    cov = np.cov(arr.T)
    # Force symmetric covariance to be safe; use eigh on symmetric matrices.
    eigvals, eigvecs = np.linalg.eigh(cov)
    # eigh returns ascending; sort descending.
    order = np.argsort(eigvals)[::-1]
    eigvals  = eigvals[order]
    eigvecs  = eigvecs[:, order]
    half_axes = tuple([float(np.sqrt(max(v, 0.0))) for v in eigvals])
    # Similarity to fiber X-axis (1, 0, 0)
    e1 = eigvecs[:, 0]
    similarity = abs(float(np.dot(e1, np.array([1.0, 0.0, 0.0]))))
    return (half_axes, eigvecs.tolist(), similarity)


def _gini_coefficient(values):
    """
    Standard Gini coefficient for a non-negative 1-D array. Returns 0
    when the array is empty or all-zero.
    """
    arr = np.array([v for v in values if v >= 0.0], dtype=float)
    if arr.size == 0:
        return 0.0
    arr = np.sort(arr)
    s = arr.sum()
    if s <= 0.0:
        return 0.0
    n = arr.size
    cum = np.cumsum(arr)
    return float((n + 1 - 2.0 * np.sum(cum) / s) / n)


def compute_fiber_surface_destruction(part, all_voids, fiber_coords,
                                      element_nodes_dict, rve_a, rve_b,
                                      fiber_radius=None):
    """
    Estimate per-fiber surface destruction using a node-count proxy:
      * For each fiber center (y0, z0) in 2D (the 3D Y-axis is the fiber
        axis in this RVE; (-Z, Y) are the in-plane coords used elsewhere
        but here we keep the 3D coords directly), find all nodes whose
        in-plane (Y, Z) distance to the fiber axis lies in a thin annulus
        around the fiber radius -- these are "interface nodes".
      * "Broken interface nodes" are interface nodes that belong to at
        least one void element.

    Returns:
        per_fiber: list of dicts {fiber_id, perimeter (proxy = N_i),
                                  area_total (= N_i), area_broken (= B_i),
                                  ratio (= B_i / N_i)}
        metrics:   dict with keys f_fiber, f_area, r_avg_broken, C_focus, Gini
    """
    per_fiber = []
    metrics = {
        'f_fiber'     : 0.0,
        'f_area'      : 0.0,
        'r_avg_broken': 0.0,
        'C_focus'     : 0.0,
        'Gini'        : 0.0,
    }
    if not fiber_coords:
        return per_fiber, metrics

    # Collect node coords once.
    node_xyz = {}
    for n in part.nodes:
        node_xyz[n.label] = np.array(n.coordinates)

    # Build the set of nodes belonging to ANY void.
    void_node_set = set()
    for v in all_voids:
        for lbl in v.get('elements', []):
            void_node_set |= element_nodes_dict.get(lbl, set())

    # Pick a tolerance: half a typical element edge, or 2% of in-plane span.
    tol = 0.02 * max(rve_a, rve_b)
    if fiber_radius is not None and fiber_radius > 0:
        # Tighter band when the radius is known.
        tol = max(tol, 0.05 * fiber_radius)

    # fiber_coords here are 2D (x, y) where x = -Z, y = Y (per
    # convert_3d_to_2d_coordinates). Convert each fiber center back to
    # (Y, Z) so we can compare with node coords directly.
    sorted_node_labels = list(node_xyz.keys())
    node_arr = np.array([node_xyz[k] for k in sorted_node_labels])  # N x 3

    r_values = []
    for f_idx, (fx, fy) in enumerate(fiber_coords):
        # x = -Z  =>  Z = -fx ; y = Y
        z0 = -fx
        y0 = fy
        # In-plane (Y, Z) distance from each node to the fiber axis.
        dy = node_arr[:, 1] - y0
        dz = node_arr[:, 2] - z0
        dist = np.sqrt(dy * dy + dz * dz)

        if fiber_radius is not None and fiber_radius > 0:
            mask = np.abs(dist - fiber_radius) <= tol
        else:
            # Treat the first quartile of distances as the interface band.
            mask = dist <= np.percentile(dist, 5)

        interface_labels = [sorted_node_labels[i] for i, m in enumerate(mask) if m]
        if not interface_labels:
            per_fiber.append({
                'fiber_id'   : f_idx + 1,
                'perimeter'  : 0,
                'area_total' : 0,
                'area_broken': 0,
                'ratio'      : 0.0,
            })
            r_values.append(0.0)
            continue
        Ni = len(interface_labels)
        Bi = len([lbl for lbl in interface_labels if lbl in void_node_set])
        ri = float(Bi) / float(Ni)
        per_fiber.append({
            'fiber_id'   : f_idx + 1,
            'perimeter'  : Ni,
            'area_total' : Ni,
            'area_broken': Bi,
            'ratio'      : ri,
        })
        r_values.append(ri)

    Nf = len(per_fiber)
    if Nf == 0:
        return per_fiber, metrics

    affected = [r for r in r_values if r > 0]
    sum_total  = float(sum([pf['area_total'] for pf in per_fiber]))
    sum_broken = float(sum([pf['area_broken'] for pf in per_fiber]))

    metrics['f_fiber']      = float(len(affected)) / float(Nf)
    metrics['f_area']       = (sum_broken / sum_total) if sum_total > 0 else 0.0
    metrics['r_avg_broken'] = (float(np.mean(affected)) if affected else 0.0)
    metrics['C_focus']      = (metrics['r_avg_broken'] / metrics['f_area']) if metrics['f_area'] > 0 else 0.0
    metrics['Gini']         = _gini_coefficient(r_values)

    return per_fiber, metrics


def output_void_statistics(model_name, part, all_voids, void_statistics,
                          rve_volume, target_vf, element_volume_dict,
                          element_centroid_dict, near_fiber_candidates,
                          rve_a, rve_b, rve_c,
                          void_distribution_method, void_distribution_value,
                          void_size_method, void_theta_value, void_priority,
                          fiber_coords, element_nodes_dict=None,
                          fiber_radius=None):
    """
    Write the void statistics report and accompanying CSV outputs.
    The optional element_nodes_dict and fiber_radius arguments enable the
    fiber-surface destruction metrics (Phase 4 Step 1).
    """
    
    # 
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    folder_name = "Void_Statistics_{}_{}".format(model_name, timestamp)
    work_dir = os.getcwd()
    output_folder = os.path.join(work_dir, folder_name)
    
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    
    # ==========  ==========
    volumes_list = []
    centroids_list = []
    for v in all_voids:
        volumes_list.append(v['volume'])
        centroids_list.append(v['centroid'])
    
    volumes = np.array(volumes_list)
    centroids = np.array(centroids_list)
    
    total_void_volume = 0.0
    for vol in volumes_list:
        total_void_volume += vol
    realized_vf = total_void_volume / rve_volume * 100
    
    # 
    mean_volume = np.mean(volumes) if len(volumes) > 0 else 0
    std_volume = np.std(volumes) if len(volumes) > 0 else 0
    min_volume = np.min(volumes) if len(volumes) > 0 else 0
    max_volume = np.max(volumes) if len(volumes) > 0 else 0
    
    # 
    num_near_fiber = 0
    num_inter_matrix = 0
    near_fiber_volume = 0.0
    inter_matrix_volume = 0.0
    
    for v in all_voids:
        if v['type'] == 'near_fiber':
            num_near_fiber += 1
            near_fiber_volume += v['volume']
        else:
            num_inter_matrix += 1
            inter_matrix_volume += v['volume']
    
    # ==========  ==========
    near_fiber_vf = realized_vf * (near_fiber_volume / max(total_void_volume, 1e-20))
    inter_matrix_vf = realized_vf * (inter_matrix_volume / max(total_void_volume, 1e-20))
    
    # ==========  ==========
    # 
    if void_distribution_method == 1:
        distribution_method_str = "Random"
        distribution_value_str = "N/A (Random)"
    else:
        distribution_method_str = "Custom"
        distribution_value_str = "{:.2f} (0=all inter-matrix, 1=all near-fiber)".format(void_distribution_value)
    
    # 
    if void_size_method == 1:
        size_method_str = "Random"
        size_value_str = "N/A (Random)"
    else:
        size_method_str = "Custom (theta)"
        size_value_str = "{} voids".format(void_theta_value)
    
    # 
    if void_priority == 1:
        priority_str = "Distribution Priority (strict w)"
    elif void_priority == 2:
        priority_str = "Size Priority (allow w deviation)"
    else:
        priority_str = "No Intervention"
    
    # ========== 1.  ==========
    report_file = os.path.join(output_folder, "void_summary_report.txt")
    
    with open(report_file, 'w') as f:
        f.write("=" * 70 + "\n")
        f.write("            MICRO-VOID INSERTION SUMMARY REPORT\n")
        f.write("=" * 70 + "\n\n")
        f.write("Model: {}\n".format(model_name))
        f.write("Generated: {}\n\n".format(time.strftime("%Y-%m-%d %H:%M:%S")))
        
        f.write("-" * 70 + "\n")
        f.write("USER INPUT PARAMETERS\n")
        f.write("-" * 70 + "\n")
        f.write("  Target Void Vf:           {:.4f}%\n".format(target_vf * 100))
        f.write("  Distribution Method:      {}\n".format(distribution_method_str))
        f.write("  Distribution Value (w):   {}\n".format(distribution_value_str))
        f.write("  Size Method:              {}\n".format(size_method_str))
        f.write("  Size Value (theta):       {}\n".format(size_value_str))
        f.write("  Priority Setting:         {}\n\n".format(priority_str))
        
        f.write("-" * 70 + "\n")
        f.write("RVE DIMENSIONS\n")
        f.write("-" * 70 + "\n")
        f.write("  RVE size (a x b x c): {:.4f} x {:.4f} x {:.4f}\n".format(rve_a, rve_b, rve_c))
        f.write("  RVE Volume:           {:.6e}\n\n".format(rve_volume))
        
        f.write("-" * 70 + "\n")
        f.write("VOLUME FRACTION RESULTS\n")
        f.write("-" * 70 + "\n")
        f.write("  Target Void Vf:     {:.4f}%\n".format(target_vf * 100))
        f.write("  Realized Void Vf:   {:.4f}%\n".format(realized_vf))
        f.write("  Total Void Volume:  {:.6e}\n".format(total_void_volume))
        f.write("  Deviation:          {:.4f}%\n\n".format(abs(realized_vf - target_vf * 100)))
        
        # ========== 1VOID COUNT AND SIZE  ==========
        f.write("-" * 70 + "\n")
        f.write("VOID COUNT AND SIZE (θ)\n")
        f.write("-" * 70 + "\n")
        f.write("  Target number:      {}\n".format(
            void_theta_value if void_size_method == 2 else "N/A (volume-based)"))
        
        # num_voidsnum_valid_voids
        num_voids = void_statistics.get('num_voids', len(all_voids))
        num_valid_voids = void_statistics.get('num_valid_voids', num_voids)
        
        f.write("  Actual voids (physically disconnected): {}\n".format(num_valid_voids))

        if num_valid_voids < num_voids:
            f.write("  WARNING: {} voids became empty during post-processing\n".format(
                num_voids - num_valid_voids))
        
        # ==========  ==========
        f.write("  Near-fiber voids (count):   {} ({:.2f}%)\n".format(
            num_near_fiber, num_near_fiber / max(len(all_voids), 1) * 100))
        f.write("  Inter-matrix voids (count): {} ({:.2f}%)\n".format(
            num_inter_matrix, num_inter_matrix / max(len(all_voids), 1) * 100))
        
        f.write("  Mean Volume:        {:.6e}\n".format(mean_volume))
        f.write("  Std Volume:         {:.6e}\n".format(std_volume))
        f.write("  Min Volume:         {:.6e}\n".format(min_volume))
        f.write("  Max Volume:         {:.6e}\n\n".format(max_volume))
        
        # ========== 2VOID DISTRIBUTION RESULTS  ==========
        f.write("-" * 70 + "\n")
        f.write("VOID DISTRIBUTION RESULTS (w)\n")
        f.write("-" * 70 + "\n")
        f.write("  Near-fiber volume:          {:.6e}\n".format(near_fiber_volume))
        f.write("  Inter-matrix volume:        {:.6e}\n".format(inter_matrix_volume))
        f.write("  Near-fiber volume fraction:     {:.4f}%\n".format(near_fiber_vf))
        f.write("  Inter-matrix volume fraction:   {:.4f}%\n".format(inter_matrix_vf))
        
        # ========== w==========
        actual_w = near_fiber_volume / max(total_void_volume, 1e-20)
        f.write("  Actual w value:             {:.4f} (volume-based)\n".format(actual_w))
        if void_distribution_method == 2:
            f.write("  Target w value:             {:.4f}\n".format(void_distribution_value))
            f.write("  w Deviation:                {:.4f}\n".format(abs(actual_w - void_distribution_value)))
        else:
            f.write("  Target w value:             /\n")
        
        f.write("\n" + "=" * 70 + "\n")
        f.write("Note: All spatial statistics computed with periodic boundary conditions.\n")
        f.write("      w value is defined as (near-fiber void volume) / (total void volume).\n")
        f.write("Output folder: {}\n".format(output_folder))

    
    # ========== 2. void_sizes.csv (extended with PCA envelope) ==========
    size_file = os.path.join(output_folder, "void_sizes.csv")
    with open(size_file, 'w') as f:
        f.write("Void_ID,Type,Volume,Num_Elements,Centroid_X,Centroid_Y,Centroid_Z,"
                "HalfAxis_1,HalfAxis_2,HalfAxis_3,"
                "e1x,e1y,e1z,e2x,e2y,e2z,e3x,e3y,e3z,"
                "Similarity_e1_to_X\n")
        for i, void_info in enumerate(all_voids):
            try:
                half_axes, eigvecs, similarity = compute_void_envelope(
                    void_info.get('elements', []), element_centroid_dict)
                e1 = eigvecs[0]
                e2 = eigvecs[1]
                e3 = eigvecs[2]
            except Exception:
                half_axes = (0.0, 0.0, 0.0)
                e1, e2, e3 = [1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]
                similarity = 0.0
            f.write("{},{},{:.6e},{},{:.6f},{:.6f},{:.6f},"
                    "{:.6e},{:.6e},{:.6e},"
                    "{:.6f},{:.6f},{:.6f},{:.6f},{:.6f},{:.6f},{:.6f},{:.6f},{:.6f},"
                    "{:.6f}\n".format(
                i + 1, void_info['type'], void_info['volume'],
                len(void_info['elements']),
                void_info['centroid'][0], void_info['centroid'][1], void_info['centroid'][2],
                half_axes[0], half_axes[1], half_axes[2],
                e1[0], e1[1], e1[2],
                e2[0], e2[1], e2[2],
                e3[0], e3[1], e3[2],
                similarity
            ))

    # ========== 2b. Per-fiber surface destruction CSV + summary metrics ==========
    if fiber_coords and element_nodes_dict is not None:
        try:
            per_fiber, fs_metrics = compute_fiber_surface_destruction(
                part, all_voids, fiber_coords, element_nodes_dict,
                rve_a, rve_b, fiber_radius=fiber_radius)
        except Exception as _exc:
            print("  [warn] Fiber-surface destruction metrics failed: {}".format(_exc))
            per_fiber, fs_metrics = [], {
                'f_fiber': 0.0, 'f_area': 0.0, 'r_avg_broken': 0.0,
                'C_focus': 0.0, 'Gini': 0.0}

        if per_fiber:
            breakdown_file = os.path.join(output_folder, "void_fiber_surface_breakdown.csv")
            with open(breakdown_file, 'w') as f:
                f.write("Fiber_ID,Perimeter_proxy,Area_total,Area_broken,Ratio\n")
                for pf in per_fiber:
                    f.write("{},{},{},{},{:.6f}\n".format(
                        pf['fiber_id'], pf['perimeter'],
                        pf['area_total'], pf['area_broken'], pf['ratio']))

        # Append the 5 concentration metrics to the summary report.
        try:
            with open(report_file, 'a') as f:
                f.write("\n" + "-" * 70 + "\n")
                f.write("FIBER-SURFACE DESTRUCTION METRICS\n")
                f.write("-" * 70 + "\n")
                f.write("  f_fiber       = {:.4f}  (fraction of fibers with any destruction)\n".format(fs_metrics['f_fiber']))
                f.write("  f_area        = {:.4f}  (overall broken-area ratio)\n".format(fs_metrics['f_area']))
                f.write("  r_avg_broken  = {:.4f}  (mean ratio over affected fibers)\n".format(fs_metrics['r_avg_broken']))
                f.write("  C_focus       = {:.4f}  (= r_avg_broken / f_area)\n".format(fs_metrics['C_focus']))
                f.write("  Gini(r_i)     = {:.4f}  (concentration coefficient)\n".format(fs_metrics['Gini']))
                f.write("\nPer-fiber breakdown: void_fiber_surface_breakdown.csv\n")
        except Exception as _exc:
            print("  [warn] Could not append fiber-surface metrics to report: {}".format(_exc))

    # ========== 3. ==========
    if len(all_voids) >= 2:
        nn1_distances, nn2_distances = calculate_void_nn_distances_periodic(
            centroids, rve_a, rve_b, rve_c)
        # NN
        nn_file = os.path.join(output_folder, "void_nn_distances.csv")
        with open(nn_file, 'w') as f:
            f.write("Void_ID,NN1_Distance,NN2_Distance\n")
            for i in range(len(all_voids)):
                f.write("{},{:.6f},{:.6f}\n".format(i + 1, nn1_distances[i], nn2_distances[i]))

        # Ripley's Kg(r)
        if len(all_voids) >= 3:
            r_ripley, K_values, K_random = calculate_ripleys_k_void_periodic(
                centroids, rve_a, rve_b, rve_c)
            
            r_pdf, g_values = calculate_void_pdf_periodic(
                centroids, rve_a, rve_b, rve_c)
            
            # Ripley's K
            ripley_file = os.path.join(output_folder, "void_ripleys_k.csv")
            with open(ripley_file, 'w') as f:
                f.write("r_distance,K_observed,K_random\n")
                for r, k, kr in zip(r_ripley, K_values, K_random):
                    f.write("{:.6f},{:.6f},{:.6f}\n".format(r, k, kr))
            
            # g(r)
            pdf_file = os.path.join(output_folder, "void_pair_distribution.csv")
            with open(pdf_file, 'w') as f:
                f.write("r_distance,g_r\n")
                for r, g in zip(r_pdf, g_values):
                    f.write("{:.6f},{:.6f}\n".format(r, g))
    
    # ========== 4. -==========
    if fiber_coords:
        fiber_surface_distances = calculate_void_fiber_distances_periodic(
            all_voids, fiber_coords, rve_a, rve_b)
        
        # 
        fiber_dist_file = os.path.join(output_folder, "void_fiber_distances.csv")
        with open(fiber_dist_file, 'w') as f:
            f.write("Void_ID,NN1_to_Fiber,NN2_to_Fiber\n")
            for i, (d1, d2) in enumerate(fiber_surface_distances):
                f.write("{},{:.6f},{:.6f}\n".format(i + 1, d1, d2))
    
    # 
    print("\n" + "=" * 70)
    print("VOID STATISTICS SUMMARY (Periodic Boundary)")
    print("=" * 70)
    print("  RVE size:                {:.4f} x {:.4f} x {:.4f}".format(rve_a, rve_b, rve_c))
    print("  Number of voids:         {}".format(len(all_voids)))
    print("  Near-fiber (count):      {} ({:.2f}%)".format(
        num_near_fiber, num_near_fiber / max(len(all_voids), 1) * 100))
    print("  Inter-matrix (count):    {} ({:.2f}%)".format(
        num_inter_matrix, num_inter_matrix / max(len(all_voids), 1) * 100))
    print("  Mean void volume:        {:.6e}".format(mean_volume))
    print("  Volume std dev:          {:.6e}".format(std_volume))
    print("  Realized Vf:             {:.4f}%".format(realized_vf))
    print("  Near-fiber Vf:           {:.4f}%".format(near_fiber_vf))
    print("  Inter-matrix Vf:         {:.4f}%".format(inter_matrix_vf))
    print("  Actual w value:          {:.4f} (volume-based)".format(actual_w))
    print("  Output folder:           {}".format(output_folder))
    print("=" * 70 + "\n")


def convert_3d_to_2d_coordinates(node_coords_3d):
    """
    3D2D
    
    y90
     (x, y) ->  (x, y, z) ->  (z, y, -x)
    
    3D (X, Y, Z)  2D  (x, y) = (-Z, Y)
    
    Args:
        node_coords_3d: 3D [X, Y, Z]  [[X1, Y1, Z1], [X2, Y2, Z2], ...]
    
    Returns:
        coords_2d: 2D [x, y]  [[x1, y1], [x2, y2], ...]
    """
    import numpy as np
    
    coords_array = np.array(node_coords_3d)
    
    # 
    if coords_array.ndim == 1:
        x_2d = -coords_array[2]  # -Z
        y_2d = coords_array[1]   # Y
        return [x_2d, y_2d]
    
    # 
    else:
        x_2d = -coords_array[:, 2]  # -Z
        y_2d = coords_array[:, 1]   # Y
        return np.column_stack([x_2d, y_2d]).tolist()

def extract_fiber_centers(part, model_name=None, work_dir=None, rve_a=None, rve_b=None):
    """
    CSVCSV
    
    Args:
        part: Abaqus part
        model_name: 
        work_dir: 
        rve_a, rve_b: RVE
    
    Returns:
        fiber_coords:  [[x, y], ...]2D
    """
    print("\n========== FIBER CENTER EXTRACTION (CSV Only) ==========")
    
    if not model_name or not work_dir:
        raise ValueError("ERROR: model_name and work_dir are required for CSV extraction")
    
    # CSV
    csv_path = find_fiber_coordinates_csv(model_name, work_dir)
    
    if not csv_path:
        raise ValueError("ERROR: Cannot find CSV file for model: {}".format(model_name))
    
    # CSV
    fiber_coords = read_fiber_coordinates_from_csv(csv_path)
    
    if not fiber_coords:
        raise ValueError("ERROR: Failed to read coordinates from CSV: {}".format(csv_path))
    
    print("  Total fibers from CSV: {}".format(len(fiber_coords)))
    print("  Coordinate system: Original 2D (x, y)")
    print("=" * 60 + "\n")
    
    return fiber_coords

def calculate_void_nn_distances_periodic(centroids, a, b, c):
    """
    
    
    """
    import numpy as np
    n = len(centroids)
    
    # volumes
    
    nn1_distances = []
    nn2_distances = []
    
    for i in range(n):
        distances = []
        for j in range(n):
            if i != j:
                # 
                center_dist = calculate_periodic_distance_3d(centroids[i], centroids[j], a, b, c)
                distances.append(center_dist)
        
        distances.sort()
        nn1_distances.append(distances[0] if len(distances) > 0 else 0)
        nn2_distances.append(distances[1] if len(distances) > 1 else 0)
    
    return nn1_distances, nn2_distances

def calculate_ripleys_k_void_periodic(centroids, a, b, c, 
                                      max_r_value=None, num_points=100):
    """
    Ripley's K
    
    """
    import numpy as np
    n = len(centroids)
    volume = a * b * c
    intensity = n / volume
    
    # ✅ volumes
    
    # ✅ 
    all_center_distances = []
    for i in range(n):
        for j in range(i+1, n):
            center_dist = calculate_periodic_distance_3d(centroids[i], centroids[j], a, b, c)
            all_center_distances.append(center_dist)
    
    if not all_center_distances:
        return [], [], []
    
    if max_r_value is None:
        max_r_value = max(all_center_distances) * 1.5
    
    r_values = np.linspace(0, max_r_value, num_points)
    K_values = []
    
    for r in r_values:
        if r == 0:
            K_values.append(0)
            continue
        
        count = 0
        for d in all_center_distances:
            if d < r:
                count += 1
        count = count * 2
        
        K = count / (n * intensity) if n * intensity > 0 else 0
        K_values.append(K)
    
    # 3D
    #K_random = [(4.0/3.0) * np.pi * r**3 for r in r_values]
    # 2D
    K_random = [np.pi * r**2 for r in r_values]
    
    return r_values, K_values, K_random

def calculate_void_pdf_periodic(centroids, a, b, c, 
                                max_r_value=None, num_bins=100):
    """
     g(r)3D
    
    """
    import numpy as np
    n = len(centroids)
    volume = a * b * c
    intensity = n / volume
    
    # volumes
    
    # 
    all_center_distances = []
    for i in range(n):
        for j in range(i+1, n):
            center_dist = calculate_periodic_distance_3d(centroids[i], centroids[j], a, b, c)
            all_center_distances.append(center_dist)
    
    if not all_center_distances:
        return [], []
    
    if max_r_value is None:
        max_r_value = max(all_center_distances) * 1.2
    
    r_values = np.linspace(0, max_r_value, num_bins)
    g_values = []
    dr = r_values[1] - r_values[0] if len(r_values) > 1 else 1.0
    
    for r in r_values:
        if r == 0:
            g_values.append(0)
            continue
        
        shell_volume = 4 * np.pi * r**2 * dr
        expected_count = intensity * shell_volume * n
        
        if expected_count == 0:
            g_values.append(0)
            continue
        
        actual_count = 0
        for d in all_center_distances:
            if r - dr/2 < d < r + dr/2:
                actual_count += 1
        actual_count = actual_count * 2
        
        g = actual_count / expected_count if expected_count > 0 else 0
        g_values.append(g)
    
    return r_values, g_values


def find_fiber_coordinates_csv(model_name, work_dir):
    """
    CSV
    
    Args:
        model_name:  'RVE_UDFiber_Random_Df7_Vf060_N70_Model_1'
        work_dir: 
    
    Returns:
        csv_path: CSVNone
    """
    
    # 
    model_number_match = re.search(r'_Model_(\d+)$', model_name)
    if not model_number_match:
        print("  WARNING: Cannot extract model number from: {}".format(model_name))
        return None
    
    model_number = int(model_number_match.group(1))
    model_number_str = "{:02d}".format(model_number)  # 
    
    print("  Model number: {} -> CSV suffix: {}".format(model_number, model_number_str))
    
    # 3
    search_dirs = [work_dir]
    current_dir = work_dir
    
    for _ in range(3):
        parent_dir = os.path.dirname(current_dir)
        if parent_dir == current_dir:
            break
        search_dirs.append(parent_dir)
        current_dir = parent_dir
    
    # 
    for search_dir in search_dirs:
        folder_pattern = os.path.join(search_dir, "RVE_UDFibers*_Vf*_xy_*units")
        matching_folders = glob.glob(folder_pattern)
        
        for folder in matching_folders:
            csv_pattern = os.path.join(folder, "*IncCoordinates{}.csv".format(model_number_str))
            matching_csvs = glob.glob(csv_pattern)
            
            if matching_csvs:
                csv_path = matching_csvs[0]
                print("  Found CSV: {}".format(csv_path))
                return csv_path
    
    print("  WARNING: No CSV file found for model number {}".format(model_number_str))
    return None

def read_fiber_coordinates_from_csv(csv_path):
    """
    CSV
    
    Args:
        csv_path: CSV
    
    Returns:
        coords:  [[x, y], [x, y], ...]None
    """
    import csv
    
    coords = []
    
    try:
        with open(csv_path, 'r') as f:
            csv_reader = csv.reader(f)
            
            # 
            first_row = next(csv_reader, None)
            if first_row:
                # 
                try:
                    x = float(first_row[0])
                    y = float(first_row[1])
                    coords.append([x, y])
                except (ValueError, IndexError):
                    # 
                    pass
            
            # 
            for row in csv_reader:
                if len(row) >= 2:
                    try:
                        x = float(row[0])
                        y = float(row[1])
                        coords.append([x, y])
                    except ValueError:
                        continue
        
        print("  Successfully read {} fiber coordinates from CSV".format(len(coords)))
        return coords
    
    except Exception as e:
        print("  ERROR reading CSV file: {}".format(e))
        return None

def calculate_distance_to_fiber_axis_periodic(void_centroid_3d, fiber_center_2d, a, b):
    """
    void2D
    
    Args:
        void_centroid_3d: void [X, Y, Z]3D
        fiber_center_2d:  [x, y]2DCSV
        a, b: RVEx, y2D
    
    Returns:
        void2D
    """
    import numpy as np
    
    # ========== 3D2D ==========
    void_xy_2d = convert_3d_to_2d_coordinates(void_centroid_3d)
    void_xy = np.array(void_xy_2d)  # 2D
    fiber_xy = np.array(fiber_center_2d)  # CSV2D
    
    # 2D
    dx = abs(void_xy[0] - fiber_xy[0])
    dy = abs(void_xy[1] - fiber_xy[1])
    
    dx = min(dx, a - dx)
    dy = min(dy, b - dy)
    
    # 2D
    distance = np.sqrt(dx**2 + dy**2)
    
    return distance

def calculate_void_fiber_distances_periodic(all_voids, fiber_coords, a, b):
    """
    2D
    
    Args:
        all_voids:  {'centroid': [X, Y, Z], ...}3D
        fiber_coords:  [[x, y], ...]2DCSV
        a, b: RVEx, y2D
    
    Returns:
        void_fiber_distances: [(NN1, NN2), ...] void
    """
    
    void_fiber_distances = []
    
    for void_info in all_voids:
        void_centroid_3d = void_info['centroid']  # 3D
        
        distances = []
        for fiber_xy in fiber_coords:  # 2DCSV
            # void
            dist = calculate_distance_to_fiber_axis_periodic(
                void_centroid_3d, fiber_xy, a, b)
            
            distances.append(dist)
        
        distances.sort()
        nn1 = distances[0] if len(distances) > 0 else 0
        nn2 = distances[1] if len(distances) > 1 else 0
        void_fiber_distances.append((nn1, nn2))
    
    return void_fiber_distances

###############################################################################
################################# for Interphase ##############################
###############################################################################
def Interface(model_for_interface, part_for_interface, interface_material, Model_range_interface, **kwargs):
    separator = "-" * 100
    created_models = []
    initial_debonding_ratio = float(kwargs.get('interface_initial_debonding', 0.0) or 0.0) / 100.0
    if initial_debonding_ratio < 0.0 or initial_debonding_ratio > 1.0:
        raise ValueError("Initial debonding ratio D must be in [0, 100]%.")
    initial_debonding_label = format_interface_debonding_label(initial_debonding_ratio * 100.0)

    # ---- interface purpose: 'mechanical' (cohesive) or 'thermal' (gap cond.)
    interface_purpose = str(kwargs.get('interface_purpose', 'mechanical') or 'mechanical').strip().lower()
    is_thermal = interface_purpose.startswith('therm') or interface_purpose == '2'
    kapitza_resistance = kwargs.get('kapitza_resistance', None)
    if is_thermal and (kapitza_resistance is None or float(kapitza_resistance) <= 0.0):
        raise ValueError("Thermal interface requires a positive Kapitza "
                         "resistance (units mm^2*K/W).")

    def process_one_model(source_model_name, copy_materials_from=None, interface_odb_file_name=None):
        # ---- protection: refuse if the source already has ANY interface ----
        if model_contains_cohesive_elements(source_model_name, part_for_interface) or \
           _model_contains_thermal_seam(source_model_name, part_for_interface):
            raise ValueError(
                "The selected model '{}'\n"
                "already contains an interface (cohesive seam or thermal "
                "contact). Re-inserting an interface on top of an existing one "
                "corrupts the mesh -- choose a fresh, interface-free model "
                "and try again.".format(source_model_name)
            )
        num_nodes_RVE, num_elements_RVE = Calnum_nodes(source_model_name, part_for_interface)
        new_model_name, new_part = copy_model_for_cohesive(source_model_name, initial_debonding_label)
        if copy_materials_from is not None and interface_odb_file_name is not None:
            for material_name in copy_materials_from.materials.keys():
                if material_name not in mdb.models[new_model_name].materials.keys():
                    mdb.models[new_model_name].materialsFromOdb(fileName=interface_odb_file_name)
        if is_thermal:
            summary = insert_thermal_seam(
                new_model_name, part_for_interface,
                kapitza_resistance, num_nodes_RVE, num_elements_RVE
            )
            summary['interface_kind'] = 'thermal'
            if 'cohesive' in new_model_name:
                thermal_name = new_model_name.replace('cohesive', 'thermal')
                if thermal_name not in mdb.models.keys():
                    mdb.models.changeKey(fromName=new_model_name, toName=thermal_name)
                    new_model_name = thermal_name
            created_models.append((new_model_name, summary))
        else:
            summary = insert_cohesive_seam(
                new_model_name, part_for_interface, interface_material,
                num_nodes_RVE, num_elements_RVE, initial_debonding_ratio
            )
            summary['interface_kind'] = 'cohesive'
            final_debonding_label = format_interface_debonding_label(summary['final_debonding_ratio'] * 100.0)
            final_model_name = rename_cohesive_model_with_final_debonding(
                source_model_name, new_model_name, final_debonding_label
            )
            summary['final_debonding_label'] = final_debonding_label
            new_model_name = final_model_name
            created_models.append((new_model_name, summary))

    if Model_range_interface == 1:
        process_one_model(model_for_interface)
    elif Model_range_interface == 2:
        select_model_interface = mdb.models[model_for_interface]
        model_name_prefix = model_for_interface.rsplit('_', 1)[0] + '_'
        # Thermal interfaces ignore the cohesive material, so skip the material
        # export job (it has no step and would abort with 'NO STEP DEFINITION').
        interface_odb_file_name = None if is_thermal else export_materials_to_odb_interface(model_for_interface)
        for model_name in mdb.models.keys():
            if model_name.startswith(model_name_prefix) and 'cohesive' not in model_name:
                process_one_model(model_name, select_model_interface, interface_odb_file_name)
    elif Model_range_interface == 3:
        interface_odb_file_name = None if is_thermal else export_materials_to_odb_interface(model_for_interface)
        user_input_interface = kwargs.get('user_input_interface')
        model_name_prefix = model_for_interface.rsplit('_', 1)[0] + '_'
        source_model = mdb.models[model_for_interface]
        valid_selected_model_names = parse_user_input(user_input_interface, model_name_prefix)
        for model_name in mdb.models.keys():
            if model_name in valid_selected_model_names:
                process_one_model(model_name, source_model, interface_odb_file_name)

    report_lines = []
    report_lines.append(' ')
    report_lines.append(separator)
    report_lines.append('-------------------------------------- Interface Information ---------------------------------------')
    report_lines.append(separator)
    report_lines.append('Successfully inserted fibre-matrix interface:')
    for created_model_name, summary in created_models:
        report_lines.append('==> {}'.format(created_model_name))
        if summary.get('interface_kind') == 'thermal':
            report_lines.append('    Interface type: THERMAL (surface-to-surface contact + gap conductance)')
            report_lines.append('    Fiber elements set: {}; matrix elements set: {}; interface faces: {}'.format(
                summary['fiber_set_name'], summary['matrix_set_name'], summary['interface_face_count']))
            report_lines.append('    Split nodes: FiberSide={}, MatrixSide={}; inserted nodes: {}'.format(
                summary['fiber_side_count'], summary['matrix_side_count'], summary['inserted_node_count']))
            report_lines.append('    Kapitza resistance R_K = {:.4g}  ->  gap conductance h = {:.4g}'.format(
                summary['kapitza_resistance'], summary['gap_conductance']))
        else:
            report_lines.append('    Interface type: MECHANICAL (cohesive seam, traction-separation)')
            report_lines.append('    Fiber elements set: {}; matrix elements set: {}; interface faces: {}'.format(
                summary['fiber_set_name'], summary['matrix_set_name'], summary['interface_face_count']))
            report_lines.append('    Cohesive elements: {}; inserted nodes: {}'.format(
                summary['cohesive_element_count'], summary['inserted_node_count']))
            report_lines.append('    Independent fiber interface geometries: {}'.format(
                summary['independent_fiber_interface_count']))
            report_lines.append('    Node sets: MatrixSide={}, FiberSide={}, CohesiveMid={}'.format(
                summary['matrix_side_count'], summary['fiber_side_count'], summary['cohesive_mid_count']))
            report_lines.append('    Shared fiber/matrix nodes after insertion: {}'.format(
                summary['shared_fiber_matrix_nodes']))
            report_lines.append('    Void-induced debonding D_void={:.2f}%; user D={:.2f}%; final D={:.2f}%'.format(
                summary['void_debonding_ratio'] * 100.0,
                summary['requested_debonding_ratio'] * 100.0,
                summary['final_debonding_ratio'] * 100.0))
            if summary['requested_debonding_ratio'] < summary['void_debonding_ratio']:
                report_lines.append('    User D is smaller than void-induced debonding; no extra artificial debonding was applied.')
            elif summary['artificial_debonded_count'] > 0:
                report_lines.append('    Artificially removed cohesive elements by label: {}'.format(
                    summary['artificial_debonded_count']))
            if summary['group_keep_protected_count'] > 0:
                report_lines.append('    Cohesive elements protected by per-fiber-geometry keep rule: {}'.format(
                    summary['group_keep_protected_count']))
    report_lines.append(separator)
    report_lines.append(' ')
    for line in report_lines:
        print(line)
    if len(created_models) == 1:
        report_name = 'Interface_Information_{}'.format(created_models[0][0])
    else:
        report_label = created_models[0][1].get('final_debonding_label', initial_debonding_label) if created_models else initial_debonding_label
        report_name = 'Interface_Information_Batch_{}'.format(report_label)
    report_path = unique_interface_report_path(os.getcwd(), report_name)
    report_file = open(report_path, 'w')
    try:
        report_file.write('\n'.join(report_lines))
        report_file.write('\n')
    finally:
        report_file.close()
    print('Interface report saved to: {}'.format(report_path))

def Calnum_nodes(model_for_interface, part_for_interface='UDComposite'):
    model = mdb.models[model_for_interface]
    p = model.parts[part_for_interface] if part_for_interface in model.parts.keys() else model.parts['UDComposite']
    num_nodes_RVE = len(p.nodes)
    num_elements_RVE = len(p.elements)

    return num_nodes_RVE, num_elements_RVE

def model_contains_cohesive_elements(model_name, part_name='UDComposite'):
    model = mdb.models[model_name]
    part = model.parts[part_name] if part_name in model.parts.keys() else model.parts['UDComposite']
    if 'CohesiveSeam-1-Elements' in part.sets.keys():
        return True
    for element in part.elements:
        try:
            element_type_text = str(element.type).upper()
        except Exception:
            element_type_text = ''
        if element_type_text.startswith('COH') or 'COHESIVE' in element_type_text:
            return True
    return False


def _model_contains_thermal_seam(model_name, part_name='UDComposite'):
    """True if the model already has a THERMAL interface (ThermalSeam sets or
    the thermal contact interaction) -- used to block double-insertion."""
    model = mdb.models[model_name]
    p = model.parts[part_name] if part_name in model.parts.keys() else model.parts['UDComposite']
    for s in p.sets.keys():
        if str(s).startswith('ThermalSeam'):
            return True
    try:
        if 'ThermalSeam-1-Contact' in model.interactions.keys():
            return True
    except Exception:
        pass
    return False

def _interface_element_labels_from_set(part, set_name):
    if set_name not in part.sets.keys():
        return set()
    return set([element.label for element in part.sets[set_name].elements])

def _interface_element_labels_from_set_or_cells(part, set_name):
    labels = _interface_element_labels_from_set(part, set_name)
    if labels:
        return labels
    if set_name in part.sets.keys() and hasattr(part.sets[set_name], 'cells') and part.sets[set_name].cells:
        labels = set()
        for cell in part.sets[set_name].cells:
            for element in cell.getElements():
                labels.add(element.label)
    return labels

def _interface_select_matrix_all_element_labels(part):
    for set_name in ('Set-Matrix-element', 'Set-Matrix'):
        labels = _interface_element_labels_from_set_or_cells(part, set_name)
        if labels:
            return set_name, labels
    raise ValueError("Interface insertion requires Set-Matrix-element or Set-Matrix.")

def _interface_select_matrix_element_set(part):
    void_labels = _interface_element_labels_from_set(part, 'Set-void')
    for set_name in ('Set-Matrix-element-novoid', 'Set-Matrix-element'):
        if set_name in part.sets.keys():
            labels = _interface_element_labels_from_set_or_cells(part, set_name)
            if labels:
                if void_labels:
                    labels = labels - void_labels
                if labels:
                    return set_name, labels
    if 'Set-Matrix' in part.sets.keys():
        labels = _interface_element_labels_from_set_or_cells(part, 'Set-Matrix')
        if labels:
            if void_labels:
                labels = labels - void_labels
                if not labels:
                    raise ValueError("Set-Matrix contains only void elements after subtracting Set-void.")
            return 'Set-Matrix-minus-void' if void_labels else 'Set-Matrix', labels
    raise ValueError("Interface insertion requires Set-Matrix-element-novoid, Set-Matrix-element, or Set-Matrix.")

def _interface_select_fiber_element_labels(part):
    for set_name in ('Set-Fiber-element', 'Set-Fiber'):
        if set_name in part.sets.keys():
            labels = _interface_element_labels_from_set_or_cells(part, set_name)
            if labels:
                return set_name, labels
    raise ValueError("Interface insertion requires Set-Fiber-element or Set-Fiber.")

def _interface_create_node_set_from_elements(part, set_name, element_labels):
    node_labels = set()
    for element in part.elements.sequenceFromLabels(_abaqus_label_tuple(element_labels)):
        for node in element.getNodes():
            node_labels.add(node.label)
    if node_labels:
        if set_name in part.sets.keys():
            del part.sets[set_name]
        part.Set(nodes=part.nodes.sequenceFromLabels(_abaqus_label_tuple(sorted(node_labels))), name=set_name)
    return node_labels

def _interface_filtered_faces(part, fiber_labels, matrix_labels, matrix_all_labels, void_labels):
    if 'Set-Interface' not in part.sets.keys():
        raise ValueError("Interface insertion requires Set-Interface from the geometry construction step.")
    candidate_faces = part.sets['Set-Interface'].faces
    filtered_faces = []
    api_supported = False
    perfect_face_count = 0
    for face in candidate_faces:
        try:
            face_elements = face.getElements()
            api_supported = True
        except Exception:
            continue
        face_labels = set([element.label for element in face_elements])
        is_perfect_interface = (face_labels & fiber_labels) and (face_labels & matrix_all_labels)
        if not is_perfect_interface:
            continue
        perfect_face_count += 1
        filtered_faces.append(face)
    if api_supported:
        if not filtered_faces:
            raise ValueError("Set-Interface contains no faces shared by Set-Fiber and non-void matrix elements.")
        return filtered_faces, {
            'perfect_face_count': perfect_face_count,
        }
    if 'Set-void' in part.sets.keys():
        raise ValueError("Cannot verify Set-Interface against Set-Matrix-element-novoid because face.getElements() is unavailable; aborting to avoid inserting cohesive elements on void boundaries.")
    print("[Interface] Warning: face.getElements() is unavailable; using Set-Interface as the fiber-matrix candidate face set.")
    return candidate_faces, {
        'perfect_face_count': len(candidate_faces),
    }

def _interface_faces_to_face_array(part, faces):
    face_array = None
    for face in faces:
        try:
            picked_face = part.faces.findAt((face.pointOn[0],))
        except Exception:
            picked_face = part.faces[face.index:face.index + 1]
        if face_array is None:
            face_array = picked_face
        else:
            face_array += picked_face
    if face_array is None:
        raise ValueError("No valid fiber-matrix interface faces were found for cohesive insertion.")
    return face_array

def _interface_make_bottom_nodes(part, top_nodes, max_original_label, tolerance=1.0e-7):
    top_coord_keys = set()
    for node in top_nodes:
        top_coord_keys.add(tuple([round(float(value) / tolerance) for value in node.coordinates]))
    bottom_labels = []
    for node in part.nodes:
        if node.label > max_original_label:
            continue
        key = tuple([round(float(value) / tolerance) for value in node.coordinates])
        if key in top_coord_keys:
            bottom_labels.append(node.label)
    return bottom_labels

def _interface_coord_key(coordinates, tolerance=1.0e-7):
    return tuple([round(float(value) / tolerance) for value in coordinates])

def _interface_set_nodes_by_labels(part, set_name, node_labels):
    if set_name in part.sets.keys():
        del part.sets[set_name]
    if node_labels:
        wanted_labels = set(node_labels)
        node_array = None
        for index, node in enumerate(part.nodes):
            if node.label in wanted_labels:
                picked_nodes = part.nodes[index:index + 1]
                if node_array is None:
                    node_array = picked_nodes
                else:
                    node_array += picked_nodes
        if node_array is None or len(node_array) != len(wanted_labels):
            found_count = 0 if node_array is None else len(node_array)
            raise ValueError(
                "Failed to create {}: requested {} node labels, found {} nodes in the part.".format(
                    set_name, len(wanted_labels), found_count
                )
            )
        part.Set(nodes=node_array, name=set_name)

def _interface_set_elements_by_labels(part, set_name, element_labels):
    if set_name in part.sets.keys():
        del part.sets[set_name]
    wanted_labels = set(element_labels)
    if not wanted_labels:
        raise ValueError("Cannot create {} because no element labels were provided.".format(set_name))
    element_array = None
    for index, element in enumerate(part.elements):
        if element.label in wanted_labels:
            picked_elements = part.elements[index:index + 1]
            if element_array is None:
                element_array = picked_elements
            else:
                element_array += picked_elements
    if element_array is None or len(element_array) != len(wanted_labels):
        found_count = 0 if element_array is None else len(element_array)
        raise ValueError(
            "Failed to create {}: requested {} element labels, found {} elements in the part.".format(
                set_name, len(wanted_labels), found_count
            )
        )
    part.Set(elements=element_array, name=set_name)
    return element_array

def _interface_delete_elements_by_labels(part, element_labels):
    if not element_labels:
        return
    delete_elements = _interface_set_elements_by_labels(part, 'Set-Interface-InitialDebonding-ToDelete', element_labels)
    try:
        part.deleteElement(elements=delete_elements)
    except Exception as error:
        raise RuntimeError("Failed to delete initial-debonded cohesive elements: {}".format(error))
    if 'Set-Interface-InitialDebonding-ToDelete' in part.sets.keys():
        del part.sets['Set-Interface-InitialDebonding-ToDelete']

def _interface_element_node_map(part, element_labels):
    node_map = {}
    if not element_labels:
        return node_map
    for element in part.elements.sequenceFromLabels(_abaqus_label_tuple(sorted(element_labels))):
        node_map[element.label] = set([node.label for node in element.getNodes()])
    return node_map

def _interface_classify_void_debonded_cohesive_labels(part, cohesive_labels, matrix_side_labels, matrix_labels, void_labels):
    matrix_side_set = set(matrix_side_labels)
    void_node_map = _interface_element_node_map(part, void_labels)
    matrix_node_map = _interface_element_node_map(part, matrix_labels)
    void_debonded = []
    for cohesive_element in part.elements.sequenceFromLabels(_abaqus_label_tuple(sorted(cohesive_labels))):
        cohesive_node_labels = set([node.label for node in cohesive_element.getNodes()])
        side_nodes = cohesive_node_labels & matrix_side_set
        if not side_nodes:
            continue
        touches_void_face = False
        for void_nodes in void_node_map.values():
            if side_nodes.issubset(void_nodes):
                touches_void_face = True
                break
        if not touches_void_face:
            continue
        touches_matrix_face = False
        for matrix_nodes in matrix_node_map.values():
            if side_nodes.issubset(matrix_nodes):
                touches_matrix_face = True
                break
        if not touches_matrix_face:
            void_debonded.append(cohesive_element.label)
    return sorted(void_debonded)

def _interface_group_cohesive_by_side_nodes(part, cohesive_labels, side_node_labels):
    side_node_set = set(side_node_labels)
    element_side_nodes = {}
    node_to_elements = {}
    for cohesive_element in part.elements.sequenceFromLabels(_abaqus_label_tuple(sorted(cohesive_labels))):
        side_nodes = set([node.label for node in cohesive_element.getNodes()]) & side_node_set
        element_side_nodes[cohesive_element.label] = side_nodes
        for node_label in side_nodes:
            node_to_elements.setdefault(node_label, set()).add(cohesive_element.label)
    groups = []
    visited = set()
    for label in sorted(element_side_nodes.keys()):
        if label in visited:
            continue
        stack = [label]
        group = set()
        visited.add(label)
        while stack:
            current = stack.pop()
            group.add(current)
            for node_label in element_side_nodes.get(current, set()):
                for neighbor in node_to_elements.get(node_label, set()):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        stack.append(neighbor)
        groups.append(group)
    return groups

def _interface_apply_group_keep_rule(delete_labels, cohesive_groups, preferred_keep_labels=None):
    delete_set = set(delete_labels)
    preferred_keep_set = set(preferred_keep_labels or [])
    protected_labels = []
    for group in cohesive_groups:
        if group and group.issubset(delete_set):
            preferred_labels = sorted(group & preferred_keep_set)
            keep_label = preferred_labels[0] if preferred_labels else min(group)
            delete_set.remove(keep_label)
            protected_labels.append(keep_label)
    return sorted(delete_set), protected_labels

def _interface_choose_initial_debond_labels(cohesive_labels, requested_d, void_d, cohesive_groups=None):
    labels = sorted(cohesive_labels)
    if requested_d <= void_d or not labels:
        return []
    delete_fraction = max(0.0, min(1.0, (requested_d - void_d) / max(1.0 - void_d, 1.0e-12)))
    delete_count = int(round(delete_fraction * len(labels)))
    if delete_count <= 0:
        return []
    random.seed(1)
    selected = sorted(random.sample(labels, delete_count))
    if cohesive_groups:
        selected, protected_labels = _interface_apply_group_keep_rule(selected, cohesive_groups)
    return selected

def _interface_split_coincident_seam_nodes(part, original_node_labels, tolerance=1.0e-7):
    original_nodes = [node for node in part.nodes if node.label in original_node_labels]
    original_coord_keys = set([_interface_coord_key(node.coordinates, tolerance) for node in original_nodes])
    new_nodes = [node for node in part.nodes if node.label not in original_node_labels]
    new_coord_keys = set([_interface_coord_key(node.coordinates, tolerance) for node in new_nodes])
    interface_coord_keys = original_coord_keys & new_coord_keys
    coincident_labels = sorted([
        node.label for node in part.nodes
        if _interface_coord_key(node.coordinates, tolerance) in interface_coord_keys
    ])
    if len(coincident_labels) % 3 != 0:
        raise ValueError(
            "The number of coincident cohesive interface nodes ({}) cannot be split equally into Top/Bottom/Mid sets.".format(
                len(coincident_labels)
            )
        )
    layer_size = int(len(coincident_labels) / 3)
    if layer_size <= 0:
        raise ValueError("No coincident cohesive interface nodes were found.")
    return (
        coincident_labels[0:layer_size],
        coincident_labels[layer_size:2 * layer_size],
        coincident_labels[2 * layer_size:3 * layer_size],
    )

def insert_cohesive_seam(model_for_interface_cohesive, part_for_interface, interface_material, num_nodes_RVE, num_elements_RVE, requested_debonding_ratio=0.0):
    model = mdb.models[model_for_interface_cohesive]
    p = model.parts[part_for_interface] if part_for_interface in model.parts.keys() else model.parts['UDComposite']
    original_node_labels = set([node.label for node in p.nodes])
    fiber_set_name, fiber_labels = _interface_select_fiber_element_labels(p)
    matrix_all_set_name, matrix_all_labels = _interface_select_matrix_all_element_labels(p)
    matrix_set_name, matrix_labels = _interface_select_matrix_element_set(p)
    void_labels = _interface_element_labels_from_set(p, 'Set-void')
    interface_faces, area_stats = _interface_filtered_faces(p, fiber_labels, matrix_labels, matrix_all_labels, void_labels)
    interface_faces = _interface_faces_to_face_array(p, interface_faces)
    if 'Set-Interface-FiberMatrix' in p.sets.keys():
        del p.sets['Set-Interface-FiberMatrix']
    p.Set(faces=interface_faces, name='Set-Interface-FiberMatrix')

    mdb.meshEditOptions.setValues(enableUndo=True, maxUndoCacheElements=0.5)
    region_interface = regionToolset.Region(side1Faces=p.sets['Set-Interface-FiberMatrix'].faces)
    try:
        p.insertElements(faces=region_interface)
    except Exception as error:
        raise RuntimeError(
            "Failed to insert cohesive elements on Set-Interface-FiberMatrix. "
            "Please make sure the model is meshed and Set-Interface contains only internal fiber/non-void-matrix faces. "
            "Abaqus error: {}".format(error)
        )
    p = model.parts[part_for_interface] if part_for_interface in model.parts.keys() else model.parts['UDComposite']
    num_nodes_RVE_cohesive = len(p.nodes)
    num_elements_RVE_cohesive = len(p.elements)
    inserted_cohesive_labels = [element.label for element in p.elements[num_elements_RVE:num_elements_RVE_cohesive]]
    bottom_labels, top_labels, mid_labels = _interface_split_coincident_seam_nodes(p, original_node_labels)
    cohesive_groups = _interface_group_cohesive_by_side_nodes(p, inserted_cohesive_labels, top_labels)
    raw_void_delete_labels = _interface_classify_void_debonded_cohesive_labels(
        p, inserted_cohesive_labels, bottom_labels, matrix_labels, void_labels
    )
    preferred_keep_labels = set(inserted_cohesive_labels) - set(raw_void_delete_labels)
    void_delete_labels, void_protected_labels = _interface_apply_group_keep_rule(
        raw_void_delete_labels, cohesive_groups, preferred_keep_labels
    )
    void_debonding_ratio = float(len(void_delete_labels)) / float(len(inserted_cohesive_labels)) if inserted_cohesive_labels else 0.0
    artificial_candidate_labels = [label for label in inserted_cohesive_labels if label not in set(void_delete_labels)]
    artificial_delete_labels = _interface_choose_initial_debond_labels(
        artificial_candidate_labels,
        requested_debonding_ratio,
        void_debonding_ratio,
        cohesive_groups,
    )
    delete_labels = sorted(set(void_delete_labels) | set(artificial_delete_labels))
    delete_labels, artificial_protected_labels = _interface_apply_group_keep_rule(
        delete_labels, cohesive_groups, preferred_keep_labels
    )
    artificial_delete_labels = sorted(set(artificial_delete_labels) & set(delete_labels))
    if delete_labels:
        _interface_delete_elements_by_labels(p, delete_labels)
        p = model.parts[part_for_interface] if part_for_interface in model.parts.keys() else model.parts['UDComposite']

    remaining_count = max(0, len(inserted_cohesive_labels) - len(delete_labels))
    remaining_cohesive_labels = [element.label for element in p.elements[num_elements_RVE:num_elements_RVE + remaining_count]]
    _interface_set_elements_by_labels(p, 'CohesiveSeam-1-Elements', remaining_cohesive_labels)
    bottom_labels, top_labels, mid_labels = _interface_split_coincident_seam_nodes(p, original_node_labels)
    cohesive_node_labels = set()
    for element in p.sets['CohesiveSeam-1-Elements'].elements:
        for node in element.getNodes():
            cohesive_node_labels.add(node.label)
    bottom_labels = [label for label in bottom_labels if label in cohesive_node_labels]
    top_labels = [label for label in top_labels if label in cohesive_node_labels]
    mid_labels = [label for label in mid_labels if label in cohesive_node_labels]
    p.Surface(face2Elements=p.sets['CohesiveSeam-1-Elements'].elements, name='CohesiveSeam-1-TopSurf')
    p.Surface(face1Elements=p.sets['CohesiveSeam-1-Elements'].elements, name='CohesiveSeam-1-BottomSurf')
    _interface_set_nodes_by_labels(p, 'CohesiveSeam-1-FiberSideNodes', top_labels)
    _interface_set_nodes_by_labels(p, 'CohesiveSeam-1-MatrixSideNodes', bottom_labels)
    _interface_set_nodes_by_labels(p, 'CohesiveSeam-1-CohesiveMidNodes', mid_labels)
    _interface_set_nodes_by_labels(p, 'CohesiveSeam-1-TopNodes', top_labels)
    _interface_set_nodes_by_labels(p, 'CohesiveSeam-1-BottomNodes', bottom_labels)
    _interface_set_nodes_by_labels(p, 'CohesiveSeam-1-MidNodes', mid_labels)

    fiber_nodes = _interface_create_node_set_from_elements(p, 'Set-Fiber-Nodes', fiber_labels)
    matrix_nodes = _interface_create_node_set_from_elements(p, 'Set-Matrix-NoVoid-Nodes', matrix_labels)
    cohesive_nodes = set()
    for element in p.sets['CohesiveSeam-1-Elements'].elements:
        for node in element.getNodes():
            cohesive_nodes.add(node.label)

    model.CohesiveSection(name='Interface_Section', response=TRACTION_SEPARATION, material=interface_material, outOfPlaneThickness=None)
    p.SectionAssignment(region=p.sets['CohesiveSeam-1-Elements'],sectionName='Interface_Section', offset=0.0, offsetType=MIDDLE_SURFACE, offsetField='', thicknessAssignment=FROM_SECTION)
    # Force the cohesive seam to plain mechanical cohesive types COH3D8 /
    # COH3D6, NOT the pore-pressure COH3D8P/COH3D6P assigned by default.
    # This RVE is purely mechanical: the interface elements must carry
    # displacement DOF only (no pore-pressure DOF).  Both hex and wedge
    # types are supplied so each seam element keeps its own topology.
    p.setElementType(
        regions=(p.sets['CohesiveSeam-1-Elements'].elements,),
        elemTypes=(mesh.ElemType(elemCode=COH3D8, elemLibrary=STANDARD),
                   mesh.ElemType(elemCode=COH3D6, elemLibrary=STANDARD)))
    session.viewports['Viewport: 1'].setValues(displayedObject=p)
    session.viewports['Viewport: 1'].partDisplay.setValues(mesh=ON)
    cmap=session.viewports['Viewport: 1'].colorMappings['Material']
    session.viewports['Viewport: 1'].setColor(colorMapping=cmap)
    session.viewports['Viewport: 1'].disableMultipleColors()
    final_debonding_ratio = (
        float(len(delete_labels)) / float(len(inserted_cohesive_labels)) if inserted_cohesive_labels else 0.0
    )
    return {
        'fiber_set_name': fiber_set_name,
        'matrix_set_name': matrix_set_name,
        'matrix_all_set_name': matrix_all_set_name,
        'interface_face_count': len(interface_faces),
        'cohesive_element_count': len(p.sets['CohesiveSeam-1-Elements'].elements),
        'inserted_node_count': num_nodes_RVE_cohesive - num_nodes_RVE,
        'matrix_side_count': len(p.sets['CohesiveSeam-1-MatrixSideNodes'].nodes),
        'fiber_side_count': len(p.sets['CohesiveSeam-1-FiberSideNodes'].nodes),
        'cohesive_mid_count': len(p.sets['CohesiveSeam-1-CohesiveMidNodes'].nodes),
        'shared_fiber_matrix_nodes': len(fiber_nodes & matrix_nodes),
        'cohesive_node_count': len(cohesive_nodes),
        'perfect_interface_area': float(len(inserted_cohesive_labels)),
        'allowed_interface_area': float(len(inserted_cohesive_labels) - len(void_delete_labels)),
        'void_debonding_ratio': void_debonding_ratio,
        'requested_debonding_ratio': requested_debonding_ratio,
        'final_debonding_ratio': final_debonding_ratio,
        'artificial_debonded_count': len(artificial_delete_labels),
        'void_interface_face_count': len(void_delete_labels),
        'independent_fiber_interface_count': len(cohesive_groups),
        'group_keep_protected_count': len(set(void_protected_labels) | set(artificial_protected_labels)),
    }

def _thermal_build_side_surface(p, node_label_set, surf_name, allowed_face_keys=None):
    """Build an orphan-mesh surface from the SOLID-element faces whose nodes
    all lie on one split side of the interface (node_label_set).
    NOTE (verify in Abaqus): relies on MeshElement.getElemFaces() returning
    faces in face1..face6 order; the faceN-Elements kwargs are grouped by that
    index.  If a face is mismatched in testing, this is the place to adjust."""
    arrname = {0: 'face1Elements', 1: 'face2Elements', 2: 'face3Elements',
               3: 'face4Elements', 4: 'face5Elements', 5: 'face6Elements'}
    allowed_face_keys = set(allowed_face_keys or [])

    # ---- Pass 1: count how many solid elements share each mesh face.
    # After the zero-thickness layer is deleted, an interface face belongs to a
    # single element (free face, count == 1); a face interior to the solid is
    # shared by two elements (count == 2). We use this to pick the genuine
    # interface face, instead of the first face whose nodes merely lie on the
    # split side -- a flat wedge/sliver element can have several such faces, and
    # picking the wrong one flips its facet normal ("facets not oriented
    # properly with respect to each other").
    face_share = {}
    for el in p.elements:
        if str(el.type).upper().startswith('COH'):
            continue
        try:
            faces = el.getElemFaces()
        except Exception:
            continue
        for face in faces:
            key = frozenset([n.label for n in face.getNodes()])
            if key:
                face_share[key] = face_share.get(key, 0) + 1

    # ---- Pass 2: for each element, select the FREE face whose nodes all lie on
    # the split side. That face is the interface face, with an outward normal
    # consistent across neighbouring elements.
    buckets = {}
    for el in p.elements:
        if str(el.type).upper().startswith('COH'):
            continue
        try:
            faces = el.getElemFaces()
        except Exception:
            continue
        for fi, face in enumerate(faces):
            fnodes = [n.label for n in face.getNodes()]
            if not fnodes:
                continue
            face_key = frozenset(fnodes)
            if allowed_face_keys and face_key not in allowed_face_keys:
                continue
            if not all([(lbl in node_label_set) for lbl in fnodes]):
                continue
            if face_share.get(face_key, 0) != 1:
                continue  # interior (shared) face -- skip, keep only free faces
            buckets.setdefault(fi, []).append(el.label)
            break
    if not buckets:
        raise RuntimeError("Thermal interface: could not build surface '%s' "
            "(no solid faces matched the split-side nodes)." % surf_name)
    kwargs = {}
    for fi, labels in buckets.items():
        kwargs[arrname[fi]] = p.elements.sequenceFromLabels(_abaqus_label_tuple(labels))
    if surf_name in p.surfaces.keys():
        del p.surfaces[surf_name]
    p.Surface(name=surf_name, **kwargs)

def _thermal_face_keys_for_elements(p, element_labels):
    face_keys = set()
    labels = tuple(sorted(set(element_labels or [])))
    if not labels:
        return face_keys
    for element in p.elements.sequenceFromLabels(_abaqus_label_tuple(labels)):
        if str(element.type).upper().startswith('COH'):
            continue
        try:
            faces = element.getElemFaces()
        except Exception:
            continue
        for face in faces:
            key = frozenset([node.label for node in face.getNodes()])
            if key:
                face_keys.add(key)
    return face_keys

def _thermal_inserted_side_face_keys(p, inserted_labels, fiber_side_labels, matrix_side_labels,
                                     void_labels=None):
    """Return non-void split-side face node keys from the temporary seam layer."""
    fiber_side_set = set(fiber_side_labels)
    matrix_side_set = set(matrix_side_labels)
    void_face_keys = _thermal_face_keys_for_elements(p, void_labels)
    fiber_face_keys = set()
    matrix_face_keys = set()
    skipped_void_faces = 0
    if not inserted_labels:
        return fiber_face_keys, matrix_face_keys, skipped_void_faces
    for element in p.elements.sequenceFromLabels(_abaqus_label_tuple(inserted_labels)):
        node_labels = [node.label for node in element.getNodes()]
        fiber_face = frozenset([label for label in node_labels if label in fiber_side_set])
        matrix_face = frozenset([label for label in node_labels if label in matrix_side_set])
        if void_face_keys and matrix_face in void_face_keys:
            skipped_void_faces += 1
            continue
        if len(fiber_face) >= 3:
            fiber_face_keys.add(fiber_face)
        if len(matrix_face) >= 3:
            matrix_face_keys.add(matrix_face)
    return fiber_face_keys, matrix_face_keys, skipped_void_faces


# ---------------------------------------------------------------------------
# Thermal-interface coupling method.  Flip THERMAL_SEAM_METHOD to test:
#   'tie'      : TIE constraint = PERFECT thermal contact (infinite h).
#                In a heat-transfer step *TIE ties the temperature DOF, so this
#                is the validation baseline -- it should recover the fully
#                bonded (no-interface) conductivity. Use it to confirm the two
#                split surfaces conduct properly before trusting gap values.
#   'gap_n2s'  : gap conductance, NODE-TO-SURFACE discretisation. Best for the
#                coincident, conforming, curved fibre interface: each secondary
#                node pairs with its coincident main facet at ~zero clearance,
#                avoiding the surface-to-surface projection clearance that made
#                the curved interface near-adiabatic.
#   'gap_s2s'  : gap conductance, SURFACE-TO-SURFACE discretisation (legacy).
# ---------------------------------------------------------------------------
THERMAL_SEAM_METHOD = 'gap_n2s'


def _create_paired(factory, name, main_surf, secondary_surf, **kw):
    """Create a contact/tie object, handling the Abaqus 2024 keyword rename
    main/secondary (older releases use master/slave).

    Only fall back to master/slave when the failure is actually about the
    surface keyword name; re-raise any other TypeError (e.g. an unsupported
    option) so the real culprit is not masked as 'keyword error on master'.
    """
    try:
        return factory(name=name, main=main_surf, secondary=secondary_surf, **kw)
    except TypeError as exc:
        msg = str(exc).lower()
        if 'main' in msg or 'secondary' in msg:
            return factory(name=name, master=main_surf, slave=secondary_surf, **kw)
        raise


def _force_node_to_surface(model, property_name):
    """Rewrite the generated contact pair to NODE-TO-SURFACE discretisation.
    CAE's SurfaceToSurfaceContactStd always emits 'type=SURFACE TO SURFACE';
    there is no direct discretisation toggle for contact pairs, so we patch the
    keyword block. Safe no-op if the pattern is not found."""
    try:
        kb = model.keywordBlock
        kb.synchVersions(storeNodesAndElements=False)
        for i, line in enumerate(kb.sieBlocks):
            up = line.upper()
            if 'CONTACT PAIR' in up and property_name.upper() in up \
               and 'SURFACE TO SURFACE' in up:
                kb.replace(i, line.replace('type=SURFACE TO SURFACE',
                                           'type=NODE TO SURFACE')
                              .replace('TYPE=SURFACE TO SURFACE',
                                       'type=NODE TO SURFACE'))
    except Exception as exc:
        print('[Interface] Could not switch contact to node-to-surface: {}'.format(exc))


def insert_thermal_seam(model_for_interface_thermal, part_for_interface,
                        kapitza_resistance, num_nodes_RVE, num_elements_RVE):
    """Zero-thickness THERMAL interface = surface-to-surface CONTACT PAIR with a
    constant *Gap Conductance  h = 1 / Kapitza_resistance.
    Reuses the same node-split as insert_cohesive_seam, then DELETES the
    inserted zero-thickness layer (a DC model must NOT contain COH elements),
    builds a surface on each free solid side, and links them by a thermal
    contact pair.  No cohesive elements / no material are created (gap
    conductance is a contact-interaction property, not a material).  Set names
    use the 'ThermalSeam-' prefix so the thermal kernel's cohesive-abort guard
    does not trip.  Units: kapitza_resistance in mm^2*K/W -> h in W/(mm^2*K)."""
    if kapitza_resistance is None or float(kapitza_resistance) <= 0.0:
        raise ValueError("Thermal interface: Kapitza resistance must be a "
                         "positive number (units mm^2*K/W).")
    gap_conductance = 1.0 / float(kapitza_resistance)

    model = mdb.models[model_for_interface_thermal]
    p = model.parts[part_for_interface] if part_for_interface in model.parts.keys() else model.parts['UDComposite']

    # ---- protection: refuse to insert on a model that already has an interface
    existing = [s for s in p.sets.keys()
                if s.startswith('ThermalSeam') or s.startswith('CohesiveSeam')]
    if existing:
        raise RuntimeError("An interface already exists on part '%s' (set "
            "'%s'). Re-inserting on top of an existing interface corrupts the "
            "mesh -- start from a fresh, interface-free model."
            % (part_for_interface, existing[0]))

    original_node_labels = set([node.label for node in p.nodes])

    # ---- 1) GENERIC interface split (same as the cohesive path) ----------
    fiber_set_name, fiber_labels = _interface_select_fiber_element_labels(p)
    matrix_all_set_name, matrix_all_labels = _interface_select_matrix_all_element_labels(p)
    matrix_set_name, matrix_labels = _interface_select_matrix_element_set(p)
    void_labels = _interface_element_labels_from_set(p, 'Set-void')
    interface_faces, area_stats = _interface_filtered_faces(p, fiber_labels, matrix_labels, matrix_all_labels, void_labels)
    interface_faces = _interface_faces_to_face_array(p, interface_faces)
    if 'Set-Interface-FiberMatrix' in p.sets.keys():
        del p.sets['Set-Interface-FiberMatrix']
    p.Set(faces=interface_faces, name='Set-Interface-FiberMatrix')

    mdb.meshEditOptions.setValues(enableUndo=True, maxUndoCacheElements=0.5)
    region_interface = regionToolset.Region(side1Faces=p.sets['Set-Interface-FiberMatrix'].faces)
    try:
        p.insertElements(faces=region_interface)
    except Exception as error:
        raise RuntimeError("Failed to split the fibre-matrix interface. Make "
            "sure the model is meshed. Abaqus error: {}".format(error))
    p = model.parts[part_for_interface] if part_for_interface in model.parts.keys() else model.parts['UDComposite']
    num_nodes_RVE_thermal = len(p.nodes)
    num_elements_RVE_thermal = len(p.elements)
    inserted_labels = [el.label for el in p.elements[num_elements_RVE:num_elements_RVE_thermal]]
    bottom_labels, top_labels, mid_labels = _interface_split_coincident_seam_nodes(p, original_node_labels)
    fiber_face_keys, matrix_face_keys, void_blocked_faces = _thermal_inserted_side_face_keys(
        p, inserted_labels, top_labels, bottom_labels, void_labels
    )
    if void_blocked_faces:
        print("[Thermal interface] Skipped {} fiber-void mesh interface face(s); only non-void fiber-matrix faces are coupled.".format(
            void_blocked_faces))

    _interface_set_nodes_by_labels(p, 'ThermalSeam-1-FiberSideNodes', top_labels)
    _interface_set_nodes_by_labels(p, 'ThermalSeam-1-MatrixSideNodes', bottom_labels)

    # ---- 2) delete the inserted zero-thickness layer (no COH in a DC model)
    if inserted_labels:
        _interface_delete_elements_by_labels(p, inserted_labels)
        p = model.parts[part_for_interface] if part_for_interface in model.parts.keys() else model.parts['UDComposite']

    # ---- 3) one surface on each free SOLID side (** verify in Abaqus **) --
    _thermal_build_side_surface(p, set(top_labels), 'ThermalSeam-1-FiberSurf', fiber_face_keys)
    _thermal_build_side_surface(p, set(bottom_labels), 'ThermalSeam-1-MatrixSurf', matrix_face_keys)

    # ---- 4) contact-interaction property: gap conductance ----------------
    # The conductance is held CONSTANT (= h) across a clearance band scaled to
    # the model size. The old fixed table ((h,0),(0,1e-6)) drove the
    # conductance to ~0 for any clearance above 1e-6 model-length-units; on a
    # faceted CURVED interface the secondary facets project onto the main
    # facets at small but non-zero clearance (up to the contact search zone),
    # so almost the whole interface became numerically adiabatic and the result
    # was insensitive to h. Widening the band to the model scale keeps h active
    # over all realistic projection clearances.
    import math as _math
    _xs = [n.coordinates[0] for n in p.nodes]
    _ys = [n.coordinates[1] for n in p.nodes]
    _zs = [n.coordinates[2] for n in p.nodes]
    _diag = _math.sqrt((max(_xs) - min(_xs)) ** 2
                       + (max(_ys) - min(_ys)) ** 2
                       + (max(_zs) - min(_zs)) ** 2)
    _c_full = 5.0e-3 * _diag      # conductance stays = h up to this clearance
    _c_zero = 1.0e-2 * _diag      # conductance -> 0 beyond this clearance

    prop_name = 'ThermalSeam-1-GapConductance'
    if prop_name in model.interactionProperties.keys():
        del model.interactionProperties[prop_name]
    cprop = model.ContactProperty(prop_name)
    cprop.ThermalConductance(
        definition=TABULAR, clearanceDependency=ON, pressureDependency=OFF,
        temperatureDependencyC=OFF, massFlowRateDependencyC=OFF,
        dependenciesC=0,
        clearanceDepTable=((gap_conductance, 0.0),
                           (gap_conductance, _c_full),
                           (0.0, _c_zero)))

    # ---- 5) couple the two split sides (assembly level) ------------------
    a = model.rootAssembly
    a.regenerate()
    inst_name = part_for_interface + '-1'
    inst = a.instances[inst_name] if inst_name in a.instances.keys() else list(a.instances.values())[0]
    msurf = inst.surfaces['ThermalSeam-1-MatrixSurf']
    fsurf = inst.surfaces['ThermalSeam-1-FiberSurf']
    if 'ThermalSeam-1-Contact' in model.interactions.keys():
        del model.interactions['ThermalSeam-1-Contact']
    if 'ThermalSeam-1-Tie' in model.constraints.keys():
        del model.constraints['ThermalSeam-1-Tie']

    if THERMAL_SEAM_METHOD == 'tie':
        # PERFECT thermal contact: TIE ties the temperature DOF -> validation
        # baseline (should recover the fully-bonded conductivity).
        _create_paired(
            model.Tie, 'ThermalSeam-1-Tie', msurf, fsurf,
            positionToleranceMethod=COMPUTED, adjust=ON,
            tieRotations=ON)
    else:
        # gap conductance contact pair (uses prop_name created above).
        _create_paired(
            model.SurfaceToSurfaceContactStd, 'ThermalSeam-1-Contact', msurf, fsurf,
            createStepName='Initial', sliding=SMALL, thickness=OFF,
            interactionProperty=prop_name, adjustMethod=NONE,
            initialClearance=OMIT, datumAxis=None, clearanceRegion=None)
        if THERMAL_SEAM_METHOD == 'gap_n2s':
            # node-to-surface discretisation for the coincident curved interface
            _force_node_to_surface(model, prop_name)

    return {
        'fiber_set_name': fiber_set_name,
        'matrix_set_name': matrix_set_name,
        'interface_face_count': len(interface_faces),
        'inserted_node_count': num_nodes_RVE_thermal - num_nodes_RVE,
        'fiber_side_count': len(top_labels),
        'matrix_side_count': len(bottom_labels),
        'void_blocked_interface_face_count': void_blocked_faces,
        'kapitza_resistance': float(kapitza_resistance),
        'gap_conductance': gap_conductance,
    }


def set_material_orientation_and_section_interface(model, interface_material):
    p = model.parts['UDComposite']
    region_interface = p.sets['CohesiveSeam-1-Elements']
    model.CohesiveSection(name='Interface_Section', response=TRACTION_SEPARATION, material=interface_material, outOfPlaneThickness=None)
    # Define material orientation
    p.MaterialOrientation(region=region_interface, orientationType=GLOBAL, axis=AXIS_1, additionalRotationType=ROTATION_NONE, localCsys=None, fieldName='', stackDirection=STACK_3)
    # Assign sections to interface
    p.SectionAssignment(region=p.sets['CohesiveSeam-1-Elements'],sectionName='Interface_Section', offset=0.0, offsetType=MIDDLE_SURFACE, offsetField='', thicknessAssignment=FROM_SECTION)
    # Force plain mechanical cohesive types (no pore-pressure P suffix).
    p.setElementType(
        regions=(p.sets['CohesiveSeam-1-Elements'].elements,),
        elemTypes=(mesh.ElemType(elemCode=COH3D8, elemLibrary=STANDARD),
                   mesh.ElemType(elemCode=COH3D6, elemLibrary=STANDARD)))

# Extraction of material from selected models
def export_materials_to_odb_interface(model_for_interface):
    odb_file = os.path.join(os.getcwd(), 'UsetoCopyMaterial_interface_{}.odb'.format(model_for_interface))
    job_for_interface = 'UsetoCopyMaterial_interface_{}'.format(model_for_interface)
    mdb.Job(name=job_for_interface, model=model_for_interface, type=ANALYSIS)
    mdb.jobs[job_for_interface].submit()
    mdb.jobs[job_for_interface].waitForCompletion()
    del mdb.jobs[job_for_interface]

    return odb_file

def format_interface_debonding_label(debonding_percent):
    value = float(debonding_percent)
    text = ('{:.2f}'.format(abs(value))).rstrip('0').rstrip('.')
    if text == '':
        text = '0'
    if '.' in text:
        integer_part, fractional_part = text.split('.', 1)
        return 'D{}p{}'.format(integer_part.zfill(3), fractional_part)
    return 'D{}'.format(text.zfill(3))

def unique_interface_report_path(work_dir, report_name):
    base_name = '{}.txt'.format(report_name)
    report_path = os.path.join(work_dir, base_name)
    if not os.path.exists(report_path):
        return report_path
    root, ext = os.path.splitext(base_name)
    index = 1
    while True:
        candidate = os.path.join(work_dir, '{}({}){}'.format(root, index, ext))
        if not os.path.exists(candidate):
            return candidate
        index += 1

def unique_cohesive_model_name(model_for_interface, debonding_label='D000', current_name=None):
    base_model_name_with_cohesive = model_for_interface.rsplit('_', 1)[0] + '_cohesive_' + model_for_interface.rsplit('_', 1)[1] + '_' + debonding_label
    model_name_with_cohesive = base_model_name_with_cohesive
    suffix_index = 1
    while model_name_with_cohesive in mdb.models.keys() and model_name_with_cohesive != current_name:
        model_name_with_cohesive = '{}_{}'.format(base_model_name_with_cohesive, suffix_index)
        suffix_index += 1
    return model_name_with_cohesive

def rename_cohesive_model_with_final_debonding(model_for_interface, current_model_name, final_debonding_label):
    final_model_name = unique_cohesive_model_name(model_for_interface, final_debonding_label, current_model_name)
    if final_model_name != current_model_name:
        mdb.models.changeKey(fromName=current_model_name, toName=final_model_name)
    return final_model_name

def copy_model_for_cohesive(model_for_interface, debonding_label='D000'):
    model_name_with_cohesive = unique_cohesive_model_name(model_for_interface, debonding_label)
    mdb.Model(name=model_name_with_cohesive, objectToCopy=mdb.models[model_for_interface])
    model = mdb.models[model_name_with_cohesive]
    part_cohesive = model.parts['UDComposite']

    return model_name_with_cohesive, part_cohesive

###############################################################################
############################ for Analysis #####################################
###############################################################################
def Analysis(model_for_analysis, part_for_analysis, meshsens, CPU,
             E11=False, E22=False, E33=False, G12=False, G13=False, G23=False,
             CTE=False, onlyPBC=False,
             Model_range_analysis=1, user_input_analysis='', analysis_type=1,
             K11=False, K22=False, K33=False, **kwargs):
    """Unified analysis dispatcher.

    Analysis type mapping (matches GUI radio buttons):
        1  Elastic + CTE
        2  Viscoelastic (Time domain)
        3  Viscoelastic (Frequency domain)
        4  Elastoplastic (uniaxial / biaxial)
        5  Thermal Conductivity

    For temperature-bearing analyses (Elastic + Elastic_temperature_points,
    Thermal multi-point, Elastoplastic multi-temperature) the dispatcher loops
    over user-supplied Celsius points and reports per-temperature plus aggregate
    output files. All temperature inputs are validated against absolute zero
    (-273.15 C). Invalid input pops a warning dialog and aborts cleanly.

    Defensive helpers (validate_celsius_*, ensure_output_path_is_safe,
    run_callable_in_directory) live in the helper block above.
    """
    separator = "-" * 100

    import_viscoelastic_time   = (analysis_type == 2)
    import_viscoelastic_freq   = (analysis_type == 3)
    # analysis_type 4 = Elastoplastic Uniaxial, 6 = Elastoplastic Biaxial.
    import_elastoplastic       = (analysis_type in (4, 6))
    import_thermal_conductivity = (analysis_type == 5) or bool(K11) or bool(K22) or bool(K33)

    # --- Validate temperature inputs up front --------------------------------
    try:
        intemp = validate_celsius_temperature_value(kwargs.get('intemp', 0.0), 'Initial temperature')
        fntemp = validate_celsius_temperature_value(kwargs.get('fntemp', 100.0), 'Final temperature')
        segment = max(int(kwargs.get('segment', 1) or 1), 1)
        elastic_temperature_points = validate_celsius_temperature_points(
            parse_temperature_points_input(kwargs.get('elastic_temperature_points', '')),
            'Elastic temperature point'
        )
        ep_temperature_points = validate_celsius_temperature_points(
            parse_temperature_points_input(kwargs.get('epTemperaturePoints', '')),
            'Elastoplastic temperature point'
        )
        visco_temperature_points = validate_celsius_temperature_points(
            parse_temperature_points_input(kwargs.get('visco_temperature_points', '')),
            'Viscoelastic temperature point'
        )
    except ValueError as error_message:
        show_analysis_warning('Temperature Input Error', str(error_message))
        return

    epTheta = float(kwargs.get('epTheta', 0.0) or 0.0)
    if import_elastoplastic and (epTheta < -EPSILON or epTheta > (90.0 + EPSILON)):
        show_analysis_warning('Elastoplastic Input Error', 'Off-axis angle must be between 0 and 90 degrees.')
        return

    keep_all_outputs = bool(kwargs.get('keepAbaqusOutputs', False))
    umatName = kwargs.get('umatName', '') or ''

    # --- Resolve target model list -------------------------------------------
    if Model_range_analysis == 1:
        target_model_names = [model_for_analysis]
    else:
        # Resolve the model index for BOTH plain ('<base>_<N>') and interface
        # ('<base>_thermal_<N>_<lbl>' / '<base>_cohesive_<N>_<lbl>') naming, so
        # batch analysis works on interface-bearing models too.
        parsed_index = split_model_index(model_for_analysis)
        if parsed_index is None:
            raise ValueError(
                "Batch analysis requires the selected model name to contain a "
                "numeric model index (e.g. '<base>_3' or "
                "'<base>_thermal_3_D000'). Current model: {}".format(model_for_analysis))
        model_name_prefix, _model_index, model_name_suffix = parsed_index
        if Model_range_analysis == 2:
            import re
            pattern = re.compile('^' + re.escape(model_name_prefix) + r'\d+'
                                 + re.escape(model_name_suffix) + '$')
            target_model_names = [name for name in mdb.models.keys() if pattern.match(name)]
        else:
            target_model_names = parse_user_input(
                kwargs.get('user_input_analysis', user_input_analysis),
                model_name_prefix, model_name_suffix)

    if not target_model_names:
        show_analysis_warning('Analysis Input Error', 'No valid model was found for the requested analysis range.')
        return

    # --- Import the relevant analyzer module ---------------------------------
    feasypbc = None
    if import_viscoelastic_time:
        feasypbc = importlib.import_module('PBC_UDFRP_Viscoelastic_Time').feasypbc
        print('Run PBC_UDFRP_Viscoelastic_Time')
    elif import_viscoelastic_freq:
        feasypbc = importlib.import_module('PBC_UDFRP_Viscoelastic_Frequency').feasypbc
        print('Run PBC_UDFRP_Viscoelastic_Frequency')
    elif not import_elastoplastic and not import_thermal_conductivity:
        feasypbc = importlib.import_module('PBC_UDFRP_Elastic_CTE').feasypbc
        print('Run PBC_UDFRP_Elastic_CTE')

    base_output_dir = os.getcwd()
    shared_timestamp = build_analysis_timestamp()
    instance_for_analysis = part_for_analysis + '-1'

    def _interface_coord_key(coordinates, tolerance):
        scale = float(tolerance) if tolerance and tolerance > 0.0 else 1.0e-9
        return tuple([int(round(float(value) / scale)) for value in coordinates])

    def model_needs_interface_pbc(model_name):
        try:
            instance = mdb.models[model_name].rootAssembly.instances[instance_for_analysis]
            seen = set()
            for node in instance.nodes:
                key = _interface_coord_key(node.coordinates, meshsens)
                if key in seen:
                    return True
                seen.add(key)
            return False
        except Exception as exc:
            print('[Interface] Duplicate-coordinate scan failed for {}: {}'.format(model_name, exc))
            return False

    def create_elastoplastic_work_model(source_model_name):
        index = 1
        while True:
            work_model_name = 'EPWork_{}'.format(index)
            if work_model_name not in mdb.models.keys():
                break
            index += 1
            if index > 9999:
                raise RuntimeError('Cannot create a unique temporary elastoplastic work model name.')
        mdb.Model(name=work_model_name, objectToCopy=mdb.models[source_model_name])
        return work_model_name

    # ----- helper: output directory ------------------------------------------
    def prepare_output_directory(model_name, analysis_name, case_label, temperature_value, sample_file_name):
        if keep_all_outputs:
            subdir_name = build_case_output_subdirectory(model_name, analysis_name, case_label, temperature_value, shared_timestamp)
            ensure_output_path_is_safe(base_output_dir, subdir_name, sample_file_name)
            return os.path.join(base_output_dir, subdir_name)
        ensure_output_path_is_safe(base_output_dir, '', sample_file_name)
        return None

    # Cache keyed by (model_name, case_label). Within a single Analysis() click,
    # all temperature points of the same load case share the same load sub-
    # folder (so they can sit side-by-side as per-temperature sub-folders).
    # Across runs, the load sub-folder gets a "(1)", "(2)", ... suffix when
    # the un-suffixed name already exists on disk, so previous results are
    # never silently overwritten.
    elastoplastic_load_folder_cache = {}

    def _pick_unique_folder_name(parent_dir, base_name):
        """Return the first non-existing name in base_name, base_name(1), ..."""
        candidate = os.path.join(parent_dir, base_name)
        if not os.path.exists(candidate):
            return base_name
        index = 1
        while True:
            suffixed = '{}({})'.format(base_name, index)
            candidate = os.path.join(parent_dir, suffixed)
            if not os.path.exists(candidate):
                return suffixed
            index += 1
            # Safety valve so a misconfigured filesystem cannot loop forever.
            if index > 9999:
                raise RuntimeError(
                    'Cannot find a unique folder name under {} after 9999 attempts.'.format(parent_dir))

    def prepare_elastoplastic_output_directory(model_name, case_label, temperature_value, sample_file_name):
        cache_key = (model_name, case_label)
        if cache_key in elastoplastic_load_folder_cache:
            load_subdirectory_name = elastoplastic_load_folder_cache[cache_key]
        else:
            base_load_name = 'Elastoplastic_{}'.format(sanitize_case_label(case_label))
            # Bump (1), (2), ... if the un-suffixed folder already exists.
            load_subdirectory_name = _pick_unique_folder_name(base_output_dir, base_load_name)
            elastoplastic_load_folder_cache[cache_key] = load_subdirectory_name
            # Create eagerly so subsequent temperature cases land in the SAME
            # uniquified folder (not in a fresh "(N+1)" sibling).
            try:
                os.makedirs(os.path.join(base_output_dir, load_subdirectory_name))
            except Exception:
                pass

        ensure_output_path_is_safe(base_output_dir, load_subdirectory_name, sample_file_name)
        load_output_dir = os.path.join(base_output_dir, load_subdirectory_name)
        if keep_all_outputs:
            # Per-temperature sub-folder, NO timestamp -- keeps the job name and
            # CSV filenames clean so Abaqus's Jobs view can open the ODB directly.
            temperature_tag = format_temperature_file_label(temperature_value) if temperature_value is not None else 'Temp_None'
            run_subdirectory_name = sanitize_case_label(temperature_tag)
            ensure_output_path_is_safe(load_output_dir, run_subdirectory_name, sample_file_name)
            return os.path.join(load_output_dir, run_subdirectory_name)
        return load_output_dir

    def rename_cte_csv_if_present(result_directory, model_name):
        legacy_csv_name = os.path.join(result_directory, '{}_CTE_results.csv'.format(model_name))
        if not os.path.exists(legacy_csv_name):
            return
        range_label = format_temperature_range_file_label(intemp, fntemp)
        renamed_csv_name = os.path.join(
            result_directory,
            '{}_CTE_results_{}_{}.csv'.format(model_name, range_label, shared_timestamp)
        )
        if os.path.exists(renamed_csv_name):
            os.remove(renamed_csv_name)
        os.rename(legacy_csv_name, renamed_csv_name)

    # ----- per-model dispatch --------------------------------------------------
    def run_elastoplastic_case_for_model(model_name):
        if model_needs_interface_pbc(model_name):
            multiaxial = importlib.import_module('PBC_UDFRP_Elastoplastic_interface')
            print('Run PBC_UDFRP_Elastoplastic_interface')
        else:
            multiaxial = importlib.import_module('PBC_UDFRP_Elastoplastic')
            print('Run PBC_UDFRP_Elastoplastic')
        feasypbc_ep = multiaxial.rve_multiaxial_analysis_complete

        # Loading mode now comes directly from the Analysis-type radio:
        #   analysis_type == 4 -> uniaxial cases (one per checked component)
        #   analysis_type == 6 -> biaxial cases (one per selected pair)
        if analysis_type == 6:
            elastoplastic_cases = build_elastoplastic_biaxial_case(kwargs)
        else:
            elastoplastic_cases = build_elastoplastic_single_axis_cases(kwargs)
        if not elastoplastic_cases:
            raise ValueError('Please select at least one valid elastoplastic load case.')

        # Forwarded straight to the kernel: when True, the StaticStep is created
        # with matrixStorage=UNSYMMETRIC for UMATs with an asymmetric tangent.
        unsymmetric_solver = bool(kwargs.get('epUnsymmetricSolver', False))
        large_deformation = bool(kwargs.get('epLargeDeformation', True))
        # Field-output sampling: N evenly-spaced frames (0 => every increment).
        try:
            field_output_intervals = int(kwargs.get('field_output_intervals', 80))
        except (TypeError, ValueError):
            field_output_intervals = 80
        # *Static adaptive energy-stabilization magnitude (DEF); forwarded to
        # the kernel StaticStep.  GUI default 2e-4; raise to damp softening.
        try:
            stabilization_magnitude = float(kwargs.get('stabilization_magnitude', 2e-4))
        except (TypeError, ValueError):
            stabilization_magnitude = 2e-4
        if not (stabilization_magnitude > 0.0):
            stabilization_magnitude = 2e-4
        # Step type: GUI combo passes friendly text; map to the kernel token.
        # Anything mentioning "dynamic" -> *Dynamic QUASI-STATIC, else *Static.
        _proc_text = str(kwargs.get('epAnalysisProcedure', '') or '')
        analysis_procedure = ('QUASI_STATIC_DYNAMIC'
                              if 'dynamic' in _proc_text.lower() else 'STATIC')

        temperature_cases = list(ep_temperature_points)
        if not temperature_cases:
            temperature_cases = [None]

        for case_data in elastoplastic_cases:
            for temperature_value in temperature_cases:
                # sample_name is only used by ensure_output_path_is_safe() for
                # the Windows path-length check; the actual CSV files written
                # by the PBC_UDFRP_Elastoplastic kernel no longer carry a
                # timestamp suffix either.
                sample_name = '{}_analysis_summary_{}_{}.csv'.format(
                    model_name,
                    sanitize_case_label(case_data['case_label']),
                    format_temperature_file_label(temperature_value) if temperature_value is not None else 'Temp_None',
                )
                work_directory = prepare_elastoplastic_output_directory(
                    model_name, case_data['case_label'], temperature_value, sample_name
                )
                analysis_kwargs = {
                    'part': None,
                    'inst': part_for_analysis,
                    'meshsens': meshsens,
                    'theta_deg': epTheta,
                    'epsilon_x': case_data['epsilon_x'],
                    'epsilon_y': case_data['epsilon_y'],
                    'epsilon_z': case_data['epsilon_z'],
                    'gamma_xy':  case_data['gamma_xy'],
                    'gamma_yz':  case_data['gamma_yz'],
                    'gamma_zx':  case_data['gamma_zx'],
                    'CPU': CPU,
                    'umat_file': umatName,
                    'output_dir': work_directory or base_output_dir,
                    'save_volume_avg': True,
                    'temperature_celsius': temperature_value,
                    'loading_label': case_data['case_label'],
                    'legacy_loading_type': case_data['legacy_loading_type'],
                    'unsymmetric_solver': unsymmetric_solver,
                    'large_deformation': large_deformation,
                    'result_model_name': model_name,
                    'field_output_intervals': field_output_intervals,
                    'stabilization_magnitude': stabilization_magnitude,
                    'analysis_procedure': analysis_procedure,
                }
                work_model_name = create_elastoplastic_work_model(model_name)
                analysis_kwargs['part'] = work_model_name
                print('Using temporary elastoplastic work model: {} (source: {})'.format(work_model_name, model_name))
                try:
                    run_callable_in_directory(work_directory, feasypbc_ep, **analysis_kwargs)
                finally:
                    try:
                        if work_model_name in mdb.models.keys():
                            del mdb.models[work_model_name]
                    except Exception as cleanup_error:
                        print('Warning: failed to delete temporary elastoplastic work model {}: {}'.format(
                            work_model_name, cleanup_error))

    def run_viscoelastic_time_for_model(model_name):
        relaxationTime = kwargs.get('relaxationTime')
        time_point = kwargs.get('time_point')
        temperature_cases = list(visco_temperature_points)
        if not temperature_cases:
            temperature_cases = [validate_celsius_temperature_value(kwargs.get('temperature', 25.0), 'Viscoelastic temperature')]
        for temperature in temperature_cases:
            work_directory = prepare_output_directory(
                model_name, 'ViscoelasticTime', 'ViscoelasticTime', temperature, 'job-E11.odb'
            )
            run_callable_in_directory(
                work_directory, feasypbc,
                model_name, instance_for_analysis, meshsens,
                E11, E22, E33, G12, G13, G23,
                CPU, relaxationTime, time_point, umatName, temperature
            )

    def run_viscoelastic_freq_for_model(model_name):
        lowerFreq = kwargs.get('lowerFreq')
        upperFreq = kwargs.get('upperFreq')
        numPoints = kwargs.get('numPoints')
        bias = kwargs.get('bias')
        temperature_cases = list(visco_temperature_points)
        if not temperature_cases:
            temperature_cases = [validate_celsius_temperature_value(kwargs.get('temperature', 25.0), 'Viscoelastic temperature')]
        for temperature in temperature_cases:
            work_directory = prepare_output_directory(
                model_name, 'ViscoelasticFrequency', 'ViscoelasticFrequency', temperature, 'job-E11.odb'
            )
            run_callable_in_directory(
                work_directory, feasypbc,
                model_name, instance_for_analysis, meshsens,
                E11, E22, E33, G12, G13, G23, CPU,
                lowerFreq, upperFreq, numPoints, bias, umatName, temperature
            )

    def run_thermal_for_model(model_name):
        if model_needs_interface_pbc(model_name):
            thermal_feasypbc = importlib.import_module('PBC_UDFRP_thermal_conductivity_Interfaceh').feasypbc
            print('Run PBC_UDFRP_thermal_conductivity_Interfaceh')
        else:
            thermal_feasypbc = importlib.import_module('PBC_UDFRP_thermal_conductivity').feasypbc
            print('Run PBC_UDFRP_thermal_conductivity')

        if onlyPBC:
            single_temperature = intemp
            work_directory = prepare_output_directory(model_name, 'ThermalConductivity', 'PBCOnly', single_temperature, 'job-K11.odb')
            run_callable_in_directory(
                work_directory, thermal_feasypbc,
                model_name, instance_for_analysis, meshsens,
                K11, K22, K33, CPU, onlyPBC, single_temperature, single_temperature
            )
            return
        # Build the linspace of segment+1 points for the legacy ramp
        if abs(fntemp - intemp) <= EPSILON:
            tps = [intemp]
        else:
            tps = list(np.linspace(intemp, fntemp, segment + 1))
        run_thermal_temperature_sweep(
            model_name, instance_for_analysis, meshsens, CPU,
            K11, K22, K33, onlyPBC, tps,
            thermal_feasypbc, shared_timestamp,
            output_root_dir=base_output_dir,
            keep_all_outputs=keep_all_outputs,
            case_label='ThermalConductivity'
        )

    def run_elastic_for_model(model_name):
        if elastic_temperature_points and not onlyPBC:
            run_elastic_temperature_sweep(
                model_name, instance_for_analysis, meshsens, CPU,
                E11, E22, E33, G12, G13, G23, onlyPBC,
                elastic_temperature_points, umatName, feasypbc,
                shared_timestamp, output_root_dir=base_output_dir,
                keep_all_outputs=keep_all_outputs, case_label='Elastic'
            )

        if CTE:
            work_directory = prepare_output_directory(
                model_name, 'ElasticCTE', 'CTE', None,
                '{}_CTE_results_{}_{}.csv'.format(
                    model_name, format_temperature_range_file_label(intemp, fntemp), shared_timestamp
                )
            )
            run_callable_in_directory(
                work_directory, feasypbc,
                model_name, instance_for_analysis, meshsens,
                E11, E22, E33, G12, G13, G23, CTE, CPU, onlyPBC,
                intemp, fntemp, segment, umatName
            )
            rename_cte_csv_if_present(work_directory or os.getcwd(), model_name)
        elif not elastic_temperature_points:
            single_temperature = 0.0
            work_directory = prepare_output_directory(model_name, 'Elastic', 'Elastic', single_temperature, 'job-E11.odb')
            run_callable_in_directory(
                work_directory, feasypbc,
                model_name, instance_for_analysis, meshsens,
                E11, E22, E33, G12, G13, G23, False, CPU, onlyPBC,
                single_temperature, single_temperature, 1, umatName
            )

    # --- Main loop -----------------------------------------------------------
    try:
        for model_name in target_model_names:
            model = mdb.models[model_name]
            model.rootAssembly.regenerate()

            start_time = time.time()
            if import_elastoplastic:
                run_elastoplastic_case_for_model(model_name)
            elif import_viscoelastic_time:
                run_viscoelastic_time_for_model(model_name)
            elif import_viscoelastic_freq:
                run_viscoelastic_freq_for_model(model_name)
            elif import_thermal_conductivity:
                run_thermal_for_model(model_name)
            else:
                run_elastic_for_model(model_name)
            print('Programme runtime for {}: {:.3f} seconds'.format(model_name, time.time() - start_time))
    except ValueError as error_message:
        show_analysis_warning('Analysis Input Error', str(error_message))
        return

    print(' ')
    print(separator)
    print('--------------------------------------- Analysis Information ---------------------------------------')
    print(separator)
    print('Successfully completed analysis for {} model(s):'.format(len(target_model_names)))
    for model_name in target_model_names:
        print('==> {}'.format(model_name))
    print(separator)
    print(separator)

def import_easypbc(model_for_analysis, part_for_analysis, import_viscoelastic, import_viscoelastic_freq, import_thermal_conductivity):
    model = mdb.models[model_for_analysis]
    part = model.parts[part_for_analysis]
    
    import_cohesive = False
    cohesive_count = 0
    
    for element in part.elements:
        if str(element.type).startswith('COH3'):
            node1 = part.nodes[element.connectivity[0]]
            node4 = part.nodes[element.connectivity[3]]
            if abs(node1.coordinates[2] - node4.coordinates[2]) < 1e-6:
                import_cohesive = True
                break
    
    if import_cohesive and import_viscoelastic:
        raise ValueError("Cannot compute viscoelastic properties for models with cohesive zones.")
    if import_cohesive and import_viscoelastic_freq:
        raise ValueError("Cannot compute viscoelastic properties for models with cohesive zones.")
    
    if import_viscoelastic:
        # Time-domain viscoelastic relaxation
        feasypbc = importlib.import_module('PBC_UDFRP_Viscoelastic_Time').feasypbc
        print("Run PBC_UDFRP_Viscoelastic_Time")
    elif import_viscoelastic_freq:
        # Frequency-domain viscoelastic (storage/loss modulus)
        feasypbc = importlib.import_module('PBC_UDFRP_Viscoelastic_Frequency').feasypbc
        print("Run PBC_UDFRP_Viscoelastic_Frequency")
    elif import_thermal_conductivity:
        # Steady-state thermal conductivity tensor
        feasypbc = importlib.import_module('PBC_UDFRP_thermal_conductivity').feasypbc
        print("Run PBC_UDFRP_thermal_conductivity")
    else:
        # Default: linear elastic (and CTE if enabled)
        feasypbc = importlib.import_module('PBC_UDFRP_Elastic_CTE').feasypbc
        print("Run PBC_UDFRP_Elastic_CTE")

    return feasypbc
