// Auto-loaded via <script> tag from index.html
// Edit the HTML inside the template literal below; do NOT change the wrapper.
window.helpContent = window.helpContent || {};
window.helpContent['zh/tab4_void'] = `
<\!-- ===== SECTION: tab4_void (中文) ======================================== -->
<h1>3.4 · 空隙插入</h1>

<p>
  <strong>Void Insertion</strong> 选项卡向已经网格化的 RVE 基体中插入微空隙。
  本页只讲操作步骤和注意事项，不展开理论背景。
</p>

<div class="callout callout-warn">
  <div class="callout-title">先网格化</div>
  <p>本选项卡需要已经网格化的模型。请先在 Mesh Control 选项卡完成网格划分。</p>
</div>

<h2>3.4.1 选择模型和 Part</h2>

<ul>
  <li><strong>Model</strong> — 列出所有打开的模型。</li>
  <li><strong>Part</strong> — 通常是 <code>UDComposite</code>，
      下拉菜单根据所选模型自动填充。</li>
</ul>

<h2>3.4.2 空隙体积分数（Void Volume Fraction）</h2>

<p>单个数值，单位<strong>百分数</strong>，默认 <code>5.0</code>。
表示空隙体积占整个 RVE 体积的百分比。插件会把这个分数精确分配到所有插入的
空隙中 —— 除了物理可行性以外不设隐性上限（即不能要求的 Vvoid 大于纤维
插入完之后剩余的实际基体体积）。</p>

<h2>3.4.3 空隙分布（Void Distribution）</h2>

<p>选择空隙在插件内定义的两种区域之间的分布方式：</p>

<ul>
  <li><strong>Random Number Method</strong> — 自动随机分布；插件在每次插入
      尝试时随机采样权重。</li>
  <li><strong>Custom (w, 0–1)</strong> — 输入权重 <code>w</code>，
      取值 <code>[0, 1]</code>，控制下方两类空隙的体积比。</li>
</ul>

<h3>插件中两种空隙类型的定义规则</h3>

<p>在插入任何空隙之前，每个候选基体单元会被严格归入下面两类之一：</p>

<table class="field-table">
  <thead><tr><th>空隙类型</th><th>定义（插件采用的判定规则）</th></tr></thead>
  <tbody>
    <tr>
      <td><strong>纤维相邻（Fiber-adjacent）</strong></td>
      <td>与 <code>Set-Fiber</code> cell 至少共享一个节点（或面）的基体单元。
          这些单元构成包裹每根纤维的薄基体壳层。</td>
    </tr>
    <tr>
      <td><strong>基体内部（Inter-matrix）</strong></td>
      <td>其余的所有基体单元 —— 即不与任何纤维接触的基体单元。这些单元通常
          位于纤维之间的"通道"区。</td>
    </tr>
  </tbody>
</table>

<p>权重 <code>w</code> 控制体积分配：</p>
<ul>
  <li><code>w = 0</code> → 全部空隙体积取自<strong>基体内部</strong>单元。</li>
  <li><code>w = 1</code> → 全部空隙体积取自<strong>纤维相邻</strong>单元。</li>
  <li><code>w ∈ (0, 1)</code> → 混合：<code>w</code> 比例的空隙体积来自
      纤维相邻单元，<code>1 − w</code> 来自基体内部单元。</li>
</ul>

<div class="callout callout-note">
  <p>分类在操作开始时基于已网格化的 <code>UDComposite</code> Part 一次完成。
  之后，插件按所选类别整单元删除，直到达到目标体积分数。</p>
</div>

<h2>3.4.4 空隙大小（Void Size）</h2>

<ul>
  <li><strong>Random Void Size</strong> — 大小随机。</li>
  <li><strong>Custom Size (theta)</strong> — 输入正整数 <code>theta</code> ≥ 1。
      <code>theta</code> 表示空隙数量；单个空隙的 Vf 即
      <code>总 Vf / theta</code>。</li>
</ul>

<div class="callout callout-warn">
  <div class="callout-title">theta = 1 的限制</div>
  <p>设 <code>theta = 1</code> 时，分布权重 <code>w</code> 只能是
  <code>0</code>、<code>1</code> 或 <strong>Random</strong>，
  不能是分数 —— 单个空隙不能在两个区域之间拆分。</p>
</div>

<h2>3.4.5 优先级（Priority）</h2>

<p>当约束之间冲突时（例如 <code>w</code> 在可用空间内无法严格满足），
决定优先保留哪一项：</p>

<table class="field-table">
  <thead><tr><th>选项</th><th>严格保持</th></tr></thead>
  <tbody>
    <tr><td><strong>Distribution Priority (strict w)</strong></td>
        <td>严格保持 <code>w</code>，空隙大小可调整。</td></tr>
    <tr><td><strong>Size Priority (allow w deviation)</strong></td>
        <td>空隙大小尽量接近目标，<code>w</code> 可调整。</td></tr>
    <tr><td><strong>No Intervention</strong></td>
        <td>插件按最佳努力放置。</td></tr>
  </tbody>
</table>

<div class="callout callout-note">
  <div class="callout-title">Vvoid 始终保证</div>
  <p>无论选哪个优先级，请求的空隙体积分数 <code>Vvoid</code> 都是唯一
  不会放宽的目标：最后一道修正会在任意空隙上增删边界单元，直到总量落在
  目标的 99%–101% 之间。可调整的只有 <em>w</em> 和 <em>theta</em>。
  若连这道修正也无法落入区间（可用单元已耗尽），汇总表会如实说明，
  而不会报告成功。</p>
</div>

<h2>3.4.6 空隙形状因子（β）— 实验功能</h2>

<div class="callout callout-warn">
  <div class="callout-title">开发中的实验功能</div>
  <p>形状因子目前是测试功能，界面和行为可能变化，生成的空隙形状尚未经过
  验证。正式研究请保持关闭。</p>
</div>

<p>默认情况下，空隙以纯距离权重生长，得到近似球形的簇团。可选的
<strong>β</strong> 形状因子会把候选权重偏向一个椭球包络，让空隙沿
长轴或短轴方向拉长。</p>

<table class="field-table">
  <thead><tr><th>选项</th><th>含义</th></tr></thead>
  <tbody>
    <tr><td><strong>启用形状因子</strong></td>
        <td>不勾选 → 沿用旧的纯距离规则（球形）。勾选 → 使用下面定义的
            椭球包络。</td></tr>
    <tr><td><strong>β 值（>0）</strong></td>
        <td>一个正实数即可。<code>β = 1</code> → 球；<code>β > 1</code>
            → 长椭球，轴比 <code>(β, 1, 1)</code>，沿纤维 X 轴延伸；
            <code>β < 1</code> → 扁椭球，轴比 <code>(1, 1, β)</code>，
            沿 Z 方向压扁。不再需要额外的形状种类单选 —— β 一个值即可
            决定形态。</td></tr>
    <tr><td><strong>统一 / 拆分</strong></td>
        <td>统一：纤维相邻与基体内部空隙共用一个 β。拆分：分别指定两类
            空隙的 β。</td></tr>
    <tr><td><strong>方向</strong></td>
        <td><em>随机 SO(3)</em>：每个空隙的包络方向独立、各向均匀随机；
            <em>正交</em>：保持包络与坐标轴对齐（长轴沿 X，短轴沿 Z）。</td></tr>
    <tr><td><strong>θ*（每根纤维平均空隙数）</strong></td>
        <td>可选信息项。启用后在汇总报告中记录 θ* 并隐含
            <code>θ = θ* × Nf</code>。已有的 θ 与 Vf 规则仍然优先。</td></tr>
  </tbody>
</table>

<div class="callout callout-note">
  <p>β 只调整生长过程中的<em>候选权重</em>。所有其它规则（目标 Vf、
  w、θ、防止纤维被完全包围、孤岛抑制等）仍然按原样严格执行，所以 β
  是软性偏好，而非硬约束。</p>
</div>

<h2>3.4.7 空隙插入模型范围</h2>

<p>与其他选项卡相同的批量控件（Current / All / Selected numbers）。
"All Models" 应用于所有与所选模型同主名的模型。</p>

<h2>3.4.8 点击 OK 之后 —— 输出文件与数据库变化</h2>

<p>对每个模型，插件会：</p>
<ol>
  <li>把每个基体单元归类为<em>纤维相邻</em>或<em>基体内部</em>（见 3.4.3）。</li>
  <li>从对应类别中整单元删除，直到达到目标 Vvoid。</li>
  <li>给删除的区域打 Set 标签 <code>Set-Void</code>，便于在 Abaqus 的 Mesh
      模块中查看。</li>
  <li>更新材料 Section 分配，使空隙区域不再承载材料。</li>
  <li>把详细统计数据写到磁盘上的专用文件夹，便于验证实际分布是否与
      输入一致。</li>
</ol>

<h3>消息区的打印内容</h3>

<p>详细数值都会写入磁盘，因此消息区保持简短：每个模型处理完打印一行，
整批结束后打印一张汇总表。</p>

<pre>Inserting voids into 5 models; target Vvoid = 5.0000%.
  [1/5] RVE_..._Model_1: 12 void(s), Vvoid = 5.0132%, OK (34.2 s)
  ...
Void insertion summary: 5 models -- 4 within tolerance, 1 relaxed, 0 not met
Target: Vvoid = 5.0000%, theta = 12, w = 0.500
  model             voids  Vvoid (%)    dev (%)       w  time (s)  status
  RVE_..._Model_1      12     5.0132    +0.0132   0.502      34.2  OK
  RVE_..._Model_3      11     5.0410    +0.0410   0.480     151.7  relaxed: theta, w</pre>

<p><em>status</em> 列为 <code>OK</code> 表示所有目标都在严格容差内达成；
<code>relaxed: theta, w</code> 表示为了收敛放宽了对应目标的容差；
若为一段简短说明，则表示该目标未能达成。涉及 <code>Vvoid</code> 的说明
优先显示，因为它是必须达成的目标。常见的一条是
<code>w = 0.50 unreachable: every matrix element touches a fiber</code>：
纤维体积分数高而网格较粗时，几乎没有"基体内部"单元可供放置空隙，
w 实际被网格锁定为 1。此时应加密网格，或对这类模型直接取 w = 1。
逐个模型的详细数据仍在下面的统计文件夹中。</p>

<h3>写到磁盘的统计文件夹</h3>

<p>插件每次运行都会在 Abaqus 工作目录下新建一个文件夹，名为
<code>Void_Statistics_&lt;model&gt;</code>。
内容如下：</p>

<table>
  <thead><tr><th>文件</th><th>内容</th></tr></thead>
  <tbody>
    <tr><td><code>void_summary_report.txt</code></td>
        <td>顶层报告 —— 用户输入、RVE 尺寸、目标 vs <strong>实际</strong>
        Vvoid、纤维相邻 / 基体内部分配、实际 <code>w</code>、与目标的
        偏差。<em>请先打开它。</em></td></tr>
    <tr><td><code>void_sizes.csv</code></td>
        <td>每个空隙：ID、类型（near-fiber / inter-matrix）、体积、
        单元数、形心 (x, y, z)，加上 PCA 包络信息：
        三条降序的半轴 <code>(h1, h2, h3)</code>、
        三个方向余弦向量 <code>(e1, e2, e3)</code>，
        以及主轴 <code>e1</code> 与全局纤维 X 轴的方向余弦相似度。</td></tr>
    <tr><td><code>void_fiber_surface_breakdown.csv</code></td>
        <td>每根纤维的表面破坏：纤维 ID、界面单元面数（同时作为周长代理量）、
        被破坏的界面面数，以及比值 <code>r_i = 破坏 / 总数</code>。</td></tr>
    <tr><td><code>void_nn_distances.csv</code></td>
        <td>空隙之间的第一、第二近邻距离。</td></tr>
    <tr><td><code>void_ripleys_k.csv</code></td>
        <td>Ripley K 函数（适用时）。</td></tr>
    <tr><td><code>void_pair_distribution.csv</code></td>
        <td>空隙形心的对分布函数 g(r)。</td></tr>
    <tr><td><code>void_fiber_distances.csv</code></td>
        <td>每个空隙到最近纤维的距离（NN1、NN2）。</td></tr>
  </tbody>
</table>

<h3>纤维表面破坏度量</h3>

<p>当纤维中心可用时，<code>void_summary_report.txt</code> 末尾会追加 5 个
反映空隙对纤维–基体界面破坏程度的浓度指标。记 <code>r_i</code> 为第
<code>i</code> 根纤维的破坏面比（界面面指纤维单元与基体或空隙单元共享的
单元面，相邻单元为空隙时记为破坏），<code>N_f</code> 为纤维总数：</p>

<table class="field-table">
  <thead><tr><th>指标</th><th>定义 / 解读</th></tr></thead>
  <tbody>
    <tr><td><code>f_fiber</code></td>
        <td>有<em>任意</em>破坏的纤维占比
            （<code>r_i > 0</code> 的纤维数除以 <code>N_f</code>）。</td></tr>
    <tr><td><code>f_area</code></td>
        <td>总体破坏面积比 = 所有纤维的破坏界面面总数 / 界面面总数。</td></tr>
    <tr><td><code>r_avg_broken</code></td>
        <td>仅对受影响纤维的 <code>r_i</code> 求均值。</td></tr>
    <tr><td><code>C_focus</code></td>
        <td><code>= r_avg_broken / f_area</code>。该值越大，
            表示破坏越集中于少数纤维。</td></tr>
    <tr><td><code>Gini(r_i)</code></td>
        <td><code>r_i</code> 的标准 Gini 系数。接近 0 → 分布均匀；
            接近 1 → 高度集中。</td></tr>
  </tbody>
</table>

<div class="callout callout-warn">
  <div class="callout-title">空隙插入并非绝对完美 —— 分析前请先检查</div>
  <p>空隙位置是一个在有限、已网格化的基体内运行的随机过程。根据所请求的
  Vf、<code>w</code>、<code>theta</code> 以及局部几何，实际分布可能与
  目标有轻微偏差 —— 极端情况下甚至可能完全失败。
  <strong>每次运行结束请先打开 <code>void_summary_report.txt</code></strong>，
  确认实际 Vf、实际 <code>w</code> 及偏差对你的研究是可以接受的，再把
  模型送去分析。</p>
</div>

<div class="callout callout-tip">
  <div class="callout-title">使用提示</div>
  <ul>
    <li>请在<em>分配材料之后</em>插入空隙。插件期望模型已网格化并完成
    材料分配。</li>
    <li>当目标 Vf 因基体空间不足而无法满足时，插件会停止并给出警告，
    不会破坏模型 —— 调整设置后再试。</li>
    <li>对同一模型再次运行本选项卡会在已有空隙上叠加 ——
    若需多种变体，请先复制模型。</li>
  </ul>
</div>
`;
