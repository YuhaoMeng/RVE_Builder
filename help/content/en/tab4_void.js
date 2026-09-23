// Auto-loaded via <script> tag from index.html
// Edit the HTML inside the template literal below; do NOT change the wrapper.
window.helpContent = window.helpContent || {};
window.helpContent['en/tab4_void'] = `
<\!-- ===== SECTION: tab4_void =============================================== -->
<h1>3.4 · Void Insertion</h1>

<p>
  The <strong>Void Insertion</strong> tab inserts microvoids into the matrix
  of an already-meshed RVE. This page focuses on what to click and what to
  watch out for; theoretical background is intentionally kept brief.
</p>

<div class="callout callout-warn">
  <div class="callout-title">Mesh first</div>
  <p>This tab needs an existing mesh. Run the <strong>Mesh Control</strong>
  tab on the model(s) before opening Void Insertion.</p>
</div>

<h2>3.4.1 Select Model and Part</h2>

<ul>
  <li><strong>Model</strong> — drop-down of all open models.</li>
  <li><strong>Part</strong> — typically <code>UDComposite</code>. The
      drop-down auto-fills with the parts in the chosen model.</li>
</ul>

<h2>3.4.2 Void Volume Fraction</h2>

<p>A single number, in <strong>percent</strong>. Default <code>5.0</code>.
This is the total void volume fraction relative to the entire RVE volume.
The plug-in will distribute exactly this fraction across the inserted
voids — no implicit cap is applied beyond physical feasibility (i.e., you
cannot ask for a Vvoid larger than the actual matrix volume left after
the fibers have been placed).</p>

<h2>3.4.3 Void Distribution</h2>

<p>Pick how voids are distributed between two regions defined inside the
plug-in:</p>

<ul>
  <li><strong>Random Number Method</strong> — distribution is automatic; the
      plug-in samples a random weight on each insertion attempt.</li>
  <li><strong>Custom (w, 0–1)</strong> — type a weight <code>w</code> in
      <code>[0, 1]</code> that controls the volumetric split between the
      two void types described below.</li>
</ul>

<h3>How the two void types are defined in the plug-in</h3>

<p>Internally, every candidate matrix element is classified into exactly one
of two categories before any void is inserted:</p>

<table class="field-table">
  <thead><tr><th>Void type</th><th>Definition (rule used by the plug-in)</th></tr></thead>
  <tbody>
    <tr>
      <td><strong>Fiber-adjacent</strong></td>
      <td>Matrix elements that share at least one node (or face) with a
          <code>Set-Fiber</code> cell. These elements form the thin matrix
          shell wrapping each fiber.</td>
    </tr>
    <tr>
      <td><strong>Inter-matrix</strong></td>
      <td>All remaining matrix elements — i.e., matrix elements that are not
          in contact with any fiber. These tend to lie in the bulk channels
          between fibers.</td>
    </tr>
  </tbody>
</table>

<p>The weight <code>w</code> then controls the volume ratio:</p>
<ul>
  <li><code>w = 0</code> → <em>all</em> void volume is taken from
      <strong>inter-matrix</strong> elements.</li>
  <li><code>w = 1</code> → <em>all</em> void volume is taken from
      <strong>fiber-adjacent</strong> elements.</li>
  <li><code>w ∈ (0, 1)</code> → mixes the two: a fraction <code>w</code>
      of the requested void volume comes from fiber-adjacent elements, and
      <code>1 − w</code> from inter-matrix elements.</li>
</ul>

<div class="callout callout-note">
  <p>The classification is performed once at the beginning of the operation
  using the meshed <code>UDComposite</code> part. Voids are then carved out
  by deleting full elements from the appropriate category until the
  requested volume fraction is reached.</p>
</div>

<h2>3.4.4 Void Size</h2>

<ul>
  <li><strong>Random Void Size</strong> — sizes are randomized within
      defaults.</li>
  <li><strong>Custom Size (theta)</strong> — type an integer
      <code>theta</code> ≥ 1. <code>theta</code> is the number of voids; the
      single-void volume fraction becomes <code>Vvoid / theta</code>.</li>
</ul>

<div class="callout callout-warn">
  <div class="callout-title">When theta = 1</div>
  <p>If you set <code>theta = 1</code>, the distribution weight <code>w</code>
  must be set to <code>0</code>, <code>1</code>, or <strong>Random</strong> —
  not a fractional value. A single void cannot be split between two regions.</p>
</div>

<h2>3.4.5 Priority</h2>

<p>Sets what to keep when constraints conflict (e.g., the requested
<code>w</code> cannot be exactly satisfied with the available space):</p>

<table class="field-table">
  <thead><tr><th>Option</th><th>What stays exact</th></tr></thead>
  <tbody>
    <tr><td><strong>Distribution Priority (strict w)</strong></td>
        <td><code>w</code> is enforced; void sizes may shift.</td></tr>
    <tr><td><strong>Size Priority (allow w deviation)</strong></td>
        <td>void sizes stay close to the target; <code>w</code> may shift.</td></tr>
    <tr><td><strong>No Intervention</strong></td>
        <td>plug-in applies a best-effort placement.</td></tr>
  </tbody>
</table>

<div class="callout callout-note">
  <div class="callout-title">Vvoid is always honoured</div>
  <p>Whatever you choose under Priority, the requested void volume fraction
  <code>Vvoid</code> is the one target that is never relaxed: a final
  correction pass adds or releases boundary elements, using any void, until
  the total is within 99%-101% of the target. Only <em>w</em> and
  <em>theta</em> are negotiable. If even that pass cannot reach the band,
  because the free element pool is exhausted, the summary table says so
  instead of reporting success.</p>
</div>

<h2>3.4.6 Void Shape Factor (β) — experimental</h2>

<div class="callout callout-warn">
  <div class="callout-title">Experimental feature under development</div>
  <p>The shape factor is a test feature. Its interface and behaviour may
  change, and the resulting void shapes have not been validated. Leave it
  disabled for production studies.</p>
</div>

<p>By default, voids grow with a purely distance-weighted rule that produces
roughly spherical clusters. The optional <strong>β</strong> shape factor biases
the candidate weighting toward an ellipsoid envelope so voids may grow as
prolate or oblate shapes.</p>

<table class="field-table">
  <thead><tr><th>Setting</th><th>Effect</th></tr></thead>
  <tbody>
    <tr><td><strong>Enable shape factor</strong></td>
        <td>Off → legacy distance-only rule (spherical voids). On → use the
            envelope described below.</td></tr>
    <tr><td><strong>β value (>0)</strong></td>
        <td>A single positive number. <code>β = 1</code> → sphere;
            <code>β > 1</code> → prolate, axes <code>(β, 1, 1)</code> along the
            fiber X-axis; <code>β < 1</code> → oblate, axes
            <code>(1, 1, β)</code> with the short axis along Z. No additional
            shape-kind radio is needed — β alone selects the form.</td></tr>
    <tr><td><strong>Unified vs. Split</strong></td>
        <td>Unified uses the same β for both fiber-adjacent and inter-matrix
            voids. Split lets you choose two β values, applied per pool.</td></tr>
    <tr><td><strong>Orientation</strong></td>
        <td><em>Random SO(3)</em> draws a uniformly random rotation for each
            void's envelope; <em>Orthogonal</em> keeps the envelope axis-aligned
            (prolate aligned with X, oblate compressed along Z).</td></tr>
    <tr><td><strong>θ* (mean voids per fiber)</strong></td>
        <td>Optional informational input. When active, the summary report
            records θ* and implies <code>θ = θ* × Nf</code>. Existing void-count
            (θ) and Vf rules still take priority.</td></tr>
  </tbody>
</table>

<div class="callout callout-note">
  <p>β only modifies the <em>candidate weighting</em> during growth. All other
  rules (target Vf, w, θ, fiber-isolation guard, island-prevention) are
  enforced exactly as before, so β is a soft preference, not a hard constraint.</p>
</div>

<h2>3.4.7 Select Model Range for Void Insertion</h2>

<p>Same batch control as the other tabs (Current / All / Selected numbers).
"All Models" applies to every model sharing the primary name of the selected
model.</p>

<h2>3.4.8 After clicking OK — outputs and database changes</h2>

<p>For each model the plug-in:</p>
<ol>
  <li>Classifies every matrix element as <em>fiber-adjacent</em> or
      <em>inter-matrix</em> (see 3.4.3).</li>
  <li>Removes a number of matrix elements from the appropriate category to
      form the voids, until the requested Vvoid is reached.</li>
  <li>Tags the deleted region with a Set named <code>Set-Void</code> so it
      can be inspected in Abaqus's Mesh module.</li>
  <li>Updates the section assignments so the void region carries no
      material.</li>
  <li>Writes a dedicated statistics folder to disk so you can verify that
      the achieved distribution matches your inputs.</li>
</ol>

<h3>What is printed in the message area</h3>

<p>The message area stays short, because the numbers are written to disk
anyway. One line is printed per model while it is processed, and one summary
table once the batch is finished:</p>

<pre>Inserting voids into 5 models; target Vvoid = 5.0000%.
  [1/5] RVE_..._Model_1: 12 void(s), Vvoid = 5.0132%, OK (34.2 s)
  ...
Void insertion summary: 5 models -- 4 within tolerance, 1 relaxed, 0 not met
Target: Vvoid = 5.0000%, theta = 12, w = 0.500
  model             voids  Vvoid (%)    dev (%)       w  time (s)  status
  RVE_..._Model_1      12     5.0132    +0.0132   0.502      34.2  OK
  RVE_..._Model_3      11     5.0410    +0.0410   0.480     151.7  relaxed: theta, w</pre>

<p>The <em>status</em> column is <code>OK</code> when every target was met
within its strict tolerance, <code>relaxed: theta, w</code> when a tolerance
had to be relaxed to converge, and a short message when a target could not be
reached at all. A message about <code>Vvoid</code> always takes precedence,
since that is the target the plug-in must meet. A frequent one is
<code>w = 0.50 unreachable: every matrix element touches a fiber</code>, which
appears at a high fiber volume fraction on a coarse mesh: there are no
inter-matrix elements to place voids in, so w is fixed at 1 by the mesh.
Refine the mesh or use w = 1 for such models. Per-model details stay in the
statistics folder below.</p>

<h3>Statistics folder written to disk</h3>

<p>The plug-in creates one folder per run, named
<code>Void_Statistics_&lt;model&gt;</code>, in the
Abaqus working directory. Contents:</p>

<table>
  <thead><tr><th>File</th><th>Contents</th></tr></thead>
  <tbody>
    <tr><td><code>void_summary_report.txt</code></td>
        <td>Top-level report — user inputs, RVE dimensions, target vs.
        <strong>actual</strong> Vvoid, near-fiber / inter-matrix split,
        actual <code>w</code> value, deviation from target. <em>Open this
        first.</em></td></tr>
    <tr><td><code>void_sizes.csv</code></td>
        <td>Per-void: ID, type (near-fiber / inter-matrix), volume,
        element count, centroid (x, y, z), plus the PCA envelope:
        three sorted half-axes <code>(h1, h2, h3)</code>, the three
        direction cosine vectors <code>(e1, e2, e3)</code>, and the
        cosine similarity of the principal axis <code>e1</code> to the
        global fiber X-axis.</td></tr>
    <tr><td><code>void_fiber_surface_breakdown.csv</code></td>
        <td>Per-fiber surface destruction: fiber ID, number of interface
        element faces (also used as the perimeter proxy), number of broken
        faces, and ratio <code>r_i = broken / total</code>.</td></tr>
    <tr><td><code>void_nn_distances.csv</code></td>
        <td>First- and second-nearest-neighbour distances between voids.</td></tr>
    <tr><td><code>void_ripleys_k.csv</code></td>
        <td>Ripley's K function (when applicable).</td></tr>
    <tr><td><code>void_pair_distribution.csv</code></td>
        <td>Pair distribution g(r) of void centres.</td></tr>
    <tr><td><code>void_fiber_distances.csv</code></td>
        <td>Distance from each void to the nearest fibers (NN1, NN2).</td></tr>
  </tbody>
</table>

<h3>Fiber-surface destruction metrics</h3>

<p>When fiber centres are available, <code>void_summary_report.txt</code> ends
with five concentration indicators of how the inserted voids broke the
fiber–matrix interface. An interface face is an element face shared by
a fiber element and a matrix or void element; it is broken when that
neighbour is a void element. Let <code>r_i</code> be the broken-face ratio on
fiber <code>i</code> and let <code>N_f</code> be the number of fibres:</p>

<table class="field-table">
  <thead><tr><th>Indicator</th><th>Definition / interpretation</th></tr></thead>
  <tbody>
    <tr><td><code>f_fiber</code></td>
        <td>Fraction of fibres with <em>any</em> destruction
            (count of <code>r_i > 0</code> divided by <code>N_f</code>).</td></tr>
    <tr><td><code>f_area</code></td>
        <td>Overall broken-area ratio = total broken interface faces /
            total interface faces summed across all fibres.</td></tr>
    <tr><td><code>r_avg_broken</code></td>
        <td>Mean of <code>r_i</code> over affected fibres only.</td></tr>
    <tr><td><code>C_focus</code></td>
        <td><code>= r_avg_broken / f_area</code>. Larger values indicate the
            destruction is concentrated on a small number of fibres.</td></tr>
    <tr><td><code>Gini(r_i)</code></td>
        <td>Standard Gini coefficient of the per-fibre ratios. Close to 0
            → spread uniformly; close to 1 → concentrated.</td></tr>
  </tbody>
</table>

<div class="callout callout-warn">
  <div class="callout-title">Void insertion is not always perfect — verify before analysing</div>
  <p>Void placement is a stochastic process running on a finite, already-meshed
  matrix. Depending on the requested Vf, <code>w</code>, <code>theta</code>
  and the local geometry, the actual distribution may deviate slightly from
  the targets — or, in extreme cases, the insertion may fail outright.
  <strong>Always open <code>void_summary_report.txt</code> after the run</strong>
  and check that actual Vf, actual <code>w</code> and the deviation values are
  acceptable for your study before submitting the model for analysis.</p>
</div>

<div class="callout callout-tip">
  <div class="callout-title">Tips</div>
  <ul>
    <li>Insert voids <em>after</em> assigning materials. The plug-in expects
    a fully meshed and material-assigned model.</li>
    <li>If a target Vf cannot be reached (because the matrix region is too
    small), the plug-in stops with a warning rather than corrupting the
    model — adjust your settings and retry.</li>
    <li>Re-running this tab on the same model re-inserts voids on top — make
    a copy first if you want multiple variants.</li>
  </ul>
</div>
`;
