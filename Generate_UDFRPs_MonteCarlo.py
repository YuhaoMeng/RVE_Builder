# -*- coding: utf-8 -*-
###############################################################################
# Generate_UDFRPs_MonteCarlo.py
# -----------------------------------------------------------------------------
# Generates 2D fiber-center coordinates for a UDFRP RVE using a Monte-Carlo
# placement algorithm with a configurable safe distance. Imported by
# RVE_Builder_UDFRPs.CreateRVE when algorithm == 1.
###############################################################################
"""

## Used to generate 2D coordinates for the randomly distributed uniaxial continuous fiber RVE model.

## The code logic is based on the Monte Carlo algorithm.

## Allows parameters to be fine-tuned according to the user's choice to ensure
     "volume fraction first" or "RVE size first".      

## "for python 3.0" .

## Code author: Yuhao Meng

## Refrence: 
    
## Thank you for using this code. 
   If you refer to this code in your related work, please cite it accordingly.

"""

from __future__ import division
from __future__ import print_function
import math, os, random, csv, time

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
        #print("Adjusted volume fraction to vf={}% to match the RVE size.".format(vf))
    
    # Create folder to save results
    folder_path = create_folder(Basefolder, vf, num_sets, N)
    
    while success_count < num_sets:
        fibers, success = use_Monte_Carlo_CreateRVE(a, b, radius, N, l_safe)
        if success:
            # Shift the fiber coordinates by a/2 and b/2
            shifted_fibers = []
            for fiber in fibers:
                x_shifted = fiber[0] + a / 2.0
                y_shifted = fiber[1] + b / 2.0
                shifted_fiber = [x_shifted, y_shifted] + fiber[2:]
                shifted_fibers.append(shifted_fiber)
                # If fibres overlap the boundary, calculate and add periodic copies
                if fiber[3] != 'in':
                    expanded_centers = CalExpendCenter(fiber, a, b)
                    for ex_center in expanded_centers:
                        ex_x_shifted = ex_center[0] + a / 2.0
                        ex_y_shifted = ex_center[1] + b / 2.0
                        shifted_fiber_expanded = [ex_x_shifted, ex_y_shifted] + fiber[2:]
                        shifted_fibers.append(shifted_fiber_expanded)
            
            circle_data.append(shifted_fibers)
            
            save_fiber_coordinates_to_csv(folder_path, fibers, N, success_count, a, b)
            success_count += 1
            print(f"Successfully generated {success_count}/{num_sets} CSV files.\n")
        else:
            print(f"Failed to generate set {success_count + 1}, retrying.")

        
    end_time = time.time()
    elapsed_time = end_time - start_time
    average_time_per_set = elapsed_time / num_sets

    Output_Information(N, vf, df, a, b, l_safe, num_sets, average_time_per_set, elapsed_time, folder_path, control_options_name)

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
    #for python 2.7
    #with open(csv_path, mode='wb') as file:
    #for python 3.0
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
        if is_fiber_valid(new_fiber, a, b, radius) and not IsIntersectSelf(new_fiber, fiberList, a, b, radius, l_safe):
            fiberList.append(new_fiber)
        attempts += 1

    if len(fiberList) < N:
        #print("Could not generate required number of fibers without overlap.")
        return fiberList, False
    else:
        return fiberList, True

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


def Output_Information(N, vf, df, a, b, l_safe, num_sets, average_time_per_set, elapsed_time, folder_path, control_options_name):
    txt_name = "RVE2D_parameters_output_Vf_{:03d}_xy_{}units_{}fiber.txt".format(int(vf + 0.5), num_sets, N)
    txt_save_path = os.path.join(folder_path, txt_name)

    with open(txt_save_path, "w") as file:
        file.write('Using the Monte Carlo algorithm, {} set(s) of random fiber circle center coordinate(s) is(are) successfully generated.\n'.format(num_sets))
        file.write('--------------------------------------------------------------------\n')
        file.write('Fixed parameter: {}\n')
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