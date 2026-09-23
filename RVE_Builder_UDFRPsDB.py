# -*- coding: utf-8 -*-
###############################################################################
# RVE_Builder_UDFRPsDB.py
# -----------------------------------------------------------------------------
# AFXDataDialog used by the "RVE Builder (UDFRPs)" plugin. Builds the tabbed
# GUI (Create RVE / Mesh Control / Materials / Void / Interface / Analysis),
# wires widgets to the keyword objects in RVE_Builder_UDFRPs_plugin, and
# forwards the OK action to the corresponding kernel handler.
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
from abaqusConstants import *
from abaqusGui import *
from kernelAccess import mdb, session
import os
thisPath = os.path.abspath(__file__)
thisDir = os.path.dirname(thisPath)
###########################################################################
# Class definition
###########################################################################
class RVE_Builder_UDFRPsDB(AFXDataDialog):
    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def __init__(self, form):
        form.setForm(self)
        AFXDataDialog.__init__(self, form, 'RVE Builder (UDFRPs)',
            self.OK|self.CANCEL, DIALOG_ACTIONS_SEPARATOR)
        okBtn = self.getActionButton(self.ID_CLICKED_OK)
        okBtn.setText('OK')
        self.currentTabIndex = 0
        self.ID_TABBOOK_1 = AFXDataDialog.ID_LAST + 100
        FXMAPFUNC(self, SEL_COMMAND, self.ID_TABBOOK_1, RVE_Builder_UDFRPsDB.onTabSwitched)
        self.TabBook_1 = FXTabBook(p=self, tgt=self, sel=self.ID_TABBOOK_1,
            opts=TABBOOK_NORMAL,
            x=0, y=0, w=0, h=0, pl=DEFAULT_SPACING, pr=DEFAULT_SPACING,
            pt=DEFAULT_SPACING, pb=DEFAULT_SPACING)
        
        #######################################################################
        # First tab： Create Rve
        #######################################################################
        
        def create_rve_tab():
            # Create Tab
            tabItem = FXTabItem(p=self.TabBook_1, text='Create RVE', ic=None, opts=TAB_TOP_NORMAL)
            self.TabItem_1 = FXVerticalFrame(p=self.TabBook_1,
                opts=FRAME_RAISED|FRAME_THICK|LAYOUT_FILL_X,
                pl=DEFAULT_SPACING, pr=DEFAULT_SPACING,
                pt=DEFAULT_SPACING, pb=DEFAULT_SPACING)
            
            AFXTextField(p=self.TabItem_1, ncols=53, labelText='Model Name*', tgt=form.myModelKw, sel=0)
            
            HFrame_Top = FXHorizontalFrame(p=self.TabItem_1, opts=LAYOUT_FILL_X|LAYOUT_FILL_Y)
            create_fibers_coordinates_generation_method_group(HFrame_Top)
            control_opions_group(HFrame_Top)
            
            HFrame_Main = FXHorizontalFrame(p=self.TabItem_1, opts=LAYOUT_FILL_X|LAYOUT_FILL_Y)
            create_geometric_parameters_group(HFrame_Main)
            create_diagram_section(HFrame_Main)
            
            create_base_parameter_section()
            
            spinner = AFXSpinner(p=self.TabItem_1, ncols=4, labelText='Number of generated models', tgt=form.file_suffix_range_SetKw, sel=0)
            spinner.setRange(1, 10000)
            spinner.setIncrement(1)
            
            AFXTextField(p=self.TabItem_1, ncols=32, labelText='Save folder directory **', tgt=form.BasefolderKw, sel=0)
            l = FXLabel(p=self.TabItem_1, text='** Automatically created when the folder directory does not exist', opts=JUSTIFY_LEFT)
        
        def create_fibers_coordinates_generation_method_group(parent):
            GroupBox_27 = FXGroupBox(p=parent, text='Fibers Coordinates Generation Method', opts=FRAME_GROOVE|LAYOUT_FILL_X|LAYOUT_FILL_Y)
            self.algorithmKw = form.algorithmKw
            self.ID_ALGORITHM_CHANGED = AFXDataDialog.ID_LAST + 200
            FXMAPFUNC(self, SEL_COMMAND, self.ID_ALGORITHM_CHANGED, RVE_Builder_UDFRPsDB.onAlgorithmChanged)
            self.algorithmKw.setTarget(self)
            self.algorithmKw.setSelector(self.ID_ALGORITHM_CHANGED)
            
            FXRadioButton(p=GroupBox_27, text='Monte Carlo', tgt=self.algorithmKw, sel=1)
            FXRadioButton(p=GroupBox_27, text='Random Sequential Expansion (RSE)', tgt=self.algorithmKw, sel=2)
            FXRadioButton(p=GroupBox_27, text='User coordinates file(s)', tgt=self.algorithmKw, sel=3)
        
        def control_opions_group(parent):
            GroupBox_20 = FXGroupBox(p=parent, text='Control Options', opts=FRAME_GROOVE|LAYOUT_FILL_X|LAYOUT_FILL_Y)
            self.control_optionsKw = form.control_optionsKw
            self.control_optionsKw.setTarget(self)
            
            FXRadioButton(p=GroupBox_20, text='keep vf', tgt=self.control_optionsKw, sel=1)
            FXRadioButton(p=GroupBox_20, text='keep RVE size', tgt=self.control_optionsKw, sel=2)

        def create_geometric_parameters_group(parent):
            GroupBox_5 = FXGroupBox(p=parent, text='Geometric Parameters', opts=FRAME_GROOVE|LAYOUT_FILL_X|LAYOUT_FILL_Y)
            HFrame_9 = FXHorizontalFrame(p=GroupBox_5)
            VAligner_8 = AFXVerticalAligner(p=HFrame_9, opts=LAYOUT_FILL_Y)
            
            HFrame_a = FXHorizontalFrame(p=VAligner_8, opts=LAYOUT_FILL_X)
            AFXTextField(p=HFrame_a, ncols=6, labelText='RVE Width (a):', tgt=form.aKw, sel=0)
            
            HFrame_b = FXHorizontalFrame(p=VAligner_8, opts=LAYOUT_FILL_X)
            AFXTextField(p=HFrame_b, ncols=6, labelText='RVE Height (b):', tgt=form.bKw, sel=0)
            
            HFrame_thickness = FXHorizontalFrame(p=VAligner_8, opts=LAYOUT_FILL_X)
            AFXTextField(p=HFrame_thickness, ncols=6, labelText='RVE thickness (t):', tgt=form.tKw, sel=0)
            
            HFrame_df = FXHorizontalFrame(p=VAligner_8, opts=LAYOUT_FILL_X)
            AFXTextField(p=HFrame_df, ncols=6, labelText='Fiber Diameter (df):', tgt=form.dfKw, sel=0)
            
            HFrame_vf = FXHorizontalFrame(p=VAligner_8, opts=LAYOUT_FILL_X)
            AFXTextField(p=HFrame_vf, ncols=6, labelText='Fiber Volume Fraction (vf):', tgt=form.vfKw, sel=0)
            FXLabel(p=HFrame_vf, text='%', opts=JUSTIFY_LEFT)
        
        def create_diagram_section(parent):
            GroupBox_29 = FXGroupBox(p=parent, text='Diagram', opts=FRAME_GROOVE|LAYOUT_FILL_X|LAYOUT_FILL_Y)
            fileName = os.path.join(thisDir, 'Random_RVE_Model.png')
            icon = afxCreatePNGIcon(fileName)
            FXLabel(p=GroupBox_29, text='', ic=icon, opts=LAYOUT_FILL_X|LAYOUT_FILL_Y)
        
        def create_base_parameter_section():
            GroupBox_28 = FXGroupBox(p=self.TabItem_1, text='Base Parameter', opts=FRAME_GROOVE|LAYOUT_FILL_X)
            
            # Label when no algorithm is selected
            self.noAlgorithmSelectedFrame = FXVerticalFrame(p=GroupBox_28, opts=LAYOUT_FILL_X)
            FXLabel(p=self.noAlgorithmSelectedFrame, text=' ', opts=JUSTIFY_LEFT)
            noAlgorithmLabel = FXLabel(p=self.noAlgorithmSelectedFrame, text='Fibers coordinates generation method not yet selected.', opts=JUSTIFY_CENTER_X|LAYOUT_CENTER_X|LAYOUT_CENTER_Y)
            FXLabel(p=self.noAlgorithmSelectedFrame, text=' ', opts=JUSTIFY_LEFT)
            
            # Base parameter for Monte Carlo algorithm
            self.baseParamMonteCarloFrame = FXVerticalFrame(p=GroupBox_28, opts=LAYOUT_FILL_X)
            l = FXLabel(p=self.baseParamMonteCarloFrame, text='Note: Maximum fiber volume fraction < 45%.', opts=JUSTIFY_LEFT)
            l.setFont(getAFXFont(FONT_BOLD))
            AFXTextField(p=self.baseParamMonteCarloFrame, ncols=8, labelText='Safe Distance between Fibers:', tgt=form.l_safeKw, sel=0)
            l = FXLabel(p=self.baseParamMonteCarloFrame, text=' ', opts=JUSTIFY_LEFT)
            l.setFont(getAFXFont(FONT_BOLD))
            
            # Base parameter for RSE algorithm
            self.baseParamRSEFrame = FXVerticalFrame(p=GroupBox_28, opts=LAYOUT_FILL_X)
            l = FXLabel(p=self.baseParamRSEFrame, text='Note: Maximum Fiber Volume Fraction < 68%.', opts=JUSTIFY_LEFT)
            l.setFont(getAFXFont(FONT_BOLD))
            AFXTextField(p=self.baseParamRSEFrame, ncols=12, labelText='Minimum Distance between Fibers: ', tgt=form.lminKw, sel=0)
            AFXTextField(p=self.baseParamRSEFrame, ncols=12, labelText='Maximum Distance between Fibers:', tgt=form.lmaxKw, sel=0)
            
            # User Coordinates parameter
            self.baseParamUserCoordinatesFrame = FXVerticalFrame(p=GroupBox_28, opts=LAYOUT_FILL_X)
            l = FXLabel(p=self.baseParamUserCoordinatesFrame, text='Note: Select the csv file and include only the coordinate values.', opts=JUSTIFY_LEFT)
            l.setFont(getAFXFont(FONT_BOLD))
            l = FXLabel(p=self.baseParamUserCoordinatesFrame, text='            Select the same number of files as set below.', opts=JUSTIFY_LEFT)
            l.setFont(getAFXFont(FONT_BOLD))
            fileHandler = RVE_Builder_UDFRPsDBFileHandler(form, 'readcsv', 'CSV files (*.csv)')
            fileTextHf = FXHorizontalFrame(p=self.baseParamUserCoordinatesFrame)
            fileTextHf.setSelector(99)
            AFXTextField(p=fileTextHf, ncols=32, labelText='Select Coordinates File(s):', tgt=form.readcsvKw, sel=0,
                         opts=AFXTEXTFIELD_STRING|LAYOUT_CENTER_Y)
            icon = afxGetIcon('fileOpen', AFX_ICON_SMALL)
            FXButton(p=fileTextHf, text='', ic=icon, tgt=fileHandler, sel=AFXMode.ID_ACTIVATE,
                     opts=BUTTON_NORMAL|LAYOUT_CENTER_Y, pl=1, pr=1, pt=1, pb=1)
            
            self.noAlgorithmSelectedFrame.show()
            self.baseParamMonteCarloFrame.hide()
            self.baseParamRSEFrame.hide()
            self.baseParamUserCoordinatesFrame.hide()
        
        create_rve_tab()
        
        #######################################################################
        # Second tab: Mesh Control
        #######################################################################
        def create_mesh_control_tab():
            tabItem = FXTabItem(p=self.TabBook_1, text='Mesh Control', ic=None, opts=TAB_TOP_NORMAL)
            self.TabItem_6 = FXVerticalFrame(p=self.TabBook_1,
                opts=FRAME_RAISED|FRAME_THICK|LAYOUT_FILL_X,
                pl=DEFAULT_SPACING, pr=DEFAULT_SPACING,
                pt=DEFAULT_SPACING, pb=DEFAULT_SPACING)
            
            def create_select_part_group():
                GroupBox_17 = FXGroupBox(p=self.TabItem_6, text='Select Model', opts=FRAME_GROOVE|LAYOUT_FILL_X)
                frame = FXHorizontalFrame(GroupBox_17)
                
                self.RootComboBox_9 = AFXComboBox(p=frame, ncols=0, nvis=1, text='Model:', tgt=form.modelNameKw, sel=0)
                self.RootComboBox_9.setMaxVisible(10)
        
                names = mdb.models.keys()
                names.sort()
                for name in names:
                    self.RootComboBox_9.appendItem(name)
                if not form.modelNameKw.getValue() in names:
                    form.modelNameKw.setValue(names[0])
                msgCount = 6
                form.modelNameKw.setTarget(self)
                form.modelNameKw.setSelector(AFXDataDialog.ID_LAST+msgCount)
                '''
                msgHandler = str(self.__class__).split('.')[-1] + '.onComboBox_9PartsChanged'
                FXMAPFUNC(self, SEL_COMMAND, AFXDataDialog.ID_LAST + msgCount, getattr(self, 'onComboBox_9PartsChanged'))
                
                self.ComboBox_9 = AFXComboBox(p=frame, ncols=0, nvis=1, text='Part:', tgt=form.partNameKw, sel=0)
                self.ComboBox_9.setMaxVisible(10)
                self.form = form
            '''
            def create_model_range_group():
                # Modify the group box title to 'Select Model Range for Meshing'
                GroupBox_39 = FXGroupBox(p=self.TabItem_6, text='Select Model Range for Meshing', opts=FRAME_GROOVE|LAYOUT_FILL_X)
                vertical_frame = FXVerticalFrame(p=GroupBox_39, opts=LAYOUT_FILL_X|LAYOUT_FILL_Y)
                
                h_frame_row1 = FXHorizontalFrame(p=vertical_frame, opts=LAYOUT_FILL_X)
                self.RadioButton_1 = FXRadioButton(p=h_frame_row1, text='Current Model', tgt=form.Model_range, sel=1)
                self.RadioButton_2 = FXRadioButton(p=h_frame_row1, text='All Models*', tgt=form.Model_range, sel=2)
                self.RadioButton_3 = FXRadioButton(p=h_frame_row1, text='Selected numbers**', tgt=form.Model_range, sel=3)
                self.TextField = FXTextField(p=h_frame_row1, ncols=10, tgt=form.someTextFieldKw, sel=0)
                self.TextField.disable()
                
                self.ID_MODEL_RANGE_CHANGED = AFXDataDialog.ID_LAST + 11
                form.Model_range.setTarget(self)
                form.Model_range.setSelector(self.ID_MODEL_RANGE_CHANGED)
                FXMAPFUNC(self, SEL_COMMAND, self.ID_MODEL_RANGE_CHANGED, RVE_Builder_UDFRPsDB.onModelRangeChanged)
                
                FXLabel(p=vertical_frame, text='Note: * Meshing applies to models with the same primary name.\n'
                                               '         ** use "-" for ranges and "," for specific values. E.g., 2, 4-11.', opts=JUSTIFY_LEFT)
                if isinstance(self.TabItem_6, FXHorizontalFrame):
                    FXVerticalSeparator(p=self.TabItem_6, pl=2, pr=2, pt=2, pb=2)
                else:
                    FXHorizontalSeparator(p=self.TabItem_6, pl=2, pr=2, pt=2, pb=2)
            
            create_select_part_group()
            create_model_range_group()
            HFrame_Main = FXHorizontalFrame(p=self.TabItem_6, opts=LAYOUT_FILL_X|LAYOUT_FILL_Y)
            VAligner_Left = AFXVerticalAligner(p=HFrame_Main, opts=LAYOUT_FILL_X|LAYOUT_FILL_Y)
            
            def create_mesh_seeds_group():
                GroupBox_18 = FXGroupBox(p=VAligner_Left, text='Seeds Control (by Number)', opts=FRAME_GROOVE|LAYOUT_FILL_X|LAYOUT_FILL_Y)
                VAligner_4 = AFXVerticalAligner(p=GroupBox_18)
            
                spinner = AFXSpinner(p=VAligner_4, ncols=4, labelText='Circle-dominant and Arc:', tgt=form.mesh_seed_size_curveKw, sel=0)
                spinner.setRange(3, 10000)
                spinner.setIncrement(1)
                spinner = AFXSpinner(p=VAligner_4, ncols=4, labelText='Along Fiber Direction Edges:', tgt=form.seeds_number_Z_lineKw, sel=0)
                spinner.setRange(1, 100000)
                spinner.setIncrement(1)
                spinner = AFXFloatSpinner(p=VAligner_4, ncols=4, labelText='Minimum Size Control:', tgt=form.minSizeFactor_controlKw, sel=0)
                spinner.setRange(0.01, 0.99)
                spinner.setIncrement(0.01)
            
            def create_mesh_type_group():
                GroupBox_MeshType = FXGroupBox(p=VAligner_Left, text='Mesh Type Selection', opts=FRAME_GROOVE|LAYOUT_FILL_X|LAYOUT_FILL_Y)
                
                self.ID_MESH_TYPE_CHANGED = AFXDataDialog.ID_LAST + 201
                form.meshTypeKw.setTarget(self)
                form.meshTypeKw.setSelector(self.ID_MESH_TYPE_CHANGED)
                FXMAPFUNC(self, SEL_COMMAND, self.ID_MESH_TYPE_CHANGED, RVE_Builder_UDFRPsDB.onMeshTypeChanged)
                
                FXRadioButton(p=GroupBox_MeshType, text='Thermal Analysis (DC3D8)', tgt=form.meshTypeKw, sel=1)
                FXRadioButton(p=GroupBox_MeshType, text='Mechanical Analysis (C3D8)', tgt=form.meshTypeKw, sel=2)
                FXRadioButton(p=GroupBox_MeshType, text='Thermo-Mechanical Coupled (C3D8T)', tgt=form.meshTypeKw, sel=3)
            
            def create_element_options_group():
                GroupBox_ElemOpt = FXGroupBox(p=VAligner_Left, text='Element Options', opts=FRAME_GROOVE|LAYOUT_FILL_X|LAYOUT_FILL_Y)
                
                # Mechanical/Coupled options frame
                self.mechanicalOptionsFrame = FXVerticalFrame(p=GroupBox_ElemOpt)
                self.quadraticCheckBox = FXCheckButton(p=self.mechanicalOptionsFrame, text='Quadratic (20-nodes)', tgt=form.useQuadraticKw, sel=0)
                self.reducedCheckBox = FXCheckButton(p=self.mechanicalOptionsFrame, text='Reduced Integration (R)', tgt=form.useReducedKw, sel=0)
                self.hybridCheckBox = FXCheckButton(p=self.mechanicalOptionsFrame, text='Hybrid Formulation (H)', tgt=form.useHybridKw, sel=0)
                
                # Thermal options frame
                self.thermalOptionsFrame = FXVerticalFrame(p=GroupBox_ElemOpt)
                
                self.ID_THERMAL_QUADRATIC_CHANGED = AFXDataDialog.ID_LAST + 204
                self.ID_THERMAL_REDUCED_CHANGED = AFXDataDialog.ID_LAST + 205
                self.ID_CONVECTION_CHANGED = AFXDataDialog.ID_LAST + 206
                self.ID_DISPERSION_CHANGED = AFXDataDialog.ID_LAST + 207
                
                form.useThermalQuadraticKw.setTarget(self)
                form.useThermalQuadraticKw.setSelector(self.ID_THERMAL_QUADRATIC_CHANGED)
                FXMAPFUNC(self, SEL_COMMAND, self.ID_THERMAL_QUADRATIC_CHANGED, RVE_Builder_UDFRPsDB.onThermalQuadraticChanged)
                
                form.useThermalReducedKw.setTarget(self)
                form.useThermalReducedKw.setSelector(self.ID_THERMAL_REDUCED_CHANGED)
                FXMAPFUNC(self, SEL_COMMAND, self.ID_THERMAL_REDUCED_CHANGED, RVE_Builder_UDFRPsDB.onThermalReducedChanged)
                
                form.useConvectionKw.setTarget(self)
                form.useConvectionKw.setSelector(self.ID_CONVECTION_CHANGED)
                FXMAPFUNC(self, SEL_COMMAND, self.ID_CONVECTION_CHANGED, RVE_Builder_UDFRPsDB.onConvectionChanged)
                
                form.useDispersionKw.setTarget(self)
                form.useDispersionKw.setSelector(self.ID_DISPERSION_CHANGED)
                FXMAPFUNC(self, SEL_COMMAND, self.ID_DISPERSION_CHANGED, RVE_Builder_UDFRPsDB.onDispersionChanged)
                
                self.thermalQuadraticCheckBox = FXCheckButton(p=self.thermalOptionsFrame, text='Quadratic (20-node)', tgt=form.useThermalQuadraticKw, sel=0)
                self.thermalReducedCheckBox = FXCheckButton(p=self.thermalOptionsFrame, text='Reduced Integration (R)', tgt=form.useThermalReducedKw, sel=0)
                self.convectionCheckBox = FXCheckButton(p=self.thermalOptionsFrame, text='Convection/Diffusion (C)', tgt=form.useConvectionKw, sel=0)
                self.dispersionCheckBox = FXCheckButton(p=self.thermalOptionsFrame, text='Dispersion Control (D)', tgt=form.useDispersionKw, sel=0)
                
                self.dispersionCheckBox.disable()
                
                FXLabel(p=GroupBox_ElemOpt, text='Note: Thermal element selection rules:\n'
                        '  - DC3D20: Cannot use R, C, or D options\n'
                        '  - DC3D8R: Cannot use C or D options\n'
                        '  - DCC3D8: Can optionally add D\n'
                        '  - DCC3D8D: Automatically includes C')
            
            def create_diagram_section():
                GroupBox_Image = FXGroupBox(p=HFrame_Main, text='Diagram', opts=FRAME_GROOVE|LAYOUT_FILL_X|LAYOUT_FILL_Y)
                fileName = os.path.join(thisDir, 'Mesh_Seed_Diagram.png')
                icon = afxCreatePNGIcon(fileName)
                FXLabel(p=GroupBox_Image, text='', ic=icon, opts=LAYOUT_FILL_X|LAYOUT_FILL_Y)
            
            create_mesh_seeds_group()
            create_mesh_type_group()
            create_element_options_group()
            create_diagram_section()
        
        create_mesh_control_tab()
        
        #######################################################################
        # Third tab: Materials
        #######################################################################
        def create_materials_tab():
            tabItem = FXTabItem(p=self.TabBook_1, text='Materials', ic=None, opts=TAB_TOP_NORMAL)
            self.TabItem_8 = FXVerticalFrame(p=self.TabBook_1,
                opts=FRAME_RAISED|FRAME_THICK|LAYOUT_FILL_X,
                pl=DEFAULT_SPACING, pr=DEFAULT_SPACING,
                pt=DEFAULT_SPACING, pb=DEFAULT_SPACING)
            create_material_selection_group()
            create_model_range_material_group()
        
        def create_material_selection_group():
            GroupBox_34 = FXGroupBox(p=self.TabItem_8, text='Select materials', opts=FRAME_GROOVE|LAYOUT_FILL_X)
            VFrame_7 = FXVerticalFrame(p=GroupBox_34)
            create_fiber_material_group(VFrame_7)
            create_matrix_material_group(VFrame_7)
        
        def create_fiber_material_group(parent):
            GroupBox_36 = FXGroupBox(p=parent, text='Fiber', opts=FRAME_GROOVE|LAYOUT_FILL_X)
            frame = FXHorizontalFrame(GroupBox_36)
        
            self.RootComboBox_11 = AFXComboBox(p=frame, ncols=0, nvis=1, text='Model:', tgt=form.model_for_materialKw, sel=0)
            self.RootComboBox_11.setMaxVisible(10)
        
            names = mdb.models.keys()
            names.sort()
            for name in names:
                self.RootComboBox_11.appendItem(name)
            if not form.model_for_materialKw.getValue() in names:
                form.model_for_materialKw.setValue(names[0])
            msgCount = 7
            msgID = AFXDataDialog.ID_LAST + msgCount
            form.model_for_materialKw.setTarget(self)
            form.model_for_materialKw.setSelector(msgID)
            FXMAPFUNC(self, SEL_COMMAND, msgID, self.onComboBox_11MaterialsChanged)
            self.ComboBox_11 = AFXComboBox(p=frame, ncols=0, nvis=1, text='Material:', tgt=form.fiber_materialKw, sel=0)
            self.ComboBox_11.setMaxVisible(10)
            self.form = form
        
        def create_matrix_material_group(parent):
            GroupBox_35 = FXGroupBox(p=parent, text='Matrix', opts=FRAME_GROOVE)
            frame = FXHorizontalFrame(GroupBox_35)
        
            self.RootComboBox_10 = AFXComboBox(p=frame, ncols=0, nvis=1, text='Model:', tgt=form.model_for_materialKw, sel=0)
            self.RootComboBox_10.setMaxVisible(10)
        
            names = mdb.models.keys()
            names.sort()
            for name in names:
                self.RootComboBox_10.appendItem(name)
            if not form.model_for_materialKw.getValue() in names:
                form.model_for_materialKw.setValue(names[0])
            msgCount = 8
            msgID = AFXDataDialog.ID_LAST + msgCount
            form.model_for_materialKw.setTarget(self)
            form.model_for_materialKw.setSelector(msgID)
            FXMAPFUNC(self, SEL_COMMAND, msgID, self.onComboBox_10MaterialsChanged)
        
            self.ComboBox_10 = AFXComboBox(p=frame, ncols=0, nvis=1, text='Material:', tgt=form.matrix_materialKw, sel=0)
            self.ComboBox_10.setMaxVisible(10)
            self.form = form
        
        def create_model_range_material_group():
            GroupBox_99 = FXGroupBox(p=self.TabItem_8, text='Select Model Range for Material', opts=FRAME_GROOVE|LAYOUT_FILL_X)
            vertical_frame9 = FXVerticalFrame(p=GroupBox_99, opts=LAYOUT_FILL_X|LAYOUT_FILL_Y)
            
            h_frame_row1 = FXHorizontalFrame(p=vertical_frame9, opts=LAYOUT_FILL_X)
            self.RadioButton_1_material = FXRadioButton(p=h_frame_row1, text='Current Model', tgt=self.form.Model_range_materialKw, sel=1)
            self.RadioButton_2_material = FXRadioButton(p=h_frame_row1, text='All Models*', tgt=self.form.Model_range_materialKw, sel=2)
            self.RadioButton_3_material = FXRadioButton(p=h_frame_row1, text='Selected numbers**', tgt=self.form.Model_range_materialKw, sel=3)
            self.TextField_material = FXTextField(p=h_frame_row1, ncols=10, tgt=self.form.user_inputKw, sel=0)
            self.TextField_material.disable()
            self.ID_MODEL_RANGE_MATERIAL_CHANGED = AFXDataDialog.ID_LAST + 22
            self.form.Model_range_materialKw.setTarget(self)
            self.form.Model_range_materialKw.setSelector(self.ID_MODEL_RANGE_MATERIAL_CHANGED)
            FXMAPFUNC(self, SEL_COMMAND, self.ID_MODEL_RANGE_MATERIAL_CHANGED, self.onModelRangeMaterialChanged)
            
            FXLabel(p=vertical_frame9, text='Note: * Materials applies to models with the same primary name.\n'
                                           '         ** use "-" for ranges and "," for specific values. E.g., 2, 4-11.', opts=JUSTIFY_LEFT)
        
        create_materials_tab()
        
        #######################################################################
        # Fourth tab： Void
        #######################################################################
        def create_void_insertion_tab():
            tabItem = FXTabItem(p=self.TabBook_1, text='Void Insertion', ic=None, opts=TAB_TOP_NORMAL)
            self.TabItem_4 = FXVerticalFrame(p=self.TabBook_1,
                opts=FRAME_RAISED|FRAME_THICK|LAYOUT_FILL_X,
                pl=DEFAULT_SPACING, pr=DEFAULT_SPACING,
                pt=DEFAULT_SPACING, pb=DEFAULT_SPACING)
            
            create_void_model_selection_group()
            create_void_volume_fraction_input()
            create_void_distribution_group()
            create_void_size_group()
            create_void_priority_group()
            create_void_shape_group()
            create_void_model_range_group()
        
        def create_void_model_selection_group():
            GroupBox = FXGroupBox(p=self.TabItem_4, text='Select Model and Part', opts=FRAME_GROOVE|LAYOUT_FILL_X)
            frame = FXHorizontalFrame(GroupBox)
            
            # Model selection combo box
            self.RootComboBox_void_model = AFXComboBox(p=frame, ncols=0, nvis=1, text='Model:', tgt=form.model_for_voidKw, sel=0)
            self.RootComboBox_void_model.setMaxVisible(10)
            names = mdb.models.keys()
            names.sort()
            for name in names:
                self.RootComboBox_void_model.appendItem(name)
            if not form.model_for_voidKw.getValue() in names:
                form.model_for_voidKw.setValue(names[0])
            msgCount = 40
            msgID = AFXDataDialog.ID_LAST + msgCount
            form.model_for_voidKw.setTarget(self)
            form.model_for_voidKw.setSelector(msgID)
            FXMAPFUNC(self, SEL_COMMAND, msgID, self.onComboBox_void_modelChanged)
            
            # Part selection combo box
            self.ComboBox_void_part = AFXComboBox(p=frame, ncols=0, nvis=1, text='Part:', tgt=form.part_for_voidKw, sel=0)
            self.ComboBox_void_part.setMaxVisible(10)
            self.updateComboBox_void_parts()  # Initialize the parts combo box
        
        def create_void_volume_fraction_input():
            GroupBox = FXGroupBox(p=self.TabItem_4, text='Void Volume Fraction', opts=FRAME_GROOVE|LAYOUT_FILL_X)
            spinner = AFXFloatSpinner(p=GroupBox, ncols=6, labelText='Target Void Volume Fraction (%):', tgt=form.target_vf_voidKw, sel=0)
            spinner.setRange(0.0, 99.99)
            spinner.setIncrement(0.01)
        
        def create_void_distribution_group():
            GroupBox_void_dist = FXGroupBox(p=self.TabItem_4, text='Void Distribution', opts=FRAME_GROOVE|LAYOUT_FILL_X)
            voidDistMethodKw = form.void_distribution_methodKw
            ID_VOID_DIST_CHANGED = AFXDataDialog.ID_LAST + 42
            FXMAPFUNC(self, SEL_COMMAND, ID_VOID_DIST_CHANGED, RVE_Builder_UDFRPsDB.onVoidDistMethodChanged)
            voidDistMethodKw.setTarget(self)
            voidDistMethodKw.setSelector(ID_VOID_DIST_CHANGED)
            
            # Both mutually-exclusive options on a single row.
            HFrame_custom = FXHorizontalFrame(p=GroupBox_void_dist, opts=LAYOUT_FILL_X)
            FXRadioButton(p=HFrame_custom, text='Random Number Method', tgt=form.void_distribution_methodKw, sel=1)
            FXRadioButton(p=HFrame_custom, text='   Custom (w, 0~1):', tgt=form.void_distribution_methodKw, sel=2)
            self.voidDistValueSpinner = AFXFloatSpinner(p=HFrame_custom, ncols=8, labelText='', tgt=form.void_distribution_valueKw, sel=0)
            self.voidDistValueSpinner.setRange(0.0, 1.0)
            self.voidDistValueSpinner.setIncrement(0.01)
            self.voidDistValueSpinner.disable()
            
            VFrame_note = FXVerticalFrame(p=GroupBox_void_dist, opts=LAYOUT_FILL_X)
            FXLabel(p=VFrame_note, text='Note: Microvoids distribution parameter (w) [fiber-adjacent voids VOLUME/total voids VOLUME]', opts=JUSTIFY_LEFT)
            FXLabel(p=VFrame_note, text='      Custom: manually control microvoid distribution type.', opts=JUSTIFY_LEFT)
            FXLabel(p=VFrame_note, text='      "0" = all inter-matrix voids, "1" = all fiber-adjacent voids.', opts=JUSTIFY_LEFT)
        
        def create_void_size_group():
            GroupBox_void_size = FXGroupBox(p=self.TabItem_4, text='Void Size', opts=FRAME_GROOVE|LAYOUT_FILL_X)
            
            voidSizeMethodKw = form.void_size_methodKw
            ID_VOID_SIZE_CHANGED = AFXDataDialog.ID_LAST + 43
            FXMAPFUNC(self, SEL_COMMAND, ID_VOID_SIZE_CHANGED, RVE_Builder_UDFRPsDB.onVoidSizeMethodChanged)
            voidSizeMethodKw.setTarget(self)
            voidSizeMethodKw.setSelector(ID_VOID_SIZE_CHANGED)
            
            # Both mutually-exclusive options on a single row.
            HFrame_custom_size = FXHorizontalFrame(p=GroupBox_void_size, opts=LAYOUT_FILL_X)
            FXRadioButton(p=HFrame_custom_size, text='Random Void Size', tgt=form.void_size_methodKw, sel=1)
            FXRadioButton(p=HFrame_custom_size, text='   Custom Size (theta):', tgt=form.void_size_methodKw, sel=2)
            self.voidThetaSpinner = AFXSpinner(p=HFrame_custom_size, ncols=6, labelText='', tgt=form.void_theta_valueKw, sel=0)
            self.voidThetaSpinner.setRange(1, 1000)
            self.voidThetaSpinner.setIncrement(1)
            self.voidThetaSpinner.disable()
            
            VFrame_size_note = FXVerticalFrame(p=GroupBox_void_size, opts=LAYOUT_FILL_X)
            FXLabel(p=VFrame_size_note, text='Note: theta = number of microvoids = total void Vf / average single void Vf', opts=JUSTIFY_LEFT)
            FXLabel(p=VFrame_size_note, text='      When theta = 1, w must be set to 0, 1, or Random.', opts=JUSTIFY_LEFT)
            
        def create_void_priority_group():
            GroupBox_void_priority = FXGroupBox(p=self.TabItem_4, text='Priority', opts=FRAME_GROOVE|LAYOUT_FILL_X)
            
            # All three options on a single horizontal row.
            HFrame_priority = FXHorizontalFrame(p=GroupBox_void_priority, opts=LAYOUT_FILL_X)
            self.RadioButton_priority_1 = FXRadioButton(p=HFrame_priority, text='Distribution Priority (strict w)', tgt=form.void_priorityKw, sel=1)
            self.RadioButton_priority_2 = FXRadioButton(p=HFrame_priority, text='Size Priority (allow w deviation)', tgt=form.void_priorityKw, sel=2)
            self.RadioButton_priority_3 = FXRadioButton(p=HFrame_priority, text='No Intervention', tgt=form.void_priorityKw, sel=3)
            
            FXLabel(p=GroupBox_void_priority, text='Note: Total void volume fraction is always guaranteed.', opts=JUSTIFY_LEFT)

        def create_void_shape_group():
            # ---- Void Shape Factor (beta) ----
            # beta = 1 -> sphere (default); beta > 1 -> prolate (beta:1:1, fiber X-axis);
            # beta < 1 -> oblate (1:1:beta, compressed along Z-axis).
            GroupBox_void_shape = FXGroupBox(p=self.TabItem_4, text='Void Shape Factor (beta) - experimental feature under development', opts=FRAME_GROOVE|LAYOUT_FILL_X)

            # Enable / disable toggle
            HFrame_enable = FXHorizontalFrame(p=GroupBox_void_shape, opts=LAYOUT_FILL_X)
            self.voidBetaActiveCheck = FXCheckButton(p=HFrame_enable,
                text='Enable shape factor (otherwise voids grow with the default distance-weighted rule)',
                tgt=form.voidBetaActiveKw, sel=0)
            ID_VOID_BETA_ACTIVE = AFXDataDialog.ID_LAST + 44
            form.voidBetaActiveKw.setTarget(self)
            form.voidBetaActiveKw.setSelector(ID_VOID_BETA_ACTIVE)
            FXMAPFUNC(self, SEL_COMMAND, ID_VOID_BETA_ACTIVE, self.onVoidBetaActiveChanged)

            # Unified vs split beta
            HFrame_mode = FXHorizontalFrame(p=GroupBox_void_shape, opts=LAYOUT_FILL_X)
            self.voidBetaUnifiedRadio1 = FXRadioButton(p=HFrame_mode, text='Unified beta', tgt=form.voidBetaUnifiedKw, sel=1)
            self.voidBetaUnifiedRadio2 = FXRadioButton(p=HFrame_mode, text='Split beta (fiber-adjacent / inter-matrix)', tgt=form.voidBetaUnifiedKw, sel=2)
            ID_VOID_BETA_UNIFIED = AFXDataDialog.ID_LAST + 45
            form.voidBetaUnifiedKw.setTarget(self)
            form.voidBetaUnifiedKw.setSelector(ID_VOID_BETA_UNIFIED)
            FXMAPFUNC(self, SEL_COMMAND, ID_VOID_BETA_UNIFIED, self.onVoidBetaUnifiedChanged)

            # Unified beta + split betas, all on a single row.
            HFrame_beta = FXHorizontalFrame(p=GroupBox_void_shape, opts=LAYOUT_FILL_X)
            FXLabel(p=HFrame_beta, text='beta (>0):', opts=JUSTIFY_LEFT)
            self.voidBetaValueSpinner = AFXFloatSpinner(p=HFrame_beta, ncols=8, labelText='', tgt=form.voidBetaValueKw, sel=0)
            self.voidBetaValueSpinner.setRange(0.01, 100.0)
            self.voidBetaValueSpinner.setIncrement(0.1)
            FXLabel(p=HFrame_beta, text='     beta (fiber-adjacent):', opts=JUSTIFY_LEFT)
            self.voidBetaFiberSpinner = AFXFloatSpinner(p=HFrame_beta, ncols=8, labelText='', tgt=form.voidBetaValueFiberKw, sel=0)
            self.voidBetaFiberSpinner.setRange(0.01, 100.0)
            self.voidBetaFiberSpinner.setIncrement(0.1)
            FXLabel(p=HFrame_beta, text='   beta (inter-matrix):', opts=JUSTIFY_LEFT)
            self.voidBetaMatrixSpinner = AFXFloatSpinner(p=HFrame_beta, ncols=8, labelText='', tgt=form.voidBetaValueMatrixKw, sel=0)
            self.voidBetaMatrixSpinner.setRange(0.01, 100.0)
            self.voidBetaMatrixSpinner.setIncrement(0.1)

            # Orientation
            HFrame_orient = FXHorizontalFrame(p=GroupBox_void_shape, opts=LAYOUT_FILL_X)
            FXLabel(p=HFrame_orient, text='Orientation:', opts=JUSTIFY_LEFT)
            self.voidBetaOrientRadio1 = FXRadioButton(p=HFrame_orient, text='Random SO(3)', tgt=form.voidBetaOrientationKw, sel=1)
            self.voidBetaOrientRadio2 = FXRadioButton(p=HFrame_orient, text='Orthogonal (X/Y/Z)', tgt=form.voidBetaOrientationKw, sel=2)

            # theta* (mean voids per fiber) -- informational; theta still drives final count
            HFrame_thetastar = FXHorizontalFrame(p=GroupBox_void_shape, opts=LAYOUT_FILL_X)
            self.voidThetaStarCheck = FXCheckButton(p=HFrame_thetastar,
                text='Use theta* (mean voids per fiber):', tgt=form.voidThetaStarActiveKw, sel=0)
            self.voidThetaStarSpinner = AFXFloatSpinner(p=HFrame_thetastar, ncols=8, labelText='', tgt=form.voidThetaStarKw, sel=0)
            self.voidThetaStarSpinner.setRange(0.0, 1000.0)
            self.voidThetaStarSpinner.setIncrement(0.1)
            ID_VOID_THETA_STAR_ACTIVE = AFXDataDialog.ID_LAST + 46
            form.voidThetaStarActiveKw.setTarget(self)
            form.voidThetaStarActiveKw.setSelector(ID_VOID_THETA_STAR_ACTIVE)
            FXMAPFUNC(self, SEL_COMMAND, ID_VOID_THETA_STAR_ACTIVE, self.onVoidThetaStarActiveChanged)

            FXLabel(p=GroupBox_void_shape, text='Note: beta=1 sphere, beta>1 prolate (X-axis), beta<1 oblate (Z-axis); see Help for details.', opts=JUSTIFY_LEFT)

            # Set initial state
            self._updateVoidBetaWidgets()

        def create_void_model_range_group():
            GroupBox = FXGroupBox(p=self.TabItem_4, text='Select Model Range for Void Insertion', opts=FRAME_GROOVE|LAYOUT_FILL_X)
            vertical_frame = FXVerticalFrame(p=GroupBox, opts=LAYOUT_FILL_X|LAYOUT_FILL_Y)
            
            h_frame_row1 = FXHorizontalFrame(p=vertical_frame, opts=LAYOUT_FILL_X)
            self.RadioButton_void_1 = FXRadioButton(p=h_frame_row1, text='Current Model', tgt=self.form.Model_range_voidKw, sel=1)
            self.RadioButton_void_2 = FXRadioButton(p=h_frame_row1, text='All Models*', tgt=self.form.Model_range_voidKw, sel=2)
            self.RadioButton_void_3 = FXRadioButton(p=h_frame_row1, text='Selected numbers**', tgt=self.form.Model_range_voidKw, sel=3)
            self.TextField_void = FXTextField(p=h_frame_row1, ncols=10, tgt=self.form.user_input_voidKw, sel=0)
            self.TextField_void.disable()
            self.ID_MODEL_RANGE_VOID_CHANGED = AFXDataDialog.ID_LAST + 41
            self.form.Model_range_voidKw.setTarget(self)
            self.form.Model_range_voidKw.setSelector(self.ID_MODEL_RANGE_VOID_CHANGED)
            FXMAPFUNC(self, SEL_COMMAND, self.ID_MODEL_RANGE_VOID_CHANGED, self.onModelRangeVoidChanged)
            FXLabel(p=vertical_frame, text='Note: * Void insertion applies to models with the same primary name.\n'
                                           '         ** use "-" for ranges and "," for specific values. E.g., 2, 4-11.', opts=JUSTIFY_LEFT)
        
        create_void_insertion_tab()
        
        #######################################################################
        # Fifth tab: Interface
        #######################################################################
        def create_interface_tab():
            tabItem = FXTabItem(p=self.TabBook_1, text='Interface', ic=None, opts=TAB_TOP_NORMAL)
            self.TabItem_3 = FXVerticalFrame(p=self.TabBook_1,
                opts=FRAME_RAISED|FRAME_THICK|LAYOUT_FILL_X,
                pl=DEFAULT_SPACING, pr=DEFAULT_SPACING,
                pt=DEFAULT_SPACING, pb=DEFAULT_SPACING)
            FXLabel(p=self.TabItem_3, text='Note: inserts a 0-thickness fibre-matrix interface. Choose its purpose below.', opts=JUSTIFY_LEFT)
            FXLabel(p=self.TabItem_3, text='Note: running this tab copies the selected model and builds the interface in the new model.', opts=JUSTIFY_LEFT)
            create_interface_purpose_group()
            create_interface_select_part_group()
            create_interface_material_group()
            create_initial_debonding_group()
            create_model_range_interface_group()

        def create_interface_purpose_group():
            GroupBox_ip = FXGroupBox(p=self.TabItem_3, text='Interface Purpose (Mechanical / Thermal)', opts=FRAME_GROOVE|LAYOUT_FILL_X)
            row = FXHorizontalFrame(p=GroupBox_ip, opts=LAYOUT_FILL_X)
            FXRadioButton(p=row, text='Mechanical: cohesive debonding (COH3D8)', tgt=form.interface_purposeKw, sel=1)
            FXRadioButton(p=row, text='Thermal: contact + gap conductance', tgt=form.interface_purposeKw, sel=2)
            krow = FXHorizontalFrame(p=GroupBox_ip, opts=LAYOUT_FILL_X)
            self.kapitzaField = AFXTextField(p=krow, ncols=14, labelText='Kapitza resistance R_K (thermal only):', tgt=form.kapitza_resistanceKw, sel=0)
            # Default purpose is Mechanical (1) -> Kapitza input is only relevant for Thermal (2),
            # so it starts disabled and is enabled only when the Thermal radio is selected.
            self.kapitzaField.disable()
            self.ID_INTERFACE_PURPOSE_CHANGED = AFXDataDialog.ID_LAST + 65
            form.interface_purposeKw.setTarget(self)
            form.interface_purposeKw.setSelector(self.ID_INTERFACE_PURPOSE_CHANGED)
            FXMAPFUNC(self, SEL_COMMAND, self.ID_INTERFACE_PURPOSE_CHANGED, self.onInterfacePurposeChanged)
            FXLabel(p=GroupBox_ip, text='Mechanical -> 0-thickness COHESIVE seam (COH3D8) that can debond. Pick a', opts=JUSTIFY_LEFT)
            FXLabel(p=GroupBox_ip, text='   cohesive MATERIAL below. For strength / damage / failure analysis.', opts=JUSTIFY_LEFT)
            FXLabel(p=GroupBox_ip, text='Thermal  -> surface-to-surface CONTACT with constant gap conductance', opts=JUSTIFY_LEFT)
            FXLabel(p=GroupBox_ip, text='   h = 1 / R_K (no cohesive elements, no material; the Material box is ignored).', opts=JUSTIFY_LEFT)
            FXLabel(p=GroupBox_ip, text='   For effective thermal-conductivity prediction.', opts=JUSTIFY_LEFT)
            FXLabel(p=GroupBox_ip, text='WARNING: an interface is built for ONE analysis type. Run a Mechanical', opts=JUSTIFY_LEFT)
            FXLabel(p=GroupBox_ip, text='   interface with the elastoplastic-interface module, a Thermal interface', opts=JUSTIFY_LEFT)
            FXLabel(p=GroupBox_ip, text='   with the thermal-conductivity module. Each analysis aborts on a mismatch.', opts=JUSTIFY_LEFT)

        def create_interface_select_part_group():
            GroupBox_16 = FXGroupBox(p=self.TabItem_3, text='Select Part', opts=FRAME_GROOVE|LAYOUT_FILL_X)
            frame = FXHorizontalFrame(GroupBox_16)
            
            self.RootComboBox_3 = AFXComboBox(p=frame, ncols=0, nvis=1, text='Model:', tgt=form.model_for_interfaceKw, sel=0)
            self.RootComboBox_3.setMaxVisible(10)

            names = mdb.models.keys()
            names.sort()
            for name in names:
                self.RootComboBox_3.appendItem(name)
            if not form.model_for_interfaceKw.getValue() in names:
                form.model_for_interfaceKw.setValue(names[0])
            msgCount = 16
            form.model_for_interfaceKw.setTarget(self)
            form.model_for_interfaceKw.setSelector(AFXDataDialog.ID_LAST+msgCount)
            msgHandler = str(self.__class__).split('.')[-1] + '.onComboBox_3PartsChanged'
            FXMAPFUNC(self, SEL_COMMAND, AFXDataDialog.ID_LAST + msgCount, getattr(self, 'onComboBox_3PartsChanged'))
            
            self.ComboBox_3 = AFXComboBox(p=frame, ncols=0, nvis=1, text='Part:', tgt=form.part_for_interfaceKw, sel=0)
            self.ComboBox_3.setMaxVisible(10)
            self.form = form
        
        def create_interface_material_group():
            GroupBox_63 = FXGroupBox(p=self.TabItem_3, text='Material for interface', opts=FRAME_GROOVE|LAYOUT_FILL_X)
            self.materialGroupBox = GroupBox_63   # kept so it can be greyed out for Thermal interfaces
            frame = FXHorizontalFrame(GroupBox_63)
        
            self.RootComboBox_63 = AFXComboBox(p=frame, ncols=0, nvis=1, text='Model:', tgt=form.model_for_interfaceKw, sel=0)
            self.RootComboBox_63.setMaxVisible(10)
        
            names = mdb.models.keys()
            names.sort()
            for name in names:
                self.RootComboBox_63.appendItem(name)
            if not form.model_for_interfaceKw.getValue() in names:
                form.model_for_interfaceKw.setValue(names[0])
            msgCount = 63
            msgID = AFXDataDialog.ID_LAST + msgCount
            form.model_for_interfaceKw.setTarget(self)
            form.model_for_interfaceKw.setSelector(msgID)
            FXMAPFUNC(self, SEL_COMMAND, msgID, self.onComboBox_63MaterialsChanged)
            self.ComboBox_63 = AFXComboBox(p=frame, ncols=0, nvis=1, text='Material:', tgt=form.interface_materialKw, sel=0)
            self.ComboBox_63.setMaxVisible(10)
            self.form = form

        def create_initial_debonding_group():
            GroupBox_64 = FXGroupBox(p=self.TabItem_3, text='Initial Debonding', opts=FRAME_GROOVE|LAYOUT_FILL_X)
            spinner = AFXFloatSpinner(p=GroupBox_64, ncols=6, labelText='Initial debonding ratio D (%):', tgt=form.interface_initial_debondingKw, sel=0)
            spinner.setRange(0.0, 100.0)
            spinner.setIncrement(0.01)
            FXLabel(p=GroupBox_64, text='D=0 means no artificial initial debonding.', opts=JUSTIFY_LEFT)
            FXLabel(p=GroupBox_64, text='For RVEs with voids, D includes the debonded fiber interface already replaced by voids.', opts=JUSTIFY_LEFT)
            FXLabel(p=GroupBox_64, text='Note: D is limited so that at least one bonded cohesive element is retained for each independent fiber geometry.', opts=JUSTIFY_LEFT)
        
        def create_model_range_interface_group():
            GroupBox_33 = FXGroupBox(p=self.TabItem_3, text='Select Model Range for Interface', opts=FRAME_GROOVE|LAYOUT_FILL_X)
            vertical_frame3 = FXVerticalFrame(p=GroupBox_33, opts=LAYOUT_FILL_X|LAYOUT_FILL_Y)
            
            h_frame_row1 = FXHorizontalFrame(p=vertical_frame3, opts=LAYOUT_FILL_X)
            self.RadioButton_1_interface = FXRadioButton(p=h_frame_row1, text='Current Model', tgt=self.form.Model_range_interfaceKw, sel=1)
            self.RadioButton_2_interface = FXRadioButton(p=h_frame_row1, text='All Models*', tgt=self.form.Model_range_interfaceKw, sel=2)
            self.RadioButton_3_interface = FXRadioButton(p=h_frame_row1, text='Selected numbers**', tgt=self.form.Model_range_interfaceKw, sel=3)
            self.TextField_interface = FXTextField(p=h_frame_row1, ncols=10, tgt=self.form.user_input_interfaceKw, sel=0)
            self.TextField_interface.disable()
            self.ID_MODEL_RANGE_interface_CHANGED = AFXDataDialog.ID_LAST + 33
            self.form.Model_range_interfaceKw.setTarget(self)
            self.form.Model_range_interfaceKw.setSelector(self.ID_MODEL_RANGE_interface_CHANGED)
            FXMAPFUNC(self, SEL_COMMAND, self.ID_MODEL_RANGE_interface_CHANGED, self.onModelRangeinterfaceChanged)
        
        create_interface_tab()
        
        #######################################################################
        # Sixth tab: Analysis
        #######################################################################
        def create_analysis_tab(self, form):
            tabItem = FXTabItem(p=self.TabBook_1, text='Analysis', ic=None, opts=TAB_TOP_NORMAL)
            self.TabItem_7 = FXVerticalFrame(p=self.TabBook_1,
                opts=FRAME_RAISED|FRAME_THICK|LAYOUT_FILL_X,
                pl=DEFAULT_SPACING, pr=DEFAULT_SPACING,
                pt=DEFAULT_SPACING, pb=DEFAULT_SPACING)
            
            create_elastic_properties_calculator(self, form)
            create_analysis_type_selector(self, form)
            create_analysis_params_panel(self, form)
            create_model_range_selection(self, form)
            
        def create_elastic_properties_calculator(self, form):
            HFrame_32 = FXHorizontalFrame(p=self.TabItem_7)
            l = FXLabel(p=HFrame_32, text='Elastic, CTE, Viscoelasticity, Elastoplasticity, Thermal conductivity', opts=JUSTIFY_LEFT)
            l.setFont(getAFXFont(FONT_BOLD))
            l = FXLabel(p=self.TabItem_7, text='Note: linking the easyPBC plug-in, consult the help manual.', opts=JUSTIFY_LEFT)

            GroupBox_38 = FXGroupBox(p=self.TabItem_7, text='Basic Information', opts=FRAME_GROOVE|LAYOUT_FILL_X)
            frame = FXHorizontalFrame(GroupBox_38)
            self.RootComboBox_13 = AFXComboBox(p=frame, ncols=0, nvis=1, text='Model:', tgt=form.model_for_analysisKw, sel=0)
            self.RootComboBox_13.setMaxVisible(10)
            names = mdb.models.keys()
            names.sort()
            for name in names:
                self.RootComboBox_13.appendItem(name)
            if not form.model_for_analysisKw.getValue() in names:
                form.model_for_analysisKw.setValue(names[0])
            
            msgCount = 10
            msgID = AFXDataDialog.ID_LAST + msgCount
            form.model_for_analysisKw.setTarget(self)
            form.model_for_analysisKw.setSelector(msgID)
            FXMAPFUNC(self, SEL_COMMAND, msgID, self.onComboBox_13PartsChanged)
            
            self.ComboBox_13 = AFXComboBox(p=frame, ncols=0, nvis=1, text='Part:', tgt=form.part_for_analysisKw, sel=0)
            self.ComboBox_13.setMaxVisible(10)
            HFrame_EL = FXHorizontalFrame(p=GroupBox_38)
            AFXTextField(p=HFrame_EL, ncols=12, labelText='Mapping accuracy *', tgt=form.meshsensKw, sel=0)
            AFXTextField(p=HFrame_EL, ncols=2, labelText='Number of CPUs to be used **', tgt=form.CPUKw, sel=0)
            l = FXLabel(p=GroupBox_38, text='*  Mesh mapping accuracy of opposite sides should be within the above value.', opts=JUSTIFY_LEFT)
            l = FXLabel(p=GroupBox_38, text='** If number of CPUs exceeds the available, all available CPUs will be used.', opts=JUSTIFY_LEFT)

            umatFrame = FXHorizontalFrame(p=GroupBox_38, opts=LAYOUT_FILL_X)
            FXLabel(p=umatFrame, text='UMAT Subroutine Selection:', opts=JUSTIFY_LEFT)
            umatFileHandler = UMATFileHandler(form, 'umatName', 'FOR files (*.for)')
            # UMAT input is optional but always available — applies to every analysis type.
            self.umatNameTextField = AFXTextField(p=umatFrame, ncols=20, labelText='', tgt=form.umatNameKw, sel=0, opts=AFXTEXTFIELD_STRING | LAYOUT_CENTER_Y)
            icon = afxGetIcon('fileOpen', AFX_ICON_SMALL)
            self.umatNameButton = FXButton(p=umatFrame, text='', ic=icon, tgt=umatFileHandler, sel=AFXMode.ID_ACTIVATE, opts=BUTTON_NORMAL | LAYOUT_CENTER_Y, pl=1, pr=1, pt=1, pb=1)
        
        def create_analysis_type_selector(self, form):
            GroupBox_type = FXGroupBox(p=self.TabItem_7, text='Analysis Type', opts=FRAME_GROOVE | LAYOUT_FILL_X)
            self.ID_ANALYSIS_TYPE_CHANGED = AFXDataDialog.ID_LAST + 50
            form.analysisTypeKw.setTarget(self)
            form.analysisTypeKw.setSelector(self.ID_ANALYSIS_TYPE_CHANGED)
            FXMAPFUNC(self, SEL_COMMAND, self.ID_ANALYSIS_TYPE_CHANGED, self.onAnalysisTypeChanged)
            columnsFrame = FXHorizontalFrame(p=GroupBox_type, opts=LAYOUT_FILL_X)
            col1 = FXVerticalFrame(p=columnsFrame, opts=LAYOUT_FILL_X)
            col2 = FXVerticalFrame(p=columnsFrame, opts=LAYOUT_FILL_X)
            col3 = FXVerticalFrame(p=columnsFrame, opts=LAYOUT_FILL_X)
            FXRadioButton(p=col1, text='Elastic and CTE',                 tgt=form.analysisTypeKw, sel=1)
            FXRadioButton(p=col1, text='Thermal Conductivity',            tgt=form.analysisTypeKw, sel=5)
            FXRadioButton(p=col2, text='Elastoplastic (Uniaxial)',        tgt=form.analysisTypeKw, sel=4)
            FXRadioButton(p=col2, text='Elastoplastic (Biaxial)',         tgt=form.analysisTypeKw, sel=6)
            FXRadioButton(p=col3, text='Viscoelastic (Time domain)',      tgt=form.analysisTypeKw, sel=2)
            FXRadioButton(p=col3, text='Viscoelastic (Frequency domain)', tgt=form.analysisTypeKw, sel=3)
            warningFrame = FXVerticalFrame(p=GroupBox_type, opts=LAYOUT_FILL_X)
            self.analysisTemperatureWarningLabel1 = FXLabel(
                p=warningFrame,
                text='Important: For all temperature-related analyses, plugin inputs must use Celsius (\u00b0C).',
                opts=JUSTIFY_LEFT
            )
            self.analysisTemperatureWarningLabel1.setFont(getAFXFont(FONT_BOLD))
            self.analysisTemperatureWarningLabel1.setTextColor(FXRGB(255, 0, 0))
            self.analysisTemperatureWarningLabel2 = FXLabel(
                p=warningFrame,
                text='Material-property definitions must use Kelvin (K), and all reported output temperatures are in Celsius (\u00b0C).',
                opts=JUSTIFY_LEFT
            )
            self.analysisTemperatureWarningLabel2.setFont(getAFXFont(FONT_BOLD))
            self.analysisTemperatureWarningLabel2.setTextColor(FXRGB(255, 0, 0))
        
        def create_analysis_params_panel(self, form):
            GroupBox_params = FXGroupBox(p=self.TabItem_7, text='Analysis Parameters', opts=FRAME_GROOVE | LAYOUT_FILL_X)
        
            # --- Panel 0: nothing selected ---
            self.paramPanelNone = FXVerticalFrame(p=GroupBox_params, opts=LAYOUT_FILL_X)
            FXLabel(p=self.paramPanelNone, text='Please select an analysis type above.', opts=JUSTIFY_CENTER_X | LAYOUT_CENTER_X)
        
            # --- Panel 1: Elastic and CTE ---
            self.paramPanelElastic = FXVerticalFrame(p=GroupBox_params, opts=LAYOUT_FILL_X)
            HFrame_elastic_temp_points = FXHorizontalFrame(p=self.paramPanelElastic, opts=LAYOUT_FILL_X)
            self.elasticTemperaturePointsTextField = AFXTextField(
                p=HFrame_elastic_temp_points, ncols=26,
                labelText='Temperature Points (\u00b0C):',
                tgt=form.elastic_temperature_pointsKw, sel=0
            )
            HFrame_E = FXHorizontalFrame(p=self.paramPanelElastic)
            FXCheckButton(p=HFrame_E, text='E11(X) ', tgt=form.E11Kw, sel=0)
            FXCheckButton(p=HFrame_E, text='E22(Y) ', tgt=form.E22Kw, sel=0)
            FXCheckButton(p=HFrame_E, text='E33(Z) ', tgt=form.E33Kw, sel=0)
            FXCheckButton(p=HFrame_E, text='G12(XY)', tgt=form.G12Kw, sel=0)
            FXCheckButton(p=HFrame_E, text='G13(XZ)', tgt=form.G13Kw, sel=0)
            FXCheckButton(p=HFrame_E, text='G23(YZ)', tgt=form.G23Kw, sel=0)
            HFrame_PBC_E = FXHorizontalFrame(p=self.paramPanelElastic)
            FXCheckButton(p=HFrame_PBC_E, text='Only Corresponding PBC', tgt=form.onlyPBCKw, sel=0)
            HFrame_CTE = FXHorizontalFrame(p=self.paramPanelElastic)
            self.import_CTECheckBox = FXCheckButton(p=HFrame_CTE, text='Coefficient of Thermal Expansion (CTE)', tgt=form.CTEKw, sel=0)
            self.ID_IMPORT_CTE_CHANGED = AFXDataDialog.ID_LAST + 52
            form.CTEKw.setTarget(self)
            form.CTEKw.setSelector(self.ID_IMPORT_CTE_CHANGED)
            FXMAPFUNC(self, SEL_COMMAND, self.ID_IMPORT_CTE_CHANGED, self.onImportCTEChanged)
            # CTE temperature inputs — disabled until the CTE checkbox is ticked
            HFrame_temp = FXHorizontalFrame(p=self.paramPanelElastic)
            self.intempTextFieldElastic = AFXTextField(p=HFrame_temp, ncols=6, labelText='Initial Temperature (\u00b0C)', tgt=form.intempKw, sel=0)
            self.intempTextFieldElastic.disable()
            self.fntempTextFieldElastic = AFXTextField(p=HFrame_temp, ncols=6, labelText='Final Temperature (\u00b0C)', tgt=form.fntempKw, sel=0)
            self.fntempTextFieldElastic.disable()
            self.segmentTextFieldElastic = AFXTextField(p=HFrame_temp, ncols=6, labelText='Segment', tgt=form.segmentKw, sel=0)
            self.segmentTextFieldElastic.disable()
        
            # --- Panel 2: Viscoelastic Time-domain ---
            self.paramPanelViscTime = FXVerticalFrame(p=GroupBox_params, opts=LAYOUT_FILL_X)
            tempFrame_VT = FXHorizontalFrame(p=self.paramPanelViscTime, opts=LAYOUT_FILL_X)
            self.viscTimeTemperaturePointsTextField = AFXTextField(
                p=tempFrame_VT, ncols=26,
                labelText='Temperature Points (\u00b0C):',
                tgt=form.visco_temperature_pointsKw, sel=0
            )
            HFrame_VT = FXHorizontalFrame(p=self.paramPanelViscTime)
            FXCheckButton(p=HFrame_VT, text='E11(X) ', tgt=form.E11Kw, sel=0)
            FXCheckButton(p=HFrame_VT, text='E22(Y) ', tgt=form.E22Kw, sel=0)
            FXCheckButton(p=HFrame_VT, text='E33(Z) ', tgt=form.E33Kw, sel=0)
            FXCheckButton(p=HFrame_VT, text='G12(XY)', tgt=form.G12Kw, sel=0)
            FXCheckButton(p=HFrame_VT, text='G13(XZ)', tgt=form.G13Kw, sel=0)
            FXCheckButton(p=HFrame_VT, text='G23(YZ)', tgt=form.G23Kw, sel=0)
            timeParamsFrame_VT = FXHorizontalFrame(p=self.paramPanelViscTime, opts=LAYOUT_FILL_X)
            relaxFrame_VT = FXHorizontalFrame(p=timeParamsFrame_VT, opts=LAYOUT_FILL_X)
            FXLabel(p=relaxFrame_VT, text='Relaxation Total Time (seconds):', opts=JUSTIFY_LEFT)
            self.relaxationTimeTextField = AFXFloatSpinner(p=relaxFrame_VT, ncols=10, labelText='', tgt=form.relaxationTimeKw, sel=0)
            self.relaxationTimeTextField.setRange(0.01, 1000000.00)
            incFrame_VT = FXHorizontalFrame(p=timeParamsFrame_VT, opts=LAYOUT_FILL_X)
            FXLabel(p=incFrame_VT, text='Number of Time Points:', opts=JUSTIFY_LEFT)
            self.time_pointTextField = AFXSpinner(p=incFrame_VT, ncols=10, labelText='', tgt=form.time_pointKw, sel=0)
            self.time_pointTextField.setRange(1, 1000000)
        
            # --- Panel 3: Viscoelastic Frequency-domain ---
            self.paramPanelViscFreq = FXVerticalFrame(p=GroupBox_params, opts=LAYOUT_FILL_X)
            tempFrame_VF = FXHorizontalFrame(p=self.paramPanelViscFreq, opts=LAYOUT_FILL_X)
            self.viscFreqTemperaturePointsTextField = AFXTextField(
                p=tempFrame_VF, ncols=26,
                labelText='Temperature Points (\u00b0C):',
                tgt=form.visco_temperature_pointsKw, sel=0
            )
            HFrame_VF = FXHorizontalFrame(p=self.paramPanelViscFreq)
            FXCheckButton(p=HFrame_VF, text='E11*(X) ', tgt=form.E11Kw, sel=0)
            FXCheckButton(p=HFrame_VF, text='E22*(Y) ', tgt=form.E22Kw, sel=0)
            FXCheckButton(p=HFrame_VF, text='E33*(Z) ', tgt=form.E33Kw, sel=0)
            FXCheckButton(p=HFrame_VF, text='G12*(XY)', tgt=form.G12Kw, sel=0)
            FXCheckButton(p=HFrame_VF, text='G13*(XZ)', tgt=form.G13Kw, sel=0)
            FXCheckButton(p=HFrame_VF, text='G23*(YZ)', tgt=form.G23Kw, sel=0)
            
            colFrame = FXHorizontalFrame(p=self.paramPanelViscFreq, opts=LAYOUT_FILL_X)
            
            leftAligner = AFXVerticalAligner(p=colFrame, opts=LAYOUT_FILL_X)
            lowerFrame = FXHorizontalFrame(p=leftAligner)
            FXLabel(p=lowerFrame, text='Lower Frequency (Hz):', opts=JUSTIFY_LEFT)
            self.lowerFreqTextField = AFXFloatSpinner(p=lowerFrame, ncols=10, labelText='', tgt=form.lowerFreqKw, sel=0)
            self.lowerFreqTextField.setRange(1e-6, 1e16)
            numPtFrame = FXHorizontalFrame(p=leftAligner)
            FXLabel(p=numPtFrame, text='Number of Points:', opts=JUSTIFY_LEFT)
            self.numPointsTextField = AFXSpinner(p=numPtFrame, ncols=10, labelText='', tgt=form.numPointsKw, sel=0)
            self.numPointsTextField.setRange(1, 1000000)
            
            rightAligner = AFXVerticalAligner(p=colFrame, opts=LAYOUT_FILL_X)
            upperFrame = FXHorizontalFrame(p=rightAligner)
            FXLabel(p=upperFrame, text='Upper Frequency (Hz):', opts=JUSTIFY_LEFT)
            self.upperFreqTextField = AFXFloatSpinner(p=upperFrame, ncols=10, labelText='', tgt=form.upperFreqKw, sel=0)
            self.upperFreqTextField.setRange(1e-6, 1e16)
            biasFrame = FXHorizontalFrame(p=rightAligner)
            FXLabel(p=biasFrame, text='Bias (Effective when >3):', opts=JUSTIFY_LEFT)
            self.biasTextField = AFXFloatSpinner(p=biasFrame, ncols=10, labelText='', tgt=form.biasKw, sel=0)
            self.biasTextField.setRange(0.0, 10000.0)
        
            # --- Panel 4: Elastoplastic (uniaxial / biaxial + multi-temperature) ---
            self.paramPanelElastoplastic = FXVerticalFrame(p=GroupBox_params, opts=LAYOUT_FILL_X)

            # Message IDs for the EP UI toggles. Uniaxial / Biaxial is now
            # decided by the Analysis-type radio (4 / 6), so the old loading-
            # mode toggle has been retired.
            self.ID_EP_SINGLE_LOAD_CHANGED    = AFXDataDialog.ID_LAST + 61
            self.ID_EP_BIAXIAL_COMBO_CHANGED  = AFXDataDialog.ID_LAST + 62
            FXMAPFUNC(self, SEL_COMMAND, self.ID_EP_SINGLE_LOAD_CHANGED,   self.onElastoplasticSingleLoadChanged)
            FXMAPFUNC(self, SEL_COMMAND, self.ID_EP_BIAXIAL_COMBO_CHANGED, self.onElastoplasticBiaxialComboChanged)

            for keyword in (
                form.epUseStrain11Kw, form.epUseStrain22Kw, form.epUseStrain33Kw,
                form.epUseShear12Kw,  form.epUseShear13Kw,  form.epUseShear23Kw,
            ):
                keyword.setTarget(self)
                keyword.setSelector(self.ID_EP_SINGLE_LOAD_CHANGED)
            form.epBiaxialComboKw.setTarget(self)
            form.epBiaxialComboKw.setSelector(self.ID_EP_BIAXIAL_COMBO_CHANGED)

            epTemperatureFrame = FXHorizontalFrame(p=self.paramPanelElastoplastic, opts=LAYOUT_FILL_X)
            self.epTemperaturePointsTextField = AFXTextField(
                p=epTemperatureFrame, ncols=18,
                labelText='Temperature Points (\u00b0C):',
                tgt=form.epTemperaturePointsKw, sel=0
            )

            # Uniaxial 6 (checkbox + Max Strain field) pairs in two rows
            self.epSingleAxisFrame = FXVerticalFrame(p=self.paramPanelElastoplastic, opts=LAYOUT_FILL_X)
            self.epSingleAxisFields = []
            singleAxisLoadItems = (
                ('Strain11', form.epUseStrain11Kw, form.epStrainXKw),
                ('Strain22', form.epUseStrain22Kw, form.epStrainYKw),
                ('Strain33', form.epUseStrain33Kw, form.epStrainZKw),
                ('Shear12',  form.epUseShear12Kw,  form.epShearXYKw),
                ('Shear13',  form.epUseShear13Kw,  form.epShearZXKw),
                ('Shear23',  form.epUseShear23Kw,  form.epShearYZKw),
            )
            for rowStart in (0, 3):
                row = FXHorizontalFrame(p=self.epSingleAxisFrame, opts=LAYOUT_FILL_X)
                for loadText, useKeyword, valueKeyword in singleAxisLoadItems[rowStart:rowStart + 3]:
                    itemFrame = FXHorizontalFrame(p=row)
                    FXCheckButton(p=itemFrame, text=loadText, tgt=useKeyword, sel=0)
                    field = AFXTextField(p=itemFrame, ncols=8, labelText='', tgt=valueKeyword, sel=0)
                    self.epSingleAxisFields.append((useKeyword, field))

            # Biaxial: combo of 15 pairs + two Max-Strain fields
            self.epBiaxialFrame = FXVerticalFrame(p=self.paramPanelElastoplastic, opts=LAYOUT_FILL_X)
            biaxialComboFrame = FXHorizontalFrame(p=self.epBiaxialFrame, opts=LAYOUT_FILL_X)
            self.epBiaxialComboBox = AFXComboBox(
                p=biaxialComboFrame, ncols=18, nvis=12,
                text='Biaxial Pair:', tgt=form.epBiaxialComboKw, sel=0
            )
            self.epBiaxialComboBox.setMaxVisible(15)
            for pairText in (
                'Strain11-Strain22', 'Strain11-Strain33', 'Strain11-Shear12', 'Strain11-Shear13', 'Strain11-Shear23',
                'Strain22-Strain33', 'Strain22-Shear12',  'Strain22-Shear13', 'Strain22-Shear23',
                'Strain33-Shear12',  'Strain33-Shear13',  'Strain33-Shear23',
                'Shear12-Shear13',   'Shear12-Shear23',   'Shear13-Shear23',
            ):
                self.epBiaxialComboBox.appendItem(pairText)
            self.epBiaxialValue1Label     = FXLabel(p=biaxialComboFrame, text='Load 1 Max Strain:', opts=JUSTIFY_LEFT)
            self.epBiaxialValue1TextField = AFXTextField(p=biaxialComboFrame, ncols=10, labelText='', tgt=form.epBiaxialValue1Kw, sel=0)
            self.epBiaxialValue2Label     = FXLabel(p=biaxialComboFrame, text='Load 2 Max Strain:', opts=JUSTIFY_LEFT)
            self.epBiaxialValue2TextField = AFXTextField(p=biaxialComboFrame, ncols=10, labelText='', tgt=form.epBiaxialValue2Kw, sel=0)

            bottomRowFrame_EP = FXHorizontalFrame(p=self.paramPanelElastoplastic, opts=LAYOUT_FILL_X)
            self.epLargeDeformationCheckBox = FXCheckButton(
                p=bottomRowFrame_EP,
                text='Nlgeom',
                tgt=form.epLargeDeformationKw, sel=0,
                opts=ICON_BEFORE_TEXT | JUSTIFY_NORMAL | LAYOUT_CENTER_Y
            )
            self.epUnsymmetricCheckBox = FXCheckButton(
                p=bottomRowFrame_EP,
                text='Unsymmetric matrix storage (UMAT)',
                tgt=form.epUnsymmetricSolverKw, sel=0,
                opts=ICON_BEFORE_TEXT | JUSTIFY_NORMAL | LAYOUT_CENTER_Y
            )
            self.epFieldOutputTextField = AFXTextField(
                p=bottomRowFrame_EP, ncols=5,
                labelText='Field-output frames:', tgt=form.field_output_intervalsKw, sel=0,
                opts=AFXTEXTFIELD_STRING | LAYOUT_CENTER_Y
            )
            self.epStabilizeMagnitudeTextField = AFXTextField(
                p=bottomRowFrame_EP, ncols=8,
                labelText='Stabilize magnitude (DEF):', tgt=form.stabilization_magnitudeKw, sel=0,
                opts=AFXTEXTFIELD_STRING | LAYOUT_CENTER_Y
            )

            # Analysis procedure (Step type) selector.  Bound to the integer
            # keyword epAnalysisProcedure: the AFXComboBox sets the keyword to
            # the selected item's 0-based index, so item 0 -> *Static,
            # item 1 -> *Dynamic QUASI-STATIC.  Order must match the kernel
            # mapping in RVE_Builder_UDFRPs.Analysis (1 == QUASI_STATIC_DYNAMIC).
            procRowFrame_EP = FXHorizontalFrame(p=self.paramPanelElastoplastic, opts=LAYOUT_FILL_X)
            self.epAnalysisProcedureComboBox = AFXComboBox(
                p=procRowFrame_EP, ncols=0, nvis=2,
                text='Analysis procedure:', tgt=form.epAnalysisProcedureKw, sel=0
            )
            self.epAnalysisProcedureComboBox.appendItem('Static + energy stabilization')
            self.epAnalysisProcedureComboBox.appendItem('Quasi-static implicit dynamics')
            self.epAnalysisProcedureComboBox.setMaxVisible(2)

            FXLabel(
                p=self.paramPanelElastoplastic,
                text='Negative = compression. Strain11/22/33 accept one or two comma-separated values; shear takes one.',
                opts=JUSTIFY_LEFT
            )
            FXLabel(
                p=self.paramPanelElastoplastic,
                text='Field-output frames: 0 = every increment. Stabilize magnitude: raise if the run aborts at minInc.',
                opts=JUSTIFY_LEFT
            )
            FXLabel(
                p=self.paramPanelElastoplastic,
                text='Analysis procedure: Static is the Melro static curve (UMAT IDMTAN=0). Quasi-static dynamics adds inertia to push through near-zero-force first-yield/softening stalls.',
                opts=JUSTIFY_LEFT
            )

            # --- Panel 5: Thermal Conductivity ---
            self.paramPanelThermal = FXVerticalFrame(p=GroupBox_params, opts=LAYOUT_FILL_X)
            HFrame_TC_temp = FXHorizontalFrame(p=self.paramPanelThermal)
            self.intempTextFieldThermal = AFXTextField(p=HFrame_TC_temp, ncols=6, labelText='Initial Temperature (\u00b0C)', tgt=form.intempKw, sel=0)
            self.fntempTextFieldThermal = AFXTextField(p=HFrame_TC_temp, ncols=6, labelText='Final Temperature (\u00b0C)', tgt=form.fntempKw, sel=0)
            self.segmentTextFieldThermal = AFXTextField(p=HFrame_TC_temp, ncols=6, labelText='Segment', tgt=form.segmentKw, sel=0)
            HFrame_TC = FXHorizontalFrame(p=self.paramPanelThermal)
            FXCheckButton(p=HFrame_TC, text='K11, K12, K13(X) ', tgt=form.K11Kw, sel=0)
            FXCheckButton(p=HFrame_TC, text='K21, K22, K23(Y) ', tgt=form.K22Kw, sel=0)
            FXCheckButton(p=HFrame_TC, text='K31, K32, K33(Z) ', tgt=form.K33Kw, sel=0)
            FXCheckButton(p=HFrame_TC, text='Only Corresponding PBC', tgt=form.onlyPBCKw, sel=0)
            
            self.paramPanelNone.show()
            self.paramPanelElastic.hide()
            self.paramPanelViscTime.hide()
            self.paramPanelViscFreq.hide()
            self.paramPanelElastoplastic.hide()
            self.paramPanelThermal.hide()
        
        def create_model_range_selection(self, form):
            GroupBox_42 = FXGroupBox(p=self.TabItem_7, text='Select Model Range for Analysis', opts=FRAME_GROOVE|LAYOUT_FILL_X)
            vertical_frame = FXVerticalFrame(p=GroupBox_42, opts=LAYOUT_FILL_X|LAYOUT_FILL_Y)
            
            h_frame_row1 = FXHorizontalFrame(p=vertical_frame, opts=LAYOUT_FILL_X)
            self.RadioButton_1_analysis = FXRadioButton(p=h_frame_row1, text='Current Model', tgt=self.form.Model_range_analysisKw, sel=1)
            self.RadioButton_2_analysis = FXRadioButton(p=h_frame_row1, text='All Models*', tgt=self.form.Model_range_analysisKw, sel=2)
            self.RadioButton_3_analysis = FXRadioButton(p=h_frame_row1, text='Selected numbers**', tgt=self.form.Model_range_analysisKw, sel=3)
            self.TextField_analysis = FXTextField(p=h_frame_row1, ncols=10, tgt=self.form.user_input_analysisKw, sel=0)
            self.TextField_analysis.disable()
            self.ID_MODEL_RANGE_ANALYSIS_CHANGED = AFXDataDialog.ID_LAST + 23
            self.form.Model_range_analysisKw.setTarget(self)
            self.form.Model_range_analysisKw.setSelector(self.ID_MODEL_RANGE_ANALYSIS_CHANGED)
            FXMAPFUNC(self, SEL_COMMAND, self.ID_MODEL_RANGE_ANALYSIS_CHANGED, self.onModelRangeAnalysisChanged)
            FXLabel(p=vertical_frame, text='Note: All Models and Selected numbers require the selected model name to end with _number.', opts=JUSTIFY_LEFT)
        
        create_analysis_tab(self, form)
    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def onTabSwitched(self, sender, sel, ptr):
        # Track active tab and refresh the Analysis sub-panels when the user
        # navigates to that tab (mirrors RVE_Builder_fillers behavior).
        self.currentTabIndex = self.TabBook_1.getCurrent()
        try:
            self.onImportCTEChanged(None, None, None)
            self.TabBook_1.recalc()
            self.resize(self.getDefaultWidth(), self.getDefaultHeight())
        except:
            pass
        return 1

    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def onAlgorithmChanged(self, sender, sel, ptr, *args):
        self.noAlgorithmSelectedFrame.hide()
        self.baseParamMonteCarloFrame.hide()
        self.baseParamRSEFrame.hide()
        self.baseParamUserCoordinatesFrame.hide()
        
        if self.algorithmKw.getValue() == 1:
            self.baseParamMonteCarloFrame.show()
        elif self.algorithmKw.getValue() == 2:
            self.baseParamRSEFrame.show()
        elif self.algorithmKw.getValue() == 3:
            self.baseParamUserCoordinatesFrame.show()
        elif self.algorithmKw.getValue() == 0:
            self.noAlgorithmSelectedFrame.show()
            
        self.baseParamMonteCarloFrame.getParent().recalc()
        return 0
    
    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def onModelRangeinterfaceChanged(self, sender, sel, ptr, *args):
        if self.form.Model_range_interfaceKw.getValue() == 3:
            self.TextField_interface.enable()
        else:
            self.TextField_interface.disable()
        return 1
    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def onInterfacePurposeChanged(self, sender, sel, ptr, *args):
        # Thermal (2): Kapitza input active, interface-material box greyed out
        # (thermal interfaces ignore the cohesive material).
        # Mechanical (1): the reverse.
        try:
            is_thermal = (self.form.interface_purposeKw.getValue() == 2)
            if is_thermal:
                self.kapitzaField.enable()
            else:
                self.kapitzaField.disable()
            for widget in (getattr(self, 'materialGroupBox', None),
                           getattr(self, 'RootComboBox_63', None),
                           getattr(self, 'ComboBox_63', None)):
                if widget is None:
                    continue
                if is_thermal:
                    widget.disable()
                else:
                    widget.enable()
        except Exception:
            pass
        return 1
    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def toggle_text_field(sender, sel, ptr):
        if RadioButton_3.getCheck():
            TextField.enable()
        else:
            TextField.disable()
    
    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def show(self):

        AFXDataDialog.show(self)

        # Sync the interface-material / Kapitza enabled-state with the current
        # interface purpose, so a remembered Thermal selection greys the
        # material box immediately (the handler otherwise only fires on change).
        try:
            self.onInterfacePurposeChanged(None, 0, None)
        except Exception:
            pass

        self.currentModelName = getCurrentContext()['modelName']
        self.form.modelNameKw.setValue(self.currentModelName)
        #mdb.models[self.currentModelName].parts.registerQuery(self.updateComboBox_9Parts)
        
        self.mechanicalOptionsFrame.show()
        self.thermalOptionsFrame.hide()
        self.mechanicalOptionsFrame.getParent().recalc()
        
        self.form.model_for_materialKw.setValue(self.currentModelName)
        mdb.models[self.currentModelName].materials.registerQuery(self.updateComboBox_11Materials)

        self.form.model_for_materialKw.setValue(self.currentModelName)
        mdb.models[self.currentModelName].materials.registerQuery(self.updateComboBox_10Materials)

        self.form.model_for_analysisKw.setValue(self.currentModelName)
        mdb.models[self.currentModelName].parts.registerQuery(self.updateComboBox_13Parts)
        
        self.form.model_for_interfaceKw.setValue(self.currentModelName)
        mdb.models[self.currentModelName].parts.registerQuery(self.updateComboBox_3Parts)
        self.updateComboBox_3Parts()
        
        self.form.model_for_interfaceKw.setValue(self.currentModelName)
        mdb.models[self.currentModelName].materials.registerQuery(self.updateComboBox_63)
        self.updateComboBox_63()
        
        self.form.model_for_voidKw.setValue(self.currentModelName)
        mdb.models[self.currentModelName].parts.registerQuery(self.updateComboBox_void_parts)
        self.updateComboBox_void_parts()
        
        # Void distribution
        if self.form.void_distribution_methodKw.getValue() == 2:
            self.voidDistValueSpinner.enable()
        else:
            self.voidDistValueSpinner.disable()
        
        # Void size
        if self.form.void_size_methodKw.getValue() == 2:
            self.voidThetaSpinner.enable()
        else:
            self.voidThetaSpinner.disable()
        
        # Priority
        self.updatePriorityState()
        # Refresh shape-factor widget state.
        self._updateVoidBetaWidgets()
        # Trigger Analysis-tab refresh — onAnalysisTypeChanged itself toggles UMAT availability.
        self.onAnalysisTypeChanged(None, None, None)
    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def hide(self):

        AFXDataDialog.hide(self)

        #mdb.models[self.currentModelName].parts.unregisterQuery(self.updateComboBox_9Parts)

        mdb.models[self.currentModelName].materials.unregisterQuery(self.updateComboBox_11Materials)

        mdb.models[self.currentModelName].materials.unregisterQuery(self.updateComboBox_10Materials)

        mdb.models[self.currentModelName].parts.unregisterQuery(self.updateComboBox_17Parts)

        mdb.models[self.currentModelName].parts.unregisterQuery(self.updateComboBox_13Parts)

        mdb.models[self.currentModelName].parts.unregisterQuery(self.updateComboBox_3Parts)

        mdb.models[self.currentModelName].materials.unregisterQuery(self.updateComboBox_63)

        mdb.models[self.currentModelName].parts.unregisterQuery(self.updateComboBox_void_parts)
    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    '''def onComboBox_9PartsChanged(self, sender, sel, ptr, *args):

        self.updateComboBox_9Parts()
        return 1'''
    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def onComboBox_3PartsChanged(self, sender, sel, ptr, *args):

        self.updateComboBox_3Parts()
        return 1
    
    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def updateComboBox_3Parts(self):
        modelName = self.form.model_for_interfaceKw.getValue()
        self.ComboBox_3.clearItems()
        names = mdb.models[modelName].parts.keys()
        names.sort()
        for name in names:
            self.ComboBox_3.appendItem(name)
        if names:
            if not self.form.part_for_interfaceKw.getValue() in names:
                self.form.part_for_interfaceKw.setValue(names[0])
        else:
            self.form.part_for_interfaceKw.setValue('')

        self.resize(self.getDefaultWidth(), self.getDefaultHeight())

    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    '''def updateComboBox_9Parts(self):

        modelName = self.form.modelNameKw.getValue()
        
        self.ComboBox_9.clearItems()
        names = mdb.models[modelName].parts.keys()
        names.sort()
        for name in names:
            self.ComboBox_9.appendItem(name)
        if names:
            if not self.form.partNameKw.getValue() in names:
                self.form.partNameKw.setValue(names[0])
        else:
            self.form.partNameKw.setValue('')

        self.resize(self.getDefaultWidth(), self.getDefaultHeight())'''
    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def onComboBox_11MaterialsChanged(self, sender, sel, ptr, *args):

        self.updateComboBox_11Materials()
        return 1

    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def updateComboBox_11Materials(self):

        modelName = self.form.model_for_materialKw.getValue()
        
        self.ComboBox_11.clearItems()
        names = mdb.models[modelName].materials.keys()
        names.sort()
        for name in names:
            self.ComboBox_11.appendItem(name)
        if names:
            if not self.form.fiber_materialKw.getValue() in names:
                self.form.fiber_materialKw.setValue(names[0])
        else:
            self.form.fiber_materialKw.setValue('')

        self.resize(self.getDefaultWidth(), self.getDefaultHeight())

    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def onComboBox_10MaterialsChanged(self, sender, sel, ptr, *args):

        self.updateComboBox_10Materials()
        return 1

    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def updateComboBox_10Materials(self):

        modelName = self.form.model_for_materialKw.getValue()
        
        self.ComboBox_10.clearItems()
        names = mdb.models[modelName].materials.keys()
        names.sort()
        for name in names:
            self.ComboBox_10.appendItem(name)
        if names:
            if not self.form.matrix_materialKw.getValue() in names:
                self.form.matrix_materialKw.setValue(names[0])
        else:
            self.form.matrix_materialKw.setValue('')

        self.resize(self.getDefaultWidth(), self.getDefaultHeight())

    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def onComboBox_17PartsChanged(self, sender, sel, ptr, *args):

        self.updateComboBox_17Parts()
        return 1

    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def updateComboBox_17Parts(self):

        modelName = self.form.modelName6Kw.getValue()
        
        self.ComboBox_17.clearItems()
        names = mdb.models[modelName].parts.keys()
        names.sort()
        for name in names:
            self.ComboBox_17.appendItem(name)
        if names:
            if not self.form.PartName_compositeKw.getValue() in names:
                self.form.PartName_compositeKw.setValue(names[0])
        else:
            self.form.PartName_compositeKw.setValue('')

        self.resize(self.getDefaultWidth(), self.getDefaultHeight())

    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def onComboBox_13PartsChanged(self, sender, sel, ptr, *args):

        self.updateComboBox_13Parts()
        return 1

    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def onModelRangeMaterialChanged(self, sender, sel, ptr, *args):
        if self.form.Model_range_materialKw.getValue() == 3:
            self.TextField_material.enable()
        else:
            self.TextField_material.disable()
        return 1
    
    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def onModelRangeAnalysisChanged(self, sender, sel, ptr, *args):
        if self.form.Model_range_analysisKw.getValue() == 3:
            self.TextField_analysis.enable()
        else:
            self.TextField_analysis.disable()
        return 1

    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def onComboBox_63Changed(self, sender, sel, ptr, *args):
        self.updateComboBox_63()
        return 1

    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def updateComboBox_63(self):
        modelName = self.form.model_for_interfaceKw.getValue()
    
        self.ComboBox_63.clearItems()
        names = mdb.models[modelName].materials.keys()
        names.sort()
        for name in names:
            self.ComboBox_63.appendItem(name)
        if names:
            if not self.form.interface_materialKw.getValue() in names:
                self.form.interface_materialKw.setValue(names[0])
        else:
            self.form.interface_materialKw.setValue('')
    
        self.resize(self.getDefaultWidth(), self.getDefaultHeight())

    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def onComboBox_63MaterialsChanged(self, sender, sel, ptr, *args):
        self.updateComboBox_63Materials()
        return 1
    
    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def updateComboBox_63Materials(self):
        modelName = self.form.model_for_interfaceKw.getValue()
        self.ComboBox_63.clearItems()
        names = mdb.models[modelName].materials.keys()
        names.sort()
        for name in names:
            self.ComboBox_63.appendItem(name)
        if names:
            if not self.form.interface_materialKw.getValue() in names:
                self.form.interface_materialKw.setValue(names[0])
        else:
            self.form.interface_materialKw.setValue('')
        self.resize(self.getDefaultWidth(), self.getDefaultHeight())

    def onComboBox_void_modelChanged(self, sender, sel, ptr, *args):
        self.updateComboBox_void_parts()
        return 1
    
    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def updateComboBox_void_parts(self):
        modelName = self.form.model_for_voidKw.getValue()
        self.ComboBox_void_part.clearItems()
        names = mdb.models[modelName].parts.keys()
        names.sort()
        for name in names:
            self.ComboBox_void_part.appendItem(name)
        if names:
            if not self.form.part_for_voidKw.getValue() in names:
                self.form.part_for_voidKw.setValue(names[0])
        else:
            self.form.part_for_voidKw.setValue('')
        self.resize(self.getDefaultWidth(), self.getDefaultHeight())
    
    def onModelRangeVoidChanged(self, sender, sel, ptr, *args):
        if self.form.Model_range_voidKw.getValue() == 3:
            self.TextField_void.enable()
        else:
            self.TextField_void.disable()
        return 1
    
    def onVoidDistMethodChanged(self, sender, sel, ptr, *args):
        if self.form.void_distribution_methodKw.getValue() == 2:  # Custom
            self.voidDistValueSpinner.enable()
        else:  # Random
            self.voidDistValueSpinner.disable()
        self.updatePriorityState()
        return 1
    
    def onVoidSizeMethodChanged(self, sender, sel, ptr, *args):
        if self.form.void_size_methodKw.getValue() == 2:  # Custom
            self.voidThetaSpinner.enable()
        else:  # Random
            self.voidThetaSpinner.disable()
        self.updatePriorityState()
        return 1
    
    # ------------------------------------------------------------------
    # Void shape factor (beta) handlers
    # ------------------------------------------------------------------
    def onVoidBetaActiveChanged(self, sender, sel, ptr, *args):
        self._updateVoidBetaWidgets()
        return 1

    def onVoidBetaUnifiedChanged(self, sender, sel, ptr, *args):
        self._updateVoidBetaWidgets()
        return 1

    def onVoidThetaStarActiveChanged(self, sender, sel, ptr, *args):
        self._updateVoidBetaWidgets()
        return 1

    def _updateVoidBetaWidgets(self):
        # Defensive: widgets may not yet exist during early construction calls.
        if not hasattr(self, 'voidBetaValueSpinner'):
            return
        active = bool(self.form.voidBetaActiveKw.getValue())
        unified = (self.form.voidBetaUnifiedKw.getValue() == 1)
        theta_star_on = bool(self.form.voidThetaStarActiveKw.getValue())

        # Unified-mode controls
        if active and unified:
            self.voidBetaValueSpinner.enable()
        else:
            self.voidBetaValueSpinner.disable()

        # Split-mode controls
        if active and not unified:
            self.voidBetaFiberSpinner.enable()
            self.voidBetaMatrixSpinner.enable()
        else:
            self.voidBetaFiberSpinner.disable()
            self.voidBetaMatrixSpinner.disable()

        # Orientation + sub-mode radios + theta* fields all need active
        if active:
            self.voidBetaUnifiedRadio1.enable()
            self.voidBetaUnifiedRadio2.enable()
            self.voidBetaOrientRadio1.enable()
            self.voidBetaOrientRadio2.enable()
            self.voidThetaStarCheck.enable()
            if theta_star_on:
                self.voidThetaStarSpinner.enable()
            else:
                self.voidThetaStarSpinner.disable()
        else:
            self.voidBetaUnifiedRadio1.disable()
            self.voidBetaUnifiedRadio2.disable()
            self.voidBetaOrientRadio1.disable()
            self.voidBetaOrientRadio2.disable()
            self.voidThetaStarCheck.disable()
            self.voidThetaStarSpinner.disable()

    def updatePriorityState(self):
        dist_custom = (self.form.void_distribution_methodKw.getValue() == 2)
        size_custom = (self.form.void_size_methodKw.getValue() == 2)
        
        if dist_custom and size_custom:
            # both specified: allow priorities 1 and 2, disable 3
            self.RadioButton_priority_1.enable()
            self.RadioButton_priority_2.enable()
            self.RadioButton_priority_3.disable()
            # if 3 is currently selected, auto-switch to 1
            if self.form.void_priorityKw.getValue() == 3:
                self.form.void_priorityKw.setValue(1)
                self.RadioButton_priority_1.setCheck(True)
        elif dist_custom and not size_custom:
            # w specified + theta random -> distribution priority
            self.form.void_priorityKw.setValue(1)
            self.RadioButton_priority_1.setCheck(True)
            self.RadioButton_priority_1.disable()
            self.RadioButton_priority_2.disable()
            self.RadioButton_priority_3.disable()
        elif not dist_custom and size_custom:
            # w random + theta specified -> size priority
            self.form.void_priorityKw.setValue(2)
            self.RadioButton_priority_2.setCheck(True)
            self.RadioButton_priority_1.disable()
            self.RadioButton_priority_2.disable()
            self.RadioButton_priority_3.disable()
        else:
            # both random -> no intervention
            self.form.void_priorityKw.setValue(3)
            self.RadioButton_priority_3.setCheck(True)
            self.RadioButton_priority_1.disable()
            self.RadioButton_priority_2.disable()
            self.RadioButton_priority_3.disable()
    
    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def updateComboBox_13Parts(self):

        modelName = self.form.model_for_analysisKw.getValue()
        self.ComboBox_13.clearItems()
        names = mdb.models[modelName].parts.keys()
        names.sort()
        for name in names:
            self.ComboBox_13.appendItem(name)
        if names:
            if not self.form.part_for_analysisKw.getValue() in names:
                self.form.part_for_analysisKw.setValue(names[0])
        else:
            self.form.part_for_analysisKw.setValue('')

        self.resize(self.getDefaultWidth(), self.getDefaultHeight())
    
    def onAnalysisTypeChanged(self, sender, sel, ptr, *args):
        # Show only the panel that corresponds to the selected analysis type.
        # Analysis-type IDs:
        #   1 = Elastic + CTE                 5 = Thermal Conductivity
        #   4 = Elastoplastic (Uniaxial)      6 = Elastoplastic (Biaxial)
        #   2 = Viscoelastic (Time)           3 = Viscoelastic (Frequency)
        # UMAT input stays enabled for every type (kernel ignores it when not used).
        val = self.form.analysisTypeKw.getValue()
        self.paramPanelNone.hide()
        self.paramPanelElastic.hide()
        self.paramPanelViscTime.hide()
        self.paramPanelViscFreq.hide()
        self.paramPanelElastoplastic.hide()
        self.paramPanelThermal.hide()
        if val == 1:
            self.paramPanelElastic.show()
        elif val == 2:
            self.paramPanelViscTime.show()
        elif val == 3:
            self.paramPanelViscFreq.show()
        elif val in (4, 6):
            # Both Elastoplastic variants share the same panel; the inner
            # uniaxial / biaxial sub-frame is selected by updateElastoplasticWidgets.
            self.paramPanelElastoplastic.show()
        elif val == 5:
            self.paramPanelThermal.show()
        else:
            self.paramPanelNone.show()
        # UMAT field and file-picker button stay enabled for every analysis type.
        self.umatNameTextField.enable()
        self.umatNameButton.enable()
        # Re-evaluate CTE-controlled enable/disable on the Elastic panel.
        self.onImportCTEChanged(None, None, None)
        # Refresh the elastoplastic sub-panels (uniaxial vs biaxial visibility,
        # per-field enable/disable). updateElastoplasticWidgets reads analysisType.
        self.updateElastoplasticWidgets()
        # Force layout refresh so the dialog resizes to fit the new panel.
        self.paramPanelNone.getParent().recalc()
        self.TabItem_7.recalc()
        self.TabBook_1.recalc()
        self.resize(self.getDefaultWidth(), self.getDefaultHeight())
        return 1

    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # Elastoplastic UI handlers
    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def onElastoplasticSingleLoadChanged(self, sender, sel, ptr, *args):
        # Any single-axis checkbox toggled; enable/disable its companion value field.
        self.updateElastoplasticWidgets()
        return 1

    def onElastoplasticBiaxialComboChanged(self, sender, sel, ptr, *args):
        # Biaxial combo selection changed; refresh in case layout depends on it.
        self.updateElastoplasticWidgets()
        return 1

    def updateElastoplasticWidgets(self):
        """Show uniaxial sub-frame for analysisType==4, biaxial for ==6, and
        enable only the active uniaxial value fields. No-op for other types."""
        try:
            analysis_type = int(self.form.analysisTypeKw.getValue())
        except Exception:
            analysis_type = 0
        if analysis_type == 6:
            # Biaxial
            try:
                self.epSingleAxisFrame.hide()
                self.epBiaxialFrame.show()
            except Exception:
                pass
            for useKeyword, field in getattr(self, 'epSingleAxisFields', []):
                try:
                    field.disable()
                except Exception:
                    pass
        elif analysis_type == 4:
            # Uniaxial: enable only the value fields whose checkbox is ticked.
            try:
                self.epBiaxialFrame.hide()
                self.epSingleAxisFrame.show()
            except Exception:
                pass
            for useKeyword, field in getattr(self, 'epSingleAxisFields', []):
                try:
                    if useKeyword.getValue():
                        field.enable()
                    else:
                        field.disable()
                except Exception:
                    pass
        # else: not an elastoplastic analysis -- nothing to toggle.

    def handleCreateRVE(self):
        myModelName = self.form.myModelKw.getValue()
        a = self.form.aKw.getValue()
        b = self.form.bKw.getValue()
        t = self.form.tKw.getValue()
        df = self.form.dfKw.getValue()
        vf = self.form.vfKw.getValue()
    
        algorithm = self.algorithmKw.getValue()
        session.writeToLog("Algorithm selected: {}\n".format(algorithm))
        
        control_options = self.control_optionsKw.getValue()
    
        if algorithm == 1:
            l_safe = self.form.l_safeKw.getValue()
            session.writeToLog('Selected Algorithm: Monte Carlo\n')
            session.writeToLog('Safe distance between fibres: {}\n'.format(l_safe))
        elif algorithm == 2:
            lmin = self.form.lminKw.getValue()
            lmax = self.form.lmaxKw.getValue()
            session.writeToLog('Selected Algorithm: RSE\n')
            session.writeToLog('Minimum distance: {}\n'.format(lmin))
            session.writeToLog('Maximum distance: {}\n'.format(lmax))
        elif algorithm == 3:
            readcsv = self.form.readcsvKw.getValue()
            session.writeToLog('Selected Algorithm: User coordinates\n')
            session.writeToLog('Coordinate file: {}\n'.format(readcsv))
    
        if control_options == 1:
            session.writeToLog('Selected control_options: keep vf\n')
        elif control_options == 2:
            session.writeToLog('Selected control_options: keep RVE size\n')
    
        session.writeToLog('Handling Create RVE with inputs:\n')
        session.writeToLog('Model Name: {}\n'.format(myModelName))
        session.writeToLog('RVE width: {}\n'.format(a))
        session.writeToLog('RVE height: {}\n'.format(b))
        session.writeToLog('RVE thickness: {}\n'.format(t))
        session.writeToLog('Diameter: {}\n'.format(df))
        session.writeToLog('Volume Fraction: {}\n'.format(vf))

    def handleMeshAndInterphase(self):
        pass

    def handleEditMaterials(self):
        pass

    def handleVoidInsertion(self):
        pass

    def handleInterface(self):
        # Implement the function to handle the 'Interface' tab actions
        modelName = self.form.model_for_interfaceKw.getValue()
        partName = self.form.part_for_interfaceKw.getValue()
        model_range_option = self.form.Model_range_interfaceKw.getValue()
        user_input = self.form.user_input_interfaceKw.getValue()
        
        session.writeToLog('Handling Interface tab with inputs:\n')
        session.writeToLog('Model Name: {}\n'.format(modelName))
        session.writeToLog('Part Name: {}\n'.format(partName))
        if model_range_option == 1:
            session.writeToLog('Applying interface to the current model.\n')
        elif model_range_option == 2:
            session.writeToLog('Applying interface to all models with the same primary name.\n')
        elif model_range_option == 3:
            session.writeToLog('Applying interface to models: {}\n'.format(user_input))
    
    def handleAnalysis(self):
        analysisModelName = self.form.model_for_analysisKw.getValue()
        analysisPartName = self.form.part_for_analysisKw.getValue()
        
        relaxationTime = self.form.relaxationTimeKw.getValue()
        time_point = self.form.time_pointKw.getValue()
        
        umatName = self.form.umatNameKw.getValue()
        analysisType = self.form.analysisTypeKw.getValue()
        
    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def onCmdClicked(self, sender, sel, ptr):
        if sel == self.ID_CLICKED_OK:
            if self.currentTabIndex == 0:
                session.writeToLog("handleCreateRVE is being called\n")
                self.handleCreateRVE()
            elif self.currentTabIndex == 1:
                self.handleMeshAndInterphase()
            elif self.currentTabIndex == 2:
                self.handleEditMaterials()
            elif self.currentTabIndex == 3:
                self.handleVoidInsertion()  # New handler for the fourth tab
            elif self.currentTabIndex == 4:
                self.handleInterface()
            elif self.currentTabIndex == 5:
                self.handleAnalysis()
            
            self.hide()
            return 1
        else:
            return AFXDataDialog.onCmdClicked(self, sender, sel, ptr)

    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def onModelRangeChanged(self, sender, sel, ptr, *args):
        if self.form.Model_range.getValue() == 3:
            self.TextField.enable()
        else:
            self.TextField.disable()
        return 1
    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def onImportCTEChanged(self, sender, sel, ptr, *args):
        # The CTE temperature ramp (Initial/Final/Segment) is enabled only when
        # the CTE checkbox is ticked AND the analysis type is Elastic+CTE.
        analysis_type = self.form.analysisTypeKw.getValue()
        cte_active = (analysis_type == 1) and self.import_CTECheckBox.getCheck()
        if cte_active:
            self.intempTextFieldElastic.enable()
            self.fntempTextFieldElastic.enable()
            self.segmentTextFieldElastic.enable()
        else:
            self.intempTextFieldElastic.disable()
            self.fntempTextFieldElastic.disable()
            self.segmentTextFieldElastic.disable()
        # The elastic Temperature Points sweep field is enabled whenever the
        # Elastic+CTE panel is the active panel (the field itself is optional).
        try:
            if analysis_type == 1:
                self.elasticTemperaturePointsTextField.enable()
            else:
                self.elasticTemperaturePointsTextField.disable()
        except Exception:
            pass
        return 1
    
    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def onMeshTypeChanged(self, sender, sel, ptr):
        """Handle mesh type change"""
        meshType = self.form.meshTypeKw.getValue()
        
        # Show/hide appropriate option frames
        if meshType == 1:  # Thermal analysis
            self.mechanicalOptionsFrame.hide()
            self.thermalOptionsFrame.show()
            # Reset thermal options to valid state
            self.updateThermalOptionsState()
        else:  # Mechanical or Coupled (both use Q, R, H options)
            self.mechanicalOptionsFrame.show()
            self.thermalOptionsFrame.hide()
        
        # Force frame recalculation
        self.mechanicalOptionsFrame.getParent().recalc()
        
        return 1
    
    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def updateThermalOptionsState(self):
        """Update thermal options based on current selections"""
        if self.form.useThermalQuadraticKw.getValue():
            # Q selected: disable all other options
            self.thermalReducedCheckBox.disable()
            self.convectionCheckBox.disable()
            self.dispersionCheckBox.disable()
        elif self.form.useThermalReducedKw.getValue():
            # R selected: disable C and D
            self.convectionCheckBox.disable()
            self.dispersionCheckBox.disable()
        elif self.form.useConvectionKw.getValue():
            # C selected: disable R, enable D
            self.thermalReducedCheckBox.disable()
            self.dispersionCheckBox.enable()
        else:
            # Nothing selected: enable R and C, disable D
            self.thermalReducedCheckBox.enable()
            self.convectionCheckBox.enable()
            self.dispersionCheckBox.disable()
    
    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def onThermalQuadraticChanged(self, sender, sel, ptr):
        """Handle thermal quadratic checkbox change"""
        if self.form.useThermalQuadraticKw.getValue():
            # When Q is selected, disable R, C, D
            self.thermalReducedCheckBox.disable()
            self.convectionCheckBox.disable()
            self.dispersionCheckBox.disable()
            # Uncheck them as well
            self.form.useThermalReducedKw.setValue(False)
            self.form.useConvectionKw.setValue(False)
            self.form.useDispersionKw.setValue(False)
        else:
            # When Q is unselected, enable R and C
            self.thermalReducedCheckBox.enable()
            self.convectionCheckBox.enable()
            # D is controlled by C state
            self.updateDispersionState()
        return 1
    
    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def onConvectionChanged(self, sender, sel, ptr):
        """Handle convection checkbox change"""
        if self.form.useConvectionKw.getValue():
            # When C is selected, R should be disabled
            self.thermalReducedCheckBox.disable()
            self.form.useThermalReducedKw.setValue(False)
            # Enable D option
            self.dispersionCheckBox.enable()
        else:
            # When C is unselected, disable and uncheck D
            self.dispersionCheckBox.disable()
            self.form.useDispersionKw.setValue(False)
            # Enable R if Q is not selected
            if not self.form.useThermalQuadraticKw.getValue():
                self.thermalReducedCheckBox.enable()
        return 1
    
    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def onDispersionChanged(self, sender, sel, ptr):
        """Handle dispersion checkbox change"""
        if self.form.useDispersionKw.getValue():
            # When D is selected, automatically select C
            self.form.useConvectionKw.setValue(True)
            self.convectionCheckBox.setCheck(True)
            # Disable R
            self.thermalReducedCheckBox.disable()
            self.form.useThermalReducedKw.setValue(False)
        return 1
    
    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def onThermalReducedChanged(self, sender, sel, ptr):
        """Handle thermal reduced checkbox change"""
        if self.form.useThermalReducedKw.getValue():
            # When R is selected, disable and uncheck C and D
            self.convectionCheckBox.disable()
            self.dispersionCheckBox.disable()
            self.form.useConvectionKw.setValue(False)
            self.form.useDispersionKw.setValue(False)
        else:
            # When R is unselected, enable C (if Q is not selected)
            if not self.form.useThermalQuadraticKw.getValue():
                self.convectionCheckBox.enable()
                self.updateDispersionState()
        return 1
    
    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def updateDispersionState(self):
        """Update dispersion checkbox state based on convection"""
        if self.form.useConvectionKw.getValue():
            self.dispersionCheckBox.enable()
        else:
            self.dispersionCheckBox.disable()
            self.form.useDispersionKw.setValue(False)
    
    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def onVoidDistMethodChanged(self, sender, sel, ptr, *args):
        if self.form.void_distribution_methodKw.getValue() == 2:  # Custom
            self.voidDistValueSpinner.enable()
        else:  # Random
            self.voidDistValueSpinner.disable()
        self.updatePriorityState()
        return 1
    
    def onVoidSizeMethodChanged(self, sender, sel, ptr, *args):
        if self.form.void_size_methodKw.getValue() == 2:  # Custom
            self.voidThetaSpinner.enable()
        else:  # Random
            self.voidThetaSpinner.disable()
        self.updatePriorityState()
        return 1
    
