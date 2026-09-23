# -*- coding: utf-8 -*-
###############################################################################
# PBC_UDFRP_Elastoplastic_interface.py
# -----------------------------------------------------------------------------
# Elastoplastic homogenization of a UDFRP RVE under PBC.
# - Uniaxial: applies any subset of {Strain11, Strain22, Strain33, Shear12,
#   Shear13, Shear23} as separate macroscopic strain cases.
# - Biaxial: applies any one of 15 pre-defined two-component combinations.
# - Multi-temperature: every case can be iterated over a list of Celsius
#   temperature points (converted to Kelvin internally).
# - Defensive cleanup wipes leftover steps / loads / BCs / constraints /
#   predefined temperature fields / analysis sets / reference points before
#   each new case to keep stale objects from polluting the run.
# - Output ODB / CSV filenames embed model name, loading label and the
#   signed temperature label only (no timestamps), so that Abaqus's Jobs
#   view can open the resulting ODB directly. Per-case uniqueness across
#   loads / temperatures is enforced by the upstream dispatcher creating
#   one sub-directory per (model, load, temperature) tuple. A re-run with
#   identical parameters re-uses the same job slot (mdb.jobs[job_name] is
#   deleted defensively before each Job() call).
# - Optional UMAT is honoured when supplied; left empty otherwise.
# - Called from RVE_Builder_UDFRPs.Analysis when analysis_type == 4.
# Author: Yuhao Meng
#
# -----------------------------------------------------------------------------
# Based on EasyPBC Ver. 1.4 (08/10/2018, updated 27/08/2019).
# Adapted for the "RVE Builder (UDFRPs)" Abaqus plug-in.
# Modifications Copyright (C) 2026 Yuhao Meng.
#
# From EasyPBC:
#      EasyPBC is an ABAQUS CAE plugin developed to estimate the homogenised
#      effective elastic properties of user-defined representative volume
#      elements.
#      Copyright (C) 2018  Sadik Lafta Omairey
#
#      This program is free software: you can redistribute it and/or modify
#      it under the terms of the GNU General Public License as published by
#      the Free Software Foundation, either version 3 of the License, or
#      (at your option) any later version.
#
#      This program is distributed in the hope that it will be useful,
#      but WITHOUT ANY WARRANTY; without even the implied warranty of
#      MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#      GNU General Public License for more details.
#
#      You should have received a copy of the GNU General Public License
#      along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
#      Citation: Omairey S, Dunning P, Sriramula S (2018) Development of an
#      ABAQUS plugin tool for periodic RVE homogenisation.
#      Engineering with Computers. https://doi.org/10.1007/s00366-018-0616-4
# -----------------------------------------------------------------------------
###############################################################################
"""
Complete RVE Multi-axial Analysis Code
Apply specified macroscopic strains, perform analysis, extract and save results to CSV files
Supports single-axis, bi-axial, and full multi-axial loading along the RVE axes
Author: Yuhao Meng
"""
from abaqus import *
from abaqusConstants import *
import __main__
import math
import section
import regionToolset
import displayGroupMdbToolset as dgm
import part
import material
import assembly
import step
import interaction
import load
import mesh
import job
import sketch
import visualization
import xyPlot
import displayGroupOdbToolset as dgo
import connectorBehavior
import time
import os
import sys
import ctypes
import multiprocessing
import numpy as np
import csv
from PBC_UDFRP_Elastic_CTE import _pbc_sorted_labels, _pbc_create_node_set, _pbc_create_single_node_sets
from PBC_UDFRP_Elastic_CTE import _pbc_build_connectivity_label_map
from PBC_UDFRP_Elastic_CTE import _pbc_build_master_triangles, _pbc_reduced_coordinates
from PBC_UDFRP_Elastic_CTE import _pbc_find_triangle_interpolation, _pbc_create_equation
from PBC_UDFRP_Elastic_CTE import _pbc_filter_allowed_labels, _pbc_find_nearest_reduced_node
from PBC_UDFRP_Elastic_CTE import _set_uniform_initial_temperature

def _interface_coord_key(coordinates, tolerance):
    scale = float(tolerance) if tolerance and tolerance > 0.0 else 1.0e-9
    return tuple([int(round(float(value) / scale)) for value in coordinates])

def has_duplicate_coordinate_nodes(modelObj, instanceName, tolerance):
    instance = modelObj.rootAssembly.instances[instanceName]
    seen = set()
    for node in instance.nodes:
        key = _interface_coord_key(node.coordinates, tolerance)
        if key in seen:
            return True
        seen.add(key)
    return False

def unique_coordinate_nodes(nodes, tolerance):
    representatives = {}
    for node in nodes:
        key = _interface_coord_key(node.coordinates, tolerance)
        current = representatives.get(key)
        if current is None or node.label < current.label:
            representatives[key] = node
    return [representatives[key] for key in sorted(representatives.keys())]

def _interface_duplicate_node_layers(nodes, tolerance):
    grouped = {}
    for node in nodes:
        key = _interface_coord_key(node.coordinates, tolerance)
        grouped.setdefault(key, []).append(node)
    maxCount = 0
    for nodeList in grouped.values():
        if len(nodeList) > maxCount:
            maxCount = len(nodeList)
    layers = []
    for layerIndex in range(1, maxCount):
        layerNodes = []
        for nodeList in grouped.values():
            nodeList = sorted(nodeList, key=lambda item: item.label)
            if len(nodeList) > layerIndex:
                layerNodes.append(nodeList[layerIndex])
        if layerNodes:
            layers.append(sorted(layerNodes, key=lambda item: item.label))
    return layers

def _interface_partition_boundary_nodes(nodes, bounds, tolerance):
    Max, May, Maz, Mnx, Mny, Mnz = bounds
    data = dict([(name, {}) for name in (
        'fronts', 'backs', 'tops', 'bots', 'lefts', 'rights',
        'ftedge', 'fbedge', 'btedge', 'bbedge',
        'fledge', 'fredge', 'bledge', 'bredge',
        'ltedge', 'lbedge', 'rtedge', 'rbedge',
    )])
    corners = dict([(name, []) for name in ('c1', 'c2', 'c3', 'c4', 'c5', 'c6', 'c7', 'c8')])
    for node in nodes:
        x, y, z = node.coordinates
        label = node.label
        coord = [x, y, z]
        onXMax = abs(x - Max) <= tolerance
        onXMin = abs(x - Mnx) <= tolerance
        onYMax = abs(y - May) <= tolerance
        onYMin = abs(y - Mny) <= tolerance
        onZMax = abs(z - Maz) <= tolerance
        onZMin = abs(z - Mnz) <= tolerance
        if onXMax and onYMax and onZMax:
            corners['c1'].append(label)
        elif onXMin and onYMax and onZMax:
            corners['c2'].append(label)
        elif onXMin and onYMax and onZMin:
            corners['c3'].append(label)
        elif onXMax and onYMax and onZMin:
            corners['c4'].append(label)
        elif onXMax and onYMin and onZMax:
            corners['c5'].append(label)
        elif onXMin and onYMin and onZMax:
            corners['c6'].append(label)
        elif onXMin and onYMin and onZMin:
            corners['c7'].append(label)
        elif onXMax and onYMin and onZMin:
            corners['c8'].append(label)
        elif onXMax and onYMax:
            data['ftedge'][label] = coord
        elif onXMax and onYMin:
            data['fbedge'][label] = coord
        elif onXMin and onYMax:
            data['btedge'][label] = coord
        elif onXMin and onYMin:
            data['bbedge'][label] = coord
        elif onXMax and onZMax:
            data['fledge'][label] = coord
        elif onXMax and onZMin:
            data['fredge'][label] = coord
        elif onXMin and onZMax:
            data['bledge'][label] = coord
        elif onXMin and onZMin:
            data['bredge'][label] = coord
        elif onZMax and onYMax:
            data['ltedge'][label] = coord
        elif onZMax and onYMin:
            data['lbedge'][label] = coord
        elif onZMin and onYMax:
            data['rtedge'][label] = coord
        elif onZMin and onYMin:
            data['rbedge'][label] = coord
        elif onXMax:
            data['fronts'][label] = coord
        elif onXMin:
            data['backs'][label] = coord
        elif onZMax:
            data['lefts'][label] = coord
        elif onZMin:
            data['rights'][label] = coord
        elif onYMax:
            data['tops'][label] = coord
        elif onYMin:
            data['bots'][label] = coord
    return data, corners

def _interface_pair_groups(slaveMap, masterMap, axes, tolerance):
    def reduced_key(coord):
        return _interface_coord_key([coord[index] for index in axes], tolerance)
    slaveGroups = {}
    masterGroups = {}
    for label, coord in slaveMap.items():
        slaveGroups.setdefault(reduced_key(coord), []).append(label)
    for label, coord in masterMap.items():
        masterGroups.setdefault(reduced_key(coord), []).append(label)
    slaveLabels = []
    masterLabels = []
    for key in sorted(slaveGroups.keys()):
        if key not in masterGroups:
            continue
        sLabels = sorted(slaveGroups[key])
        mLabels = sorted(masterGroups[key])
        pairCount = min(len(sLabels), len(mLabels))
        slaveLabels.extend(sLabels[:pairCount])
        masterLabels.extend(mLabels[:pairCount])
    return slaveLabels, masterLabels

def _interface_create_single_sets(a, instanceName, prefix, labels):
    for label in labels:
        setName = '%s%s' % (prefix, label)
        if setName not in a.sets:
            a.SetFromNodeLabels(name=setName, nodeLabels=((instanceName, [label]),))

def _interface_macro_for(macro_map, axis, comp, direction):
    terms = []
    for coef, setName, dof in macro_map.get((axis, comp), []):
        terms.append((-direction * coef, setName, dof))
    return terms

def _interface_add_elastoplastic_layer_pbc(modelName, a, instanceName, layerNodes,
                                           bounds, tolerance, macro_map, equation_prefix):
    data, corners = _interface_partition_boundary_nodes(layerNodes, bounds, tolerance)
    fronts, backs = _interface_pair_groups(data['fronts'], data['backs'], (1, 2), tolerance)
    tops, bots = _interface_pair_groups(data['tops'], data['bots'], (0, 2), tolerance)
    lefts, rights = _interface_pair_groups(data['lefts'], data['rights'], (0, 1), tolerance)
    ftedge, btedge = _interface_pair_groups(data['ftedge'], data['btedge'], (1, 2), tolerance)
    btedge2, bbedge = _interface_pair_groups(data['btedge'], data['bbedge'], (0, 2), tolerance)
    bbedge2, fbedge = _interface_pair_groups(data['bbedge'], data['fbedge'], (1, 2), tolerance)
    fledge, bledge = _interface_pair_groups(data['fledge'], data['bledge'], (1, 2), tolerance)
    bledge2, bredge = _interface_pair_groups(data['bledge'], data['bredge'], (0, 1), tolerance)
    bredge2, fredge = _interface_pair_groups(data['bredge'], data['fredge'], (1, 2), tolerance)
    ltedge, lbedge = _interface_pair_groups(data['ltedge'], data['lbedge'], (0, 2), tolerance)
    lbedge2, rbedge = _interface_pair_groups(data['lbedge'], data['rbedge'], (0, 1), tolerance)
    rbedge2, rtedge = _interface_pair_groups(data['rbedge'], data['rtedge'], (0, 2), tolerance)
    edgeRows = [(a1, b1, c1, d1) for a1, b1, b2, c1, c2, d1 in zip(ftedge, btedge, btedge2, bbedge, bbedge2, fbedge) if b1 == b2 and c1 == c2]
    ftedge, btedge, bbedge, fbedge = zip(*edgeRows) if edgeRows else ([], [], [], [])
    edgeRows = [(a1, b1, c1, d1) for a1, b1, b2, c1, c2, d1 in zip(fledge, bledge, bledge2, bredge, bredge2, fredge) if b1 == b2 and c1 == c2]
    fledge, bledge, bredge, fredge = zip(*edgeRows) if edgeRows else ([], [], [], [])
    edgeRows = [(a1, b1, c1, d1) for a1, b1, b2, c1, c2, d1 in zip(ltedge, lbedge, lbedge2, rbedge, rbedge2, rtedge) if b1 == b2 and c1 == c2]
    ltedge, lbedge, rbedge, rtedge = zip(*edgeRows) if edgeRows else ([], [], [], [])
    setPrefixes = ['iface_fronts', 'iface_backs', 'iface_tops', 'iface_bots', 'iface_lefts', 'iface_rights',
                   'iface_ftedge', 'iface_btedge', 'iface_bbedge', 'iface_fbedge',
                   'iface_fledge', 'iface_bledge', 'iface_bredge', 'iface_fredge',
                   'iface_ltedge', 'iface_lbedge', 'iface_rbedge', 'iface_rtedge']
    labelLists = [fronts, backs, tops, bots, lefts, rights, ftedge, btedge, bbedge, fbedge,
                  fledge, bledge, bredge, fredge, ltedge, lbedge, rbedge, rtedge]
    for setPrefix, labelList in zip(setPrefixes, labelLists):
        _interface_create_single_sets(a, instanceName, setPrefix, labelList)
    for cornerName, labels in corners.items():
        _interface_create_single_sets(a, instanceName, 'iface_%s_' % cornerName, labels)
    modelObj = mdb.models[modelName]
    def eq(name, slaveSet, masterSet, comp, macroTerms):
        terms = [(1.0, slaveSet, comp), (-1.0, masterSet, comp)]
        terms.extend(macroTerms)
        modelObj.Equation(name=name, terms=tuple(terms))
    for slave, master in zip(fronts, backs):
        for comp in (1, 2, 3):
            eq('%s-FB-U%d-%s' % (equation_prefix, comp, slave), 'iface_fronts%s' % slave, 'iface_backs%s' % master, comp, macro_map.get(('x', comp), []))
    for slave, master in zip(tops, bots):
        for comp in (1, 2, 3):
            eq('%s-TB-U%d-%s' % (equation_prefix, comp, slave), 'iface_tops%s' % slave, 'iface_bots%s' % master, comp, macro_map.get(('y', comp), []))
    for slave, master in zip(lefts, rights):
        for comp in (1, 2, 3):
            eq('%s-LR-U%d-%s' % (equation_prefix, comp, slave), 'iface_lefts%s' % slave, 'iface_rights%s' % master, comp, macro_map.get(('z', comp), []))
    for ft, bt, bb, fb in zip(ftedge, btedge, bbedge, fbedge):
        for comp in (1, 2, 3):
            eq('%s-FTBT-U%d-%s' % (equation_prefix, comp, ft), 'iface_ftedge%s' % ft, 'iface_btedge%s' % bt, comp, _interface_macro_for(macro_map, 'x', comp, -1))
            eq('%s-BTBB-U%d-%s' % (equation_prefix, comp, bt), 'iface_btedge%s' % bt, 'iface_bbedge%s' % bb, comp, _interface_macro_for(macro_map, 'y', comp, -1))
            eq('%s-BBFB-U%d-%s' % (equation_prefix, comp, bb), 'iface_bbedge%s' % bb, 'iface_fbedge%s' % fb, comp, _interface_macro_for(macro_map, 'x', comp, +1))
    for fl, bl, br, fr in zip(fledge, bledge, bredge, fredge):
        for comp in (1, 2, 3):
            eq('%s-FLBL-U%d-%s' % (equation_prefix, comp, fl), 'iface_fledge%s' % fl, 'iface_bledge%s' % bl, comp, _interface_macro_for(macro_map, 'x', comp, -1))
            eq('%s-BLBR-U%d-%s' % (equation_prefix, comp, bl), 'iface_bledge%s' % bl, 'iface_bredge%s' % br, comp, _interface_macro_for(macro_map, 'z', comp, -1))
            eq('%s-BRFR-U%d-%s' % (equation_prefix, comp, br), 'iface_bredge%s' % br, 'iface_fredge%s' % fr, comp, _interface_macro_for(macro_map, 'x', comp, +1))
    for lt, lb, rb, rt in zip(ltedge, lbedge, rbedge, rtedge):
        for comp in (1, 2, 3):
            eq('%s-LTLB-U%d-%s' % (equation_prefix, comp, lt), 'iface_ltedge%s' % lt, 'iface_lbedge%s' % lb, comp, _interface_macro_for(macro_map, 'y', comp, -1))
            eq('%s-LBRB-U%d-%s' % (equation_prefix, comp, lb), 'iface_lbedge%s' % lb, 'iface_rbedge%s' % rb, comp, _interface_macro_for(macro_map, 'z', comp, -1))
            eq('%s-RBRT-U%d-%s' % (equation_prefix, comp, rb), 'iface_rbedge%s' % rb, 'iface_rtedge%s' % rt, comp, _interface_macro_for(macro_map, 'y', comp, +1))
    cornerRows = zip(
        sorted(corners['c6']), sorted(corners['c2']), sorted(corners['c3']), sorted(corners['c4']),
        sorted(corners['c8']), sorted(corners['c5']), sorted(corners['c1']), sorted(corners['c7'])
    )
    for rowIndex, (c6, c2, c3, c4, c8, c5, c1, c7) in enumerate(cornerRows, start=1):
        cornerSteps = [
            ('iface_c6_%s' % c6, 'iface_c2_%s' % c2, [('y', +1)]),
            ('iface_c2_%s' % c2, 'iface_c3_%s' % c3, [('z', -1)]),
            ('iface_c3_%s' % c3, 'iface_c4_%s' % c4, [('x', +1)]),
            ('iface_c4_%s' % c4, 'iface_c8_%s' % c8, [('y', -1)]),
            ('iface_c8_%s' % c8, 'iface_c5_%s' % c5, [('z', +1)]),
            ('iface_c5_%s' % c5, 'iface_c1_%s' % c1, [('y', +1)]),
            ('iface_c1_%s' % c1, 'iface_c7_%s' % c7, [('x', -1), ('y', -1), ('z', -1)]),
        ]
        for stepIndex, (slaveSet, masterSet, axesDirs) in enumerate(cornerSteps, start=1):
            for comp in (1, 2, 3):
                macroTerms = []
                for axis, direction in axesDirs:
                    macroTerms.extend(_interface_macro_for(macro_map, axis, comp, direction))
                eq('%s-Corner%d-U%d-%d' % (equation_prefix, stepIndex, comp, rowIndex), slaveSet, masterSet, comp, macroTerms)

def format_temperature_file_label(temperature_value):
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

def sanitize_loading_label(label_text):
    text_value = str(label_text or '').strip()
    if text_value == '':
        return 'Analysis'
    sanitized = []
    for char in text_value:
        if char.isalnum() or char in ('_', '-'):
            sanitized.append(char)
        else:
            sanitized.append('_')
    sanitized_text = ''.join(sanitized)
    while '__' in sanitized_text:
        sanitized_text = sanitized_text.replace('__', '_')
    return sanitized_text.strip('_') or 'Analysis'

def sanitize_job_token(label_text):
    text_value = str(label_text or '').strip()
    if text_value == '':
        return 'Job'
    sanitized = []
    for char in text_value:
        if char.isalnum():
            sanitized.append(char)
        else:
            sanitized.append('_')
    sanitized_text = ''.join(sanitized)
    while '__' in sanitized_text:
        sanitized_text = sanitized_text.replace('__', '_')
    return sanitized_text.strip('_') or 'Job'

def build_result_timestamp():
    current_time = time.time()
    milliseconds = int((current_time - int(current_time)) * 1000.0)
    return '{}_{:03d}'.format(time.strftime('%Y%m%d_%H%M%S', time.localtime(current_time)), milliseconds)

def build_elastoplastic_job_name(model_name, loading_label, temperature_celsius, run_timestamp=None):
    model_token = sanitize_job_token(model_name)[:18]
    loading_token = sanitize_job_token(loading_label)[:18]
    temperature_token = sanitize_job_token(format_temperature_file_label(temperature_celsius))[:12]
    name_parts = ['Job', model_token, loading_token]
    if temperature_token != '':
        name_parts.append(temperature_token)
    return '_'.join(name_parts)

def _delete_elastoplastic_analysis_steps(modelObj):
    stepNames = list(modelObj.steps.keys())
    stepNames.reverse()
    for stepName in stepNames:
        if stepName != 'Initial':
            del modelObj.steps[stepName]

def _delete_elastoplastic_loads_bcs_outputs(modelObj):
    loadNames = list(modelObj.loads.keys())
    for loadName in loadNames:
        del modelObj.loads[loadName]
    bcNames = list(modelObj.boundaryConditions.keys())
    for bcName in bcNames:
        del modelObj.boundaryConditions[bcName]
    historyNames = list(modelObj.historyOutputRequests.keys())
    for historyName in historyNames:
        if historyName != 'H-Output-1':
            del modelObj.historyOutputRequests[historyName]

def _delete_elastoplastic_constraints(modelObj):
    constraintNames = list(modelObj.constraints.keys())
    for constraintName in constraintNames:
        del modelObj.constraints[constraintName]

def _delete_elastoplastic_temperature_fields(modelObj):
    fieldNames = list(modelObj.predefinedFields.keys())
    for fieldName in fieldNames:
        if fieldName.startswith('Predefined Field-') or ('Temperature' in fieldName):
            del modelObj.predefinedFields[fieldName]

def _delete_elastoplastic_analysis_sets(assemblyObj):
    exactSetNames = (
        'RP1', 'RP2', 'RP3', 'RP4', 'RP5', 'RP6',
        'c1', 'c2', 'c3', 'c4', 'c5', 'c6', 'c7', 'c8',
        'ftedge', 'fbedge', 'btedge', 'bbedge',
        'fledge', 'fredge', 'bledge', 'bredge',
        'ltedge', 'lbedge', 'rtedge', 'rbedge',
        'fronts', 'backs', 'lefts', 'rights', 'tops', 'bots',
        'frontbc', 'backbc', 'leftbc', 'rightbc', 'topbc', 'botbc',
        'Error set', 'ELASTIC_ALL_NODES', 'UMAT_HISTORY_ELEMENTS'
    )
    prefixSetNames = (
        'PBCNode', 'iface_',
        'ftedge', 'fbedge', 'btedge', 'bbedge',
        'fledge', 'fredge', 'bledge', 'bredge',
        'ltedge', 'lbedge', 'rtedge', 'rbedge',
        'fronts', 'backs', 'lefts', 'rights', 'tops', 'bots',
        'frontbc', 'backbc', 'leftbc', 'rightbc', 'topbc', 'botbc'
    )
    setNames = list(assemblyObj.sets.keys())
    for setName in setNames:
        shouldDelete = False
        if setName in exactSetNames:
            shouldDelete = True
        else:
            for prefixName in prefixSetNames:
                if setName.startswith(prefixName):
                    shouldDelete = True
                    break
        if shouldDelete:
            del assemblyObj.sets[setName]

def _delete_elastoplastic_reference_points(assemblyObj):
    featureNames = list(assemblyObj.features.keys())
    for featureName in featureNames:
        if featureName.startswith('RP'):
            del assemblyObj.features[featureName]

