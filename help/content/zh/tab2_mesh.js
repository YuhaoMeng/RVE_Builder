// Auto-loaded via <script> tag from index.html
// Edit the HTML inside the template literal below; do NOT change the wrapper.
window.helpContent = window.helpContent || {};
window.helpContent['zh/tab2_mesh'] = `
<\!-- ===== SECTION: tab2_mesh (中文) ======================================== -->
<h1>3.2 · 网格控制</h1>

<p>
  <strong>Mesh Control</strong> 选项卡为选定的 RVE 模型布置种子并执行网格化。
  也可以根据后续要做的分析切换单元类型和形状。
</p>

<figure class="figure">
  <img src="images/Mesh_Seed_Diagram.png" alt="网格种子示意">
  <figcaption>图 2 — 各个种子控制参数的作用位置。</figcaption>
</figure>

<h2>3.2.1 选择模型（Select Model）</h2>

<p>下拉菜单选择要划分网格的模型和 Part。插件设计为针对 <code>UDComposite</code>
Part — 除非自定义过几何，否则保持选择即可。</p>

<h2>3.2.2 网格化模型范围（Select Model Range for Meshing）</h2>

<p>所有选项卡通用的批量控件：</p>
<ul>
  <li><strong>Current Model</strong> — 仅划分当前选中的模型。</li>
  <li><strong>All Models</strong> — 对所有与当前模型同主名的模型划分网格。</li>
  <li><strong>Selected numbers</strong> — 自定义编号列表，用 <code>-</code>
      表示范围，用 <code>,</code> 分隔不同项。例：<code>1, 4-9</code>。</li>
</ul>

<h2>3.2.3 种子控制（Seeds Control by Number）</h2>

<table class="field-table">
  <thead><tr><th>字段</th><th>默认</th><th>含义</th></tr></thead>
  <tbody>
    <tr><td>Circle-dominant and Arc</td><td>12</td>
        <td>纤维圆和弧的种子数（横截面视角）。</td></tr>
    <tr><td>Cross-Section Edges</td><td>20</td>
        <td>RVE 外边界横截面的种子数。</td></tr>
    <tr><td>Along Fiber Direction Edges</td><td>10</td>
        <td>沿纤维轴向（X 方向）的种子数。</td></tr>
    <tr><td>Minimum Size Control</td><td>0.1</td>
        <td>最小单元尺寸因子（传递给 Abaqus 网格器）。</td></tr>
  </tbody>
</table>

<h3>推荐种子数 —— 计算公式</h3>

<p>
  设 <code>NR</code> 为纤维圆周上布置的种子数（即
  <strong>Circle-dominant and Arc</strong> 一栏的值），由此推得纤维上的
  <em>近似单元尺寸</em>为：
</p>
<p style="text-align:center;">
  $$ \\text{size}_{\\mathrm{approx}} \\;=\\; \\dfrac{\\pi \\, d_f}{N_R} $$
</p>
<p>
  为使横截面 / 厚度方向的网格与之保持一致，长度为 <code>L</code> 的边上
  应布置的种子数 <code>NL</code>：
</p>
<p style="text-align:center;">
  $$ N_L \\;=\\; \\dfrac{L}{\\text{size}_{\\mathrm{approx}}} \\;=\\; \\dfrac{L \\, N_R}{\\pi \\, d_f} $$
</p>
<p>
  对 <strong>Cross-Section Edges</strong>，取 <code>L = a</code>
  （或 <code>b</code>）；对 <strong>Along Fiber Direction Edges</strong>，
  取 <code>L = t</code>。
</p>

<div id="seed-calc" class="seed-calculator">
  <h4>种子数交互计算器</h4>
  <div class="calc-grid">
    <label>纤维直径 d<sub>f</sub>
      <input type="number" data-calc="df" value="7" step="0.1" min="0">
    </label>
    <label>纤维上种子数 N<sub>R</sub>
      <input type="number" data-calc="nr" value="12" step="1" min="1">
    </label>
    <label>边长 L
      <input type="number" data-calc="l" value="50" step="1" min="0">
    </label>
  </div>
  <div class="calc-output">
    <div>近似单元尺寸：<span data-calc="size">—</span></div>
    <div>推荐 N<sub>L</sub>：<span data-calc="nl">—</span></div>
  </div>
</div>

<div class="callout callout-note">
  <p>这只是把上面的公式做了 UI 包装。修改任意字段即可实时看到结果。
  Cross-Section Edges 把 <code>L</code> 填 RVE 的宽 / 高；
  Along Fiber Direction Edges 把 <code>L</code> 填 RVE 厚度。</p>
</div>

<h2>3.2.4 网格类型选择（Mesh Type Selection）</h2>

<p>请<em>在</em>网格化前选好分析类型——单元库依赖这个选择。</p>

<table class="field-table">
  <thead><tr><th>网格类型</th><th>线性单元</th><th>对应分析</th></tr></thead>
  <tbody>
    <tr><td>Mechanical Analysis (C3D8)</td><td>C3D8 / C3D6</td>
        <td>弹性、CTE、粘弹性、弹塑性。</td></tr>
    <tr><td>Thermal Analysis (DC3D8)</td><td>DC3D8 / DC3D6</td>
        <td>热导率。</td></tr>
    <tr><td>Thermo-Mechanical Coupled (C3D8T)</td><td>C3D8T / C3D6T</td>
        <td>热-力耦合分析。</td></tr>
  </tbody>
</table>

<h2>3.2.5 单元选项（Element Options）</h2>

<p>单元升级开关：</p>

<div class="inline-tabs">
  <div class="tab-buttons">
    <button class="tab-btn">力学 / 耦合</button>
    <button class="tab-btn">热</button>
  </div>
  <div class="tab-panel">
    <ul>
      <li><strong>Quadratic (20-nodes)</strong> — C3D8 → C3D20（C3D6 → C3D15）。
          精度更高，但计算量大。</li>
      <li><strong>Reduced Integration (R)</strong> — 添加 R 后缀（如 C3D8R）。
          网格非常粗时需注意沙漏模式。</li>
      <li><strong>Hybrid Formulation (H)</strong> — 添加 H 后缀。
          基体接近不可压缩时必需。</li>
    </ul>
  </div>
  <div class="tab-panel">
    <ul>
      <li><strong>Quadratic (20-node)</strong> — DC3D8 → DC3D20。</li>
      <li><strong>Reduced Integration (R)</strong></li>
      <li><strong>Convection/Diffusion (C)</strong></li>
      <li><strong>Dispersion Control (D)</strong></li>
    </ul>
    <div class="callout callout-note">
      <p><strong>热单元规则：</strong>只有部分组合是有效的 Abaqus 单元符号。
      无效组合在网格化时会被忽略。</p>
    </div>
  </div>
</div>

<h2>3.2.6 单元形状（Element Shape）</h2>

<ul>
  <li><strong>HEX-dominated, C3D8 + C3D6</strong> — 平衡之选，默认。</li>
  <li><strong>HEX-dominated, C3D20 + C3D15</strong> — 二次单元升级版。</li>
  <li><strong>WEDGE, C3D6</strong> — 仅楔形单元。当 Vf 极高，六面体网格
      失败时使用。</li>
</ul>

<div class="callout callout-warn">
  <div class="callout-title">其他单元类型已被限制</div>
  <p>为保证后续可施加 PBC，插件限制了可选单元类型。在插件外手动替换其他
  单元可能导致 Analysis 选项卡失败。</p>
</div>

<h2>3.2.7 点击 OK 之后 —— 输出文件与数据库变化</h2>

<p>
  本选项卡不会写出额外文件。所选模型直接在原位完成网格化，结果可在 Abaqus
  的 Mesh 模块查看。具体动作：
</p>
<ul>
  <li>按上面输入的种子数布置 edge seeds。</li>
  <li>按所选单元形状生成网格。</li>
  <li>按 Mesh Type + Element Options 设置每个 cell 的单元类型
      （如 C3D8R、C3D20H、DC3D8）。</li>
  <li>若需要全局尺寸因子，按 <em>Minimum Size Control</em> 计算。</li>
</ul>

<div class="callout callout-tip">
  <div class="callout-title">验证</div>
  <p>网格化完成后，可切换到 Abaqus 的 Mesh 模块检查单元数量和质量。
  <code>UDComposite</code> Part 现在已包含可用于 Materials 和 Analysis
  选项卡的网格实例。</p>
</div>
`;
