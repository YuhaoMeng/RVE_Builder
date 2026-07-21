// Auto-loaded via <script> tag from index.html
// Edit the HTML inside the template literal below; do NOT change the wrapper.
window.helpContent = window.helpContent || {};
window.helpContent['zh/tab3_materials'] = `
<\!-- ===== SECTION: tab3_materials (中文) =================================== -->
<h1>3.3 · 材料</h1>

<p>
  <strong>Materials</strong> 选项卡为已网格化的 RVE 分配纤维和基体材料，
  并创建相应的 Section。支持跨多个模型批量传播。
</p>

<h2>前提条件</h2>

<div class="callout callout-warn">
  <div class="callout-title">先定义材料</div>
  <p>本选项卡<em>不</em>创建材料，只分配已存在的材料。打开本选项卡之前，
  请先在 Abaqus 标准的 Material 模块中定义纤维材料和基体材料 ——
  至少在目标模型之一中定义即可。批量操作会从该源模型把材料复制到其他模型。</p>
</div>

<h2>3.3.1 选择材料（Select materials）</h2>

<p>两个下拉菜单：</p>
<ul>
  <li><strong>Fiber</strong> — 选择已经为纤维相定义好的材料。</li>
  <li><strong>Matrix</strong> — 选择已经为基体相定义好的材料。</li>
</ul>

<p>点击 OK 后插件会：</p>
<ol>
  <li>为每种材料创建一个实体 Section。</li>
  <li>把 Section 分配给创建 RVE 时生成的 <code>Set-Fiber</code> 和 <code>Set-Matrix</code> Set。</li>
  <li>设置材料方向（沿 X 方向）。</li>
</ol>

<h2>3.3.2 材料应用模型范围（Select Model Range for Material）</h2>

<p>与其他选项卡相同的批量控件（Current / All / Selected numbers）。
当应用到多个模型时，插件会借助 Abaqus 的 <code>materialsFromOdb</code>
功能：先把源模型的材料定义写入临时 ODB，再读出来供其他模型使用 ——
因为 Abaqus 没有内置的跨模型材料复制功能。</p>

<div class="callout callout-note">
  <div class="callout-title">批量复制材料时的提示信息</div>
  <p>过程中可能出现少量警告（来自临时 ODB 的写入）。只要 Section 分配
  成功，这些警告可以忽略。</p>
</div>

<h2>如果某个模型缺材料怎么办？</h2>

<p>选 <strong>All Models</strong> 或 <strong>Selected numbers</strong> 时，
如果目标模型缺少纤维 / 基体材料，插件会自动从源模型复制 ——
你只需要在一个模型中定义材料。</p>

<h2>3.3.3 点击 OK 之后 —— 输出文件与数据库变化</h2>

<p>对每个受影响的模型，插件会：</p>
<ol>
  <li>为每种材料创建一个 Solid Section（<code>Fiber-Section</code> 和
      <code>Matrix-Section</code>）。</li>
  <li>把这些 Section 分配给创建 RVE 时生成的 <code>Set-Fiber</code> 和
      <code>Set-Matrix</code>。</li>
  <li>把材料方向设为沿纤维轴向（X 方向）。</li>
  <li>批量模式下：在工作目录创建一个临时 <code>.odb</code> 用于跨模型
      复制材料定义，完成后会清理掉。</li>
</ol>

<p>本选项卡正常完成后不会在工作目录留下任何永久文件。</p>
`;