###########################################################################
# File Handling Class Definition
###########################################################################

class RVE_Builder_UDFRPsDBFileHandler(FXObject):

    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def __init__(self, form, keyword, patterns='*'):

        self.form = form
        self.patterns = patterns
        self.patternTgt = AFXIntTarget(0)
        
        self.cmd_tab2 = AFXCommand(self.form, 'command_name')
        
        exec('self.fileNameKw = form.%sKw' % keyword)
        
        self.readOnlyKw = AFXBoolKeyword(None, 'readOnly', AFXBoolKeyword.TRUE_FALSE)
        
        FXObject.__init__(self)
        FXMAPFUNC(self, SEL_COMMAND, AFXMode.ID_ACTIVATE, RVE_Builder_UDFRPsDBFileHandler.activate)
    
    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def activate(self, sender, sel, ptr):

       fileDb = AFXFileSelectorDialog(getAFXApp().getAFXMainWindow(), 'Select a File',
           self.fileNameKw, self.readOnlyKw,
           AFXSELECTFILE_MULTIPLE, self.patterns, self.patternTgt)
       fileDb.setReadOnlyPatterns('*.odb')
       fileDb.create()
       fileDb.showModal()
    

class UMATFileHandler(FXObject):

    def __init__(self, form, keyword, patterns='FOR files (*.for)'):
        self.form = form
        self.patterns = patterns
        self.patternTgt = AFXIntTarget(0)
        exec('self.fileNameKw = form.%sKw' % keyword)
        self.readOnlyKw = AFXBoolKeyword(None, 'readOnly', AFXBoolKeyword.TRUE_FALSE)
        FXObject.__init__(self)
        FXMAPFUNC(self, SEL_COMMAND, AFXMode.ID_ACTIVATE, UMATFileHandler.activate)

    def activate(self, sender, sel, ptr):
        fileDb = AFXFileSelectorDialog(getAFXApp().getAFXMainWindow(), 'Select a FOR File',
            self.fileNameKw, self.readOnlyKw,
            AFXSELECTFILE_ANY, self.patterns, self.patternTgt)
        fileDb.setReadOnlyPatterns('*.for')
        fileDb.create()
        fileDb.showModal()