def _reset_elastoplastic_analysis_state(modelObj, assemblyObj):
    _delete_elastoplastic_loads_bcs_outputs(modelObj)
    _delete_elastoplastic_constraints(modelObj)
    _delete_elastoplastic_temperature_fields(modelObj)
    _delete_elastoplastic_analysis_steps(modelObj)
    _delete_elastoplastic_analysis_sets(assemblyObj)
    _delete_elastoplastic_reference_points(assemblyObj)

def normalize_loading_type_label(loading_type):
    loading_map = {
        'Strain11': 'E11',
        'Strain22': 'E22',
        'Strain33': 'E33',
        'Shear12': 'G12',
        'Shear13': 'G13',
        'Shear23': 'G23',
    }
    return loading_map.get(loading_type, loading_type)

def create_csv_writer(filename, fieldnames):
    """Create CSV writer with specified fieldnames.
    Open in BINARY mode so Abaqus's Python 2.7 does not add a stray '\\r' to
    csv's line ending on Windows (that artifact produced a blank row between
    every data row).  Py3 uses newline='' for the same effect."""
    try:
        import sys as _sys
        if _sys.version_info[0] >= 3:
            csvfile = open(filename, 'w', newline='')
        else:
            csvfile = open(filename, 'wb')
        # extrasaction='ignore' so result dicts with extra keys do not raise -- the
        # row simply omits those columns. Matches the user expectation that mismatched
        # post-processing data still writes a valid CSV.
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames, lineterminator='\n', extrasaction='ignore')
        writer.writeheader()
        return csvfile, writer
    except Exception as e:
        print("Error creating CSV file: {}".format(str(e)))
        return None, None

def close_csv_file(csvfile):
    """Close CSV file safely"""
    if csvfile:
        csvfile.close()


# one concise explanation per summary variable (★ = value to type into the card)
_CONC_SUMMARY_DOC = [
    ('Loading_Direction',     'loading direction 11/22/33 (22 = transverse tension)'),
    ('Matrix_Region',         'name of the element set used to extract matrix stress'),
    ('Void_Model',            'whether this RVE is a porous (void) model'),
    ('Matrix_Porosity',       'matrix porosity = void/(void+solid)'),
    ('SCF_loc_elastic',       'elastic regime: matrix mean stress / macro stress (Mori-Tanaka localization factor, usually <1)'),
    ('k_yield_onset',         '★PROPS(39) K_YIELD: matrix Mises peak/mean @yield; controls when the matrix yields'),
    ('yield_onset_frame',     'frame index at which matrix yield is detected'),
    ('yield_onset_macro',     'macro stress at matrix yield (MPa)'),
    ('SCFt_at_onset',         '★PROPS(29) SCFt: matrix transverse stress peak/mean @debond; transverse-tension stress concentration'),
    ('SCFt_tot_at_onset',     'matrix peak / macro stress = SCF_loc x SCFt'),
    ('debond_onset_frame',    'frame index of interface debonding onset'),
    ('debond_onset_macro_stress', 'macro stress at debonding onset (MPa); approximately the red-line peak'),
    ('debond_onset_macro_strain', 'macro strain at debonding onset'),
    ('debond_onset_mtx_avg',  'matrix mean transverse stress at debonding (MPa)'),
    ('debond_onset_iface_Tn', 'interface peak normal traction at debonding (MPa)'),
    ('K_int_debond_driver',   '★PROPS(38) K_INT: interface peak traction / matrix mean; drives when debonding occurs'),
    ('K_INT_eff_trigger',     'event-matched: TN0 / matrix mean @debond (~raw; must be x alpha before filling the card)'),
    ('K_YIELD_eff_trigger',   'event-matched: s0t / matrix Mises mean @yield (must be x alpha)'),
    ('SCFt_eff_trigger',      'event-matched: sigma_ft / matrix mean @damage (must be x alpha)'),
    ('SCF_loc_at_yield',      'yield frame SCF_loc(RVE) = matrix mean / macro; used to compute alpha'),
    ('SCF_loc_at_debond',     'debond frame SCF_loc(RVE) = matrix mean / macro; used to compute alpha'),
    ('alpha_hint',            'alpha correction: card value = eff_trigger x SCF_loc_RVE / SCF_loc_UMAT(STATEV34/macro)'),
    ('onset_by',              'debond criterion: CSDMG/SDEG init / iface_traction_peak / macro_stress_peak'),
]


def write_summary_txt(path, summary):
    """Write the concentration summary as an annotated .txt: one variable per
    line, aligned 'name = value   # meaning'. Keys not documented are appended."""
    try:
        doc_keys = [k for (k, _d) in _CONC_SUMMARY_DOC]
        extra = [k for k in summary.keys() if k not in doc_keys]
        items = _CONC_SUMMARY_DOC + [(k, '') for k in extra]
        wname = max([len(k) for (k, _d) in items])
        vals = []
        for (k, _d) in items:
            v = summary.get(k, '')
            vals.append(('%.4f' % v) if isinstance(v, float) else str(v))
        wval = max([len(s) for s in vals]) if vals else 1
        f = open(path, 'w')
        f.write('# RVE stress-concentration factor summary  (UMAT calibration)\n')
        f.write('# one variable per line;  name = value   # meaning\n')
        f.write('# the three rows marked PROPS(..) and ★ are the stress-concentration factors to enter in the material card\n')
        f.write('# ' + '-' * 64 + '\n')
        for i, (k, d) in enumerate(items):
            line = '%s = %s' % (k.ljust(wname), vals[i].ljust(wval))
            if d:
                line = '%s   # %s' % (line, d)
            f.write(line + '\n')
        f.close()
        return True
    except Exception as e:
        print("Error writing summary txt: {}".format(str(e)))
        return False


# Field-output sampling.  A macroscopic stress-strain curve needs only ~50-100
# frames, but 'frequency=1' on a fine mesh bloats the ODB to many GB and the
# (largely serial) ODB I/O then dominates wall-clock.  numIntervals=N writes N
# evenly-spaced field frames over the step (Abaqus '*Output, field, number
# interval=N').  Set to 0 to restore the old every-increment full output
# (frequency=1).  History output (RP forces, energies in energy_check) is
# UNAFFECTED and stays every increment, so the energy curve keeps full density;
# only the field-based macroscopic stress-strain curve becomes ~N points.
FIELD_OUTPUT_NUM_INTERVALS = 80


# Physical constituent densities for the quasi-static implicit-dynamics step,
# in consistent N-mm-MPa-tonne-s units (tonne/mm^3 = g/cm^3 x 1e-9):
#   epoxy matrix   ~1.20 g/cm^3 -> 1.20e-9
#   E-glass fibre  ~2.54 g/cm^3 -> 2.54e-9   (E=74 GPa, nu=0.2 => E-glass)
#   cohesive/interface: zero-thickness, mass negligible -> matrix value
# IMPORTANT: Melro et al. (2013) Parts I & II are *static* analyses, so the
# paper reports NO density -- these are standard constituent values, not paper
# values.  In quasi-static implicit dynamics the stress-strain result is
# INDEPENDENT of density as long as ALLKE/ALLIE (KE_Ratio in the energy_check
# CSV) stays small; density is a numerical inertial regulariser here, not a
# constitutive parameter.  Densities the user already defined are NOT touched.
QUASI_STATIC_DEFAULT_DENSITY = 1.20e-9
QUASI_STATIC_DENSITY_BY_NAME = (
    ('eglass',    2.54e-9),
    ('glass',     2.54e-9),
    ('carbon',    1.80e-9),
    ('fib',       2.54e-9),
    ('epoxy',     1.20e-9),
    ('matrix',    1.20e-9),
    ('interface', 1.20e-9),
    ('cohes',     1.20e-9),
)


def _density_for_material(mname, default_density):
    low = mname.lower()
    for key, rho in QUASI_STATIC_DENSITY_BY_NAME:
        if key in low:
            return rho
    return default_density


def ensure_material_density(model, default_density=QUASI_STATIC_DEFAULT_DENSITY,
                            verbose=True):
    """Implicit dynamics needs a mass matrix, so every material must have a
    *Density.  Add a physically-reasonable density (matched by material name;
    see QUASI_STATIC_DENSITY_BY_NAME) to any material that lacks one; existing
    densities are left untouched.  Returns the list of patched 'name=rho'."""
    patched = []
    try:
        for mname in model.materials.keys():
            mat = model.materials[mname]
            has_density = False
            try:
                has_density = mat.density is not None
            except Exception:
                has_density = False
            if not has_density:
                rho = _density_for_material(mname, default_density)
                try:
                    mat.Density(table=((rho,),))
                    patched.append('%s=%g' % (mname, rho))
                except Exception as e:
                    print('  [density] could not set density on %s: %s'
                          % (mname, str(e)))
        if verbose and patched:
            print('  [density] auto-added density to materials lacking one: %s'
                  % ', '.join(patched))
    except Exception as e:
        print('  [density] material density scan failed: %s' % str(e))
    return patched


def extract_energy_history(odb, step_name, output_dir, output_model_name,
                           loading_label='', verbose=True):
    """Extract whole-model energy history and write an energy-verification CSV.

    Reads ALLIE / ALLSE / ALLPD / ALLDMD / ALLSD / ALLVD / ALLKE / ALLWK from the
    assembly (whole-model) history region produced by the 'H-Output-UMAT-Energy'
    request, then writes one row per history frame with two diagnostic ratios:

        Stab_Visc_Ratio = (ALLSD + ALLVD) / ALLIE   -- artificial-damping fraction
        KE_Ratio        = ALLKE / ALLIE             -- inertia fraction (quasi-static check)

    plus an Energy_OK flag (1 while both ratios are within tolerance, else 0).
    The softening/descending branch is physically trustworthy only while
    Energy_OK == 1; once the ratios blow up the curve is carried by artificial
    energy, not by the real material response.

    NOTE: ALLDMD only captures Abaqus built-in (cohesive) damage dissipation.
    The matrix UMAT's own (Bazant/Melro) damage dissipation is NOT included here.
    """
    try:
        if step_name not in odb.steps.keys():
            available = odb.steps.keys()
            if not available:
                return None
            step_name = available[0]
        step = odb.steps[step_name]

        # Locate the whole-model assembly history region (the one carrying ALLIE).
        energy_region = None
        for rname in step.historyRegions.keys():
            hr = step.historyRegions[rname]
            if 'ALLIE' in hr.historyOutputs.keys():
                energy_region = hr
                break
        if energy_region is None:
            if verbose:
                print("  Energy check: no whole-model energy history in ODB; skipped.")
            return None

        wanted = ['ALLIE', 'ALLSE', 'ALLPD', 'ALLDMD', 'ALLSD', 'ALLVD',
                  'ALLKE', 'ALLWK']
        series = {}
        time_axis = None
        for var in wanted:
            if var in energy_region.historyOutputs.keys():
                data = energy_region.historyOutputs[var].data  # list of (time, value)
                series[var] = [float(v) for (t, v) in data]
                if time_axis is None:
                    time_axis = [float(t) for (t, v) in data]

        if time_axis is None:
            if verbose:
                print("  Energy check: energy region found but no usable series; skipped.")
            return None

        n = len(time_axis)
        for var in series:
            n = min(n, len(series[var]))

        # Tolerances: artificial damping should stay small; inertia negligible.
        STAB_VISC_TOL = 0.10   # (ALLSD+ALLVD)/ALLIE
        KE_TOL = 0.02          # ALLKE/ALLIE (quasi-static dynamics sanity check)

        fieldnames = ['Frame', 'Time', 'ALLIE', 'ALLSE', 'ALLPD', 'ALLDMD',
                      'ALLSD', 'ALLVD', 'ALLKE', 'ALLWK',
                      'Stab_Visc_Ratio', 'KE_Ratio', 'Energy_OK']
        filename = os.path.join(output_dir,
            '{}_energy_check_{}.csv'.format(
                output_model_name, loading_label))
        csvfile, writer = create_csv_writer(filename, fieldnames)
        if not writer:
            return None

        def _get(var, i):
            s = series.get(var)
            return s[i] if (s is not None and i < len(s)) else 0.0

        last_ok_time = None
        first_bad_time = None
        for i in range(n):
            allie = _get('ALLIE', i)
            allsd = _get('ALLSD', i)
            allvd = _get('ALLVD', i)
            allke = _get('ALLKE', i)
            denom = abs(allie)
            if denom > 1e-30:
                sv_ratio = (allsd + allvd) / denom
                ke_ratio = allke / denom
            else:
                sv_ratio = 0.0
                ke_ratio = 0.0
            ok = 1 if (abs(sv_ratio) <= STAB_VISC_TOL and abs(ke_ratio) <= KE_TOL) else 0
            if ok:
                last_ok_time = time_axis[i]
            elif first_bad_time is None:
                first_bad_time = time_axis[i]
            writer.writerow({
                'Frame': i,
                'Time': time_axis[i],
                'ALLIE': allie,
                'ALLSE': _get('ALLSE', i),
                'ALLPD': _get('ALLPD', i),
                'ALLDMD': _get('ALLDMD', i),
                'ALLSD': allsd,
                'ALLVD': allvd,
                'ALLKE': allke,
                'ALLWK': _get('ALLWK', i),
                'Stab_Visc_Ratio': sv_ratio,
                'KE_Ratio': ke_ratio,
                'Energy_OK': ok,
            })
        close_csv_file(csvfile)

        if verbose:
            print("  Energy check CSV: %s" % os.path.basename(filename))
            if first_bad_time is not None:
                print("  *** Energy WARNING: (ALLSD+ALLVD)/ALLIE or ALLKE/ALLIE exceeded "
                      "tolerance at step time %.4g; results are physically trustworthy "
                      "only up to step time %s." % (
                          first_bad_time,
                          ('%.4g' % last_ok_time) if last_ok_time is not None else 'N/A'))
            else:
                print("  Energy check: artificial-energy ratios within tolerance "
                      "for all frames.")
        return filename
    except Exception as e:
        print("  Energy check failed: %s" % str(e))
        return None


def build_multiaxial_strict_pbc_equations_3d(modelName, a, instanceName,
                                              fronts, backs, tops, bots, lefts, rights,
                                              ftedge, btedge, bbedge, fbedge,
                                              fledge, bledge, bredge, fredge,
                                              ltedge, lbedge, rbedge, rtedge,
                                              macro_map, equation_prefix='StrictPBC'):
    """
    Strict point-to-point multiaxial PBC equations using the EasyPBC face/edge/
    corner walk. Each DOF is eliminated by exactly one Equation, mirroring the
    proven elastic-CTE PBC layout but parameterized by `macro_map`, so any
    combination of normal + shear loading can be handled in a single solve.

    Inputs:
      * fronts/backs, tops/bots, lefts/rights -- face-interior node label lists
        (must already be paired by coordinate so list[i] are geometric pairs)
      * ftedge/btedge/bbedge/fbedge -- Z-parallel edge 4-tuples
      * fledge/bledge/bredge/fredge -- Y-parallel edge 4-tuples
      * ltedge/lbedge/rbedge/rtedge -- X-parallel edge 4-tuples
      * c1..c8 singleton sets are looked up by name (already created upstream)
      * macro_map -- {(axis, comp): [(coef, set, dof), ...]} matching the
        face-interior convention "u_slave - u_master + macro_map_terms = 0".

    Edge and corner walks reuse the EasyPBC layout (chains of 3 and 7 steps),
    with macro terms picked up only on transitions where the relevant axis
    actually changes, and the sign flipped for forward (low->high) transitions.
    """
    modelObj = mdb.models[modelName]

    # axis -> low corner coord side; +1 = forward (slave on low side, master on
    # high side); -1 = backward. Flip macro_map sign on forward transitions.
    def _macro_for(axis, comp, direction):
        out = []
        for coef, set_name, dof in macro_map.get((axis, comp), []):
            out.append((-direction * coef, set_name, dof))
        return out

    createdCount = [0]

    def _eq(name, slave_set, master_set, comp, macro_terms):
        terms = [(1.0, slave_set, comp), (-1.0, master_set, comp)]
        terms.extend(macro_terms)
        try:
            modelObj.Equation(name=name, terms=tuple(terms))
            createdCount[0] += 1
        except Exception as exc:
            # Skip duplicates silently; surface anything else.
            msg = str(exc).lower()
            if 'already exists' not in msg and 'duplicate' not in msg:
                print('[warn] Equation %s failed: %s' % (name, exc))

    # ---- Face-interior equations (slave on high coord, master on low coord) ----
    for s, m in zip(fronts, backs):
        for c in (1, 2, 3):
            _eq('%s-FB-U%d-%s' % (equation_prefix, c, s),
                'fronts%s' % s, 'backs%s' % m, c, macro_map.get(('x', c), []))
    for s, m in zip(tops, bots):
        for c in (1, 2, 3):
            _eq('%s-TB-U%d-%s' % (equation_prefix, c, s),
                'tops%s' % s, 'bots%s' % m, c, macro_map.get(('y', c), []))
    for s, m in zip(lefts, rights):
        for c in (1, 2, 3):
            _eq('%s-LR-U%d-%s' % (equation_prefix, c, s),
                'lefts%s' % s, 'rights%s' % m, c, macro_map.get(('z', c), []))

    # ---- Edge chains (3 steps per 4-tuple, 3 components each) ----
    # Z-parallel edges: ftedge (Hx,Hy) -> btedge (Lx,Hy) -> bbedge (Lx,Ly) -> fbedge (Hx,Ly)
    for ft, bt, bb, fb in zip(ftedge, btedge, bbedge, fbedge):
        for c in (1, 2, 3):
            _eq('%s-FTBT-U%d-%s' % (equation_prefix, c, ft),
                'ftedge%s' % ft, 'btedge%s' % bt, c, _macro_for('x', c, -1))
            _eq('%s-BTBB-U%d-%s' % (equation_prefix, c, bt),
                'btedge%s' % bt, 'bbedge%s' % bb, c, _macro_for('y', c, -1))
            _eq('%s-BBFB-U%d-%s' % (equation_prefix, c, bb),
                'bbedge%s' % bb, 'fbedge%s' % fb, c, _macro_for('x', c, +1))
    # Y-parallel edges: fledge (Hx,Hz) -> bledge (Lx,Hz) -> bredge (Lx,Lz) -> fredge (Hx,Lz)
    for fl, bl, br, fr in zip(fledge, bledge, bredge, fredge):
        for c in (1, 2, 3):
            _eq('%s-FLBL-U%d-%s' % (equation_prefix, c, fl),
                'fledge%s' % fl, 'bledge%s' % bl, c, _macro_for('x', c, -1))
            _eq('%s-BLBR-U%d-%s' % (equation_prefix, c, bl),
                'bledge%s' % bl, 'bredge%s' % br, c, _macro_for('z', c, -1))
            _eq('%s-BRFR-U%d-%s' % (equation_prefix, c, br),
                'bredge%s' % br, 'fredge%s' % fr, c, _macro_for('x', c, +1))
    # X-parallel edges: ltedge (Hy,Hz) -> lbedge (Ly,Hz) -> rbedge (Ly,Lz) -> rtedge (Hy,Lz)
    for lt, lb, rb, rt in zip(ltedge, lbedge, rbedge, rtedge):
        for c in (1, 2, 3):
            _eq('%s-LTLB-U%d-%s' % (equation_prefix, c, lt),
                'ltedge%s' % lt, 'lbedge%s' % lb, c, _macro_for('y', c, -1))
            _eq('%s-LBRB-U%d-%s' % (equation_prefix, c, lb),
                'lbedge%s' % lb, 'rbedge%s' % rb, c, _macro_for('z', c, -1))
            _eq('%s-RBRT-U%d-%s' % (equation_prefix, c, rb),
                'rbedge%s' % rb, 'rtedge%s' % rt, c, _macro_for('y', c, +1))

    # ---- Corner walk c6 -> c2 -> c3 -> c4 -> c8 -> c5 -> c1 -> c7 ----
    # Each step: (slave_set, master_set, [(axis, direction), ...]).
    # direction=+1 if slave is on the LOW side of the changing axis (forward
    # transition); -1 if slave is on the HIGH side (backward transition).
    corner_steps = [
        ('c6', 'c2', [('y', +1)]),
        ('c2', 'c3', [('z', -1)]),
        ('c3', 'c4', [('x', +1)]),
        ('c4', 'c8', [('y', -1)]),
        ('c8', 'c5', [('z', +1)]),
        ('c5', 'c1', [('y', +1)]),
        ('c1', 'c7', [('x', -1), ('y', -1), ('z', -1)]),
    ]
    for step_idx, (a_set, b_set, axes_dirs) in enumerate(corner_steps, start=1):
        for c in (1, 2, 3):
            macro_terms = []
            for axis, direction in axes_dirs:
                macro_terms.extend(_macro_for(axis, c, direction))
            _eq('%s-Corner%d-U%d' % (equation_prefix, step_idx, c),
                a_set, b_set, c, macro_terms)

    print('Created %d strict point-to-point PBC equations (face/edge/corner).' % createdCount[0])


