# -*- coding: utf-8 -*-
###############################################################################
# PBC_UDFRP_thermal_conductivity.py
# -----------------------------------------------------------------------------
# Steady-state thermal-conductivity homogenization of a UDFRP RVE under
# periodic temperature boundary conditions. Returns the effective
# conductivity tensor components K11/K22/K33 (and off-diagonals when needed).
# Called from RVE_Builder_UDFRPs.Analysis when analysis_type == 5.
###############################################################################
## Importing ABAQUS Data and Python modules ##
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
import re
from odbAccess import openOdb

def _thermal_node_ref(instanceName, label):
    return '%s.%s' % (instanceName, int(label))

def build_equation_keywords(eqs):
    lines = []
    for terms in eqs:
        lines.append('*Equation')
        lines.append(str(len(terms)))
        for pos in range(0, len(terms), 4):
            seg = ', '.join(['%s, %d, %s' % (ref, dof, repr(float(coef)))
                            for (coef, ref, dof) in terms[pos:pos + 4]])
            lines.append(seg)
    return '\n'.join(lines)

def _insert_equation_keywords(modelName, eqs):
    if not eqs:
        return
    kb = mdb.models[modelName].keywordBlock
    kb.synchVersions(storeNodesAndElements=False)
    idx = None
    for n, line in enumerate(kb.sieBlocks):
        if line.lstrip().lower().startswith('*end assembly'):
            idx = n
            break
    if idx is None:
        for n, line in enumerate(kb.sieBlocks):
            if line.lstrip().lower().startswith('*step'):
                idx = n
                break
    if idx is None:
        idx = len(kb.sieBlocks)
    kb.insert(max(idx - 1, 0), build_equation_keywords(eqs))

def _append_standard_thermal_pbc(eqs, instanceName, tops, bots, lefts, rights,
                                 fronts, backs, fledge, bledge, bredge,
                                 fredge, ltedge, lbedge, rbedge, rtedge,
                                 ftedge, btedge, bbedge, fbedge):
    n = lambda label: _thermal_node_ref(instanceName, label)
    for i, k in zip(tops, bots):
        eqs.append([(1.0, n(i), 11), (-1.0, n(k), 11), (-1.0, 'RP2', 11)])
    for i, k in zip(lefts, rights):
        eqs.append([(1.0, n(i), 11), (-1.0, n(k), 11), (-1.0, 'RP3', 11)])
    for i, k in zip(fronts, backs):
        eqs.append([(1.0, n(i), 11), (-1.0, n(k), 11), (-1.0, 'RP1', 11)])

    eqs.append([(1.0, 'c6', 11), (-1.0, 'c2', 11), (1.0, 'RP2', 11)])
    eqs.append([(1.0, 'c2', 11), (-1.0, 'c3', 11), (-1.0, 'RP3', 11)])
    eqs.append([(1.0, 'c3', 11), (-1.0, 'c4', 11), (1.0, 'RP1', 11)])
    eqs.append([(1.0, 'c4', 11), (-1.0, 'c8', 11), (-1.0, 'RP2', 11)])
    eqs.append([(1.0, 'c8', 11), (-1.0, 'c5', 11), (1.0, 'RP3', 11)])
    eqs.append([(1.0, 'c5', 11), (-1.0, 'c1', 11), (1.0, 'RP2', 11)])
    eqs.append([(1.0, 'c1', 11), (-1.0, 'c7', 11), (-1.0, 'RP1', 11), (-1.0, 'RP2', 11), (-1.0, 'RP3', 11)])

    for i, k, j, l in zip(fledge, bledge, bredge, fredge):
        eqs.append([(1.0, n(i), 11), (-1.0, n(k), 11), (-1.0, 'RP1', 11)])
        eqs.append([(1.0, n(k), 11), (-1.0, n(j), 11), (-1.0, 'RP3', 11)])
        eqs.append([(1.0, n(j), 11), (-1.0, n(l), 11), (1.0, 'RP1', 11)])

    for i, k, j, l in zip(ltedge, lbedge, rbedge, rtedge):
        eqs.append([(1.0, n(i), 11), (-1.0, n(k), 11), (-1.0, 'RP2', 11)])
        eqs.append([(1.0, n(k), 11), (-1.0, n(j), 11), (-1.0, 'RP3', 11)])
        eqs.append([(1.0, n(j), 11), (-1.0, n(l), 11), (1.0, 'RP2', 11)])

    for i, k, j, l in zip(ftedge, btedge, bbedge, fbedge):
        eqs.append([(1.0, n(i), 11), (-1.0, n(k), 11), (-1.0, 'RP1', 11)])
        eqs.append([(1.0, n(k), 11), (-1.0, n(j), 11), (-1.0, 'RP2', 11)])
        eqs.append([(1.0, n(j), 11), (-1.0, n(l), 11), (1.0, 'RP1', 11)])

