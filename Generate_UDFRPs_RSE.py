# -*- coding: utf-8 -*-
###############################################################################
# Generate_UDFRPs_RSE.py
# -----------------------------------------------------------------------------
# Generates 2D fiber-center coordinates for a UDFRP RVE using the
# Random Sequential Expansion (RSE) algorithm. Imported by
# RVE_Builder_UDFRPs.CreateRVE when algorithm == 2.
#
# -----------------------------------------------------------------------------
# Part of the "RVE Builder (UDFRPs)" Abaqus/CAE plug-in.
# Copyright (C) 2026 Yuhao Meng
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.  You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# The PBC homogenization kernels shipped with this plug-in are derived from
# EasyPBC, Copyright (C) 2018 Sadik Lafta Omairey, distributed under the GNU
# GPL; see the individual PBC_UDFRP_*.py files.
# -----------------------------------------------------------------------------
###############################################################################
"""
Generates 2D fibre-centre coordinates for a randomly distributed unidirectional
continuous-fibre RVE with the Random Sequential Expansion (RSE) algorithm.

* "volume fraction first" or "RVE size first" control (control_options)
* lmin / lmax: seeding distance range from an existing fibre
* MIN_GAP: optional minimum surface-to-surface gap between any two fibres
* BOUNDARY_CLEARANCE: keeps fibres away from RVE corners and thin edge slivers
* writes the coordinates (with periodic images) to CSV together with
  first/second nearest-neighbour distances, Ripley's K and the pair
  distribution function

Author: Yuhao Meng (yuhaomeng@oceanica.ufrj.br)

References
    Lei Yang, Ying Yan, Zhiguo Ran, Yujia Liu, A new method for generating
    random fiber distributions for fiber reinforced composites, Composites
    Science and Technology 76 (2013) 14-20,
    https://doi.org/10.1016/j.compscitech.2012.12.001
    https://github.com/qinguoming/MyPluginDevlopReposity/tree/master/500-RandomFiberRVEScript
"""

import math, os
import random
import csv
import time
import numpy as np

# Boundary clearance, as a fraction of the fibre radius.  A candidate fibre is
# rejected when a corner of the RVE lies inside or within this clearance of
# the fibre, or when the fibre crosses an RVE edge (or stops short of it) by
# less than this clearance.  This avoids fibres that cover an RVE corner (the
# geometry kernel cannot split such a fibre into four periodic parts) and the
# thin slivers that make meshing fail.  Set it to 0.0 to disable the check.
BOUNDARY_CLEARANCE = 0.1

# Minimum surface-to-surface gap between ANY two fibres (model units, same as
# the fibre diameter).  lmin / lmax only control the seeding distance from the
# parent fibre; other neighbours may come arbitrarily close, which is what makes
# meshing fail when fibres nearly touch.  A value of about 0.03-0.05 df removes
# such near-contacts.  It lowers the achievable Vf and, in Keep-Vf mode, raises
# the number of re-rolled draws, so it is off by default.
MIN_GAP = 0.0