def build_multiaxial_nonmatching_equations_3d(modelName, a, instanceName, nodeLookup,
                                              frontbcxyz, backbcxyz, topbcxyz, botbcxyz,
                                              leftbcxyz, rightbcxyz, Max, May, Mnx, Mny,
                                              Mnz, Maz, tol, macro_map,
                                              equation_prefix='NearestPBC-MultiAxial'):
    modelObj = mdb.models[modelName]
    boundary_labels = set(frontbcxyz.keys()) | set(backbcxyz.keys()) | set(topbcxyz.keys()) | set(botbcxyz.keys()) | set(leftbcxyz.keys()) | set(rightbcxyz.keys())
    _pbc_create_single_node_sets(a, instanceName, sorted(boundary_labels))
    xMasterLabels = _pbc_filter_allowed_labels(_pbc_sorted_labels(backbcxyz), None)
    yMasterLabels = _pbc_filter_allowed_labels(_pbc_sorted_labels(botbcxyz), None)
    zMasterLabels = _pbc_filter_allowed_labels(_pbc_sorted_labels(rightbcxyz), None)
    xSlaveLabels = _pbc_sorted_labels(frontbcxyz)
    ySlaveLabels = []
    for label in _pbc_sorted_labels(topbcxyz):
        if abs(nodeLookup[label].coordinates[0] - Max) > tol:
            ySlaveLabels.append(label)
    zSlaveLabels = []
    for label in _pbc_sorted_labels(leftbcxyz):
        if abs(nodeLookup[label].coordinates[0] - Max) > tol and abs(nodeLookup[label].coordinates[1] - May) > tol:
            zSlaveLabels.append(label)
    createdCount = 0
    maxPairDistance = 0.0
    for label in xSlaveLabels:
        point = _pbc_reduced_coordinates(nodeLookup[label].coordinates, 0, 3)
        masterLabels, weights, pairDistance = _pbc_find_nearest_reduced_node(point, xMasterLabels, nodeLookup, 0, 3)
        if not masterLabels:
            print('Warning: no nearest master node found for X face node %s.' % label)
            continue
        if pairDistance > maxPairDistance:
            maxPairDistance = pairDistance
        for component in (1, 2, 3):
            equationName = '%s-X-U%s-%s' % (equation_prefix, component, label)
            _pbc_create_equation(modelObj, equationName, label, masterLabels, weights, component, macro_map.get(('x', component), []))
            createdCount += 1
    for label in ySlaveLabels:
        point = _pbc_reduced_coordinates(nodeLookup[label].coordinates, 1, 3)
        masterLabels, weights, pairDistance = _pbc_find_nearest_reduced_node(point, yMasterLabels, nodeLookup, 1, 3)
        if not masterLabels:
            print('Warning: no nearest master node found for Y face node %s.' % label)
            continue
        if pairDistance > maxPairDistance:
            maxPairDistance = pairDistance
        for component in (1, 2, 3):
            equationName = '%s-Y-U%s-%s' % (equation_prefix, component, label)
            _pbc_create_equation(modelObj, equationName, label, masterLabels, weights, component, macro_map.get(('y', component), []))
            createdCount += 1
    for label in zSlaveLabels:
        point = _pbc_reduced_coordinates(nodeLookup[label].coordinates, 2, 3)
        masterLabels, weights, pairDistance = _pbc_find_nearest_reduced_node(point, zMasterLabels, nodeLookup, 2, 3)
        if not masterLabels:
            print('Warning: no nearest master node found for Z face node %s.' % label)
            continue
        if pairDistance > maxPairDistance:
            maxPairDistance = pairDistance
        for component in (1, 2, 3):
            equationName = '%s-Z-U%s-%s' % (equation_prefix, component, label)
            _pbc_create_equation(modelObj, equationName, label, masterLabels, weights, component, macro_map.get(('z', component), []))
            createdCount += 1
    print("Created {} nearest-node multiaxial periodic equations. Max reduced mismatch = {}".format(createdCount, maxPairDistance))

def extract_reference_point_results(odb, step_name, frame_number=None, rve_dimensions=None):
    
    rp_results = []
    
    try:
        # check whether the step exists
        if step_name not in odb.steps.keys():
            available_steps = odb.steps.keys()
            print("WARNING: Step '{}' not found in ODB".format(step_name))
            print("Available steps: {}".format(available_steps))
            if len(available_steps) == 0:
                print("ERROR: No steps available in ODB")
                return []
            # use the first available step
            step_name = available_steps[0]
        
        step = odb.steps[step_name]
        
        # check whether frame data exists
        if len(step.frames) == 0:
            print("WARNING: No frames available in step '{}'".format(step_name))
            return []
        
        
        L = rve_dimensions['L']
        H = rve_dimensions['H']
        W = rve_dimensions['W']
        
        area_x = H * W 
        area_y = L * W 
        area_z = L * H 
        
        # determine which frames to process
        if frame_number is not None:
            # check whether the requested frame exists
            if frame_number < 0:
                frame_number = len(step.frames) + frame_number
            if frame_number >= len(step.frames):
                print("WARNING: Requested frame {} not available, using last frame {}".format(
                    frame_number, len(step.frames)-1))
                frame_number = len(step.frames) - 1
            frames_to_process = [step.frames[frame_number]]
            frame_indices = [frame_number]
        else:
            frames_to_process = step.frames
            frame_indices = range(len(step.frames))
        
        # find the active reference points
        active_reference_points = []
        for rp_name in ['RP1', 'RP2', 'RP3', 'RP4', 'RP5', 'RP6']:
            if rp_name in odb.rootAssembly.nodeSets.keys():
                rp_set = odb.rootAssembly.nodeSets[rp_name]
                active_reference_points.append((rp_name, rp_set))
        
        
        # extract data for each frame
        for frame_idx, frame in zip(frame_indices, frames_to_process):
            try:
                # get time / increment info
                try:
                    time_value = frame.frameValue
                    increment = frame.incrementNumber
                except:
                    time_value = float(frame_idx)
                    increment = frame_idx
                
                # process each active reference point
                for rp_name, rp_set in active_reference_points:
                    result_dict = {
                        'Frame': frame_idx,
                        'Time': time_value,
                        'Increment': increment,
                        'Reference_Point': rp_name
                    }
                    
                    # extract displacement (with error handling)
                    u1, u2, u3 = 0.0, 0.0, 0.0
                    if 'U' in frame.fieldOutputs:
                        try:
                            disp_field = frame.fieldOutputs['U']
                            disp_data = disp_field.getSubset(region=rp_set)
                            if disp_data.values:
                                disp_value = disp_data.values[0]
                                u1 = disp_value.data[0] if len(disp_value.data) > 0 else 0.0
                                u2 = disp_value.data[1] if len(disp_value.data) > 1 else 0.0
                                u3 = disp_value.data[2] if len(disp_value.data) > 2 else 0.0
                        except Exception as e:
                            print("WARNING: Failed to extract U for {} at frame {}: {}".format(
                                rp_name, frame_idx, str(e)))
                    
                    result_dict.update({'U1': u1, 'U2': u2, 'U3': u3})
                    
                    # extract reaction force (with error handling)
                    rf1, rf2, rf3 = 0.0, 0.0, 0.0
                    if 'RF' in frame.fieldOutputs:
                        try:
                            rf_field = frame.fieldOutputs['RF']
                            rf_data = rf_field.getSubset(region=rp_set)
                            if rf_data.values:
                                rf_value = rf_data.values[0]
                                rf1 = rf_value.data[0] if len(rf_value.data) > 0 else 0.0
                                rf2 = rf_value.data[1] if len(rf_value.data) > 1 else 0.0
                                rf3 = rf_value.data[2] if len(rf_value.data) > 2 else 0.0
                        except Exception as e:
                            print("WARNING: Failed to extract RF for {} at frame {}: {}".format(
                                rp_name, frame_idx, str(e)))
                    
                    result_dict.update({'RF1': rf1, 'RF2': rf2, 'RF3': rf3})
                    
                    # compute stress/strain (original logic kept)
                    stress_11 = stress_22 = stress_33 = 0.0
                    strain_11 = strain_22 = strain_33 = 0.0
                    
                    if rp_name == 'RP1':
                        if abs(u1) > 1e-12 or abs(rf1) > 1e-12:
                            stress_11 = rf1 / area_x
                            strain_11 = u1 / L
                    elif rp_name == 'RP2':
                        if abs(u2) > 1e-12 or abs(rf2) > 1e-12:    
                            stress_22 = rf2 / area_y
                            strain_22 = u2 / H
                    elif rp_name == 'RP3':
                        if abs(u3) > 1e-12 or abs(rf3) > 1e-12:    
                            stress_33 = rf3 / area_z
                            strain_33 = u3 / W
                    
                    result_dict.update({
                        'Stress_11': stress_11, 'Stress_22': stress_22, 'Stress_33': stress_33,
                        'Strain_11': strain_11, 'Strain_22': strain_22, 'Strain_33': strain_33
                    })
                    
                    # compute shear stress/strain
                    if rp_name == 'RP4':
                        tau_12 = (abs(rf1) / area_y + abs(rf2) / area_x) / 2 
                        gamma_12 = (u1/H + u2/L) / 2
                        result_dict.update({'Shear_Stress_12': tau_12, 'Shear_Strain_12': gamma_12})
                    elif rp_name == 'RP5':
                        tau_13 = (abs(rf1) / area_z + abs(rf3) / area_x) / 2
                        gamma_13 = (u1/W + u3/L) / 2
                        result_dict.update({'Shear_Stress_13': tau_13, 'Shear_Strain_13': gamma_13})
                    elif rp_name == 'RP6':
                        tau_23 = (abs(rf2) / area_z + abs(rf3) / area_y) / 2
                        gamma_23 = (u2/W + u3/H) / 2
                        result_dict.update({'Shear_Stress_23': tau_23, 'Shear_Strain_23': gamma_23})
                    
                    # add default shear values
                    if 'Shear_Stress_12' not in result_dict:
                        result_dict.update({'Shear_Stress_12': 0.0, 'Shear_Strain_12': 0.0})
                    if 'Shear_Stress_13' not in result_dict:
                        result_dict.update({'Shear_Stress_13': 0.0, 'Shear_Strain_13': 0.0})
                    if 'Shear_Stress_23' not in result_dict:
                        result_dict.update({'Shear_Stress_23': 0.0, 'Shear_Strain_23': 0.0})
                    
                    rp_results.append(result_dict)
            
            except Exception as e:
                print("WARNING: Error processing frame {}: {}".format(frame_idx, str(e)))
                continue
        
        return rp_results
        
    except Exception as e:
        print("ERROR extracting reference point results: {}".format(str(e)))
        import traceback
        traceback.print_exc()
        return []

def extract_reference_point_results_single_frame(odb, step_name, frame_number, rve_dimensions=None):
    return extract_reference_point_results(odb, step_name, frame_number, rve_dimensions)


def extract_reference_point_time_history(odb, step_name, rve_dimensions=None):
    return extract_reference_point_results(odb, step_name, frame_number=None, rve_dimensions=rve_dimensions)


def save_reference_point_time_history(rp_results, output_dir, modelName, applied_strains=None, loading_label='Analysis'):
    import os
    saved_files = []
    # Group data by reference point
    rp_data_by_point = {}
    for result in rp_results:
        rp_name = result['Reference_Point']
        if rp_name not in rp_data_by_point:
            rp_data_by_point[rp_name] = []
        rp_data_by_point[rp_name].append(result)
    
    # 1. Save combined reference point file (all RPs in one file) - basic data only
    combined_fieldnames = ['Frame', 'Time', 'Increment', 'Reference_Point', 'U1', 'U2', 'U3', 'RF1', 'RF2', 'RF3',
                          'Stress_11', 'Stress_22', 'Stress_33', 'Strain_11', 'Strain_22', 'Strain_33',
                          'Shear_Stress_12', 'Shear_Strain_12', 'Shear_Stress_13', 'Shear_Strain_13',
                          'Shear_Stress_23', 'Shear_Strain_23']  # Removed individual Mises values
    
    combined_filename = os.path.join(output_dir, '{}_all_RP_history_{}.csv'.format(
        modelName, sanitize_loading_label(loading_label)))
    csvfile, writer = create_csv_writer(combined_filename, combined_fieldnames)
    if writer:
        for result in rp_results:
            row_data = {}
            for key in combined_fieldnames:
                row_data[key] = result.get(key, 0.0)
            writer.writerow(row_data)
        close_csv_file(csvfile)
        saved_files.append(combined_filename)
    
    # 2. Calculate and save macroscopic stress-strain tensor with proper von Mises values
    macroscopic_data = calculate_macroscopic_stress_strain(rp_results)
    
    if macroscopic_data:
        # Save macroscopic stress-strain file
        macro_filename = os.path.join(output_dir, '{}_macroscopic_stress_strain_{}.csv'.format(
            modelName, sanitize_loading_label(loading_label)))
        macro_fieldnames = ['Frame', 'Time', 'Increment',
                           'Sigma_11', 'Sigma_22', 'Sigma_33', 'Tau_12', 'Tau_13', 'Tau_23',
                           'Epsilon_11', 'Epsilon_22', 'Epsilon_33', '2*Gamma_12', '2*Gamma_13', '2*Gamma_23',
                           'Von_Mises_Stress', 'Von_Mises_Strain', 'Hydrostatic_Pressure', 'Stress_Triaxiality',
                           'Volumetric_Strain', 'Equivalent_Strain_Rate']
        
        csvfile, writer = create_csv_writer(macro_filename, macro_fieldnames)
        if writer:
            for result in macroscopic_data:
                row_data = {}
                for key in macro_fieldnames:
                    row_data[key] = result.get(key, 0.0)
                writer.writerow(row_data)
            close_csv_file(csvfile)
            saved_files.append(macro_filename)
            print("  Macroscopic stress-strain: {} ({} records)".format(os.path.basename(macro_filename), len(macroscopic_data)))
    
    # 3. Create loading-specific stress-strain curve files based on applied strains
    if applied_strains and macroscopic_data:
        epsilon_x = applied_strains.get('epsilon_x', 0)
        epsilon_y = applied_strains.get('epsilon_y', 0) 
        epsilon_z = applied_strains.get('epsilon_z', 0)
        gamma_xy = applied_strains.get('gamma_xy', 0)
        gamma_yz = applied_strains.get('gamma_yz', 0)
        gamma_zx = applied_strains.get('gamma_zx', 0)
        
        # Identify primary loading direction
        loading_cases = []
        
        # Single axis loading cases
        if abs(epsilon_x) > 1e-12 and abs(epsilon_y) < 1e-12 and abs(epsilon_z) < 1e-12:
            loading_cases.append(('X_uniaxial', 'RP1', 'Stress_11', 'Strain_11', epsilon_x))
        elif abs(epsilon_y) > 1e-12 and abs(epsilon_x) < 1e-12 and abs(epsilon_z) < 1e-12:
            loading_cases.append(('Y_uniaxial', 'RP2', 'Stress_22', 'Strain_22', epsilon_y))
        elif abs(epsilon_z) > 1e-12 and abs(epsilon_x) < 1e-12 and abs(epsilon_y) < 1e-12:
            loading_cases.append(('Z_uniaxial', 'RP3', 'Stress_33', 'Strain_33', epsilon_z))
        
        # Biaxial loading cases
        elif abs(epsilon_x) > 1e-12 and abs(epsilon_y) > 1e-12 and abs(epsilon_z) < 1e-12:
            loading_cases.append(('XY_biaxial', 'RP1', 'Stress_11', 'Strain_11', epsilon_x))
            loading_cases.append(('XY_biaxial', 'RP2', 'Stress_22', 'Strain_22', epsilon_y))
        elif abs(epsilon_x) > 1e-12 and abs(epsilon_z) > 1e-12 and abs(epsilon_y) < 1e-12:
            loading_cases.append(('XZ_biaxial', 'RP1', 'Stress_11', 'Strain_11', epsilon_x))
            loading_cases.append(('XZ_biaxial', 'RP3', 'Stress_33', 'Strain_33', epsilon_z))
        elif abs(epsilon_y) > 1e-12 and abs(epsilon_z) > 1e-12 and abs(epsilon_x) < 1e-12:
            loading_cases.append(('YZ_biaxial', 'RP2', 'Stress_22', 'Strain_22', epsilon_y))
            loading_cases.append(('YZ_biaxial', 'RP3', 'Stress_33', 'Strain_33', epsilon_z))
        
        # Pure shear cases
        elif abs(gamma_xy) > 1e-12 and abs(gamma_yz) < 1e-12 and abs(gamma_zx) < 1e-12:
            loading_cases.append(('XY_shear', 'RP4', 'Shear_Stress_12', 'Shear_Strain_12', gamma_xy))
        elif abs(gamma_yz) > 1e-12 and abs(gamma_xy) < 1e-12 and abs(gamma_zx) < 1e-12:
            loading_cases.append(('YZ_shear', 'RP6', 'Shear_Stress_23', 'Shear_Strain_23', gamma_yz))
        elif abs(gamma_zx) > 1e-12 and abs(gamma_xy) < 1e-12 and abs(gamma_yz) < 1e-12:
            loading_cases.append(('ZX_shear', 'RP5', 'Shear_Stress_13', 'Shear_Strain_13', gamma_zx))
        
        # Multiaxial cases (all non-zero)
        else:
            loading_cases.append(('Multiaxial', 'RP1', 'Stress_11', 'Strain_11', epsilon_x))
            if abs(epsilon_y) > 1e-12:
                loading_cases.append(('Multiaxial', 'RP2', 'Stress_22', 'Strain_22', epsilon_y))
            if abs(epsilon_z) > 1e-12:
                loading_cases.append(('Multiaxial', 'RP3', 'Stress_33', 'Strain_33', epsilon_z))
    
    return saved_files


def extract_element_results(odb, step_name, frame_number, instance_name):
    """Extract element stress, strain, and Mises stress results"""
    
    element_results = []
    
    try:
        frame = odb.steps[step_name].frames[frame_number]
        instance = odb.rootAssembly.instances[instance_name]
        
        # Extract stress data
        stress_data = None
        if 'S' in frame.fieldOutputs:
            stress_field = frame.fieldOutputs['S']
            stress_data = stress_field.getSubset(region=instance)
        
        # Extract strain data
        strain_data = None
        if 'E' in frame.fieldOutputs:
            strain_field = frame.fieldOutputs['E']
            strain_data = strain_field.getSubset(region=instance)
        elif 'LE' in frame.fieldOutputs:
            strain_field = frame.fieldOutputs['LE']
            strain_data = strain_field.getSubset(region=instance)
        
        # Extract equivalent stress (Mises)
        mises_data = None
        if 'MISES' in frame.fieldOutputs:
            mises_field = frame.fieldOutputs['MISES']
            mises_data = mises_field.getSubset(region=instance)
        
        # Extract plastic strain
        pe_data = None
        if 'PE' in frame.fieldOutputs:
            pe_field = frame.fieldOutputs['PE']
            pe_data = pe_field.getSubset(region=instance)
        
        # Extract strain energy density
        sdeg_data = None
        if 'SENER' in frame.fieldOutputs:
            sdeg_field = frame.fieldOutputs['SENER']
            sdeg_data = sdeg_field.getSubset(region=instance)
            
        # Extract element status
        status_data = None
        if 'STATUS' in frame.fieldOutputs:
            status_field = frame.fieldOutputs['STATUS']
            status_data = status_field.getSubset(region=instance)
            
        # Process stress data
        if stress_data:
            for stress_value in stress_data.values:
                element_label = stress_value.elementLabel
                integration_point = stress_value.integrationPoint if hasattr(stress_value, 'integrationPoint') else 1
                
                result_dict = {
                    'Element_Label': element_label,
                    'Integration_Point': integration_point,
                    'S11': stress_value.data[0] if len(stress_value.data) > 0 else 0.0,
                    'S22': stress_value.data[1] if len(stress_value.data) > 1 else 0.0,
                    'S33': stress_value.data[2] if len(stress_value.data) > 2 else 0.0,
                    'S12': stress_value.data[3] if len(stress_value.data) > 3 else 0.0,
                    'S13': stress_value.data[4] if len(stress_value.data) > 4 else 0.0,
                    'S23': stress_value.data[5] if len(stress_value.data) > 5 else 0.0
                }
                
                # Add strain data
                if strain_data:
                    strain_value = None
                    for strain in strain_data.values:
                        if (strain.elementLabel == element_label and 
                            getattr(strain, 'integrationPoint', 1) == integration_point):
                            strain_value = strain
                            break
                    
                    if strain_value:
                        result_dict.update({
                            'E11': strain_value.data[0] if len(strain_value.data) > 0 else 0.0,
                            'E22': strain_value.data[1] if len(strain_value.data) > 1 else 0.0,
                            'E33': strain_value.data[2] if len(strain_value.data) > 2 else 0.0,
                            'E12': strain_value.data[3] if len(strain_value.data) > 3 else 0.0,
                            'E13': strain_value.data[4] if len(strain_value.data) > 4 else 0.0,
                            'E23': strain_value.data[5] if len(strain_value.data) > 5 else 0.0
                        })
                    else:
                        result_dict.update({
                            'E11': 0.0, 'E22': 0.0, 'E33': 0.0,
                            'E12': 0.0, 'E13': 0.0, 'E23': 0.0
                        })
                else:
                    result_dict.update({
                        'E11': 0.0, 'E22': 0.0, 'E33': 0.0,
                        'E12': 0.0, 'E13': 0.0, 'E23': 0.0
                    })
                
                # Add Mises stress
                if mises_data:
                    mises_value = None
                    for mises in mises_data.values:
                        if (mises.elementLabel == element_label and 
                            getattr(mises, 'integrationPoint', 1) == integration_point):
                            mises_value = mises
                            break
                    
                    if mises_value:
                        result_dict['MISES'] = mises_value.data
                    else:
                        result_dict['MISES'] = 0.0
                else:
                    result_dict['MISES'] = 0.0
                
                element_results.append(result_dict)
                
                # Add plastic strain
                if pe_data:
                    pe_value = None
                    for pe in pe_data.values:
                        if (pe.elementLabel == element_label and 
                            getattr(pe, 'integrationPoint', 1) == integration_point):
                            pe_value = pe
                            break
                    if pe_value:
                        result_dict.update({
                            'PE11': pe_value.data[0] if len(pe_value.data) > 0 else 0.0,
                            'PE22': pe_value.data[1] if len(pe_value.data) > 1 else 0.0,
                            'PE33': pe_value.data[2] if len(pe_value.data) > 2 else 0.0,
                            'PE12': pe_value.data[3] if len(pe_value.data) > 3 else 0.0
                        })
                    else:
                        result_dict.update({'PE11': 0.0, 'PE22': 0.0, 'PE33': 0.0, 'PE12': 0.0})
                else:
                    result_dict.update({'PE11': 0.0, 'PE22': 0.0, 'PE33': 0.0, 'PE12': 0.0})
                
                # Add strain energy density
                if sdeg_data:
                    sdeg_value = None
                    for sdeg in sdeg_data.values:
                        if (sdeg.elementLabel == element_label and 
                            getattr(sdeg, 'integrationPoint', 1) == integration_point):
                            sdeg_value = sdeg
                            break
                    result_dict['SDEG'] = sdeg_value.data if sdeg_value else 0.0
                else:
                    result_dict['SDEG'] = 0.0
                
                # Add element status
                if status_data:
                    status_value = None
                    for status in status_data.values:
                        if status.elementLabel == element_label:
                            status_value = status
                            break
                    result_dict['STATUS'] = status_value.data if status_value else 0.0
                else:
                    result_dict['STATUS'] = 0.0
        return element_results
        
    except Exception as e:
        print("Error extracting element results: {}".format(str(e)))
        return []