def _clear_thermal_analysis_features(modelObj):
    for stepName in ('K33', 'K22', 'K11'):
        if stepName in modelObj.steps.keys():
            del modelObj.steps[stepName]
    for loadName in list(modelObj.loads.keys()):
        del modelObj.loads[loadName]
    for bcName in list(modelObj.boundaryConditions.keys()):
        del modelObj.boundaryConditions[bcName]
    if 'F-Output-1' in modelObj.fieldOutputRequests.keys():
        del modelObj.fieldOutputRequests['F-Output-1']

def _create_thermal_steps_and_bcs(modelObj, a, T_ref, delta_T):
    modelObj.HeatTransferStep(name='K11', previous='Initial', response=STEADY_STATE, amplitude=RAMP)
    modelObj.TemperatureBC(name='fixK11', createStepName='K11', region=a.sets['backbc'], magnitude=T_ref - delta_T/2.0, distributionType=UNIFORM)
    modelObj.TemperatureBC(name='gradK11', createStepName='K11', region=a.sets['RP1'], magnitude=delta_T, distributionType=UNIFORM)

    modelObj.HeatTransferStep(name='K22', previous='K11', response=STEADY_STATE, amplitude=RAMP)
    modelObj.TemperatureBC(name='fixK22', createStepName='K22', region=a.sets['botbc'], magnitude=T_ref - delta_T/2.0, distributionType=UNIFORM)
    modelObj.TemperatureBC(name='gradK22', createStepName='K22', region=a.sets['RP2'], magnitude=delta_T, distributionType=UNIFORM)

    modelObj.HeatTransferStep(name='K33', previous='K22', response=STEADY_STATE, amplitude=RAMP)
    modelObj.TemperatureBC(name='fixK33', createStepName='K33', region=a.sets['rightbc'], magnitude=T_ref - delta_T/2.0, distributionType=UNIFORM)
    modelObj.TemperatureBC(name='gradK33', createStepName='K33', region=a.sets['RP3'], magnitude=delta_T, distributionType=UNIFORM)

    modelObj.boundaryConditions['fixK11'].deactivate('K22')
    modelObj.boundaryConditions['gradK11'].deactivate('K22')
    modelObj.boundaryConditions['fixK22'].deactivate('K33')
    modelObj.boundaryConditions['gradK22'].deactivate('K33')
    modelObj.FieldOutputRequest(name='F-Output-1', createStepName='K11', variables=('HFL','NT','RFL','IVOL',))

def _calculate_conductivity_from_step(odb, upperName, stepName, RVE_volume, temp_gradient):
    step = odb.steps[stepName]
    frame = step.frames[-1]
    hfl_field = frame.fieldOutputs['HFL']
    ivol_field = frame.fieldOutputs['IVOL']
    hfl1_dict = {}
    hfl2_dict = {}
    hfl3_dict = {}
    ivol_dict = {}

    for value in hfl_field.values:
        key = (value.elementLabel, value.integrationPoint)
        hfl1_dict[key] = value.data[0]
        hfl2_dict[key] = value.data[1]
        hfl3_dict[key] = value.data[2]
    for value in ivol_field.values:
        key = (value.elementLabel, value.integrationPoint)
        ivol_dict[key] = value.data

    odb_instance = odb.rootAssembly.instances[upperName]
    total_heat_flux_k1 = 0.0
    total_heat_flux_k2 = 0.0
    total_heat_flux_k3 = 0.0

    for element in odb_instance.elements:
        element_label = element.label
        element_type = element.type if hasattr(element, 'type') else None
        if element_type == 'DC3D8':
            num_ip = 8
        elif element_type == 'DC3D6':
            num_ip = 6
        else:
            print(f"Unsupported element type: {element_type}")
            continue

        for ip in range(1, num_ip + 1):
            key = (element_label, ip)
            if key in hfl1_dict and key in ivol_dict:
                total_heat_flux_k1 += hfl1_dict[key] * ivol_dict[key]
            if key in hfl2_dict and key in ivol_dict:
                total_heat_flux_k2 += hfl2_dict[key] * ivol_dict[key]
            if key in hfl3_dict and key in ivol_dict:
                total_heat_flux_k3 += hfl3_dict[key] * ivol_dict[key]

    q_avg_k1 = total_heat_flux_k1 / RVE_volume
    q_avg_k2 = total_heat_flux_k2 / RVE_volume
    q_avg_k3 = total_heat_flux_k3 / RVE_volume
    return -q_avg_k1 / temp_gradient, -q_avg_k2 / temp_gradient, -q_avg_k3 / temp_gradient

