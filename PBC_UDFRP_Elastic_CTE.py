# -*- coding: utf-8 -*-
###############################################################################
# PBC_UDFRP_Elastic_CTE.py
# -----------------------------------------------------------------------------
# Linear elastic + Coefficient of Thermal Expansion (CTE) homogenization of a
# UDFRP RVE under periodic boundary conditions. Called from
# RVE_Builder_UDFRPs.Analysis when analysis_type == 1.
###############################################################################
'''

Base on EasyPBC Ver. 1.4 (27/08/2019).
Updated to calculate CTE vs. temperature.(10/07/2025, Yuhao Meng)

From EasyPBC:
##      EasyPBC Ver. 1.4   (08/10/2018) updated on (27/08/2019) to calculte CTE and fix work directory change error.
##      EasyPBC is an ABAQUS CAE plugin developed to estimate the homogenised effective elastic properties of user created periodic(RVE))
##      Copyright (C) 2018  Sadik Lafta Omairey
##
##      This program is distributed in the hope that it will be useful,
##      but WITHOUT ANY WARRANTY; without even the implied warranty of
##      MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
##      GNU General Public License for more details.
##
##      You should have received a copy of the GNU General Public License
##      along with this program.  If not, see <https://www.gnu.org/licenses/>.
##      Kindly do not re-distribute as it is subjected to updates.
##
##      Citation: Omairey S, Dunning P, Sriramula S (2018) Development of an ABAQUS plugin tool for periodic RVE homogenisation.
##      Engineering with Computers. https://doi.org/10.1007/s00366-018-0616-4
##      Email sadik.omairey@gmail.com to obtain the latest version of the software.
'''

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
import numpy as np
import csv


def _set_uniform_initial_temperature(modelObj, assemblyObj, instanceName, temperature_value, field_name):
        node_labels = []
        for node in assemblyObj.allInstances[instanceName].nodes:
                node_labels.append(int(node.label))
        if 'ELASTIC_ALL_NODES' in assemblyObj.sets.keys():
                del assemblyObj.sets['ELASTIC_ALL_NODES']
        assemblyObj.SetFromNodeLabels(name='ELASTIC_ALL_NODES', nodeLabels=((instanceName, node_labels),))
        if field_name in modelObj.predefinedFields.keys():
                del modelObj.predefinedFields[field_name]
        modelObj.Temperature(name=field_name, createStepName='Initial',
                region=assemblyObj.sets['ELASTIC_ALL_NODES'], distributionType=UNIFORM,
                crossSectionDistribution=CONSTANT_THROUGH_THICKNESS, magnitudes=(temperature_value,))


# ---- Ported helpers from fillers/PBC_Elastic_CTE.py (Phase 3) ----
# Imported by PBC_UDFRP_Elastoplastic and other PBC modules.

def _pbc_sorted_labels(label_dict):
        labels = list(label_dict.keys())
        labels.sort()
        return labels

def _pbc_create_node_set(a, instanceName, setName, labels):
        if labels:
                a.SetFromNodeLabels(name=setName, nodeLabels=((instanceName, labels),))

def _pbc_single_node_set_name(label):
        return 'PBCNode%s' % (label)

def _pbc_create_single_node_sets(a, instanceName, labels):
        for label in labels:
                setName = _pbc_single_node_set_name(label)
                if setName not in a.sets.keys():
                        a.SetFromNodeLabels(name=setName, nodeLabels=((instanceName, [label]),))

def _pbc_reduced_coordinates(coords, axisIndex, dimension):
        if dimension == 2:
                if axisIndex == 0:
                        return np.array([coords[1]], dtype=float)
                return np.array([coords[0]], dtype=float)
        if axisIndex == 0:
                return np.array([coords[1], coords[2]], dtype=float)
        if axisIndex == 1:
                return np.array([coords[0], coords[2]], dtype=float)
        return np.array([coords[0], coords[1]], dtype=float)


def _pbc_get_3d_faces(element):
        conn = list(element.connectivity)
        if len(conn) in (4, 10):
                corners = conn[:4]
                localFaces = ((0, 1, 2), (0, 3, 1), (1, 3, 2), (2, 3, 0))
        elif len(conn) in (6, 15):
                corners = conn[:6]
                localFaces = ((0, 1, 2), (3, 5, 4), (0, 3, 4, 1), (1, 4, 5, 2), (2, 5, 3, 0))
        elif len(conn) in (5, 13):
                corners = conn[:5]
                localFaces = ((0, 1, 2, 3), (0, 4, 1), (1, 4, 2), (2, 4, 3), (3, 4, 0))
        else:
                corners = conn[:8]
                localFaces = ((0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0))
        faces = []
        for face in localFaces:
                faceLabels = []
                for i in face:
                        faceLabels.append(corners[i])
                faces.append(tuple(faceLabels))
        return faces

def _pbc_build_connectivity_label_map(instanceObj):
        connectivityLabelMap = {}
        usesNodeIndex = False
        for element in instanceObj.elements:
                if 0 in list(element.connectivity):
                        usesNodeIndex = True
                        break
        if usesNodeIndex:
                for nodeIndex, node in enumerate(instanceObj.nodes):
                        connectivityLabelMap[nodeIndex] = node.label
        else:
                for node in instanceObj.nodes:
                        connectivityLabelMap[node.label] = node.label
        return connectivityLabelMap


def _pbc_build_master_triangles(instanceObj, nodeLookup, connectivityLabelMap, axisIndex, planeValue, tol, allowedLabels=None):
        faceMap = {}
        for element in instanceObj.elements:
                for face in _pbc_get_3d_faces(element):
                        labels = []
                        missingLabel = False
                        for connectivityLabel in face:
                                if connectivityLabel not in connectivityLabelMap.keys():
                                        missingLabel = True
                                        break
                                labels.append(connectivityLabelMap[connectivityLabel])
                        if missingLabel == True:
                                continue
                        labels = tuple(labels)
                        if allowedLabels is not None:
                                labelsAllowed = True
                                for label in labels:
                                        if label not in allowedLabels:
                                                labelsAllowed = False
                                                break
                                if labelsAllowed == False:
                                        continue
                        coords = [nodeLookup[label].coordinates for label in labels]
                        isOnPlane = True
                        for coord in coords:
                                if abs(coord[axisIndex] - planeValue) > tol:
                                        isOnPlane = False
                                        break
                        if isOnPlane == True:
                                key = tuple(sorted(labels))
                                faceMap[key] = labels
        triangleData = []
        for face in faceMap.values():
                if len(face) == 3:
                        triangles = (face,)
                else:
                        triangles = ((face[0], face[1], face[2]), (face[0], face[2], face[3]))
                for tri in triangles:
                        points = []
                        for label in tri:
                                points.append(_pbc_reduced_coordinates(nodeLookup[label].coordinates, axisIndex, 3))
                        triangleData.append((tri, points))
        return triangleData

def _pbc_barycentric_coordinates(point, triPoints):
        a = triPoints[0]
        b = triPoints[1]
        c = triPoints[2]
        v0 = b - a
        v1 = c - a
        v2 = point - a
        detT = v0[0] * v1[1] - v0[1] * v1[0]
        if abs(detT) <= 1.0e-14:
                return None
        invDet = 1.0 / detT
        w1 = (v2[0] * v1[1] - v2[1] * v1[0]) * invDet
        w2 = (v0[0] * v2[1] - v0[1] * v2[0]) * invDet
        w0 = 1.0 - w1 - w2
        return [w0, w1, w2]

def _pbc_inverse_distance_weights(point, candidateLabels, nodeLookup, axisIndex, dimension):
        distances = []
        for label in candidateLabels:
                reducedPoint = _pbc_reduced_coordinates(nodeLookup[label].coordinates, axisIndex, dimension)
                dist = np.linalg.norm(point - reducedPoint)
                distances.append((dist, label))
        distances.sort(key=lambda item: item[0])
        if not distances:
                return [], []
        if distances[0][0] <= 1.0e-12:
                return [distances[0][1]], [1.0]
        count = min(3, len(distances))
        selected = distances[:count]
        weights = []
        for dist, label in selected:
                weights.append(1.0 / max(dist, 1.0e-12))
        totalWeight = sum(weights)
        normWeights = [weight / totalWeight for weight in weights]
        return [label for dist, label in selected], normWeights

def _pbc_filter_allowed_labels(labels, allowedLabels):
        if allowedLabels is None:
                return labels
        allowedSet = set(allowedLabels)
        filteredLabels = []
        for label in labels:
                if label in allowedSet:
                        filteredLabels.append(label)
        return filteredLabels

def _pbc_find_nearest_reduced_node(point, candidateLabels, nodeLookup, axisIndex, dimension):
        bestLabel = None
        bestDistance = 1.0e+60
        for label in candidateLabels:
                reducedPoint = _pbc_reduced_coordinates(nodeLookup[label].coordinates, axisIndex, dimension)
                distance = np.linalg.norm(point - reducedPoint)
                if distance < bestDistance:
                        bestDistance = distance
                        bestLabel = label
        if bestLabel is None:
                return [], [], bestDistance
        return [bestLabel], [1.0], bestDistance


