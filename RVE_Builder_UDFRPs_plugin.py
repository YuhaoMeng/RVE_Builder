# -*- coding: utf-8 -*-
###############################################################################
# RVE_Builder_UDFRPs_plugin.py
# -----------------------------------------------------------------------------
# Plugin entry: registers the GUI form for "RVE Builder (UDFRPs)" in Abaqus.
# Defines AFXForm with all keywords (one cmd per tab) and binds the dialog
# class from RVE_Builder_UDFRPsDB. Kernel side is implemented in
# RVE_Builder_UDFRPs.py (imported via kernelInitString).
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

from abaqusGui import *
from abaqusConstants import ALL
import osutils, os

###########################################################################
# Class definition
###########################################################################

class RVE_Builder_UDFRPs_plugin(AFXForm):

    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def __init__(self, owner):

        AFXForm.__init__(self, owner)
        self.owner = owner
        self.form = None
        self.radioButtonGroups = {}

        # One AFXGuiCommand per tab -- bound to a kernel method in RVE_Builder_UDFRPs
        self.cmd_tab1 = AFXGuiCommand(mode=self, method='CreateRVE',    objectName='RVE_Builder_UDFRPs', registerQuery=False)
        self.cmd_tab2 = AFXGuiCommand(mode=self, method='MeshControl',  objectName='RVE_Builder_UDFRPs', registerQuery=False)
        self.cmd_tab3 = AFXGuiCommand(mode=self, method='Material',     objectName='RVE_Builder_UDFRPs', registerQuery=False)
        self.cmd_tab4 = AFXGuiCommand(mode=self, method='Void',         objectName='RVE_Builder_UDFRPs', registerQuery=False)
        self.cmd_tab5 = AFXGuiCommand(mode=self, method='Interface',    objectName='RVE_Builder_UDFRPs', registerQuery=False)
        self.cmd_tab6 = AFXGuiCommand(mode=self, method='Analysis',     objectName='RVE_Builder_UDFRPs', registerQuery=False)

        # Keywords for the first tab (Create RVE)
        self.myModelKw = AFXStringKeyword(self.cmd_tab1, 'myModel', True, 'RVE_UDFiber_Random')
        self.file_suffix_range_SetKw = AFXIntKeyword(self.cmd_tab1, 'file_suffix_range_Set', True, 1)

        self.dfKw = AFXFloatKeyword(self.cmd_tab1, 'df', True, 7.0)
        self.vfKw = AFXFloatKeyword(self.cmd_tab1, 'vf', True, 40)
        self.aKw = AFXFloatKeyword(self.cmd_tab1, 'a', True, 50.0)
        self.bKw = AFXFloatKeyword(self.cmd_tab1, 'b', True, 50.0)
        self.tKw = AFXFloatKeyword(self.cmd_tab1, 't', True, 50.0)

        self.algorithmKw = AFXIntKeyword(self.cmd_tab1, 'algorithm', True, 0)

        self.control_optionsKw = AFXIntKeyword(self.cmd_tab1, 'control_options', True, 0)

        self.l_safeKw = AFXFloatKeyword(self.cmd_tab1, 'l_safe', True, 0.5)
        self.lminKw = AFXFloatKeyword(self.cmd_tab1, 'lmin', True, 0.1)
        self.lmaxKw = AFXFloatKeyword(self.cmd_tab1, 'lmax', True, 1)
        self.readcsvKw = AFXStringKeyword(self.cmd_tab1, 'readcsv', True, '')
        # Default save folder: filled with the Abaqus work directory when the
        # dialog opens (see getFirstDialog); the plug-in is registered before the
        # work directory is known.
        self.BasefolderKw = AFXStringKeyword(self.cmd_tab1, 'Basefolder', True, '')

        # Keywords for the second tab (Mesh Control)
        self.modelNameKw = AFXStringKeyword(self.cmd_tab2, 'modelName', True)
        #self.partNameKw = AFXStringKeyword(self.cmd_tab2, 'partName', True)
        self.mesh_seed_size_curveKw = AFXIntKeyword(self.cmd_tab2, 'mesh_seed_size_curve', True, 12)
        self.mesh_seed_sizeKw = AFXIntKeyword(self.cmd_tab2, 'mesh_seed_number', True, 20)
        self.seeds_number_Z_lineKw = AFXIntKeyword(self.cmd_tab2, 'seeds_number_Z_line', True, 10)
        self.minSizeFactor_controlKw = AFXFloatKeyword(self.cmd_tab2, 'minSizeFactor_control', True, 0.1)
        self.Model_range = AFXIntKeyword(self.cmd_tab2, 'Model_range', True, 1)
        self.someTextFieldKw = AFXStringKeyword(self.cmd_tab2, 'someTextField', True, '1, 4-9')
        self.meshTypeKw = AFXIntKeyword(self.cmd_tab2, 'meshType', True, 0)

        self.useQuadraticKw = AFXBoolKeyword(self.cmd_tab2, 'useQuadratic', AFXBoolKeyword.TRUE_FALSE, True, False)
        self.useReducedKw = AFXBoolKeyword(self.cmd_tab2, 'useReduced', AFXBoolKeyword.TRUE_FALSE, True, False)
        self.useHybridKw = AFXBoolKeyword(self.cmd_tab2, 'useHybrid', AFXBoolKeyword.TRUE_FALSE, True, False)
        self.useThermalQuadraticKw = AFXBoolKeyword(self.cmd_tab2, 'useThermalQuadratic', AFXBoolKeyword.TRUE_FALSE, True, False)
        self.useThermalReducedKw = AFXBoolKeyword(self.cmd_tab2, 'useThermalReduced', AFXBoolKeyword.TRUE_FALSE, True, False)
        self.useConvectionKw = AFXBoolKeyword(self.cmd_tab2, 'useConvection', AFXBoolKeyword.TRUE_FALSE, True, False)
        self.useDispersionKw = AFXBoolKeyword(self.cmd_tab2, 'useDispersion', AFXBoolKeyword.TRUE_FALSE, True, False)


        # Keywords for the third tab (Materials)
        self.model_for_materialKw = AFXStringKeyword(self.cmd_tab3, 'model_for_material', True)
        self.fiber_materialKw = AFXStringKeyword(self.cmd_tab3, 'fiber_material', True)
        self.matrix_materialKw = AFXStringKeyword(self.cmd_tab3, 'matrix_material', True)
        self.Model_range_materialKw = AFXIntKeyword(self.cmd_tab3, 'Model_range_material', True, 1)
        self.user_inputKw = AFXStringKeyword(self.cmd_tab3, 'user_input', True, '1, 4-9')

        # Keywords for the fourth tab (Void)
        self.model_for_voidKw = AFXStringKeyword(self.cmd_tab4, 'model_for_void', True)
        self.part_for_voidKw = AFXStringKeyword(self.cmd_tab4, 'part_for_void', True)
        self.target_vf_voidKw = AFXFloatKeyword(self.cmd_tab4, 'target_vf_void', True, 5.0)
        self.Model_range_voidKw = AFXIntKeyword(self.cmd_tab4, 'Model_range_void', True, 1)
        self.user_input_voidKw = AFXStringKeyword(self.cmd_tab4, 'user_input_void', True, '1, 4-9')
        self.void_distribution_methodKw = AFXIntKeyword(self.cmd_tab4, 'void_distribution_method', True, 1)
        self.void_distribution_valueKw = AFXFloatKeyword(self.cmd_tab4, 'void_distribution_value', True, 0.5)
        self.void_size_methodKw = AFXIntKeyword(self.cmd_tab4, 'void_size_method', True, 1)
        self.void_theta_valueKw = AFXIntKeyword(self.cmd_tab4, 'void_theta_value', True, 5)
        self.void_priorityKw = AFXIntKeyword(self.cmd_tab4, 'void_priority', True, 3)

        # ---- Void shape factor β ----
        # When voidBetaActive is False, β is ignored and voids grow with the legacy
        # distance-weighted rule. When True, the candidate weighting is biased by
        # an ellipsoid envelope of axes proportional to (β, 1, 1) for β > 1
        # (prolate, elongated along the fiber X-axis) or (1, 1, β) for β < 1
        # (oblate, compressed along the Z-axis); β = 1 returns a sphere.
        self.voidBetaActiveKw      = AFXBoolKeyword (self.cmd_tab4, 'void_beta_active',      AFXBoolKeyword.TRUE_FALSE, True, False)
        self.voidBetaValueKw       = AFXFloatKeyword(self.cmd_tab4, 'void_beta_value',       True, 1.0)
        # 1 = random SO(3), 2 = orthogonal (axis-aligned to X/Y/Z)
        self.voidBetaOrientationKw = AFXIntKeyword  (self.cmd_tab4, 'void_beta_orientation', True, 1)
        # 1 = same β for both fiber-adjacent and inter-matrix voids; 2 = use separate β for each pool
        self.voidBetaUnifiedKw     = AFXIntKeyword  (self.cmd_tab4, 'void_beta_unified',     True, 1)
        self.voidBetaValueFiberKw  = AFXFloatKeyword(self.cmd_tab4, 'void_beta_value_fiber', True, 1.0)
        self.voidBetaValueMatrixKw = AFXFloatKeyword(self.cmd_tab4, 'void_beta_value_matrix',True, 1.0)
        # θ* = θ_fiber / Nf -- mean number of voids per fiber when active (informational input)
        self.voidThetaStarActiveKw = AFXBoolKeyword (self.cmd_tab4, 'void_theta_star_active',AFXBoolKeyword.TRUE_FALSE, True, False)
        self.voidThetaStarKw       = AFXFloatKeyword(self.cmd_tab4, 'void_theta_star',       True, 0.0)

        # Keywords for the fifth tab (Interface)
        self.model_for_interfaceKw = AFXStringKeyword(self.cmd_tab5, 'model_for_interface', True)
        self.part_for_interfaceKw = AFXStringKeyword(self.cmd_tab5, 'part_for_interface', True)
        self.Model_range_interfaceKw = AFXIntKeyword(self.cmd_tab5, 'Model_range_interface', True, 1)
        self.user_input_interfaceKw = AFXStringKeyword(self.cmd_tab5, 'user_input_interface', True, '1, 4-9')
        self.interface_materialKw = AFXStringKeyword(self.cmd_tab5, 'interface_material', True)
        self.interface_initial_debondingKw = AFXFloatKeyword(self.cmd_tab5, 'interface_initial_debonding', True, 0.0)
        # 1 = Mechanical (cohesive debonding); 2 = Thermal (contact + gap conductance)
        self.interface_purposeKw = AFXIntKeyword(self.cmd_tab5, 'interface_purpose', True, 1)
        # Kapitza thermal-boundary resistance R_K [mm^2*K/W]; kernel uses h = 1/R_K
        self.kapitza_resistanceKw = AFXFloatKeyword(self.cmd_tab5, 'kapitza_resistance', True, 1.0E-02)

        # Keywords for the sixth tab (Analysis)
        self.model_for_analysisKw = AFXStringKeyword(self.cmd_tab6, 'model_for_analysis', True)
        self.part_for_analysisKw = AFXStringKeyword(self.cmd_tab6, 'part_for_analysis', True)
        self.meshsensKw = AFXFloatKeyword(self.cmd_tab6, 'meshsens', True, 1E-04)
        self.CPUKw = AFXIntKeyword(self.cmd_tab6, 'CPU', True, 1)
        self.umatNameKw = AFXStringKeyword(self.cmd_tab6, 'umatName', True)

        # Elastic moduli flags
        self.E11Kw = AFXBoolKeyword(self.cmd_tab6, 'E11', AFXBoolKeyword.TRUE_FALSE, True, False)
        self.E22Kw = AFXBoolKeyword(self.cmd_tab6, 'E22', AFXBoolKeyword.TRUE_FALSE, True, False)
        self.E33Kw = AFXBoolKeyword(self.cmd_tab6, 'E33', AFXBoolKeyword.TRUE_FALSE, True, False)
        self.G12Kw = AFXBoolKeyword(self.cmd_tab6, 'G12', AFXBoolKeyword.TRUE_FALSE, True, False)
        self.G13Kw = AFXBoolKeyword(self.cmd_tab6, 'G13', AFXBoolKeyword.TRUE_FALSE, True, False)
        self.G23Kw = AFXBoolKeyword(self.cmd_tab6, 'G23', AFXBoolKeyword.TRUE_FALSE, True, False)

        # CTE (Coefficient of Thermal Expansion) options
        self.CTEKw = AFXBoolKeyword(self.cmd_tab6, 'CTE', AFXBoolKeyword.TRUE_FALSE, True, False)
        self.intempKw = AFXFloatKeyword(self.cmd_tab6, 'intemp', True, 0.0)
        self.fntempKw = AFXFloatKeyword(self.cmd_tab6, 'fntemp', True, 100)
        self.segmentKw = AFXIntKeyword(self.cmd_tab6, 'segment', True, 100)
        # Field-output sampling for elastoplastic runs: N evenly-spaced field
        # frames over the step (0 => every increment / full output).  Keeps the
        # ODB small; history output (RP forces, energies) is unaffected.
        self.field_output_intervalsKw = AFXIntKeyword(self.cmd_tab6, 'field_output_intervals', True, 80)
        # Elastoplastic *Static adaptive energy-stabilization magnitude
        # (DISSIPATED_ENERGY_FRACTION, DEF).  Default 2e-4.  Raise (e.g. 1e-3)
        # to damp the cohesive/damage-softening localization when the run
        # cuts back to minInc and aborts; lower to reduce artificial damping.
        self.stabilization_magnitudeKw = AFXFloatKeyword(self.cmd_tab6, 'stabilization_magnitude', True, 2e-4)
        # Elastoplastic analysis procedure (Step type).  STRING keyword: the
        # AFXComboBox passes the selected item's text verbatim (same pattern as
        # the Model/Part combos), so the kernel maps by text.  An int keyword
        # would make Abaqus try to eval the item text as a number -> syntax err.
        #   'Static + energy stabilization'   -> *Static (default; Melro static
        #       curve, UMAT must run IDMTAN=0 secant).
        #   'Quasi-static implicit dynamics'  -> *Dynamic, application=QUASI-
        #       STATIC: the inertia term gives a force basis through the near-
        #       zero-force first-yield / softening windows where pure *Static
        #       stalls ("ZERO FORCE EVERYWHERE"); needs *Density on every mat.
        self.epAnalysisProcedureKw = AFXStringKeyword(self.cmd_tab6, 'epAnalysisProcedure', True, 'Static + energy stabilization')

        self.onlyPBCKw = AFXBoolKeyword(self.cmd_tab6, 'onlyPBC', AFXBoolKeyword.TRUE_FALSE, True, False)
        self.Model_range_analysisKw = AFXIntKeyword(self.cmd_tab6, 'Model_range_analysis', True, 1)
        self.user_input_analysisKw = AFXStringKeyword(self.cmd_tab6, 'user_input_analysis', True, '1, 4-9')

        # Analysis type radio: 0=none, 1=Elastic+CTE, 2=ViscTime, 3=ViscFreq, 4=Elastoplastic, 5=Thermal
        self.analysisTypeKw = AFXIntKeyword(self.cmd_tab6, 'analysis_type', True, 0)

        # Viscoelastic time-domain
        self.import_viscoelasticKw = AFXBoolKeyword(self.cmd_tab6, 'import_viscoelastic', AFXBoolKeyword.TRUE_FALSE, True, False)
        self.temperatureKw = AFXFloatKeyword(self.cmd_tab6, 'temperature', True, 25)
        self.visco_temperature_pointsKw = AFXStringKeyword(self.cmd_tab6, 'visco_temperature_points', True, '25,50,75,100')
        self.relaxationTimeKw = AFXFloatKeyword(self.cmd_tab6, 'relaxationTime', True, 1800)
        self.time_pointKw = AFXIntKeyword(self.cmd_tab6, 'time_point', True, 20)

        # Viscoelastic frequency-domain
        self.import_viscoelastic_freqKw = AFXBoolKeyword(self.cmd_tab6, 'import_viscoelastic_freq', AFXBoolKeyword.TRUE_FALSE, True, False)
        self.lowerFreqKw = AFXFloatKeyword(self.cmd_tab6, 'lowerFreq', True, 0.1)
        self.upperFreqKw = AFXFloatKeyword(self.cmd_tab6, 'upperFreq', True, 1000.0)
        self.numPointsKw = AFXIntKeyword(self.cmd_tab6, 'numPoints', True, 50)
        self.biasKw = AFXFloatKeyword(self.cmd_tab6, 'bias', True, 1.0)

        # Thermal conductivity flags
        self.K11Kw = AFXBoolKeyword(self.cmd_tab6, 'K11', AFXBoolKeyword.TRUE_FALSE, True, False)
        self.K22Kw = AFXBoolKeyword(self.cmd_tab6, 'K22', AFXBoolKeyword.TRUE_FALSE, True, False)
        self.K33Kw = AFXBoolKeyword(self.cmd_tab6, 'K33', AFXBoolKeyword.TRUE_FALSE, True, False)

        self.import_thermal_conductivityKw = AFXBoolKeyword(self.cmd_tab6, 'import_thermal_conductivity', AFXBoolKeyword.TRUE_FALSE, True, False)

        # Elastoplastic strain inputs
        self.epStrainXKw  = AFXStringKeyword(self.cmd_tab6, 'epStrainX',  True, '0.001')
        self.epStrainYKw  = AFXStringKeyword(self.cmd_tab6, 'epStrainY',  True, '0.0')
        self.epStrainZKw  = AFXStringKeyword(self.cmd_tab6, 'epStrainZ',  True, '0.0')
        self.epShearXYKw  = AFXFloatKeyword(self.cmd_tab6, 'epShearXY',  True, 0.0)
        self.epShearYZKw  = AFXFloatKeyword(self.cmd_tab6, 'epShearYZ',  True, 0.0)
        self.epShearZXKw  = AFXFloatKeyword(self.cmd_tab6, 'epShearZX',  True, 0.0)

        # ----- New (multi-temperature + safer outputs + EP uniaxial/biaxial) -----
        # Comma-separated Celsius list for the elastic temperature sweep.
        self.elastic_temperature_pointsKw = AFXStringKeyword(self.cmd_tab6, 'elastic_temperature_points', True, '25,50,75,100')
        # Uniaxial vs Biaxial is now encoded by the Analysis-type radio
        # (4 = Elastoplastic Uniaxial, 6 = Elastoplastic Biaxial), so the old
        # epLoadingMode keyword has been retired -- the dispatcher reads
        # analysis_type directly.
        # Unsymmetric matrix storage for the StaticStep -- enable when the
        # active UMAT has an asymmetric tangent (e.g. non-associated flow,
        # Chaboche kinematic hardening). Off = standard symmetric solver.
        self.epUnsymmetricSolverKw = AFXBoolKeyword(self.cmd_tab6, 'epUnsymmetricSolver', AFXBoolKeyword.TRUE_FALSE, True, False)
        self.epLargeDeformationKw = AFXBoolKeyword(self.cmd_tab6, 'epLargeDeformation', AFXBoolKeyword.TRUE_FALSE, True, True)
        # Uniaxial component flags (which strain cases to actually run).
        self.epUseStrain11Kw = AFXBoolKeyword(self.cmd_tab6, 'epUseStrain11', AFXBoolKeyword.TRUE_FALSE, True, False)
        self.epUseStrain22Kw = AFXBoolKeyword(self.cmd_tab6, 'epUseStrain22', AFXBoolKeyword.TRUE_FALSE, True, False)
        self.epUseStrain33Kw = AFXBoolKeyword(self.cmd_tab6, 'epUseStrain33', AFXBoolKeyword.TRUE_FALSE, True, False)
        self.epUseShear12Kw  = AFXBoolKeyword(self.cmd_tab6, 'epUseShear12',  AFXBoolKeyword.TRUE_FALSE, True, False)
        self.epUseShear13Kw  = AFXBoolKeyword(self.cmd_tab6, 'epUseShear13',  AFXBoolKeyword.TRUE_FALSE, True, False)
        self.epUseShear23Kw  = AFXBoolKeyword(self.cmd_tab6, 'epUseShear23',  AFXBoolKeyword.TRUE_FALSE, True, False)
        # Biaxial selection (one of 15 pre-defined pairs) + the two values.
        self.epBiaxialComboKw  = AFXStringKeyword(self.cmd_tab6, 'epBiaxialCombo',  True, '')
        self.epBiaxialValue1Kw = AFXFloatKeyword(self.cmd_tab6,  'epBiaxialValue1', True, 0.0)
        self.epBiaxialValue2Kw = AFXFloatKeyword(self.cmd_tab6,  'epBiaxialValue2', True, 0.0)
        # Comma-separated Celsius list for the elastoplastic temperature sweep.
        self.epTemperaturePointsKw = AFXStringKeyword(self.cmd_tab6, 'epTemperaturePoints', True, '25,50,75,100')

    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def setForm(self, form):
        self.form = form

    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def getFirstDialog(self):

        # Default save folder: the current Abaqus work directory (File ->
        # Set Work Directory), unless the user already typed a folder.
        if not self.BasefolderKw.getValue():
            try:
                work_dir = getAFXApp().getAFXMainWindow().getWorkDirectory()
            except Exception:
                work_dir = os.getcwd()
            self.BasefolderKw.setValue(work_dir.replace('\\', '/'))

        # Open the dialog window (defined in RVE_Builder_UDFRPsDB)
        import RVE_Builder_UDFRPsDB
        return RVE_Builder_UDFRPsDB.RVE_Builder_UDFRPsDB(self)

    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def getCommandString(self):
        # Map currentTabIndex to the corresponding kernel command.
        # Visible tabs: 0..5 -> Create / Mesh / Material / Void / Interface / Analysis.
        if self.form.currentTabIndex == 0:
            cmd = self.cmd_tab1.getCommandString()
        elif self.form.currentTabIndex == 1:
            cmd = self.cmd_tab2.getCommandString()
        elif self.form.currentTabIndex == 2:
            cmd = self.cmd_tab3.getCommandString()
        elif self.form.currentTabIndex == 3:
            cmd = self.cmd_tab4.getCommandString()
        elif self.form.currentTabIndex == 4:
            cmd = self.cmd_tab5.getCommandString()
        elif self.form.currentTabIndex == 5:
            cmd = self.cmd_tab6.getCommandString()
        return cmd

    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def doCustomChecks(self):

        return True

    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def okToCancel(self):

        return False

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Registration Plugin
thisPath = os.path.abspath(__file__)
thisDir = os.path.dirname(thisPath)
# Local HTML help manual shipped with the plugin (open in default browser).
helpFile = os.path.join(thisDir, 'help', 'index.html').replace('\\', '/')
helpUrl  = 'file:///' + helpFile if os.path.exists(helpFile) else 'N/A'

# Plug-in menu icon. Sits next to this file in the plug-in folder. If the PNG
# is missing for any reason we fall back to icon=None so the registration still
# succeeds; Abaqus will then just show the default bullet next to the menu item.
iconFile = os.path.join(thisDir, 'icon.png')
try:
    pluginIcon = afxCreatePNGIcon(iconFile) if os.path.exists(iconFile) else None
except Exception:
    pluginIcon = None

toolset = getAFXApp().getAFXMainWindow().getPluginToolset()
toolset.registerGuiMenuButton(
    buttonText='RVE Builder (UDFRPs)',
    object=RVE_Builder_UDFRPs_plugin(toolset),
    messageId=AFXMode.ID_ACTIVATE,
    icon=pluginIcon,
    kernelInitString='import RVE_Builder_UDFRPs',
    applicableModules=ALL,
    version='1.0',
    author='Yuhao Meng',
    description='3D UD Fiber RVE Builder (UDFRPs) - see Help for details.',
    helpUrl=helpUrl
)
