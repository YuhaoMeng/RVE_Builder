// Auto-loaded via <script> tag from index.html
// Edit the HTML inside the template literal below; do NOT change the wrapper.
window.helpContent = window.helpContent || {};
window.helpContent['pt/tab2_mesh'] = `
<!-- ===== SECTION: tab2_mesh (PT-BR) ======================================= -->
<h1>3.2 · Mesh Control</h1>

<p>
  A aba <strong>Mesh Control</strong> aplica sementes e gera a malha do(s)
  modelo(s) RVE selecionado(s). Também permite trocar tipo e formato de
  elemento conforme a análise planejada.
</p>

<figure class="figure">
  <img src="images/Mesh_Seed_Diagram.png" alt="Diagrama de sementes de malha">
  <figcaption>Fig 2 — Onde cada parâmetro de semeadura atua.</figcaption>
</figure>

<h2>3.2.1 Select Model</h2>

<p>Listas suspensas selecionam o modelo e a Part a malhar. O plug-in foi
projetado para a Part <code>UDComposite</code> — deixe selecionada, salvo
se você customizou a geometria.</p>

<h2>3.2.2 Select Model Range for Meshing</h2>

<p>Controle em lote comum a todas as abas:</p>
<ul>
  <li><strong>Current Model</strong> — apenas o modelo atualmente selecionado.</li>
  <li><strong>All Models</strong> — todos os modelos com o mesmo nome
      principal.</li>
  <li><strong>Selected numbers</strong> — lista personalizada usando
      "<code>-</code>" para intervalos e "<code>,</code>" para itens.
      Exemplo: <code>1, 4-9</code>.</li>
</ul>

<h2>3.2.3 Seeds Control (by Number)</h2>

<table class="field-table">
  <thead><tr><th>Campo</th><th>Padrão</th><th>Significado</th></tr></thead>
  <tbody>
    <tr><td>Circle-dominant and Arc</td><td>12</td>
        <td>Sementes ao redor de círculos / arcos das fibras (vista da seção transversal).</td></tr>
    <tr><td>Cross-Section Edges</td><td>20</td>
        <td>Sementes nas arestas externas da seção transversal.</td></tr>
    <tr><td>Along Fiber Direction Edges</td><td>10</td>
        <td>Sementes ao longo do eixo da fibra (direção X).</td></tr>
    <tr><td>Minimum Size Control</td><td>0.1</td>
        <td>Fator mínimo de tamanho de elemento (passado ao malhador do Abaqus).</td></tr>
  </tbody>
</table>

<h3>Sementes recomendadas — fórmulas</h3>

<p>
  Seja <code>NR</code> o número de sementes ao redor da fibra (valor digitado
  em <strong>Circle-dominant and Arc</strong>). O <em>tamanho aproximado de
  elemento</em> em uma fibra é:
</p>
<p style="text-align:center;">
  $$ \\text{size}_{\\mathrm{approx}} \\;=\\; \\dfrac{\\pi \\, d_f}{N_R} $$
</p>
<p>
  Para manter a malha da seção transversal / espessura consistente com esse
  tamanho, o número de sementes <code>NL</code> em uma aresta de comprimento
  <code>L</code> deve ser:
</p>
<p style="text-align:center;">
  $$ N_L \\;=\\; \\dfrac{L}{\\text{size}_{\\mathrm{approx}}} \\;=\\; \\dfrac{L \\, N_R}{\\pi \\, d_f} $$
</p>
<p>
  Aplique a fórmula a <strong>Cross-Section Edges</strong> com
  <code>L = a</code> (ou <code>b</code>), e a
  <strong>Along Fiber Direction Edges</strong> com <code>L = t</code>.
</p>

<div id="seed-calc" class="seed-calculator">
  <h4>Calculadora interativa de sementes</h4>
  <div class="calc-grid">
    <label>Diâmetro da fibra d<sub>f</sub>
      <input type="number" data-calc="df" value="7" step="0.1" min="0">
    </label>
    <label>Sementes na fibra N<sub>R</sub>
      <input type="number" data-calc="nr" value="12" step="1" min="1">
    </label>
    <label>Comprimento da aresta L
      <input type="number" data-calc="l" value="50" step="1" min="0">
    </label>
  </div>
  <div class="calc-output">
    <div>Tamanho aprox. do elemento: <span data-calc="size">—</span></div>
    <div>N<sub>L</sub> recomendado: <span data-calc="nl">—</span></div>
  </div>
</div>

<div class="callout callout-note">
  <p>A calculadora é só a fórmula acima encapsulada em uma UI. Edite
  qualquer campo para ver o resultado em tempo real. Para Cross-Section
  Edges use <code>L</code> = largura ou altura do RVE; para Along Fiber
  Direction Edges use <code>L</code> = profundidade do RVE.</p>
</div>

<h2>3.2.4 Mesh Type Selection</h2>

<p>Escolha o tipo de análise <em>antes</em> de malhar — a biblioteca de
elementos depende disso.</p>

<table class="field-table">
  <thead><tr><th>Mesh Type</th><th>Elemento linear</th><th>Use com</th></tr></thead>
  <tbody>
    <tr><td>Mechanical Analysis (C3D8)</td><td>C3D8 / C3D6</td>
        <td>Elastic, CTE, Viscoelastic, Elastoplastic.</td></tr>
    <tr><td>Thermal Analysis (DC3D8)</td><td>DC3D8 / DC3D6</td>
        <td>Thermal Conductivity.</td></tr>
    <tr><td>Thermo-Mechanical Coupled (C3D8T)</td><td>C3D8T / C3D6T</td>
        <td>Problemas térmico–estruturais acoplados.</td></tr>
  </tbody>
</table>

<h2>3.2.5 Element Options</h2>

<p>Toggles abaixo dos botões de Mesh Type permitem aprimorar os elementos:</p>

<div class="inline-tabs">
  <div class="tab-buttons">
    <button class="tab-btn">Mecânico / Acoplado</button>
    <button class="tab-btn">Térmico</button>
  </div>
  <div class="tab-panel">
    <ul>
      <li><strong>Quadratic (20-nodes)</strong> — promove C3D8 → C3D20 (e
          C3D6 → C3D15). Maior precisão, custo bem maior.</li>
      <li><strong>Reduced Integration (R)</strong> — adiciona o sufixo "R".
          Cuidado com modos hourglass em malhas muito grosseiras.</li>
      <li><strong>Hybrid Formulation (H)</strong> — adiciona o sufixo "H".
          Necessário para matrizes quase incompressíveis.</li>
    </ul>
  </div>
  <div class="tab-panel">
    <ul>
      <li><strong>Quadratic (20-node)</strong> — DC3D8 → DC3D20.</li>
      <li><strong>Reduced Integration (R)</strong></li>
      <li><strong>Convection/Diffusion (C)</strong></li>
      <li><strong>Dispersion Control (D)</strong></li>
    </ul>
    <div class="callout callout-note">
      <p><strong>Regras de elementos térmicos:</strong> apenas certas
      combinações produzem um símbolo de elemento Abaqus válido. As
      inválidas são ignoradas no momento do malhamento.</p>
    </div>
  </div>
</div>

<h2>3.2.6 Element Shape</h2>

<ul>
  <li><strong>HEX-dominated, C3D8 + C3D6</strong> — equilíbrio padrão.</li>
  <li><strong>HEX-dominated, C3D20 + C3D15</strong> — versão quadrática.</li>
  <li><strong>WEDGE, C3D6</strong> — só wedge, útil quando a malha
      hexaedral falha em Vf extremos.</li>
</ul>

<div class="callout callout-warn">
  <div class="callout-title">Outros tipos de elemento são restritos</div>
  <p>Para garantir que as PBC possam ser aplicadas depois, o plug-in
  restringe as opções disponíveis. Substituir por outros tipos manualmente
  pode quebrar a aba Analysis.</p>
</div>

<h2>3.2.7 Após clicar em OK — saídas e mudanças no banco de dados</h2>

<p>
  Esta aba não grava arquivos externos. O(s) modelo(s) selecionado(s)
  é(são) malhado(s) in-place; o resultado pode ser visto no módulo Mesh do
  Abaqus. Especificamente:
</p>
<ul>
  <li>Sementes de aresta são aplicadas conforme os valores acima.</li>
  <li>A malha é gerada usando o formato escolhido.</li>
  <li>O tipo de elemento é definido em todas as cells conforme as opções
      Mesh Type + Element Options (ex: C3D8R, C3D20H, DC3D8).</li>
  <li>Se um fator global de tamanho for necessário, é calculado a partir
      de <em>Minimum Size Control</em>.</li>
</ul>

<div class="callout callout-tip">
  <div class="callout-title">Verificação</div>
  <p>Após malhar, troque para o módulo Mesh do Abaqus para inspecionar a
  contagem e qualidade dos elementos. A Part <code>UDComposite</code> agora
  contém uma instância malhada pronta para as abas Materials e Analysis.</p>
</div>
`;