def _pbc_find_triangle_interpolation(point, triangles, fallbackLabels, nodeLookup, axisIndex, tol):
        bestLabels = []
        bestWeights = []
        bestScore = -1.0e+60
        for labels, triPoints in triangles:
                weights = _pbc_barycentric_coordinates(point, triPoints)
                if weights is None:
                        continue
                score = min(weights)
                if score > bestScore:
                        clipped = [max(weight, 0.0) for weight in weights]
                        totalClip = sum(clipped)
                        if totalClip > 1.0e-14:
                                bestLabels = list(labels)
                                bestWeights = [weight / totalClip for weight in clipped]
                                bestScore = score
                if score >= -tol:
                        return list(labels), weights
        if bestLabels:
                return bestLabels, bestWeights
        return _pbc_inverse_distance_weights(point, fallbackLabels, nodeLookup, axisIndex, 3)



def _pbc_create_equation(modelObj, equationName, slaveLabel, masterLabels, weights, component, macroTerms):
        terms = [(1.0, _pbc_single_node_set_name(slaveLabel), component)]
        for label, weight in zip(masterLabels, weights):
                terms.append((-float(weight), _pbc_single_node_set_name(label), component))
        for coeff, setName, dof in macroTerms:
                terms.append((float(coeff), setName, dof))
        modelObj.Equation(name=equationName, terms=tuple(terms))





def _elastic_node_ref(instanceName, label):
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
        modelObj = mdb.models[modelName]
        for cName in list(modelObj.constraints.keys()):
                del modelObj.constraints[cName]
        kb = modelObj.keywordBlock
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

def _append_elastic_pbc_2d(eqs, instanceName, tops, bots, fronts, backs):
        n = lambda label: _elastic_node_ref(instanceName, label)
        for i, k in zip(tops, bots):
                eqs.append([(1.0, n(i), 1), (-1.0, n(k), 1)])
        for i, k in zip(tops, bots):
                eqs.append([(1.0, n(i), 2), (-1.0, n(k), 2), (-1.0, 'RP5', 2)])
        for i, k in zip(fronts, backs):
                eqs.append([(1.0, n(i), 1), (-1.0, n(k), 1), (-1.0, 'RP4', 1)])
        for i, k in zip(fronts, backs):
                eqs.append([(1.0, n(i), 2), (-1.0, n(k), 2)])
        eqs.append([(1.0, 'c6', 1), (-1.0, 'c2', 1)])
        eqs.append([(1.0, 'c2', 1), (-1.0, 'c1', 1), (1.0, 'RP4', 1)])
        eqs.append([(1.0, 'c1', 1), (-1.0, 'c5', 1)])
        eqs.append([(1.0, 'c6', 2), (-1.0, 'c2', 2), (1.0, 'RP5', 2)])
        eqs.append([(1.0, 'c2', 2), (-1.0, 'c1', 2)])
        eqs.append([(1.0, 'c1', 2), (-1.0, 'c5', 2), (-1.0, 'RP5', 2)])

def _append_shear_pbc_2d(eqs, instanceName, tops, bots, fronts, backs):
        n = lambda label: _elastic_node_ref(instanceName, label)
        for i, k in zip(tops, bots):
                eqs.append([(1.0, n(i), 1), (-1.0, n(k), 1), (-1.0, 'RP4', 1)])
        for i, k in zip(tops, bots):
                eqs.append([(1.0, n(i), 2), (-1.0, n(k), 2), (-1.0, 'RP1', 2)])
        for i, k in zip(fronts, backs):
                eqs.append([(1.0, n(i), 1), (-1.0, n(k), 1), (-1.0, 'RP3', 1)])
        for i, k in zip(fronts, backs):
                eqs.append([(1.0, n(i), 2), (-1.0, n(k), 2), (-1.0, 'RP4', 2)])
        eqs.append([(1.0, 'c6', 1), (-1.0, 'c2', 1), (1.0, 'RP4', 1)])
        eqs.append([(1.0, 'c2', 1), (-1.0, 'c1', 1), (1.0, 'RP3', 1)])
        eqs.append([(1.0, 'c1', 1), (-1.0, 'c5', 1), (-1.0, 'RP4', 1)])
        eqs.append([(1.0, 'c6', 2), (-1.0, 'c2', 2), (1.0, 'RP1', 2)])
        eqs.append([(1.0, 'c2', 2), (-1.0, 'c1', 2), (1.0, 'RP4', 2)])
        eqs.append([(1.0, 'c1', 2), (-1.0, 'c5', 2), (-1.0, 'RP1', 2)])

def _append_elastic_pbc_3d(eqs, instanceName, tops, bots, lefts, rights, fronts, backs,
        ftedge, btedge, bbedge, fbedge, fledge, bledge, bredge, fredge,
        ltedge, lbedge, rbedge, rtedge):
        n = lambda label: _elastic_node_ref(instanceName, label)
        for i, k in zip(tops, bots):
                eqs.append([(1.0, n(i), 1), (-1.0, n(k), 1)])
                eqs.append([(1.0, n(i), 2), (-1.0, n(k), 2), (-1.0, 'RP5', 2)])
                eqs.append([(1.0, n(i), 3), (-1.0, n(k), 3)])
        for i, k in zip(lefts, rights):
                eqs.append([(1.0, n(i), 1), (-1.0, n(k), 1)])
                eqs.append([(1.0, n(i), 2), (-1.0, n(k), 2)])
                eqs.append([(1.0, n(i), 3), (-1.0, n(k), 3), (-1.0, 'RP6', 3)])
        for i, k in zip(fronts, backs):
                eqs.append([(1.0, n(i), 1), (-1.0, n(k), 1), (-1.0, 'RP4', 1)])
                eqs.append([(1.0, n(i), 2), (-1.0, n(k), 2)])
                eqs.append([(1.0, n(i), 3), (-1.0, n(k), 3)])

        eqs.append([(1.0, 'c6', 1), (-1.0, 'c2', 1)])
        eqs.append([(1.0, 'c2', 1), (-1.0, 'c3', 1)])
        eqs.append([(1.0, 'c3', 1), (-1.0, 'c4', 1), (1.0, 'RP4', 1)])
        eqs.append([(1.0, 'c4', 1), (-1.0, 'c8', 1)])
        eqs.append([(1.0, 'c8', 1), (-1.0, 'c5', 1)])
        eqs.append([(1.0, 'c5', 1), (-1.0, 'c1', 1)])
        eqs.append([(1.0, 'c1', 1), (-1.0, 'c7', 1), (-1.0, 'RP4', 1)])
        eqs.append([(1.0, 'c6', 2), (-1.0, 'c2', 2), (1.0, 'RP5', 2)])
        eqs.append([(1.0, 'c2', 2), (-1.0, 'c3', 2)])
        eqs.append([(1.0, 'c3', 2), (-1.0, 'c4', 2)])
        eqs.append([(1.0, 'c4', 2), (-1.0, 'c8', 2), (-1.0, 'RP5', 2)])
        eqs.append([(1.0, 'c8', 2), (-1.0, 'c5', 2)])
        eqs.append([(1.0, 'c5', 2), (-1.0, 'c1', 2), (1.0, 'RP5', 2)])
        eqs.append([(1.0, 'c1', 2), (-1.0, 'c7', 2), (-1.0, 'RP5', 2)])
        eqs.append([(1.0, 'c6', 3), (-1.0, 'c2', 3)])
        eqs.append([(1.0, 'c2', 3), (-1.0, 'c3', 3), (-1.0, 'RP6', 3)])
        eqs.append([(1.0, 'c3', 3), (-1.0, 'c4', 3)])
        eqs.append([(1.0, 'c4', 3), (-1.0, 'c8', 3)])
        eqs.append([(1.0, 'c8', 3), (-1.0, 'c5', 3), (1.0, 'RP6', 3)])
        eqs.append([(1.0, 'c5', 3), (-1.0, 'c1', 3)])
        eqs.append([(1.0, 'c1', 3), (-1.0, 'c7', 3), (-1.0, 'RP6', 3)])

        for i, k, j, l in zip(ftedge, btedge, bbedge, fbedge):
                eqs.append([(1.0, n(i), 1), (-1.0, n(k), 1), (-1.0, 'RP4', 1)])
                eqs.append([(1.0, n(k), 1), (-1.0, n(j), 1)])
                eqs.append([(1.0, n(j), 1), (-1.0, n(l), 1), (1.0, 'RP4', 1)])
                eqs.append([(1.0, n(i), 2), (-1.0, n(k), 2)])
                eqs.append([(1.0, n(k), 2), (-1.0, n(j), 2), (-1.0, 'RP5', 2)])
                eqs.append([(1.0, n(j), 2), (-1.0, n(l), 2)])
                eqs.append([(1.0, n(i), 3), (-1.0, n(k), 3)])
                eqs.append([(1.0, n(k), 3), (-1.0, n(j), 3)])
                eqs.append([(1.0, n(j), 3), (-1.0, n(l), 3)])
        for i, k, j, l in zip(fledge, bledge, bredge, fredge):
                eqs.append([(1.0, n(i), 1), (-1.0, n(k), 1), (-1.0, 'RP4', 1)])
                eqs.append([(1.0, n(k), 1), (-1.0, n(j), 1)])
                eqs.append([(1.0, n(j), 1), (-1.0, n(l), 1), (1.0, 'RP4', 1)])
                eqs.append([(1.0, n(i), 2), (-1.0, n(k), 2)])
                eqs.append([(1.0, n(k), 2), (-1.0, n(j), 2)])
                eqs.append([(1.0, n(j), 2), (-1.0, n(l), 2)])
                eqs.append([(1.0, n(i), 3), (-1.0, n(k), 3)])
                eqs.append([(1.0, n(k), 3), (-1.0, n(j), 3), (-1.0, 'RP6', 3)])
                eqs.append([(1.0, n(j), 3), (-1.0, n(l), 3)])
        for i, k, j, l in zip(ltedge, lbedge, rbedge, rtedge):
                eqs.append([(1.0, n(i), 1), (-1.0, n(k), 1)])
                eqs.append([(1.0, n(k), 1), (-1.0, n(j), 1)])
                eqs.append([(1.0, n(j), 1), (-1.0, n(l), 1)])
                eqs.append([(1.0, n(i), 2), (-1.0, n(k), 2), (-1.0, 'RP5', 2)])
                eqs.append([(1.0, n(k), 2), (-1.0, n(j), 2)])
                eqs.append([(1.0, n(j), 2), (-1.0, n(l), 2), (1.0, 'RP5', 2)])
                eqs.append([(1.0, n(i), 3), (-1.0, n(k), 3)])
                eqs.append([(1.0, n(k), 3), (-1.0, n(j), 3), (-1.0, 'RP6', 3)])
                eqs.append([(1.0, n(j), 3), (-1.0, n(l), 3)])