def RSE_algorithm(Basefolder, vf, df, a, b, file_suffix_range_Set, lmax, lmin, control_options):
    start_time_RSE_Method = time.time()
    circle_data = []
    # Basic geometric parameter of RVE
    radius = df / 2.0
    area_fiber_single = math.pi * (radius**2.0)
    area_RVE = a * b
    N = int((vf * 0.01 * area_RVE) / area_fiber_single)
    
    if control_options == 1:
        control_options_name = "vf"
        area_fiber_total = N * area_fiber_single
        area_RVE_new = area_fiber_total / (vf * 0.01)
        scale_factor = math.sqrt(area_RVE_new / area_RVE)
        a *= scale_factor
        b *= scale_factor
        area_RVE = a * b
    elif control_options == 2:
        control_options_name = "RVE width and height"
        area_fiber_total = N * area_fiber_single
        vf = (area_fiber_total / area_RVE) * 100
    
    if N < 1:
        raise ValueError("Error: Insertion of fibers less than 1, please adjust RVE size")
    
    vf0 = (math.pi * (radius**2.0)) / (a * b)
    vf0 = 100 * vf0
    success_count = 0
    
    # Lists to store statistical analysis results for all generated configurations
    all_nn1_distances = []
    all_nn2_distances = []
    all_nn1_prob_density_results = []  # Store probability density for each configuration
    all_nn2_prob_density_results = []  # Store probability density for each configuration
    all_ripley_k_results = []
    all_pdf_results = []
    
    # Save coordinates to CSV
    success_count = 0
    all_statistics = []  # store statistics for every configuration
    
    # Create folder
    folder_path = create_folder(Basefolder, vf, file_suffix_range_Set, N)
    
    # Save coordinates to CSV
    # A config that jams short of the target (Keep-Vf mode only) is re-rolled up
    # to MAX_CONFIG_RETRIES times before giving up, so one unlucky draw does not
    # discard the configs already generated. Raise it if you still hit the limit.
    target_frac = vf / 100.0
    tol = max(1.0e-9, target_frac * 1.0e-6)
    MAX_CONFIG_RETRIES = 20
    config_retries = 0
    best_vf_cfg = -1.0
    best_n_cfg = 0
    config_records = []          # one entry per saved configuration (for the check table)
    config_start_time = time.time()
    while success_count < file_suffix_range_Set:
        fibers, current_vf, success = use_RSE_CreateRVE(vf0, vf, a, b, radius, lmax, lmin)
        if success:
            # ---- (Keep-Vf mode only) require the target Vf; re-roll if short --
            # Only control_options == 1 ("keep Vf") pre-sizes the cell for exactly
            # N fibres, so it must place all N. If a draw jams short, re-roll this
            # config (up to MAX_CONFIG_RETRIES) instead of aborting the whole run,
            # so the configs already finished are kept. control_options == 2
            # ("keep RVE size") accepts whatever packs and reports the actual Vf.
            if control_options == 1 and current_vf < target_frac - tol:
                if current_vf > best_vf_cfg:
                    best_vf_cfg = current_vf
                    best_n_cfg = len(fibers)
                config_retries += 1
                if config_retries <= MAX_CONFIG_RETRIES:
                    continue        # re-roll silently; the count goes into the check table
                # retries exhausted for this config -> stop the whole run
                print(' ')
                print('====================================================================')
                print(' RSE could NOT reach the target fibre volume fraction - STOPPING.')
                print('   Target Vf        : {:.4f}%   (needs N = {} fibres)'.format(target_frac * 100.0, N))
                print('   Best of {:d} tries : {:.4f}%   (placed {} fibres)'.format(MAX_CONFIG_RETRIES + 1, best_vf_cfg * 100.0, best_n_cfg))
                print('   Shortfall        : {:.4f}%   ({} fibre(s) short)'.format((target_frac - best_vf_cfg) * 100.0, N - best_n_cfg))
                print(' Configs already finished (if any) are saved in the output folder.')
                print(' Fix: lower BOTH lmin and lmax so new fibres are seeded closer to')
                print('      existing ones (this raises the achievable packing density).')
                print('      Current lmin = {}, lmax = {}. Try roughly halving them'.format(lmin, lmax))
                print('      (e.g. lmin -> {:.4g}, lmax -> {:.4g}) and/or lower the target Vf,'.format(lmin / 2.0, lmax / 2.0))
                print('      then run again.')
                print('====================================================================')
                print(' ')
                raise ValueError(
                    'RSE could not reach target {:.2f}% after {} tries (best {:.2f}%). '
                    'Lower lmin/lmax to seed fibres closer, or reduce the target Vf, '
                    'then re-run.'.format(target_frac * 100.0, MAX_CONFIG_RETRIES + 1, best_vf_cfg * 100.0))
            # target met: record the outcome, reset the retry state, then save
            config_records.append({
                'config': success_count + 1,
                'fibers': len(fibers),
                'vf': current_vf * 100.0,
                'rerolls': config_retries,
                'time': time.time() - config_start_time,
            })
            config_start_time = time.time()
            config_retries = 0
            best_vf_cfg = -1.0
            best_n_cfg = 0
            # existing save logic (saves the full coordinates including mirror images)
            valid_fibers = []
            unique_coords = set()
            rect = (0, a, 0, b)
            for fiber in fibers:
                x, y, radius_fiber, flag = fiber
                coord = (x, y)                
                if circle_rectangle_intersect(x, y, radius_fiber, rect):
                    if coord not in unique_coords:
                        valid_fibers.append(fiber)
                        unique_coords.add(coord)
                if flag != 'in':
                    expanded_centers = CalExpendCenter(fiber, a, b)
                    for ex_center in expanded_centers:
                        ex_x, ex_y = ex_center
                        expanded_coord = (ex_x, ex_y)                        
                        if circle_rectangle_intersect(ex_x, ex_y, radius_fiber, rect):
                            if expanded_coord not in unique_coords:
                                expanded_fiber = [ex_x, ex_y, radius_fiber, flag]
                                valid_fibers.append(expanded_fiber)
                                unique_coords.add(expanded_coord)  

            circle_data.append(valid_fibers)
            save_fiber_coordinates_to_csv(folder_path, fibers, N, success_count, a, b)
            
            # use the original fiberList (without mirror images) for statistical analysis
            stats = perform_statistics_analysis_rse(
                fibers,           # original fiber list
                a, b,            # RVE dimensions
                radius,          # fiber radius
                folder_path,     # output folder
                success_count + 1  # configuration number (1-based)
            )
            all_statistics.append(stats)
            
            success_count += 1
            print("==> Successfully generated {}/{} CSV files.\n".format(success_count, file_suffix_range_Set))
    
    # save the statistics summary
    save_nn_summary_rse(all_statistics, folder_path)
    
    end_time_RSE_Method = time.time()
    elapsed_time_RSE_Method = end_time_RSE_Method - start_time_RSE_Method
    average_time_per_set_of_coordinates_created = elapsed_time_RSE_Method / file_suffix_range_Set
    
    # Report the volume fraction that was ACTUALLY achieved, not the requested
    # target. (Every generated config passed the target check above, so this is
    # within one fibre of the target; it is never silently the raw target.)
    reported_vf = current_vf

    # Save information in .txt file
    Output_Information(N, reported_vf, df, a, b, lmin, lmax, file_suffix_range_Set, 
                      average_time_per_set_of_coordinates_created, elapsed_time_RSE_Method, 
                      folder_path, control_options_name,
                      target_vf=vf, config_records=config_records)
    
    # Info output
    print(' ')
    print('--------------------------------------------------------------------')
    print('------------------------------ Info show ---------------------------')
    print('--------------------------------------------------------------------')
    print('Fixed parameter: {}\n'.format(control_options_name))
    print(' Volume Fraction of Fiber (achieved)              {:.4f}%'.format(reported_vf * 100))
    print(' Diameter of fiber                                {}'.format(df))
    print(' Number of fibers                                 {}'.format(N))
    print(' RVE width                                        {}'.format(a))
    print(' RVE height                                       {}'.format(b))
    print(' l_min for RSE                                    {}'.format(lmin))
    print(' l_max for RSE                                    {}'.format(lmax))
    print('--------------------------------------------------------------------')
    print(" Average time per set of coordinates created:     {:.2f} seconds.".format(average_time_per_set_of_coordinates_created))
    print(" Total time {:02d} set(s) of coordinates created:     {:.2f} seconds.".format(file_suffix_range_Set, elapsed_time_RSE_Method))
    print('--------------------------------------------------------------------')
    print(' Statistical analysis results have been saved:')
    print('   - Nearest neighbor distances with probability densities')
    print("   - Ripley's K function with normalized distances")
    print('   - Pair distribution function with normalized distances')
    print(' The folder containing all results has been saved at: ')
    print("    ==> {}".format(folder_path))
    print('--------------------------------------------------------------------')
    print('--------------------------------------------------------------------')
    print(' ')
    
    return circle_data

