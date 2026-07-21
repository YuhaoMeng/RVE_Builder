// Auto-loaded via <script> tag from index.html
// Edit the HTML inside the template literal below; do NOT change the wrapper.
window.helpContent = window.helpContent || {};
window.helpContent['pt/tab5_interface'] = `
<!-- ===== SECTION: tab5_interface (PT-BR) ================================== -->
<h1>3.5 · Interface</h1>

<p>
  A aba <strong>Interface</strong> insere costuras coesivas (COH3D8) de
  espessura zero na interface fibra-matriz de um RVE malhado, de modo que
  análises elastoplásticas ou térmicas posteriores possam modelar o
  comportamento de descolamento dessa interface. A aba trabalha em uma
  <em>cópia</em> do modelo selecionado, preservando a malha original.
</p>

<div class="callout callout-warn">
  <div class="callout-title">Ordem de execução</div>
  <p>Esta aba precisa de um modelo já malhado e com materiais atribuídos.
  Execute <strong>Mesh Control</strong> e <strong>Materials</strong>
  antes. Se você também quer estudar efeitos de vazios, execute
  <strong>Void Insertion</strong> antes de Interface.</p>
</div>

<h2>3.5.1 Select Part</h2>

<ul>
  <li><strong>Model</strong> — lista todos os modelos abertos.</li>
  <li><strong>Part</strong> — tipicamente <code>UDComposite</code>. A lista
      de Parts se preenche automaticamente conforme o modelo escolhido.</li>
</ul>

<h2>3.5.2 Material para a interface</h2>

<p>Escolha o material coesivo a atribuir às costuras COH3D8. A lista vem
dos materiais já definidos no modelo escolhido — defina o material da
interface na aba Materials (ou no CAE) antes de abrir esta aba.</p>

<h2>3.5.3 Descolamento inicial (Initial Debonding)</h2>

<p>Um único número, <strong>D</strong>, em porcentagem (0–100). Controla
quanto da interface fibra-matriz já começa <em>descolada</em> antes do
início da análise.</p>

<ul>
  <li><code>D = 0</code> → todas as costuras COH3D8 começam coladas. A lei
      coesiva governa o dano progressivo quando a carga é aplicada.</li>
  <li><code>D &gt; 0</code> → essa fração das costuras é removida no
      momento da inserção, simulando defeitos de fabricação, fadiga prévia
      ou vazios que já tocam a interface.</li>
  <li>Se o modelo já tem vazios que substituem parte da interface das
      fibras (aba Void Insertion), esses vazios <em>contam</em> dentro de
      <code>D</code>. Com 3% de vazios já em contato com a interface,
      pedir <code>D = 5%</code> apaga outros 2% de elementos coesivos.</li>
  <li>D é limitado de modo que cada fibra independente mantenha pelo menos
      um elemento coesivo colado. Isso evita fibras flutuantes que travariam
      o solver.</li>
</ul>

<h2>3.5.4 Faixa de modelos para a operação de interface</h2>

<p>Mesmo controle em lote das outras abas (Current / All / Selected numbers).
"All Models" se aplica a todos os modelos com mesmo nome principal.</p>

<h2>3.5.5 Após clicar em OK</h2>

<p>Para cada modelo alvo, o plug-in:</p>
<ol>
  <li>Duplica o modelo em um novo modelo
      <code>&lt;model&gt;_Interface_D&lt;D final %&gt;</code> para que a
      malha original fique intocada.</li>
  <li>Gera elementos coesivos COH3D8 em todas as interfaces fibra-matriz
      da cópia, usando o material coesivo escolhido.</li>
  <li>Se <code>D &gt; 0</code>, remove a fração pedida de elementos
      coesivos (seleção aleatória, descontando vazios e respeitando o
      mínimo por fibra).</li>
  <li>Imprime um resumo na área de mensagens: nome do modelo, sets de
      elementos fibra / matriz, faces de interface, COH3D8 criados, nós
      inseridos, geometrias de interface de fibras independentes,
      <code>D_void</code> induzido por vazios, <code>D</code> do usuário e
      <code>D</code> final.</li>
  <li>O mesmo resumo é gravado em um relatório txt no disco:
      <code>Interface_Information_&lt;model&gt;.txt</code> em execuções de
      modelo único, ou
      <code>Interface_Information_Batch_D&lt;D&gt;.txt</code> em execuções
      em lote. Se um relatório com o mesmo nome já existir no diretório
      de trabalho, um sufixo é adicionado para não sobrescrever.</li>
</ol>

<h2>3.5.6 O que muda depois</h2>

<p>A aba Interface não roda análises por si só, apenas prepara a malha.
Execuções subsequentes da aba <strong>Analysis</strong> sobre os modelos
<code>*_Interface</code> se comportam assim:</p>

<table class="field-table">
  <thead><tr><th>Tipo de análise</th><th>Comportamento em modelos com interface</th></tr></thead>
  <tbody>
    <tr>
      <td><strong>Elastic + CTE</strong> / Viscoelastic / Viscoelastic Freq</td>
      <td>O kernel PBC padrão roda no modelo duplicado. As costuras
      coesivas respondem segundo a rigidez elástica do material.</td>
    </tr>
    <tr>
      <td><strong>Elastoplastic (Uniaxial / Biaxial)</strong></td>
      <td>Quando o modelo escolhido é um modelo <code>*_Interface</code>
      com <code>D &gt; 0</code> (ou contém costuras COH3D8), o dispatcher
      roteia automaticamente para
      <code>PBC_UDFRP_Elastoplastic_interface</code> em vez do kernel
      padrão. Essa variante trata os elementos COH3D8 durante a geração
      de equações e o setup do step.</td>
    </tr>
    <tr>
      <td><strong>Thermal Conductivity</strong></td>
      <td>Mesmo roteamento: o dispatcher usa
      <code>PBC_UDFRP_thermal_conductivity_Interfaceh</code>, e as costuras
      coesivas contribuem com a condutividade / resistência térmica
      correta na interface.</td>
    </tr>
  </tbody>
</table>

<div class="callout callout-tip">
  <div class="callout-title">Dicas</div>
  <ul>
    <li>Para comparar <em>com</em> e <em>sem</em> interface, mantenha o
    modelo original intocado e rode Analysis tanto em
    <code>&lt;model&gt;</code> quanto em
    <code>&lt;model&gt;_Interface</code>.</li>
    <li>As unidades do material coesivo precisam combinar com o resto do
    modelo (MPa / mm etc. — manter um conjunto consistente).</li>
    <li>Reexecutar esta aba sobre o mesmo modelo-fonte gera uma nova
    cópia <code>*_Interface</code>; a anterior fica como está, exclua-a
    manualmente se precisar.</li>
  </ul>
</div>
`;
