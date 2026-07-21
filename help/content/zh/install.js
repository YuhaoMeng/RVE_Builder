// Auto-loaded via <script> tag from index.html
// Edit the HTML inside the template literal below; do NOT change the wrapper.
window.helpContent = window.helpContent || {};
window.helpContent['zh/install'] = `
<\!-- ===== SECTION: install (中文) ========================================== -->
<h1>2 · 插件安装</h1>

<p>
  本插件基于 <strong>Abaqus/CAE 2024</strong>，使用 Abaqus 内置的 Python 3
  解释器。插件会在 GitHub 上不定期更新；为避免运行时兼容问题，请使用
  推荐的 Abaqus 版本。
</p>

<h2>安装位置</h2>

<p>把整个 <code>RVE_Builder_plugin</code> 文件夹复制到 Abaqus 的插件目录。
在 Windows 上通常是：</p>

<pre><code>C:\\SIMULIA\\CAE\\plugins\\2024\\</code></pre>

<p>复制完成后重启 Abaqus/CAE。插件会出现在
<strong>Plug-ins → RVE Builder (UDFRPs)</strong> 菜单中。</p>

<h2>包内文件</h2>

<table class="field-table">
  <thead>
    <tr><th>文件</th><th>类型</th><th>用途</th></tr>
  </thead>
  <tbody>
    <tr><td><code>RVE_Builder_UDFRPs_plugin.py</code></td><td>GUI 表单</td>
        <td>注册插件菜单项并定义所有关键字绑定。</td></tr>
    <tr><td><code>RVE_Builder_UDFRPsDB.py</code></td><td>GUI 对话框</td>
        <td>构建带选项卡的对话框窗口并连接 UI 事件。</td></tr>
    <tr><td><code>RVE_Builder_UDFRPs.py</code></td><td>内核</td>
        <td>实现各选项卡触发的实际操作。</td></tr>
    <tr><td><code>Generate_UDFRPs_MonteCarlo.py</code></td><td>生成器</td>
        <td>Monte-Carlo 纤维坐标生成器。</td></tr>
    <tr><td><code>Generate_UDFRPs_RSE.py</code></td><td>生成器</td>
        <td>RSE 纤维坐标生成器。</td></tr>
    <tr><td><code>PBC_UDFRP_Elastic_CTE.py</code></td><td>分析器</td>
        <td>弹性 + CTE 均质化（analysis_type = 1）。</td></tr>
    <tr><td><code>PBC_UDFRP_Viscoelastic_Time.py</code></td><td>分析器</td>
        <td>时域粘弹性分析（analysis_type = 2）。</td></tr>
    <tr><td><code>PBC_UDFRP_Viscoelastic_Frequency.py</code></td><td>分析器</td>
        <td>频域粘弹性分析（analysis_type = 3）。</td></tr>
    <tr><td><code>PBC_UDFRP_Elastoplastic.py</code></td><td>分析器</td>
        <td>宏观应变下的弹塑性分析。同时覆盖单轴（analysis_type = 4）和
        双轴（analysis_type = 6）。每次运行会自动设置 Solution Controls 为
        <em>Specify ON、Discontinuous、IC = 30</em>，GUI 提供
        <em>Nlgeom</em> 和 <em>Unsymmetric 矩阵存储</em>两个开关。</td></tr>
    <tr><td><code>PBC_UDFRP_thermal_conductivity.py</code></td><td>分析器</td>
        <td>稳态热导率张量（analysis_type = 5）。</td></tr>
    <tr><td><code>PBC_UDFRP_Elastoplastic_interface.py</code></td><td>分析器</td>
        <td>弹塑性 kernel 的"带界面"变体；当所选模型已含 COH3D8 内聚单元
        （例如 Interface 选项卡产生的 <code>*_Interface</code> 模型）时，
        由 dispatcher 自动选用。</td></tr>
    <tr><td><code>PBC_UDFRP_thermal_conductivity_Interfaceh.py</code></td><td>分析器</td>
        <td>热导率 kernel 的“带界面”变体，同样自动路由。</td></tr>
  </tbody>
</table>

<h2>验证安装</h2>
<ol>
  <li>打开 Abaqus/CAE 2024。</li>
  <li>顶部菜单 <strong>Plug-ins</strong>。</li>
  <li>应能看到 <strong>RVE Builder (UDFRPs)</strong>。点击打开对话框。</li>
  <li>对话框应显示 6 个选项卡：Create RVE、Mesh Control、Materials、
      Void Insertion、Interface、Analysis。</li>
</ol>

<details class="collapsible">
  <summary>常见问题</summary>
  <p><strong>菜单中找不到插件。</strong>检查文件夹路径是否正确；右键文件 →
  属性 → 解除锁定。</p>
  <p><strong>"Module not found" 错误。</strong>缺少某个重命名后的伴随文件。
  确认上表中所有文件都在插件目录的根，没被放进子文件夹。</p>
  <p><strong>"AttributeError: object has no attribute …"。</strong>可能加载
  了过期的 <code>__pycache__</code>。删除插件目录中的
  <code>__pycache__</code> 文件夹后重启 Abaqus。</p>
</details>
`;