def calculate_macroscopic_stress_strain(rp_results):
    macroscopic_results = []
    
    if not rp_results:
        return macroscopic_results
    
    # Group data by frame number
    frame_data = {}
    for result in rp_results:
        frame = result.get('Frame', 0)
        if frame not in frame_data:
            frame_data[frame] = {}
        rp_name = result['Reference_Point']
        frame_data[frame][rp_name] = result
    
    # Process each frame
    for frame in sorted(frame_data.keys()):
        frame_rps = frame_data[frame]
        
        # Initialize macroscopic stress-strain components
        macro_result = {'Frame': frame,'Time': 0.0,'Increment': frame}
        
        # Get time from any available RP (should be same for all RPs in same frame)
        for rp_data in frame_rps.values():
            macro_result['Time'] = rp_data.get('Time', 0.0)
            macro_result['Increment'] = rp_data.get('Increment', frame)
            break
        
        sigma_11 = frame_rps.get('RP1', {}).get('Stress_11', 0.0)  # X-direction from RP1
        sigma_22 = frame_rps.get('RP2', {}).get('Stress_22', 0.0)  # Y-direction from RP2
        sigma_33 = frame_rps.get('RP3', {}).get('Stress_33', 0.0)  # Z-direction from RP3
        tau_12 = frame_rps.get('RP4', {}).get('Shear_Stress_12', 0.0)  # XY shear from RP4
        tau_13 = frame_rps.get('RP5', {}).get('Shear_Stress_13', 0.0)  # XZ shear from RP5
        tau_23 = frame_rps.get('RP6', {}).get('Shear_Stress_23', 0.0)  # YZ shear from RP6
        
        epsilon_11 = frame_rps.get('RP1', {}).get('Strain_11', 0.0)  # X-direction from RP1
        epsilon_22 = frame_rps.get('RP2', {}).get('Strain_22', 0.0)  # Y-direction from RP2
        epsilon_33 = frame_rps.get('RP3', {}).get('Strain_33', 0.0)  # Z-direction from RP3
        gamma_12 = frame_rps.get('RP4', {}).get('Shear_Strain_12', 0.0)  # XY shear from RP4
        gamma_13 = frame_rps.get('RP5', {}).get('Shear_Strain_13', 0.0)  # XZ shear from RP5
        gamma_23 = frame_rps.get('RP6', {}).get('Shear_Strain_23', 0.0)  # YZ shear from RP6
        
        # Store macroscopic stress-strain components
        macro_result.update({'Sigma_11': sigma_11,'Sigma_22': sigma_22,'Sigma_33': sigma_33,
                             'Tau_12': tau_12,'Tau_13': tau_13,'Tau_23': tau_23,
                             'Epsilon_11': epsilon_11,'Epsilon_22': epsilon_22,'Epsilon_33': epsilon_33,
                             '2*Gamma_12': gamma_12*2,'2*Gamma_13': gamma_13*2,'2*Gamma_23': gamma_23*2})
        
        # Calculate hydrostatic pressure (mean stress)
        # σ_h = (σ_11 + σ_22 + σ_33) / 3
        hydrostatic_pressure = (sigma_11 + sigma_22 + sigma_33) / 3.0
        macro_result['Hydrostatic_Pressure'] = hydrostatic_pressure
        
        # Calculate von Mises equivalent stress
        # σ_eq = sqrt(0.5*[(σ11-σ22)² + (σ22-σ33)² + (σ33-σ11)²] + 3*(tau12² + tau13² + tau23²))
        deviatoric_part = 0.5 * ((sigma_11 - sigma_22)**2 + (sigma_22 - sigma_33)**2 + (sigma_33 - sigma_11)**2)
        shear_part = 3.0 * (tau_12**2 + tau_13**2 + tau_23**2)
        von_mises_stress = (deviatoric_part + shear_part)**0.5
        macro_result['Von_Mises_Stress'] = von_mises_stress
        
        # Calculate stress triaxiality
        # T = σ_h / σ_eq (hydrostatic stress / von Mises stress)
        if von_mises_stress > 1e-12:
            stress_triaxiality = hydrostatic_pressure / von_mises_stress
        else:
            stress_triaxiality = 0.0
        macro_result['Stress_Triaxiality'] = stress_triaxiality
        
        # Calculate von Mises equivalent strain
        # epsilon_eq = sqrt((2/3)*[(epsilon11-epsilon22)² + (epsilon22-epsilon33)² + (epsilon33-epsilon11)²] + (1/3)*(gamma12² + gamma13² + gamma23²))
        strain_deviatoric_part = (2.0/3.0) * ((epsilon_11 - epsilon_22)**2 + (epsilon_22 - epsilon_33)**2 + (epsilon_33 - epsilon_11)**2)
        strain_shear_part = (1.0/3.0) * (gamma_12**2 + gamma_13**2 + gamma_23**2)
        von_mises_strain = (strain_deviatoric_part + strain_shear_part)**0.5
        macro_result['Von_Mises_Strain'] = von_mises_strain
        
        # Calculate volumetric strain
        volumetric_strain = epsilon_11 + epsilon_22 + epsilon_33
        macro_result['Volumetric_Strain'] = volumetric_strain
        
        # Calculate equivalent plastic strain rate (if time data available)
        if len(macroscopic_results) > 0 and macro_result['Time'] > macroscopic_results[-1]['Time']:
            dt = macro_result['Time'] - macroscopic_results[-1]['Time']
            if dt > 1e-12:
                d_von_mises_strain = von_mises_strain - macroscopic_results[-1]['Von_Mises_Strain']
                equivalent_strain_rate = d_von_mises_strain / dt
                macro_result['Equivalent_Strain_Rate'] = equivalent_strain_rate
            else:
                macro_result['Equivalent_Strain_Rate'] = 0.0
        else:
            macro_result['Equivalent_Strain_Rate'] = 0.0
        
        macroscopic_results.append(macro_result)
        
    return macroscopic_results

def calculate_volume_averages(element_results):
    """Calculate volume-averaged stress and strain values"""
    
    if not element_results:
        return {}
    
    try:
        # Calculate average stress and strain
        avg_stress = {'S11': 0.0, 'S22': 0.0, 'S33': 0.0,'S12': 0.0, 'S13': 0.0, 'S23': 0.0}
        avg_strain = {'E11': 0.0, 'E22': 0.0, 'E33': 0.0,'E12': 0.0, 'E13': 0.0, 'E23': 0.0}
        avg_mises = 0.0
        
        n_elements = len(element_results)
        
        for result in element_results:
            for key in avg_stress.keys():
                avg_stress[key] += result.get(key, 0.0)
            for key in avg_strain.keys():
                avg_strain[key] += result.get(key, 0.0)
            avg_mises += result.get('MISES', 0.0)
        
        # Calculate averages
        for key in avg_stress.keys():
            avg_stress[key] /= n_elements
        for key in avg_strain.keys():
            avg_strain[key] /= n_elements
        avg_mises /= n_elements
        
        # Combine results
        volume_averages = {}
        volume_averages.update(avg_stress)
        volume_averages.update(avg_strain)
        volume_averages['MISES_avg'] = avg_mises
        
        return volume_averages
        
    except Exception as e:
        print("Error calculating volume averages: {}".format(str(e)))
        return {}

# ----------------------------------------------------------------------------
# Curve fitting is not part of this plugin.  The functions below only write the
# concentration_history CSV and its summary; UMAT parameters are fitted from
# that CSV by an external script.
# ----------------------------------------------------------------------------


def _wquantile(pairs, q):
    """Volume-weighted quantile of (value, weight) pairs at level q in [0,1].

    Hazen-type: cumulative weight at the CENTER of each sorted sample's weight
    band, linearly interpolated.  IVOL weighting makes the high quantile robust
    to mesh refinement (refining near a fibre splits one big IP volume into many
    small ones of the SAME total weight, leaving the quantile unchanged), unlike
    a single max (singularity-/mesh-dominated) or a count-based percentile
    (over-samples the densely meshed hot-spot region).  Returns 0.0 if empty."""
    if not pairs:
        return 0.0
    sp = sorted(pairs, key=lambda t: t[0])
    wtot = 0.0
    for _, w in sp:
        wtot += w
    if wtot <= 0.0:
        return sp[-1][0]
    F = []
    run = 0.0
    for v, w in sp:
        F.append((run + 0.5 * w) / wtot)
        run += w
    if q <= F[0]:
        return sp[0][0]
    if q >= F[-1]:
        return sp[-1][0]
    for i in range(1, len(sp)):
        if q <= F[i]:
            f0 = F[i - 1]; f1 = F[i]
            v0 = sp[i - 1][0]; v1 = sp[i][0]
            return v0 + (v1 - v0) * (q - f0) / (f1 - f0) if f1 > f0 else v1
    return sp[-1][0]