def _append_shear_pbc_3d(eqs, instanceName, tops, bots, lefts, rights, fronts, backs,
        ftedge, btedge, bbedge, fbedge, fledge, bledge, bredge, fredge,
        ltedge, lbedge, rbedge, rtedge):
        n = lambda label: _elastic_node_ref(instanceName, label)
        for i, k in zip(tops, bots):
                eqs.append([(1.0, n(i), 1), (-1.0, n(k), 1), (-1.0, 'RP4', 1)])
                eqs.append([(1.0, n(i), 2), (-1.0, n(k), 2), (-1.0, 'RP1', 2)])
                eqs.append([(1.0, n(i), 3), (-1.0, n(k), 3), (-1.0, 'RP6', 3)])
        for i, k in zip(lefts, rights):
                eqs.append([(1.0, n(i), 1), (-1.0, n(k), 1), (-1.0, 'RP5', 1)])
                eqs.append([(1.0, n(i), 2), (-1.0, n(k), 2), (-1.0, 'RP6', 2)])
                eqs.append([(1.0, n(i), 3), (-1.0, n(k), 3), (-1.0, 'RP2', 3)])
        for i, k in zip(fronts, backs):
                eqs.append([(1.0, n(i), 1), (-1.0, n(k), 1), (-1.0, 'RP3', 1)])
                eqs.append([(1.0, n(i), 2), (-1.0, n(k), 2), (-1.0, 'RP4', 2)])
                eqs.append([(1.0, n(i), 3), (-1.0, n(k), 3), (-1.0, 'RP5', 3)])

        eqs.append([(1.0, 'c6', 1), (-1.0, 'c2', 1), (1.0, 'RP4', 1)])
        eqs.append([(1.0, 'c2', 1), (-1.0, 'c3', 1), (-1.0, 'RP5', 1)])
        eqs.append([(1.0, 'c3', 1), (-1.0, 'c4', 1), (1.0, 'RP3', 1)])
        eqs.append([(1.0, 'c4', 1), (-1.0, 'c8', 1), (-1.0, 'RP4', 1)])
        eqs.append([(1.0, 'c8', 1), (-1.0, 'c5', 1), (1.0, 'RP5', 1)])
        eqs.append([(1.0, 'c5', 1), (-1.0, 'c1', 1), (1.0, 'RP4', 1)])
        eqs.append([(1.0, 'c1', 1), (-1.0, 'c7', 1), (-1.0, 'RP3', 1), (-1.0, 'RP4', 1), (-1.0, 'RP5', 1)])
        eqs.append([(1.0, 'c6', 2), (-1.0, 'c2', 2), (1.0, 'RP1', 2)])
        eqs.append([(1.0, 'c2', 2), (-1.0, 'c3', 2), (-1.0, 'RP6', 2)])
        eqs.append([(1.0, 'c3', 2), (-1.0, 'c4', 2), (1.0, 'RP4', 2)])
        eqs.append([(1.0, 'c4', 2), (-1.0, 'c8', 2), (-1.0, 'RP1', 2)])
        eqs.append([(1.0, 'c8', 2), (-1.0, 'c5', 2), (1.0, 'RP6', 2)])
        eqs.append([(1.0, 'c5', 2), (-1.0, 'c1', 2), (1.0, 'RP1', 2)])
        eqs.append([(1.0, 'c1', 2), (-1.0, 'c7', 2), (-1.0, 'RP1', 2), (-1.0, 'RP4', 2), (-1.0, 'RP6', 2)])
        eqs.append([(1.0, 'c6', 3), (-1.0, 'c2', 3), (1.0, 'RP6', 3)])
        eqs.append([(1.0, 'c2', 3), (-1.0, 'c3', 3), (-1.0, 'RP2', 3)])
        eqs.append([(1.0, 'c3', 3), (-1.0, 'c4', 3), (1.0, 'RP5', 3)])
        eqs.append([(1.0, 'c4', 3), (-1.0, 'c8', 3), (-1.0, 'RP6', 3)])
        eqs.append([(1.0, 'c8', 3), (-1.0, 'c5', 3), (1.0, 'RP2', 3)])
        eqs.append([(1.0, 'c5', 3), (-1.0, 'c1', 3), (1.0, 'RP6', 3)])
        eqs.append([(1.0, 'c1', 3), (-1.0, 'c7', 3), (-1.0, 'RP2', 3), (-1.0, 'RP5', 3), (-1.0, 'RP6', 3)])

        for i, k, j, l in zip(ftedge, btedge, bbedge, fbedge):
                eqs.append([(1.0, n(i), 1), (-1.0, n(k), 1), (-1.0, 'RP3', 1)])
                eqs.append([(1.0, n(k), 1), (-1.0, n(j), 1), (-1.0, 'RP4', 1)])
                eqs.append([(1.0, n(j), 1), (-1.0, n(l), 1), (1.0, 'RP3', 1)])
                eqs.append([(1.0, n(i), 2), (-1.0, n(k), 2), (-1.0, 'RP4', 2)])
                eqs.append([(1.0, n(k), 2), (-1.0, n(j), 2), (-1.0, 'RP1', 2)])
                eqs.append([(1.0, n(j), 2), (-1.0, n(l), 2), (1.0, 'RP4', 2)])
                eqs.append([(1.0, n(i), 3), (-1.0, n(k), 3), (-1.0, 'RP5', 3)])
                eqs.append([(1.0, n(k), 3), (-1.0, n(j), 3), (-1.0, 'RP6', 3)])
                eqs.append([(1.0, n(j), 3), (-1.0, n(l), 3), (1.0, 'RP5', 3)])
        for i, k, j, l in zip(fledge, bledge, bredge, fredge):
                eqs.append([(1.0, n(i), 1), (-1.0, n(k), 1), (-1.0, 'RP3', 1)])
                eqs.append([(1.0, n(k), 1), (-1.0, n(j), 1), (-1.0, 'RP5', 1)])
                eqs.append([(1.0, n(j), 1), (-1.0, n(l), 1), (1.0, 'RP3', 1)])
                eqs.append([(1.0, n(i), 2), (-1.0, n(k), 2), (-1.0, 'RP4', 2)])
                eqs.append([(1.0, n(k), 2), (-1.0, n(j), 2), (-1.0, 'RP6', 2)])
                eqs.append([(1.0, n(j), 2), (-1.0, n(l), 2), (1.0, 'RP4', 2)])
                eqs.append([(1.0, n(i), 3), (-1.0, n(k), 3), (-1.0, 'RP5', 3)])
                eqs.append([(1.0, n(k), 3), (-1.0, n(j), 3), (-1.0, 'RP2', 3)])
                eqs.append([(1.0, n(j), 3), (-1.0, n(l), 3), (1.0, 'RP5', 3)])
        for i, k, j, l in zip(ltedge, lbedge, rbedge, rtedge):
                eqs.append([(1.0, n(i), 1), (-1.0, n(k), 1), (-1.0, 'RP4', 1)])
                eqs.append([(1.0, n(k), 1), (-1.0, n(j), 1), (-1.0, 'RP5', 1)])
                eqs.append([(1.0, n(j), 1), (-1.0, n(l), 1), (1.0, 'RP4', 1)])
                eqs.append([(1.0, n(i), 2), (-1.0, n(k), 2), (-1.0, 'RP1', 2)])
                eqs.append([(1.0, n(k), 2), (-1.0, n(j), 2), (-1.0, 'RP6', 2)])
                eqs.append([(1.0, n(j), 2), (-1.0, n(l), 2), (1.0, 'RP1', 2)])
                eqs.append([(1.0, n(i), 3), (-1.0, n(k), 3), (-1.0, 'RP6', 3)])
                eqs.append([(1.0, n(k), 3), (-1.0, n(j), 3), (-1.0, 'RP2', 3)])
                eqs.append([(1.0, n(j), 3), (-1.0, n(l), 3), (1.0, 'RP6', 3)])

