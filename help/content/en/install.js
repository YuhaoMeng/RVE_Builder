// Auto-loaded via <script> tag from index.html
// Edit the HTML inside the template literal below; do NOT change the wrapper.
window.helpContent = window.helpContent || {};
window.helpContent['en/install'] = `
<\!-- ===== SECTION: install ================================================= -->
<h1>2 · Plugin Installation</h1>

<p>
  This plug-in is built for <strong>Abaqus/CAE 2024</strong> and uses
  Abaqus's built-in Python 3 interpreter. It is updated periodically on
  GitHub; to avoid runtime issues, please use the recommended Abaqus
  version.
</p>

<h2>Install location</h2>

<p>Copy the entire <code>RVE_Builder_plugin</code> folder into your Abaqus
plug-ins directory. On Windows that is typically:</p>

<pre><code>C:\\SIMULIA\\CAE\\plugins\\2024\\</code></pre>

<p>After copying, restart Abaqus/CAE. The plug-in appears in the menu as
<strong>Plug-ins → RVE Builder (UDFRPs)</strong>.</p>

<h2>Files in the package</h2>

<table class="field-table">
  <thead>
    <tr><th>File</th><th>Type</th><th>Purpose</th></tr>
  </thead>
  <tbody>
    <tr><td><code>RVE_Builder_UDFRPs_plugin.py</code></td><td>GUI form</td>
        <td>Registers the plug-in menu entry and defines all keyword bindings.</td></tr>
    <tr><td><code>RVE_Builder_UDFRPsDB.py</code></td><td>GUI dialog</td>
        <td>Builds the tabbed dialog window and wires UI events.</td></tr>
    <tr><td><code>RVE_Builder_UDFRPs.py</code></td><td>Kernel</td>
        <td>Implements the operations triggered by each tab.</td></tr>
    <tr><td><code>Generate_UDFRPs_MonteCarlo.py</code></td><td>Generator</td>
        <td>Monte-Carlo fiber-coordinate generator.</td></tr>
    <tr><td><code>Generate_UDFRPs_RSE.py</code></td><td>Generator</td>
        <td>Random Sequential Expansion fiber-coordinate generator.</td></tr>
    <tr><td><code>PBC_UDFRP_Elastic_CTE.py</code></td><td>Analyzer</td>
        <td>Elastic + CTE homogenization (analysis_type = 1).</td></tr>
    <tr><td><code>PBC_UDFRP_Viscoelastic_Time.py</code></td><td>Analyzer</td>
        <td>Viscoelastic time-domain analysis (analysis_type = 2).</td></tr>
    <tr><td><code>PBC_UDFRP_Viscoelastic_Frequency.py</code></td><td>Analyzer</td>
        <td>Viscoelastic frequency-domain analysis (analysis_type = 3).</td></tr>
    <tr><td><code>PBC_UDFRP_Elastoplastic.py</code></td><td>Analyzer</td>
        <td>Elastoplastic analysis under macroscopic strain. Handles both
        Uniaxial (analysis_type = 4) and Biaxial (analysis_type = 6). Sets
        Solution Controls to <em>Specify ON, Discontinuous, IC = 30</em>
        for every run and exposes <em>Nlgeom</em> and <em>Unsymmetric matrix
        storage</em> toggles via the GUI.</td></tr>
    <tr><td><code>PBC_UDFRP_thermal_conductivity.py</code></td><td>Analyzer</td>
        <td>Steady-state thermal conductivity tensor (analysis_type = 5).</td></tr>
    <tr><td><code>PBC_UDFRP_Elastoplastic_interface.py</code></td><td>Analyzer</td>
        <td>Interface-aware variant of the elastoplastic kernel; selected
        automatically by the dispatcher when the chosen model contains
        COH3D8 cohesive seams (e.g. an <code>*_Interface</code> model
        produced by the Interface tab).</td></tr>
    <tr><td><code>PBC_UDFRP_thermal_conductivity_Interfaceh.py</code></td><td>Analyzer</td>
        <td>Interface-aware variant of the thermal-conductivity kernel,
        chosen automatically under the same condition.</td></tr>
  </tbody>
</table>

<h2>Verifying the installation</h2>
<ol>
  <li>Open Abaqus/CAE 2024.</li>
  <li>From the top menu choose <strong>Plug-ins</strong>.</li>
  <li>You should see <strong>RVE Builder (UDFRPs)</strong> listed. Click it
      to open the dialog.</li>
  <li>You should see six tabs: Create RVE, Mesh Control, Materials,
      Void Insertion, Interface, Analysis.</li>
</ol>

<details class="collapsible">
  <summary>Troubleshooting</summary>
  <p><strong>Plug-in does not appear in the menu.</strong> Confirm the folder
  is at the correct path and the files are not blocked by Windows (right-click
  → Properties → Unblock).</p>
  <p><strong>"Module not found" error.</strong> One of the renamed companion
  files is missing. Make sure all files in the table above are present and not
  inside a sub-folder.</p>
  <p><strong>"AttributeError: object has no attribute …".</strong> A stale
  <code>__pycache__</code> may be loaded. Delete the
  <code>__pycache__</code> folder inside the plug-in directory and restart
  Abaqus.</p>
</details>
`;