def extract_concentration_factors(odb, step_name, instance_name, rp_history,
                                  output_dir, output_model_name,
                                  loading_label='Analysis',
                                  matrix_set='Set-Matrix'):
    """Physically-sourced stress-concentration factors for the bridging+SCF
    UMAT -- read directly from the RVE field so SCFt / yield-concentration come
    from physics, not guessing.

    Per frame, over the MATRIX element subset (volume-weighted by IVOL):
      SCF_loc  = <sig_L>_mtx / Sigma_L_macro    (Mori-Tanaka localization, ~0.81)
      SCFt     = max(sig_L)_mtx / <sig_L>_mtx   (inter-fibre ligament peak/avg)
      SCFt_tot = max(sig_L)_mtx / Sigma_L_macro (= SCF_loc * SCFt)
      k_yield  = max(Mises)_mtx / <Mises>_mtx   (local/avg = the UMAT 1.15 factor)
    L = loading direction = dominant macro normal component (auto-detected).
    Summary reports the three physical instants: elastic localization
    (mean SCF_loc pre-yield), matrix-yield onset (first PEEQ>0 -> k_yield), and
    damage/debond onset (max interface traction CSTRESS if present, else macro-
    stress peak -> SCFt).  These numbers feed the UMAT card directly.
    """
    try:
        step = odb.steps[step_name]
        instance = odb.rootAssembly.instances[instance_name]
    except Exception as e:
        print("  concentration: cannot access step/instance: %s" % str(e))
        return [], {}

    # ---- region selection: case-insensitive + void-aware --------------------
    # ODB set names are stored UPPERCASE, so the old exact-case lookup of
    # 'Set-Matrix' silently fell back to the whole instance (fibre included).
    # Match case-insensitively here.  For RVEs with inserted voids the builder
    # creates, within the matrix phase:
    #   Set-Matrix / Set-Matrix-element : matrix INCLUDING the void 'air' elems
    #   Set-Matrix-element-novoid       : SOLID load-bearing matrix (voids out)
    #   Set-void                        : the void 'air' (near-zero stress) elems
    # The UMAT models the SOLID matrix point, so the concentration factors must
    # be taken over the void-FREE solid matrix: the near-zero 'air' elements
    # would otherwise drag the average down and spuriously inflate k_yield/SCFt.
    # The void's stress-raising effect is still captured, through the elevated
    # field in the SOLID matrix elements surrounding each void.
    def _eset_pools():
        # ODB set names are stored UPPERCASE and may live on ANY instance or on
        # the rootAssembly -- search them all (the given instance first).
        pools = [instance.elementSets]
        try:
            for _in in odb.rootAssembly.instances.keys():
                src = odb.rootAssembly.instances[_in].elementSets
                if src not in pools:
                    pools.append(src)
        except Exception:
            pass
        try:
            pools.append(odb.rootAssembly.elementSets)
        except Exception:
            pass
        return pools

    def _find_eset(name):
        wl = name.strip().upper()
        for src in _eset_pools():
            try:
                for k in src.keys():
                    if k.upper() == wl:
                        return src[k]
            except Exception:
                pass
        return None

    def _find_eset_fuzzy(must_have, must_not):
        for src in _eset_pools():
            try:
                for k in src.keys():
                    u = k.upper()
                    if all([t in u for t in must_have]) and \
                            not any([t in u for t in must_not]):
                        return src[k], k
            except Exception:
                pass
        return None, None

    void_reg = _find_eset('Set-void')
    has_void = void_reg is not None
    if has_void:
        prefer = ['Set-Matrix-element-novoid', 'Set-Matrix-element', matrix_set, 'Set-Matrix']
    else:
        prefer = [matrix_set, 'Set-Matrix-element', 'Set-Matrix']
    mreg, mreg_name = None, None
    for _cand in prefer:
        mreg = _find_eset(_cand)
        if mreg is not None:
            mreg_name = _cand
            break
    if mreg is None:
        print("  concentration: no matrix set found (tried %s); using whole instance."
              % ', '.join(prefer))
        mreg, mreg_name = instance, '<whole-instance>'
    if has_void:
        print("  concentration: VOID model -> SCF over SOLID matrix '%s' (voids excluded)." % mreg_name)

    # cohesive INTERFACE element set.  With cohesive ELEMENTS (COH3D8) the
    # interface normal traction is the element stress S (S33 ~ normal), NOT the
    # contact CSTRESS field (which is empty for cohesive elements).  XKINT =
    # max(iface Tn)/<sig_L>_mtx is therefore read from S over this set.
    ireg, ireg_name = None, None
    for _icand in ('Set-Interface-FiberMatrix', 'Set-Interface',
                   'Set-Cohesive', 'Set-CZM', 'Set-Coh'):
        ireg = _find_eset(_icand)
        if ireg is not None:
            ireg_name = _icand
            break
    if ireg is None:
        ireg, ireg_name = _find_eset_fuzzy(['INTERFACE'], ['STRAIGHT'])
    if ireg is None:
        ireg, ireg_name = _find_eset_fuzzy(['COH'], ['STRAIGHT'])
    if ireg is not None:
        print("  concentration: cohesive interface set '%s' -> XKINT from S." % ireg_name)
    else:
        print("  concentration: no cohesive interface set -> XKINT from CSTRESS / off.")

    # matrix porosity = void / (void + solid), from IVOL of the first frame with it
    void_vf = 0.0
    if has_void:
        try:
            for _fr in range(len(step.frames)):
                _fo = step.frames[_fr].fieldOutputs
                if 'IVOL' not in _fo:
                    continue
                _vv = sum([v.data for v in _fo['IVOL'].getSubset(region=void_reg).values])
                _vm = sum([v.data for v in _fo['IVOL'].getSubset(region=mreg).values])
                if (_vv + _vm) > 0.0:
                    void_vf = _vv / (_vv + _vm)
                break
        except Exception:
            void_vf = 0.0

    macro = calculate_macroscopic_stress_strain(rp_history) if rp_history else []
    macro_by_frame = {}
    for m in macro:
        macro_by_frame[m.get('Frame', 0)] = m

    rows = []
    nfr = len(step.frames)
    for fr in range(nfr):
        frame = step.frames[fr]
        fo = frame.fieldOutputs
        if 'S' not in fo:
            continue
        try:
            Ssub = fo['S'].getSubset(region=mreg)
        except Exception:
            continue
        vmap = {}
        if 'IVOL' in fo:
            try:
                for v in fo['IVOL'].getSubset(region=mreg).values:
                    vmap[(v.elementLabel, getattr(v, 'integrationPoint', 1))] = v.data
            except Exception:
                vmap = {}
        sumw = 0.0
        s_avg = [0.0, 0.0, 0.0]
        s_pk = [-1.0e30, -1.0e30, -1.0e30]
        mis_sum = 0.0
        mis_pk = 0.0
        mis_sq_sum = 0.0          # IVOL-weighted Mises^2 (second moment)
        vm_pairs = []             # (Mises, IVOL weight) for the volume-weighted quantile
        for sv in Ssub.values:
            d = sv.data
            w = vmap.get((sv.elementLabel, getattr(sv, 'integrationPoint', 1)), 1.0)
            sumw += w
            s11 = d[0] if len(d) > 0 else 0.0
            s22 = d[1] if len(d) > 1 else 0.0
            s33 = d[2] if len(d) > 2 else 0.0
            s12 = d[3] if len(d) > 3 else 0.0
            s13 = d[4] if len(d) > 4 else 0.0
            s23 = d[5] if len(d) > 5 else 0.0
            comp = (s11, s22, s33)
            for k in range(3):
                s_avg[k] += w * comp[k]
                if comp[k] > s_pk[k]:
                    s_pk[k] = comp[k]
            vm = 0.5 * ((s11 - s22) ** 2 + (s22 - s33) ** 2 + (s33 - s11) ** 2)
            vm = (vm + 3.0 * (s12 * s12 + s13 * s13 + s23 * s23)) ** 0.5
            mis_sum += w * vm
            mis_sq_sum += w * vm * vm
            vm_pairs.append((vm, w))
            if vm > mis_pk:
                mis_pk = vm
        if sumw <= 0.0:
            continue
        for k in range(3):
            s_avg[k] /= sumw
        mis_avg = mis_sum / sumw
        # Volume-weighted high quantiles of the matrix Mises field: the mean
        # field underestimates the local yield onset and the single maximum is
        # mesh-dominated, so the P90-P95 band (the most-loaded 5-10% of the
        # matrix volume) is used as the mesh-robust yield-onset measure.
        mis_q90 = _wquantile(vm_pairs, 0.90)
        mis_q95 = _wquantile(vm_pairs, 0.95)
        # Second moment (RMS) of the matrix Mises stress: the Doghri/MFH
        # intra-phase heterogeneity ratio sqrt(<Mises^2>)/<Mises>.
        mis_2m = (mis_sq_sum / sumw) ** 0.5

        peeq_pk = 0.0
        if 'PEEQ' in fo:
            try:
                for pv in fo['PEEQ'].getSubset(region=mreg).values:
                    if pv.data > peeq_pk:
                        peeq_pk = pv.data
            except Exception:
                pass

        # Interface normal traction:
        #  cohesive ELEMENTS -> direct stress S over the interface set (the
        #    in-plane components are ~0 for traction-separation, so the max of
        #    the three direct components picks the normal traction regardless
        #    of which local axis Abaqus assigned to S33);
        #  cohesive CONTACT  -> fall back to CSTRESS.
        #   tn_pk  = maximum over the interface set (geometric hot spot)
        #   tn_avg = IVOL(area)-weighted average of the tensile traction; the
        #            area-averaged value is the whole-element debond driver
        #            from which XKINT is built.
        tn_pk = 0.0
        tn_sum = 0.0          # IVOL-weighted sum of tensile interface traction
        tn_w = 0.0            # accumulated IVOL weight
        if ireg is not None and 'S' in fo:
            ivmap = {}
            if 'IVOL' in fo:
                try:
                    for v in fo['IVOL'].getSubset(region=ireg).values:
                        ivmap[(v.elementLabel, getattr(v, 'integrationPoint', 1))] = v.data
                except Exception:
                    ivmap = {}
            try:
                for cv in fo['S'].getSubset(region=ireg).values:
                    cd = cv.data
                    cand = max([cd[j] for j in range(min(3, len(cd)))])
                    w = ivmap.get((cv.elementLabel, getattr(cv, 'integrationPoint', 1)), 1.0)
                    if cand > tn_pk:
                        tn_pk = cand
                    if cand > 0.0:
                        tn_sum += w * cand
                        tn_w += w
            except Exception:
                pass
        if tn_pk <= 0.0 and 'CSTRESS' in fo:
            try:
                for cv in fo['CSTRESS'].values:
                    cp = abs(cv.data[0]) if len(cv.data) > 0 else 0.0
                    if cp > tn_pk:
                        tn_pk = cp
                    if cp > 0.0:
                        tn_sum += cp
                        tn_w += 1.0
            except Exception:
                pass
        tn_avg = (tn_sum / tn_w) if tn_w > 0.0 else 0.0

        # cohesive (interface) debond: CSDMG = overall damage (>0 means the
        # interface has STARTED to debond); CSMAXSCRT/CSQUADSCRT = the damage-
        # initiation criterion (reaches 1.0 exactly at onset).  These mark the
        # physical slope-drop onset of the with-CZM (red) curve.
        csdmg_pk = 0.0
        csinit_pk = 0.0
        for _cv in ('CSDMG',):
            if _cv in fo:
                try:
                    for dv in fo[_cv].values:
                        if dv.data > csdmg_pk:
                            csdmg_pk = dv.data
                except Exception:
                    pass
        for _cv in ('CSMAXSCRT', 'CSQUADSCRT'):
            if _cv in fo:
                try:
                    for dv in fo[_cv].values:
                        if dv.data > csinit_pk:
                            csinit_pk = dv.data
                except Exception:
                    pass

        mrow = macro_by_frame.get(fr, {})
        rows.append({
            'Frame': fr,
            'Time': frame.frameValue,
            'Macro_S11': mrow.get('Sigma_11', 0.0),
            'Macro_S22': mrow.get('Sigma_22', 0.0),
            'Macro_S33': mrow.get('Sigma_33', 0.0),
            'Macro_E11': mrow.get('Epsilon_11', 0.0),
            'Macro_E22': mrow.get('Epsilon_22', 0.0),
            'Macro_E33': mrow.get('Epsilon_33', 0.0),
            'Mtx_S11_avg': s_avg[0], 'Mtx_S22_avg': s_avg[1], 'Mtx_S33_avg': s_avg[2],
            'Mtx_S11_pk': s_pk[0], 'Mtx_S22_pk': s_pk[1], 'Mtx_S33_pk': s_pk[2],
            'Mtx_Mises_avg': mis_avg, 'Mtx_Mises_pk': mis_pk,
            'Mtx_Mises_2m': mis_2m,
            'Mtx_Mises_q90': mis_q90, 'Mtx_Mises_q95': mis_q95,
            'Mtx_PEEQ_pk': peeq_pk, 'Iface_Tn_pk': tn_pk,
            'Iface_Tn_avg': tn_avg,
            'Iface_CSDMG_pk': csdmg_pk, 'Iface_init_pk': csinit_pk,
        })

    if not rows:
        print("  concentration: no frames with stress field; skipped.")
        return [], {}

    last = rows[-1]
    cand = [abs(last['Macro_S11']), abs(last['Macro_S22']), abs(last['Macro_S33'])]
    Lidx = cand.index(max(cand))
    Lname = ('11', '22', '33')[Lidx]
    mac_key = 'Macro_S' + Lname
    avg_key = 'Mtx_S' + Lname + '_avg'
    pk_key = 'Mtx_S' + Lname + '_pk'

    def _safe(a, b):
        return a / b if abs(b) > 1.0e-12 else 0.0

    for r in rows:
        r['SCF_loc'] = _safe(r[avg_key], r[mac_key])
        r['SCFt'] = _safe(r[pk_key], r[avg_key])
        r['SCFt_tot'] = _safe(r[pk_key], r[mac_key])
        r['k_yield'] = _safe(r['Mtx_Mises_pk'], r['Mtx_Mises_avg'])
        # second-moment yield amplifier sqrt(<Mises^2>)/<Mises>
        r['XKYLD_2m'] = _safe(r['Mtx_Mises_2m'], r['Mtx_Mises_avg'])
        # principled YIELD driver: volume-weighted P90 / P95 of matrix Mises over
        # matrix-avg Mises.  Field-derived (no macro-curve peeking); the fitter
        # prefers XKYLD_q90.  q95 written so the quantile level can be judged
        # against the RVE yield-onset timing rather than the macro curve.
        r['XKYLD_q90'] = _safe(r['Mtx_Mises_q90'], r['Mtx_Mises_avg'])
        r['XKYLD_q95'] = _safe(r['Mtx_Mises_q95'], r['Mtx_Mises_avg'])
        # interface-average debond amplifier <Tn_iface> / <sigma_m_transverse>
        # (k_int above is the peak-based counterpart)
        r['XKINT_avg'] = _safe(r['Iface_Tn_avg'], r[avg_key])

    eps_key = 'Macro_E' + Lname
    idx_yield = None
    for i, r in enumerate(rows):
        if r['Mtx_PEEQ_pk'] > 1.0e-8:
            idx_yield = i
            break

    # RVE-pinned yield-knee strain eps_y = first frame where the
    # matrix AVERAGE Mises reaches the matrix Hill tensile-yield onset s0t.  This
    # is the strain at which the mean field (not the geometric hot spot) yields --
    # the correct knee to pin XKYLD's elastic->evolution transition.
    _S0T_pin = 36.6932
    idx_s0t = None
    for i, r in enumerate(rows):
        if r.get('Mtx_Mises_avg', 0.0) >= _S0T_pin:
            idx_s0t = i
            break
    epsy_s0t = rows[idx_s0t].get(eps_key, 0.0) if idx_s0t is not None else 0.0

    # --- INTERFACE debond onset (the with-CZM slope-drop point) ---
    # Priority: (1) CSDMG first > 0 (interface has started to debond);
    #           (2) initiation criterion CSMAXSCRT/CSQUADSCRT first >= ~1;
    #           (3) interface traction peak; (4) macro-stress peak (no CZM).
    idx_deb = None
    onset_by = None
    for i, r in enumerate(rows):
        if r.get('Iface_CSDMG_pk', 0.0) > 1.0e-6:
            idx_deb = i; onset_by = 'CSDMG_init'; break
    if idx_deb is None:
        for i, r in enumerate(rows):
            if r.get('Iface_init_pk', 0.0) >= 0.999:
                idx_deb = i; onset_by = 'init_criterion'; break
    has_iface = any([r['Iface_Tn_pk'] > 1.0e-12 for r in rows])
    if idx_deb is None and has_iface:
        idx_deb = max(range(len(rows)), key=lambda i: rows[i]['Iface_Tn_pk'])
        onset_by = 'interface_traction_peak'
    if idx_deb is None:
        idx_deb = max(range(len(rows)), key=lambda i: abs(rows[i][mac_key]))
        onset_by = 'macro_stress_peak'

    pre = rows[:idx_yield] if idx_yield else rows[:max(1, len(rows) // 3)]
    pre = [r for r in pre if abs(r[mac_key]) > 1.0e-6]
    scf_loc_elastic = (sum([r['SCF_loc'] for r in pre]) / len(pre)) if pre else rows[0]['SCF_loc']

    ry = rows[idx_yield] if idx_yield is not None else {}
    rd = rows[idx_deb]
    # interface concentration to use as the UMAT debond DRIVER:
    # K_int = interface peak normal traction / matrix-average transverse stress
    # at debond onset.  Multiply sigma_m_loc by K_int so the UMAT triggers
    # debond at the SAME composite strain as the RVE (fixes "onset too late").
    k_int = (rd['Iface_Tn_pk'] / rd[avg_key]) if abs(rd[avg_key]) > 1.0e-12 else 0.0
    # --- EVENT-MATCHED ("effective trigger") factors --------------------------
    # The UMAT fires each event when  factor * SIGML(2) >= micro-threshold, with
    # SIGML(2) = its MT-localized matrix transverse stress.  Self-consistent
    # factor = threshold / (matrix stress @ event).  K_INT_eff ~= K_int_raw (the
    # onset traction is ~TN0), so the RAW ratio still over-fires because the
    # UMAT's SIGML localizes stronger than the real RVE.  The CARD value =
    # eff_trigger * alpha, alpha = SCF_loc_RVE / SCF_loc_UMAT, where SCF_loc_UMAT
    # = STATEV(34)/macro from the single-element ODB at the same strain.
    _TN0 = 50.0       # cohesive normal strength (card const 33)
    _S0T = 36.6932    # matrix Hill tensile yield onset (card const 21)
    _SFT = 93.0       # matrix tensile strength sigma_ft (card const 10)
    k_int_eff = (_TN0 / rd[avg_key]) if abs(rd[avg_key]) > 1.0e-12 else 0.0
    # pin the debond eps_y to the MACRO stress peak strain
    # of the with-CZM (red) curve -- the strain at which the homogenized composite
    # actually loses load-carrying capacity -- rather than to the geometric-hot-spot
    # traction-peak frame.  This is the eps_y the fitter should hand XKINT.
    idx_macro_peak = max(range(len(rows)), key=lambda i: abs(rows[i][mac_key]))
    rp = rows[idx_macro_peak]
    epsy_macro_peak = rp.get(eps_key, 0.0)
    xkint_avg_at_debond = rd.get('XKINT_avg', 0.0)
    _ymis = ry.get('Mtx_Mises_avg', 0.0)
    k_yield_eff = (_S0T / _ymis) if abs(_ymis) > 1.0e-12 else 0.0
    scft_eff = (_SFT / rd[avg_key]) if abs(rd[avg_key]) > 1.0e-12 else 0.0
    summary = {
        'Loading_Direction': Lname,
        'Matrix_Region': mreg_name,
        'Void_Model': has_void,
        'Matrix_Porosity': void_vf,
        'SCF_loc_elastic': scf_loc_elastic,
        'k_yield_onset': ry.get('k_yield', 0.0),
        'XKYLD_2m_onset': ry.get('XKYLD_2m', 0.0),
        'XKYLD_q90_onset': ry.get('XKYLD_q90', 0.0),
        'XKYLD_q95_onset': ry.get('XKYLD_q95', 0.0),
        'epsy_s0t_crossing': epsy_s0t,
        'epsy_s0t_frame': rows[idx_s0t]['Frame'] if idx_s0t is not None else -1,
        'yield_onset_frame': ry.get('Frame', -1),
        'yield_onset_macro': ry.get(mac_key, 0.0),
        'SCFt_at_onset': rd['SCFt'],
        'SCFt_tot_at_onset': rd['SCFt_tot'],
        'debond_onset_frame': rd['Frame'],
        'debond_onset_macro_stress': rd[mac_key],
        'debond_onset_macro_strain': rd.get(eps_key, 0.0),
        'debond_onset_mtx_avg': rd[avg_key],
        'debond_onset_iface_Tn': rd['Iface_Tn_pk'],
        'debond_onset_iface_Tn_avg': rd.get('Iface_Tn_avg', 0.0),
        'XKINT_avg_at_debond': xkint_avg_at_debond,
        'epsy_macro_peak': epsy_macro_peak,
        'epsy_macro_peak_frame': rp.get('Frame', -1),
        'macro_peak_stress': rp.get(mac_key, 0.0),
        'K_int_debond_driver': k_int,
        'K_INT_eff_trigger': k_int_eff,
        'K_YIELD_eff_trigger': k_yield_eff,
        'SCFt_eff_trigger': scft_eff,
        'SCF_loc_at_yield': ry.get('SCF_loc', 0.0),
        'SCF_loc_at_debond': rd.get('SCF_loc', 0.0),
        'alpha_hint': 'card = eff_trigger * SCF_loc_RVE / SCF_loc_UMAT(STATEV34/macro)',
        'onset_by': onset_by,
    }

    saved = []
    base = sanitize_loading_label(loading_label)
    hist_name = os.path.join(output_dir, '{}_concentration_history_{}.csv'.format(
        output_model_name, base))
    hist_fields = ['Frame', 'Time', mac_key, eps_key, avg_key, pk_key,
                   'SCF_loc', 'SCFt', 'SCFt_tot', 'Mtx_Mises_avg', 'Mtx_Mises_pk',
                   'Mtx_Mises_2m', 'Mtx_Mises_q90', 'Mtx_Mises_q95',
                   'k_yield', 'XKYLD_2m', 'XKYLD_q90', 'XKYLD_q95',
                   'Mtx_PEEQ_pk', 'Iface_Tn_pk', 'Iface_Tn_avg', 'XKINT_avg',
                   'Iface_CSDMG_pk', 'Iface_init_pk',
                   'Macro_S11', 'Macro_S22', 'Macro_S33',
                   'Macro_E11', 'Macro_E22', 'Macro_E33',
                   'Mtx_S11_avg', 'Mtx_S22_avg', 'Mtx_S33_avg',
                   'Mtx_S11_pk', 'Mtx_S22_pk', 'Mtx_S33_pk']
    csvfile, writer = create_csv_writer(hist_name, hist_fields)
    if writer:
        for r in rows:
            writer.writerow(r)
        close_csv_file(csvfile)
        saved.append(hist_name)
        print("  concentration history: %s" % os.path.basename(hist_name))

    sum_name = os.path.join(output_dir, '{}_concentration_summary_{}.txt'.format(
        output_model_name, base))
    if write_summary_txt(sum_name, summary):
        saved.append(sum_name)
        print("  concentration summary: %s" % os.path.basename(sum_name))

    print("  [UMAT calibration] loading dir %s | SCF_loc(elastic)=%.3f "
          "| k_yield(onset)=%.3f | SCFt(onset)=%.3f | SCFt_tot=%.3f"
          % (Lname, scf_loc_elastic, summary['k_yield_onset'],
             summary['SCFt_at_onset'], summary['SCFt_tot_at_onset']))
    print("  [interface debond] by=%s | onset strain=%.5f stress=%.3f "
          "| K_int(driver)=%.3f  (multiply sigma_m_loc by K_int in the UMAT)"
          % (summary['onset_by'], summary['debond_onset_macro_strain'],
             summary['debond_onset_macro_stress'], summary['K_int_debond_driver']))

    # Parameter fitting is intentionally not performed here; the CSV and
    # summary written above are the plugin's output.
    return saved, summary

def calculate_effective_properties(rp_results, L, H, W, applied_strains):
    """Calculate effective material properties from reference point results"""
    
    properties = {}
    
    try:
        # Create dictionary for reference point data
        rp_data = {}
        for rp in rp_results:
            rp_name = rp['Reference_Point']
            rp_data[rp_name] = rp
        
        epsilon_x = applied_strains['epsilon_x']
        epsilon_y = applied_strains['epsilon_y'] 
        epsilon_z = applied_strains['epsilon_z']
        gamma_xy = applied_strains['gamma_xy']
        gamma_yz = applied_strains['gamma_yz']
        gamma_zx = applied_strains['gamma_zx']
        
        # Calculate effective elastic moduli
        # E1 (X-direction) - from RP1 reaction force and applied strain
        if 'RP1' in rp_data and abs(epsilon_x) > 1e-12:
            rf1_rp1 = abs(rp_data['RP1']['RF1'])
            stress_x = rf1_rp1 / (H * W)  # X-direction stress
            E1_eff = stress_x / abs(epsilon_x) if abs(epsilon_x) > 1e-12 else 0.0
            properties['E1_effective'] = E1_eff
            properties['Stress_X'] = stress_x
            properties['Force_X'] = rf1_rp1
        else:
            properties['E1_effective'] = 0.0
            properties['Stress_X'] = 0.0
            properties['Force_X'] = 0.0
        
        # E2 (Y-direction) - from RP2 reaction force and applied strain
        if 'RP2' in rp_data and abs(epsilon_y) > 1e-12:
            rf2_rp2 = abs(rp_data['RP2']['RF2'])
            stress_y = rf2_rp2 / (L * W)  # Y-direction stress
            E2_eff = stress_y / abs(epsilon_y) if abs(epsilon_y) > 1e-12 else 0.0
            properties['E2_effective'] = E2_eff
            properties['Stress_Y'] = stress_y
            properties['Force_Y'] = rf2_rp2
        else:
            properties['E2_effective'] = 0.0
            properties['Stress_Y'] = 0.0
            properties['Force_Y'] = 0.0
        
        # E3 (Z-direction) - from RP3 reaction force and applied strain
        if 'RP3' in rp_data and abs(epsilon_z) > 1e-12:
            rf3_rp3 = abs(rp_data['RP3']['RF3'])
            stress_z = rf3_rp3 / (L * H)  # Z-direction stress
            E3_eff = stress_z / abs(epsilon_z) if abs(epsilon_z) > 1e-12 else 0.0
            properties['E3_effective'] = E3_eff
            properties['Stress_Z'] = stress_z
            properties['Force_Z'] = rf3_rp3
        else:
            properties['E3_effective'] = 0.0
            properties['Stress_Z'] = 0.0
            properties['Force_Z'] = 0.0
        
        # Shear moduli calculations
        # G12 - from RP4 calculation
        if 'RP4' in rp_data and abs(gamma_xy) > 1e-12:
            rf1_rp4 = abs(rp_data['RP4']['RF1'])
            rf2_rp4 = abs(rp_data['RP4']['RF2'])
            tau_xy = (rf1_rp4 + rf2_rp4) / (2 * H * W)  # Average shear stress
            G12_eff = tau_xy / abs(gamma_xy) if abs(gamma_xy) > 1e-12 else 0.0
            properties['G12_effective'] = G12_eff
            properties['Shear_Stress_XY'] = tau_xy
        else:
            properties['G12_effective'] = 0.0
            properties['Shear_Stress_XY'] = 0.0
        
        # G13 - from RP5 calculation  
        if 'RP5' in rp_data and abs(gamma_zx) > 1e-12:
            rf1_rp5 = abs(rp_data['RP5']['RF1'])
            rf3_rp5 = abs(rp_data['RP5']['RF3'])
            tau_xz = (rf1_rp5 + rf3_rp5) / (2 * H * L)  # Average shear stress
            G13_eff = tau_xz / abs(gamma_zx) if abs(gamma_zx) > 1e-12 else 0.0
            properties['G13_effective'] = G13_eff
            properties['Shear_Stress_XZ'] = tau_xz
        else:
            properties['G13_effective'] = 0.0
            properties['Shear_Stress_XZ'] = 0.0
        
        # G23 - from RP6 calculation
        if 'RP6' in rp_data and abs(gamma_yz) > 1e-12:
            rf2_rp6 = abs(rp_data['RP6']['RF2'])
            rf3_rp6 = abs(rp_data['RP6']['RF3'])
            tau_yz = (rf2_rp6 + rf3_rp6) / (2 * L * W)  # Average shear stress
            G23_eff = tau_yz / abs(gamma_yz) if abs(gamma_yz) > 1e-12 else 0.0
            properties['G23_effective'] = G23_eff
            properties['Shear_Stress_YZ'] = tau_yz
        else:
            properties['G23_effective'] = 0.0
            properties['Shear_Stress_YZ'] = 0.0
        
        # Poisson's ratio calculations (for single-axis loading cases)
        # v12 = -strain_y / strain_x (when only X-direction loading)
        if abs(epsilon_x) > 1e-12 and abs(epsilon_y) < 1e-12:
            # Single-axis X loading case, calculate Y-direction strain from RP2 displacement
            if 'RP2' in rp_data:
                strain_y_induced = rp_data['RP2']['U2'] / H
                v12 = -strain_y_induced / epsilon_x if abs(epsilon_x) > 1e-12 else 0.0
                properties['Poisson_12'] = v12
            else:
                properties['Poisson_12'] = 0.0
        else:
            properties['Poisson_12'] = 0.0
        
        # v13 = -strain_z / strain_x (when only X-direction loading)
        if abs(epsilon_x) > 1e-12 and abs(epsilon_z) < 1e-12:
            if 'RP3' in rp_data:
                strain_z_induced = rp_data['RP3']['U3'] / W
                v13 = -strain_z_induced / epsilon_x if abs(epsilon_x) > 1e-12 else 0.0
                properties['Poisson_13'] = v13
            else:
                properties['Poisson_13'] = 0.0
        else:
            properties['Poisson_13'] = 0.0
        
        # Similar calculations for other Poisson's ratios
        properties['Poisson_21'] = 0.0  # Would need Y-only loading
        properties['Poisson_23'] = 0.0  # Would need Y-only loading
        properties['Poisson_31'] = 0.0  # Would need Z-only loading
        properties['Poisson_32'] = 0.0  # Would need Z-only loading
        
        return properties
        
    except Exception as e:
        print("Error calculating effective properties: {}".format(str(e)))
        return {}

def is_rp_active_in_constraints(modelName, rp_name):
    """Check if the reference point is referenced in any of the constraint equations"""
    for constraint_name, constraint in mdb.models[modelName].constraints.items():
        if hasattr(constraint, 'terms'):
            for term in constraint.terms:
                if len(term) >= 2 and term[1] == rp_name:
                    return True
    return False

def calculate_true_stress_strain_from_rp(rp_results, loading_type, L, H, W):
    """
    Compute true stress/strain from reference-point results (loading direction only)
    
    Parameters:
    - rp_results: reference-point time-history data
    - loading_type: 'E11', 'E22', 'E33', 'G12', 'G13', 'G23'
    - L, H, W: original RVE dimensions
    
    Returns:
    - List of dicts with Frame, True_Stress, True_Strain
    """
    true_results = []
    loading_type = normalize_loading_type_label(loading_type)
    
    # group by frame
    frame_data = {}
    for result in rp_results:
        frame = result.get('Frame', 0)
        if frame not in frame_data:
            frame_data[frame] = {}
        rp_name = result['Reference_Point']
        frame_data[frame][rp_name] = result
    
    # compute true stress/strain for each frame
    for frame in sorted(frame_data.keys()):
        frame_rps = frame_data[frame]
        
        result_dict = {
            'Frame': frame,
            'Time': frame_rps.get('RP1', {}).get('Time', 0.0)
        }
        
        if loading_type == 'E11':  # tension in X
            if 'RP1' not in frame_rps:
                continue
            rp1_data = frame_rps['RP1']
            
            # engineering strain and stress
            eng_strain = rp1_data['U1'] / L
            eng_stress = rp1_data['RF1'] / (H * W)
            
            # true strain: ln(1 + eps_eng)
            if eng_strain > -0.999:  # avoid ln(negative)
                true_strain = np.log(1.0 + eng_strain)
            else:
                true_strain = 0.0
            
            # true stress: sigma_eng * (1 + eps_eng)
            true_stress = eng_stress * (1.0 + eng_strain)
            
            result_dict.update({
                'True_Stress': true_stress,
                'True_Strain': true_strain,
                'True_Stress_Abs': abs(true_stress),
                'True_Strain_Abs': abs(true_strain)
            })
            
        elif loading_type == 'E22':  # tension in Y
            if 'RP2' not in frame_rps:
                continue
            rp2_data = frame_rps['RP2']
            
            eng_strain = rp2_data['U2'] / H
            eng_stress = rp2_data['RF2'] / (L * W)
            
            if eng_strain > -0.999:
                true_strain = np.log(1.0 + eng_strain)
            else:
                true_strain = 0.0
            
            true_stress = eng_stress * (1.0 + eng_strain)
            
            result_dict.update({
                'True_Stress': true_stress,
                'True_Strain': true_strain,
                'True_Stress_Abs': abs(true_stress),
                'True_Strain_Abs': abs(true_strain)
            })
            
        elif loading_type == 'E33':  # tension in Z
            if 'RP3' not in frame_rps:
                continue
            rp3_data = frame_rps['RP3']
            
            eng_strain = rp3_data['U3'] / W
            eng_stress = rp3_data['RF3'] / (L * H)
            
            if eng_strain > -0.999:
                true_strain = np.log(1.0 + eng_strain)
            else:
                true_strain = 0.0
            
            true_stress = eng_stress * (1.0 + eng_strain)
            
            result_dict.update({
                'True_Stress': true_stress,
                'True_Strain': true_strain,
                'True_Stress_Abs': abs(true_stress),
                'True_Strain_Abs': abs(true_strain)
            })
            
        elif loading_type == 'G12':  # XY shear
            if 'RP4' not in frame_rps:
                continue
            rp4_data = frame_rps['RP4']

            # RP carries the *tensor* shear (eps_ij = (u_i/L_j + u_j/L_i)/2)
            # and the engineering shear stress tau_ij (averaged from the two RFs).
            tensor_shear_strain = rp4_data.get('Shear_Strain_12', 0.0)
            eng_shear_stress    = rp4_data.get('Shear_Stress_12', 0.0)

            # True (log) tensor shear: ln(1 + eps_ij) * sign(eps_ij).
            if abs(tensor_shear_strain) > 1e-12:
                true_shear_strain_tensor = np.log(1.0 + abs(tensor_shear_strain)) * np.sign(tensor_shear_strain)
            else:
                true_shear_strain_tensor = tensor_shear_strain
            # Engineering true shear = 2 * tensor (matches "2*Gamma_ij" in macroscopic CSV).
            true_shear_strain_engineering = 2.0 * true_shear_strain_tensor
            # True (Cauchy) shear stress.
            true_shear_stress = eng_shear_stress * (1.0 + abs(tensor_shear_strain))

            result_dict.update({
                'True_Shear_Strain_Tensor':      true_shear_strain_tensor,
                'True_Shear_Strain_Engineering': true_shear_strain_engineering,
                'True_Shear_Stress':             true_shear_stress,
            })
            
        elif loading_type == 'G13':  # XZ shear
            if 'RP5' not in frame_rps:
                continue
            rp5_data = frame_rps['RP5']

            # RP carries the *tensor* shear (eps_ij = (u_i/L_j + u_j/L_i)/2)
            # and the engineering shear stress tau_ij (averaged from the two RFs).
            tensor_shear_strain = rp5_data.get('Shear_Strain_13', 0.0)
            eng_shear_stress    = rp5_data.get('Shear_Stress_13', 0.0)

            # True (log) tensor shear: ln(1 + eps_ij) * sign(eps_ij).
            if abs(tensor_shear_strain) > 1e-12:
                true_shear_strain_tensor = np.log(1.0 + abs(tensor_shear_strain)) * np.sign(tensor_shear_strain)
            else:
                true_shear_strain_tensor = tensor_shear_strain
            # Engineering true shear = 2 * tensor (matches "2*Gamma_ij" in macroscopic CSV).
            true_shear_strain_engineering = 2.0 * true_shear_strain_tensor
            # True (Cauchy) shear stress.
            true_shear_stress = eng_shear_stress * (1.0 + abs(tensor_shear_strain))

            result_dict.update({
                'True_Shear_Strain_Tensor':      true_shear_strain_tensor,
                'True_Shear_Strain_Engineering': true_shear_strain_engineering,
                'True_Shear_Stress':             true_shear_stress,
            })
            
        elif loading_type == 'G23':  # YZ shear
            if 'RP6' not in frame_rps:
                continue
            rp6_data = frame_rps['RP6']

            # RP carries the *tensor* shear (eps_ij = (u_i/L_j + u_j/L_i)/2)
            # and the engineering shear stress tau_ij (averaged from the two RFs).
            tensor_shear_strain = rp6_data.get('Shear_Strain_23', 0.0)
            eng_shear_stress    = rp6_data.get('Shear_Stress_23', 0.0)

            # True (log) tensor shear: ln(1 + eps_ij) * sign(eps_ij).
            if abs(tensor_shear_strain) > 1e-12:
                true_shear_strain_tensor = np.log(1.0 + abs(tensor_shear_strain)) * np.sign(tensor_shear_strain)
            else:
                true_shear_strain_tensor = tensor_shear_strain
            # Engineering true shear = 2 * tensor (matches "2*Gamma_ij" in macroscopic CSV).
            true_shear_strain_engineering = 2.0 * true_shear_strain_tensor
            # True (Cauchy) shear stress.
            true_shear_stress = eng_shear_stress * (1.0 + abs(tensor_shear_strain))

            result_dict.update({
                'True_Shear_Strain_Tensor':      true_shear_strain_tensor,
                'True_Shear_Strain_Engineering': true_shear_strain_engineering,
                'True_Shear_Stress':             true_shear_stress,
            })
        
        if ('True_Stress' in result_dict) or ('True_Shear_Stress' in result_dict):
            true_results.append(result_dict)
    
    return true_results


def save_true_stress_strain(true_results, output_dir, modelName, loading_type):
    """Write the true stress-strain CSV.

    Column layout depends on loading_type so the shear convention (tensor vs
    engineering shear) is unambiguous in the header:
      * Normal (E11 / E22 / E33):
            Frame, Time, True_Strain, True_Stress, True_Strain_Abs, True_Stress_Abs
        where True_Strain = ln(1 + eps_eng) and True_Stress = sigma_eng * (1 + eps_eng);
        the *_Abs columns are the absolute values (mirror of the no-interface kernel).
      * Shear (G12 / G13 / G23):
            Frame, Time,
            True_Shear_Strain_Tensor       (= ln(1 + eps_ij) * sign(eps_ij), with eps_ij = gamma_eng / 2)
            True_Shear_Strain_Engineering  (= 2 * True_Shear_Strain_Tensor; matches "2*Gamma_ij" in the macroscopic CSV)
            True_Shear_Stress              (= tau_eng * (1 + |eps_ij|); Cauchy shear stress)
    """
    if not true_results:
        return None

    filename = os.path.join(output_dir,
                           '{}_true_stress_strain_{}.csv'.format(
                               modelName, sanitize_loading_label(loading_type)))

    # Detect shear mode primarily from the result dict's actual keys (so the
    # caller can pass an already-sanitized label like 'Shear23_Temp_025' and we
    # still pick the right CSV layout). normalize_loading_type_label is used as
    # a second pass when the dicts somehow contain neither variant.
    sample_row = true_results[0] if true_results else {}
    is_shear = any([k in sample_row for k in ('True_Shear_Stress', 'True_Shear_Strain_Tensor', 'True_Shear_Strain_Engineering')])
    if not is_shear and 'True_Stress' not in sample_row:
        normalized_type = normalize_loading_type_label(loading_type)
        is_shear = normalized_type in ('G12', 'G13', 'G23')

    if is_shear:
        fieldnames = ['Frame', 'Time',
                      'True_Shear_Strain_Tensor',
                      'True_Shear_Strain_Engineering',
                      'True_Shear_Stress']
    else:
        fieldnames = ['Frame', 'Time', 'True_Strain', 'True_Stress', 'True_Strain_Abs', 'True_Stress_Abs']
    
    csvfile, writer = create_csv_writer(filename, fieldnames)
    if writer:
        for result in true_results:
            writer.writerow(result)
        close_csv_file(csvfile)
        print("  True stress-strain curve: {} ({} points)".format(
            os.path.basename(filename), len(true_results)))
        return filename
    
    return None



def rve_multiaxial_analysis_complete(part, inst, meshsens, epsilon_x, epsilon_y, epsilon_z,
                                   gamma_xy, gamma_yz, gamma_zx, CPU, umat_file='', output_dir=None,
                                   save_volume_avg=True, temperature_celsius=None, loading_label='Analysis',
                                   legacy_loading_type='', unsymmetric_solver=False, large_deformation=True,
                                   result_model_name=None, field_output_intervals=None,
                                   stabilization_magnitude=None, analysis_procedure='STATIC'):

    print("=" * 80)
    print("STARTING COMPLETE RVE MULTI-AXIAL ANALYSIS")
    print("=" * 80)
    
    model = mdb.models[part]
    model.rootAssembly.regenerate()

    # ---- Element-family guard (MECHANICAL / cohesive interface analysis) ----
    # Abort early if this model was meshed for a THERMAL analysis (DC* heat-
    # transfer elements).  Stress and heat-transfer element families never mix
    # within a model, so the first element of each part is representative.
    for _pname in model.parts.keys():
        _els = model.parts[_pname].elements
        if len(_els) == 0:
            continue
        _etype = str(_els[0].type).upper()
        if _etype[:2] == 'DC':
            raise ValueError(
                "Mechanical interface analysis ABORTED: part '%s' uses heat-"
                "transfer elements (%s). This model is built for a THERMAL "
                "conductivity analysis -- run the thermal module, or re-mesh "
                "with stress elements (e.g. C3D8R) for the mechanical "
                "(cohesive) interface." % (_pname, _etype))

    if output_dir is None:
        output_dir = os.getcwd()
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    path = os.getcwd()
    
    start_time = time.time()
    
    for T in range(1):
        modelName = part
        output_model_name = result_model_name or modelName
        instanceName = inst + '-1'
        upperName = inst.upper()
        
        # Error checking
        if part not in (mdb.models.keys()):
            print('Error: Model "{}" not found!'.format(part))
            return False
        
        a = mdb.models[modelName].rootAssembly
        if not mdb.models[modelName].rootAssembly.instances.keys():
            print('Error: No instances found in the model!')
            return False
        
        if instanceName not in mdb.models[modelName].rootAssembly.instances.keys():
            print('Error: Instance "{}" not found!'.format(instanceName))
            return False
    
        CPUs = int(round(CPU))
        if CPUs > multiprocessing.cpu_count():
            CPUs = multiprocessing.cpu_count()
            print('Warning: Using maximum available CPUs ({})'.format(CPUs))
    
        allInterfaceNodes = mdb.models[modelName].rootAssembly.instances[instanceName].nodes
        interfaceDuplicateLayers = _interface_duplicate_node_layers(allInterfaceNodes, meshsens)
        Nodeset = allInterfaceNodes
        if has_duplicate_coordinate_nodes(mdb.models[modelName], instanceName, meshsens):
            Nodeset = unique_coordinate_nodes(Nodeset, meshsens)
            print('[Interface] Duplicate coordinate nodes detected; main RVE layer uses label representatives and extra interface layers are constrained separately.')
        _reset_elastoplastic_analysis_state(mdb.models[modelName], a)
        if temperature_celsius is not None:
            _set_uniform_initial_temperature(
                mdb.models[modelName], a, instanceName,
                float(temperature_celsius) + 273.15,
                'Elastoplastic-Initial-Temperature'
            )
        
        # Get RVE dimensions
        j = 0
        x=[]
        y=[]
        z=[]
        c1=[]
        c2=[]
        c3=[]
        c4=[]
        c5=[]
        c6=[]
        c7=[]
        c8=[]
        Max=[]
        ftedgexyz={}
        btedgexyz={}
        fbedgexyz={}
        bbedgexyz={}
        fledgexyz={}
        bledgexyz={}
        fredgexyz={}
        bredgexyz={}
        ltedgexyz={}
        rtedgexyz={}
        lbedgexyz={}
        rbedgexyz={}
        frontsxyz={}
        backsxyz={}
        topsxyz={}
        botsxyz={}
        leftsxyz={}
        rightsxyz={}
        frontbcxyz={}
        backbcxyz={}
        topbcxyz={}
        botbcxyz={}
        leftbcxyz={}
        rightbcxyz={}
        ftedge=[]
        btedge=[]
        fbedge=[]
        bbedge=[]
        fledge=[]
        fredge=[]
        bledge=[]
        bredge=[]
        ltedge=[]
        lbedge=[]
        rtedge=[]
        rbedge=[]
        fronts=[]
        backs=[]
        lefts=[]
        rights=[]
        tops=[]
        bots=[]
        backs=[]
        frontbc=[]
        backbc=[]
        leftbc=[]
        rightbc=[]
        topbc=[]
        botbc=[]
        backbc=[]
        errorset=[]
        coc1={}
        coc2={}
        coc3={}
        coc4={}
        coc5={}
        coc6={}
        coc7={}
        coc8={}
        
        error=False

        print(('============================== PBC and Equations ==============================='))
        
        ## Identifying RVE size ##    
        for i in Nodeset:
            x.append(i.coordinates[0])
            y.append(i.coordinates[1])
            z.append(i.coordinates[2])
            j += 1
        
        if not x:
            print('Error: No nodes found in instance!')
            return False
        
        Max, May, Maz, Mnx, Mny, Mnz = max(x), max(y), max(z), min(x), min(y), min(z)
        L = abs(Max - Mnx)
        H = abs(May - Mny)
        W = abs(Maz - Mnz)
        
        # Macroscopic strains are prescribed directly along the RVE axes
        # (x = fiber direction, y-z = transverse plane). Off-axis loading is not
        # handled here: a uniaxial off-axis test is a mixed stress/strain problem
        # (one prescribed strain, five zero stresses) and needs its own module.
        epsilon_1 = epsilon_x
        epsilon_2 = epsilon_y
        epsilon_3 = epsilon_z
        gamma_12 = gamma_xy
        gamma_23 = gamma_yz
        gamma_31 = gamma_zx
        
        # Calculate displacements
        # for tensile
        Dispx = epsilon_1* L
        Dispy = epsilon_2* H
        Dispz = epsilon_3* W
        # for shear
        Dispxy_x = gamma_12* H
        Dispxy_y = gamma_12* L
        Dispyz_y = gamma_23* W
        Dispyz_z = gamma_23* H
        Dispzx_z = gamma_31* L
        Dispzx_x = gamma_31* W
        
        # Create reference points
        # Create 6 reference points for 3D loading control
        a.ReferencePoint(point=(Max+0.8*L, May-0.5*H, Maz-0.5*W))  ## RP6: Shear gamma_23 control
        a.ReferencePoint(point=(Max+0.6*L, May-0.5*H, Maz-0.5*W))  ## RP5: Shear gamma_13 control  
        a.ReferencePoint(point=(Max+0.4*L, May-0.5*H, Maz-0.5*W))  ## RP4: Shear gamma_12 control
        a.ReferencePoint(point=(Max+0.2*L, May-0.5*H, Maz-0.5*W))  ## RP3: Z-direction control
        a.ReferencePoint(point=(Max-0.5*L, May-0.5*H, Maz+0.2*W))  ## RP2: Y-direction control
        a.ReferencePoint(point=(Max-0.5*L, May+0.2*H, Maz-0.5*W))  ## RP1: X-direction control
        
        r1 = a.referencePoints
        
        ## Naming Ref. Points ##
        d=1
        for i in r1.keys():
            refPoints1=(r1[i], )
            a.Set(referencePoints=refPoints1, name='RP%s' % (d))
            d=d+1
          
        ## Identifying boundary nodes ##
        for i in Nodeset:
            if (Mnx+meshsens) < i.coordinates[0] < (Max-meshsens) and (Mny+meshsens) < i.coordinates[1] < (May-meshsens) and (Mnz+meshsens) < i.coordinates[2] < (Maz-meshsens):
                continue
            if abs(i.coordinates[0]-Max)<=meshsens:
                frontbcxyz[i.label]=[i.coordinates[0], i.coordinates[1], i.coordinates[2]]	
            if abs(i.coordinates[0]-Mnx)<=meshsens:
                backbcxyz[i.label]=[i.coordinates[0], i.coordinates[1], i.coordinates[2]]	
            if abs(i.coordinates[2]-Maz)<=meshsens:
                leftbcxyz[i.label]=[i.coordinates[0], i.coordinates[1], i.coordinates[2]]
            if abs(i.coordinates[2]-Mnz)<=meshsens:
                rightbcxyz[i.label]=[i.coordinates[0], i.coordinates[1], i.coordinates[2]]	
            if abs(i.coordinates[1]-May)<=meshsens:
                topbcxyz[i.label]=[i.coordinates[0], i.coordinates[1], i.coordinates[2]]	
            if abs(i.coordinates[1]-Mny)<=meshsens:
                botbcxyz[i.label]=[i.coordinates[0], i.coordinates[1], i.coordinates[2]]
            if abs(i.coordinates[0]-Max)<=meshsens and abs(i.coordinates[1]-May)<=meshsens and abs(i.coordinates[2]-Maz)<=meshsens:
                c1.insert(0,i.label)
                coc1[i.label]=[i.coordinates[0], i.coordinates[1], i.coordinates[2]]
            if abs(i.coordinates[0]-Mnx)<=meshsens and abs(i.coordinates[1]-May)<=meshsens and abs(i.coordinates[2]-Maz)<=meshsens:
                c2.insert(0,i.label)
                coc2[i.label]=[i.coordinates[0], i.coordinates[1], i.coordinates[2]]
            if abs(i.coordinates[0]-Mnx)<=meshsens and abs(i.coordinates[1]-May)<=meshsens and abs(i.coordinates[2]-Mnz)<=meshsens:
                c3.insert(0,i.label)
                coc3[i.label]=[i.coordinates[0], i.coordinates[1], i.coordinates[2]]
            if abs(i.coordinates[0]-Max)<=meshsens and abs(i.coordinates[1]-May)<=meshsens and abs(i.coordinates[2]-Mnz)<=meshsens:
                c4.insert(0,i.label)
                coc4[i.label]=[i.coordinates[0], i.coordinates[1], i.coordinates[2]]
            if abs(i.coordinates[0]-Max)<=meshsens and abs(i.coordinates[1]-Mny)<=meshsens and abs(i.coordinates[2]-Maz)<=meshsens:
                c5.insert(0,i.label)
                coc5[i.label]=[i.coordinates[0], i.coordinates[1], i.coordinates[2]]
            if abs(i.coordinates[0]-Mnx)<=meshsens and abs(i.coordinates[1]-Mny)<=meshsens and abs(i.coordinates[2]-Maz)<=meshsens:
                c6.insert(0,i.label)
                coc6[i.label]=[i.coordinates[0], i.coordinates[1], i.coordinates[2]]
            if abs(i.coordinates[0]-Mnx)<=meshsens and abs(i.coordinates[1]-Mny)<=meshsens and abs(i.coordinates[2]-Mnz)<=meshsens:
                c7.insert(0,i.label)
                coc7[i.label]=[i.coordinates[0], i.coordinates[1], i.coordinates[2]]
            if abs(i.coordinates[0]-Max)<=meshsens and abs(i.coordinates[1]-Mny)<=meshsens and abs(i.coordinates[2]-Mnz)<=meshsens:
                c8.insert(0,i.label)
                coc8[i.label]=[i.coordinates[0], i.coordinates[1], i.coordinates[2]]
            if abs(i.coordinates[0]-Max)<=meshsens and abs(i.coordinates[1]-May)<=meshsens and abs(i.coordinates[2]-Maz)>meshsens and abs(i.coordinates[2]-Mnz)>meshsens:
                ftedgexyz[i.label]=[i.coordinates[0], i.coordinates[1], i.coordinates[2]]
            if abs(i.coordinates[0]-Max)<=meshsens and abs(i.coordinates[1]-Mny)<=meshsens and abs(i.coordinates[2]-Maz)>meshsens and abs(i.coordinates[2]-Mnz)>meshsens:
                fbedgexyz[i.label]=[i.coordinates[0], i.coordinates[1], i.coordinates[2]]
            if abs(i.coordinates[0]-Mnx)<=meshsens and abs(i.coordinates[1]-May)<=meshsens and abs(i.coordinates[2]-Maz)>meshsens and abs(i.coordinates[2]-Mnz)>meshsens:
                btedgexyz[i.label]=[i.coordinates[0], i.coordinates[1], i.coordinates[2]]
            if abs(i.coordinates[0]-Mnx)<=meshsens and abs(i.coordinates[1]-Mny)<=meshsens and abs(i.coordinates[2]-Maz)>meshsens and abs(i.coordinates[2]-Mnz)>meshsens:
                bbedgexyz[i.label]=[i.coordinates[0], i.coordinates[1], i.coordinates[2]]	
            if abs(i.coordinates[0]-Max)<=meshsens and abs(i.coordinates[2]-Maz)<=meshsens and abs(i.coordinates[1]-May)>meshsens and abs(i.coordinates[1]-Mny)>meshsens:
                fledgexyz[i.label]=[i.coordinates[0], i.coordinates[1], i.coordinates[2]]	
            if abs(i.coordinates[0]-Max)<=meshsens and abs(i.coordinates[2]-Mnz)<=meshsens and abs(i.coordinates[1]-May)>meshsens and abs(i.coordinates[1]-Mny)>meshsens:
                fredgexyz[i.label]=[i.coordinates[0], i.coordinates[1], i.coordinates[2]]	
            if abs(i.coordinates[0]-Mnx)<=meshsens and abs(i.coordinates[2]-Maz)<=meshsens and abs(i.coordinates[1]-May)>meshsens and abs(i.coordinates[1]-Mny)>meshsens:
                bledgexyz[i.label]=[i.coordinates[0], i.coordinates[1], i.coordinates[2]]	
            if abs(i.coordinates[0]-Mnx)<=meshsens and abs(i.coordinates[2]-Mnz)<=meshsens and abs(i.coordinates[1]-May)>meshsens and abs(i.coordinates[1]-Mny)>meshsens:
                bredgexyz[i.label]=[i.coordinates[0], i.coordinates[1], i.coordinates[2]]	
            if abs(i.coordinates[2]-Maz)<=meshsens and abs(i.coordinates[1]-May)<=meshsens and abs(i.coordinates[0]-Max)>meshsens and abs(i.coordinates[0]-Mnx)>meshsens:
                ltedgexyz[i.label]=[i.coordinates[0], i.coordinates[1], i.coordinates[2]]	
            if abs(i.coordinates[2]-Maz)<=meshsens and abs(i.coordinates[1]-Mny)<=meshsens and abs(i.coordinates[0]-Max)>meshsens and abs(i.coordinates[0]-Mnx)>meshsens:
                lbedgexyz[i.label]=[i.coordinates[0], i.coordinates[1], i.coordinates[2]]	
            if abs(i.coordinates[2]-Mnz)<=meshsens and abs(i.coordinates[1]-May)<=meshsens and abs(i.coordinates[0]-Max)>meshsens and abs(i.coordinates[0]-Mnx)>meshsens:
                rtedgexyz[i.label]=[i.coordinates[0], i.coordinates[1], i.coordinates[2]]	
            if abs(i.coordinates[2]-Mnz)<=meshsens and abs(i.coordinates[1]-Mny)<=meshsens and abs(i.coordinates[0]-Max)>meshsens and abs(i.coordinates[0]-Mnx)>meshsens:
                rbedgexyz[i.label]=[i.coordinates[0], i.coordinates[1], i.coordinates[2]]	
            if abs(i.coordinates[0]-Max)<=meshsens and abs(i.coordinates[1]-May)>meshsens and abs(i.coordinates[1]-Mny)>meshsens and abs(i.coordinates[2]-Maz)>meshsens and abs(i.coordinates[2]-Mnz)>meshsens:
                frontsxyz[i.label]=[i.coordinates[0], i.coordinates[1], i.coordinates[2]]
            if abs(i.coordinates[0]-Mnx)<=meshsens and abs(i.coordinates[1]-May)>meshsens and abs(i.coordinates[1]-Mny)>meshsens and abs(i.coordinates[2]-Maz)>meshsens and abs(i.coordinates[2]-Mnz)>meshsens:
                backsxyz[i.label]=[i.coordinates[0], i.coordinates[1], i.coordinates[2]] 
            if abs(i.coordinates[2]-Maz)<=meshsens and abs(i.coordinates[1]-May)>meshsens and abs(i.coordinates[1]-Mny)>meshsens and abs(i.coordinates[0]-Max)>meshsens and abs(i.coordinates[0]-Mnx)>meshsens:
                leftsxyz[i.label]=[i.coordinates[0], i.coordinates[1], i.coordinates[2]]	
            if abs(i.coordinates[2]-Mnz)<=meshsens and abs(i.coordinates[1]-May)>meshsens and abs(i.coordinates[1]-Mny)>meshsens and abs(i.coordinates[0]-Max)>meshsens and abs(i.coordinates[0]-Mnx)>meshsens:
                rightsxyz[i.label]=[i.coordinates[0], i.coordinates[1], i.coordinates[2]]   
            if abs(i.coordinates[1]-May)<=meshsens and abs(i.coordinates[0]-Max)>meshsens and abs(i.coordinates[0]-Mnx)>meshsens and abs(i.coordinates[2]-Maz)>meshsens and abs(i.coordinates[2]-Mnz)>meshsens:
                topsxyz[i.label]=[i.coordinates[0], i.coordinates[1], i.coordinates[2]]
            if abs(i.coordinates[1]-Mny)<=meshsens and abs(i.coordinates[0]-Max)>meshsens and abs(i.coordinates[0]-Mnx)>meshsens and abs(i.coordinates[2]-Maz)>meshsens and abs(i.coordinates[2]-Mnz)>meshsens:
                botsxyz[i.label]=[i.coordinates[0], i.coordinates[1], i.coordinates[2]]

        ## Checking number of nodes of opposite/associated sets ##
        if len(frontsxyz) != len(backsxyz):
         print('Warning: Number of Nodes in Front surface (fronts) not equal to number of nodes in Back surface (backs). These sets will not be created!!')
         print('         Refer to error 06 troubleshooting in easyPBC user guide.')
         frontsxyz={}
         error=True
        if len(topsxyz) != len(botsxyz):
         print('Warning: Number of Nodes in Top surface (tops) not equal to number of nodes in Bottom surface (bots). These sets will not be created!!')
         print('         Refer to error 06 in easyPBC user guide.')
         topsxyz={}
         error=True
        if len(leftsxyz) != len(rightsxyz):
         print('Warning: Number of Nodes in Left surface (lefts) not equal to number of nodes in Right surface (rights). These sets will not be created!!')
         print('         Refer to error 06 in easyPBC user guide.')
         leftsxyz={}
         error=True
        if len(ftedgexyz) != len(btedgexyz) or len(btedgexyz) != len(bbedgexyz) or len(bbedgexyz) != len(ftedgexyz):
         print('Warning: Number of nodes in front-top ,back-top, back-bottom, front-bottom (ftedge, btedge, bbedge and fbedge) are not equal. These sets will not be created!!')
         print('         Refer to error 06 in easyPBC user guide.')
         ftedgexyz={}
         error=True
        if len(fledgexyz) != len(bledgexyz) or len(bledgexyz) != len(bredgexyz) or len(bredgexyz) != len(fredgexyz):
         print('Warning: Number of nodes in front-left, back-left, back-right, front-right edge (fledge, bledge, bredge and fredge) are not equal. These sets will not be created!!')
         print('         Refer to error 06 in easyPBC user guide.')
         fledgexyz={}
         error=True
        if len(ltedgexyz) != len(rtedgexyz) or len(rtedgexyz) != len(rbedgexyz) or len(rbedgexyz) != len(lbedgexyz):
         print('Warning: Number of nodes in left-top, right-top, right-bottom, front-bottom edge (ltedge, rtedge, rbedge and fbedge). are not equal. These sets will not be created!!')
         print('         Refer to error 06 in easyPBC user guide.')
         ltedgexyz={}
         error=True
        if len(frontbcxyz) != len(backbcxyz):
         print('Warning: Number of Nodes in Front BC surface (frontbc) not equal to number of nodes in Back BC surface (backbc). These sets will not be created!!')
         print('         Refer to error 06 troubleshooting in easyPBC user guide.')
         frontbcxyz={}
         error=True
        if len(topbcxyz) != len(botbcxyz):
         print('Warning: Number of Nodes in Top BC surface (topbc) not equal to number of nodes in Bottom BC surface (botbc). These sets will not be created!!')
         print('         Refer to error 06 in easyPBC user guide.')
         topbcxyz={}
         error=True
        if len(leftbcxyz) != len(rightbcxyz):
         print('Warning: Number of Nodes in Left BC surface (leftbc) not equal to number of nodes in Right BC surface (rightbc). These sets will not be created!!')
         print('         Refer to error 06 in easyPBC user guide.')
         leftbcxyz={}
         error=True

        ## Sorting and appending sets ##
        for i in frontsxyz.keys():
                for k in backsxyz.keys():
                        if abs(frontsxyz[i][1] - backsxyz[k][1])<=meshsens and abs(frontsxyz[i][2] - backsxyz[k][2])<=meshsens:
                                fronts.append(i)
                                backs.append(k)

        if len(frontsxyz)!= len(fronts) or len(backsxyz)!= len(backs):
            print('Warning: Node(s) in Front and/or Back surface (fronts and/or backs) was not imported. effected sets will not be created!!')
            print('         Refer to error 07 in easyPBC user guide and created Error set (if applicable).')
            for i, k in zip(frontsxyz.keys(),backsxyz.keys()):
                    if i not in fronts:
                            errorset.append(i)
                    if k not in backs:
                            errorset.append(k)
            fronts=[]
            backs=[]
            error=True                    
        if len(fronts)!=len(set(fronts)) or len(backs)!=len(set(backs)):
            print('Warning: Node(s) in either Front or Back surface (fronts or backs) being linked with more than one opposite node. effected sets will not be created!!')
            print('         Refer to error 08 in easyPBC user guide.')
            fronts=[]
            backs=[]
            error=True

        for i in topsxyz.keys():
            for k in botsxyz.keys():
                if abs(topsxyz[i][0] - botsxyz[k][0]) <=meshsens and abs(topsxyz[i][2] - botsxyz[k][2]) <=meshsens:
                    tops.append(i)
                    bots.append(k)
        if len(topsxyz)!= len(tops) or len(botsxyz)!= len(bots):
            print('Warning: Node(s) in Top and/or Bottom surface (tops and/or bots) was not imported. effected sets will not be created!!')
            print('         Refer to error 07 in easyPBC user guide and created Error set (if applicable).')
            for i, k in zip(topsxyz.keys(),botsxyz.keys()):
                    if i not in tops:
                            errorset.append(i)
                    if k not in bots:
                            errorset.append(k)
            tops=[]
            bots=[]
            error=True
        if len(tops)!=len(set(tops)) or len(bots)!=len(set(bots)):
            print('Warning: Node(s) in either Top or Bottom surface (tops or bots) being linked with more than one opposite node. effected sets will not be created!!')
            print('         Refer to error 08 in easyPBC user guide.')
            tops=[]
            bots=[]
            error=True


        for i in leftsxyz.keys():
            for k in rightsxyz.keys():
                if abs(leftsxyz[i][0] - rightsxyz[k][0])<=meshsens and abs(leftsxyz[i][1] - rightsxyz[k][1]) <=meshsens:
                    lefts.append(i)
                    rights.append(k)
        if len(leftsxyz)!= len(lefts) or len(rightsxyz)!= len(rights):
            print('Warning: Node(s) in Left and/or Right surface (lefts and/or rights) was not imported. effected sets will not be created!!')
            print('         Refer to error 07 in easyPBC user guide and created Error set (if applicable).')
            for i, k in zip(leftsxyz.keys(),rightsxyz.keys()):
                    if i not in lefts:
                            errorset.append(i)
                    if k not in rights:
                            errorset.append(k)                    
            lefts=[]
            rights=[]
            error=True                    
        if len(lefts)!=len(set(lefts)) or len(rights)!=len(set(rights)):
            print('Warning: Node(s) in either Left or Right surface (lefts or rights) being linked with more than one opposite node. effected sets will not be created!!')
            print('         Refer to error 08 in easyPBC user guide.')
            lefts=[]
            rights=[]
            error=True

        for i in frontbcxyz.keys():
            for k in backbcxyz.keys():
                if abs(frontbcxyz[i][1] - backbcxyz[k][1])<=meshsens and abs(frontbcxyz[i][2] - backbcxyz[k][2])<=meshsens:
                    frontbc.append(i)
                    backbc.append(k)
        if len(frontbcxyz)!= len(frontbc) or len(backbcxyz)!= len(backbc):
            print('Warning: Node(s) in Front BC and/or Back BC surface (frontbc and/or backbc) was not imported. effected sets will not be created!!')
            print('         Refer to error 07 in easyPBC user guide and created Error set (if applicable).')
            for i, k in zip(frontbcxyz.keys(),backbcxyz.keys()):
                    if i not in frontbc:
                            errorset.append(i)
                    if k not in backbc:
                            errorset.append(k)
            frontbc=[]
            backbc=[]
            error=True
        if len(frontbc)!=len(set(frontbc)) or len(backbc)!=len(set(backbc)):
            print('Warning: Node(s) in either Front BC or Back BC surface (frontbc or backbc) being linked with more than one opposite node. effected sets will not be created!!')
            print('         Refer to error 08 in easyPBC user guide.')
            frontbc=[]
            backbc=[]
            error=True


        for i in topbcxyz.keys():
            for k in botbcxyz.keys():
                if abs(topbcxyz[i][0] - botbcxyz[k][0]) <=meshsens and abs(topbcxyz[i][2] - botbcxyz[k][2]) <=meshsens:
                    topbc.append(i)
                    botbc.append(k)
        if len(topbcxyz)!= len(topbc) or len(botbcxyz)!= len(botbc):
            print('Warning: Node(s) in Top BC and/or Bottom BC surface (topbc and/or botbc) was not imported. effected sets will not be created!!')
            print('         Refer to error 07 in easyPBC user guide and created Error set (if applicable).')
            for i, k in zip(topbcxyz.keys(),botbcxyz.keys()):
                    if i not in topbc:
                            errorset.append(i)
                    if k not in botbc:
                            errorset.append(k)
            topbc=[]
            botbc=[]
            error=True
        if len(topbc)!=len(set(topbc)) or len(botbc)!=len(set(botbc)):
            print('Warning: Node(s) in either Top BC or Bottom BC surface (topbc or botbc) being linked with more than one opposite node. effected sets will not be created!!')
            print('         Refer to error 08 in easyPBC user guide.')
            topbc=[]
            botbc=[]
            error=True


        for i in leftbcxyz.keys():
            for k in rightbcxyz.keys():
                if abs(leftbcxyz[i][0] - rightbcxyz[k][0])<=meshsens and abs(leftbcxyz[i][1] - rightbcxyz[k][1]) <=meshsens:
                    leftbc.append(i)
                    rightbc.append(k)
        if len(leftbcxyz)!= len(leftbc) or len(rightbcxyz)!= len(rightbc):
            print('Warning: Node(s) in Left BC and/or Right BC surface (lefts and/or rights) was not imported. effected sets will not be created!!')
            print('         Refer to error 07 in easyPBC user guide and created Error set (if applicable).')
            for i, k in zip(leftbcxyz.keys(),rightbcxyz.keys()):
                    if i not in leftbc:
                            errorset.append(i)
                    if k not in rightbc:
                            errorset.append(k)            
            leftbc=[]
            rightbc=[]
            error=True
        if len(leftbc)!=len(set(leftbc)) or len(rightbc)!=len(set(rightbc)):
            print('Warning: Node(s) in either Left BC or Right BC surface (leftbc or rightbc) being linked with more than one opposite node. effected sets will not be created!!')
            print('         Refer to error 08 in easyPBC user guide.')
            leftbc=[]
            rightbc=[]
            error=True


        for i in ftedgexyz.keys():
            for k in btedgexyz.keys():
                if abs(ftedgexyz[i][1] - btedgexyz[k][1])<=meshsens and abs(ftedgexyz[i][2] - btedgexyz[k][2])<=meshsens:
                    ftedge.append(i)
                    btedge.append(k)
        for i in btedge:
            for k in bbedgexyz.keys():
                if abs(btedgexyz[i][0] - bbedgexyz[k][0]) <=meshsens and abs(btedgexyz[i][2] - bbedgexyz[k][2]) <=meshsens:
                    bbedge.append(k)    
        for i in bbedge:
            for k in fbedgexyz.keys():
                if abs(bbedgexyz[i][1] - fbedgexyz[k][1]) <=meshsens and abs(bbedgexyz[i][2] - fbedgexyz[k][2]) <=meshsens:
                    fbedge.append(k) 
        if len(ftedge)!=len(set(ftedge)) or len(btedge)!=len(set(btedge)) or len(bbedge)!=len(set(bbedge)) or len(fbedge)!=len(set(fbedge)):
            print('Warning: Node(s) in either front-top, back-top, back-bottom and front-bottom edge(ftedge, btedge, bbedge and fbedge) being linked with more than one opposite node. effected sets will not be created!!')
            print('         Refer to error 08 in easyPBC user guide.')
            ftedge=[]
            btedge=[]
            bbedg=[]
            fbedge=[]
            error==True
        if len(ftedgexyz)!= len(ftedge) or len(btedgexyz)!= len(btedge) or len(bbedgexyz)!= len(bbedge) or len(fbedgexyz)!= len(fbedge):
            print('Warning: Node(s) in front-top, back-top, back-bottom and front-bottom edge(ftedge, btedge, bbedge and fbedge) were not imported. these sets will not be created!!')
            print('         Refer to error 07 in easyPBC user guide and created Error set (if applicable).')
            ftedge=[]
            btedge=[]
            bbedg=[]
            fbedge=[]
            error=True

        for i in ltedgexyz.keys():
            for k in rtedgexyz.keys():
                if abs(ltedgexyz[i][0] - rtedgexyz[k][0])<=meshsens and abs(ltedgexyz[i][1] - rtedgexyz[k][1])<=meshsens:
                    ltedge.append(i)
                    rtedge.append(k)
        for i in rtedge:
            for k in rbedgexyz.keys():
                if abs(rtedgexyz[i][0] - rbedgexyz[k][0])<=meshsens and abs(rtedgexyz[i][2] - rbedgexyz[k][2])<=meshsens:
                    rbedge.append(k)    
        for i in rbedge:
            for k in lbedgexyz.keys():
                if abs(rbedgexyz[i][0] - lbedgexyz[k][0])<=meshsens and abs(rbedgexyz[i][1] - lbedgexyz[k][1])<=meshsens:
                    lbedge.append(k) 

        if len(ltedge)!=len(set(ltedge)) or len(rtedge)!=len(set(rtedge)) or len(rbedge)!=len(set(rbedge)) or len(lbedge)!=len(set(lbedge)):
            print('Warning: Node(s) in either front-top, back-bottom and front-bottom edge(ltedge, rtedge, rbedge and lbedge) being linked with more than one opposite node. effected sets will not be created!!')
            print('         Refer to error 08 in easyPBC user guide.')
            ltedge=[]
            rtedge=[]
            rbedg=[]
            lbedge=[]
            error=True

        if len(ltedgexyz)!= len(ltedge) or len(rtedgexyz)!= len(rtedge) or len(rbedgexyz)!= len(rbedge) or len(lbedgexyz)!= len(lbedge):
            print('Warning: Node(s) in left-top, right-top, right-bottom, left-bottom edge (ltedge, rtedge, rbedge and lbedge) were not imported. these sets will not be created!!')
            print('         Refer to error 07 in easyPBC user guide and created Error set (if applicable).')
            ltedge=[]
            rtedge=[]
            rbedg=[]
            lbedge=[]
            error=True

        for i in fledgexyz.keys():
            for k in bledgexyz.keys():
                if abs(fledgexyz[i][1] - bledgexyz[k][1])<=meshsens and abs(fledgexyz[i][2] - bledgexyz[k][2])<=meshsens:
                    fledge.append(i)
                    bledge.append(k)
        for i in bledge:
            for k in bredgexyz.keys():
                if abs(bledgexyz[i][0] - bredgexyz[k][0])<=meshsens and abs(bledgexyz[i][1] - bredgexyz[k][1])<=meshsens:
                    bredge.append(k)    
        for i in bredge:
            for k in fredgexyz.keys():
                if abs(bredgexyz[i][1] - fredgexyz[k][1])<=meshsens and abs(bredgexyz[i][2] - fredgexyz[k][2])<=meshsens:
                    fredge.append(k) 

        if len(fledge)!=len(set(fledge)) or len(bledge)!=len(set(bledge)) or len(bredge)!=len(set(bredge)) or len(fredge)!=len(set(fredge)):
            print('Warning: Node(s) in either front-left, back-left, back-right and front-right edge(fledge, bledge, bredge and fredge) being linked with more than one opposite node. effected sets will not be created!!')
            print('         Refer to error 08 in easyPBC user guide.')
            fledge=[]
            bledge=[]
            bredg=[]
            fredge=[]
            error=True
        if len(fledgexyz)!= len(fledge) or len(bledgexyz)!= len(bledge) or len(bredgexyz)!= len(bredge) or len(fredgexyz)!= len(fredge):
            print('Warning: Node(s) in front-left, back-left, back-right and front-right edge (fledge, bledge, bredge and fredge) were not imported. these sets will not be created!!')
            print('         Refer to error 07 in easyPBC user user guide.')
            fledge=[]
            bledge=[]
            bredg=[]
            fredge=[]
            error=True

        # NOTE: do NOT overwrite the coordinate-paired lists with sort-by-label
        # versions. The strict point-to-point PBC builder depends on `fronts[i]`
        # being the geometric pair of `backs[i]` etc., which is set up by the
        # coordinate-matching block above. Sorting by label here would destroy
        # that pairing and force a nearest-node fallback.
        error = False
        if not fronts or not backs or not lefts or not rights or not tops or not bots:
            print('Warning: Non-matching PBC face-interior nodes were not fully detected.')
            print('         This can be acceptable for very coarse meshes such as a single-element test.')
        if not frontbc or not backbc or not leftbc or not rightbc or not topbc or not botbc:
            print('Warning: Non-matching PBC boundary-condition nodes were not fully detected.')
            error = True
        if not c1 or not c2 or not c3 or not c4 or not c5 or not c6 or not c7 or not c8:
            print('Warning: Corner nodes were not fully detected for rigid-body control.')
            error = True

        ## Creating ABAQUS sets ##
        _pbc_create_node_set(a, instanceName, 'c1', c1)
        _pbc_create_node_set(a, instanceName, 'c2', c2)
        _pbc_create_node_set(a, instanceName, 'c3', c3)
        _pbc_create_node_set(a, instanceName, 'c4', c4)
        _pbc_create_node_set(a, instanceName, 'c5', c5)
        _pbc_create_node_set(a, instanceName, 'c6', c6)
        _pbc_create_node_set(a, instanceName, 'c7', c7)
        _pbc_create_node_set(a, instanceName, 'c8', c8)
        _pbc_create_node_set(a, instanceName, 'ftedge', ftedge)
        _pbc_create_node_set(a, instanceName, 'fbedge', fbedge)
        _pbc_create_node_set(a, instanceName, 'btedge', btedge)
        _pbc_create_node_set(a, instanceName, 'bbedge', bbedge)
        _pbc_create_node_set(a, instanceName, 'fledge', fledge)
        _pbc_create_node_set(a, instanceName, 'fredge', fredge)
        _pbc_create_node_set(a, instanceName, 'bledge', bledge)
        _pbc_create_node_set(a, instanceName, 'bredge', bredge)
        _pbc_create_node_set(a, instanceName, 'ltedge', ltedge)
        _pbc_create_node_set(a, instanceName, 'lbedge', lbedge)
        _pbc_create_node_set(a, instanceName, 'rtedge', rtedge)
        _pbc_create_node_set(a, instanceName, 'rbedge', rbedge)
        _pbc_create_node_set(a, instanceName, 'fronts', fronts)
        _pbc_create_node_set(a, instanceName, 'backs', backs)
        _pbc_create_node_set(a, instanceName, 'lefts', lefts)
        _pbc_create_node_set(a, instanceName, 'rights', rights)
        _pbc_create_node_set(a, instanceName, 'tops', tops)
        _pbc_create_node_set(a, instanceName, 'bots', bots)
        _pbc_create_node_set(a, instanceName, 'frontbc', frontbc)
        _pbc_create_node_set(a, instanceName, 'backbc', backbc)
        _pbc_create_node_set(a, instanceName, 'leftbc', leftbc)
        _pbc_create_node_set(a, instanceName, 'rightbc', rightbc)
        _pbc_create_node_set(a, instanceName, 'topbc', topbc)
        _pbc_create_node_set(a, instanceName, 'botbc', botbc)
        print('============================= End of Sets Creation =============================')
        
        # Create analysis step
        if 'Step-1' in mdb.models[modelName].steps.keys():
            del mdb.models[modelName].steps['Step-1']
        
        # Step-1 options (all set from the GUI):
        #   analysis_procedure      : STATIC (default) or QUASI_STATIC_DYNAMIC
        #   stabilization_magnitude : dissipated-energy fraction for *Static
        #   unsymmetric_solver      : opt-in UNSYMMETRIC storage (about 2x memory/time)
        # With *Static and no inertia term the UMAT must use the secant
        # tangent (IDMTAN=0); the consistent tangent is indefinite in softening.
        # Implicit dynamics needs a mass matrix, so ensure_material_density adds
        # a *Density to any material missing one.
        # GUI-driven stabilization magnitude (DEF); None -> 2e-4 default.
        _stab_mag = 2e-4 if stabilization_magnitude is None else float(stabilization_magnitude)
        if not (_stab_mag > 0.0):
            _stab_mag = 2e-4
        # GUI-driven step type: 'STATIC' (default) or 'QUASI_STATIC_DYNAMIC'.
        _proc = str(analysis_procedure).upper() if analysis_procedure else 'STATIC'
        if _proc == 'QUASI_STATIC_DYNAMIC':
            # *Dynamic, application=QUASI-STATIC.  The M/(beta*dt^2) inertia
            # term supplies a force basis through the near-zero-force first-
            # yield / softening windows where pure *Static stalls ("ZERO FORCE
            # EVERYWHERE").  Implicit dynamics needs a mass matrix, so
            # ensure_material_density adds a *Density wherever it is missing.
            # NB: inertia regularization perturbs the curve Melro defines as a
            # *static* result; monitor KE_Ratio (ALLKE/ALLIE) in energy_check.
            dyn_step_kwargs = dict(
                previous='Initial',
                description='RVE Multi-axial Loading (quasi-static implicit dynamics)',
                timePeriod=1.0, maxNumInc=100000,
                application=QUASI_STATIC,
                initialInc=0.001, minInc=1e-9, maxInc=0.01,
                nlgeom=ON if large_deformation else OFF,
            )
            if unsymmetric_solver:
                dyn_step_kwargs['matrixStorage'] = UNSYMMETRIC
            mdb.models[modelName].ImplicitDynamicsStep(name='Step-1', **dyn_step_kwargs)
            ensure_material_density(mdb.models[modelName])
        else:
            static_step_kwargs = dict(
                previous='Initial',
                description='RVE Multi-axial Loading Analysis',
                timePeriod=1.0, maxNumInc=10000,
                initialInc=1e-5, minInc=1e-8, maxInc=0.01,
                nlgeom=ON if large_deformation else OFF,
                stabilizationMethod=DISSIPATED_ENERGY_FRACTION,
                stabilizationMagnitude=_stab_mag,
                adaptiveDampingRatio=0.05,
                continueDampingFactors=False,
            )
            if unsymmetric_solver:
                static_step_kwargs['matrixStorage'] = UNSYMMETRIC
            mdb.models[modelName].StaticStep(name='Step-1', **static_step_kwargs)

        # ---- Solution Controls (SYNCED from PBC_UDFRP_Elastoplastic.py) ----
        # These were missing in this interface kernel, so cohesive RVE jobs ran
        # on Abaqus defaults (R_n=0.005, C_n=0.01, IC=16, I_A=5).  At the
        # damage/debonding band the residual stalls at a noise floor (~1e-8)
        # that the strict default check falsely flags as "DIVERGING" -> TOO
        # MANY ATTEMPTS abort (the recurring single-node failure).
        #   displacementField pos 1: R_n = 0.02 (force residual; was 0.005)
        #                    pos 2: C_n = 1.0  (disp correction; was 0.01)
        #   timeIncrementation: discontinuous I0=8, IR=10; IC=30 (pos4);
        #                       I_A=10 (pos8, max cut-backs per increment).
        mdb.models[modelName].steps['Step-1'].control.setValues(
            # Line search: scales the Newton correction so the idam=1 tangent
            # jump / damage softening does not overshoot into divergence.
            lineSearch=(4.0, 1.0, 0.0001, 0.25, 0.10),
            allowPropagation=OFF,
            discontinuous=ON,
            displacementField=(0.02, 1.0, 0.0, 0.0, 0.02, 1e-05,
                               0.001, 1e-08, 1.0, 1e-05, 1e-08),
            timeIncrementation=(8.0, 10.0, 9.0, 30.0,
                                10.0, 4.0, 12.0, 10.0, 6.0, 3.0, 50.0),
        )
        '''
        # For UMAT
        mdb.models[modelName].ImplicitDynamicsStep(name='Step-1', previous='Initial', nlgeom=ON,
                                                   timePeriod=1.0,maxNumInc=1000, initialInc=0.001, minInc=1e-10
                                                   )

        # For VUMAT
        mdb.models[modelName].ExplicitDynamicsStep(name='Step-1', previous='Initial',timePeriod=1.0,
                                                massScaling=((SEMI_AUTOMATIC, MODEL, AT_BEGINNING, 0.0, 0.0, 
                                                              BELOW_MIN, 1, 0, 0.0, 0.0, 0, None),)
                                            )
        '''
        
        if error == True:
            print(('Error(s) found during sets creation, please check the error No.(s) above with EasyPBC user guide.'))
            if errorset:
                a.SetFromNodeLabels(name='Error set', nodeLabels=((instanceName,errorset),))
            return False
            
        if error==False:
            for i,k in zip(tops,bots):
                a.SetFromNodeLabels(name='tops%s' % (i), nodeLabels=((instanceName,[i]),))
                a.SetFromNodeLabels(name='bots%s' % (k), nodeLabels=((instanceName,[k]),))
    
            for i,k in zip(fronts,backs):
                a.SetFromNodeLabels(name='fronts%s' % (i), nodeLabels=((instanceName,[i]),))
                a.SetFromNodeLabels(name='backs%s' % (k), nodeLabels=((instanceName,[k]),))
    
            for i,k in zip(lefts,rights):
                a.SetFromNodeLabels(name='lefts%s' % (i), nodeLabels=((instanceName,[i]),))
                a.SetFromNodeLabels(name='rights%s' % (k), nodeLabels=((instanceName,[k]),))
    
            for i,k,j,l in zip(ftedge,btedge,bbedge,fbedge):
                a.SetFromNodeLabels(name='ftedge%s' % (i), nodeLabels=((instanceName,[i]),))
                a.SetFromNodeLabels(name='btedge%s' % (k), nodeLabels=((instanceName,[k]),))
                a.SetFromNodeLabels(name='bbedge%s' % (j), nodeLabels=((instanceName,[j]),))
                a.SetFromNodeLabels(name='fbedge%s' % (l), nodeLabels=((instanceName,[l]),))
    
            for i,k,j,l in zip(fledge,bledge,bredge,fredge):
                a.SetFromNodeLabels(name='fledge%s' % (i), nodeLabels=((instanceName,[i]),))
                a.SetFromNodeLabels(name='bledge%s' % (k), nodeLabels=((instanceName,[k]),))
                a.SetFromNodeLabels(name='bredge%s' % (j), nodeLabels=((instanceName,[j]),))
                a.SetFromNodeLabels(name='fredge%s' % (l), nodeLabels=((instanceName,[l]),))
    
            for i,k,j,l in zip(ltedge,lbedge,rbedge,rtedge):
                a.SetFromNodeLabels(name='ltedge%s' % (i), nodeLabels=((instanceName,[i]),))
                a.SetFromNodeLabels(name='lbedge%s' % (k), nodeLabels=((instanceName,[k]),))
                a.SetFromNodeLabels(name='rbedge%s' % (j), nodeLabels=((instanceName,[j]),))
                a.SetFromNodeLabels(name='rtedge%s' % (l), nodeLabels=((instanceName,[l]),))
    
            for i,k in zip(topbc,botbc):
                a.SetFromNodeLabels(name='topbc%s' % (i), nodeLabels=((instanceName,[i]),))
                a.SetFromNodeLabels(name='botbc%s' % (k), nodeLabels=((instanceName,[k]),))
    
            for i,k in zip(frontbc,backbc):
                a.SetFromNodeLabels(name='frontbc%s' % (i), nodeLabels=((instanceName,[i]),))
                a.SetFromNodeLabels(name='backbc%s' % (k), nodeLabels=((instanceName,[k]),))
    
            for i,k in zip(leftbc,rightbc):
                a.SetFromNodeLabels(name='leftbc%s' % (i), nodeLabels=((instanceName,[i]),))
                a.SetFromNodeLabels(name='rightbc%s' % (k), nodeLabels=((instanceName,[k]),))

            active_components = []
            if abs(epsilon_1) > 1e-12:
                active_components.append(('E11', 'RP1', (Dispx, UNSET, UNSET)))
            if abs(epsilon_2) > 1e-12:
                active_components.append(('E22', 'RP2', (UNSET, Dispy, UNSET)))
            if abs(epsilon_3) > 1e-12:
                active_components.append(('E33', 'RP3', (UNSET, UNSET, Dispz)))
            if abs(gamma_12) > 1e-12:
                active_components.append(('G12', 'RP4', (Dispxy_x, Dispxy_y, UNSET)))
            if abs(gamma_31) > 1e-12:
                active_components.append(('G13', 'RP5', (Dispzx_x, UNSET, Dispzx_z)))
            if abs(gamma_23) > 1e-12:
                active_components.append(('G23', 'RP6', (UNSET, Dispyz_y, Dispyz_z)))

            if not active_components:
                print('Error: No loading specified!')
                return False

            loading_type = legacy_loading_type if legacy_loading_type else active_components[0][0]
            loading_label_to_use = loading_label if str(loading_label).strip() != '' else loading_type
            job_name = build_elastoplastic_job_name(
                modelName, loading_label_to_use, temperature_celsius
            )
            print("Loading type: %s" % loading_type)
            print("Loading label: %s" % loading_label_to_use)
            print("Job name: %s" % job_name)
            
            results_data = {}
            results_data['loading_type'] = loading_type
            results_data['loading_label'] = loading_label_to_use
            results_data['job_name'] = job_name

            ## Build strict point-to-point PBC equations for the active loading
            ## combination. macro_map encodes the macro-displacement terms per
            ## (face, component) and is assembled by superposing the normal
            ## contribution (branch 1) and the shear contribution (branch 2).
            ## This gives:
            ##   * pure normal      -> only the 3 diagonal entries (RP1/RP2/RP3)
            ##   * pure shear       -> only the 6 off-diagonal entries (RP4/RP5/RP6)
            ##                         with NO diagonal entries. Keeping the
            ##                         diagonals out here matters: a single-axis
            ##                         shear form can carry residual diagonal terms
            ##                         that vanish on their own but contaminate
            ##                         combined loads.
            ##   * mixed (orthogonal) -> straight superposition
            ## NOTE: For "coupled" biaxial pairs like E1+G12 / E1+G31 / E2+G23 /
            ## E2+G12 / E3+G23 / E3+G31 (where the normal and shear share an axis),
            ## the superposition form used here is the physically consistent
            ## extension. Combined coupled cases should still be sanity-checked
            ## against an independent solution before publishing.
            active_normal_components = [c for c in active_components if c[0] in ['E11', 'E22', 'E33']]
            active_shear_components  = [c for c in active_components if c[0] in ['G12', 'G13', 'G23']]
            has_normal = len(active_normal_components) > 0
            has_shear  = len(active_shear_components) > 0

            macro_map = {}
            if has_normal:
                # Branch 1: normal (diagonal) macro-displacement terms.
                macro_map[('x', 1)] = [(-1.0, 'RP1', 1)]
                macro_map[('y', 2)] = [(-1.0, 'RP2', 2)]
                macro_map[('z', 3)] = [(-1.0, 'RP3', 3)]
            if has_shear:
                # Branch 2: shear (off-diagonal) macro-displacement terms.
                macro_map[('x', 2)] = [(-1.0, 'RP4', 2)]
                macro_map[('x', 3)] = [(-1.0, 'RP5', 3)]
                macro_map[('y', 1)] = [(-1.0, 'RP4', 1)]
                macro_map[('y', 3)] = [(-1.0, 'RP6', 3)]
                macro_map[('z', 1)] = [(-1.0, 'RP5', 1)]
                macro_map[('z', 2)] = [(-1.0, 'RP6', 2)]

            build_multiaxial_strict_pbc_equations_3d(
                modelName, a, instanceName,
                fronts, backs, tops, bots, lefts, rights,
                ftedge, btedge, bbedge, fbedge,
                fledge, bledge, bredge, fredge,
                ltedge, lbedge, rbedge, rtedge,
                macro_map,
                equation_prefix='StrictPBC-{}'.format(sanitize_loading_label(loading_label_to_use))
            )
            for layerIndex, layerNodes in enumerate(interfaceDuplicateLayers, start=1):
                _interface_add_elastoplastic_layer_pbc(
                    modelName, a, instanceName, layerNodes,
                    (Max, May, Maz, Mnx, Mny, Mnz), meshsens, macro_map,
                    'InterfacePBC-L{}-{}'.format(layerIndex, sanitize_loading_label(loading_label_to_use))
                )

            
            region_c6 = a.sets['c6']
            mdb.models[modelName].DisplacementBC(name='BC-Fix-c6', createStepName='Step-1',
                region=region_c6, u1=0.0, u2=0.0, u3=0.0)

            active_shear_rps = []
            for component_name, rp_name, displacement_values in active_components:
                region = a.sets[rp_name]
                mdb.models[modelName].DisplacementBC(
                    name='BC-{}'.format(component_name),
                    createStepName='Step-1',
                    region=region,
                    u1=displacement_values[0],
                    u2=displacement_values[1],
                    u3=displacement_values[2]
                )
                if component_name in ['G12', 'G13', 'G23']:
                    active_shear_rps.append(rp_name)

            if len(active_shear_components) > 0:
                for rp_name in ['RP4', 'RP5', 'RP6']:
                    if rp_name not in active_shear_rps:
                        mdb.models[modelName].DisplacementBC(
                            name='BC-{}-Zero'.format(rp_name),
                            createStepName='Step-1',
                            region=a.sets[rp_name],
                            u1=0.0, u2=0.0, u3=0.0
                        )
            
            print("Constraints and BCs applied successfully for %s" % loading_label_to_use)
            
            # Set up output requests
            
            for req in mdb.models[modelName].fieldOutputRequests.keys():
                if req != 'F-Output-1':
                    del mdb.models[modelName].fieldOutputRequests[req]
            
            for req in mdb.models[modelName].historyOutputRequests.keys():
                if req != 'H-Output-1':
                    del mdb.models[modelName].historyOutputRequests[req]
            
            # Resolve field-output sampling: GUI value (field_output_intervals)
            # overrides the module default; None falls back to the constant.
            _n_intervals = (FIELD_OUTPUT_NUM_INTERVALS if field_output_intervals is None
                            else int(field_output_intervals))
            _fo_vars = ('S', 'PE', 'PEEQ', 'PEMAG', 'LE', 'U', 'RF', 'CF',
                        'CSTRESS', 'CDISP', 'SDV', 'STATUS', 'IVOL',
                        'CSDMG', 'CSMAXSCRT', 'CSQUADSCRT')
            if _n_intervals and _n_intervals > 0:
                mdb.models[modelName].fieldOutputRequests['F-Output-1'].setValues(
                    variables=_fo_vars,
                    numIntervals=_n_intervals, timeMarks=OFF
                )
            else:
                mdb.models[modelName].fieldOutputRequests['F-Output-1'].setValues(
                    variables=_fo_vars, frequency=1
                )

            # History output request for reference points
            h_output_counter = 1
            for rp_name in ['RP1', 'RP2', 'RP3', 'RP4', 'RP5', 'RP6']:
                if rp_name in a.sets.keys() and is_rp_active_in_constraints(modelName, rp_name):
                    region = a.sets[rp_name]
                    if h_output_counter == 1:
                        # modify the existing H-Output-1
                        mdb.models[modelName].historyOutputRequests['H-Output-1'].setValues(variables=PRESELECT,region=region,frequency=1)
                    else:
                        # create a new history-output request
                        mdb.models[modelName].HistoryOutputRequest(name='H-Output-%d' % h_output_counter, createStepName='Step-1',variables=PRESELECT,region=region,frequency=1)
                    h_output_counter += 1

            mdb.models[modelName].HistoryOutputRequest(
                name='H-Output-UMAT-Energy',
                createStepName='Step-1',
                variables=('ALLAE', 'ALLCD', 'ALLDMD', 'ALLEE', 'ALLFD', 'ALLIE',
                           'ALLJD', 'ALLKE', 'ALLKL', 'ALLPD', 'ALLQB', 'ALLSE',
                           'ALLSD', 'ALLVD', 'ALLWK', 'ETOTAL'),
                frequency=1
            )
            print("UMAT output enabled: field SDV/STATUS.")
            
            # Create and submit job. Delete any prior job with the same name so
            # re-runs do not collide (timestamp-free job names mean repeated runs of
            # the same case reuse the same job slot, which is the friendly behavior
            # for opening the ODB straight from Abaqus's Jobs view).
            if job_name in mdb.jobs.keys():
                del mdb.jobs[job_name]
            mdb.Job(name=job_name, model=modelName, description='Complete RVE Multi-axial Analysis',
                type=ANALYSIS, atTime=None, waitMinutes=0, waitHours=0,queue=None, memory=90, memoryUnits=PERCENTAGE,
                getMemoryFromAnalysis=True, explicitPrecision=SINGLE,nodalOutputPrecision=SINGLE, echoPrint=OFF, 
                modelPrint=OFF, contactPrint=OFF, historyPrint=OFF,userSubroutine=umat_file, scratch='', multiprocessingMode=DEFAULT,
                numCpus=CPUs, numDomains=CPUs, numGPUs=0)
            
            submission_time = time.time()
            mdb.jobs[job_name].submit(consistencyChecking=OFF)
            mdb.jobs[job_name].waitForCompletion()
            analysis_time = time.time() - submission_time
            
            odb_path = os.path.join(path, job_name + '.odb')
            odb = session.openOdb(name=odb_path)
            step_name = 'Step-1'
            frame_number = -1
            
            rve_dimensions = {'L': L, 'H': H, 'W': W}
            
            # 3. Extract reference point results with stress-strain calculations
            # Extract time history for all frames with stress-strain data
            rp_time_history = extract_reference_point_time_history(odb, step_name, rve_dimensions)
            
            # Also extract final frame results for effective properties calculation
            rp_final_results = extract_reference_point_results_single_frame(odb, step_name, frame_number, rve_dimensions)
            
            results_data['reference_points_history'] = rp_time_history
            results_data['reference_points_final'] = rp_final_results
            
            # For backward compatibility, use final results for properties calculation
            rp_results = rp_final_results
            
            # 4. Calculate volume averages
            element_results = extract_element_results(odb, step_name, frame_number, instanceName)
            results_data['element'] = element_results
            
            if save_volume_avg and element_results:
                volume_averages = calculate_volume_averages(element_results)
                results_data['volume_averages'] = volume_averages
            else:
                volume_averages = {}

            # 4b. Physically-sourced stress-concentration factors for the
            # bridging+SCF UMAT (SCFt, yield concentration) -- read from the RVE
            # field, no guessing.  Must run while the ODB is open.
            conc_files = []
            try:
                conc_files, conc_summary = extract_concentration_factors(
                    odb, step_name, instanceName, rp_time_history,
                    output_dir, output_model_name,
                    loading_label=loading_label_to_use)
                results_data['concentration_summary'] = conc_summary
            except Exception as _ce:
                print("  concentration extraction skipped: %s" % str(_ce))

            # 4.6 Whole-model energy verification CSV (must run while the ODB is open)
            _energy_label = sanitize_loading_label(loading_label_to_use)
            _energy_temp_lbl = format_temperature_file_label(temperature_celsius)
            if _energy_temp_lbl != '':
                _energy_label = '{}_{}'.format(_energy_label, _energy_temp_lbl)
            energy_csv = extract_energy_history(
                odb, step_name, output_dir, output_model_name,
                loading_label=_energy_label)

            # Close ODB
            odb.close()
            
            # Save results to CSV files (timestamps removed; subdirectory uniqueness already enforced upstream)
            file_loading_label = sanitize_loading_label(loading_label_to_use)
            temperature_file_label = format_temperature_file_label(temperature_celsius)
            if temperature_file_label != '':
                file_loading_label = '{}_{}'.format(file_loading_label, temperature_file_label)
            applied_strains = {
                'epsilon_x': epsilon_x, 'epsilon_y': epsilon_y, 'epsilon_z': epsilon_z,
                'gamma_xy': gamma_xy, 'gamma_yz': gamma_yz, 'gamma_zx': gamma_zx
            }
            
            saved_files = []

            # Register the concentration-factor CSVs (produced while ODB open)
            try:
                saved_files.extend(conc_files)
            except NameError:
                pass

            # Register the energy-verification CSV produced above (if any)
            try:
                if energy_csv:
                    saved_files.append(energy_csv)
            except NameError:
                pass

            # 4. Save reference point stress-strain time history
            if 'reference_points_history' in results_data and results_data['reference_points_history']:
                history_files = save_reference_point_time_history(
                    results_data['reference_points_history'],
                    output_dir,
                    output_model_name,
                    applied_strains=applied_strains,
                    loading_label=file_loading_label
                )
                saved_files.extend(history_files)
            # 4.5 save the true stress/strain curve
            if 'reference_points_history' in results_data and results_data['reference_points_history']:
                true_results = calculate_true_stress_strain_from_rp(
                    results_data['reference_points_history'],
                    loading_type,  # this variable must be passed in from above
                    L, H, W
                )
                if true_results:
                    true_file = save_true_stress_strain(
                        true_results,
                        output_dir,
                        output_model_name,
                        file_loading_label
                    )
                    if true_file:
                        saved_files.append(true_file)
            # 5. Save volume averages
            if save_volume_avg and 'volume_averages' in results_data and results_data['volume_averages']:
                avg_filename = os.path.join(output_dir, '{}_volume_averages_{}.csv'.format(output_model_name, file_loading_label))
                avg_fieldnames = list(results_data['volume_averages'].keys())
                
                csvfile, writer = create_csv_writer(avg_filename, avg_fieldnames)
                if writer:
                    writer.writerow(results_data['volume_averages'])
                    close_csv_file(csvfile)
                    saved_files.append(avg_filename)
                    print("  Volume averages: %s" % os.path.basename(avg_filename))
            
            # 6. Calculate and save effective properties and analysis summary
            effective_properties = {}
            if rp_results:
                effective_properties = calculate_effective_properties(rp_results, L, H, W, applied_strains)
            
            # Create comprehensive analysis summary
            summary_filename = os.path.join(output_dir, '{}_analysis_summary_{}.csv'.format(output_model_name, file_loading_label))
            summary_data = {
                'Model': output_model_name,
                'Instance': instanceName,
                'Job_Name': job_name,
                'Loading_Label': loading_label_to_use,
                'Input_Strain_X': epsilon_x,
                'Input_Strain_Y': epsilon_y,
                'Input_Strain_Z': epsilon_z,
                'Input_Shear_XY': gamma_xy,
                'Input_Shear_YZ': gamma_yz,
                'Input_Shear_ZX': gamma_zx,
                'RVE_Length': L,
                'RVE_Height': H,
                'RVE_Width': W,
                'RVE_Volume': L * H * W,
                'Displacement_X': Dispx,
                'Displacement_Y': Dispy,
                'Displacement_Z': Dispz,
                'Num_Nodes': len(results_data.get('nodal', [])),
                'Num_Elements': len(results_data.get('element', [])),
                'Num_Integration_Points': len(results_data.get('element', [])),
                'Analysis_Time_sec': analysis_time,
                'Total_Time_sec': time.time() - start_time,
                'Mesh_Sensitivity': meshsens,
                'CPUs_Used': CPUs
            }
            if temperature_celsius is not None:
                summary_data['Temperature_C'] = float(temperature_celsius)
            
            # Add effective properties to summary
            if effective_properties:
                for key, value in effective_properties.items():
                    summary_data[key] = value
            
            # Add volume averages to summary (with prefix)
            if volume_averages:
                for key, value in volume_averages.items():
                    summary_data['VolAvg_' + key] = value
            
            summary_fieldnames = list(summary_data.keys())
            csvfile, writer = create_csv_writer(summary_filename, summary_fieldnames)
            if writer:
                writer.writerow(summary_data)
                close_csv_file(csvfile)
                saved_files.append(summary_filename)
                
            # Print comprehensive results summary
            print("\n" + "=" * 80)
            print("ANALYSIS RESULTS SUMMARY")
            print("=" * 80)
            
            print("Analysis Parameters:")
            print("  Model: %s, Instance: %s" % (output_model_name, instanceName))
            print("  Applied global strains: epsilon_x=%.6f, epsilon_y=%.6f, epsilon_z=%.6f" % (epsilon_x, epsilon_y, epsilon_z))
            print("  Applied shear strains: gamma_xy=%.6f, gamma_yz=%.6f, gamma_zx=%.6f" % (gamma_xy, gamma_yz, gamma_zx))
            print("  RVE dimensions: L=%.6f, H=%.6f, W=%.6f" % (L, H, W))
            
            if rp_results:
                print("\nReference Point Results:")
                for rp in rp_results:
                    print("  %s: U=[%.6f, %.6f, %.6f], RF=[%.2f, %.2f, %.2f]" % (
                        rp['Reference_Point'], rp['U1'], rp['U2'], rp['U3'],
                        rp['RF1'], rp['RF2'], rp['RF3']))
            
            if effective_properties:
                print("\nCalculated Effective Properties:")
                if effective_properties.get('E1_effective', 0) > 0:
                    print("  E1_effective = %.2f MPa" % effective_properties['E1_effective'])
                if effective_properties.get('E2_effective', 0) > 0:
                    print("  E2_effective = %.2f MPa" % effective_properties['E2_effective'])
                if effective_properties.get('E3_effective', 0) > 0:
                    print("  E3_effective = %.2f MPa" % effective_properties['E3_effective'])
                if effective_properties.get('G12_effective', 0) > 0:
                    print("  G12_effective = %.2f MPa" % effective_properties['G12_effective'])
                if effective_properties.get('Poisson_12', 0) != 0:
                    print("  Poisson_12 = %.4f" % effective_properties['Poisson_12'])
            
            if volume_averages:
                print("\nVolume-Averaged Results:")
                print("  Average stress: σ11=%.2f, σ22=%.2f, σ33=%.2f MPa" % 
                      (volume_averages.get('S11', 0), volume_averages.get('S22', 0), volume_averages.get('S33', 0)))
                print("  Average strain: epsilon_11=%.6f, epsilon_22=%.6f, epsilon_33=%.6f" % 
                      (volume_averages.get('E11', 0), volume_averages.get('E22', 0), volume_averages.get('E33', 0)))
                print("  Average Mises stress: %.2f MPa" % volume_averages.get('MISES_avg', 0))
            
            print("\nPerformance:")
            print("  Analysis time: %.2f seconds" % analysis_time)
            print("  Total execution time: %.2f seconds" % (time.time() - start_time))
            print("  CPUs used: %d" % CPUs)

            print("\nOutput Files (%d files saved):" % len(saved_files))
            for i, filepath in enumerate(saved_files, 1):
                print("  %d. %s" % (i, os.path.basename(filepath)))
            print("\nOutput directory: %s" % output_dir)
            print("=" * 80)

        return True

# GUI entry point used by RVE_Builder_UDFRPs.Analysis -- thin wrapper.
def rve_multiaxial_analysis_complete_gui(modelName, partName, meshSens, strainX, strainY, strainZ, shearXY, shearYZ, shearZX, cpu, umatName='', unsymmetric_solver=False, large_deformation=True):
    return rve_multiaxial_analysis_complete(
        part=modelName, inst=partName, meshsens=meshSens,
        epsilon_x=strainX, epsilon_y=strainY, epsilon_z=strainZ,
        gamma_xy=shearXY, gamma_yz=shearYZ, gamma_zx=shearZX,
        CPU=cpu, umat_file=umatName, output_dir=None, save_volume_avg=True,
        unsymmetric_solver=unsymmetric_solver, large_deformation=large_deformation)