def _unique_model_copy_name(baseModelName, suffix):
        root = '%s_%s' % (baseModelName, suffix)
        name = root
        idx = 1
        while name in mdb.models.keys():
                idx += 1
                name = '%s_%s' % (root, idx)
        return name

def _clear_elastic_analysis_features(modelObj, clearPredefined=False):
        for stepName in list(modelObj.steps.keys()):
                if stepName != 'Initial':
                        del modelObj.steps[stepName]
        for loadName in list(modelObj.loads.keys()):
                del modelObj.loads[loadName]
        for bcName in list(modelObj.boundaryConditions.keys()):
                del modelObj.boundaryConditions[bcName]
        for constraintName in list(modelObj.constraints.keys()):
                del modelObj.constraints[constraintName]
        for requestName in list(modelObj.historyOutputRequests.keys()):
                if requestName != 'H-Output-1':
                        del modelObj.historyOutputRequests[requestName]
        if clearPredefined:
                for fieldName in list(modelObj.predefinedFields.keys()):
                        del modelObj.predefinedFields[fieldName]

def _copy_model_for_keyword_job(baseModelName, suffix, clearPredefined=False):
        modelCopyName = _unique_model_copy_name(baseModelName, suffix)
        mdb.Model(name=modelCopyName, objectToCopy=mdb.models[baseModelName])
        modelObj = mdb.models[modelCopyName]
        _clear_elastic_analysis_features(modelObj, clearPredefined=clearPredefined)
        return modelCopyName, modelObj, modelObj.rootAssembly

_JOB_TEMP_SUFFIX = ''   # set by feasypbc from (intemp, fntemp); makes every ODB name unique per temperature

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

def _delete_model_copy(model_copy_name):
    """Delete a temporary model copy (and the job objects that point at it) once its results are read."""
    try:
        for job_name in list(mdb.jobs.keys()):
            try:
                if str(getattr(mdb.jobs[job_name], 'model', '')) == model_copy_name:
                    del mdb.jobs[job_name]
            except Exception:
                pass
        if model_copy_name in mdb.models.keys():
            del mdb.models[model_copy_name]
    except Exception as cleanup_error:
        print('Warning: could not delete temporary model %s: %s' % (model_copy_name, cleanup_error))

def _job_name(baseModelName, suffix):
        return '%s-job-%s%s' % (baseModelName, suffix, _JOB_TEMP_SUFFIX)

def _submit_keyword_job(jobName, modelName, CPUs, umatName, path):
        if jobName in mdb.jobs.keys():
                del mdb.jobs[jobName]
        mdb.Job(name=jobName, model=modelName, description='', type=ANALYSIS,
                atTime=None, waitMinutes=0, waitHours=0, queue=None, memory=90,
                memoryUnits=PERCENTAGE, getMemoryFromAnalysis=True,
                explicitPrecision=SINGLE, nodalOutputPrecision=SINGLE, echoPrint=OFF,
                modelPrint=OFF, contactPrint=OFF, historyPrint=OFF, userSubroutine=umatName,
                scratch='', multiprocessingMode=DEFAULT, numCpus=CPUs, numDomains=CPUs, numGPUs=1)
        mdb.jobs[jobName].submit(consistencyChecking=OFF)
        mdb.jobs[jobName].waitForCompletion()
        odbPath = '%s\\%s.odb' % (path, jobName)
        o3 = session.openOdb(name=odbPath)
        odb = session.odbs[odbPath]
        session.viewports['Viewport: 1'].setValues(displayedObject=o3)
        odbName = session.viewports[session.currentViewportName].odbDisplay.name
        return odb, odbName

def _clear_xydata():
        for key in list(session.xyDataObjects.keys()):
                del session.xyDataObjects[key]

def _set_odb_frame(odb, odbName, stepName):
        frameIndex = len(odb.steps[stepName].frames) - 1
        if frameIndex < 0:
                frameIndex = 0
        session.odbData[odbName].setValues(activeFrames=((stepName, (frameIndex, )), ))

def _sum_rf_from_step(odb, odbName, stepName, component, nodeSetName):
        _clear_xydata()
        _set_odb_frame(odb, odbName, stepName)
        session.xyDataListFromField(odb=odb, outputPosition=NODAL,
                variable=(('RF', NODAL, ((COMPONENT, 'RF%d' % component), )), ),
                nodeSets=(nodeSetName, ))
        total = 0
        for key in session.xyDataObjects.keys():
                total = total + session.xyDataObjects[key][0][1]
        return total

def _u_value_from_step(odb, odbName, stepName, component, nodeSets, upperName, label):
        _clear_xydata()
        _set_odb_frame(odb, odbName, stepName)
        session.xyDataListFromField(odb=odb, outputPosition=NODAL,
                variable=(('U', NODAL, ((COMPONENT, 'U%d' % component), )), ),
                nodeSets=nodeSets)
        key = 'U:U%d PI: %s N: %s' % (component, upperName, label)
        return session.xyDataObjects[key][0][1]

def _add_history_output(modelObj, stepName):
        regionDef = modelObj.rootAssembly.sets['c1']
        modelObj.HistoryOutputRequest(name='H-Output-%s' % stepName,
                createStepName=stepName, variables=('RT', ), region=regionDef,
                sectionPoints=DEFAULT, rebar=EXCLUDE)

def _create_bc(modelObj, a, name, stepName, setName, u1=UNSET, u2=UNSET, u3=UNSET):
        modelObj.DisplacementBC(name=name, createStepName=stepName, region=a.sets[setName],
                u1=u1, u2=u2, u3=u3, ur1=UNSET, ur2=UNSET, ur3=UNSET,
                amplitude=UNSET, fixed=OFF, distributionType=UNIFORM, fieldName='',
                localCsys=None)
        return name

def _deactivate_previous_bcs(modelObj, previousBcNames, stepName):
        for bcName in previousBcNames:
                modelObj.boundaryConditions[bcName].deactivate(stepName)

def _create_elastic_steps_and_bcs_2d(modelObj, a, cases, Dispx, Dispy):
        previous = 'Initial'
        previousBcs = []
        for caseName in cases:
                modelObj.StaticStep(name=caseName, previous=previous)
                _deactivate_previous_bcs(modelObj, previousBcs, caseName)
                if caseName == 'E11':
                        previousBcs = [_create_bc(modelObj, a, 'E11-1', caseName, 'RP4', u1=Dispx)]
                elif caseName == 'E22':
                        previousBcs = [_create_bc(modelObj, a, 'E22-1', caseName, 'RP5', u2=Dispy)]
                _add_history_output(modelObj, caseName)
                previous = caseName

def _create_shear_steps_and_bcs_2d(modelObj, a, cases, Dispx, Dispy):
        previous = 'Initial'
        previousBcs = []
        for caseName in cases:
                modelObj.StaticStep(name=caseName, previous=previous)
                _deactivate_previous_bcs(modelObj, previousBcs, caseName)
                previousBcs = [_create_bc(modelObj, a, 'G12-1', caseName, 'RP4', u1=Dispx, u2=Dispy)]
                _add_history_output(modelObj, caseName)
                previous = caseName

def _create_elastic_steps_and_bcs_3d(modelObj, a, cases, Dispx, Dispy, Dispz):
        previous = 'Initial'
        previousBcs = []
        for caseName in cases:
                modelObj.StaticStep(name=caseName, previous=previous)
                _deactivate_previous_bcs(modelObj, previousBcs, caseName)
                if caseName == 'E11':
                        previousBcs = [_create_bc(modelObj, a, 'E11-1', caseName, 'RP4', u1=Dispx)]
                elif caseName == 'E22':
                        previousBcs = [_create_bc(modelObj, a, 'E22-1', caseName, 'RP5', u2=Dispy)]
                elif caseName == 'E33':
                        previousBcs = [_create_bc(modelObj, a, 'E33-1', caseName, 'RP6', u3=Dispz)]
                _add_history_output(modelObj, caseName)
                previous = caseName

def _create_shear_steps_and_bcs_3d(modelObj, a, cases, Dispx, Dispy, Dispz):
        previous = 'Initial'
        previousBcs = []
        for caseName in cases:
                modelObj.StaticStep(name=caseName, previous=previous)
                _deactivate_previous_bcs(modelObj, previousBcs, caseName)
                if caseName == 'G12':
                        previousBcs = [
                                _create_bc(modelObj, a, 'G12-1', caseName, 'RP4', u1=Dispx, u2=Dispy),
                                _create_bc(modelObj, a, 'G12-2', caseName, 'RP5', u1=0, u2=0, u3=0),
                                _create_bc(modelObj, a, 'G12-3', caseName, 'RP6', u1=0, u2=0, u3=0)]
                elif caseName == 'G13':
                        previousBcs = [
                                _create_bc(modelObj, a, 'G13-1', caseName, 'RP5', u1=Dispx, u3=Dispz),
                                _create_bc(modelObj, a, 'G13-2', caseName, 'RP4', u1=0, u2=0, u3=0),
                                _create_bc(modelObj, a, 'G13-3', caseName, 'RP6', u1=0, u2=0, u3=0)]
                elif caseName == 'G23':
                        previousBcs = [
                                _create_bc(modelObj, a, 'G23-1', caseName, 'RP6', u2=Dispy, u3=Dispz),
                                _create_bc(modelObj, a, 'G23-2', caseName, 'RP4', u1=0, u2=0, u3=0),
                                _create_bc(modelObj, a, 'G23-3', caseName, 'RP5', u1=0, u2=0, u3=0)]
                _add_history_output(modelObj, caseName)
                previous = caseName

