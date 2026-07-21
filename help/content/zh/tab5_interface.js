// Auto-loaded via <script> tag from index.html
// Edit the HTML inside the template literal below; do NOT change the wrapper.
window.helpContent = window.helpContent || {};
window.helpContent['zh/tab5_interface'] = `
<!-- ===== SECTION: tab5_interface (中文) =================================== -->
<h1>3.5 · 界面（Interface）</h1>

<p>
  <strong>Interface</strong> 选项卡在已网格化 RVE 的纤维-基体界面处插入
  零厚度内聚单元（COH3D8），用于在后续弹塑性或热导率分析里模拟界面脱粘。
  该选项卡作用在所选模型的<em>副本</em>上，原始网格保持不变。
</p>

<div class="callout callout-warn">
  <div class="callout-title">执行顺序</div>
  <p>本选项卡需要已网格化、已分配材料的模型。请先完成
  <strong>Mesh Control</strong> 和 <strong>Materials</strong>。如果要叠加
  孔洞效应，请在打开 Interface 之前先运行 <strong>Void Insertion</strong>。</p>
</div>

<h2>3.5.1 选择 Part</h2>

<ul>
  <li><strong>Model</strong> — 列出所有打开的模型。</li>
  <li><strong>Part</strong> — 通常是 <code>UDComposite</code>，
      Part 列表会根据所选模型自动填充。</li>
</ul>

<h2>3.5.2 界面材料</h2>

<p>从所选模型中已有的材料里挑选一个赋给 COH3D8 内聚单元。请先在
Materials 选项卡或 CAE 里定义好界面材料，再打开本选项卡。</p>

<h2>3.5.3 初始脱粘（Initial Debonding）</h2>

<p>一个数字 <strong>D</strong>，单位百分比（0–100），控制有多少纤维-基体
界面在分析开始前就已经<em>脱粘</em>。</p>

<ul>
  <li><code>D = 0</code> → 所有 COH3D8 单元都处于粘结状态。加载后由本构
      关系控制损伤演化。</li>
  <li><code>D &gt; 0</code> → 插入时直接删除对应比例的内聚单元，用于模拟
      制造缺陷、疲劳预损或已经接触界面的孔洞。</li>
  <li>如果模型里有 Void Insertion 引入的、已经接触界面的孔洞，那些孔洞算
      作 <code>D</code> 的一部分。例如界面上 3% 已被孔洞占据，
      设 <code>D = 5%</code> 时只会再额外删除 2% 的内聚单元。</li>
  <li>D 受到一个保底限制：每根独立的纤维至少保留 1 个粘结的内聚单元，
      避免出现"游离的"纤维而导致求解失败。</li>
</ul>

<h2>3.5.4 界面操作的模型范围</h2>

<p>跟其他选项卡相同的批量控件（Current / All / Selected numbers）。
"All Models" 应用于所有与所选模型同主名的模型。</p>

<h2>3.5.5 点击 OK 之后</h2>

<p>对每个目标模型，插件会：</p>
<ol>
  <li>把模型复制成一个新的
      <code>&lt;model&gt;_Interface_D&lt;最终 D %&gt;</code> 模型，
      原网格不受影响。</li>
  <li>在副本里的每个纤维-基体界面生成 COH3D8 内聚单元，材料为上面选定的
      界面材料。</li>
  <li>若 <code>D &gt; 0</code>，随机删除指定比例的内聚单元
      （已考虑孔洞贡献和每根纤维的保底约束）。</li>
  <li>在消息区打印汇总：模型名、纤维 / 基体单元集名、界面 face 数、
      生成的 COH3D8 单元数、插入的节点数、独立纤维界面几何数、
      孔洞引起的 <code>D_void</code>、用户 <code>D</code>、
      最终 <code>D</code>。</li>
  <li>同样的汇总也会写到磁盘上的 txt 报告：单模型运行时文件名是
      <code>Interface_Information_&lt;model&gt;.txt</code>，
      批量运行时是 <code>Interface_Information_Batch_D&lt;D&gt;.txt</code>。
      如果工作目录里已经存在同名报告，会自动加后缀避免覆盖。</li>
</ol>

<h2>3.5.6 对后续分析的影响</h2>

<p>Interface 选项卡本身不跑分析，只准备网格。之后在 Analysis 选项卡上对
<code>*_Interface</code> 模型跑分析时，行为如下：</p>

<table class="field-table">
  <thead><tr><th>分析类型</th><th>对启用界面的模型的行为</th></tr></thead>
  <tbody>
    <tr>
      <td><strong>Elastic + CTE</strong> / 粘弹时域 / 粘弹频域</td>
      <td>用标准 PBC kernel 跑复制后的模型。内聚单元按其材料的弹性刚度
      参与响应。</td>
    </tr>
    <tr>
      <td><strong>弹塑性（单轴 / 双轴）</strong></td>
      <td>当所选模型是 <code>*_Interface</code> 模型且
      <code>D &gt; 0</code>（或存在 COH3D8 单元）时，dispatcher 会自动
      切换到 <code>PBC_UDFRP_Elastoplastic_interface</code>，
      而不是默认 kernel。该 kernel 在生成方程和设置分析步时正确处理 COH3D8。</td>
    </tr>
    <tr>
      <td><strong>热导率</strong></td>
      <td>同样的自动路由：dispatcher 使用
      <code>PBC_UDFRP_thermal_conductivity_Interfaceh</code>，
      内聚单元正确贡献界面的热阻 / 热导。</td>
    </tr>
  </tbody>
</table>

<div class="callout callout-tip">
  <div class="callout-title">提示</div>
  <ul>
    <li>想对比"有界面 vs 无界面"的差异，保留原模型不动，分别对
    <code>&lt;model&gt;</code> 和 <code>&lt;model&gt;_Interface</code> 跑
    Analysis。</li>
    <li>内聚材料的单位必须跟模型其余部分一致（MPa / mm 等保持一套自洽单位）。</li>
    <li>对同一源模型再次运行本选项卡会生成新的 <code>*_Interface</code>
    副本；旧副本不会自动删除，请手动清理。</li>
  </ul>
</div>
`;