## Plugin main GUI function ##

def feasypbc(part,inst,meshsens,K11,K22,K33,CPU,onlyPBC, intemp, fntemp):
    import os
    path = os.getcwd()
    for T in (range(1)):
        start = time.time()
        modelName = part
        instanceName = inst
        partName = instanceName.replace('-1','')
        upperName= inst.upper()
        fail = []
        keycheck2 =[inst]
        if part not in (mdb.models.keys()):
                Er2=0
                messageBox2 = ctypes.windll.user32.MessageBoxA
                returnValue = messageBox2(Er2,'Model name is incorrect, please input the correct Model name.','EasyPBC Start-up error 02',0x30 | 0x0)
                print('Start-up error 02. Refer EasyPBC user guide')
                continue
        a = mdb.models[modelName].rootAssembly
        errorcheck1 = mdb.models[modelName].rootAssembly.instances.keys()
        if errorcheck1 == fail:
                Er1=0
                messageBox1 = ctypes.windll.user32.MessageBoxA
                returnValue = messageBox1(Er1,'Model part is not created!\nPlease create part and try again','EasyPBC Start-up error 01',0x30 | 0x0)
                print('Start-up error 01. Refer EasyPBC user guide')
                continue
        if (mdb.models[modelName].rootAssembly.instances.keys()) != keycheck2:                       
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
        error=False
        print(('----------------------------------'))
        print(('-------- Start of EasyPBC --------'))
        print(('----------------------------------'))
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
        ## 3D model ##########################################################
        L=abs(Max-Mnx)
        H=abs(May-Mny)
        W=abs(Maz-Mnz)
        Dispx = L*0.2
        Dispy = H*0.2
        Dispz = W*0.2
        ## Creating Ref. Points ##
        for i in a.features.keys():
            if i.startswith('RP'):
                del a.features['%s' % (i)]
        a.ReferencePoint(point=(Max+0.8*abs(Max-Mnx), May-0.5*(May-Mny), Maz-0.5*(Maz-Mnz)))  ## RP1: G23
        a.ReferencePoint(point=(Max+0.6*abs(Max-Mnx), May-0.5*(May-Mny), Maz-0.5*(Maz-Mnz)))  ## RP2: G13
        a.ReferencePoint(point=(Max+0.4*abs(Max-Mnx), May-0.5*(May-Mny), Maz-0.5*(Maz-Mnz)))  ## RP3: G12
        a.ReferencePoint(point=(Max+0.2*abs(Max-Mnx), May-0.5*(May-Mny), Maz-0.5*(Maz-Mnz)))  ## RP3: Rigid body movement X-axis
        a.ReferencePoint(point=(Max-0.5*(Max-Mnx), May-0.5*(May-Mny), Maz+0.2*abs(Maz-Mnz)))  ## RP2: Rigid body movement Z-axis
        a.ReferencePoint(point=(Max-0.5*(Max-Mnx), May+0.2*abs(May-Mny), Maz-0.5*(Maz-Mnz)))  ## RP1: Rigid body movement Y-axis
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
        a.SetFromNodeLabels(name='botface', nodeLabels=((instanceName,botbc),))
        elem_labels = [elem.label for elem in mdb.models[modelName].rootAssembly.instances[instanceName].elements]
        a.SetFromElementLabels(name='ALL_ELEMS', elementLabels=((instanceName, elem_labels),))
        all_nodes = mdb.models[modelName].rootAssembly.instances[instanceName].nodes
        all_node_labels = [node.label for node in all_nodes]
        a.SetFromNodeLabels(name='ALL_NODES', nodeLabels=((instanceName, all_node_labels),))
        print('------ End of Sets Creation ------')

    ## Extracting model mass ##
    prop = mdb.models[modelName].rootAssembly.getMassProperties()
    mass = prop['mass']
    a = mdb.models[modelName].rootAssembly
    Nodeset = a.instances[instanceName].nodes
    ## Collecting keyword-block PBC equations ##
    if error == False:
        eqs = []
        thermal_setup_start = time.time()
        if K11 == True or K22 == True or K33 == True:
            for i in list(mdb.models[modelName].constraints.keys()):
                    del mdb.models[modelName].constraints[i]
            _append_standard_thermal_pbc(
                eqs, instanceName, tops, bots, lefts, rights, fronts, backs,
                fledge, bledge, bredge, fredge, ltedge, lbedge, rbedge,
                rtedge, ftedge, btedge, bbedge, fbedge
            )
            print('------ Thermal PBC equations collected for keyword block: %s ------' % len(eqs))
            print('------ Thermal PBC equation collection duration %.3f seconds ------' % (time.time() - thermal_setup_start))
                
        # temperature
        # Each temperature point is solved as an ISOTHERMAL state at the target
        # temperature T_ref = intemp: a tiny probe gradient delta_T is applied
        # and the RVE is centred on T_ref (via the fixed-face BCs below), so a
        # temperature-dependent conductivity is evaluated AT that point and the
        # swept points give k_eff(T). delta_T's magnitude does not bias k_eff
        # (the extraction k = -<HFL>/(delta_T/delta_x) is linear); keep it small
        # so the RVE stays effectively isothermal at T_ref.
        delta_T = 1.0
        T_ref = intemp
        delta_x = L
        delta_y = H
        delta_z = W
        RVE_volume = H * W * L
        
        K11_value = 'N/A'
        K21_value = 'N/A'
        K31_value = 'N/A'
        K12_value = 'N/A'
        K22_value = 'N/A'
        K32_value = 'N/A'
        K13_value = 'N/A'
        K23_value = 'N/A'
        K33_value = 'N/A'
        odb = None

        if K11 == True or K22 == True or K33 == True:
            if onlyPBC:
                _insert_equation_keywords(modelName, eqs)
                print('------ Thermal keyword block setup duration %.3f seconds ------' % (time.time() - thermal_setup_start))
            else:
                modelObj = mdb.models[modelName]
                thermalJobName = '%s-job-thermal' % modelName
                if thermalJobName in mdb.jobs.keys():
                    del mdb.jobs[thermalJobName]
                _clear_thermal_analysis_features(modelObj)
                _create_thermal_steps_and_bcs(modelObj, a, T_ref, delta_T)
                _insert_equation_keywords(modelName, eqs)
                print('------ Thermal keyword block setup duration before job submit %.3f seconds ------' % (time.time() - thermal_setup_start))
                mdb.Job(name=thermalJobName, model=modelName, description='', type=ANALYSIS, atTime=None, waitMinutes=0, waitHours=0, queue=None, memory=90, memoryUnits=PERCENTAGE, getMemoryFromAnalysis=True, explicitPrecision=SINGLE, nodalOutputPrecision=SINGLE, echoPrint=OFF, modelPrint=OFF, contactPrint=OFF, historyPrint=OFF, userSubroutine='', scratch='', multiprocessingMode=DEFAULT, numCpus=CPUs, numDomains=CPUs, numGPUs=1)
                mdb.jobs[thermalJobName].submit(consistencyChecking=OFF)
                mdb.jobs[thermalJobName].waitForCompletion()

                odb_path = '%s\\%s.odb' % (path, thermalJobName)
                o3 = session.openOdb(name=odb_path)
                odb = session.odbs[odb_path]

                if K11 == True:
                    K11_value, K21_value, K31_value = _calculate_conductivity_from_step(
                        odb, upperName, 'K11', RVE_volume, delta_T / delta_x
                    )
                    print(f'Effective thermal conductivity K11: {K11_value:.4f} W/(m·K)')
                    print(f'Effective thermal conductivity K21: {K21_value:.4f} W/(m·K)')
                    print(f'Effective thermal conductivity K31: {K31_value:.4f} W/(m·K)')

        ## Thermal conductivity K22 ##
        if K22 and not onlyPBC and odb is not None:
            K12_value, K22_value, K32_value = _calculate_conductivity_from_step(
                odb, upperName, 'K22', RVE_volume, delta_T / delta_y
            )
            print(f'Effective thermal conductivity K12: {K12_value:.4f} W/(m·K)')
            print(f'Effective thermal conductivity K22: {K22_value:.4f} W/(m·K)')
            print(f'Effective thermal conductivity K32: {K32_value:.4f} W/(m·K)')

        ## Thermal conductivity K33 ##
        if K33 and not onlyPBC and odb is not None:
            K13_value, K23_value, K33_value = _calculate_conductivity_from_step(
                odb, upperName, 'K33', RVE_volume, delta_T / delta_z
            )
            print(f'Effective thermal conductivity K13: {K13_value:.4f} W/(m·K)')
            print(f'Effective thermal conductivity K23: {K23_value:.4f} W/(m·K)')
            print(f'Effective thermal conductivity K33: {K33_value:.4f} W/(m·K)')

        if odb is not None:
            odb.close()

        density = 0
        if mass != None:
            density = mass / (L * W * H)

        print('----------------------------------------------------')
        print('----------------------------------------------------')
        print('The homogenised thermal properties:')
        print('K11=%s W/(m·K)' % ('N/A' if K11_value == 'N/A' else '%.4f' % K11_value))
        print('K22=%s W/(m·K)' % ('N/A' if K22_value == 'N/A' else '%.4f' % K22_value))
        print('K33=%s W/(m·K)' % ('N/A' if K33_value == 'N/A' else '%.4f' % K33_value))
        print('K12=%s W/(m·K)' % ('N/A' if K12_value == 'N/A' else '%.4f' % K12_value))
        print('K21=%s W/(m·K)' % ('N/A' if K21_value == 'N/A' else '%.4f' % K21_value))
        print('K13=%s W/(m·K)' % ('N/A' if K13_value == 'N/A' else '%.4f' % K13_value))
        print('K31=%s W/(m·K)' % ('N/A' if K31_value == 'N/A' else '%.4f' % K31_value))
        print('K23=%s W/(m·K)' % ('N/A' if K23_value == 'N/A' else '%.4f' % K23_value))
        print('K32=%s W/(m·K)' % ('N/A' if K32_value == 'N/A' else '%.4f' % K32_value))
        print('Processing duration %s seconds' % (time.time() - start))
        print('----------------------------------------------------')

        filename = f'{part}_thermal_properties.txt'
        print(f'The homogenised thermal properties are saved in ABAQUS Work Directory under {filename}')
        with open(filename, 'w') as f:
            f.write(f'{"Property":^10}{"Value":^20}{"Unit":^20}\n')
            f.write(f'{"K11":^10}{K11_value if K11_value == "N/A" else K11_value:^20}{"W/(m·K)":^20}\n')
            f.write(f'{"K22":^10}{K22_value if K22_value == "N/A" else K22_value:^20}{"W/(m·K)":^20}\n')
            f.write(f'{"K33":^10}{K33_value if K33_value == "N/A" else K33_value:^20}{"W/(m·K)":^20}\n')
            f.write(f'{"K12":^10}{K12_value if K12_value == "N/A" else K12_value:^20}{"W/(m·K)":^20}\n')
            f.write(f'{"K21":^10}{K21_value if K21_value == "N/A" else K21_value:^20}{"W/(m·K)":^20}\n')
            f.write(f'{"K13":^10}{K13_value if K13_value == "N/A" else K13_value:^20}{"W/(m·K)":^20}\n')
            f.write(f'{"K31":^10}{K31_value if K31_value == "N/A" else K31_value:^20}{"W/(m·K)":^20}\n')
            f.write(f'{"K23":^10}{K23_value if K23_value == "N/A" else K23_value:^20}{"W/(m·K)":^20}\n')
            f.write(f'{"K32":^10}{K32_value if K32_value == "N/A" else K32_value:^20}{"W/(m·K)":^20}\n')
            f.write(f'Total mass={mass} Mass units\n')
            f.write(f'Homogenised density={density} Density units\n')
            f.write(f'Processing duration {time.time() - start} Seconds\n')

        filename = f'{part}_thermal_properties(easycopy).txt'
        with open(filename, 'w') as f:
            f.write(f'{K11_value if K11_value == "N/A" else K11_value:^10}\n')
            f.write(f'{K22_value if K22_value == "N/A" else K22_value:^10}\n')
            f.write(f'{K33_value if K33_value == "N/A" else K33_value:^10}\n')
            f.write(f'{K12_value if K12_value == "N/A" else K12_value:^10}\n')
            f.write(f'{K21_value if K21_value == "N/A" else K21_value:^10}\n')
            f.write(f'{K13_value if K13_value == "N/A" else K13_value:^10}\n')
            f.write(f'{K31_value if K31_value == "N/A" else K31_value:^10}\n')
            f.write(f'{K23_value if K23_value == "N/A" else K23_value:^10}\n')
            f.write(f'{K32_value if K32_value == "N/A" else K32_value:^10}\n')
            if mass is None:
                mass = "N/A"
            if density is None:
                density = "N/A"
            f.write(f'{mass:^10}\n')
            f.write(f'{density:^10}\n')
            f.write(f'{(time.time() - start):^10}\n')

        print('----------------------------------------------------')
        if onlyPBC:
            print('EasyPBC created Periodic Boundary Conditions only. For further investigation, use relevant Reference Points to apply temperature gradients based on your needs.')

        if len(session.odbData.keys()) >= 1:
            a = mdb.models[modelName].rootAssembly

    if error:
        print('Error(s) found during sets creation, please check the error No.(s) above with EasyPBC user guide.')
        a.SetFromNodeLabels(name='Error set', nodeLabels=((instanceName, errorset),))
