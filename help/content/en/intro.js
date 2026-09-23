// Auto-loaded via <script> tag from index.html
// Edit the HTML inside the template literal below; do NOT change the wrapper.
window.helpContent = window.helpContent || {};
window.helpContent['en/intro'] = `
<\!-- ===== SECTION: intro =================================================== -->
<h1>1 · Introduction</h1>

<p>
  <strong>RVE Builder (UDFRPs)</strong> is an Abaqus/CAE plug-in that
  automates the full workflow of building Representative Volume Elements
  (RVEs) for unidirectional continuous fiber-reinforced polymers and
  computing their effective properties under periodic boundary conditions
  (PBC). Geometry generation, meshing, material assignment, microvoid
  insertion and homogenization analysis are all available from a single
  tabbed dialog — no scripting and no third-party software required.
</p>

<p>
  The plug-in is designed for both single-shot exploratory studies and
  large statistical batches. Every operation accepts a model-range selector,
  so a parameter study with dozens of stochastic realizations can be meshed,
  assigned and analysed in one click. Five homogenization analyses are
  supported out of the box: linear elastic with optional CTE, time- and
  frequency-domain viscoelasticity, elastoplasticity with optional UMAT, and
  steady-state thermal conductivity. Microvoids can be added to the matrix
  with controllable spatial distribution (random or fiber-adjacent weighted)
  and size strategy (random or fixed count).
</p>

<div class="callout callout-note">
  <div class="callout-title">Author</div>
  <p>Yuhao Meng · Ocean Engineering Program, COPPE, Universidade Federal do
  Rio de Janeiro, Brazil.</p>
  <p>This plug-in is developed by a single author as a personal effort and
  is shared here for academic exchange and discussion. Shortcomings are
  unavoidable — comments, corrections and suggestions are most welcome.
  Contact: <a href="mailto:yuhaomeng@oceanica.ufrj.br">yuhaomeng@oceanica.ufrj.br</a>.</p>
</div>

<h2>Capabilities at a glance</h2>
<ul>
  <li>Random fiber distributions via <strong>Monte Carlo</strong>,
      <strong>RSE</strong>, or imported CSV coordinates.</li>
  <li>Mesh seeding with built-in element-type and shape selection (mechanical,
      thermal, thermo-mechanical coupled).</li>
  <li>Cross-model batch material assignment using Abaqus's ODB material copy.</li>
  <li>Matrix microvoid insertion with controllable size, distribution and
      priority.</li>
  <li>Six PBC-based homogenization analyses (Elastic + CTE, Thermal
      Conductivity, Elastoplastic Uniaxial, Elastoplastic Biaxial,
      Viscoelastic Time, Viscoelastic Frequency); the elastoplastic and
      thermal analyzers automatically switch to interface-aware kernels when
      cohesive seams are present.</li>
  <li>Optional zero-thickness cohesive interface (COH3D8) insertion at the
      fiber-matrix surface, with an Initial Debonding ratio for pre-damaged
      cases.</li>
</ul>

<h2>Plug-in structure</h2>
<p>The plug-in exposes <strong>six tabs</strong>, one per workflow stage:</p>

<div class="inline-tabs">
  <div class="tab-buttons">
    <button class="tab-btn">Create RVE</button>
    <button class="tab-btn">Mesh Control</button>
    <button class="tab-btn">Materials</button>
    <button class="tab-btn">Void Insertion</button>
    <button class="tab-btn">Interface</button>
    <button class="tab-btn">Analysis</button>
  </div>
  <div class="tab-panel">
    <p>Set geometry, fiber-coordinate generator, volume fraction, and how
    many models to generate in a batch.</p>
  </div>
  <div class="tab-panel">
    <p>Apply mesh seeds, choose element shape (HEX/WEDGE), and pick mesh type
    (mechanical / thermal / coupled).</p>
  </div>
  <div class="tab-panel">
    <p>Assign fiber and matrix materials. Use Abaqus ODB-based material copy
    to propagate the assignment to many models at once.</p>
  </div>
  <div class="tab-panel">
    <p>Insert voids with controllable distribution (random or fiber-adjacent
    weighted), size method, and priority. Operates after meshing.</p>
  </div>
  <div class="tab-panel">
    <p>Insert zero-thickness cohesive seams (COH3D8) at the fiber-matrix
    interface, optionally with a fraction already debonded. Works on a copy
    of the source model so the original mesh is preserved.</p>
  </div>
  <div class="tab-panel">
    <p>Set up periodic boundary conditions and run any of the six
    homogenization analyses. Optional UMAT subroutine; the elastoplastic
    and thermal kernels automatically switch to interface-aware variants
    when cohesive seams are present.</p>
  </div>
</div>

<div class="callout callout-tip">
  <div class="callout-title">Workflow</div>
  <p>The tabs are designed to be used in order &mdash; Create RVE &rarr; Mesh
  Control &rarr; Materials &rarr; (optional) Void Insertion &rarr;
  (optional) Interface &rarr; Analysis. Each tab includes a
  <em>Select Model Range</em> control that lets you operate on the current
  model, all models with the same primary name, or a specific subset.</p>
</div>

`;
