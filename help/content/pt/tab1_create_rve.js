// Auto-loaded via <script> tag from index.html
// Edit the HTML inside the template literal below; do NOT change the wrapper.
window.helpContent = window.helpContent || {};
window.helpContent['pt/tab1_create_rve'] = `
<!-- ===== SECTION: tab1_create_rve (PT-BR) ================================= -->
<h1>3.1 · Create RVE</h1>

<p>
  A aba <strong>Create RVE</strong> gera a geometria do RVE. Você define
  o nome do modelo, escolhe como os centros das fibras são produzidos,
  define os parâmetros geométricos e quantos modelos serão gerados em lote.
</p>

<figure class="figure">
  <img src="images/Random_RVE_Model.png" alt="Exemplo de RVE aleatório">
  <figcaption>Fig 1 — Exemplo de RVE com fibras UD distribuídas aleatoriamente.</figcaption>
</figure>

<h2>3.1.1 Model Name</h2>

<p>
  Define o nome principal do modelo gerado. Padrão:
  <code>RVE_UDFiber_Random</code>. O plug-in então acrescenta diâmetro,
  fração volumétrica, número de fibras e um sufixo numérico:
</p>

<pre><code>RVE_UDFiber_Random_Df7_Vf040_N143_Model_1
RVE_UDFiber_Random_Df7_Vf040_N143_Model_2
…</code></pre>

<p>Este esquema de nomes é o que as operações em lote das outras abas
usam para detectar "todos os modelos com o mesmo nome principal".</p>

<h2>3.1.2 Fibers Coordinates Generation Method</h2>

<p>Escolha um dos três geradores:</p>

<table class="field-table">
  <thead>
    <tr><th>Método</th><th>Limite Vf</th><th>Notas</th></tr>
  </thead>
  <tbody>
    <tr>
      <td><strong>Monte Carlo</strong></td>
      <td>≈ 45%</td>
      <td>Posiciona fibras aleatoriamente e rejeita sobreposições. Rápido,
      mas com Vf limitado por congestionamento.</td>
    </tr>
    <tr>
      <td><strong>Random Sequential Expansion (RSE)</strong></td>
      <td>≈ 68%</td>
      <td>Cresce iterativamente o conjunto de fibras. Atinge Vf maior, mas
      mais lento.</td>
    </tr>
    <tr>
      <td><strong>User coordinates file(s)</strong></td>
      <td>—</td>
      <td>Importa centros de fibras de um ou mais arquivos CSV. Duas colunas
      <em>(x, y)</em>, sem cabeçalho.</td>
    </tr>
  </tbody>
</table>

<div class="callout callout-warn">
  <div class="callout-title">O limite de Vf é estrito</div>
  <p>Estes limites de Vf são tratados como <strong>limites estritos</strong>.
  Valores acima do limite são rejeitados com erro, em vez de tentar uma
  geração instável.</p>
</div>

<h2>3.1.3 Geometric Parameters</h2>

<table class="field-table">
  <thead>
    <tr><th>Parâmetro</th><th>Padrão</th><th>Significado</th></tr>
  </thead>
  <tbody>
    <tr><td>RVE Width <code>a</code></td><td>50</td>
        <td>Largura da seção transversal (direção Y).</td></tr>
    <tr><td>RVE Height <code>b</code></td><td>50</td>
        <td>Altura da seção transversal (direção Z).</td></tr>
    <tr><td>RVE Depth <code>t</code></td><td>50</td>
        <td>Comprimento ao longo do eixo da fibra (direção X).</td></tr>
    <tr><td>Fiber Diameter <code>df</code></td><td>7</td>
        <td>Valor único — todas as fibras compartilham este diâmetro.</td></tr>
    <tr><td>Fiber Volume Fraction <code>Vf</code></td><td>40</td>
        <td>Em porcentagem. O plug-in calcula o número inteiro <code>N</code>
        de fibras a partir de <code>(Vf · a · b) / (π · df² / 4)</code>.</td></tr>
  </tbody>
</table>

<div class="callout callout-note">
  <div class="callout-title">Unidades</div>
  <p>As unidades devem ser autoconsistentes. O diâmetro da fibra costuma ser
  em μm, então as dimensões do RVE também devem ser em μm. As propriedades
  do material da aba Materials devem usar unidades compatíveis (por exemplo,
  MPa = N/μm²).</p>
</div>

<h2>3.1.4 Control Options</h2>

<p>Como <code>N</code> é arredondado, ou a fração volumétrica ou as dimensões
do RVE precisam ser ligeiramente ajustadas para que a geometria efetiva
corresponda exatamente a uma das entradas.</p>

<ul>
  <li><strong>keep vf</strong> — mantém Vf fixo e escala <code>a</code>,
      <code>b</code> proporcionalmente.</li>
  <li><strong>keep RVE size</strong> — mantém <code>a</code>, <code>b</code>
      fixos e reporta o Vf efetivo.</li>
</ul>

<h2>3.1.5 Base Parameter</h2>

<p>Este painel se atualiza dinamicamente conforme o gerador escolhido:</p>

<details class="collapsible" open>
  <summary>Monte Carlo — extras</summary>
  <p><strong>Safe distance between fibers</strong> — distância
  centro-a-centro mínima permitida ao aceitar uma nova fibra. Valores
  maiores → malha mais limpa, mas Vf máximo menor.</p>
</details>

<details class="collapsible">
  <summary>RSE — extras</summary>
  <p><strong>Lmin</strong> e <strong>Lmax</strong> — distâncias inter-fibras
  mínima e máxima permitidas durante a expansão. Obrigatórios.
  <code>Lmax ≥ Lmin &gt; 0</code>.</p>
</details>

<details class="collapsible">
  <summary>Coordenadas do usuário — extras</summary>
  <p>Selecione um ou mais arquivos CSV. O número de arquivos selecionados
  deve ser igual a "Number of generated models" abaixo. Cada arquivo deve
  conter apenas duas colunas <em>(x, y)</em>, com origem <code>(0, 0)</code>
  no canto inferior esquerdo da seção transversal do RVE.</p>
</details>

<h2>3.1.6 Number of generated models</h2>

<p>Usado para geração em lote, por exemplo, em estudos estatísticos com
Monte Carlo. Todos os modelos gerados compartilham os mesmos parâmetros
geométricos; apenas as posições aleatórias das fibras diferem.</p>

<h2>3.1.7 Save folder directory</h2>

<p>Onde gravar os arquivos CSV de coordenadas e o resumo de parâmetros.
Padrão <code>C:/UDFiber RVE Builder</code>. A pasta é criada automaticamente
se não existir.</p>

<p>Após clicar em OK, o plug-in gera arquivos como:</p>

<pre><code>C:/UDFiber RVE Builder/RVE_UDFibers_143fiber_Vf049_xy_20units/
   ├─ RVE2D_143Inclusions_IncCoordinates01.csv
   ├─ RVE2D_143Inclusions_IncCoordinates02.csv
   ├─ …
   └─ RVE2D_parameters_output_Vf_049_xy_20units_143fiber.txt</code></pre>

<p>O arquivo <code>.txt</code> registra Vf efetivo, dimensões, número de
fibras e tempo de execução. Reuse os CSVs depois pelo modo
<em>User coordinates file(s)</em>.</p>

<h2>3.1.8 Após clicar em OK — saídas e mudanças no banco de dados</h2>

<p>Ao clicar em OK, o plug-in executa três passos em ordem:</p>

<ol>
  <li>Gera (ou lê) as coordenadas dos centros das fibras e as escreve na
      pasta de salvamento configurada.</li>
  <li>Cria um modelo Abaqus por geometria solicitada, nomeado conforme
      <em>3.1.1 Model Name</em>. Cada modelo contém três Parts:
      <code>Fiber</code>, <code>Matrix</code>, e o
      <code>UDComposite</code> resultante da fusão.</li>
  <li>Popula o <code>UDComposite</code> com Sets nomeados (cells, edges e
      faces) que todas as abas posteriores (Mesh Control, Materials,
      Analysis) dependem.</li>
</ol>

<h3>Arquivos gravados em disco</h3>

<table>
  <thead><tr><th>Arquivo</th><th>Função</th></tr></thead>
  <tbody>
    <tr><td><code>RVE2D_&lt;N&gt;Inclusions_IncCoordinates&lt;ii&gt;.csv</code></td>
        <td>Coordenadas (x, y) dos centros das fibras, um arquivo por modelo.</td></tr>
    <tr><td><code>RVE2D_parameters_output_Vf_&lt;v&gt;_xy_&lt;n&gt;units_&lt;N&gt;fiber.txt</code></td>
        <td>Resumo: Vf alvo / efetivo, dimensões do RVE, número de fibras, tempo.</td></tr>
  </tbody>
</table>

<h3>Arquivos de estatística da distribuição (por configuração)</h3>

<p>Para ajudar a verificar se a distribuição aleatória de fibras se comporta
como esperado, o plug-in também escreve arquivos de estatísticas por
configuração, ao lado dos CSVs de coordenadas:</p>

<table>
  <thead><tr><th>Arquivo</th><th>Conteúdo</th></tr></thead>
  <tbody>
    <tr><td><code>first_nearest_neighbor_config_&lt;ii&gt;.csv</code></td>
        <td>Histograma da distância ao primeiro vizinho mais próximo.</td></tr>
    <tr><td><code>second_nearest_neighbor_config_&lt;ii&gt;.csv</code></td>
        <td>Histograma da distância ao segundo vizinho mais próximo.</td></tr>
    <tr><td><code>ripleys_K_function_config_&lt;ii&gt;.csv</code></td>
        <td>Função K de Ripley com raio normalizado.</td></tr>
    <tr><td><code>pair_distribution_function_config_&lt;ii&gt;.csv</code></td>
        <td>Função de distribuição de pares g(r) com raio normalizado.</td></tr>
    <tr><td><code>nn_summary.csv</code></td>
        <td>Resumo das estatísticas de vizinhança entre configurações.</td></tr>
  </tbody>
</table>

<h3>Sets criados em <code>UDComposite</code></h3>

<table class="field-table">
  <thead><tr><th>Nome do Set</th><th>Geometria</th><th>Função</th></tr></thead>
  <tbody>
    <tr><td><code>Set-Fiber</code></td><td>Cells</td>
        <td>Todas as cells de fibra — usado na atribuição do material da fibra.</td></tr>
    <tr><td><code>Set-Matrix</code></td><td>Cells</td>
        <td>Todas as cells de matriz — usado na atribuição do material da matriz e na inserção de vazios.</td></tr>
    <tr><td><code>Set-Arc</code></td><td>Edges</td>
        <td>Arcos das fibras que cruzam o contorno do RVE — usado nas sementes circunferenciais.</td></tr>
    <tr><td><code>Set-full-circle</code></td><td>Edges</td>
        <td>Contornos circulares completos das fibras (fibras internas) — sementes circunferenciais.</td></tr>
    <tr><td><code>Set-Fiber-Straightness</code> (e <code>-vertical</code>, <code>-horizontal</code>)</td><td>Edges</td>
        <td>Arestas retas das fibras nas faces do RVE — sementes da seção transversal.</td></tr>
    <tr><td><code>Set-Matrix-Straightness</code> (e <code>-vertical</code>, <code>-horizontal</code>)</td><td>Edges</td>
        <td>Arestas retas da matriz nas faces do RVE — sementes da seção transversal.</td></tr>
    <tr><td><code>Set-thickness-Straightness</code></td><td>Edges</td>
        <td>Arestas ao longo do eixo da fibra (X) — sementes da espessura.</td></tr>
  </tbody>
</table>

<div class="callout callout-warn">
  <div class="callout-title">Não renomeie os Sets gerados automaticamente</div>
  <p>As abas Mesh Control, Materials, Void Insertion e Analysis localizam
  estes Sets pelo nome. Renomear qualquer um deles fará as abas posteriores
  falharem. Se precisar de Sets adicionais, crie novos em vez de modificar
  estes.</p>
</div>
`;
