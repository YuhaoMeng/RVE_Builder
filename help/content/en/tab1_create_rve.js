// Auto-loaded via <script> tag from index.html
// Edit the HTML inside the template literal below; do NOT change the wrapper.
window.helpContent = window.helpContent || {};
window.helpContent['en/tab1_create_rve'] = `
<\!-- ===== SECTION: tab1_create_rve ========================================= -->
<h1>3.1 · Create RVE</h1>

<p>
  The <strong>Create RVE</strong> tab generates the RVE geometry. You set
  the model name, choose how fiber centers are produced, define the geometric
  parameters, and decide how many models to generate in one batch.
</p>

<figure class="figure">
  <img src="images/Random_RVE_Model.png" alt="Random RVE model example">
  <figcaption>Fig 1 — Example of a randomly distributed UD-fiber RVE.</figcaption>
</figure>

<h2>3.1.1 Model Name</h2>

<p>
  Sets the primary name of the generated model. Default:
  <code>RVE_UDFiber_Random</code>. The plug-in then appends the diameter,
  volume fraction, fiber count, and a numeric suffix:
</p>

<pre><code>RVE_UDFiber_Random_Df7_Vf040_N143_Model_1
RVE_UDFiber_Random_Df7_Vf040_N143_Model_2
…</code></pre>

<p>This naming scheme is what the batch operations on later tabs use to
detect "all models with the same primary name".</p>

<h2>3.1.2 Fibers Coordinates Generation Method</h2>

<p>Choose one of three generators:</p>

<table class="field-table">
  <thead>
    <tr><th>Method</th><th>Vf cap</th><th>Notes</th></tr>
  </thead>
  <tbody>
    <tr>
      <td><strong>Monte Carlo</strong></td>
      <td>≈ 45%</td>
      <td>Randomly drops fibers and rejects overlaps. Fast but capped at lower
      Vf because of jamming.</td>
    </tr>
    <tr>
      <td><strong>Random Sequential Expansion (RSE)</strong></td>
      <td>≈ 68%</td>
      <td>Iteratively grows the fiber set. Reaches higher Vf but slower.</td>
    </tr>
    <tr>
      <td><strong>User coordinates file(s)</strong></td>
      <td>—</td>
      <td>Imports fiber centers from one or more CSV files. Two columns
      <em>(x, y)</em>, no headers.</td>
    </tr>
  </tbody>
</table>

<div class="callout callout-warn">
  <div class="callout-title">Vf cap is enforced</div>
  <p>These Vf caps are treated as <strong>hard limits</strong>. The plug-in
  rejects values above the cap with an error rather than attempting an
  unreliable generation.</p>
</div>

<h2>3.1.3 Geometric Parameters</h2>

<table class="field-table">
  <thead>
    <tr><th>Parameter</th><th>Default</th><th>Meaning</th></tr>
  </thead>
  <tbody>
    <tr><td>RVE Width <code>a</code></td><td>50</td>
        <td>Cross-section width (Y direction).</td></tr>
    <tr><td>RVE Height <code>b</code></td><td>50</td>
        <td>Cross-section height (Z direction).</td></tr>
    <tr><td>RVE Depth <code>t</code></td><td>50</td>
        <td>Length along the fiber axis (X direction).</td></tr>
    <tr><td>Fiber Diameter <code>df</code></td><td>7</td>
        <td>Single value — all fibers share this diameter.</td></tr>
    <tr><td>Fiber Volume Fraction <code>Vf</code></td><td>40</td>
        <td>Percent. The plug-in computes the integer fiber count
        <code>N</code> from <code>(Vf · a · b) / (π · df² / 4)</code>.</td></tr>
  </tbody>
</table>

<div class="callout callout-note">
  <div class="callout-title">Units</div>
  <p>Units must be self-consistent. The fiber diameter is usually entered in
  μm, so the RVE dimensions should be in μm too. Mechanical properties on the
  Materials tab must use compatible units (e.g., MPa = N/μm²).</p>
</div>

<h2>3.1.4 Control Options</h2>

<p>Because <code>N</code> is rounded to an integer, either the volume fraction
or the RVE dimensions must be adjusted slightly so that the actual geometry
matches one of the inputs exactly.</p>

<ul>
  <li><strong>keep vf</strong> — keeps Vf fixed and scales <code>a</code>,
      <code>b</code> proportionally.</li>
  <li><strong>keep RVE size</strong> — keeps <code>a</code>, <code>b</code>
      fixed and reports the actual Vf produced.</li>
</ul>

<h2>3.1.5 Base Parameter</h2>

<p>This pane updates dynamically based on the selected generator:</p>

<details class="collapsible" open>
  <summary>Monte Carlo extras</summary>
  <p><strong>Safe distance between fibers</strong> — minimum allowable
  centre-to-centre distance for accepting a new fiber. Larger values =
  cleaner mesh but lower achievable Vf.</p>
</details>

<details class="collapsible">
  <summary>RSE extras</summary>
  <p><strong>Lmin</strong> and <strong>Lmax</strong> — minimum and maximum
  allowable inter-fiber distances during expansion. Required.
  <code>Lmax ≥ Lmin &gt; 0</code>.</p>
</details>

<details class="collapsible">
  <summary>User coordinates extras</summary>
  <p>Browse to one or more CSV files. The number of files selected must equal
  the "Number of generated models" below. Each file must contain only two
  columns of <em>(x, y)</em> coordinates referenced to the bottom-left corner
  <code>(0, 0)</code> of the RVE cross-section.</p>
</details>

<h2>3.1.6 Number of generated models</h2>

<p>Used for batch generation, e.g., for Monte-Carlo statistical studies.
All generated models share identical geometric parameters; only the random
fiber positions differ.</p>

<h2>3.1.7 Save folder directory</h2>

<p>Where to write the generated CSV coordinate files and a parameters
summary. Default <code>C:/UDFiber RVE Builder</code>. The folder is created
automatically if it does not exist.</p>

<h2>3.1.8 After clicking OK — outputs and database changes</h2>

<p>Once you click OK the plug-in performs three steps in order:</p>

<ol>
  <li>Generates (or reads) the fiber-centre coordinates and writes them to
      the configured save folder.</li>
  <li>Creates one Abaqus model per requested geometry, named per
      <em>3.1.1 Model Name</em>. Each model contains three parts:
      <code>Fiber</code>, <code>Matrix</code>, and the merged
      <code>UDComposite</code>.</li>
  <li>Populates <code>UDComposite</code> with named cell, edge and face
      Sets that all later tabs rely on.</li>
</ol>

<h3>Files written to disk</h3>

<table>
  <thead><tr><th>File</th><th>Purpose</th></tr></thead>
  <tbody>
    <tr><td><code>RVE2D_&lt;N&gt;Inclusions_IncCoordinates&lt;ii&gt;.csv</code></td>
        <td>Two-column (x, y) fiber-centre coordinates, one file per model.</td></tr>
    <tr><td><code>RVE2D_parameters_output_Vf_&lt;v&gt;_xy_&lt;n&gt;units_&lt;N&gt;fiber.txt</code></td>
        <td>Summary report: target / actual Vf, RVE dimensions, fiber count and timing.</td></tr>
  </tbody>
</table>

<h3>Statistical-distribution files (per configuration)</h3>

<p>To help you check that the random fiber distribution behaves as
expected, the plug-in also writes per-configuration statistics files
alongside the CSV coordinates:</p>

<table>
  <thead><tr><th>File</th><th>Contents</th></tr></thead>
  <tbody>
    <tr><td><code>first_nearest_neighbor_config_&lt;ii&gt;.csv</code></td>
        <td>First nearest-neighbour distance histogram.</td></tr>
    <tr><td><code>second_nearest_neighbor_config_&lt;ii&gt;.csv</code></td>
        <td>Second nearest-neighbour distance histogram.</td></tr>
    <tr><td><code>ripleys_K_function_config_&lt;ii&gt;.csv</code></td>
        <td>Ripley's K function with normalized radius.</td></tr>
    <tr><td><code>pair_distribution_function_config_&lt;ii&gt;.csv</code></td>
        <td>Pair distribution function g(r) with normalized radius.</td></tr>
    <tr><td><code>nn_summary.csv</code></td>
        <td>Cross-configuration summary of nearest-neighbour statistics.</td></tr>
  </tbody>
</table>

<h3>Sets created on UDComposite</h3>

<table class="field-table">
  <thead><tr><th>Set name</th><th>Geometry</th><th>Purpose</th></tr></thead>
  <tbody>
    <tr><td><code>Set-Fiber</code></td><td>Cells</td>
        <td>All fiber cells — used for fiber material assignment.</td></tr>
    <tr><td><code>Set-Matrix</code></td><td>Cells</td>
        <td>All matrix cells — used for matrix material assignment and void insertion.</td></tr>
    <tr><td><code>Set-Arc</code></td><td>Edges</td>
        <td>Arc segments of fibers crossing the RVE boundary — used for circumferential mesh seeds.</td></tr>
    <tr><td><code>Set-full-circle</code></td><td>Edges</td>
        <td>Full-circle fiber boundaries (interior fibers) — used for circumferential mesh seeds.</td></tr>
    <tr><td><code>Set-Fiber-Straightness</code> (and -vertical, -horizontal)</td><td>Edges</td>
        <td>Straight fiber edges along the RVE faces — used for cross-section seeding.</td></tr>
    <tr><td><code>Set-Matrix-Straightness</code> (and -vertical, -horizontal)</td><td>Edges</td>
        <td>Straight matrix edges along the RVE faces — used for cross-section seeding.</td></tr>
    <tr><td><code>Set-thickness-Straightness</code></td><td>Edges</td>
        <td>Edges along the fiber-axis (X) direction — used for through-thickness seeding.</td></tr>
  </tbody>
</table>

<div class="callout callout-warn">
  <div class="callout-title">Do not rename the auto-generated Sets</div>
  <p>The Mesh Control, Materials, Void Insertion and Analysis tabs all look
  these Sets up by name. Renaming any of them will cause the later tabs to
  fail. If you need additional Sets, create new ones rather than modifying
  these.</p>
</div>
`;
