// Auto-loaded via <script> tag from index.html
// Edit the HTML inside the template literal below; do NOT change the wrapper.
window.helpContent = window.helpContent || {};
window.helpContent['en/qanda'] = `
<\!-- ===== SECTION: qanda =================================================== -->
<h1>4 · Q&amp;A · How it works inside</h1>

<p>
  This section gives a peek under the hood — the core working principles of
  each tab in plain-language Q&amp;A form. The goal is to help you reason
  about what the plug-in is doing and to debug unexpected behaviour, not to
  replace the mathematical references listed in <em>6 · References</em>.
</p>

<h2>Create RVE</h2>

<details class="collapsible" open>
  <summary>Q. How are the random fiber circles actually placed in the RVE
  cross-section?</summary>
  <p>For Monte Carlo, the generator repeatedly draws a candidate centre
  inside the RVE rectangle and accepts it if every existing fiber is at
  least the user-supplied <em>safe distance</em> away. Rejected candidates
  are simply re-drawn. For RSE, fibers are first scattered freely, then a
  "growth" phase iteratively repels and re-positions them until inter-fiber
  distances satisfy <code>Lmin ≤ d ≤ Lmax</code>. Both methods enforce
  periodicity at the four RVE faces: a fiber that crosses one face is
  duplicated on the opposite face so the cross-section tiles seamlessly.</p>
</details>

<details class="collapsible">
  <summary>Q. How does the plug-in turn (x, y) coordinates into Abaqus
  parts and Sets?</summary>
  <p>The 2D fiber circles and the rectangular RVE boundary are written into
  an Abaqus sketch as circle and line equations. The plug-in then
  <em>analytically</em> intersects each circle with each line — these
  closed-form intersections (rather than numerical picking) determine the
  exact edges, arcs and faces of the cross-section. The 2D sketch is
  extruded along X to form the 3D <code>UDComposite</code> part. Finally,
  <code>part.findAt(point)</code> with carefully chosen probe points is
  used to collect cells, edges and faces into the named Sets listed in
  <em>3.1.8</em> — every Set is built deterministically from the geometry,
  not from indices.</p>
</details>

<details class="collapsible">
  <summary>Q. Why is the actual Vf sometimes slightly off from what I
  asked?</summary>
  <p>The integer fiber count <code>N</code> is rounded from
  <code>(Vf · a · b) / (π · df² / 4)</code>. Either Vf or the cross-section
  dimensions must absorb that rounding — the <em>Control Options</em>
  radio decides which one. The actual values are recorded in the
  <code>parameters_output</code> TXT file.</p>
</details>

<h2>Mesh Control</h2>

<details class="collapsible">
  <summary>Q. Why does the plug-in restrict the element types I can
  pick?</summary>
  <p>Periodic boundary conditions are applied by tying nodes on opposite
  faces of the RVE together. That requires the mesh to be conforming on
  paired faces, which is guaranteed only with the element families
  exposed in <em>Mesh Type</em> and <em>Element Shape</em>. Substituting
  other element types manually (e.g., tetrahedra) can break the PBC step.</p>
</details>

<details class="collapsible">
  <summary>Q. How does the seed-count formula in 3.2.3 follow from
  <code>NR</code>?</summary>
  <p>Each fiber circle of diameter <code>df</code> is approximated by a
  polygon with <code>NR</code> seeds, giving a side length of
  <code>π · df / NR</code>. Using the same characteristic size on every
  edge keeps the cross-section mesh roughly uniform, which is why the
  recommended <code>NL = L · NR / (π · df)</code>. The interactive
  calculator on that page is just a UI for this formula.</p>
</details>

<h2>Materials</h2>

<details class="collapsible">
  <summary>Q. Why does batch mode write a temporary ODB?</summary>
  <p>Abaqus does not expose an API to copy a material definition directly
  from one in-memory model to another. The workaround is to write the
  source model's materials to an ODB
  (<code>materialsFromOdb</code>-compatible) and read them back in each
  target model. That is what the temporary file
  <code>UsetoCopyMaterial_&lt;model&gt;.odb</code> is for; the plug-in
  removes it once assignments are complete.</p>
</details>

<h2>Void Insertion</h2>

<details class="collapsible">
  <summary>Q. How does the plug-in decide which matrix elements become
  voids?</summary>
  <p>Once the mesh exists, every matrix element is labelled either
  <em>fiber-adjacent</em> (shares a node or face with a <code>Set-Fiber</code>
  cell) or <em>inter-matrix</em> (everything else). The plug-in then walks
  the labelled lists, picking elements to delete in proportions that
  match the requested weight <code>w</code> and the size strategy
  (<code>theta</code> or random). Deletion stops when the cumulative
  removed volume reaches the requested Vf.</p>
</details>

<details class="collapsible">
  <summary>Q. Why does the achieved <code>w</code> sometimes differ from
  the target?</summary>
  <p>The pool of fiber-adjacent elements is finite — at high Vf or extreme
  <code>w</code> values, one category may run out of candidates before the
  target is met. The <em>Priority</em> control tells the plug-in which
  invariant to keep: strict <code>w</code> (sizes may shift),
  strict sizes (<code>w</code> may shift), or best-effort. The
  <code>void_summary_report.txt</code> always reports the realised
  values.</p>
</details>

<h2>Analysis</h2>

<details class="collapsible">
  <summary>Q. What is the role of "periodic boundary conditions"?</summary>
  <p>The RVE is a finite chunk of a notionally infinite composite. To
  recover the bulk effective response, displacements on opposite RVE faces
  are constrained to differ by a constant macroscopic strain — that is the
  PBC. EasyPBC implements these constraints as linear equations between
  matched nodes, which is why mesh mapping accuracy and the choice of
  element types matter.</p>
</details>

<details class="collapsible">
  <summary>Q. How are the elastic moduli E11–G23 actually computed?</summary>
  <p>For each requested modulus, the plug-in applies a unit macroscopic
  strain (e.g., ε11 = 1, others = 0) and lets Abaqus solve the RVE under
  PBC. The volume-averaged stress is then read from the ODB and the
  modulus is computed as the corresponding stress / strain ratio. Six
  independent load cases yield the full orthotropic stiffness
  (E11/E22/E33 + G12/G13/G23).</p>
</details>

<details class="collapsible">
  <summary>Q. What changes for the viscoelastic analyses?</summary>
  <p>Same PBC machinery, but the constitutive law is now time- or
  frequency-dependent. <strong>Time domain</strong> runs a relaxation
  step under sustained strain and samples E(t) or G(t) at user-defined
  time points. <strong>Frequency domain</strong> uses Abaqus's
  steady-state dynamic step to sweep frequency and report complex moduli
  E*(ω) or G*(ω).</p>
</details>

<details class="collapsible">
  <summary>Q. What does the elasto-plastic analysis actually solve?</summary>
  <p>It applies user-prescribed macroscopic strains (single or biaxial
  with an off-axis angle) under PBC and lets Abaqus integrate the
  nonlinear constitutive law of fiber + matrix step by step. If you
  provide a UMAT, that subroutine takes over the matrix's constitutive
  behaviour; otherwise the plug-in uses whatever you defined in the
  Materials tab. The stress-strain history is then exported to CSV for
  post-processing.</p>
</details>

<details class="collapsible">
  <summary>Q. And the thermal conductivity analysis?</summary>
  <p>Periodic temperature boundary conditions replace mechanical ones:
  a unit temperature gradient is applied in each requested direction
  while the opposite face is held at the reference temperature.
  Abaqus's steady-state heat-transfer solver then yields the
  volume-averaged heat flux, from which K11–K33 are recovered.</p>
</details>

<div class="callout callout-tip">
  <div class="callout-title">Want more depth?</div>
  <p>For the mathematical derivations behind PBC, RSE/Monte-Carlo fiber
  generation, and the bridging / Kerner micromechanical framework used in
  the source paper, see <em>6 · References</em>.</p>
</div>
`;
