# -*- coding: utf-8 -*-
###############################################################################
# Generate_UDFRPs_MonteCarlo.py
# -----------------------------------------------------------------------------
# Generates 2D fiber-center coordinates for a UDFRP RVE using a Monte-Carlo
# placement algorithm with a configurable safe distance. Imported by
# RVE_Builder_UDFRPs.CreateRVE when algorithm == 1.
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
continuous-fibre RVE by Monte-Carlo placement with rejection of overlaps.

* "volume fraction first" or "RVE size first" control (control_options)
* l_safe: minimum surface-to-surface gap between any two fibres
* BOUNDARY_CLEARANCE: keeps fibres away from RVE corners and thin edge slivers
* writes the coordinates (with periodic images) to CSV

Author: Yuhao Meng (yuhaomeng@oceanica.ufrj.br)
"""

from __future__ import division
from __future__ import print_function
import math, os, random, csv, time

# Boundary clearance, as a fraction of the fibre radius.  A candidate fibre is
# rejected when a corner of the RVE lies inside or within this clearance of
# the fibre, or when the fibre crosses an RVE edge (or stops short of it) by
# less than this clearance.  This avoids fibres that cover an RVE corner (the
# geometry kernel cannot split such a fibre into four periodic parts) and the
# thin slivers that make meshing fail.  Set it to 0.0 to disable the check.
BOUNDARY_CLEARANCE = 0.1


def Monte_Carlo_algorithm(Basefolder, vf, df, a, b, num_sets, l_safe, control_options):
    start_time = time.time()
    circle_data = []
    success_count = 0
    radius = df / 2.0
    # Compute the number of fibers (N)
    area_RVE = a * b
    area_fiber_single = math.pi * (radius ** 2.0)
    N = int((vf *0.01 * area_RVE) / area_fiber_single)

    if control_options == 1:
        control_options_name = "vf"
        # Adjust a and b to match the exact volume fraction
        area_fiber_total = N * area_fiber_single
        area_RVE_new = area_fiber_total / (vf *0.01)
        scale_factor = math.sqrt(area_RVE_new / area_RVE)
        a *= scale_factor
        b *= scale_factor
        area_RVE = a * b
        print("Adjusted RVE dimensions to a={}, b={} to match the desired volume fraction.".format(a, b))
    elif control_options == 2:
        control_options_name = "RVE width and height"
        # Keep RVE size fixed, adjust vf accordingly
        area_fiber_total = N * area_fiber_single
        vf = (area_fiber_total / area_RVE) * 100
    
    # Create folder to save results
    folder_path = create_folder(Basefolder, vf, num_sets, N)
    
    config_records = []          # one entry per saved configuration (for the check table)
    config_start_time = time.time()
    failed_draws = 0
    while success_count < num_sets:
        fibers, success = use_Monte_Carlo_CreateRVE(a, b, radius, N, l_safe)
        if success:
            config_records.append({
                'config': success_count + 1,
                'fibers': len(fibers),
                'vf': len(fibers) * area_fiber_single / area_RVE * 100.0,
                'rerolls': failed_draws,
                'time': time.time() - config_start_time,
            })
            config_start_time = time.time()
            failed_draws = 0
            # Shift the fiber coordinates by a/2 and b/2 and add the periodic
            # copies of boundary fibres.  CalExpendCenter returns the original
            # centre as well, so duplicates are filtered by coordinate.
            shifted_fibers = []
            unique_coords = set()
            for fiber in fibers:
                centers = [(fiber[0], fiber[1])]
                if fiber[3] != 'in':
                    centers = CalExpendCenter(fiber, a, b)
                for cx, cy in centers:
                    coord = (cx + a / 2.0, cy + b / 2.0)
                    if coord in unique_coords:
                        continue
                    unique_coords.add(coord)
                    shifted_fibers.append([coord[0], coord[1]] + fiber[2:])
            
            circle_data.append(shifted_fibers)
            
            save_fiber_coordinates_to_csv(folder_path, fibers, N, success_count, a, b)
            success_count += 1
            print(f"Successfully generated {success_count}/{num_sets} CSV files.\n")
        else:
            failed_draws += 1       # retried silently; the count goes into the check table

        
    end_time = time.time()
    elapsed_time = end_time - start_time
    average_time_per_set = elapsed_time / num_sets

    Output_Information(N, vf, df, a, b, l_safe, num_sets, average_time_per_set, elapsed_time, folder_path, control_options_name,
                       config_records=config_records)

    # Info output
    print(' ')
    print('--------------------------------------------------------------------')
    print('------------------------------ Info show ---------------------------')
    print('--------------------------------------------------------------------')
    print(f'Fixed parameter: {control_options_name}\n')
    print(f'Using the Monte Carlo algorithm, {num_sets} set(s) of random fiber circle center coordinate(s) is(are) successfully generated.\n')
    print(' Volume Fraction of Fiber                         {:.4f}%'.format(vf))
    print(' Diameter of fiber                                {}'.format(df))
    print(' Number of fibers                                 {}'.format(N))
    print(' RVE width                                        {}'.format(a))
    print(' RVE height                                       {}'.format(b))
    print(' Safe distance between fibers                     {:.2f}'.format(l_safe))
    print('--------------------------------------------------------------------')
    print(" Average time per set of coordinates created:     {:.2f} seconds.".format(average_time_per_set))
    print(" Total time {:02d} set(s) of coordinates created:     {:.2f} seconds.".format(num_sets, elapsed_time))
    print('--------------------------------------------------------------------')
    print(" The folder containing the model information and the coordinates of {} set(s) of random fiber centers has been saved at: ".format(num_sets))
    print("    ==> {}".format(folder_path))
    print('--------------------------------------------------------------------')
    print('--------------------------------------------------------------------')
    print(' ')
    return circle_data

def create_folder(Basefolder, vf, num_sets, N):
    folder_name = "RVE_UDFibers{}_Vf{:03d}_xy_{}units".format(N, int(vf + 0.5), num_sets)
    folder_path = os.path.join(Basefolder, folder_name)
    # Check if the folder already exists, if so, add suffix and increment it
    suffix_folder = 0
    original_folder_path = folder_path

    while os.path.exists(folder_path):
        suffix_folder += 1
        folder_path = original_folder_path + "({})".format(suffix_folder)

    if not os.path.exists(folder_path):
        os.makedirs(folder_path)

    return folder_path

def save_fiber_coordinates_to_csv(folder_path, fibers, N, success_count, a, b):
    all_fibers = []
    # Iterate over all fibers
    for fiber in fibers:
        x, y, _, flag = fiber
        x_shifted = x + a / 2.0
        y_shifted = y + b / 2.0
        all_fibers.append((x_shifted, y_shifted))
        # If the fiber overlaps the boundary, include the periodic images
        if flag != 'in':
            expanded_centers = CalExpendCenter(fiber, a, b)
            for ex_center in expanded_centers:
                ex_x, ex_y = ex_center
                ex_x_shifted = ex_x + a / 2.0
                ex_y_shifted = ex_y + b / 2.0
                all_fibers.append((ex_x_shifted, ex_y_shifted))
    # Remove duplicates
    unique_fibers = set(all_fibers)
    # Generate CSV file name
    csv_name = "RVE2D_{}Inclusions_IncCoordinates{:02d}.csv".format(N, success_count + 1)
    csv_path = os.path.join(folder_path, csv_name)
    # Write to CSV
    with open(csv_path, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(['X', 'Y'])
        for x, y in unique_fibers:
            writer.writerow([x, y])

def use_Monte_Carlo_CreateRVE(a, b, radius, N, l_safe):
    fiberList = []
    max_attempts = N * 1000  # Prevent infinite loop
    attempts = 0

    while len(fiberList) < N and attempts < max_attempts:
        x = random.uniform(-a / 2, a / 2)
        y = random.uniform(-b / 2, b / 2)
        flag = ISoverreach(x, y, radius, a, b)
        new_fiber = [x, y, radius, flag]
        if not boundary_clearance_ok(x + a / 2.0, y + b / 2.0, radius, a, b):
            attempts += 1
            continue
        if is_fiber_valid(new_fiber, a, b, radius) and not IsIntersectSelf(new_fiber, fiberList, a, b, radius, l_safe):
            fiberList.append(new_fiber)
        attempts += 1

    if len(fiberList) < N:
        return fiberList, False
    else:
        return fiberList, True

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


def is_fiber_valid(fiber, a, b, radius):
    x, y, _, flag = fiber
    # Fiber must be inside the RVE or touching the boundary
    if flag != 'out':
        return True
    return False

# Determine whether the fiber intersects the boundary, returning the intersection location.
def ISoverreach(x, y, r, a, b):
    """Determine whether the fiber intersects the boundary, returning the intersection location."""
    left_overlap = x - r < -0.5 * a
    right_overlap = x + r > 0.5 * a
    bottom_overlap = y - r < -0.5 * b
    top_overlap = y + r > 0.5 * b

    if left_overlap and bottom_overlap:
        return 'Clb'  # Overlaps left and bottom boundaries
    elif left_overlap and top_overlap:
        return 'Clu'  # Overlaps left and top boundaries
    elif right_overlap and bottom_overlap:
        return 'Crb'  # Overlaps right and bottom boundaries
    elif right_overlap and top_overlap:
        return 'Cru'  # Overlaps right and top boundaries
    elif left_overlap:
        return 'Bl'   # Overlaps left boundary
    elif right_overlap:
        return 'Br'   # Overlaps right boundary
    elif bottom_overlap:
        return 'Bb'   # Overlaps bottom boundary
    elif top_overlap:
        return 'Bu'   # Overlaps top boundary
    elif (-0.5 * a + r) <= x <= (0.5 * a - r) and (-0.5 * b + r) <= y <= (0.5 * b - r):
        return 'in'   # Fully inside the RVE
    else:
        return 'out'  # Completely outside the RVE

# Calculate the distance between two points
def P2Pdistance(p1, p2):
    return math.hypot(p1[0] - p2[0], p1[1] - p2[1])

# Check for overlap with existing fibers, including periodic images
def IsIntersectSelf(new_fiber, fiberList, a, b, radius, l_safe):
    x_new, y_new, _, flag_new = new_fiber
    existing_fibers_expanded = []

    for fiber in fiberList:
        x_exist, y_exist, _, flag_exist = fiber
        # Get expanded centers for periodic images
        expanded_centers = [ (x_exist, y_exist) ]
        if flag_exist != 'in':
            expanded_centers += CalExpendCenter(fiber, a, b)
        existing_fibers_expanded.extend(expanded_centers)

    # Expand the new fiber's periodic images if it overlaps with boundary
    new_fiber_centers = [ (x_new, y_new) ]
    if flag_new != 'in':
        new_fiber_centers += CalExpendCenter(new_fiber, a, b)

    min_distance = 2 * radius + l_safe  # Minimum allowable distance between centers

    for x1, y1 in new_fiber_centers:
        for x2, y2 in existing_fibers_expanded:
            distance = P2Pdistance((x1, y1), (x2, y2))
            if distance < min_distance - 1e-6:  # small epsilon to account for floating point errors
                return True  # Overlapping
    return False

def CalExpendCenter(fiber, a, b):
    x = fiber[0]
    y = fiber[1]
    tempflag = fiber[3]
    if tempflag in ['Clu', 'Clb', 'Cru', 'Crb']:
        if tempflag == 'Clu':
            c1 = (x, y)
            c2 = (x + a, y)
            c3 = (x, y - b)
            c4 = (x + a, y - b)
        elif tempflag == 'Clb':
            c1 = (x, y)
            c2 = (x + a, y)
            c3 = (x, y + b)
            c4 = (x + a, y + b)
        elif tempflag == 'Cru':
            c1 = (x, y)
            c2 = (x - a, y)
            c3 = (x, y - b)
            c4 = (x - a, y - b)
        elif tempflag == 'Crb':
            c1 = (x, y)
            c2 = (x - a, y)
            c3 = (x, y + b)
            c4 = (x - a, y + b)
        return [c1, c2, c3, c4]
    elif tempflag == 'Bl':
        return [(x, y), (x + a, y)]
    elif tempflag == 'Br':
        return [(x, y), (x - a, y)]
    elif tempflag == 'Bb':
        return [(x, y), (x, y + b)]
    elif tempflag == 'Bu':
        return [(x, y), (x, y - b)]
    else:
        return [(x, y)]


def Output_Information(N, vf, df, a, b, l_safe, num_sets, average_time_per_set, elapsed_time, folder_path, control_options_name,
                       config_records=None):
    txt_name = "RVE2D_parameters_output_Vf_{:03d}_xy_{}units_{}fiber.txt".format(int(vf + 0.5), num_sets, N)
    txt_save_path = os.path.join(folder_path, txt_name)

    with open(txt_save_path, "w") as file:
        file.write('Using the Monte Carlo algorithm, {} set(s) of random fiber circle center coordinate(s) is(are) successfully generated.\n'.format(num_sets))
        file.write('--------------------------------------------------------------------\n')
        file.write('Fixed parameter: {}\n'.format(control_options_name))
        file.write('--------------------------------------------------------------------\n')
        file.write('User input parameters\n')
        file.write(' Volume Fraction of Fiber                         {:.4f}%\n'.format(vf))
        file.write(' Diameter of fiber                                {}\n'.format(df))
        file.write(' Number of fibers                                 {}\n'.format(N))
        file.write(' RVE width                                        {}\n'.format(a))
        file.write(' RVE height                                       {}\n'.format(b))
        file.write(' Safe distance between fibers                     {:.2f}\n'.format(l_safe))
        file.write('--------------------------------------------------------------------\n')
        file.write(" Average time per set of coordinates created:     {:.2f} seconds.\n".format(average_time_per_set))
        file.write(" Total time {:02d} set(s) of coordinates created:     {:.2f} seconds.\n".format(num_sets, elapsed_time))
        file.write('--------------------------------------------------------------------\n')
        file.write(" The folder containing the model information and the coordinates of {} set(s) of random fiber centers has been saved at:\n".format(num_sets))
        file.write("==> {}\n".format(folder_path))
        file.write('--------------------------------------------------------------------\n')
        file.write(" Files: RVE2D_{}Inclusions_IncCoordinatesXX.csv = fibre-centre coordinates of configuration XX\n".format(N))
        if config_records:
            write_config_check_table(file, config_records, N, vf, a, b)


def write_config_check_table(file, config_records, N, target_vf, a, b):
    """Per-configuration check: user input versus what was actually generated."""
    file.write('--------------------------------------------------------------------\n')
    file.write(' Per-configuration check (target vs. achieved)\n')
    file.write('   target: {} fibres, Vf = {:.4f}%, RVE {:.6g} x {:.6g}\n'.format(N, target_vf, a, b))
    file.write('   {:>6s} {:>8s} {:>12s} {:>10s} {:>13s} {:>9s}\n'.format(
        'config', 'fibres', 'Vf achieved', 'Vf diff', 'failed draws', 'time (s)'))
    n_short = 0
    for rec in config_records:
        flag = '' if rec['fibers'] == N else '   <-- short of N'
        if rec['fibers'] != N:
            n_short += 1
        file.write('   {:>6d} {:>8d} {:>11.4f}% {:>+9.4f}% {:>13d} {:>9.2f}{}\n'.format(
            rec['config'], rec['fibers'], rec['vf'], rec['vf'] - target_vf, rec['rerolls'], rec['time'], flag))
    if n_short == 0:
        file.write('   All {} configurations contain exactly {} fibres.\n'.format(len(config_records), N))
    else:
        file.write('   {} of {} configurations are short of {} fibres.\n'.format(n_short, len(config_records), N))