# New statistical analysis functions
def calculate_periodic_distance_rse(fiber1, fiber2, a, b):
    """
    Compute the periodic distance between two fiber centers
    
    Args:
        fiber1, fiber2: fiber data [x, y, radius, flag]
        a, b: RVE dimensions
    
    Returns:
        shortest periodic distance
    """
    x1, y1 = fiber1[0], fiber1[1]
    x2, y2 = fiber2[0], fiber2[1]
    
    dx = abs(x1 - x2)
    dy = abs(y1 - y2)
    
    # periodic boundary: take the shortest path
    dx = min(dx, a - dx)
    dy = min(dy, b - dy)
    
    return math.sqrt(dx**2 + dy**2)

def calculate_nearest_neighbors_rse(fiberList, a, b):
    """
    Compute the 1st and 2nd nearest-neighbor distances for each fiber
    Uses the original fiberList and periodic-distance calculation to handle boundaries
    
    Args:
        fiberList: original fiber list (without mirror images)
        a, b: RVE dimensions
    
    Returns:
        nn1_distances: list of 1st nearest-neighbor distances
        nn2_distances: list of 2nd nearest-neighbor distances
    """
    n = len(fiberList)
    nn1_distances = []
    nn2_distances = []
    
    for i in range(n):
        distances = []
        for j in range(n):
            if i != j:
                dist = calculate_periodic_distance_rse(fiberList[i], fiberList[j], a, b)
                distances.append(dist)
        
        # sort and take the first two
        distances.sort()
        nn1_distances.append(distances[0])
        nn2_distances.append(distances[1])
    
    return nn1_distances, nn2_distances

def calculate_probability_density_rse(distances, radius, num_bins=50):
    """
    Compute the probability-density distribution of nearest-neighbor distances
    """
    distances_array = np.array(distances)
    normalized = distances_array / radius
    
    # compute histogram
    counts, bin_edges = np.histogram(normalized, bins=num_bins, density=False)
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
    bin_width = bin_edges[1] - bin_edges[0]
    
    # normalize to probability density
    prob_density = counts / (len(distances) * bin_width)
    
    return bin_centers.tolist(), prob_density.tolist()

