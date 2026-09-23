// Auto-loaded via <script> tag from index.html
// Edit the HTML inside the template literal below; do NOT change the wrapper.
window.helpContent = window.helpContent || {};
window.helpContent['zh/tab6_analysis'] = `
<\!-- ===== SECTION: tab6_analysis (中文) ==================================== -->
<h1>3.6 · 分析</h1>

<p>
  <strong>Analysis</strong> 选项卡施加 PBC 并对所选模型运行 6 种均质化分析
  之一。PBC 实现基于开源插件 EasyPBC [3]，并扩展支持了粘弹性、弹塑性和
  热导率分析。
</p>

<div class="callout callout-warn">
  <div class="callout-title">保留了 EasyPBC 原有的报错和警告信息</div>
  <p>本选项卡完整保留了 EasyPBC 的原始报错和警告文本。如果运行失败或
  出现涉及 PBC、节点对应容差、相关 / 独立节点等的提示，请查阅
  <a href="https://doi.org/10.1007/s00366-018-0616-4" target="_blank" rel="noopener">EasyPBC 论文 (Omairey 等, 2019)</a>
  确定原因。其他范围之外的问题（分析类型相关参数、UMAT 加载等）见下文。</p>
</div>

<div class="callout callout-warn" style="border-left-color:#cc0000;">
  <div class="callout-title" style="color:#cc0000;">单位提醒 · 输入 °C、内部转 K</div>
  <p style="color:#cc0000;">
    <strong>包含温度的所有分析，插件输入一律使用摄氏度（°C）。</strong>
    Abaqus 中的材料属性定义仍然以开尔文（K）为准；插件会把 °C
    输入自动转为 K，输出文件中所有报告温度都是 °C。插件 GUI 顶部那两行加粗
    的红色提示重复了同样的约定。
  </p>
</div>

<h2>3.6.1 基本信息（Basic Information）</h2>

<table class="field-table">
  <thead><tr><th>字段</th><th>默认</th><th>含义</th></tr></thead>
  <tbody>
    <tr><td>Model</td><td>（当前）</td><td>要运行分析的模型。</td></tr>
    <tr><td>Part</td><td>UDComposite</td><td>根据所选模型自动填充。</td></tr>
    <tr><td>Mapping accuracy *</td><td>1E-04</td>
        <td>RVE 对面节点的匹配容差，应小于最小网格边长。</td></tr>
    <tr><td>Number of CPUs **</td><td>1</td>
        <td>分配给 Abaqus 作业的 CPU 数。超过实际可用数时会自动使用全部可用 CPU。</td></tr>
    <tr><td>UMAT Subroutine</td><td>（留空）</td>
        <td>可选，<strong>对所有分析类型都开放</strong>。如需 Abaqus 调用
        自定义 Fortran <code>.for</code> 子程序，请选择该文件；留空则使用
        Materials 选项卡中定义的材料和 Abaqus 内置求解器。Thermal
        Conductivity 后端当前不接收 UMAT 参数，因此在该类型下输入的路径
        会被静默忽略；其余分析类型都会照常调用 UMAT。</td></tr>
  </tbody>
</table>

<h2>3.6.2 分析类型（Analysis Type）</h2>

<p>单选。下方的"Analysis Parameters"面板会随之切换。</p>

<table class="narrow-index-table">
  <thead><tr><th>#</th><th>类型</th><th>对应后端模块</th></tr></thead>
  <tbody>
    <tr><td>1</td><td>弹性 + CTE</td>
        <td><code>PBC_UDFRP_Elastic_CTE</code></td></tr>
    <tr><td>5</td><td>热导率</td>
        <td><code>PBC_UDFRP_thermal_conductivity</code>
        （含内聚界面时自动切到 <code>_Interfaceh</code>）</td></tr>
    <tr><td>4</td><td>弹塑性（单轴）</td>
        <td><code>PBC_UDFRP_Elastoplastic</code>
        （含内聚界面时自动切到 <code>_interface</code>）</td></tr>
    <tr><td>6</td><td>弹塑性（双轴）</td>
        <td><code>PBC_UDFRP_Elastoplastic</code>
        （含内聚界面时自动切到 <code>_interface</code>）</td></tr>
    <tr><td>2</td><td>粘弹性（时域）</td>
        <td><code>PBC_UDFRP_Viscoelastic_Time</code></td></tr>
    <tr><td>3</td><td>粘弹性（频域）</td>
        <td><code>PBC_UDFRP_Viscoelastic_Frequency</code></td></tr>
  </tbody>
</table>

<h2>3.6.3 分析参数（按类型）</h2>

<div class="inline-tabs">
  <div class="tab-buttons">
    <button class="tab-btn">弹性 + CTE</button>
    <button class="tab-btn">粘弹性（时域）</button>
    <button class="tab-btn">粘弹性（频域）</button>
    <button class="tab-btn">弹塑性(单轴)</button>
    <button class="tab-btn">弹塑性(双轴)</button>
    <button class="tab-btn">热导率</button>
  </div>

  <div class="tab-panel">
    <p>选择要计算的模量（任意组合）：</p>
    <ul>
      <li><strong>E11(X)、E22(Y)、E33(Z)</strong> — 杨氏模量。</li>
      <li><strong>G12(XY)、G13(XZ)、G23(YZ)</strong> — 剪切模量。</li>
      <li><strong>Only Corresponding PBC</strong> — 仅施加对应模量的 PBC
          而不求解（用于检查边界条件）。</li>
      <li><strong>Coefficient of Thermal Expansion (CTE)</strong> — 添加
          热载荷分析步，启用下方温度输入。</li>
    </ul>
    <p>勾选 <strong>CTE</strong> 后：</p>
    <ul>
      <li><strong>Initial / Final Temperature (°C)</strong>、<strong>Segment</strong>
          — 温度阶梯设置。输入单位为摄氏度，内部自动转换为开尔文。</li>
    </ul>
    <p><strong>Temperature Points (°C)</strong> — 可选的逗号分隔
    摄氏度列表（例如 <code>-40, 25, 80, 120</code>）。填入后调度器会在每个
    温度点上各跑一次弹性分析，同时输出逐点 CSV 和汇总的
    <code>&lt;model&gt;_elastic_temperature_sweep_&lt;timestamp&gt;.csv</code>。提交
    任务之前每个数值都会被对照绝对零度（−273.15 °C）校验。</p>
  </div>

  <div class="tab-panel">
    <ul>
      <li><strong>E11/E22/E33/G12/G13/G23</strong> — 选择要松弛的分量。</li>
      <li><strong>Temperature (°C)</strong> — 固定温度（−273 ~ 5000）。</li>
      <li><strong>Relaxation Total Time (s)</strong> — 松弛时长。</li>
      <li><strong>Number of Time Points</strong> — 沿松弛曲线的采样点数。</li>
    </ul>
    <p>输出为指定时间点上的松弛模量 E(t) 或 G(t)。</p>
  </div>

  <div class="tab-panel">
    <ul>
      <li><strong>E11*/E22*/E33*/G12*/G13*/G23*</strong> — 复模量。</li>
      <li><strong>Temperature (°C)</strong> — 固定温度。</li>
      <li><strong>Lower / Upper Frequency (Hz)</strong> — 扫频范围。</li>
      <li><strong>Number of Points</strong> — 总采样点数。</li>
      <li><strong>Bias</strong> — 大于 3 时把采样点向下界聚集；不大于 3 时
          采用均匀采样。</li>
    </ul>
  </div>

  <div class="tab-panel">
    <p>在 PBC 下施加宏观应变。<strong>单轴布局</strong>
    (Analysis Type = 4) 下，设置任意 6 个独立应变分量的组合，
    dispatcher 会"每勾一个跑一个 case"。</p>

    <h4>单轴输入</h4>
    <p>6 个独立复选框 &mdash;
    <strong>Strain11、Strain22、Strain33、Shear12、Shear13、Shear23</strong>
    &mdash; 每个配一个数值框。勾选要跑的分量、填目标应变，
    dispatcher 会 "每勾一个跑一个 case"，未勾的跳过。</p>
    <ul>
      <li><strong>Strain11 / Strain22 / Strain33</strong> 接受单值，或
          <em>逗号分隔的两个值</em>。例
          <code>0.012,-0.016</code> 会跑两次：拉伸(+0.012)与
          压缩(-0.016)，一键扫两种情形。</li>
      <li><strong>Shear12 / Shear13 / Shear23</strong> 仅接受单值
          （工程剪应变）。</li>
    </ul>

    <h4>共享输入（单轴/双轴通用）</h4>
    <ul>
      <li><strong>Temperature Points（&deg;C）</strong> &mdash; 可选，
          逗号分隔的温度列表。每个 case 在每个温度上重跑，同一 case 的
          各温度结果放在同一子文件夹，作业名和 CSV 名带温度标签
          （如 <code>Temp_025</code>）。</li>
      <li><strong>Nlgeom</strong>（大变形）&mdash; 复选框，默认<em>开</em>。
          只有当小变形分析足够时才关。</li>
      <li><strong>Unsymmetric matrix storage (UMAT)</strong> &mdash;
          复选框，默认<em>关</em>。UMAT 切线刚度不对称（非关联流动、
          Chaboche 等）时勾上。非对称求解器内存和耗时大致翻倍，按需启用。</li>
    </ul>

    <div class="callout callout-tip">
      <p>负值表示压缩。剪切输入使用工程剪应变约定。</p>
    </div>

    <div class="callout callout-note">
      <div class="callout-title">UMAT 是可选项</div>
      <p>UMAT <strong>不是必需的</strong>。如果你有自定义 Fortran
      <code>.for</code> 子程序就在 Basic Information 面板里选上，留空
      则用 Materials 里定义的材料 + Abaqus 内置弹塑性求解。</p>
    </div>

    <div class="callout callout-warn">
      <div class="callout-title">自动设置 Solution Controls</div>
      <p>每次弹塑性运行都会自动设置 <em>General Solution Controls</em>：
      <strong>Specify ON</strong>、<strong>Discontinuous analysis</strong>
      （I0=8、IR=10）、<strong>IC=30</strong>（默认 16）。日志里会有一行
      <code>[StaticStep] Solution controls: ...</code> 确认。</p>
    </div>

    <div class="callout callout-warn">
      <div class="callout-title">case 之间的防御性清理 + 文件夹防覆写</div>
      <p>每跑下一个 case 之前会清掉残留的 step、load、BC、constraint、
      预定义温度场、analysis set 和 reference point。Job 名是<em>稳定</em>的
      <code>Job_&lt;model&gt;_&lt;load&gt;_&lt;Temp&gt;.odb</code>
      （不带时间戳），可直接从 Abaqus Jobs 视图打开 ODB。若同名 Job 已存在
      则先删；若 load 子文件夹在磁盘上已存在，dispatcher 会自动加
      <code>(1)</code>、<code>(2)</code> 后缀，绝不覆盖旧结果。</p>
    </div>

    <div class="callout callout-note">
      <div class="callout-title">界面感知的自动路由</div>
      <p>如果所选模型是 Interface 选项卡产生的 <code>*_Interface</code>
      模型（或任何已含 COH3D8 内聚单元的模型），dispatcher 会自动切换到
      <code>PBC_UDFRP_Elastoplastic_interface</code>。GUI 行为不变，
      日志可确认路由。</p>
    </div>
  </div>

  <div class="tab-panel">
    <p>在 PBC 下施加宏观应变。<strong>双轴布局</strong>
    (Analysis Type = 6) 从预定列表里选一对两分量联合加载，跑一个联合 case。</p>

    <h4>双轴输入</h4>
    <p>下拉提供 15 种双分量组合：Strain11-Strain22、
    Strain11-Strain33、Strain11-Shear12、Strain11-Shear13、Strain11-Shear23、
    Strain22-Strain33、Strain22-Shear12、Strain22-Shear13、Strain22-Shear23、
    Strain33-Shear12、Strain33-Shear13、Strain33-Shear23、
    Shear12-Shear13、Shear12-Shear23、Shear13-Shear23。选一对，
    然后设置 <strong>Load 1 Max Strain</strong> 和
    <strong>Load 2 Max Strain</strong>。Strain 分量负值表示压缩，
    Shear 分量使用工程剪应变约定。</p>

    <h4>共享输入（单轴/双轴通用）</h4>
    <ul>
      <li><strong>Temperature Points（&deg;C）</strong> &mdash; 可选，
          逗号分隔的温度列表。每个 case 在每个温度上重跑，同一 case 的
          各温度结果放在同一子文件夹，作业名和 CSV 名带温度标签
          （如 <code>Temp_025</code>）。</li>
      <li><strong>Nlgeom</strong>（大变形）&mdash; 复选框，默认<em>开</em>。
          只有当小变形分析足够时才关。</li>
      <li><strong>Unsymmetric matrix storage (UMAT)</strong> &mdash;
          复选框，默认<em>关</em>。UMAT 切线刚度不对称（非关联流动、
          Chaboche 等）时勾上。非对称求解器内存和耗时大致翻倍，按需启用。</li>
    </ul>

    <div class="callout callout-tip">
      <p>负值表示压缩。剪切输入使用工程剪应变约定。</p>
    </div>

    <div class="callout callout-note">
      <div class="callout-title">UMAT 是可选项</div>
      <p>UMAT <strong>不是必需的</strong>。如果你有自定义 Fortran
      <code>.for</code> 子程序就在 Basic Information 面板里选上，留空
      则用 Materials 里定义的材料 + Abaqus 内置弹塑性求解。</p>
    </div>

    <div class="callout callout-warn">
      <div class="callout-title">自动设置 Solution Controls</div>
      <p>每次弹塑性运行都会自动设置 <em>General Solution Controls</em>：
      <strong>Specify ON</strong>、<strong>Discontinuous analysis</strong>
      （I0=8、IR=10）、<strong>IC=30</strong>（默认 16）。日志里会有一行
      <code>[StaticStep] Solution controls: ...</code> 确认。</p>
    </div>

    <div class="callout callout-warn">
      <div class="callout-title">case 之间的防御性清理 + 文件夹防覆写</div>
      <p>每跑下一个 case 之前会清掉残留的 step、load、BC、constraint、
      预定义温度场、analysis set 和 reference point。Job 名是<em>稳定</em>的
      <code>Job_&lt;model&gt;_&lt;load&gt;_&lt;Temp&gt;.odb</code>
      （不带时间戳），可直接从 Abaqus Jobs 视图打开 ODB。若同名 Job 已存在
      则先删；若 load 子文件夹在磁盘上已存在，dispatcher 会自动加
      <code>(1)</code>、<code>(2)</code> 后缀，绝不覆盖旧结果。</p>
    </div>

    <div class="callout callout-note">
      <div class="callout-title">界面感知的自动路由</div>
      <p>如果所选模型是 Interface 选项卡产生的 <code>*_Interface</code>
      模型（或任何已含 COH3D8 内聚单元的模型），dispatcher 会自动切换到
      <code>PBC_UDFRP_Elastoplastic_interface</code>。GUI 行为不变，
      日志可确认路由。</p>
    </div>
  </div>

  <div class="tab-panel">
    <p>选择要计算的导热分量：</p>
    <ul>
      <li><strong>K11, K12, K13 (X)</strong> / <strong>K21, K22, K23 (Y)</strong>
          / <strong>K31, K32, K33 (Z)</strong></li>
      <li><strong>Only Corresponding PBC</strong> — 同弹性面板。</li>
      <li><strong>Initial / Final Temperature (°C)</strong>、<strong>Segment</strong>
          — 可选温度扫描，输入单位为 °C，内部自动转 K。</li>
    </ul>
    <div class="callout callout-warn">
      <p>必须使用<strong>热</strong>类型网格（DC3D8 系列）。如果之前是
      力学网格，请先在 Mesh Control 选项卡重新划分。</p>
    </div>
  </div>
</div>

<h2>3.6.4 分析模型范围</h2>

<p>同样的 Current / All / Selected numbers 控件。多模型时，插件会为每个
模型提交一个 Abaqus 作业并汇总结果。</p>

<ul>
  <li><strong>Current</strong> — 仅分析所选模型。</li>
  <li><strong>All Models</strong> — 分析与所选模型同名、同模型序号规律的
      所有模型。</li>
  <li><strong>Selected numbers</strong> — 逗号 / 区间列表
      （如 <code>1,3,5-8</code>），指定要分析的模型序号。</li>
</ul>

<div class="callout callout-note">
  <div class="callout-title">批量分析现已支持含界面模型</div>
  <p>普通模型命名为 <code>&lt;base&gt;_&lt;N&gt;</code>，其中
  <code>N</code> 为模型序号。<strong>含界面模型</strong>（由界面选项卡生成）
  会把序号嵌入在末尾界面标签<em>之前</em>，例如
  <code>&lt;base&gt;_cohesive_3_D000</code>（内聚脱粘）或
  <code>&lt;base&gt;_thermal_3_&hellip;</code>（热界面 Kapitza 缝）。早期版本
  用简单的 <code>rsplit('_')</code> 解析序号，会把末尾标签（如
  <code>D000</code>）误当成序号，导致 <em>All Models</em> 与
  <em>Selected numbers</em> 在含界面模型上失效。现在调度器可同时识别两种
  命名方式，因此批量分析（All / Selected numbers）在普通模型<strong>和</strong>
  含界面模型上都能正确运行，含界面热导率分析也包含在内。</p>
</div>

<h2>3.6.5 行为说明</h2>

<ul>
  <li><strong>UMAT</strong> 输入会根据分析类型自动启用 / 禁用，仅
      Elastoplastic 时启用。即使启用也是<em>可选</em>，不需要时留空即可。</li>
  <li><strong>CTE 温度输入</strong>仅在勾选 CTE 复选框时启用。</li>
  <li>切换分析类型会触发对话框重排，只显示当前类型相关的字段。</li>
</ul>

<h2>3.6.6 点击 OK 之后 —— 输出文件与数据库变化</h2>

<p>对每个选中的模型，插件会：</p>
<ol>
  <li>在网格化的 <code>UDComposite</code> 实例上生成周期性边界条件。</li>
  <li>按所选分析类型创建分析步（每个模量一步，CTE 时再加一个热步）。</li>
  <li>提交 Abaqus 作业，等待完成，并把生成的 <code>.odb</code> 写到
      工作目录。</li>
  <li>对 ODB 做后处理，并在 ODB 旁边输出包含均质化结果的 CSV / TXT 摘要。</li>
</ol>

<p>批量运行（All / Selected numbers）时，每个模型会得到一份 ODB 和一份
摘要文件，命名沿用模型名。汇总结果显示在 Abaqus 的消息区。</p>
<h3>弹性 + CTE 输出</h3>

<table class="field-table">
  <thead><tr><th>文件</th><th>内容</th></tr></thead>
  <tbody>
    <tr>
      <td><code>&lt;part&gt;_elastic_properties.txt</code></td>
      <td>纯文本报告，记录均匀化后的工程模量（按勾选输出
      E11/E22/E33 和 G12/G13/G23），勾了 CTE 时还附带 CTE 值。
      <code>&lt;part&gt;_elastic_properties(easycopy).txt</code> 为
      EasyPBC 风格的"便于复制粘贴"版本。</td>
    </tr>
    <tr>
      <td><code>&lt;model&gt;_CTE_results.csv</code></td>
      <td>CTE 温度段每段一行：起始 / 终止 / 平均温度 和 CTE_X/CTE_Y/CTE_Z。
      批量运行时 dispatcher 会重命名加入温度范围。</td>
    </tr>
    <tr>
      <td><code>&lt;model&gt;_elastic_temperature_sweep_&lt;timestamp&gt;.csv</code></td>
      <td>仅在 <em>Temperature Points (&deg;C)</em> 非空时生成。每行汇总
      指定温度下的模量。</td>
    </tr>
  </tbody>
</table>

<h3>热导率输出</h3>

<table class="field-table">
  <thead><tr><th>文件</th><th>内容</th></tr></thead>
  <tbody>
    <tr>
      <td><code>&lt;part&gt;_thermal_properties.txt</code></td>
      <td>纯文本报告，按勾选方向列出导热张量
      （K11/K12/K13、K21/K22/K23、K31/K32/K33）。
      <code>(easycopy).txt</code> 是便于复制粘贴的版本。</td>
    </tr>
  </tbody>
</table>

<h3>粘弹性时域 / 频域输出</h3>

<table class="field-table">
  <thead><tr><th>文件命名</th><th>内容</th></tr></thead>
  <tbody>
    <tr>
      <td><code>&lt;model&gt;_E11_v12_v13_viscoelastic_time_Temp&lt;TTT&gt;.csv</code><br>
          <code>&lt;model&gt;_E33_v31_v32_viscoelastic_time_Temp&lt;TTT&gt;.csv</code><br>
          <code>&lt;model&gt;_G12_viscoelastic_time_Temp&lt;TTT&gt;.csv</code><br>
          <code>&lt;model&gt;_G13_viscoelastic_time_Temp&lt;TTT&gt;.csv</code><br>
          <code>&lt;model&gt;_G23_viscoelastic_time_Temp&lt;TTT&gt;.csv</code></td>
      <td>时域松弛模量 / 泊松比，按选定时间点采样。每个激活分量、每个温度
      各一个文件。频域用 <code>_viscoelastic_freq_</code> 替代
      <code>_viscoelastic_time_</code>，列对应复模量（storage / loss）的
      频率采样。</td>
    </tr>
  </tbody>
</table>

<h3>弹塑性 CSV 输出</h3>

<p>对每个（模型、load case、温度）组合，分析器会在对应子文件夹内写下
这些文件：</p>

<table class="field-table">
  <thead><tr><th>文件</th><th>内容</th></tr></thead>
  <tbody>
    <tr>
      <td><code>&lt;model&gt;_all_RP_history_&lt;case&gt;.csv</code></td>
      <td>每帧 × 每个 reference point 的历程（U1/U2/U3、RF1/RF2/RF3、
      每个 RP 的 6 个应力 / 应变分量）。</td>
    </tr>
    <tr>
      <td><code>&lt;model&gt;_macroscopic_stress_strain_&lt;case&gt;.csv</code></td>
      <td>每帧完整的 6+6 宏观应力 / 应变张量，外加 von Mises、
      hydrostatic、triaxiality、体积应变、等效应变率。剪切量用
      <code>2*Gamma_ij</code>（工程剪应变）。</td>
    </tr>
    <tr>
      <td><code>&lt;model&gt;_true_stress_strain_&lt;case&gt;.csv</code></td>
      <td>加载方向上的真（Cauchy）应力 / 对数应变。列布局根据加载类型不同：
        <ul>
          <li><em>正应变</em>（E11/E22/E33）：4 列数据 &mdash;
          <code>True_Strain</code>、<code>True_Stress</code>、
          <code>True_Strain_Abs</code>、<code>True_Stress_Abs</code>。
          后两列是前两列的 abs，方便压缩曲线直接画在上半平面。</li>
          <li><em>剪切</em>（G12/G13/G23）：2 列数据 &mdash;
          <code>True_Shear_Strain</code>（张量真剪应变，
          <code>= ln(1 + eps_ij) * sign</code>，乘 2 得到工程剪应变）和
          <code>True_Shear_Stress</code>（Cauchy 剪应力）。</li>
        </ul>
      </td>
    </tr>
    <tr>
      <td><code>&lt;model&gt;_volume_averages_&lt;case&gt;.csv</code></td>
      <td>RVE 内的体积平均应力 / 应变 / Mises（一行）。</td>
    </tr>
    <tr>
      <td><code>&lt;model&gt;_analysis_summary_&lt;case&gt;.csv</code></td>
      <td>单行总结：模型名、instance、加载标签、有效性质、apparent stiffness。</td>
    </tr>
  </tbody>
</table>
`;
