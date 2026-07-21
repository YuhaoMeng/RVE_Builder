// Auto-loaded via <script> tag from index.html
// Edit the HTML inside the template literal below; do NOT change the wrapper.
window.helpContent = window.helpContent || {};
window.helpContent['pt/tab3_materials'] = `
<!-- ===== SECTION: tab3_materials (PT-BR) ================================== -->
<h1>3.3 · Materials</h1>

<p>
  A aba <strong>Materials</strong> atribui materiais à fibra e à matriz no
  RVE malhado, e cria as Sections correspondentes. Suporta propagação em
  lote entre vários modelos.
</p>

<h2>Pré-requisito</h2>

<div class="callout callout-warn">
  <div class="callout-title">Defina os materiais antes</div>
  <p>Esta aba <em>não</em> cria materiais — apenas atribui materiais já
  existentes. Antes de abri-la, defina o material da fibra e o da matriz no
  módulo padrão Material do Abaqus em pelo menos um dos modelos. A operação
  em lote copia os materiais para os outros.</p>
</div>

<h2>3.3.1 Select materials</h2>

<p>Dois drop-downs:</p>
<ul>
  <li><strong>Fiber</strong> — material previamente definido para a fase fibra.</li>
  <li><strong>Matrix</strong> — material previamente definido para a fase matriz.</li>
</ul>

<p>Clique OK para:</p>
<ol>
  <li>Criar uma Section sólida por material.</li>
  <li>Atribuir as Sections aos sets <code>Fibers</code> e <code>Matrix</code>
      criados em Create RVE.</li>
  <li>Definir orientação do material (eixo X).</li>
</ol>

<h2>3.3.2 Select Model Range for Material</h2>

<p>Mesmo controle em lote das outras abas (Current / All / Selected
numbers). Para múltiplos modelos, o plug-in usa
<code>materialsFromOdb</code> do Abaqus para copiar os materiais do modelo
"fonte" para os outros antes de atribuir as Sections — o Abaqus não tem
cópia direta de material entre modelos, então essa etapa gera um ODB
temporário.</p>

<div class="callout callout-note">
  <div class="callout-title">Mensagens durante a cópia em lote</div>
  <p>Pode haver alguns avisos inofensivos enquanto o ODB temporário é
  escrito. Podem ser ignorados desde que as atribuições de Section
  finalizem com sucesso.</p>
</div>

<h2>E se um modelo não tiver o material?</h2>

<p>Selecionando <strong>All Models</strong> ou
<strong>Selected numbers</strong>, se algum modelo-alvo ainda não tiver
os materiais definidos, o plug-in copia automaticamente do modelo fonte —
basta definir os materiais em um único modelo.</p>

<h2>3.3.3 Após clicar em OK — saídas e mudanças no banco de dados</h2>

<p>Para cada modelo afetado, o plug-in:</p>
<ol>
  <li>Cria uma Solid Section por material (<code>Fiber-Section</code>
      e <code>Matrix-Section</code>).</li>
  <li>Atribui essas Sections aos sets <code>Set-Fiber</code> e
      <code>Set-Matrix</code> criados em Create RVE.</li>
  <li>Define a orientação do material ao longo do eixo da fibra (X).</li>
  <li>No modo lote: cria um <code>.odb</code> temporário no diretório de
      trabalho, usado apenas para copiar materiais entre modelos, e o
      remove em seguida.</li>
</ol>

<p>Nenhum arquivo permanente é deixado no diretório de trabalho após a
execução com sucesso desta aba.</p>
`;
