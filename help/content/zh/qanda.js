// Auto-loaded via <script> tag from index.html
// Edit the HTML inside the template literal below; do NOT change the wrapper.
window.helpContent = window.helpContent || {};
window.helpContent['zh/qanda'] = `
<\!-- ===== SECTION: qanda (中文) ============================================ -->
<h1>4 · Q&amp;A · 工作原理</h1>

<p>
  本节以问答形式扼要介绍每个选项卡的核心工作原理，方便理解插件背后的逻辑、
  以及排查意料之外的行为。详细数学推导仍以 <em>5 · 参考文献</em> 中列出的
  文献为准。
</p>

<h2>Create RVE</h2>

<details class="collapsible" open>
  <summary>Q. 随机纤维圆是怎么"落"进 RVE 横截面的？</summary>
  <p>Monte Carlo：每次在 RVE 矩形内随机抽一个候选圆心，只有与所有已接受
  纤维的距离都不小于<em>安全距离</em>时才接受，否则重抽。RSE：从一根种子
  纤维出发逐根添加 —— 随机选一根已有纤维，在距其表面
  <code>[Lmin, Lmax]</code> 内的随机位置放一根新纤维，与其余纤维不重叠
  （或满足可选的 <code>MIN_GAP</code> 间隙）即接受；排到无法再放入后，
  再随机移除纤维直到目标 Vf。两种方法都强制在 RVE 四个面上保持
  周期性 —— 跨越某一面的纤维会被复制到对面，使横截面可以无缝拼贴。</p>
</details>

<details class="collapsible">
  <summary>Q. 插件如何把 (x, y) 坐标变成 Abaqus 的 Part 与 Set？</summary>
  <p>把每个纤维圆与 RVE 矩形边界都写成 Abaqus 草图里的圆方程和直线方程，
  插件接着<em>解析地</em>求出圆 vs 直线的交点 —— 用闭式交点（而不是
  数值挑取）来确定横截面的各条边、弧段、面。2D 草图沿 X 方向拉伸，得到
  3D 的 <code>UDComposite</code> Part。最后，<code>part.findAt(point)</code>
  配合精心选择的探针点，把 edges / faces 收集到 <em>3.1.8</em>
  列出的命名 Set 里。cell 集合 <code>Set-Fiber</code> 与 <code>Set-Matrix</code>
  按几何判定：取每个 cell 内部一点，检验它是否落在某个纤维圆（含周期镜像）
  内，因此不依赖布尔合并后 Abaqus 给 cell 编号的顺序。</p>
</details>

<details class="collapsible">
  <summary>Q. 实际 Vf 为什么有时跟我输入的不一致？</summary>
  <p>纤维数 <code>N</code> 是
  <code>(Vf · a · b) / (π · df² / 4)</code> 的整数化结果，要么由 Vf 吸收
  这个取整误差、要么由横截面尺寸吸收 —— 由 <em>Control Options</em> 决定。
  实际值会记录在 <code>parameters_output</code> 的 TXT 文件里。</p>
</details>

<details class="collapsible">
  <summary>Q. 纤维落在 RVE 顶点上会怎样？</summary>
  <p>覆盖顶点的纤维会被切成四块薄片，分别位于四个顶点。因此 Monte Carlo 和
  RSE 生成器不会生成这种纤维：圆覆盖或擦过顶点、跨越 RVE 边（或距边）不足
  0.1 倍半径的候选都会被拒绝（生成器文件中的 <code>BOUNDARY_CLEARANCE</code>）。
  用户坐标文件按原样使用。如果你的坐标里有纤维覆盖顶点，
  <code>Set-Fiber</code> / <code>Set-Matrix</code> 仍按几何判定，但顶点薄片
  很难划分网格，边上的种子也可能不均匀。建议把整组坐标平移一个常量
  （圆心按周期回绕），使任何纤维都不覆盖顶点，并在划分网格前到 Abaqus 中
  检查这两个 cell 集合。</p>
</details>

<h2>Mesh Control</h2>

<details class="collapsible">
  <summary>Q. 网格划分失败，或个别单元被标为 error，为什么？</summary>
  <p>扫掠网格严格跟随横截面分块，网格质量取决于几何。两根几乎相切的纤维
  之间的基体通道比一个单元还窄，擦边而过的纤维会留下极小的弓形薄片，
  两者都会让网格划分失败或留下少数畸变单元。处理顺序：增大纤维最小间隙
  （Monte Carlo 的 <em>Safe distance</em>、RSE 的
  <code>Generate_UDFRPs_RSE.py</code> 顶部常量 <code>MIN_GAP</code>），使最窄
  通道至少约一个单元宽；重新生成坐标，换一个随机实现往往就能正常划分；
  增加圆周种子数；或把 <em>Element Shape</em> 改为 WEDGE，它对狭窄区域
  更宽容。狭窄通道里的少数畸变单元体积可以忽略，通常不影响均匀化模量；
  做损伤或界面分析时请重新生成。</p>
</details>

<details class="collapsible">
  <summary>Q. 为什么插件限制了可选的单元类型？</summary>
  <p>周期性边界条件靠"把对面节点绑在一起"实现，这要求一对面的网格能配对。
  只有 <em>Mesh Type</em> 和 <em>Element Shape</em> 暴露出的单元族能保证
  这一点。在插件外手动换成其他单元（例如四面体）会让 PBC 步骤失败。</p>
</details>

<details class="collapsible">
  <summary>Q. 3.2.3 里的种子公式是怎么从 <code>NR</code> 推出来的？</summary>
  <p>把每个直径 <code>df</code> 的纤维圆看作 <code>NR</code> 段的多边形，
  每段长度即 <code>π · df / NR</code>。让横截面其他边也用相近的特征尺寸，
  得到 <code>NL = L · NR / (π · df)</code>。页面上的交互式计算器就是把
  这条公式包成 UI 而已。</p>
</details>

<h2>Materials</h2>

<details class="collapsible">
  <summary>Q. 批量模式为什么要写临时 ODB？</summary>
  <p>Abaqus 没有"直接把材料从一个内存模型复制到另一个"的 API。变通方案
  是把源模型的材料写到一个 ODB 中（兼容
  <code>materialsFromOdb</code>），然后让其他目标模型把它读进来。临时
  文件 <code>UsetoCopyMaterial_&lt;model&gt;.odb</code> 就是为此而生，
  分配完成后插件会把它删掉。</p>
</details>

<h2>Void Insertion</h2>

<details class="collapsible">
  <summary>Q. 插件如何决定哪些基体单元会变成空隙？</summary>
  <p>网格化之后，每个基体单元被打上一个标签：<em>纤维相邻</em>（与
  <code>Set-Fiber</code> cell 至少共享一个节点或面）或<em>基体内部</em>
  （其余）。然后插件按照请求的权重 <code>w</code> 和大小策略
  （<code>theta</code> 或随机）从两个标签列表里挑单元整块删除，累计删除
  体积达到目标 Vf 时停止。</p>
</details>

<details class="collapsible">
  <summary>Q. 实际的 <code>w</code> 为什么有时与目标不一致？</summary>
  <p>纤维相邻单元的"池子"是有限的 —— 当 Vf 较大或 <code>w</code> 极端
  时，某一类可能在达到目标之前就被掏空。<em>Priority</em> 选项决定保留
  哪个量：严格 <code>w</code>（让单个空隙大小变）、严格大小（让
  <code>w</code> 变）、或尽力而为。
  <code>void_summary_report.txt</code> 会如实报告实际值。</p>
</details>

<h2>Analysis</h2>

<details class="collapsible">
  <summary>Q. 周期性边界条件起什么作用？</summary>
  <p>RVE 是无限大复合材料的一小块。为了把"块"的有效响应还原回"无限大"，
  需要让 RVE 对面两面的位移之差等于一个宏观应变 —— 这就是 PBC。EasyPBC
  通过把对面节点绑成线性方程实现这个条件，因此网格匹配容差和单元类型
  才会这么关键。</p>
</details>

<details class="collapsible">
  <summary>Q. E11–G23 这些弹性模量具体怎么算？</summary>
  <p>对每一个要算的模量，插件施加对应的单位宏观应变（如 ε11 = 1，其余 0），
  让 Abaqus 在 PBC 下求解。然后从 ODB 里读出体积平均应力，除以宏观应变
  得到模量。六个独立工况就给出完整的正交各向异性刚度
  （E11/E22/E33 + G12/G13/G23）。</p>
</details>

<details class="collapsible">
  <summary>Q. 粘弹性分析有什么不同？</summary>
  <p>PBC 框架相同，但本构是含时间 / 频率的。<strong>时域</strong>：
  保持应变，运行一个松弛步，在用户指定的时间点采样 E(t) 或 G(t)。
  <strong>频域</strong>：用 Abaqus 的稳态动态步扫频，输出复模量
  E*(ω) 或 G*(ω)。</p>
</details>

<details class="collapsible">
  <summary>Q. 弹塑性分析具体在解什么？</summary>
  <p>在 PBC 下施加用户指定的宏观应变（沿 RVE 坐标轴的单轴或双轴），
  让 Abaqus 步步推进 fiber + matrix 的非线性本构。如果提供了 UMAT，那
  基体的本构就交给该子程序；否则用 Materials 选项卡里定义的材料。
  应力-应变历史以 CSV 形式导出，便于后处理。</p>
</details>

<details class="collapsible">
  <summary>Q. 热导率分析呢？</summary>
  <p>用周期温度边界条件取代力学的：在请求的方向上施加单位温度梯度，
  对面保持参考温度。Abaqus 的稳态传热求解器给出体积平均热流，从中
  反推出 K11–K33。</p>
</details>

<div class="callout callout-tip">
  <div class="callout-title">想要更深入？</div>
  <p>PBC 的数学推导、RSE / Monte-Carlo 纤维生成的细节，以及源论文里
  Bridging / Kerner 微观力学框架，请见 <em>5 · 参考文献</em>。</p>
</div>
`;
