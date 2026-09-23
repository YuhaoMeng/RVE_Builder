# RVE Builder (UDFRPs)

An Abaqus/CAE plug-in that automates the full workflow of building
**Representative Volume Elements (RVEs)** for unidirectional continuous
fiber-reinforced polymers (UDFRPs) and computing their effective properties
under **periodic boundary conditions (PBC)** — all from a single tabbed
dialog, with no scripting and no third-party software required.

Geometry generation, meshing, material assignment, microvoid insertion,
cohesive-interface insertion and homogenization analysis are driven from one
GUI. Every operation accepts a model-range selector, so a parameter study with
dozens of stochastic realizations can be generated, meshed, assigned and
analysed in a single click.

> **License:** GNU General Public License v3.0 (GPLv3). This plug-in builds on
> [EasyPBC](https://doi.org/10.1007/s00366-018-0616-4) (© 2018 Sadik Lafta
> Omairey), which is GPL-licensed; as a derivative work this plug-in is
> therefore also released under the GPL. See [`LICENSE`](LICENSE).

## Features

- **Random fiber distributions** via Monte Carlo, Random Sequential Expansion
  (RSE), or imported CSV coordinates.
- **Mesh seeding** with built-in element-type and shape selection (mechanical,
  thermal, or thermo-mechanically coupled).
- **Cross-model batch material assignment** using Abaqus's ODB-based material
  copy, to propagate one definition across many models at once.
- **Matrix microvoid insertion** with controllable spatial distribution
  (random or fiber-adjacent weighted) and size strategy.
- **Optional zero-thickness cohesive interface** (COH3D8) at the fiber/matrix
  surface, with an initial-debonding ratio for pre-damaged cases.
- **Six PBC-based homogenization analyses** (see table below); the
  elastoplastic and thermal analyzers automatically switch to interface-aware
  kernels when cohesive seams are present.

## Requirements

- **Abaqus/CAE 2024** (uses Abaqus's built-in Python 3 interpreter).
- Windows (installation paths below assume Windows; adjust for other OSes).

## Installation

1. Copy the entire plug-in folder into your Abaqus plug-ins directory. On
   Windows this is typically:

   ```
   C:\SIMULIA\CAE\plugins\2024\
   ```

2. Restart Abaqus/CAE.
3. The plug-in appears under **Plug-ins → RVE Builder (UDFRPs)**.

If the plug-in does not appear, confirm the files are not blocked by Windows
(right-click → Properties → Unblock) and that all files sit directly in the
plug-in folder (not in a sub-folder). If you hit an `AttributeError` after an
update, delete the `__pycache__` folder in the plug-in directory and restart.

## Usage

The dialog exposes **six tabs**, intended to be used in order. Each tab
includes a *Select Model Range* control to operate on the current model, all
models sharing a primary name, or a specific subset.

1. **Create RVE** — set geometry, fiber-coordinate generator (Monte Carlo /
   RSE / CSV), volume fraction, and batch size.
2. **Mesh Control** — apply mesh seeds, choose element shape (HEX / WEDGE) and
   mesh type (mechanical / thermal / coupled).
3. **Materials** — assign fiber and matrix materials; optionally use ODB-based
   copy to propagate the assignment across many models.
4. **Void Insertion** *(optional)* — insert voids with controllable
   distribution, size method and priority (runs after meshing).
5. **Interface** *(optional)* — insert zero-thickness cohesive seams (COH3D8)
   at the fiber/matrix interface, optionally partly debonded. Works on a copy
   of the source model so the original mesh is preserved.
6. **Analysis** — set up periodic boundary conditions and run any of the
   homogenization analyses below. Optional UMAT subroutine supported.

## Homogenization analyses

| `analysis_type` | Analyzer file | Purpose |
| --- | --- | --- |
| 1 | `PBC_UDFRP_Elastic_CTE.py` | Linear elastic + coefficient of thermal expansion (CTE) |
| 2 | `PBC_UDFRP_Viscoelastic_Time.py` | Viscoelastic, time domain |
| 3 | `PBC_UDFRP_Viscoelastic_Frequency.py` | Viscoelastic, frequency domain |
| 4 | `PBC_UDFRP_Elastoplastic.py` | Elastoplastic, uniaxial macroscopic strain |
| 5 | `PBC_UDFRP_thermal_conductivity.py` | Steady-state thermal conductivity tensor |
| 6 | `PBC_UDFRP_Elastoplastic.py` | Elastoplastic, biaxial macroscopic strain |

When the selected model contains COH3D8 cohesive seams, the dispatcher
automatically selects the interface-aware variants
`PBC_UDFRP_Elastoplastic_interface.py` and
`PBC_UDFRP_thermal_conductivity_Interfaceh.py`.

## Repository structure

| File | Role |
| --- | --- |
| `RVE_Builder_UDFRPs_plugin.py` | GUI form — registers the menu entry and keyword bindings |
| `RVE_Builder_UDFRPsDB.py` | GUI dialog — builds the tabbed window and wires UI events |
| `RVE_Builder_UDFRPs.py` | Kernel — implements the operation behind each tab |
| `Generate_UDFRPs_MonteCarlo.py` | Monte-Carlo fiber-coordinate generator |
| `Generate_UDFRPs_RSE.py` | Random Sequential Expansion fiber-coordinate generator |
| `PBC_UDFRP_*.py` | PBC homogenization analyzers (see table above) |
| `help/` | Bundled multilingual help site (EN / PT / ZH), opened from the dialog |
| `icon.png`, `*.png` | Plug-in icon and dialog diagrams |

## Citation

If this plug-in supports your research, please cite:

> Yuhao Meng, Murilo Augusto Vaz, Marcelo Caire. *An efficient micromechanical
> framework for elastic and viscoelastic properties prediction of
> unidirectional continuous fiber-reinforced polymers with microvoids.*
> Composite Structures, Vol. 387, 2026, 120307. ISSN 0263-8223.
> https://doi.org/10.1016/j.compstruct.2026.120307

Please also cite the underlying EasyPBC work:

> Omairey S., Dunning P., Sriramula S. (2018). *Development of an ABAQUS plugin
> tool for periodic RVE homogenisation.* Engineering with Computers.
> https://doi.org/10.1007/s00366-018-0616-4

## License

Released under the **GNU General Public License v3.0** — see [`LICENSE`](LICENSE)
for the full text. Portions are derived from **EasyPBC** (© 2018 Sadik Lafta
Omairey), which is distributed under the GNU GPL.

## Acknowledgements

Developed by **Yuhao Meng** at the Ocean Engineering Program, COPPE,
Universidade Federal do Rio de Janeiro (UFRJ), Brazil, with thanks to
Prof. Murilo Augusto Vaz and Prof. Marcelo Caire. Sincere thanks to
S. L. Omairey, author of EasyPBC, on which the PBC homogenization kernels are
based.

## Contact

Questions, corrections and suggestions are welcome:
Yuhao Meng — <yuhaomeng@oceanica.ufrj.br>
