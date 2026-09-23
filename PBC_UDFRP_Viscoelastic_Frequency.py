# -*- coding: utf-8 -*-
###############################################################################
# PBC_UDFRP_Viscoelastic_Frequency.py
# -----------------------------------------------------------------------------
# Frequency-domain viscoelastic homogenization of a UDFRP RVE under PBC.
# Sweeps frequency between user-defined bounds and reports storage / loss
# moduli. Called from RVE_Builder_UDFRPs.Analysis when analysis_type == 3.
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
## Importing ABAQUS Data and Python modules ##

from __future__ import absolute_import
from __future__ import print_function
from abaqus import *
from abaqusConstants import *
import __main__, math, section, regionToolset, displayGroupMdbToolset as dgm, part, material, assembly, step, interaction, load, mesh, job, sketch, visualization, xyPlot, displayGroupOdbToolset as dgo, connectorBehavior, time, os, sys, ctypes, multiprocessing
import string
import numpy as np
from six.moves import range
from six.moves import zip
import glob
import csv
import time
from PBC_UDFRP_Elastic_CTE import (
    _append_elastic_pbc_3d,
    _append_shear_pbc_3d,
    _insert_equation_keywords,
)

def _delete_viscoelastic_analysis_sets(assemblyObj):
    exactSetNames = (
        'RP1', 'RP2', 'RP3', 'RP4', 'RP5', 'RP6',
        'c1', 'c2', 'c3', 'c4', 'c5', 'c6', 'c7', 'c8',
        'ftedge', 'fbedge', 'btedge', 'bbedge',
        'fledge', 'fredge', 'bledge', 'bredge',
        'ltedge', 'lbedge', 'rtedge', 'rbedge',
        'fronts', 'backs', 'lefts', 'rights', 'tops', 'bots',
        'frontbc', 'backbc', 'leftbc', 'rightbc', 'topbc', 'botbc',
        'ALL_NODES'
    )
    prefixSetNames = (
        'ftedge', 'fbedge', 'btedge', 'bbedge',
        'fledge', 'fredge', 'bledge', 'bredge',
        'ltedge', 'lbedge', 'rtedge', 'rbedge',
        'fronts', 'backs', 'lefts', 'rights', 'tops', 'bots'
    )
    for setName in list(assemblyObj.sets.keys()):
        if setName in exactSetNames:
            del assemblyObj.sets[setName]
            continue
        for prefixName in prefixSetNames:
            if setName.startswith(prefixName):
                del assemblyObj.sets[setName]
                break

def _reset_viscoelastic_analysis_state(modelObj, assemblyObj):
    for name in list(modelObj.loads.keys()):
        del modelObj.loads[name]
    for name in list(modelObj.boundaryConditions.keys()):
        del modelObj.boundaryConditions[name]
    for name in list(modelObj.constraints.keys()):
        del modelObj.constraints[name]
    for name in list(modelObj.predefinedFields.keys()):
        del modelObj.predefinedFields[name]
    for name in list(modelObj.fieldOutputRequests.keys()):
        if name != 'F-Output-1':
            del modelObj.fieldOutputRequests[name]
    for name in list(modelObj.historyOutputRequests.keys()):
        if name != 'H-Output-1':
            del modelObj.historyOutputRequests[name]
    for name in list(modelObj.steps.keys()):
        if name != 'Initial':
            del modelObj.steps[name]
    _delete_viscoelastic_analysis_sets(assemblyObj)
    for name in list(assemblyObj.features.keys()):
        if name.startswith('RP'):
            del assemblyObj.features[name]

def _set_viscoelastic_initial_temperature(modelName, assemblyObj, temperature):
    if 'InitialTemp' in mdb.models[modelName].predefinedFields.keys():
        del mdb.models[modelName].predefinedFields['InitialTemp']
    regionTemp = assemblyObj.sets['ALL_NODES']
    mdb.models[modelName].Temperature(
        name='InitialTemp', createStepName='Initial', region=regionTemp,
        distributionType=UNIFORM, crossSectionDistribution=CONSTANT_THROUGH_THICKNESS,
        magnitudes=(temperature + 273.15,)
    )

def _unique_viscoelastic_case_model_name(baseModelName, suffix):
    root = '%s_%s' % (baseModelName, suffix)
    name = root
    idx = 1
    while name in mdb.models.keys():
        idx += 1
        name = '%s_%s' % (root, idx)
    return name

def _clear_viscoelastic_case_analysis_features(modelObj):
    for name in list(modelObj.loads.keys()):
        del modelObj.loads[name]
    for name in list(modelObj.boundaryConditions.keys()):
        del modelObj.boundaryConditions[name]
    for name in list(modelObj.constraints.keys()):
        del modelObj.constraints[name]
    for name in list(modelObj.predefinedFields.keys()):
        del modelObj.predefinedFields[name]
    for name in list(modelObj.fieldOutputRequests.keys()):
        if name != 'F-Output-1':
            del modelObj.fieldOutputRequests[name]
    for name in list(modelObj.historyOutputRequests.keys()):
        if name != 'H-Output-1':
            del modelObj.historyOutputRequests[name]
    for name in list(modelObj.steps.keys()):
        if name != 'Initial':
            del modelObj.steps[name]

def _copy_viscoelastic_case_model(baseModelName, suffix):
    caseModelName = _unique_viscoelastic_case_model_name(baseModelName, suffix)
    mdb.Model(name=caseModelName, objectToCopy=mdb.models[baseModelName])
    modelObj = mdb.models[caseModelName]
    _clear_viscoelastic_case_analysis_features(modelObj)
    return caseModelName, modelObj, modelObj.rootAssembly

def _create_viscoelastic_frequency_steps(modelObj, lowerFreq, upperFreq, numPoints, bias):
    modelObj.StaticStep(name='Step-0', previous='Initial')
    modelObj.SteadyStateDirectStep(
        name='Step-1', previous='Step-0',
        frequencyRange=((lowerFreq, upperFreq, numPoints, bias), )
    )

def _prepare_viscoelastic_frequency_case_model(baseModelName, caseName, lowerFreq, upperFreq, numPoints, bias):
    caseModelName, modelObj, assemblyObj = _copy_viscoelastic_case_model(baseModelName, '%s_KW' % caseName)
    _create_viscoelastic_frequency_steps(modelObj, lowerFreq, upperFreq, numPoints, bias)
    return caseModelName, assemblyObj


def format_temperature_file_label(temperature_value):
    """Filesystem-safe label such as Temp_025 or Temp_m050p5 (same convention as the kernel)."""
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

def _job_temperature_suffix(intemp, fntemp=None):
    """'_Temp_025' for a single temperature, '_Temp_025to100' for a ramp, '' if unknown.
    Appended to job names so ODBs of different temperature points never overwrite each other."""
    try:
        lo = float(intemp)
    except (TypeError, ValueError):
        return ''
    try:
        hi = float(fntemp) if fntemp is not None else lo
    except (TypeError, ValueError):
        hi = lo
    if abs(hi - lo) <= 1.0e-12:
        return '_' + format_temperature_file_label(lo)
    return '_' + format_temperature_file_label(lo) + 'to' + format_temperature_file_label(hi).replace('Temp_', '')

def _delete_viscoelastic_case_model(case_model_name):
    """Delete a temporary model copy (and the job objects that point at it) once its results are read."""
    try:
        for job_name in list(mdb.jobs.keys()):
            try:
                if str(getattr(mdb.jobs[job_name], 'model', '')) == case_model_name:
                    del mdb.jobs[job_name]
            except Exception:
                pass
        if case_model_name in mdb.models.keys():
            del mdb.models[case_model_name]
    except Exception as cleanup_error:
        print('Warning: could not delete temporary model %s: %s' % (case_model_name, cleanup_error))

def _viscoelastic_job_name(baseModelName, caseName, temperature=None):
    return '%s-job-%s%s' % (baseModelName, caseName, _job_temperature_suffix(temperature))

def _insert_viscoelastic_3d_keyword_pbc(modelName, pbcGroup, pbcKeywordArgs):
    setupStart = time.time()
    eqs = []
    if pbcGroup == 'E':
        _append_elastic_pbc_3d(eqs, *pbcKeywordArgs)
    elif pbcGroup == 'G':
        _append_shear_pbc_3d(eqs, *pbcKeywordArgs)
    else:
        raise ValueError('Unknown PBC group: %s' % pbcGroup)
    _insert_equation_keywords(modelName, eqs)