def calculate_ripleys_k_rse(fiberList, a, b, radius, max_r_multiplier=15, num_points=100):
    """
    Compute Ripley's K function
    """
    n = len(fiberList)
    area = a * b
    intensity = n / area
    
    # compute distances between all fiber pairs
    all_distances = []
    for i in range(n):
        for j in range(i+1, n):
            dist = calculate_periodic_distance_rse(fiberList[i], fiberList[j], a, b)
            all_distances.append(dist)
    
    # range of r values
    r_values = np.linspace(0, max_r_multiplier * radius, num_points)
    K_values = []
    
    for r in r_values:
        if r == 0:
            K_values.append(0)
            continue
        
        # count point pairs within radius r
        count = len([d for d in all_distances if d < r])
        # multiply by 2 because only the upper triangle was computed
        count = count * 2
        
        # Ripley's K estimate
        K = count / (n * intensity)
        K_values.append(K)
    
    # theoretical K(r) for a random distribution = pi * r^2
    K_random = (math.pi * r_values**2).tolist()
    
    # normalize
    r_normalized = (r_values / radius).tolist()
    
    return r_normalized, K_values, K_random







def save_statistics_csv_rse(folder_path, nn1_data, nn2_data, ripley_data, pdf_data, config_num):
    """
    Save statistical-analysis results to a CSV file
    
    Args:
        folder_path: output folder
        nn1_data: (normalized_dist, prob_density) tuple
        nn2_data: (normalized_dist, prob_density) tuple
        ripley_data: (r_normalized, K_values, K_random) tuple
        pdf_data: (r_normalized, g_values) tuple
        config_num: configuration number (1-based)
    """
    # NN1 probability density
    nn1_file = os.path.join(folder_path, f"nn1_probability_density_config_{config_num:02d}.csv")
    with open(nn1_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Distance_divided_by_fiber_radius', 'Probability_Density'])
        for dist, dens in zip(nn1_data[0], nn1_data[1]):
            writer.writerow([dist, dens])
    
    # NN2 probability density
    nn2_file = os.path.join(folder_path, f"nn2_probability_density_config_{config_num:02d}.csv")
    with open(nn2_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Distance_divided_by_fiber_radius', 'Probability_Density'])
        for dist, dens in zip(nn2_data[0], nn2_data[1]):
            writer.writerow([dist, dens])
    
    # Ripley's K
    ripley_file = os.path.join(folder_path, f"ripleys_k_config_{config_num:02d}.csv")
    with open(ripley_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['r_divided_by_fiber_radius', 'K(r)', 'K_random(r)'])
        for r, k, k_rand in zip(ripley_data[0], ripley_data[1], ripley_data[2]):
            writer.writerow([r, k, k_rand])
    
    # radial distribution function
    pdf_file = os.path.join(folder_path, f"pair_distribution_function_config_{config_num:02d}.csv")
    with open(pdf_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['r_divided_by_fiber_radius', 'g(r)'])
        for r, g in zip(pdf_data[0], pdf_data[1]):
            writer.writerow([r, g])

def calculate_pair_distribution_function_rse(fiberList, a, b, radius, max_r_multiplier=15, num_bins=100):
    """
    Compute the radial distribution function g(r)
    
    g(r) measures local density fluctuations relative to complete spatial randomness (CSR)
    for CSR, g(r) ~ 1 (for large enough r)
    g(r) > 1 indicates clustering, g(r) < 1 indicates repulsion
    
    Args:
        fiberList: original fiber list
        a, b: RVE dimensions
        radius: fiber radius
        max_r_multiplier: maximum radius (in units of fiber radius)
        num_bins: number of bins
    
    Returns:
        r_normalized: normalized-radius array
        g_values: array of g(r) values
    """
    n = len(fiberList)
    area = a * b
    intensity = n / area  # number density (fibers/area)
    
    # compute distances between all fiber pairs (upper triangle, n*(n-1)/2 pairs total)
    all_distances = []
    for i in range(n):
        for j in range(i+1, n):
            dist = calculate_periodic_distance_rse(fiberList[i], fiberList[j], a, b)
            all_distances.append(dist)
    
    all_distances = np.array(all_distances)
    
    # bin setup
    max_r = max_r_multiplier * radius
    r_bins = np.linspace(0, max_r, num_bins + 1)
    r_centers = (r_bins[:-1] + r_bins[1:]) / 2
    dr = r_bins[1] - r_bins[0]
    
    # compute distance histogram
    counts, _ = np.histogram(all_distances, bins=r_bins)
    
    # compute g(r)
    g_values = []
    for i in range(num_bins):
        r = r_centers[i]
        if r < radius * 0.1:  # g(r) = 0 as r -> 0 (hard-core repulsion)
            g_values.append(0)
        else:
            # ring area: pi*[(r+dr/2)^2 - (r-dr/2)^2] ~ 2*pi*r*dr
            ring_area = math.pi * ((r + dr/2)**2 - (r - dr/2)**2)
            
            # for CSR, expected number of point pairs in the ring:
            # expected_pairs = [total pairs] * [ring area / total area]
            #                = [n*(n-1)/2] * [ring_area / area]
            #                = (n-1)/2 * ring_area * intensity
            # note: NOT n*(n-1)/2, because intensity already includes n
            expected_count = (n - 1) / 2 * ring_area * intensity
            
            # g(r) = actual pairs / expected pairs
            if expected_count > 0:
                g = counts[i] / expected_count
                g_values.append(g)
            else:
                g_values.append(0)
    
    # normalized radius
    r_normalized = (r_centers / radius).tolist()
    
    return r_normalized, g_values



def perform_statistics_analysis_rse(fiberList, a, b, radius, folder_path, config_num):
    """
    Run the full statistical analysis (called during generation)
    
    Args:
        fiberList: original fiber list (without mirror images)
        a, b: RVE dimensions
        radius: fiber radius
        folder_path: output folder
        config_num: configuration number (1-based)
    
    Returns:
        dictionary of statistics
    """
    # compute nearest-neighbor distances
    nn1_distances, nn2_distances = calculate_nearest_neighbors_rse(fiberList, a, b)
    
    # compute probability density
    nn1_centers, nn1_density = calculate_probability_density_rse(nn1_distances, radius)
    nn2_centers, nn2_density = calculate_probability_density_rse(nn2_distances, radius)
    
    # compute Ripley's K
    r_ripley, K_values, K_random = calculate_ripleys_k_rse(fiberList, a, b, radius)
    
    # compute the radial distribution function
    r_pdf, g_values = calculate_pair_distribution_function_rse(fiberList, a, b, radius)
    
    # save to CSV file
    save_statistics_csv_rse(
        folder_path,
        (nn1_centers, nn1_density),
        (nn2_centers, nn2_density),
        (r_ripley, K_values, K_random),
        (r_pdf, g_values),
        config_num
    )
    
    return {
        'nn1_mean': np.mean(nn1_distances),
        'nn1_std': np.std(nn1_distances),
        'nn1_min': np.min(nn1_distances),
        'nn1_max': np.max(nn1_distances),
        'nn2_mean': np.mean(nn2_distances),
        'nn2_std': np.std(nn2_distances),
        'nn2_min': np.min(nn2_distances),
        'nn2_max': np.max(nn2_distances)
    }




def save_nn_summary_rse(all_stats, folder_path):
    """
    Save the nearest-neighbor statistics summary for all configurations
    """
    summary_file = os.path.join(folder_path, "nearest_neighbor_distances.csv")
    with open(summary_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Config', 'NN1_Mean', 'NN1_Std', 'NN1_Min', 'NN1_Max',
                        'NN2_Mean', 'NN2_Std', 'NN2_Min', 'NN2_Max'])
        
        for i, stats in enumerate(all_stats, 1):
            writer.writerow([
                i,
                stats['nn1_mean'], stats['nn1_std'], stats['nn1_min'], stats['nn1_max'],
                stats['nn2_mean'], stats['nn2_std'], stats['nn2_min'], stats['nn2_max']
            ])


# Original functions remain unchanged below...

def create_folder(Basefolder, vf, file_suffix_range_Set, N):
    folder_name = "RVE_UDFibers{}_Vf{:03d}_xy_{}units".format(N, int(vf + 0.5), file_suffix_range_Set)
    folder_path = os.path.join(Basefolder, folder_name)
    suffix_folder = 0
    original_folder_path = folder_path
    
    while os.path.exists(folder_path):
        suffix_folder += 1
        folder_path = original_folder_path + "({})".format(suffix_folder)
    
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
    
    return folder_path

def save_fiber_coordinates_to_csv(folder_path, fibers, N, success_count, a, b):
    rect = (0, a, 0, b)
    all_fibers = []
    for fiber in fibers:
        x, y, radius, flag = fiber
        if circle_rectangle_intersect(x, y, radius, rect):
            all_fibers.append((x, y))
        if flag != 'in':
            expanded_centers = CalExpendCenter(fiber, a, b)
            for ex_center in expanded_centers:
                ex_x, ex_y = ex_center
                if circle_rectangle_intersect(ex_x, ex_y, radius, rect):
                    all_fibers.append((ex_x, ex_y))
    unique_fibers = set(all_fibers)
    csv_name = "RVE2D_{}Inclusions_IncCoordinates{:02d}.csv".format(N, success_count + 1)
    csv_path = os.path.join(folder_path, csv_name)
    with open(csv_path, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(['X', 'Y'])
        for x, y in unique_fibers:
            writer.writerow([x, y])


def round_fiber_data(fiber, decimal_places=15):
    return [round(value, decimal_places) if isinstance(value, float) else value for value in fiber]

def use_RSE_CreateRVE(vf0, vf, a, b, radius, lmax, lmin):
    fiberList = []
    # --- Packing effort.  Every draw packs to its jam point before fibres are
    #     removed down to the target, so these two numbers set the cost of
    #     confirming the jam.  Doubling them to 1000 / 1000 roughly triples the
    #     time per draw and barely raises the jam density; a draw that still
    #     falls short of N fibres is re-rolled in RSE_algorithm (Keep-Vf mode).
    #   Num_try                      : placement tries per chosen neighbour fibre
    #   max_attempts_without_success : consecutive dead-ends allowed before the
    #                                  cell is declared "jammed" and packing stops
    Num_try = 500
    max_attempts_without_success = 500
    attempts_without_success = 0
    cell_size = 2 * radius + MIN_GAP

    initFiber = FirstFiber(radius, a, b)
    if initFiber is None:
        return [], 0, False
    fiberList.append(initFiber)
    grid = build_grid_with_periodic(fiberList, a, b, cell_size)

    while attempts_without_success < max_attempts_without_success:
        Fiber_i = random.choice(fiberList)
        success = False
        for _ in range(Num_try):
            tempFiber = GenerateFiber(Fiber_i, radius, lmin, lmax, a, b)
            if tempFiber is None:
                continue
            if not IsintersectSelf(tempFiber, grid, a, b, radius, cell_size, MIN_GAP):
                fiberList.append(tempFiber)
                add_fiber_to_grid_with_periodic(tempFiber, grid, a, b, cell_size)
                success = True
                break
        if not success:
            attempts_without_success += 1
        else:
            attempts_without_success = 0

    current_vf = CalVolumeFraction(fiberList, a, b, radius)
    
    closest_vf = current_vf
    closest_fiberList = list(fiberList)

    while current_vf > vf / 100.0:
        removed_index = random.randint(0, len(fiberList) - 1)
        removed_fiber = fiberList.pop(removed_index)
        remove_fiber_from_grid_with_periodic(removed_fiber, grid, a, b, cell_size)
        current_vf = CalVolumeFraction(fiberList, a, b, radius)

        if abs(current_vf - vf / 100.0) < abs(closest_vf - vf / 100.0):
            closest_vf = current_vf
            closest_fiberList = list(fiberList)
        else:
            fiberList.append(removed_fiber)
            add_fiber_to_grid_with_periodic(removed_fiber, grid, a, b, cell_size)
            break

    return closest_fiberList, closest_vf, True

def IsintersectSelf(nowfiber, grid, a, b, radius, cell_size, min_gap=0.0):
    """True when nowfiber (or any periodic image) comes closer than
    2*radius + min_gap (centre to centre) to a fibre already in the grid."""
    nowfiber_centers = CalExpendCenter(nowfiber, a, b)
    for center_now in nowfiber_centers:
        x_now, y_now = center_now
        cell_x = int((x_now + a / 2) / cell_size)
        cell_y = int((y_now + b / 2) / cell_size)
        neighboring_cells = get_neighboring_cells(cell_x, cell_y)
        for cell in neighboring_cells:
            if cell in grid:
                for x_j, y_j, Fiber_j in grid[cell]:
                    if Fiber_j == nowfiber:
                        continue
                    if P2Pdistance_squared((x_now, y_now), (x_j, y_j)) < (2.0 * radius + min_gap) ** 2:
                        return True
    return False

def FirstFiber(radius, a, b):
    for _ in range(500):
        x1 = random.uniform(-radius, a + radius)
        y1 = random.uniform(-radius, b + radius)
        flag = ISoverreach(x1, y1, radius, a, b)
        if flag != 'out' and boundary_clearance_ok(x1, y1, radius, a, b):
            return [x1, y1, radius, flag]
    return None

def GenerateFiber(preFiber, radius, lmin, lmax, a, b):
    for _ in range(500):
        xlast = preFiber[0]
        ylast = preFiber[1]
        distance = random.uniform(max(lmin, MIN_GAP) + 2 * radius, lmax + 2 * radius)
        angle = random.uniform(0, 2 * math.pi)
        x = xlast + distance * math.cos(angle)
        y = ylast + distance * math.sin(angle)
        flag = ISoverreach(x, y, radius, a, b)
        if flag != 'out' and boundary_clearance_ok(x, y, radius, a, b):
            return [x, y, radius, flag]
    return None

def boundary_clearance_ok(x, y, r, a, b, clearance=None):
    """Return False when the fibre centred at (x, y) violates the boundary
    clearance rule.  Coordinates are in the RVE frame [0, a] x [0, b].

    * every RVE corner must stay at least r + h away from the centre (the
      fibre must not cover or graze a corner);
    * for every RVE edge the fibre must either cross it by at least h or stay
      at least h away from it (no thin caps, no thin matrix strips),

    where h = clearance * r (clearance defaults to BOUNDARY_CLEARANCE)."""
    h = (BOUNDARY_CLEARANCE if clearance is None else clearance) * r
    if h <= 0.0:
        return True
    # fast path: a fibre that stays at least h inside every edge passes
    if r + h < x < a - r - h and r + h < y < b - r - h:
        return True
    for cx, cy in ((0.0, 0.0), (a, 0.0), (0.0, b), (a, b)):
        if math.hypot(x - cx, y - cy) < r + h:
            return False
    for s in (x, a - x, y, b - y):
        if r - h < abs(s) < r + h:
            return False
    return True


def CalVolumeFraction(fiberlist, a, b, radius):
    area_fibers = len(fiberlist) * math.pi * radius ** 2
    area_rve = a * b
    return area_fibers / area_rve

def remove_fiber_from_grid_with_periodic(fiber, grid, a, b, cell_size):
    fiber_centers = CalExpendCenter(fiber, a, b)
    for center in fiber_centers:
        x, y = center
        cell_x = int((x + a / 2) / cell_size)
        cell_y = int((y + b / 2) / cell_size)
        key = (cell_x, cell_y)
        if key in grid:
            grid[key] = [item for item in grid[key] if item[2] != fiber]
            if not grid[key]:
                del grid[key]

def ISoverreach(x, y, r, a, b):
    if x + r <= 0 or x - r >= a or y + r <= 0 or y - r >= b:
        return 'out'
    elif (x - r >= 0) and (x + r <= a) and (y - r >= 0) and (y + r <= b):
        return 'in'
    else:
        left_overlap = x - r < 0
        right_overlap = x + r > a
        bottom_overlap = y - r < 0
        top_overlap = y + r > b

        if left_overlap and bottom_overlap:
            return 'Clb'
        elif left_overlap and top_overlap:
            return 'Clu'
        elif right_overlap and bottom_overlap:
            return 'Crb'
        elif right_overlap and top_overlap:
            return 'Cru'
        elif left_overlap:
            return 'Bl'
        elif right_overlap:
            return 'Br'
        elif bottom_overlap:
            return 'Bb'
        elif top_overlap:
            return 'Bu'
        else:
            return 'in'

def P2Pdistance_squared(p1, p2):
    return (p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2

def is_fiber_valid(fiber, a, b, radius):
    x, y = fiber[0], fiber[1]
    if -0.5 * a + radius <= x <= 0.5 * a - radius and -0.5 * b + radius <= y <= 0.5 * b - radius:
        return True
    if ISoverreach(x, y, radius, a, b) != 'out':
        return True
    return False


def get_neighboring_cells(cell_x, cell_y):
    cells = []
    for dx in [-1, 0, 1]:
        for dy in [-1, 0, 1]:
            cells.append((cell_x + dx, cell_y + dy))
    return cells

def build_grid_with_periodic(fiberlist, a, b, cell_size):
    grid = {}
    for fiber in fiberlist:
        fiber_centers = CalExpendCenter(fiber, a, b)
        for center in fiber_centers:
            x, y = center
            cell_x = int((x + a / 2) / cell_size)
            cell_y = int((y + b / 2) / cell_size)
            key = (cell_x, cell_y)
            if key not in grid:
                grid[key] = []
            grid[key].append((x, y, fiber))
    return grid

def add_fiber_to_grid_with_periodic(fiber, grid, a, b, cell_size):
    fiber_centers = CalExpendCenter(fiber, a, b)
    for center in fiber_centers:
        x, y = center
        cell_x = int((x + a / 2) / cell_size)
        cell_y = int((y + b / 2) / cell_size)
        key = (cell_x, cell_y)
        if key not in grid:
            grid[key] = []
        grid[key].append((x, y, fiber))

def CalExpendCenter(fiber, a, b):
    x = fiber[0]
    y = fiber[1]
    tempflag = fiber[3]
    expanded_centers = []
    shifts = []
    if tempflag == 'Clu':
        shifts = [(0, 0), (a, 0), (0, -b), (a, -b)]
    elif tempflag == 'Clb':
        shifts = [(0, 0), (a, 0), (0, b), (a, b)]
    elif tempflag == 'Cru':
        shifts = [(0, 0), (-a, 0), (0, -b), (-a, -b)]
    elif tempflag == 'Crb':
        shifts = [(0, 0), (-a, 0), (0, b), (-a, b)]
    elif tempflag == 'Bl':
        shifts = [(0, 0), (a, 0)]
    elif tempflag == 'Br':
        shifts = [(0, 0), (-a, 0)]
    elif tempflag == 'Bb':
        shifts = [(0, 0), (0, b)]
    elif tempflag == 'Bu':
        shifts = [(0, 0), (0, -b)]
    else:
        shifts = [(0, 0)]

    for dx, dy in shifts:
        cx = x + dx
        cy = y + dy
        expanded_centers.append((cx, cy))

    return expanded_centers

def circle_rectangle_intersect(cx, cy, radius, rect):
    x_min, x_max, y_min, y_max = rect
    nearest_x = max(x_min, min(cx, x_max))
    nearest_y = max(y_min, min(cy, y_max))
    dx = nearest_x - cx
    dy = nearest_y - cy
    distance_squared = dx * dx + dy * dy
    
    return distance_squared <= radius * radius

def Output_Information(N, current_vf, df, a, b, lmin, lmax, file_suffix_range_Set, average_time_per_set_of_coordinates_created, elapsed_time_RSE_Method, folder_path, control_options_name,
                       target_vf=None, config_records=None):
    txt_name = "RVE2D_parameters_output_Vf_{:03d}_xy_{}units_{}fiber.txt".format(int(current_vf * 100 + 0.5), file_suffix_range_Set, N)
    txt_save_path = os.path.join(folder_path, txt_name)
    
    with open(txt_save_path, "w") as file:
        file.write('Using the RSE algorithm, {} sets of random fiber circle center coordinates are successfully generated\n'.format(file_suffix_range_Set))
        file.write('--------------------------------------------------------------------\n')
        file.write('Fixed parameter: {}\n'.format(control_options_name))
        file.write('--------------------------------------------------------------------\n')
        file.write('User input parameters\n')
        file.write(' Volume Fraction of Fiber                         {:.4f}\n'.format(current_vf * 100))
        file.write(' Diameter of fiber                                {}\n'.format(df))
        file.write(' Number of fibers                                 {}\n'.format(N))
        file.write(' RVE width                                        {}\n'.format(a))
        file.write(' RVE height                                       {}\n'.format(b))
        file.write(' l_min for RSE                                    {}\n'.format(lmin))
        file.write(' l_max for RSE                                    {}\n'.format(lmax))
        file.write('--------------------------------------------------------------------\n')
        file.write(" Average time per set of coordinates created:     {:.2f} seconds.\n".format(average_time_per_set_of_coordinates_created))
        file.write(" Total time {:02d} set(s) of coordinates created:     {:.2f} seconds.\n".format(file_suffix_range_Set, elapsed_time_RSE_Method))
        file.write('--------------------------------------------------------------------\n')
        file.write(" The folder containing the model information and the coordinates of {} set(s) of random fiber centers has been saved at:\n".format(file_suffix_range_Set))
        file.write("==> {}\n".format(folder_path))
        file.write('--------------------------------------------------------------------\n')
        file.write(" Statistical analysis results have been exported to CSV files:\n")
        file.write("   - RVE2D_{}Inclusions_IncCoordinatesXX.csv: fibre-centre coordinates of configuration XX\n".format(N))
        file.write("   - nn1_probability_density_config_XX.csv: 1st nearest-neighbour distance density\n")
        file.write("   - nn2_probability_density_config_XX.csv: 2nd nearest-neighbour distance density\n")
        file.write("   - ripleys_k_config_XX.csv: Ripley's K function\n")
        file.write("   - pair_distribution_function_config_XX.csv: pair distribution function g(r)\n")
        file.write("   - nearest_neighbor_distances.csv: nearest-neighbour summary of all configurations\n")
        if config_records:
            write_config_check_table(file, config_records, N, target_vf, a, b)


def write_config_check_table(file, config_records, N, target_vf, a, b):
    """Per-configuration check: user input versus what was actually generated."""
    file.write('--------------------------------------------------------------------\n')
    file.write(' Per-configuration check (target vs. achieved)\n')
    file.write('   target: {} fibres, Vf = {:.4f}%, RVE {:.6g} x {:.6g}\n'.format(
        N, target_vf if target_vf is not None else float('nan'), a, b))
    file.write('   {:>6s} {:>8s} {:>12s} {:>10s} {:>9s} {:>9s}\n'.format(
        'config', 'fibres', 'Vf achieved', 'Vf diff', 're-rolls', 'time (s)'))
    n_short = 0
    for rec in config_records:
        diff = rec['vf'] - target_vf if target_vf is not None else 0.0
        flag = '' if rec['fibers'] == N else '   <-- short of N'
        if rec['fibers'] != N:
            n_short += 1
        file.write('   {:>6d} {:>8d} {:>11.4f}% {:>+9.4f}% {:>9d} {:>9.2f}{}\n'.format(
            rec['config'], rec['fibers'], rec['vf'], diff, rec['rerolls'], rec['time'], flag))
    total_rerolls = sum(rec['rerolls'] for rec in config_records)
    if n_short == 0:
        file.write('   All {} configurations contain exactly {} fibres'.format(len(config_records), N))
    else:
        file.write('   {} of {} configurations are short of {} fibres (keep-RVE-size mode reports the achieved Vf)'.format(
            n_short, len(config_records), N))
    file.write(' ({} re-rolled draw(s) in total).\n'.format(total_rerolls) if total_rerolls else '.\n')

# Example usage (uncomment to test):
"""
if __name__ == "__main__":
    Basefolder = "./"  # Current directory
    vf = 30  # Volume fraction in percentage
    df = 10  # Fiber diameter
    a = 100  # RVE width
    b = 100  # RVE height
    file_suffix_range_Set = 2  # Number of configurations to generate
    lmax = 15  # Maximum distance for RSE
    lmin = 0  # Minimum distance for RSE
    control_options = 1  # 1 for fixed vf, 2 for fixed RVE size
    
    circle_data = RSE_algorithm(Basefolder, vf, df, a, b, file_suffix_range_Set, lmax, lmin, control_options)
"""
