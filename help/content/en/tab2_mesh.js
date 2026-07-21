// Auto-loaded via <script> tag from index.html
// Edit the HTML inside the template literal below; do NOT change the wrapper.
window.helpContent = window.helpContent || {};
window.helpContent['en/tab2_mesh'] = `
<\!-- ===== SECTION: tab2_mesh =============================================== -->
<h1>3.2 · Mesh Control</h1>

<p>
  The <strong>Mesh Control</strong> tab applies seeds and meshes the
  selected RVE model(s). It also lets you switch element type and shape
  according to the analysis you plan to run later.
</p>

<figure class="figure">
  <img src="images/Mesh_Seed_Diagram.png" alt="Mesh seed diagram">
  <figcaption>Fig 2 — Where each seed-control parameter applies.</figcaption>
</figure>

<h2>3.2.1 Select Model</h2>

<p>Drop-down lists pick the model and the part to mesh. The plug-in is
designed for the <code>UDComposite</code> part — leave it selected unless
you have customized the geometry.</p>

<h2>3.2.2 Select Model Range for Meshing</h2>

<p>Common batch control used across all tabs:</p>
<ul>
  <li><strong>Current Model</strong> — mesh only the model currently selected.</li>
  <li><strong>All Models</strong> — mesh every model that shares the primary
      name of the selected model (e.g., <code>RVE_UDFiber_Random_Df7_Vf040_…</code>).</li>
  <li><strong>Selected numbers</strong> — type a custom list using
      "<code>-</code>" for ranges and "<code>,</code>" to separate items.
      Example: <code>1, 4-9</code>.</li>
</ul>

<h2>3.2.3 Seeds Control (by Number)</h2>

<table class="field-table">
  <thead><tr><th>Field</th><th>Default</th><th>Meaning</th></tr></thead>
  <tbody>
    <tr><td>Circle-dominant and Arc</td><td>12</td>
        <td>Number of seeds around fiber circles and arcs (cross-section view).</td></tr>
    <tr><td>Cross-Section Edges</td><td>20</td>
        <td>Number of seeds along the RVE outer cross-section edges.</td></tr>
    <tr><td>Along Fiber Direction Edges</td><td>10</td>
        <td>Number of seeds along the fiber axis (X direction).</td></tr>
    <tr><td>Minimum Size Control</td><td>0.1</td>
        <td>Minimum allowable element size factor (passed to Abaqus's
        meshing algorithm).</td></tr>
  </tbody>
</table>

<h3>Recommended seed counts — formulas</h3>

<p>
  Let <code>NR</code> be the number of seeds placed around the fiber
  circumference (the value entered in <strong>Circle-dominant and Arc</strong>).
  The implied <em>approximate element size</em> on a fiber is:
</p>
<p style="text-align:center;">
  $$ \\text{size}_{\\mathrm{approx}} \\;=\\; \\dfrac{\\pi \\, d_f}{N_R} $$
</p>
<p>
  To keep the cross-section / through-thickness mesh consistent with that
  size, the seed count <code>NL</code> for an edge of length <code>L</code>
  should be:
</p>
<p style="text-align:center;">
  $$ N_L \\;=\\; \\dfrac{L}{\\text{size}_{\\mathrm{approx}}} \\;=\\; \\dfrac{L \\, N_R}{\\pi \\, d_f} $$
</p>
<p>
  Apply this formula to <strong>Cross-Section Edges</strong> with
  <code>L = a</code> (or <code>b</code>), and to
  <strong>Along Fiber Direction Edges</strong> with <code>L = t</code>.
</p>

<div id="seed-calc" class="seed-calculator">
  <h4>Interactive seed calculator</h4>
  <div class="calc-grid">
    <label>Fiber diameter d<sub>f</sub>
      <input type="number" data-calc="df" value="7" step="0.1" min="0">
    </label>
    <label>Seeds on fiber N<sub>R</sub>
      <input type="number" data-calc="nr" value="12" step="1" min="1">
    </label>
    <label>Edge length L
      <input type="number" data-calc="l" value="50" step="1" min="0">
    </label>
  </div>
  <div class="calc-output">
    <div>Approx. element size: <span data-calc="size">—</span></div>
    <div>Recommended N<sub>L</sub>: <span data-calc="nl">—</span></div>
  </div>
</div>

<div class="callout callout-note">
  <p>The calculator is just the formulas above wrapped in a UI. Edit any
  field to update the result instantly. For Cross-Section Edges set
  <code>L</code> to the RVE width or height; for Along Fiber Direction Edges
  set <code>L</code> to the RVE depth.</p>
</div>

<h2>3.2.4 Mesh Type Selection</h2>

<p>Pick the analysis kind <em>before</em> meshing — element library depends
on it.</p>

<table class="field-table">
  <thead><tr><th>Mesh Type</th><th>Linear element</th><th>Use with</th></tr></thead>
  <tbody>
    <tr><td>Mechanical Analysis (C3D8)</td><td>C3D8 / C3D6</td>
        <td>Elastic, CTE, Viscoelastic, Elastoplastic.</td></tr>
    <tr><td>Thermal Analysis (DC3D8)</td><td>DC3D8 / DC3D6</td>
        <td>Thermal Conductivity.</td></tr>
    <tr><td>Thermo-Mechanical Coupled (C3D8T)</td><td>C3D8T / C3D6T</td>
        <td>Coupled thermal–stress problems.</td></tr>
  </tbody>
</table>

<h2>3.2.5 Element Options</h2>

<p>Toggles below the mesh-type radio buttons let you upgrade elements:</p>

<div class="inline-tabs">
  <div class="tab-buttons">
    <button class="tab-btn">Mechanical / Coupled</button>
    <button class="tab-btn">Thermal</button>
  </div>
  <div class="tab-panel">
    <ul>
      <li><strong>Quadratic (20-nodes)</strong> — promotes C3D8 → C3D20 (and
          C3D6 → C3D15). Higher accuracy, much higher cost.</li>
      <li><strong>Reduced Integration (R)</strong> — adds the "R" suffix
          (e.g., C3D8R). Use with caution on very coarse meshes due to hourglass
          modes.</li>
      <li><strong>Hybrid Formulation (H)</strong> — adds the "H" suffix.
          Required for nearly incompressible matrices.</li>
    </ul>
  </div>
  <div class="tab-panel">
    <ul>
      <li><strong>Quadratic (20-node)</strong> — DC3D8 → DC3D20.</li>
      <li><strong>Reduced Integration (R)</strong></li>
      <li><strong>Convection/Diffusion (C)</strong></li>
      <li><strong>Dispersion Control (D)</strong></li>
    </ul>
    <div class="callout callout-note">
      <p><strong>Thermal element rules:</strong> only certain combinations
      of options produce a valid Abaqus element symbol. Invalid combinations
      are ignored at mesh time.</p>
    </div>
  </div>
</div>

<h2>3.2.6 Element Shape</h2>

<ul>
  <li><strong>HEX-dominated, C3D8 + C3D6</strong> — best balance, default.</li>
  <li><strong>HEX-dominated, C3D20 + C3D15</strong> — quadratic upgrade.</li>
  <li><strong>WEDGE, C3D6</strong> — wedge-only, useful when hexahedral
      meshing fails on extreme Vf models.</li>
</ul>

<div class="callout callout-warn">
  <div class="callout-title">Other element types are restricted</div>
  <p>To guarantee that periodic boundary conditions can be applied later, the
  plug-in restricts the available choices. Substituting other element types
  manually outside the plug-in may break the Analysis tab.</p>
</div>

<h2>3.2.7 After clicking OK — outputs and database changes</h2>

<p>
  No external files are written by this tab. The selected model(s) are
  meshed in place and Abaqus's mesh module shows the result. Specifically:
</p>
<ul>
  <li>Edge seeds are applied per the values entered above.</li>
  <li>The mesh is generated using the chosen element shape.</li>
  <li>Element type is set on every cell according to the Mesh Type and
      Element Options selections (e.g., C3D8R, C3D20H, DC3D8).</li>
  <li>If a global element-size factor was needed, it is computed from
      <em>Minimum Size Control</em>.</li>
</ul>

<div class="callout callout-tip">
  <div class="callout-title">Verification</div>
  <p>After meshing, switch to Abaqus's Mesh module to inspect element
  count and quality. The <code>UDComposite</code> part should now contain
  a meshed instance ready for the Materials and Analysis tabs.</p>
</div>
`;