## Plugin main GUI function ##
def feasypbc(part,inst,meshsens,E11,E22,E33,G12,G13,G23,CPU, lowerFreq, upperFreq, numPoints, bias, umatName, temperature):
    import os
    path = os.getcwd()
    for T in (list(range(1))):
        start = time.time()
        modelName = part
        instanceName = inst
        upperName= inst.upper()
        
        fail = []
        keycheck2 =[inst]
        
        if part not in (list(mdb.models.keys())):
            Er2=0
            messageBox2 = ctypes.windll.user32.MessageBoxA
            returnValue = messageBox2(Er2,'Model name is incorrect, please input the correct Model name.','EasyPBC Start-up error 02',0x30 | 0x0)
            print('Start-up error 02. Refer EasyPBC user guide')
            continue
        
        a = mdb.models[modelName].rootAssembly
        errorcheck1 = list(mdb.models[modelName].rootAssembly.instances.keys())
        if errorcheck1 == fail:
            Er1=0
            messageBox1 = ctypes.windll.user32.MessageBoxA
            returnValue = messageBox1(Er1,'Model part is not created!\nPlease create part and try again','EasyPBC Start-up error 01',0x30 | 0x0)
            print('Start-up error 01. Refer EasyPBC user guide')
            continue
        
        if (list(mdb.models[modelName].rootAssembly.instances.keys())) != keycheck2:                       
            Er3=0
            messageBox3 = ctypes.windll.user32.MessageBoxA
            returnValue = messageBox3(Er3,'Instance name is incorrect, please input the correct instance name.','EasyPBC Start-up error 03',0x30 | 0x0)
            print('Start-up error 03. Refer EasyPBC user guide')
            continue

        if CPU <= 0:
            Er5=0
            messageBox5 = ctypes.windll.user32.MessageBoxA
            returnValue = messageBox5(Er5,'Specified number of CPUs is <= zero, please set it to a value larger than zero.','EasyPBC Start-up error 05',0x30 | 0x0)
            print('Start-up error 05. Refer EasyPBC user guide')
            continue

        
        CPUs = int(round(CPU))
        if CPUs > multiprocessing.cpu_count():
            CPUs = multiprocessing.cpu_count()
            print(('Warning: Specified number of CPUs is greater than the available. The maximum available number of CPUs is used (%s CPU(s)).' % CPUs))


        Nodeset = mdb.models[modelName].rootAssembly.instances[instanceName].nodes
        _reset_viscoelastic_analysis_state(mdb.models[modelName], a)

        ## Start of sets creation ##                
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
        all_nodes = []
        
        error=False

        print ('----------------------------------')
        print ('-------- Start of EasyPBC --------')
        print ('----------------------------------')

        ## Identifying RVE size ##    
        for i in Nodeset:
            x.insert(j,i.coordinates[0])
            y.insert(j,i.coordinates[1])
            z.insert(j,i.coordinates[2])
            j=j+1

        errorcheck4 = x                   
        if not errorcheck4:
            Er4=0
            messageBox4 = ctypes.windll.user32.MessageBoxA
            returnValue = messageBox4(Er4,'Instance not detected! Make sure:\n1- Instance is created;\n2- Double click on instance to refresh it before running EasyPBC;\n3- Part/instnace is meshed.','EasyPBC Start-up error 04',0x30 | 0x0)
            print('Start-up error 04. Refer EasyPBC user guide')
            continue

        Max = max(x)
        May = max(y)
        Maz = max(z)
        Mnx = min(x)
        Mny = min(y)
        Mnz = min(z)
        
        if (Maz - Mnz)<=meshsens:  ## 2D Model Check
            print ('Only 3D RVE can be used.')
        ## 3D model ##########################################################
        L=abs(Max-Mnx)
        H=abs(May-Mny)
        W=abs(Maz-Mnz)
        
        Dispx = L*0.01
        Dispy = H*0.01
        Dispz = W*0.01
        
        ## Creating Ref. Points ##
        for i in a.features.keys():
            if i.startswith('RP'):
                del a.features['%s' % (i)]
        
        a.ReferencePoint(point=(Max+0.8*L, May-0.5*(May-Mny), Maz-0.5*(Maz-Mnz)))  ## RP6: G23
        a.ReferencePoint(point=(Max+0.6*L, May-0.5*(May-Mny), Maz-0.5*(Maz-Mnz)))  ## RP5: G13
        a.ReferencePoint(point=(Max+0.4*L, May-0.5*(May-Mny), Maz-0.5*(Maz-Mnz)))  ## RP4: G12
        a.ReferencePoint(point=(Max+0.2*L, May-0.5*(May-Mny), Maz-0.5*(Maz-Mnz)))  ## RP3: Rigid body movement X-axis
        a.ReferencePoint(point=(Max-0.5*(Max-Mnx), May-0.5*(May-Mny), Maz+0.2*W))  ## RP2: Rigid body movement Z-axis
        a.ReferencePoint(point=(Max-0.5*(Max-Mnx), May+0.2*H, Maz-0.5*(Maz-Mnz)))  ## RP1: Rigid body movement Y-axis

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
            print ('Warning: Number of Nodes in Front surface (fronts) not equal to number of nodes in Back surface (backs). These sets will not be created!!')
            print ('         Refer to error 06 troubleshooting in easyPBC user guide.')
            frontsxyz={}
            error=True
        if len(topsxyz) != len(botsxyz):
            print ('Warning: Number of Nodes in Top surface (tops) not equal to number of nodes in Bottom surface (bots). These sets will not be created!!')
            print ('         Refer to error 06 in easyPBC user guide.')
            topsxyz={}
            error=True
        if len(leftsxyz) != len(rightsxyz):
            print ('Warning: Number of Nodes in Left surface (lefts) not equal to number of nodes in Right surface (rights). These sets will not be created!!')
            print ('         Refer to error 06 in easyPBC user guide.')
            leftsxyz={}
            error=True
        if len(ftedgexyz) != len(btedgexyz) or len(btedgexyz) != len(bbedgexyz) or len(bbedgexyz) != len(ftedgexyz):
            print ('Warning: Number of nodes in front-top ,back-top, back-bottom, front-bottom (ftedge, btedge, bbedge and fbedge) are not equal. These sets will not be created!!')
            print ('         Refer to error 06 in easyPBC user guide.')
            ftedgexyz={}
            error=True
        if len(fledgexyz) != len(bledgexyz) or len(bledgexyz) != len(bredgexyz) or len(bredgexyz) != len(fredgexyz):
            print ('Warning: Number of nodes in front-left, back-left, back-right, front-right edge (fledge, bledge, bredge and fredge) are not equal. These sets will not be created!!')
            print ('         Refer to error 06 in easyPBC user guide.')
            fledgexyz={}
            error=True
        if len(ltedgexyz) != len(rtedgexyz) or len(rtedgexyz) != len(rbedgexyz) or len(rbedgexyz) != len(lbedgexyz):
            print ('Warning: Number of nodes in left-top, right-top, right-bottom, front-bottom edge (ltedge, rtedge, rbedge and fbedge). are not equal. These sets will not be created!!')
            print ('         Refer to error 06 in easyPBC user guide.')
            ltedgexyz={}
            error=True
        if len(frontbcxyz) != len(backbcxyz):
            print ('Warning: Number of Nodes in Front BC surface (frontbc) not equal to number of nodes in Back BC surface (backbc). These sets will not be created!!')
            print ('         Refer to error 06 troubleshooting in easyPBC user guide.')
            frontbcxyz={}
            error=True
        if len(topbcxyz) != len(botbcxyz):
            print ('Warning: Number of Nodes in Top BC surface (topbc) not equal to number of nodes in Bottom BC surface (botbc). These sets will not be created!!')
            print ('         Refer to error 06 in easyPBC user guide.')
            topbcxyz={}
            error=True
        if len(leftbcxyz) != len(rightbcxyz):
            print ('Warning: Number of Nodes in Left BC surface (leftbc) not equal to number of nodes in Right BC surface (rightbc). These sets will not be created!!')
            print ('         Refer to error 06 in easyPBC user guide.')
            leftbcxyz={}
            error=True

        ## Sorting and appending sets ##
        for i in frontsxyz.keys():
            for k in backsxyz.keys():
                if abs(frontsxyz[i][1] - backsxyz[k][1])<=meshsens and abs(frontsxyz[i][2] - backsxyz[k][2])<=meshsens:
                    fronts.append(i)
                    backs.append(k)

        if len(frontsxyz)!= len(fronts) or len(backsxyz)!= len(backs):
            print ('Warning: Node(s) in Front and/or Back surface (fronts and/or backs) was not imported. effected sets will not be created!!')
            print ('         Refer to error 07 in easyPBC user guide and created Error set (if applicable).')
            for i, k in zip(list(frontsxyz.keys()),list(backsxyz.keys())):
                if i not in fronts:
                    errorset.append(i)
                if k not in backs:
                    errorset.append(k)
            fronts=[]
            backs=[]
            error=True                    
        if len(fronts)!=len(set(fronts)) or len(backs)!=len(set(backs)):
            print ('Warning: Node(s) in either Front or Back surface (fronts or backs) being linked with more than one opposite node. effected sets will not be created!!')
            print ('         Refer to error 08 in easyPBC user guide.')
            fronts=[]
            backs=[]
            error=True

        for i in topsxyz.keys():
            for k in botsxyz.keys():
                if abs(topsxyz[i][0] - botsxyz[k][0]) <=meshsens and abs(topsxyz[i][2] - botsxyz[k][2]) <=meshsens:
                    tops.append(i)
                    bots.append(k)
        if len(topsxyz)!= len(tops) or len(botsxyz)!= len(bots):
            print ('Warning: Node(s) in Top and/or Bottom surface (tops and/or bots) was not imported. effected sets will not be created!!')
            print ('         Refer to error 07 in easyPBC user guide and created Error set (if applicable).')
            for i, k in zip(list(topsxyz.keys()),list(botsxyz.keys())):
                if i not in tops:
                    errorset.append(i)
                if k not in bots:
                    errorset.append(k)
            tops=[]
            bots=[]
            error=True
        if len(tops)!=len(set(tops)) or len(bots)!=len(set(bots)):
            print ('Warning: Node(s) in either Top or Bottom surface (tops or bots) being linked with more than one opposite node. effected sets will not be created!!')
            print ('         Refer to error 08 in easyPBC user guide.')
            tops=[]
            bots=[]
            error=True


        for i in leftsxyz.keys():
            for k in rightsxyz.keys():
                if abs(leftsxyz[i][0] - rightsxyz[k][0])<=meshsens and abs(leftsxyz[i][1] - rightsxyz[k][1]) <=meshsens:
                    lefts.append(i)
                    rights.append(k)
        if len(leftsxyz)!= len(lefts) or len(rightsxyz)!= len(rights):
            print ('Warning: Node(s) in Left and/or Right surface (lefts and/or rights) was not imported. effected sets will not be created!!')
            print ('         Refer to error 07 in easyPBC user guide and created Error set (if applicable).')
            for i, k in zip(list(leftsxyz.keys()),list(rightsxyz.keys())):
                    if i not in lefts:
                        errorset.append(i)
                    if k not in rights:
                        errorset.append(k)                    
            lefts=[]
            rights=[]
            error=True                    
        if len(lefts)!=len(set(lefts)) or len(rights)!=len(set(rights)):
            print ('Warning: Node(s) in either Left or Right surface (lefts or rights) being linked with more than one opposite node. effected sets will not be created!!')
            print ('         Refer to error 08 in easyPBC user guide.')
            lefts=[]
            rights=[]
            error=True

        for i in frontbcxyz.keys():
            for k in backbcxyz.keys():
                if abs(frontbcxyz[i][1] - backbcxyz[k][1])<=meshsens and abs(frontbcxyz[i][2] - backbcxyz[k][2])<=meshsens:
                    frontbc.append(i)
                    backbc.append(k)
        if len(frontbcxyz)!= len(frontbc) or len(backbcxyz)!= len(backbc):
            print ('Warning: Node(s) in Front BC and/or Back BC surface (frontbc and/or backbc) was not imported. effected sets will not be created!!')
            print ('         Refer to error 07 in easyPBC user guide and created Error set (if applicable).')
            for i, k in zip(list(frontbcxyz.keys()),list(backbcxyz.keys())):
                if i not in frontbc:
                    errorset.append(i)
                if k not in backbc:
                    errorset.append(k)
            frontbc=[]
            backbc=[]
            error=True
        if len(frontbc)!=len(set(frontbc)) or len(backbc)!=len(set(backbc)):
            print ('Warning: Node(s) in either Front BC or Back BC surface (frontbc or backbc) being linked with more than one opposite node. effected sets will not be created!!')
            print ('         Refer to error 08 in easyPBC user guide.')
            frontbc=[]
            backbc=[]
            error=True

        for i in topbcxyz.keys():
            for k in botbcxyz.keys():
                if abs(topbcxyz[i][0] - botbcxyz[k][0]) <=meshsens and abs(topbcxyz[i][2] - botbcxyz[k][2]) <=meshsens:
                    topbc.append(i)
                    botbc.append(k)
        if len(topbcxyz)!= len(topbc) or len(botbcxyz)!= len(botbc):
            print ('Warning: Node(s) in Top BC and/or Bottom BC surface (topbc and/or botbc) was not imported. effected sets will not be created!!')
            print ('         Refer to error 07 in easyPBC user guide and created Error set (if applicable).')
            for i, k in zip(list(topbcxyz.keys()),list(botbcxyz.keys())):
                if i not in topbc:
                    errorset.append(i)
                if k not in botbc:
                    errorset.append(k)
            topbc=[]
            botbc=[]
            error=True
        if len(topbc)!=len(set(topbc)) or len(botbc)!=len(set(botbc)):
            print ('Warning: Node(s) in either Top BC or Bottom BC surface (topbc or botbc) being linked with more than one opposite node. effected sets will not be created!!')
            print ('         Refer to error 08 in easyPBC user guide.')
            topbc=[]
            botbc=[]
            error=True

        for i in leftbcxyz.keys():
            for k in rightbcxyz.keys():
                if abs(leftbcxyz[i][0] - rightbcxyz[k][0])<=meshsens and abs(leftbcxyz[i][1] - rightbcxyz[k][1]) <=meshsens:
                    leftbc.append(i)
                    rightbc.append(k)
        if len(leftbcxyz)!= len(leftbc) or len(rightbcxyz)!= len(rightbc):
            print ('Warning: Node(s) in Left BC and/or Right BC surface (lefts and/or rights) was not imported. effected sets will not be created!!')
            print ('         Refer to error 07 in easyPBC user guide and created Error set (if applicable).')
            for i, k in zip(list(leftbcxyz.keys()),list(rightbcxyz.keys())):
                    if i not in leftbc:
                        errorset.append(i)
                    if k not in rightbc:
                        errorset.append(k)            
            leftbc=[]
            rightbc=[]
            error=True
        if len(leftbc)!=len(set(leftbc)) or len(rightbc)!=len(set(rightbc)):
            print ('Warning: Node(s) in either Left BC or Right BC surface (leftbc or rightbc) being linked with more than one opposite node. effected sets will not be created!!')
            print ('         Refer to error 08 in easyPBC user guide.')
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
            print ('Warning: Node(s) in either front-top, back-top, back-bottom and front-bottom edge(ftedge, btedge, bbedge and fbedge) being linked with more than one opposite node. effected sets will not be created!!')
            print ('         Refer to error 08 in easyPBC user guide.')
            ftedge=[]
            btedge=[]
            bbedge=[]
            fbedge=[]
            error==True
        if len(ftedgexyz)!= len(ftedge) or len(btedgexyz)!= len(btedge) or len(bbedgexyz)!= len(bbedge) or len(fbedgexyz)!= len(fbedge):
            print ('Warning: Node(s) in front-top, back-top, back-bottom and front-bottom edge(ftedge, btedge, bbedge and fbedge) were not imported. these sets will not be created!!')
            print ('         Refer to error 07 in easyPBC user guide and created Error set (if applicable).')
            ftedge=[]
            btedge=[]
            bbedge=[]
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
            print ('Warning: Node(s) in either front-top, back-bottom and front-bottom edge(ltedge, rtedge, rbedge and lbedge) being linked with more than one opposite node. effected sets will not be created!!')
            print ('         Refer to error 08 in easyPBC user guide.')
            ltedge=[]
            rtedge=[]
            rbedge=[]
            lbedge=[]
            error=True

        if len(ltedgexyz)!= len(ltedge) or len(rtedgexyz)!= len(rtedge) or len(rbedgexyz)!= len(rbedge) or len(lbedgexyz)!= len(lbedge):
            print ('Warning: Node(s) in left-top, right-top, right-bottom, left-bottom edge (ltedge, rtedge, rbedge and lbedge) were not imported. these sets will not be created!!')
            print ('         Refer to error 07 in easyPBC user guide and created Error set (if applicable).')
            ltedge=[]
            rtedge=[]
            rbedge=[]
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
            print ('Warning: Node(s) in either front-left, back-left, back-right and front-right edge(fledge, bledge, bredge and fredge) being linked with more than one opposite node. effected sets will not be created!!')
            print ('         Refer to error 08 in easyPBC user guide.')
            fledge=[]
            bledge=[]
            bredge=[]
            fredge=[]
            error=True
        if len(fledgexyz)!= len(fledge) or len(bledgexyz)!= len(bledge) or len(bredgexyz)!= len(bredge) or len(fredgexyz)!= len(fredge):
            print ('Warning: Node(s) in front-left, back-left, back-right and front-right edge (fledge, bledge, bredge and fredge) were not imported. these sets will not be created!!')
            print ('         Refer to error 07 in easyPBC user user guide.')
            fledge=[]
            bledge=[]
            bredge=[]
            fredge=[]
            error=True

        ## Creating ABAQUS sets ##
        a.SetFromNodeLabels(name='c1', nodeLabels=((instanceName,c1),))
        a.SetFromNodeLabels(name='c2', nodeLabels=((instanceName,c2),))
        a.SetFromNodeLabels(name='c3', nodeLabels=((instanceName,c3),))
        a.SetFromNodeLabels(name='c4', nodeLabels=((instanceName,c4),))
        a.SetFromNodeLabels(name='c5', nodeLabels=((instanceName,c5),))
        a.SetFromNodeLabels(name='c6', nodeLabels=((instanceName,c6),))
        a.SetFromNodeLabels(name='c7', nodeLabels=((instanceName,c7),))
        a.SetFromNodeLabels(name='c8', nodeLabels=((instanceName,c8),))
        a.SetFromNodeLabels(name='ftedge', nodeLabels=((instanceName,ftedge),))
        a.SetFromNodeLabels(name='fbedge', nodeLabels=((instanceName,fbedge),))
        a.SetFromNodeLabels(name='btedge', nodeLabels=((instanceName,btedge),))
        a.SetFromNodeLabels(name='bbedge', nodeLabels=((instanceName,bbedge),))
        a.SetFromNodeLabels(name='fledge', nodeLabels=((instanceName,fledge),))
        a.SetFromNodeLabels(name='fredge', nodeLabels=((instanceName,fredge),))
        a.SetFromNodeLabels(name='bledge', nodeLabels=((instanceName,bledge),))
        a.SetFromNodeLabels(name='bredge', nodeLabels=((instanceName,bredge),))
        a.SetFromNodeLabels(name='ltedge', nodeLabels=((instanceName,ltedge),))
        a.SetFromNodeLabels(name='lbedge', nodeLabels=((instanceName,lbedge),))
        a.SetFromNodeLabels(name='rtedge', nodeLabels=((instanceName,rtedge),))
        a.SetFromNodeLabels(name='rbedge', nodeLabels=((instanceName,rbedge),))
        a.SetFromNodeLabels(name='fronts', nodeLabels=((instanceName,fronts),))
        a.SetFromNodeLabels(name='backs', nodeLabels=((instanceName,backs),))
        a.SetFromNodeLabels(name='lefts', nodeLabels=((instanceName,lefts),))
        a.SetFromNodeLabels(name='rights', nodeLabels=((instanceName,rights),))
        a.SetFromNodeLabels(name='tops', nodeLabels=((instanceName,tops),))
        a.SetFromNodeLabels(name='bots', nodeLabels=((instanceName,bots),))
        a.SetFromNodeLabels(name='frontbc', nodeLabels=((instanceName,frontbc),))
        a.SetFromNodeLabels(name='backbc', nodeLabels=((instanceName,backbc),))
        a.SetFromNodeLabels(name='leftbc', nodeLabels=((instanceName,leftbc),))
        a.SetFromNodeLabels(name='rightbc', nodeLabels=((instanceName,rightbc),))
        a.SetFromNodeLabels(name='topbc', nodeLabels=((instanceName,topbc),))
        a.SetFromNodeLabels(name='botbc', nodeLabels=((instanceName,botbc),))
        a.Set(name='ALL_NODES', nodes=a.instances[instanceName].nodes)
        print ('------ End of Sets Creation ------')

        ## Extracting model mass ##
        prop=mdb.models[modelName].rootAssembly.getMassProperties()
        mass=prop['mass']

        a = mdb.models[modelName].rootAssembly
        Nodeset = mdb.models[modelName].rootAssembly.instances[instanceName].nodes
        
        baseModelName = modelName
        pbcKeywordArgs = (
            instanceName, tops, bots, lefts, rights, fronts, backs,
            ftedge, btedge, bbedge, fbedge, fledge, bledge, bredge, fredge,
            ltedge, lbedge, rbedge, rtedge
        )

        ## Keyword-block PBC setup ##
        if error==False:
            
            ## Keyword-block PBC equations are inserted per load-case model.
            ## viscoelastic E11(f)
            if E11==True:
                caseModelName, a = _prepare_viscoelastic_frequency_case_model(
                    baseModelName, 'E11', lowerFreq, upperFreq, numPoints, bias
                )
                modelName = caseModelName
                jobName = _viscoelastic_job_name(baseModelName, 'E11', temperature)
                for i in mdb.models[modelName].loads.keys():
                        del mdb.models[modelName].loads[i]
                for i in mdb.models[modelName].boundaryConditions.keys():
                        del mdb.models[modelName].boundaryConditions[i]
                
                region = a.sets['RP4']
                mdb.models[modelName].DisplacementBC(name='E11-1', createStepName='Initial',region=region, u1=SET, u2=UNSET, u3=UNSET, ur1=UNSET, ur2=UNSET, ur3=UNSET, distributionType=UNIFORM, fieldName='', localCsys=None)
                
                mdb.models[modelName].boundaryConditions['E11-1'].setValuesInStep(stepName='Step-0', u1=Dispx)
                mdb.models[modelName].boundaryConditions['E11-1'].setValuesInStep(stepName='Step-1', u1=Dispx+0j)
                _set_viscoelastic_initial_temperature(modelName, a, temperature)
                _insert_viscoelastic_3d_keyword_pbc(modelName, 'E', pbcKeywordArgs)
                
                regionDef=mdb.models[modelName].rootAssembly.sets['c1']
                
                import os, glob
                
                if jobName in mdb.jobs.keys():
                    del mdb.jobs[jobName]
                mdb.Job(name=jobName, model=modelName, description='', type=ANALYSIS,
                        atTime=None, waitMinutes=0, waitHours=0, queue=None, memory=98,
                        memoryUnits=PERCENTAGE, getMemoryFromAnalysis=True,
                        explicitPrecision=SINGLE, nodalOutputPrecision=SINGLE, echoPrint=OFF,
                        modelPrint=OFF, contactPrint=OFF, historyPrint=OFF, userSubroutine=umatName,
                        scratch='', multiprocessingMode=DEFAULT, numCpus=CPUs, numDomains=CPUs, numGPUs=0)
                mdb.jobs[jobName].submit(consistencyChecking=OFF)
                mdb.jobs[jobName].waitForCompletion()
                
                odb_path = os.path.join(path, jobName + '.odb')
                o3 = session.openOdb(name=odb_path)
                
                file_name = '{}_E11_v12_v13_viscoelastic_freq_Temp{:03d}.csv'.format(baseModelName, int(temperature))
                with open(file_name, 'w') as file:
                    file.write('Frequency [Hz], E11_storage [Unit], E11_loss [Unit], v12_real, v12_imag, v13_real, v13_imag\n')
                    written_data = set()
                    
                    freq_step_name = o3.steps.keys()[-1]
                    freq_step = o3.steps[freq_step_name]
                    strain_11_real = Dispx / L
                    
                    for frame in freq_step.frames:
                        if frame.frameValue == 0.0:
                            continue
                        freq_value = frame.frequency
                        
                        rf_field = frame.fieldOutputs['RF']
                        rf_RP4 = rf_field.getSubset(region=o3.rootAssembly.nodeSets['RP4']).values[0]
                        forceE11_real = rf_RP4.data[0]
                        forceE11_imag = rf_RP4.conjugateData[0]
                        E11_storage = (forceE11_real / (H * W)) / strain_11_real
                        E11_loss    = (forceE11_imag / (H * W)) / strain_11_real
                        
                        u_field = frame.fieldOutputs['U']
                        val_C1 = u_field.getSubset(region=o3.rootAssembly.nodeSets['C1']).values[0]
                        val_C2 = u_field.getSubset(region=o3.rootAssembly.nodeSets['C2']).values[0]
                        val_C4 = u_field.getSubset(region=o3.rootAssembly.nodeSets['C4']).values[0]
                        val_C5 = u_field.getSubset(region=o3.rootAssembly.nodeSets['C5']).values[0]
                        
                        E11U1_real = val_C1.data[0] - val_C2.data[0]
                        actual_strain_11 = E11U1_real / L
                        
                        E11U2_real = val_C1.data[1] - val_C5.data[1]
                        E11U2_imag = val_C1.conjugateData[1] - val_C5.conjugateData[1]
                        
                        E11U3_real = val_C1.data[2] - val_C4.data[2]
                        E11U3_imag = val_C1.conjugateData[2] - val_C4.conjugateData[2]
                        
                        if actual_strain_11 != 0:
                            v12_real = -(E11U2_real / H) / actual_strain_11
                            v12_imag = -(E11U2_imag / H) / actual_strain_11
                            v13_real = -(E11U3_real / W) / actual_strain_11
                            v13_imag = -(E11U3_imag / W) / actual_strain_11
                        else:
                            v12_real = v12_imag = v13_real = v13_imag = 0.0
                        
                        data_tuple = (freq_value, E11_storage, E11_loss, v12_real, v12_imag, v13_real, v13_imag)
                        if data_tuple not in written_data:
                            written_data.add(data_tuple)
                            file.write('{:.10e}, {:.10e}, {:.10e}, {:.10e}, {:.10e}, {:.10e}, {:.10e}\n'.format(*data_tuple))
                
                o3.close()
                _delete_viscoelastic_case_model(caseModelName)
                print("====> Results have been saved in {}.".format(file_name))
                print('---------- Successful calculation of equivalent viscoelasticity E11, V12, V13 ----------')
                modelName = baseModelName
                a = mdb.models[modelName].rootAssembly
                

            ## viscoelastic E22(f)
            if E11==False:
                E11='N/A'
                V12='N/A'
                V13='N/A'
            
            if E22==True:
                caseModelName, a = _prepare_viscoelastic_frequency_case_model(
                    baseModelName, 'E22', lowerFreq, upperFreq, numPoints, bias
                )
                modelName = caseModelName
                jobName = _viscoelastic_job_name(baseModelName, 'E22', temperature)
                for i in mdb.models[modelName].loads.keys():
                        del mdb.models[modelName].loads[i]
                for i in mdb.models[modelName].boundaryConditions.keys():
                        del mdb.models[modelName].boundaryConditions[i]
                
                region = a.sets['RP5']
                
                mdb.models[modelName].DisplacementBC(name='E22-2', createStepName='Initial',region=region, u1=UNSET, u2=SET, u3=UNSET, ur1=UNSET, ur2=UNSET, ur3=UNSET, distributionType=UNIFORM, fieldName='', localCsys=None)
                mdb.models[modelName].boundaryConditions['E22-2'].setValuesInStep(stepName='Step-0', u2=Dispy)
                mdb.models[modelName].boundaryConditions['E22-2'].setValuesInStep(stepName='Step-1', u2=Dispy+0j)
                _set_viscoelastic_initial_temperature(modelName, a, temperature)
                _insert_viscoelastic_3d_keyword_pbc(modelName, 'E', pbcKeywordArgs)
                
                regionDef=mdb.models[modelName].rootAssembly.sets['c1']
                
                import os, glob
                
                if jobName in mdb.jobs.keys():
                    del mdb.jobs[jobName]
                mdb.Job(name=jobName, model=modelName, description='', type=ANALYSIS,
                        atTime=None, waitMinutes=0, waitHours=0, queue=None, memory=98,
                        memoryUnits=PERCENTAGE, getMemoryFromAnalysis=True,
                        explicitPrecision=SINGLE, nodalOutputPrecision=SINGLE, echoPrint=OFF,
                        modelPrint=OFF, contactPrint=OFF, historyPrint=OFF, userSubroutine=umatName,
                        scratch='', multiprocessingMode=DEFAULT, numCpus=CPUs, numDomains=CPUs, numGPUs=0)
                mdb.jobs[jobName].submit(consistencyChecking=OFF)
                mdb.jobs[jobName].waitForCompletion()
                
                # --- Post-processing (fixed complex-number reading and modulus calculation) ---
                odb_path = os.path.join(path, jobName + '.odb')
                o3 = session.openOdb(name=odb_path)
                
                file_name = '{}_E22_v21_v23_viscoelastic_freq_Temp{:03d}.csv'.format(baseModelName, int(temperature))
                with open(file_name, 'w') as file:
                    file.write('Frequency [Hz], E22_storage [Unit], E22_loss [Unit], v21_real, v21_imag, v23_real, v23_imag\n')
                    written_data = set()
                    
                    # get the last analysis step dynamically (usually the frequency-sweep step)
                    freq_step_name = o3.steps.keys()[-1]
                    freq_step = o3.steps[freq_step_name]
                    
                    # theoretical macro strain (imaginary displacement = 0, so strain is fully real)
                    strain_22_real = Dispy / H
                    
                    for frame in freq_step.frames:
                        # skip the initial frame that has no frequency data (if any)
                        if frame.frameValue == 0.0:
                            continue
                        
                        freq_value = frame.frequency
                        
                        # 1. extract reaction force (RF2) - index [1] = Y direction
                        rf_field = frame.fieldOutputs['RF']
                        rf_RP5 = rf_field.getSubset(region=o3.rootAssembly.nodeSets['RP5']).values[0]
                        forceE22_real = rf_RP5.data[1]          # real part
                        forceE22_imag = rf_RP5.conjugateData[1] # imaginary part
                        
                        # compute storage and loss moduli
                        # E = (F / Area) / Strain
                        E22_storage = (forceE22_real / (L * W)) / strain_22_real
                        E22_loss    = (forceE22_imag / (L * W)) / strain_22_real
                        
                        # 2. extract displacements to compute Poisson's ratio
                        u_field = frame.fieldOutputs['U']
                        
                        # extract displacement of each control node (U1, U2, U3 = index [0], [1], [2])
                        val_C1 = u_field.getSubset(region=o3.rootAssembly.nodeSets['C1']).values[0]
                        val_C2 = u_field.getSubset(region=o3.rootAssembly.nodeSets['C2']).values[0]
                        val_C4 = u_field.getSubset(region=o3.rootAssembly.nodeSets['C4']).values[0]
                        val_C5 = u_field.getSubset(region=o3.rootAssembly.nodeSets['C5']).values[0]
                        
                        # relative displacement change in direction 1 (dU1)
                        E22U1_real = val_C1.data[0] - val_C2.data[0]
                        E22U1_imag = val_C1.conjugateData[0] - val_C2.conjugateData[0]
                        
                        # relative displacement change in direction 2 (dU2) - real part should be very close to applied Dispy
                        E22U2_real = val_C1.data[1] - val_C5.data[1]
                        
                        # relative displacement change in direction 3 (dU3)
                        E22U3_real = val_C1.data[2] - val_C4.data[2]
                        E22U3_imag = val_C1.conjugateData[2] - val_C4.conjugateData[2]
                        
                        # compute complex Poisson's ratios v21 and v23
                        # formula: v_ij = - (dUi / L_i) / (dUj / L_j)
                        # note the negative sign; use the actual macro strain (E22U2_real / H) as denominator
                        actual_strain_22 = E22U2_real / H
                        if actual_strain_22 != 0:
                            v21_real = - (E22U1_real / L) / actual_strain_22
                            v21_imag = - (E22U1_imag / L) / actual_strain_22
                            
                            v23_real = - (E22U3_real / W) / actual_strain_22
                            v23_imag = - (E22U3_imag / W) / actual_strain_22
                        else:
                            v21_real = v21_imag = v23_real = v23_imag = 0.0
                    
                        data_tuple = (freq_value, E22_storage, E22_loss, v21_real, v21_imag, v23_real, v23_imag)
                        
                        if data_tuple not in written_data:
                            written_data.add(data_tuple)
                            file.write('{:.10e}, {:.10e}, {:.10e}, {:.10e}, {:.10e}, {:.10e}, {:.10e}\n'.format(*data_tuple))
                
                o3.close()
                _delete_viscoelastic_case_model(caseModelName)
                print("====> Results have been saved in {}.".format(file_name))
                print('---------- Successful calculation of equivalent viscoelasticity E22, V21, V23 ----------')
                modelName = baseModelName
                a = mdb.models[modelName].rootAssembly
                
            if E22==False:
                E22='N/A'
                V21='N/A'
                V23='N/A'
            ## viscoelastic E33(f)
            if E33==True:
                caseModelName, a = _prepare_viscoelastic_frequency_case_model(
                    baseModelName, 'E33', lowerFreq, upperFreq, numPoints, bias
                )
                modelName = caseModelName
                jobName = _viscoelastic_job_name(baseModelName, 'E33', temperature)
                for i in mdb.models[modelName].loads.keys():
                        del mdb.models[modelName].loads[i]
                for i in mdb.models[modelName].boundaryConditions.keys():
                        del mdb.models[modelName].boundaryConditions[i]
                
                region = a.sets['RP6']
                
                mdb.models[modelName].DisplacementBC(name='E33-3', createStepName='Initial',region=region, u1=UNSET, u2=UNSET, u3=SET, ur1=UNSET, ur2=UNSET, ur3=UNSET, distributionType=UNIFORM, fieldName='', localCsys=None)
                mdb.models[modelName].boundaryConditions['E33-3'].setValuesInStep(stepName='Step-0', u3=Dispz)
                mdb.models[modelName].boundaryConditions['E33-3'].setValuesInStep(stepName='Step-1', u3=Dispz+0j)
                _set_viscoelastic_initial_temperature(modelName, a, temperature)
                _insert_viscoelastic_3d_keyword_pbc(modelName, 'E', pbcKeywordArgs)
                
                regionDef=mdb.models[modelName].rootAssembly.sets['c1']
                
                import os, glob
                
                if jobName in mdb.jobs.keys():
                    del mdb.jobs[jobName]
                mdb.Job(name=jobName, model=modelName, description='', type=ANALYSIS,
                        atTime=None, waitMinutes=0, waitHours=0, queue=None, memory=98,
                        memoryUnits=PERCENTAGE, getMemoryFromAnalysis=True,
                        explicitPrecision=SINGLE, nodalOutputPrecision=SINGLE, echoPrint=OFF,
                        modelPrint=OFF, contactPrint=OFF, historyPrint=OFF, userSubroutine=umatName,
                        scratch='', multiprocessingMode=DEFAULT, numCpus=CPUs, numDomains=CPUs, numGPUs=0)
                mdb.jobs[jobName].submit(consistencyChecking=OFF)
                mdb.jobs[jobName].waitForCompletion()
                
                odb_path = os.path.join(path, jobName + '.odb')
                o3 = session.openOdb(name=odb_path)
                
                file_name = '{}_E33_v31_v32_viscoelastic_freq_Temp{:03d}.csv'.format(baseModelName, int(temperature))
                with open(file_name, 'w') as file:
                    file.write('Frequency [Hz], E33_storage [Unit], E33_loss [Unit], v31_real, v31_imag, v32_real, v32_imag\n')
                    written_data = set()
                    
                    freq_step_name = o3.steps.keys()[-1]
                    freq_step = o3.steps[freq_step_name]
                    strain_33_real = Dispz / W
                    
                    for frame in freq_step.frames:
                        if frame.frameValue == 0.0:
                            continue
                        freq_value = frame.frequency
                        
                        rf_field = frame.fieldOutputs['RF']
                        rf_RP6 = rf_field.getSubset(region=o3.rootAssembly.nodeSets['RP6']).values[0]
                        forceE33_real = rf_RP6.data[2]
                        forceE33_imag = rf_RP6.conjugateData[2]
                        E33_storage = (forceE33_real / (L * H)) / strain_33_real
                        E33_loss    = (forceE33_imag / (L * H)) / strain_33_real
                        
                        u_field = frame.fieldOutputs['U']
                        val_C1 = u_field.getSubset(region=o3.rootAssembly.nodeSets['C1']).values[0]
                        val_C2 = u_field.getSubset(region=o3.rootAssembly.nodeSets['C2']).values[0]
                        val_C4 = u_field.getSubset(region=o3.rootAssembly.nodeSets['C4']).values[0]
                        val_C5 = u_field.getSubset(region=o3.rootAssembly.nodeSets['C5']).values[0]
                        
                        E33U3_real = val_C1.data[2] - val_C4.data[2]
                        actual_strain_33 = E33U3_real / W
                        
                        E33U1_real = val_C1.data[0] - val_C2.data[0]
                        E33U1_imag = val_C1.conjugateData[0] - val_C2.conjugateData[0]
                        
                        E33U2_real = val_C1.data[1] - val_C5.data[1]
                        E33U2_imag = val_C1.conjugateData[1] - val_C5.conjugateData[1]
                        
                        if actual_strain_33 != 0:
                            v31_real = -(E33U1_real / L) / actual_strain_33
                            v31_imag = -(E33U1_imag / L) / actual_strain_33
                            v32_real = -(E33U2_real / H) / actual_strain_33
                            v32_imag = -(E33U2_imag / H) / actual_strain_33
                        else:
                            v31_real = v31_imag = v32_real = v32_imag = 0.0
                        
                        data_tuple = (freq_value, E33_storage, E33_loss, v31_real, v31_imag, v32_real, v32_imag)
                        if data_tuple not in written_data:
                            written_data.add(data_tuple)
                            file.write('{:.10e}, {:.10e}, {:.10e}, {:.10e}, {:.10e}, {:.10e}, {:.10e}\n'.format(*data_tuple))
                
                o3.close()
                _delete_viscoelastic_case_model(caseModelName)
                print("====> Results have been saved in {}.".format(file_name))
                print('---------- Successful calculation of equivalent viscoelasticity E33, V31, V32 ----------')
                modelName = baseModelName
                a = mdb.models[modelName].rootAssembly

            if E33==False:
                    E33='N/A'
                    V31='N/A'
                    V32='N/A'
            ## Shear modulus G12(f)
            if G12==True:
                caseModelName, a = _prepare_viscoelastic_frequency_case_model(
                    baseModelName, 'G12', lowerFreq, upperFreq, numPoints, bias
                )
                modelName = caseModelName
                jobName = _viscoelastic_job_name(baseModelName, 'G12', temperature)
                for i in mdb.models[modelName].loads.keys():
                        del mdb.models[modelName].loads[i]
                for i in mdb.models[modelName].boundaryConditions.keys():
                        del mdb.models[modelName].boundaryConditions[i]
                        
                region = a.sets['RP4']
                
                mdb.models[modelName].DisplacementBC(name='G12-1', createStepName='Initial',region=region, u1=SET, u2=SET, u3=UNSET, ur1=UNSET, ur2=UNSET, ur3=UNSET, distributionType=UNIFORM, fieldName='', localCsys=None)
                mdb.models[modelName].boundaryConditions['G12-1'].setValuesInStep(stepName='Step-0', u1=Dispx, u2=Dispy)
                mdb.models[modelName].boundaryConditions['G12-1'].setValuesInStep(stepName='Step-1', u1=Dispx+0j, u2=Dispy+0j)
                
                region = a.sets['RP5']
                mdb.models[modelName].DisplacementBC(name='G12-2', createStepName='Step-0',region=region, u1=0.0, u2=0.0, u3=0.0,ur1=UNSET, ur2=UNSET, ur3=UNSET,amplitude=UNSET, fixed=OFF, distributionType=UNIFORM, fieldName='',localCsys=None)
                region = a.sets['RP6']
                mdb.models[modelName].DisplacementBC(name='G12-3', createStepName='Step-0',region=region, u1=0.0, u2=0.0, u3=0.0,ur1=UNSET, ur2=UNSET, ur3=UNSET,amplitude=UNSET, fixed=OFF, distributionType=UNIFORM, fieldName='',localCsys=None)
                _set_viscoelastic_initial_temperature(modelName, a, temperature)
                _insert_viscoelastic_3d_keyword_pbc(modelName, 'G', pbcKeywordArgs)
                
                regionDef=mdb.models[modelName].rootAssembly.sets['c1']
                
                import os, glob
                
                if jobName in mdb.jobs.keys():
                    del mdb.jobs[jobName]
                mdb.Job(name=jobName, model=modelName, description='', type=ANALYSIS,
                        atTime=None, waitMinutes=0, waitHours=0, queue=None, memory=98,
                        memoryUnits=PERCENTAGE, getMemoryFromAnalysis=True,
                        explicitPrecision=SINGLE, nodalOutputPrecision=SINGLE, echoPrint=OFF,
                        modelPrint=OFF, contactPrint=OFF, historyPrint=OFF, userSubroutine=umatName,
                        scratch='', multiprocessingMode=DEFAULT, numCpus=CPUs, numDomains=CPUs, numGPUs=0)
                mdb.jobs[jobName].submit(consistencyChecking=OFF)
                mdb.jobs[jobName].waitForCompletion()
                
                odb_path = os.path.join(path, jobName + '.odb')
                o3 = session.openOdb(name=odb_path)
                
                file_name = '{}_G12_viscoelastic_freq_Temp{:03d}.csv'.format(baseModelName, int(temperature))
                with open(file_name, 'w') as file:
                    file.write('Frequency [Hz], G12_storage [Unit], G12_loss [Unit]\n')
                    written_data = set()
                    
                    freq_step_name = o3.steps.keys()[-1]
                    freq_step = o3.steps[freq_step_name]
                    shear_strain_12 = (Dispx / H) + (Dispy / L)
                    
                    for frame in freq_step.frames:
                        if frame.frameValue == 0.0:
                            continue
                        freq_value = frame.frequency
                        
                        rf_field = frame.fieldOutputs['RF']
                        rf_RP4 = rf_field.getSubset(region=o3.rootAssembly.nodeSets['RP4']).values[0]
                        forceG12_real = rf_RP4.data[0]
                        forceG12_imag = rf_RP4.conjugateData[0]
                        G12_storage = (forceG12_real / (L * W)) / shear_strain_12
                        G12_loss    = (forceG12_imag / (L * W)) / shear_strain_12
                        
                        data_tuple = (freq_value, G12_storage, G12_loss)
                        if data_tuple not in written_data:
                            written_data.add(data_tuple)
                            file.write('{:.10e}, {:.10e}, {:.10e}\n'.format(*data_tuple))
                
                o3.close()
                _delete_viscoelastic_case_model(caseModelName)
                print("====> Results have been saved in {}.".format(file_name))
                print('---------- Successful calculation of equivalent viscoelasticity G12 ----------')
                modelName = baseModelName
                a = mdb.models[modelName].rootAssembly
                
            ## Shear modulus G13(f)
            if G12==False:
                G12='N/A'
            if G13==True:
                caseModelName, a = _prepare_viscoelastic_frequency_case_model(
                    baseModelName, 'G13', lowerFreq, upperFreq, numPoints, bias
                )
                modelName = caseModelName
                jobName = _viscoelastic_job_name(baseModelName, 'G13', temperature)
                for i in mdb.models[modelName].loads.keys():
                        del mdb.models[modelName].loads[i]
                for i in mdb.models[modelName].boundaryConditions.keys():
                        del mdb.models[modelName].boundaryConditions[i]
                        
                region = a.sets['RP4']
                mdb.models[modelName].DisplacementBC(name='G13-2', createStepName='Step-0', region=region, u1=0, u2=0, u3=0, ur1=UNSET, ur2=UNSET, ur3=UNSET, amplitude=UNSET, fixed=OFF, distributionType=UNIFORM, fieldName='', localCsys=None)
                region = a.sets['RP5']
                
                mdb.models[modelName].DisplacementBC(name='G13-1', createStepName='Initial',region=region, u1=SET, u2=UNSET, u3=SET, ur1=UNSET, ur2=UNSET, ur3=UNSET, distributionType=UNIFORM, fieldName='', localCsys=None)
                mdb.models[modelName].boundaryConditions['G13-1'].setValuesInStep(stepName='Step-0', u1=Dispx, u3=Dispz)
                mdb.models[modelName].boundaryConditions['G13-1'].setValuesInStep(stepName='Step-1', u1=Dispx+0j, u3=Dispz+0j)
                region = a.sets['RP6']
                mdb.models[modelName].DisplacementBC(name='G13-3', createStepName='Step-0', region=region, u1=0, u2=0, u3=0, ur1=UNSET, ur2=UNSET, ur3=UNSET, amplitude=UNSET, fixed=OFF, distributionType=UNIFORM, fieldName='', localCsys=None)
                _set_viscoelastic_initial_temperature(modelName, a, temperature)
                _insert_viscoelastic_3d_keyword_pbc(modelName, 'G', pbcKeywordArgs)
                
                regionDef=mdb.models[modelName].rootAssembly.sets['c1']
                
                import os, glob
                
                if jobName in mdb.jobs.keys():
                    del mdb.jobs[jobName]
                mdb.Job(name=jobName, model=modelName, description='', type=ANALYSIS,
                        atTime=None, waitMinutes=0, waitHours=0, queue=None, memory=98,
                        memoryUnits=PERCENTAGE, getMemoryFromAnalysis=True,
                        explicitPrecision=SINGLE, nodalOutputPrecision=SINGLE, echoPrint=OFF,
                        modelPrint=OFF, contactPrint=OFF, historyPrint=OFF, userSubroutine=umatName,
                        scratch='', multiprocessingMode=DEFAULT, numCpus=CPUs, numDomains=CPUs, numGPUs=0)
                mdb.jobs[jobName].submit(consistencyChecking=OFF)
                mdb.jobs[jobName].waitForCompletion()
                
                odb_path = os.path.join(path, jobName + '.odb')
                o3 = session.openOdb(name=odb_path)
                
                file_name = '{}_G13_viscoelastic_freq_Temp{:03d}.csv'.format(baseModelName, int(temperature))
                with open(file_name, 'w') as file:
                    file.write('Frequency [Hz], G13_storage [Unit], G13_loss [Unit]\n')
                    written_data = set()
                    
                    freq_step_name = o3.steps.keys()[-1]
                    freq_step = o3.steps[freq_step_name]
                    shear_strain_13 = (Dispx / W) + (Dispz / L)
                    
                    for frame in freq_step.frames:
                        if frame.frameValue == 0.0:
                            continue
                        freq_value = frame.frequency
                        
                        rf_field = frame.fieldOutputs['RF']
                        rf_RP5 = rf_field.getSubset(region=o3.rootAssembly.nodeSets['RP5']).values[0]
                        forceG13_real = rf_RP5.data[0]
                        forceG13_imag = rf_RP5.conjugateData[0]
                        G13_storage = (forceG13_real / (H * L)) / shear_strain_13
                        G13_loss    = (forceG13_imag / (H * L)) / shear_strain_13
                        
                        data_tuple = (freq_value, G13_storage, G13_loss)
                        if data_tuple not in written_data:
                            written_data.add(data_tuple)
                            file.write('{:.10e}, {:.10e}, {:.10e}\n'.format(*data_tuple))
                
                o3.close()
                _delete_viscoelastic_case_model(caseModelName)
                print("====> Results have been saved in {}.".format(file_name))
                print('---------- Successful calculation of equivalent viscoelasticity G13 ----------')
                modelName = baseModelName
                a = mdb.models[modelName].rootAssembly
                
            if G13==False:
                    G13='N/A'
            ## Shear modulus G23(f)
            if G23==True:
                caseModelName, a = _prepare_viscoelastic_frequency_case_model(
                    baseModelName, 'G23', lowerFreq, upperFreq, numPoints, bias
                )
                modelName = caseModelName
                jobName = _viscoelastic_job_name(baseModelName, 'G23', temperature)
                for i in mdb.models[modelName].loads.keys():
                        del mdb.models[modelName].loads[i]
                for i in mdb.models[modelName].boundaryConditions.keys():
                        del mdb.models[modelName].boundaryConditions[i]
                        
                region = a.sets['RP4']
                mdb.models[modelName].DisplacementBC(name='G23-2', createStepName='Step-0',region=region, u1=0.0, u2=0.0, u3=0.0,ur1=UNSET, ur2=UNSET, ur3=UNSET,amplitude=UNSET, fixed=OFF, distributionType=UNIFORM, fieldName='',localCsys=None)
                region = a.sets['RP5']
                mdb.models[modelName].DisplacementBC(name='G23-3', createStepName='Step-0',region=region, u1=0.0, u2=0.0, u3=0.0,ur1=UNSET, ur2=UNSET, ur3=UNSET,amplitude=UNSET, fixed=OFF, distributionType=UNIFORM, fieldName='',localCsys=None)
                region = a.sets['RP6']
                
                mdb.models[modelName].DisplacementBC(name='G23-1', createStepName='Initial',region=region, u1=UNSET, u2=SET, u3=SET, ur1=UNSET, ur2=UNSET, ur3=UNSET, distributionType=UNIFORM, fieldName='', localCsys=None)
                mdb.models[modelName].boundaryConditions['G23-1'].setValuesInStep(stepName='Step-0', u2=Dispy, u3=Dispz)
                mdb.models[modelName].boundaryConditions['G23-1'].setValuesInStep(stepName='Step-1', u2=Dispy+0j, u3=Dispz+0j)
                _set_viscoelastic_initial_temperature(modelName, a, temperature)
                _insert_viscoelastic_3d_keyword_pbc(modelName, 'G', pbcKeywordArgs)
                
                regionDef=mdb.models[modelName].rootAssembly.sets['c1']
                
                import os, glob
                
                if jobName in mdb.jobs.keys():
                    del mdb.jobs[jobName]
                mdb.Job(name=jobName, model=modelName, description='', type=ANALYSIS,
                        atTime=None, waitMinutes=0, waitHours=0, queue=None, memory=98,
                        memoryUnits=PERCENTAGE, getMemoryFromAnalysis=True,
                        explicitPrecision=SINGLE, nodalOutputPrecision=SINGLE, echoPrint=OFF,
                        modelPrint=OFF, contactPrint=OFF, historyPrint=OFF, userSubroutine=umatName,
                        scratch='', multiprocessingMode=DEFAULT, numCpus=CPUs, numDomains=CPUs, numGPUs=0)
                mdb.jobs[jobName].submit(consistencyChecking=OFF)
                
                mdb.jobs[jobName].waitForCompletion()
                
                odb_path = os.path.join(path, jobName + '.odb')
                o3 = session.openOdb(name=odb_path)
                
                file_name = '{}_G23_viscoelastic_freq_Temp{:03d}.csv'.format(baseModelName, int(temperature))
                with open(file_name, 'w') as file:
                    file.write('Frequency [Hz], G23_storage [Unit], G23_loss [Unit]\n')
                    written_data = set()
                    
                    freq_step_name = o3.steps.keys()[-1]
                    freq_step = o3.steps[freq_step_name]
                    shear_strain_23 = (Dispy / W) + (Dispz / H)
                    
                    for frame in freq_step.frames:
                        if frame.frameValue == 0.0:
                            continue
                        freq_value = frame.frequency
                        
                        rf_field = frame.fieldOutputs['RF']
                        rf_RP6 = rf_field.getSubset(region=o3.rootAssembly.nodeSets['RP6']).values[0]
                        forceG23_real = rf_RP6.data[1]
                        forceG23_imag = rf_RP6.conjugateData[1]
                        G23_storage = (forceG23_real / (L * H)) / shear_strain_23
                        G23_loss    = (forceG23_imag / (L * H)) / shear_strain_23
                        
                        data_tuple = (freq_value, G23_storage, G23_loss)
                        if data_tuple not in written_data:
                            written_data.add(data_tuple)
                            file.write('{:.10e}, {:.10e}, {:.10e}\n'.format(*data_tuple))
                
                o3.close()
                _delete_viscoelastic_case_model(caseModelName)
                print("====> Results have been saved in {}.".format(file_name))
                print('---------- Successful calculation of equivalent viscoelasticity G23 ----------')
                modelName = baseModelName
                a = mdb.models[modelName].rootAssembly

            if G23==False:
                    G23='N/A'
            density = 0
            if mass != None:
                    density = mass/(L*W*H)
            
            # combine the .csv files
            csv_files = glob.glob(f'{baseModelName}*.csv')
            if not csv_files:
                exit()
            file_data = []
            for file in csv_files:
                with open(file, 'r', newline='') as f:
                    reader = csv.reader(f)
                    rows = list(reader)
                    if not rows:
                        continue
                    header = rows[0]
                    data = rows[1:]
                    file_data.append((header, data))
            if not file_data:
                exit()
            
            merged_header = []
            for header, _ in file_data:
                merged_header.extend(header)
            
            max_rows = max([len(data) for _, data in file_data])
            
            merged_data = []
            for i in range(max_rows):
                merged_row = []
                for header, data in file_data:
                    num_cols = len(header)
                    if i < len(data):
                        row = data[i]
                        if len(row) < num_cols:
                            row = row + [''] * (num_cols - len(row))
                    else:
                        row = [''] * num_cols
                    merged_row.extend(row)
                merged_data.append(merged_row)
            
            output_file = f'{baseModelName}_viscoelastic_freq_results_Temp{int(temperature):03d}.csv'
            with open(output_file, 'w', newline='') as f_out:
                writer = csv.writer(f_out)
                writer.writerow(merged_header)
                writer.writerows(merged_data)
            
            # Calculate Cij from Eij and Poisson's ratios
            # Read the merged results to extract Eij and vij vs time
            merged_csv = output_file
            with open(merged_csv, 'r') as f:
                reader = csv.reader(f)
                all_rows = list(reader)
            
            header_row = [h.strip() for h in all_rows[0]]
            
            def col_idx(name):
                for idx, h in enumerate(header_row):
                    if name in h:
                        return idx
                return None
            
            # Find column indices
            freq_idx     = col_idx('Frequency [Hz]')
            E11s_idx     = col_idx('E11_storage [Unit]')
            E11l_idx     = col_idx('E11_loss [Unit]')
            E22s_idx     = col_idx('E22_storage [Unit]')
            E22l_idx     = col_idx('E22_loss [Unit]')
            E33s_idx     = col_idx('E33_storage [Unit]')
            E33l_idx     = col_idx('E33_loss [Unit]')
            v12r_idx     = col_idx('v12_real')
            v12i_idx     = col_idx('v12_imag')
            v13r_idx     = col_idx('v13_real')
            v13i_idx     = col_idx('v13_imag')
            v21r_idx     = col_idx('v21_real')
            v21i_idx     = col_idx('v21_imag')
            v23r_idx     = col_idx('v23_real')
            v23i_idx     = col_idx('v23_imag')
            v31r_idx     = col_idx('v31_real')
            v31i_idx     = col_idx('v31_imag')
            v32r_idx     = col_idx('v32_real')
            v32i_idx     = col_idx('v32_imag')
            G12s_idx     = col_idx('G12_storage [Unit]')
            G12l_idx     = col_idx('G12_loss [Unit]')
            G13s_idx     = col_idx('G13_storage [Unit]')
            G13l_idx     = col_idx('G13_loss [Unit]')
            G23s_idx     = col_idx('G23_storage [Unit]')
            G23l_idx     = col_idx('G23_loss [Unit]')
            
            cij_file = f'{modelName}_viscoelastic_freq_results_Cij_Temp{int(temperature):03d}.csv'
            with open(cij_file, 'w', newline='') as f_cij:
                writer_cij = csv.writer(f_cij)
                writer_cij.writerow(['Frequency [Hz]', 'Angular Frequency [rad/s]',
                    'C11_storage [Unit]', 'C11_loss [Unit]', 'C22_storage [Unit]', 'C22_loss [Unit]', 'C33_storage [Unit]', 'C33_loss [Unit]',
                    'C12_storage [Unit]', 'C12_loss [Unit]', 'C13_storage [Unit]', 'C13_loss [Unit]', 'C23_storage [Unit]', 'C23_loss [Unit]',
                    'C44_storage [Unit]', 'C44_loss [Unit]', 'C55_storage [Unit]', 'C55_loss [Unit]', 'C66_storage [Unit]', 'C66_loss [Unit]'])
                
                for row in all_rows[1:]:
                    try:
                        freq = float(row[freq_idx]) if freq_idx is not None else None
                        omega = 2 * math.pi * freq
                
                        E11s = float(row[E11s_idx]) if E11s_idx is not None else None
                        E11l = float(row[E11l_idx]) if E11l_idx is not None else None
                        E22s = float(row[E22s_idx]) if E22s_idx is not None else None
                        E22l = float(row[E22l_idx]) if E22l_idx is not None else None
                        E33s = float(row[E33s_idx]) if E33s_idx is not None else None
                        E33l = float(row[E33l_idx]) if E33l_idx is not None else None
                
                        v12r = float(row[v12r_idx]) if v12r_idx is not None else 0.0
                        v12i = float(row[v12i_idx]) if v12i_idx is not None else 0.0
                        v13r = float(row[v13r_idx]) if v13r_idx is not None else 0.0
                        v13i = float(row[v13i_idx]) if v13i_idx is not None else 0.0
                        v21r = float(row[v21r_idx]) if v21r_idx is not None else 0.0
                        v21i = float(row[v21i_idx]) if v21i_idx is not None else 0.0
                        v23r = float(row[v23r_idx]) if v23r_idx is not None else 0.0
                        v23i = float(row[v23i_idx]) if v23i_idx is not None else 0.0
                        v31r = float(row[v31r_idx]) if v31r_idx is not None else 0.0
                        v31i = float(row[v31i_idx]) if v31i_idx is not None else 0.0
                        v32r = float(row[v32r_idx]) if v32r_idx is not None else 0.0
                        v32i = float(row[v32i_idx]) if v32i_idx is not None else 0.0
                
                        G12s = float(row[G12s_idx]) if G12s_idx is not None else None
                        G12l = float(row[G12l_idx]) if G12l_idx is not None else None
                        G13s = float(row[G13s_idx]) if G13s_idx is not None else None
                        G13l = float(row[G13l_idx]) if G13l_idx is not None else None
                        G23s = float(row[G23s_idx]) if G23s_idx is not None else None
                        G23l = float(row[G23l_idx]) if G23l_idx is not None else None
                
                        if None in (freq, E11s, E11l, E22s, E22l, E33s, E33l):
                            continue
                
                        # Build complex compliance matrix S* = S' + iS''
                        E11c = complex(E11s, E11l)
                        E22c = complex(E22s, E22l)
                        E33c = complex(E33s, E33l)
                        v12c = complex(v12r, v12i)
                        v13c = complex(v13r, v13i)
                        v21c = complex(v21r, v21i)
                        v23c = complex(v23r, v23i)
                        v31c = complex(v31r, v31i)
                        v32c = complex(v32r, v32i)
                        G12c = complex(G12s, G12l) if (G12s is not None and G12l is not None) else None
                        G13c = complex(G13s, G13l) if (G13s is not None and G13l is not None) else None
                        G23c = complex(G23s, G23l) if (G23s is not None and G23l is not None) else None
                
                        S = np.array([
                            [ 1/E11c,    -v12c/E11c, -v13c/E11c, 0, 0, 0],
                            [-v21c/E22c,  1/E22c,    -v23c/E22c, 0, 0, 0],
                            [-v31c/E33c, -v32c/E33c,  1/E33c,    0, 0, 0],
                            [0, 0, 0, 1/G23c if G23c is not None else 0, 0, 0],
                            [0, 0, 0, 0, 1/G13c if G13c is not None else 0, 0],
                            [0, 0, 0, 0, 0, 1/G12c if G12c is not None else 0],
                        ], dtype=complex)
                        C = np.linalg.inv(S)
                
                        writer_cij.writerow([
                            '{:.14e}'.format(freq),
                            '{:.14e}'.format(omega),
                            '{:.14e}'.format(C[0,0].real ), '{:.14e}'.format(C[0,0].imag ),
                            '{:.14e}'.format(C[1,1].real ), '{:.14e}'.format(C[1,1].imag ),
                            '{:.14e}'.format(C[2,2].real ), '{:.14e}'.format(C[2,2].imag ),
                            '{:.14e}'.format(C[0,1].real ), '{:.14e}'.format(C[0,1].imag ),
                            '{:.14e}'.format(C[0,2].real ), '{:.14e}'.format(C[0,2].imag ),
                            '{:.14e}'.format(C[1,2].real ), '{:.14e}'.format(C[1,2].imag ),
                            '{:.14e}'.format(C[3,3].real ), '{:.14e}'.format(C[3,3].imag ),
                            '{:.14e}'.format(C[4,4].real ), '{:.14e}'.format(C[4,4].imag ),
                            '{:.14e}'.format(C[5,5].real ), '{:.14e}'.format(C[5,5].imag ),
                        ])
                    except (ValueError, IndexError, np.linalg.LinAlgError):
                        continue
            
            print("====> Cij results saved in {}.".format(cij_file))
            
            print ('================================================================================================================')
            print ('The effective viscoelastic stress relaxation stiffness matrix is saved in ABAQUS Work Directory under .csv files')
            print ('================================================================================================================')
            print ('---------------------------------------')
            print ('---- End of EasyPBC (Viscoelastic) ----')
            print ('---------------------------------------')
        if error==True:
            print ('Error(s) found during sets creation, please check the error No.(s) above with EasyPBC user guide.')
            
            a.SetFromNodeLabels(name='Error set', nodeLabels=((instanceName,errorset),))

