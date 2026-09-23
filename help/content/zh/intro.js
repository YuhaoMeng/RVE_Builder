// Auto-loaded via <script> tag from index.html
// Edit the HTML inside the template literal below; do NOT change the wrapper.
window.helpContent = window.helpContent || {};
window.helpContent['zh/intro'] = `
<\!-- ===== SECTION: intro (中文) ============================================ -->
<h1>1 · 简介</h1>

<p>
  <strong>RVE Builder（UDFRPs）</strong>是一款 Abaqus/CAE 插件，把单向连续
  纤维增强聚合物（UDFRPs）的代表性体积单元（RVE）建模到周期性边界条件（PBC）
  下的均质化分析全流程自动化。几何生成、网格划分、材料分配、微空隙插入和
  均质化分析均可在一个对话框内完成 —— 无需写脚本，也无需任何第三方软件。
</p>

<p>
  插件既适合单次探索性研究，也适合大规模统计批处理。每个操作都带"模型范围
  选择器"，几十个随机实现的参数研究可以一键完成网格划分、材料分配和分析。
  内置 6 种均质化分析：含 CTE 的线弹性、时域 / 频域粘弹性、可选 UMAT 的弹塑性、
  稳态热导率。基体微空隙的空间分布（随机或纤维相邻加权）和大小策略
  （随机或定数）均可控制。
</p>

<div class="callout callout-note">
  <div class="callout-title">作者</div>
  <p>孟禹豪 · 巴西里约热内卢联邦大学（COPPE/UFRJ）海洋工程系。</p>
  <p>本插件由作者独立开发，谨此分享，仅供学术交流与讨论之用。
  其中疏漏与不足之处在所难免，恳请同行不吝赐教，惠予批评指正。
  联系邮箱：<a href="mailto:yuhaomeng@oceanica.ufrj.br">yuhaomeng@oceanica.ufrj.br</a>。</p>
</div>

<h2>主要功能</h2>
<ul>
  <li>使用 <strong>Monte Carlo</strong>、<strong>RSE</strong> 算法生成
      随机纤维分布，或导入 CSV 坐标文件。</li>
  <li>精细控制网格种子，并选择单元类型（力学、热、热-力耦合）。</li>
  <li>借助 Abaqus 的 ODB 跨模型材料复制实现批量材料分配。</li>
  <li>在基体中插入微空隙，可控制大小、分布和优先级。</li>
  <li>6 种基于 PBC 的均质化分析（弹性 + CTE、热导率、单轴弹塑性、双轴弹塑性、
      时域粘弹性、频域粘弹性）；存在内聚界面时，弹塑性与热分析自动切换到
      界面版本的求解内核。</li>
</ul>

<h2>插件结构</h2>
<p>插件提供 <strong>6 个选项卡</strong>，对应工作流的各个阶段：</p>

<div class="inline-tabs">
  <div class="tab-buttons">
    <button class="tab-btn">创建 RVE</button>
    <button class="tab-btn">网格控制</button>
    <button class="tab-btn">材料</button>
    <button class="tab-btn">空隙插入</button>
    <button class="tab-btn">界面</button>
    <button class="tab-btn">分析</button>
  </div>
  <div class="tab-panel">
    <p>设置几何尺寸、纤维坐标生成方法、体积分数和批量生成的模型数量。</p>
  </div>
  <div class="tab-panel">
    <p>布置网格种子、选择单元形状（HEX/WEDGE）、选择网格类型（力学 / 热 / 耦合）。</p>
  </div>
  <div class="tab-panel">
    <p>分配纤维和基体材料。利用 Abaqus 的 ODB 跨模型材料复制功能，
    一次性应用到多个模型。</p>
  </div>
  <div class="tab-panel">
    <p>插入空隙，可控制分布（随机或纤维相邻加权）、大小方法和优先级。
    需在网格化之后使用。</p>
  </div>
  <div class="tab-panel">
    <p>在纤维-基体界面处插入零厚度内聚单元（COH3D8），可选预先脱粘比例。
    操作在模型副本上进行，原始网格保持不变。</p>
  </div>
  <div class="tab-panel">
    <p>设置 PBC 并运行 6 种均质化分析之一。可选地传入用户 UMAT 子程序。
    选择已含内聚单元的模型时，弹塑性和热导率会自动切到 interface-aware kernel。</p>
  </div>
</div>

<div class="callout callout-tip">
  <div class="callout-title">推荐工作流</div>
  <p>建议按选项卡顺序使用：创建 RVE → 网格控制 → 材料 →（可选）空隙插入 →
  （可选）界面 → 分析。每个选项卡都包含<em>选择模型范围</em>控件，可以作用于当前模型、
  所有同主名模型，或指定的模型子集。</p>
</div>

`;