def _postprocess_2d_elastic(odb, odbName, stepName, caseName, upperName, c1, c2, c5,
        coc1, coc2, coc5, L, H, Thikness, Dispx, Dispy):
        if caseName == 'E11':
                force = _sum_rf_from_step(odb, odbName, stepName, 1, 'RP4')
                value = abs(force / (H * Thikness)) / (Dispx / L)
                C1U1new = _u_value_from_step(odb, odbName, stepName, 1, ('C1', 'C2', ), upperName, c1[0]) + coc1[c1[0]][0]
                C2U1new = _u_value_from_step(odb, odbName, stepName, 1, ('C1', 'C2', ), upperName, c2[0]) + coc2[c2[0]][0]
                E11U1 = abs(L - abs(C1U1new - C2U1new))
                C1U2new = _u_value_from_step(odb, odbName, stepName, 2, ('C1', 'C5', ), upperName, c1[0]) + coc1[c1[0]][1]
                C5U2new = _u_value_from_step(odb, odbName, stepName, 2, ('C1', 'C5', ), upperName, c5[0]) + coc5[c5[0]][1]
                E11U2 = abs(H - abs(C1U2new - C5U2new))
                return value, (E11U2 / H) / (E11U1 / L)
        force = _sum_rf_from_step(odb, odbName, stepName, 2, 'RP5')
        value = abs(force / (L * Thikness)) / (Dispy / H)
        C1U1new = _u_value_from_step(odb, odbName, stepName, 1, ('C1', 'C2', ), upperName, c1[0]) + coc1[c1[0]][0]
        C2U1new = _u_value_from_step(odb, odbName, stepName, 1, ('C1', 'C2', ), upperName, c2[0]) + coc2[c2[0]][0]
        E22U1 = abs(L - abs(C1U1new - C2U1new))
        C1U2new = _u_value_from_step(odb, odbName, stepName, 2, ('C1', 'C5', ), upperName, c1[0]) + coc1[c1[0]][1]
        C5U2new = _u_value_from_step(odb, odbName, stepName, 2, ('C1', 'C5', ), upperName, c5[0]) + coc5[c5[0]][1]
        E22U2 = abs(H - abs(C1U2new - C5U2new))
        return value, (E22U1 / L) / (E22U2 / H)

def _postprocess_3d_elastic(odb, odbName, stepName, caseName, upperName, c1, c2, c4, c5,
        coc1, coc2, coc4, coc5, L, H, W, Dispx, Dispy, Dispz):
        if caseName == 'E11':
                force = _sum_rf_from_step(odb, odbName, stepName, 1, 'RP4')
                value = abs(force / (H * W)) / (Dispx / L)
        elif caseName == 'E22':
                force = _sum_rf_from_step(odb, odbName, stepName, 2, 'RP5')
                value = abs(force / (W * L)) / (Dispy / H)
        else:
                force = _sum_rf_from_step(odb, odbName, stepName, 3, 'RP6')
                value = abs(force / (H * L)) / (Dispz / W)

        C1U1new = _u_value_from_step(odb, odbName, stepName, 1, ('C1', 'C2', ), upperName, c1[0]) + coc1[c1[0]][0]
        C2U1new = _u_value_from_step(odb, odbName, stepName, 1, ('C1', 'C2', ), upperName, c2[0]) + coc2[c2[0]][0]
        du1 = abs(L - abs(C1U1new - C2U1new))
        C1U2new = _u_value_from_step(odb, odbName, stepName, 2, ('C1', 'C5', ), upperName, c1[0]) + coc1[c1[0]][1]
        C5U2new = _u_value_from_step(odb, odbName, stepName, 2, ('C1', 'C5', ), upperName, c5[0]) + coc5[c5[0]][1]
        du2 = abs(H - abs(C1U2new - C5U2new))
        C1U3new = _u_value_from_step(odb, odbName, stepName, 3, ('C1', 'C4', ), upperName, c1[0]) + coc1[c1[0]][2]
        C4U3new = _u_value_from_step(odb, odbName, stepName, 3, ('C1', 'C4', ), upperName, c4[0]) + coc4[c4[0]][2]
        du3 = abs(W - abs(C1U3new - C4U3new))

        if caseName == 'E11':
                return value, (du2 / H) / (du1 / L), (du3 / W) / (du1 / L)
        if caseName == 'E22':
                return value, (du1 / L) / (du2 / H), (du3 / W) / (du2 / H)
        return value, (du1 / L) / (du3 / W), (du2 / H) / (du3 / W)

def _run_cte_keyword_job(baseModelName, modelName, instanceName, upperName, path, CPUs, umatName,
        c1, c2, c4, c5, coc1, coc2, coc4, coc5, L, H, W, intemp, fntemp, segment, eqs):
        cteModelName, cteModelObj, cteAssembly = _copy_model_for_keyword_job(modelName, 'CTE_KW', clearPredefined=True)
        nodeNo = [int(i.label) for i in cteAssembly.allInstances[instanceName].nodes]
        cteAssembly.SetFromNodeLabels(name='CTE_part', nodeLabels=((instanceName, nodeNo),))
        region = cteAssembly.sets['CTE_part']
        intemp = intemp + 273.15
        fntemp = fntemp + 273.15
        temps = np.linspace(intemp, fntemp, segment + 1)
        for i in range(1, segment + 1):
                cteModelObj.StaticStep(name='Step-%d' % i, previous='Initial' if i == 1 else 'Step-%d' % (i - 1))
        cteModelObj.Temperature(name='Predefined Field-1',
                createStepName='Initial', region=region, distributionType=UNIFORM,
                crossSectionDistribution=CONSTANT_THROUGH_THICKNESS, magnitudes=(intemp, ))
        for i in range(1, segment + 1):
                cteModelObj.predefinedFields['Predefined Field-1'].setValuesInStep(
                        stepName='Step-%d' % i, magnitudes=(temps[i], ))
        _insert_equation_keywords(cteModelName, eqs)
        jobName = _job_name(baseModelName, 'CTE')
        odb, odbName = _submit_keyword_job(jobName, cteModelName, CPUs, umatName, path)

        DistX_prev = L
        DistY_prev = H
        DistZ_prev = W
        temperatures = []
        start_temps = []
        end_temps = []
        CTE_X_list = []
        CTE_Y_list = []
        CTE_Z_list = []
        CTE_X = 0
        CTE_Y = 0
        CTE_Z = 0
        for i in range(segment + 1):
                if i == 0:
                        DistX_i = L
                        DistY_i = H
                        DistZ_i = W
                else:
                        step_name = 'Step-%d' % i
                        _set_odb_frame(odb, odbName, step_name)
                        session.xyDataListFromField(odb=odb, outputPosition=NODAL,
                                variable=(('U', NODAL, ((COMPONENT, 'U1'), )), ), nodeSets=('C1', 'C2', ))
                        C1U1_i = session.xyDataObjects['U:U1 PI: %s N: %s' % (upperName, c1[0])][0][1]
                        C2U1_i = session.xyDataObjects['U:U1 PI: %s N: %s' % (upperName, c2[0])][0][1]
                        DistX_i = abs((C1U1_i + coc1[c1[0]][0]) - (C2U1_i + coc2[c2[0]][0]))
                        session.xyDataListFromField(odb=odb, outputPosition=NODAL,
                                variable=(('U', NODAL, ((COMPONENT, 'U2'), )), ), nodeSets=('C1', 'C5', ))
                        C1U2_i = session.xyDataObjects['U:U2 PI: %s N: %s' % (upperName, c1[0])][0][1]
                        C5U2_i = session.xyDataObjects['U:U2 PI: %s N: %s' % (upperName, c5[0])][0][1]
                        DistY_i = abs((C1U2_i + coc1[c1[0]][1]) - (C5U2_i + coc5[c5[0]][1]))
                        session.xyDataListFromField(odb=odb, outputPosition=NODAL,
                                variable=(('U', NODAL, ((COMPONENT, 'U3'), )), ), nodeSets=('C1', 'C4', ))
                        C1U3_i = session.xyDataObjects['U:U3 PI: %s N: %s' % (upperName, c1[0])][0][1]
                        C4U3_i = session.xyDataObjects['U:U3 PI: %s N: %s' % (upperName, c4[0])][0][1]
                        DistZ_i = abs((C1U3_i + coc1[c1[0]][2]) - (C4U3_i + coc4[c4[0]][2]))
                delta_temp = temps[i] - (temps[0] if i == 0 else temps[i - 1])
                CTE_X = (DistX_i - DistX_prev) / (L * delta_temp) if delta_temp != 0 else 0
                CTE_Y = (DistY_i - DistY_prev) / (H * delta_temp) if delta_temp != 0 else 0
                CTE_Z = (DistZ_i - DistZ_prev) / (W * delta_temp) if delta_temp != 0 else 0
                DistX_prev = DistX_i
                DistY_prev = DistY_i
                DistZ_prev = DistZ_i
                temp_avg = (temps[0] if i == 0 else temps[i - 1] + temps[i]) / 2
                start_temp = temps[0] if i == 0 else temps[i - 1]
                end_temp = temps[i]
                temperatures.append(temp_avg)
                start_temps.append(start_temp)
                end_temps.append(end_temp)
                CTE_X_list.append(CTE_X)
                CTE_Y_list.append(CTE_Y)
                CTE_Z_list.append(CTE_Z)
                _clear_xydata()
        csv_filename = f'{baseModelName}_CTE_results.csv'
        with open(csv_filename, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['Start Temperature', 'End Temperature', 'Average Temperature', 'CTE_X', 'CTE_Y', 'CTE_Z'])
                for st, et, t, cte_x, cte_y, cte_z in zip(start_temps, end_temps, temperatures, CTE_X_list, CTE_Y_list, CTE_Z_list):
                        writer.writerow([st, et, t, cte_x, cte_y, cte_z])
        _delete_model_copy(cteModelName)
        return CTE_X, CTE_Y, CTE_Z, odb

