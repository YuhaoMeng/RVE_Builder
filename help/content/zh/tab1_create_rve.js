// Auto-loaded via <script> tag from index.html
// Edit the HTML inside the template literal below; do NOT change the wrapper.
window.helpContent = window.helpContent || {};
window.helpContent['zh/tab1_create_rve'] = `
<\!-- ===== SECTION: tab1_create_rve (中文) ================================== -->
<h1>3.1 · 创建 RVE</h1>

<p>
  <strong>Create RVE</strong> 选项卡用于生成 RVE 几何模型。需要设置模型主名、
  选择纤维生成方法、定义几何参数，并指定一次批量生成多少个模型。
</p>

<figure class="figure">
  <img src="images/Random_RVE_Model.png" alt="随机 RVE 模型示例">
  <figcaption>图 1 — 随机分布的单向纤维 RVE 示例。</figcaption>
</figure>

<h2>3.1.1 模型主名（Model Name）</h2>

<p>
  设置生成模型的主名称。默认 <code>RVE_UDFiber_Random</code>。
  插件会自动追加直径、体积分数、纤维数和数字后缀：
</p>

<pre><code>RVE_UDFiber_Random_Df7_Vf040_N143_Model_1
RVE_UDFiber_Random_Df7_Vf040_N143_Model_2
…</code></pre>

<p>这个命名规则正是后续选项卡里"所有同主名模型"批量操作所依赖的。</p>

<h2>3.1.2 纤维坐标生成方法</h2>

<p>三选一：</p>

<table class="field-table">
  <thead>
    <tr><th>方法</th><th>Vf 上限</th><th>说明</th></tr>
  </thead>
  <tbody>
    <tr>
      <td><strong>Monte Carlo</strong></td>
      <td>≈ 45%</td>
      <td>随机投放纤维，重叠则拒绝。速度快，但 Vf 上限较低（受卡塞限制）。</td>
    </tr>
    <tr>
      <td><strong>Random Sequential Expansion (RSE)</strong></td>
      <td>≈ 68%</td>
      <td>迭代扩展纤维集合，可达更高 Vf，但速度较慢。</td>
    </tr>
    <tr>
      <td><strong>User coordinates file(s)</strong></td>
      <td>—</td>
      <td>从 CSV 文件导入纤维中心坐标。两列 (x, y)，无表头。</td>
    </tr>
  </tbody>
</table>

<div class="callout callout-warn">
  <div class="callout-title">Vf 上限为硬性限制</div>
  <p>这些 Vf 上限被作为<strong>硬性限制</strong>。超过上限时插件会直接报错，
  不会尝试不可靠的生成过程。</p>
</div>

<h2>3.1.3 几何参数（Geometric Parameters）</h2>

<table class="field-table">
  <thead>
    <tr><th>参数</th><th>默认</th><th>含义</th></tr>
  </thead>
  <tbody>
    <tr><td>RVE 宽度 <code>a</code></td><td>50</td>
        <td>横截面宽度（Y 方向）。</td></tr>
    <tr><td>RVE 高度 <code>b</code></td><td>50</td>
        <td>横截面高度（Z 方向）。</td></tr>
    <tr><td>RVE 厚度 <code>t</code></td><td>50</td>
        <td>沿纤维轴向的长度（X 方向）。</td></tr>
    <tr><td>纤维直径 <code>df</code></td><td>7</td>
        <td>所有纤维共用此直径。</td></tr>
    <tr><td>纤维体积分数 <code>Vf</code></td><td>40</td>
        <td>百分数。插件根据
        <code>(Vf · a · b) / (π · df² / 4)</code> 计算整数纤维数 <code>N</code>。</td></tr>
  </tbody>
</table>

<div class="callout callout-note">
  <div class="callout-title">单位</div>
  <p>所有数值需保持单位一致。纤维直径通常是 μm，所以 RVE 尺寸也应是 μm。
  材料属性需对应一致单位（如 MPa = N/μm²）。</p>
</div>

<h2>3.1.4 控制选项（Control Options）</h2>

<p>由于 <code>N</code> 取整，体积分数和 RVE 尺寸不可能同时精确匹配。需要选一项进行微调：</p>

<ul>
  <li><strong>keep vf</strong> — 保留输入的体积分数，按比例缩放
      <code>a</code> 和 <code>b</code>。</li>
  <li><strong>keep RVE size</strong> — 保留输入的 <code>a</code>、
      <code>b</code>，输出实际生成的 Vf。</li>
</ul>

<h2>3.1.5 基础参数（Base Parameter）</h2>

<p>这部分会根据所选生成方法动态变化：</p>

<details class="collapsible" open>
  <summary>Monte Carlo 选项</summary>
  <p><strong>Safe distance between fibers</strong> — 新纤维与所有已有纤维
  （含周期镜像）之间允许的最小表面间隙，即圆心距必须大于
  <code>df + safe distance</code>。值越大，网格越干净，但能达到的 Vf 越低。</p>
</details>

<details class="collapsible">
  <summary>RSE 选项</summary>
  <p><strong>Lmin</strong> 和 <strong>Lmax</strong> — 每根新纤维以
  <code>[Lmin, Lmax]</code> 内的随机表面间距种在某根已有纤维旁。
  <code>Lmax ≥ Lmin &gt; 0</code>。对其余邻居只要求不重叠，因此两根纤维
  可能几乎相切；如需对<em>所有</em>纤维对强制间隙，请修改
  <code>Generate_UDFRPs_RSE.py</code> 顶部的常量 <code>MIN_GAP</code>
  （模型单位，约 0.03–0.05 df）。间隙会降低可达 Vf，在 <em>keep vf</em>
  模式下还会增加重掷次数。</p>
</details>

<div class="callout callout-note">
  <div class="callout-title">边界余量</div>
  <p>两种生成器都会拒绝覆盖或擦过 RVE 顶点的候选纤维，以及跨越 RVE 边
  （或距边）不足 0.1 倍纤维半径的候选纤维。这样可以避免顶点纤维
  （几何内核无法可靠地把它切成四块周期部分）和导致网格划分失败的薄片。
  被排除的面积只占横截面的千分之几。阈值为两个生成器文件顶部的常量
  <code>BOUNDARY_CLEARANCE</code>（设为 0 可关闭）。用户坐标文件
  <em>不会</em>被过滤，见 Q&amp;A。</p>
</div>

<details class="collapsible">
  <summary>用户坐标选项</summary>
  <p>选择一个或多个 CSV 文件。文件数量必须等于下方"生成模型数"。
  CSV 文件只能有两列 (x, y) 坐标，原点 (0, 0) 位于 RVE 横截面左下角。</p>
</details>

<h2>3.1.6 生成模型数（Number of generated models）</h2>

<p>用于批量生成（如 Monte-Carlo 统计研究）。所有模型几何参数相同，
只有随机纤维位置不同。</p>

<h2>3.1.7 保存路径（Save folder directory）</h2>

<p>生成的 CSV 坐标文件和参数总结的保存位置。默认
<code>C:/UDFiber RVE Builder</code>。文件夹不存在时会自动创建。</p>

<h2>3.1.8 点击 OK 之后 —— 输出文件与数据库变化</h2>

<p>点击 OK 后插件依次完成 3 步：</p>

<ol>
  <li>生成（或读取）纤维中心坐标，写入指定的保存目录。</li>
  <li>按 <em>3.1.1 模型主名</em> 创建若干 Abaqus 模型，每个模型包含 3 个 Part：
      <code>Fiber</code>、<code>Matrix</code> 和合并后的
      <code>UDComposite</code>。</li>
  <li>在 <code>UDComposite</code> 中创建若干命名 Set（cells / edges / faces），
      后续所有选项卡都依赖这些 Set。</li>
</ol>

<h3>写到磁盘的文件</h3>

<table>
  <thead><tr><th>文件</th><th>用途</th></tr></thead>
  <tbody>
    <tr><td><code>RVE2D_&lt;N&gt;Inclusions_IncCoordinates&lt;ii&gt;.csv</code></td>
        <td>两列 (x, y) 的纤维中心坐标，每个模型一份。</td></tr>
    <tr><td><code>RVE2D_parameters_output_Vf_&lt;v&gt;_xy_&lt;n&gt;units_&lt;N&gt;fiber.txt</code></td>
        <td>汇总报告：目标 / 实际 Vf、RVE 尺寸、纤维数、耗时。</td></tr>
  </tbody>
</table>

<h3>统计分布文件（每个配置一份）</h3>

<p>为方便检查随机纤维分布是否符合预期，插件还会在 CSV 坐标旁同步写出
每个配置的统计文件：</p>

<table>
  <thead><tr><th>文件</th><th>内容</th></tr></thead>
  <tbody>
    <tr><td><code>nn1_probability_density_config_&lt;ii&gt;.csv</code></td>
        <td>第一近邻距离直方图。</td></tr>
    <tr><td><code>nn2_probability_density_config_&lt;ii&gt;.csv</code></td>
        <td>第二近邻距离直方图。</td></tr>
    <tr><td><code>ripleys_k_config_&lt;ii&gt;.csv</code></td>
        <td>归一化半径下的 Ripley K 函数。</td></tr>
    <tr><td><code>pair_distribution_function_config_&lt;ii&gt;.csv</code></td>
        <td>归一化半径下的对分布函数 g(r)。</td></tr>
    <tr><td><code>RVE2D_parameters_output_…txt</code></td>
        <td>汇总报告；末尾附每个算例的核对表（实际纤维数、实际 Vf、重掷次数、
        耗时），便于逐个对照输入快速核对。</td></tr>
    <tr><td><code>nearest_neighbor_distances.csv</code></td>
        <td>跨多个配置的近邻统计汇总。</td></tr>
  </tbody>
</table>

<h3>UDComposite 中创建的 Set</h3>

<table class="field-table">
  <thead><tr><th>Set 名称</th><th>几何类型</th><th>用途</th></tr></thead>
  <tbody>
    <tr><td><code>Set-Fiber</code></td><td>Cells</td>
        <td>所有纤维 cells —— 用于纤维材料分配。</td></tr>
    <tr><td><code>Set-Matrix</code></td><td>Cells</td>
        <td>所有基体 cells —— 用于基体材料分配和空隙插入。</td></tr>
    <tr><td><code>Set-Arc</code></td><td>Edges</td>
        <td>跨越 RVE 边界的纤维弧段 —— 用于圆周方向布种。</td></tr>
    <tr><td><code>Set-full-circle</code></td><td>Edges</td>
        <td>完整的纤维圆边界（内部纤维）—— 用于圆周方向布种。</td></tr>
    <tr><td><code>Set-Fiber-Straightness</code>（含 -vertical、-horizontal）</td><td>Edges</td>
        <td>RVE 表面上的纤维直线边 —— 用于横截面布种。</td></tr>
    <tr><td><code>Set-Matrix-Straightness</code>（含 -vertical、-horizontal）</td><td>Edges</td>
        <td>RVE 表面上的基体直线边 —— 用于横截面布种。</td></tr>
    <tr><td><code>Set-thickness-Straightness</code></td><td>Edges</td>
        <td>沿纤维轴向（X 方向）的边 —— 用于厚度方向布种。</td></tr>
  </tbody>
</table>

<div class="callout callout-warn">
  <div class="callout-title">不要重命名自动生成的 Set</div>
  <p>Mesh Control、Materials、Void Insertion、Analysis 选项卡都靠名称查找
  这些 Set。重命名任何一个都会导致后续选项卡失败。如需额外 Set，请新建，
  不要修改这些。</p>
</div>
`;
