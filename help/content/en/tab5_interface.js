// Auto-loaded via <script> tag from index.html
// Edit the HTML inside the template literal below; do NOT change the wrapper.
window.helpContent = window.helpContent || {};
window.helpContent['en/tab5_interface'] = `
<!-- ===== SECTION: tab5_interface ========================================== -->
<h1>3.5 · Interface</h1>

<p>
  The <strong>Interface</strong> tab inserts zero-thickness cohesive seams
  (COH3D8) at the fiber-matrix interface of a meshed RVE, so that subsequent
  elastoplastic or thermal analyses can model the debonding behaviour of
  that interface. The tab works on a <em>copy</em> of the selected model so
  the original mesh is preserved.
</p>

<div class="callout callout-warn">
  <div class="callout-title">Run order</div>
  <p>This tab needs an already-meshed model with materials assigned. Run
  the <strong>Mesh Control</strong> and <strong>Materials</strong> tabs
  first. If you intend to also study void effects, run
  <strong>Void Insertion</strong> before Interface.</p>
</div>

<h2>3.5.1 Select Part</h2>

<ul>
  <li><strong>Model</strong> — drop-down of all open models.</li>
  <li><strong>Part</strong> — typically <code>UDComposite</code>. The
      part list auto-fills with the parts in the chosen model.</li>
</ul>

<h2>3.5.2 Material for interface</h2>

<p>Pick the cohesive material to assign to the COH3D8 seams. The list is
populated from the materials already defined in the chosen model, so define
the interface material on the Materials tab (or in CAE) before opening this
tab.</p>

<h2>3.5.3 Initial Debonding</h2>

<p>One number, <strong>D</strong>, in percent (0–100). It controls how much
of the fiber-matrix interface starts out <em>already debonded</em> at
analysis time.</p>

<ul>
  <li><code>D = 0</code> → every COH3D8 seam is bonded. The cohesive law
      governs progressive damage when load is applied.</li>
  <li><code>D &gt; 0</code> → that fraction of the seams is removed at
      insertion, simulating manufacturing defects, prior fatigue, or
      voids that already touch the interface.</li>
  <li>If the model has voids that already replace part of the fiber
      interface (Void Insertion tab), those voids are counted as part of
      <code>D</code>. So with 3% voids touching the interface, asking for
      <code>D = 5%</code> deletes another 2% of cohesive elements.</li>
  <li>D is capped so that each independent fiber keeps at least one bonded
      cohesive element. This avoids floating fibers that would crash the
      solver.</li>
</ul>

<h2>3.5.4 Select Model Range for Interface</h2>

<p>Same batch control as the other tabs (Current / All / Selected numbers).
"All Models" applies to every model that shares the primary name of the
selected model.</p>

<h2>3.5.5 After clicking OK</h2>

<p>For every targeted model the plug-in:</p>
<ol>
  <li>Duplicates the model into a new model named
      <code>&lt;model&gt;_Interface_D&lt;final D %&gt;</code> so the
      original mesh is untouched.</li>
  <li>Generates COH3D8 cohesive elements at every fiber-matrix interface in
      the copy, using the chosen cohesive material.</li>
  <li>If <code>D &gt; 0</code>, removes the requested fraction of cohesive
      elements (random selection, voids and the per-fiber minimum already
      accounted for).</li>
  <li>Prints a summary to the message area: model name, fiber / matrix
      element-set names, total interface faces, COH3D8 elements created,
      inserted nodes, independent fiber-interface geometries, void-induced
      <code>D_void</code>, user <code>D</code>, final <code>D</code>.</li>
  <li>Also writes the same summary to a plain-text report on disk:
      <code>Interface_Information_&lt;model&gt;.txt</code> for a single-model
      run, or <code>Interface_Information_Batch_D&lt;D&gt;.txt</code> for
      batch runs. If a report with that name already exists in the working
      directory, a suffix is appended so previous reports are not
      overwritten.</li>
</ol>

<h2>3.5.6 What changes downstream</h2>

<p>The Interface tab does not run analyses by itself. It only prepares the
mesh. Subsequent runs of the <strong>Analysis</strong> tab on these
<code>*_Interface</code> models behave as follows:</p>

<table class="field-table">
  <thead><tr><th>Analysis type</th><th>Behaviour on interface-enabled models</th></tr></thead>
  <tbody>
    <tr>
      <td><strong>Elastic + CTE</strong> / Viscoelastic / Viscoelastic Freq</td>
      <td>Standard PBC kernel runs on the duplicated model. The cohesive
      seams behave according to their material's elastic stiffness.</td>
    </tr>
    <tr>
      <td><strong>Elastoplastic (Uniaxial / Biaxial)</strong></td>
      <td>When the chosen model is an <code>*_Interface</code> model with
      <code>D &gt; 0</code> (or any cohesive seams present), the dispatcher
      automatically routes to <code>PBC_UDFRP_Elastoplastic_interface</code>
      instead of the default kernel. This variant handles the COH3D8
      elements during equation generation and step setup.</td>
    </tr>
    <tr>
      <td><strong>Thermal Conductivity</strong></td>
      <td>Same routing: the dispatcher uses
      <code>PBC_UDFRP_thermal_conductivity_Interfaceh</code> so the cohesive
      seams contribute the correct conductivity (or thermal resistance)
      through the interface.</td>
    </tr>
  </tbody>
</table>

<div class="callout callout-tip">
  <div class="callout-title">Tips</div>
  <ul>
    <li>If you want to compare <em>with</em> and <em>without</em> interface,
    keep the original model untouched and run Analysis on both
    <code>&lt;model&gt;</code> and <code>&lt;model&gt;_Interface</code>.</li>
    <li>Cohesive material units must match the rest of the model (consistent
    set of MPa / mm / etc.).</li>
    <li>Re-running this tab on the same source model creates a fresh
    <code>*_Interface</code> copy; the previous copy stays as-is unless you
    delete it manually.</li>
  </ul>
</div>
`;
