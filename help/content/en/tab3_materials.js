// Auto-loaded via <script> tag from index.html
// Edit the HTML inside the template literal below; do NOT change the wrapper.
window.helpContent = window.helpContent || {};
window.helpContent['en/tab3_materials'] = `
<\!-- ===== SECTION: tab3_materials ========================================== -->
<h1>3.3 · Materials</h1>

<p>
  The <strong>Materials</strong> tab assigns fiber and matrix materials to
  the meshed RVE and creates the corresponding sections. It supports batch
  propagation across multiple models.
</p>

<h2>Prerequisite</h2>

<div class="callout callout-warn">
  <div class="callout-title">Define materials first</div>
  <p>This tab does <em>not</em> create materials — it only assigns existing
  ones. Before opening this tab, define the fiber material and matrix
  material in Abaqus's standard Material module on at least one of the
  target models. Only that model needs both materials defined; the batch
  operation copies them to the others.</p>
</div>

<h2>3.3.1 Select materials</h2>

<p>Two drop-downs:</p>
<ul>
  <li><strong>Fiber</strong> — select the material previously defined for
      the fiber phase.</li>
  <li><strong>Matrix</strong> — select the material previously defined for
      the matrix phase.</li>
</ul>

<p>Click OK to:</p>
<ol>
  <li>Create one solid section per material.</li>
  <li>Assign sections to the <code>Set-Fiber</code> and
      <code>Set-Matrix</code> sets that were created during Create RVE.</li>
  <li>Set material orientation (axis along the X direction).</li>
</ol>

<h2>3.3.2 Select Model Range for Material</h2>

<p>Same batch control as on other tabs (Current / All / Selected numbers).
When applied to multiple models the plug-in uses Abaqus's
<code>materialsFromOdb</code> facility to copy material definitions from the
"source" model to the others before assigning sections — Abaqus has no
built-in cross-model material copy, so this step generates a temporary ODB
and reads materials back from it.</p>

<div class="callout callout-note">
  <div class="callout-title">Error messages during batch material copy</div>
  <p>You may see a few harmless warnings while the temporary ODB is being
  written. They can be ignored as long as the section assignments complete
  successfully.</p>
</div>

<h2>What if a model is missing the material?</h2>

<p>If you select <strong>All Models</strong> or
<strong>Selected numbers</strong> and some target models do not yet have
the fiber/matrix materials defined, the plug-in copies them in
automatically from the source model — you only need to define materials in
one model.</p>

<h2>3.3.3 After clicking OK — outputs and database changes</h2>

<p>For each affected model the plug-in:</p>
<ol>
  <li>Creates one solid section per material (<code>Fiber-Section</code>
      and <code>Matrix-Section</code>).</li>
  <li>Assigns those sections to the <code>Set-Fiber</code> and
      <code>Set-Matrix</code> sets created during Create RVE.</li>
  <li>Sets material orientation along the fiber axis (X direction).</li>
  <li>For batch mode: creates a temporary <code>.odb</code> in the working
      directory, used only to copy material definitions across models, then
      cleans it up.</li>
</ol>

<p>No permanent files are left in the working directory after this tab
completes successfully.</p>
`;