def _write_2d_results(part, E11, E22, G12, V12, V21, mass, density, duration):
        filename = ('%s_elastic_properties.txt' % part)
        print('The homogenised elastic properties are saved in ABAQUS Work Directory under %s' % filename)
        f = open(filename, 'w')
        f.write(f'{"Property":^10}{"Value":^20}{"Unit":^20}\n')
        f.write(f'{"E11":^10}{E11:^20}{"Stress units":^20}\n')
        f.write(f'{"V12":^10}{V12:^20}{"ratio":^20}\n')
        f.write(f'{"E22":^10}{E22:^20}{"Stress units":^20}\n')
        f.write(f'{"V21":^10}{V21:^20}{"ratio":^20}\n')
        f.write(f'{"G12":^10}{G12:^20}{"Stress units":^20}\n')
        f.write(f'Total mass={mass} Mass units \n')
        f.write(f'Homogenised density={density} Density units \n')
        f.write(f'processing duration {duration} Seconds\n')
        f.close()
        filename = f'{part}_elastic_properties(easycopy).txt'
        f = open(filename, 'w')
        f.write(f'{E11:^10}\n')
        f.write(f'{E22:^10}\n')
        f.write(f'{G12:^10}\n')
        f.write(f'{V12:^10}\n')
        f.write(f'{V21:^10}\n')
        f.write(f'{mass:^10}\n')
        f.write(f'{density:^10}\n')
        f.write(f'{duration:^10}\n')
        f.close()

def _write_3d_results(part, E11, E22, E33, G12, G13, G23, V12, V13, V21, V23,
        V31, V32, CTE_X, CTE_Y, CTE_Z, mass, density, duration):
        filename = ('%s_elastic_properties.txt' % part)
        print(f'The homogenised elastic properties are saved in ABAQUS Work Directory under {filename}')
        f = open(filename, 'w')
        f.write(f'{"Property":^10}{"Value":^20}{"Unit":^20}\n')
        f.write(f'{"E11":^10}{E11:^20}{"Stress units":^20}\n')
        f.write(f'{"V12":^10}{V12:^20}{"ratio":^20}\n')
        f.write(f'{"V13":^10}{V13:^20}{"ratio":^20}\n')
        f.write(f'{"E22":^10}{E22:^20}{"Stress units":^20}\n')
        f.write(f'{"V21":^10}{V21:^20}{"ratio":^20}\n')
        f.write(f'{"V23":^10}{V23:^20}{"ratio":^20}\n')
        f.write(f'{"E33":^10}{E33:^20}{"Stress units":^20}\n')
        f.write(f'{"V31":^10}{V31:^20}{"ratio":^20}\n')
        f.write(f'{"V32":^10}{V32:^20}{"ratio":^20}\n')
        f.write(f'{"G12":^10}{G12:^20}{"Stress units":^20}\n')
        f.write(f'{"G13":^10}{G13:^20}{"Stress units":^20}\n')
        f.write(f'{"G23":^10}{G23:^20}{"Stress units":^20}\n')
        f.write(f'{"CTE X":^10}{CTE_X:^20}{"N/A":^20}\n')
        f.write(f'{"CTE Y":^10}{CTE_Y:^20}{"N/A":^20}\n')
        f.write(f'{"CTE Z":^10}{CTE_Z:^20}{"N/A":^20}\n')
        f.write(f'Total mass={mass} Mass units \n')
        f.write(f'Homogenised density={density} Density units \n')
        f.write(f'processing duration {duration} Seconds\n')
        f.close()
        filename = f'{part}_elastic_properties(easycopy).txt'
        f = open(filename, 'w')
        f.write(f'{E11:^10}\n')
        f.write(f'{E22:^10}\n')
        f.write(f'{E33:^10}\n')
        f.write(f'{G12:^10}\n')
        f.write(f'{G13:^10}\n')
        f.write(f'{G23:^10}\n')
        f.write(f'{V12:^10}\n')
        f.write(f'{V13:^10}\n')
        f.write(f'{V21:^10}\n')
        f.write(f'{V23:^10}\n')
        f.write(f'{V31:^10}\n')
        f.write(f'{V32:^10}\n')
        f.write(f'{CTE_X:^10}\n')
        f.write(f'{CTE_Y:^10}\n')
        f.write(f'{CTE_Z:^10}\n')
        if mass is None:
                mass = "N/A"
        if density is None:
                density = "N/A"
        f.write(f'{mass:^10}\n')
        f.write(f'{density:^10}\n')
        f.write(f'{duration:^10}\n')
        f.close()

def _run_elastic_cte_keyword_2d(part, modelName, instanceName, upperName, path, CPUs, onlyPBC,
        E11_flag, E22_flag, G12_flag, umatName, start, a, tops, bots, fronts, backs,
        c1, c2, c5, coc1, coc2, coc5, L, H, W, Thikness, Dispx, Dispy, mass):
        setupStart = time.time()
        E11 = 'N/A'
        E22 = 'N/A'
        G12 = 'N/A'
        V12 = 'N/A'
        V21 = 'N/A'
        odb = None
        if onlyPBC:
                eqs = []
                if E11_flag or E22_flag:
                        _append_elastic_pbc_2d(eqs, instanceName, tops, bots, fronts, backs)
                if G12_flag:
                        _append_shear_pbc_2d(eqs, instanceName, tops, bots, fronts, backs)
                _insert_equation_keywords(modelName, eqs)
        else:
                normalCases = []
                if E11_flag:
                        normalCases.append('E11')
                if E22_flag:
                        normalCases.append('E22')
                if normalCases:
                        eqs = []
                        _append_elastic_pbc_2d(eqs, instanceName, tops, bots, fronts, backs)
                        normalModelName, normalModelObj, normalAssembly = _copy_model_for_keyword_job(modelName, 'E2D_KW')
                        _create_elastic_steps_and_bcs_2d(normalModelObj, normalAssembly, normalCases, Dispx, Dispy)
                        _insert_equation_keywords(normalModelName, eqs)
                        odb, odbName = _submit_keyword_job(_job_name(modelName, 'E2D'), normalModelName, CPUs, umatName, path)
                        if E11_flag:
                                E11, V12 = _postprocess_2d_elastic(odb, odbName, 'E11', 'E11', upperName, c1, c2, c5,
                                        coc1, coc2, coc5, L, H, Thikness, Dispx, Dispy)
                        if E22_flag:
                                E22, V21 = _postprocess_2d_elastic(odb, odbName, 'E22', 'E22', upperName, c1, c2, c5,
                                        coc1, coc2, coc5, L, H, Thikness, Dispx, Dispy)
                        odb.close()
                        odb = None
                        _delete_model_copy(normalModelName)
                if G12_flag:
                        eqs = []
                        _append_shear_pbc_2d(eqs, instanceName, tops, bots, fronts, backs)
                        shearModelName, shearModelObj, shearAssembly = _copy_model_for_keyword_job(modelName, 'G2D_KW')
                        _create_shear_steps_and_bcs_2d(shearModelObj, shearAssembly, ['G12'], Dispx, Dispy)
                        _insert_equation_keywords(shearModelName, eqs)
                        odb, odbName = _submit_keyword_job(_job_name(modelName, 'G2D'), shearModelName, CPUs, umatName, path)
                        forceG12 = _sum_rf_from_step(odb, odbName, 'G12', 1, 'RP4')
                        stressG12 = abs(forceG12 / (L * Thikness))
                        G12 = stressG12 / ((Dispx / H) + (Dispy / L))
                        odb.close()
                        odb = None
                        _delete_model_copy(shearModelName)

        density = 0
        if mass != None:
                density = mass / (L * W * H)
        duration = time.time() - start
        print('----------------------------------------------------')
        print('----------------------------------------------------')
        print('The homogenised elastic properties:')
        print('E11=%s Stress units' % (E11))
        print('V12=%s ratio' % (V12))
        print('E22=%s Stress units' % (E22))
        print('V21=%s ratio' % (V21))
        print('G12=%s Stress units' % (G12))
        print('----------------------------------------------------')
        print('Total mass=%s Mass units' % (mass))
        print('Homogenised density=%s Density units' % (density))
        print('----------------------------------------------------')
        print('Processing duration %s seconds' % duration)
        print('----------------------------------------------------')
        _write_2d_results(part, E11, E22, G12, V12, V21, mass, density, duration)
        print('Citation: Omairey S, Dunning P, Sriramula S (2018) Development of an ABAQUS plugin tool for periodic RVE homogenisation.')
        print('Engineering with Computers. https://doi.org/10.1007/s00366-018-0616-4')
        print(('----------------------------------------------------'))
        if onlyPBC == True:
                print(('EasyPBC created Period Boundary Conditions only. For further investigation, used relevant Reference Points to apply loads/displacements based on your needs. Details on the use of Reference Points are illustrated in Table 1 of the referred paper.'))
        _clear_xydata()
        print(('---------------------------------------'))
        print(('--------- End of EasyPBC (2D) ---------'))
        print(('---------------------------------------'))
        a = mdb.models[modelName].rootAssembly
        session.viewports['Viewport: 1'].setValues(displayedObject=a)

def _run_elastic_cte_keyword_3d(part, modelName, instanceName, upperName, path, CPUs, onlyPBC,
        E11_flag, E22_flag, E33_flag, G12_flag, G13_flag, G23_flag, CTE_flag, umatName,
        start, a, tops, bots, lefts, rights, fronts, backs, ftedge, btedge, bbedge, fbedge,
        fledge, bledge, bredge, fredge, ltedge, lbedge, rbedge, rtedge, c1, c2, c4, c5,
        coc1, coc2, coc4, coc5, L, H, W, Dispx, Dispy, Dispz, mass, intemp, fntemp, segment):
        setupStart = time.time()
        E11 = 'N/A'
        E22 = 'N/A'
        E33 = 'N/A'
        G12 = 'N/A'
        G13 = 'N/A'
        G23 = 'N/A'
        V12 = 'N/A'
        V13 = 'N/A'
        V21 = 'N/A'
        V23 = 'N/A'
        V31 = 'N/A'
        V32 = 'N/A'
        CTE_X = 'N/A'
        CTE_Y = 'N/A'
        CTE_Z = 'N/A'
        lastMechanicalEqs = []

        if onlyPBC:
                eqs = []
                if E11_flag or E22_flag or E33_flag:
                        _append_elastic_pbc_3d(eqs, instanceName, tops, bots, lefts, rights, fronts, backs,
                                ftedge, btedge, bbedge, fbedge, fledge, bledge, bredge, fredge,
                                ltedge, lbedge, rbedge, rtedge)
                if G12_flag or G13_flag or G23_flag:
                        _append_shear_pbc_3d(eqs, instanceName, tops, bots, lefts, rights, fronts, backs,
                                ftedge, btedge, bbedge, fbedge, fledge, bledge, bredge, fredge,
                                ltedge, lbedge, rbedge, rtedge)
                _insert_equation_keywords(modelName, eqs)
        else:
                normalCases = []
                if E11_flag:
                        normalCases.append('E11')
                if E22_flag:
                        normalCases.append('E22')
                if E33_flag:
                        normalCases.append('E33')
                if normalCases:
                        eqs = []
                        _append_elastic_pbc_3d(eqs, instanceName, tops, bots, lefts, rights, fronts, backs,
                                ftedge, btedge, bbedge, fbedge, fledge, bledge, bredge, fredge,
                                ltedge, lbedge, rbedge, rtedge)
                        lastMechanicalEqs = list(eqs)
                        normalModelName, normalModelObj, normalAssembly = _copy_model_for_keyword_job(modelName, 'E3D_KW')
                        _create_elastic_steps_and_bcs_3d(normalModelObj, normalAssembly, normalCases, Dispx, Dispy, Dispz)
                        _insert_equation_keywords(normalModelName, eqs)
                        odb, odbName = _submit_keyword_job(_job_name(modelName, 'E3D'), normalModelName, CPUs, umatName, path)
                        if E11_flag:
                                E11, V12, V13 = _postprocess_3d_elastic(odb, odbName, 'E11', 'E11', upperName,
                                        c1, c2, c4, c5, coc1, coc2, coc4, coc5, L, H, W, Dispx, Dispy, Dispz)
                        if E22_flag:
                                E22, V21, V23 = _postprocess_3d_elastic(odb, odbName, 'E22', 'E22', upperName,
                                        c1, c2, c4, c5, coc1, coc2, coc4, coc5, L, H, W, Dispx, Dispy, Dispz)
                        if E33_flag:
                                E33, V31, V32 = _postprocess_3d_elastic(odb, odbName, 'E33', 'E33', upperName,
                                        c1, c2, c4, c5, coc1, coc2, coc4, coc5, L, H, W, Dispx, Dispy, Dispz)
                        odb.close()
                        _delete_model_copy(normalModelName)
                shearCases = []
                if G12_flag:
                        shearCases.append('G12')
                if G13_flag:
                        shearCases.append('G13')
                if G23_flag:
                        shearCases.append('G23')
                if shearCases:
                        eqs = []
                        _append_shear_pbc_3d(eqs, instanceName, tops, bots, lefts, rights, fronts, backs,
                                ftedge, btedge, bbedge, fbedge, fledge, bledge, bredge, fredge,
                                ltedge, lbedge, rbedge, rtedge)
                        lastMechanicalEqs = list(eqs)
                        shearModelName, shearModelObj, shearAssembly = _copy_model_for_keyword_job(modelName, 'G3D_KW')
                        _create_shear_steps_and_bcs_3d(shearModelObj, shearAssembly, shearCases, Dispx, Dispy, Dispz)
                        _insert_equation_keywords(shearModelName, eqs)
                        odb, odbName = _submit_keyword_job(_job_name(modelName, 'G3D'), shearModelName, CPUs, umatName, path)
                        if G12_flag:
                                forceG12 = _sum_rf_from_step(odb, odbName, 'G12', 1, 'RP4')
                                stressG12 = abs(forceG12 / (L * W))
                                G12 = stressG12 / ((Dispx / H) + (Dispy / L))
                        if G13_flag:
                                forceG13 = _sum_rf_from_step(odb, odbName, 'G13', 1, 'RP5')
                                stressG13 = abs(forceG13 / (H * L))
                                G13 = stressG13 / ((Dispx / W) + (Dispz / L))
                        if G23_flag:
                                forceG23 = _sum_rf_from_step(odb, odbName, 'G23', 2, 'RP6')
                                stressG23 = abs(forceG23 / (L * H))
                                G23 = stressG23 / ((Dispy / W) + (Dispz / H))
                        odb.close()
                        _delete_model_copy(shearModelName)
                if CTE_flag:
                        CTE_X, CTE_Y, CTE_Z, cteOdb = _run_cte_keyword_job(modelName, modelName, instanceName,
                                upperName, path, CPUs, umatName, c1, c2, c4, c5, coc1, coc2, coc4, coc5,
                                L, H, W, float(intemp), float(fntemp), int(segment), lastMechanicalEqs)
                        cteOdb.close()

        density = 0
        if mass != None:
                density = mass / (L * W * H)
        duration = time.time() - start
        print('----------------------------------------------------')
        print('----------------------------------------------------')
        print('The homogenised elastic properties:')
        print('E11=%s Stress units' % (E11))
        print('V12=%s ratio' % (V12))
        print('V13=%s ratio' % (V13))
        print('E22=%s Stress units' % (E22))
        print('V21=%s ratio' % (V21))
        print('V23=%s ratio' % (V23))
        print('E33=%s Stress units' % (E33))
        print('V31=%s ratio' % (V31))
        print('V32=%s ratio' % (V32))
        print('G12=%s Stress units' % (G12))
        print('G13=%s Stress units' % (G13))
        print('G23=%s Stress units' % (G23))
        print('CTE X=%s N/A' % (CTE_X))
        print('CTE Y=%s N/A' % (CTE_Y))
        print('CTE Z=%s N/A' % (CTE_Z))
        print('----------------------------------------------------')
        print('Total mass=%s Mass units' % (mass))
        print('Homogenised density=%s Density units' % (density))
        print('----------------------------------------------------')
        print('Processing duration %s seconds' % duration)
        print('----------------------------------------------------')
        _write_3d_results(part, E11, E22, E33, G12, G13, G23, V12, V13, V21, V23,
                V31, V32, CTE_X, CTE_Y, CTE_Z, mass, density, duration)
        print('Citation: Omairey S, Dunning P, Sriramula S (2018) Development of an ABAQUS plugin tool for periodic RVE homogenisation.')
        print('Engineering with Computers. https://doi.org/10.1007/s00366-018-0616-4')
        print(('----------------------------------------------------'))
        if onlyPBC == True:
                print(('EasyPBC created Period Boundary Conditions only. For further investigation, used relevant Reference Points to apply loads/displacements based on your needs. Details on the use of Reference Points are illustrated in Table 1 of the referred paper.'))
        _clear_xydata()
        print(('---------------------------------------'))
        print(('--------- End of EasyPBC (3D) ---------'))
        print(('---------------------------------------'))
        a = mdb.models[modelName].rootAssembly
        session.viewports['Viewport: 1'].setValues(displayedObject=a)

## Plugin main GUI function ##

def feasypbc(part,inst,meshsens,E11,E22,E33,G12,G13,G23,CTE,CPU,onlyPBC, intemp, fntemp, segment, umatName,
        elastic_temperature_points=None):
        import os
        global _JOB_TEMP_SUFFIX
        _JOB_TEMP_SUFFIX = _job_temperature_suffix(intemp, fntemp)
        path = os.getcwd()
        if elastic_temperature_points is None:
                elastic_temperature_points = []
        for T in (range(1)):
                start = time.time()
                modelName = part
                instanceName = inst
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
                '''
                if (mdb.models[modelName].rootAssembly.instances.keys()) != keycheck2:                       
                        Er3=0
                        messageBox3 = ctypes.windll.user32.MessageBoxA
                        returnValue = messageBox3(Er3,'Instance name is incorrect, please input the correct instance name.','EasyPBC Start-up error 03',0x30 | 0x0)
                        print('Start-up error 03. Refer EasyPBC user guide')
                        continue
                '''
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
                if onlyPBC == False and CTE == False and not elastic_temperature_points and abs(float(fntemp) - float(intemp)) <= 1.0e-12:
                        _set_uniform_initial_temperature(mdb.models[modelName], a, instanceName,
                                float(intemp) + 273.15, 'Elastic-Initial-Temperature')


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


                
                if (Maz - Mnz)<=meshsens:  ## 2D Model Check

                ############################################ 2D Section #####################################

                        L=abs(Max-Mnx)
                        H=abs(May-Mny)
                        
                        Dispx = L*0.2
                        Dispy = H*0.2

                        #### This part is commented out to reduce complexity for users whom merge parts into a single instance. ##############
                        
##                        partName = mdb.models[modelName].rootAssembly.instances[inst].partName                ## Extracts part name used in the instance
##                        AssSec = mdb.models[modelName].parts[partName].sectionAssignments[0].sectionName
##                        if AssSec == None:
##                                print('Warning: No shell sections detected, please create a section and try again!!'
##                                print('         Refer to error 09 troubleshooting in easyPBC user guide.'
##                                error=True
##                                continue

                        SecName = mdb.models[modelName].sections.keys()[0]                                      ## Finding the name of first section            
                        Thikness = mdb.models[modelName].sections[SecName].thickness
                        skipAtt = False
                        
                        if Thikness == None or Thikness == 0:
                                Thikness = 1
                                print('Attention: EasyPBC did not detected a shell thickness. Thus, it assumes thickness is equal to 1.0 unit length')
                                print('           If another thickness value is desired, divide the elastic property(ies) by the actual thickness value.')
                                skipAtt = True
                        if skipAtt == False:
                                print('Attention: EasyPBC detected a shell thickness of %s unit length from the first section in ABAQUS property module.' % Thikness)
                                print('           If this value is incorrect (this section is not used), multiply the elastic property(ies) %s and divide it by the actual value.' % Thikness)

                        
                        ## Creating Ref. Points (Same R.Ps as in the 3D case) ##
                        for i in a.features.keys():
                            if i.startswith('RP'):
                                del a.features['%s' % (i)]
                        a.ReferencePoint(point=(Max+0.8*abs(Max-Mnx), May-0.5*(May-Mny), Maz-0.5*(Maz-Mnz)))  ## RP6: G23
                        a.ReferencePoint(point=(Max+0.6*abs(Max-Mnx), May-0.5*(May-Mny), Maz-0.5*(Maz-Mnz)))  ## RP5: G13
                        a.ReferencePoint(point=(Max+0.4*abs(Max-Mnx), May-0.5*(May-Mny), Maz-0.5*(Maz-Mnz)))  ## RP4: G12
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
                            if (Mnx+meshsens) < i.coordinates[0] < (Max-meshsens) and (Mny+meshsens) < i.coordinates[1] < (May-meshsens):
                                continue

                            if abs(i.coordinates[0]-Max)<=meshsens and abs(i.coordinates[1]-May)<=meshsens:
                                c1.insert(0,i.label)
                                coc1[i.label]=[i.coordinates[0], i.coordinates[1]]
                            if abs(i.coordinates[0]-Mnx)<=meshsens and abs(i.coordinates[1]-May)<=meshsens:
                                c2.insert(0,i.label)
                                coc2[i.label]=[i.coordinates[0], i.coordinates[1]]
                            if abs(i.coordinates[0]-Max)<=meshsens and abs(i.coordinates[1]-Mny)<=meshsens:
                                c5.insert(0,i.label)
                                coc5[i.label]=[i.coordinates[0], i.coordinates[1]]
                            if abs(i.coordinates[0]-Mnx)<=meshsens and abs(i.coordinates[1]-Mny)<=meshsens:
                                c6.insert(0,i.label)
                                coc6[i.label]=[i.coordinates[0], i.coordinates[1]]
                            if abs(i.coordinates[0]-Max)<=meshsens and abs(i.coordinates[1]-May)>meshsens and abs(i.coordinates[1]-Mny)>meshsens:
                                frontsxyz[i.label]=[i.coordinates[0], i.coordinates[1]]
                            if abs(i.coordinates[0]-Mnx)<=meshsens and abs(i.coordinates[1]-May)>meshsens and abs(i.coordinates[1]-Mny)>meshsens:
                                backsxyz[i.label]=[i.coordinates[0], i.coordinates[1]] 
                            if abs(i.coordinates[1]-May)<=meshsens and abs(i.coordinates[0]-Max)>meshsens and abs(i.coordinates[0]-Mnx)>meshsens:
                                topsxyz[i.label]=[i.coordinates[0], i.coordinates[1]]
                            if abs(i.coordinates[1]-Mny)<=meshsens and abs(i.coordinates[0]-Max)>meshsens and abs(i.coordinates[0]-Mnx)>meshsens:
                                botsxyz[i.label]=[i.coordinates[0], i.coordinates[1]]

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
       
                        ## Sorting and appending sets ##
                        for i in frontsxyz.keys():
                                for k in backsxyz.keys():
                                        if abs(frontsxyz[i][1] - backsxyz[k][1])<=meshsens:
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
                                if abs(topsxyz[i][0] - botsxyz[k][0]) <=meshsens:
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



                        ## Creating ABAQUS sets ##
                        a.SetFromNodeLabels(name='c1', nodeLabels=((instanceName,c1),))
                        a.SetFromNodeLabels(name='c2', nodeLabels=((instanceName,c2),))
                        a.SetFromNodeLabels(name='c5', nodeLabels=((instanceName,c5),))
                        a.SetFromNodeLabels(name='c6', nodeLabels=((instanceName,c6),))
                        a.SetFromNodeLabels(name='fronts', nodeLabels=((instanceName,fronts),))
                        a.SetFromNodeLabels(name='backs', nodeLabels=((instanceName,backs),))
                        a.SetFromNodeLabels(name='tops', nodeLabels=((instanceName,tops),))
                        a.SetFromNodeLabels(name='bots', nodeLabels=((instanceName,bots),))
                        print('------ End of Sets Creation ------')

                        ## Extracting model mass ##
                        prop=mdb.models[modelName].rootAssembly.getMassProperties()
                        mass=prop['mass']

                        a = mdb.models[modelName].rootAssembly
                        Nodeset = mdb.models[modelName].rootAssembly.instances[instanceName].nodes
                        if error == False:
                                _run_elastic_cte_keyword_2d(
                                        part, modelName, instanceName, upperName, path, CPUs, onlyPBC,
                                        E11 == True, E22 == True, G12 == True, umatName, start, a,
                                        tops, bots, fronts, backs, c1, c2, c5, coc1, coc2, coc5,
                                        L, H, W, Thikness, Dispx, Dispy, mass)
                        continue


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
                a.ReferencePoint(point=(Max+0.8*abs(Max-Mnx), May-0.5*(May-Mny), Maz-0.5*(Maz-Mnz)))  ## RP6: G23
                a.ReferencePoint(point=(Max+0.6*abs(Max-Mnx), May-0.5*(May-Mny), Maz-0.5*(Maz-Mnz)))  ## RP5: G13
                a.ReferencePoint(point=(Max+0.4*abs(Max-Mnx), May-0.5*(May-Mny), Maz-0.5*(Maz-Mnz)))  ## RP4: G12
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
                print('------ End of Sets Creation ------')

                ## Extracting model mass ##
                prop=mdb.models[modelName].rootAssembly.getMassProperties()
                mass=prop['mass']

                a = mdb.models[modelName].rootAssembly
                Nodeset = mdb.models[modelName].rootAssembly.instances[instanceName].nodes
                if error == False:
                        _run_elastic_cte_keyword_3d(
                                part, modelName, instanceName, upperName, path, CPUs, onlyPBC,
                                E11 == True, E22 == True, E33 == True, G12 == True, G13 == True, G23 == True,
                                CTE == True, umatName, start, a, tops, bots, lefts, rights, fronts, backs,
                                ftedge, btedge, bbedge, fbedge, fledge, bledge, bredge, fredge,
                                ltedge, lbedge, rbedge, rtedge, c1, c2, c4, c5, coc1, coc2, coc4, coc5,
                                L, H, W, Dispx, Dispy, Dispz, mass, intemp, fntemp, segment)
                if error==True:
                        print(('Error(s) found during sets creation, please check the error No.(s) above with EasyPBC user guide.'))
                        
                        a.SetFromNodeLabels(name='Error set', nodeLabels=((instanceName,errorset),))

