// Auto-loaded via <script> tag from index.html
// Edit the HTML inside the template literal below; do NOT change the wrapper.
window.helpContent = window.helpContent || {};
window.helpContent['pt/intro'] = `
<!-- ===== SECTION: intro (PT-BR) =========================================== -->
<h1>1 · Introdução</h1>

<p>
  <strong>RVE Builder (UDFRPs)</strong> é um plug-in para Abaqus/CAE que
  automatiza todo o fluxo de construção de Elementos de Volume Representativo
  (RVE) para polímeros reforçados com fibra contínua unidirecional, e o
  cálculo das suas propriedades efetivas sob condições de contorno periódicas
  (PBC). Geração da geometria, malha, atribuição de materiais, inserção de
  microvazios e análise de homogeneização ficam disponíveis numa única caixa
  de diálogo com abas — sem necessidade de scripts nem software de terceiros.
</p>

<p>
  O plug-in foi pensado tanto para estudos exploratórios pontuais como para
  grandes lotes estatísticos. Cada operação aceita um seletor de intervalo de
  modelos, de modo que um estudo paramétrico com dezenas de realizações
  estocásticas pode ser malhado, atribuído e analisado em um só clique.
  Cinco análises de homogeneização são suportadas de fábrica: elástica linear
  com CTE opcional, viscoelasticidade no domínio do tempo e da frequência,
  elasto-plástica com UMAT opcional e condutividade térmica em regime
  estacionário. Microvazios podem ser adicionados na matriz com distribuição
  espacial controlável (aleatória ou ponderada para vizinhança das fibras) e
  estratégia de tamanho (aleatória ou número fixo).
</p>

<div class="callout callout-note">
  <div class="callout-title">Autor</div>
  <p>Yuhao Meng · Programa de Engenharia Oceânica, COPPE, Universidade
  Federal do Rio de Janeiro, Brasil.</p>
  <p>Este plug-in é desenvolvido por um único autor, como esforço pessoal,
  e compartilhado aqui para intercâmbio e discussão acadêmica.
  Limitações são inevitáveis — comentários, correções e sugestões são
  muito bem-vindos.
  Contato: <a href="mailto:yuhaomeng@oceanica.ufrj.br">yuhaomeng@oceanica.ufrj.br</a>.</p>
</div>

<h2>Visão geral das capacidades</h2>
<ul>
  <li>Distribuições aleatórias de fibras via <strong>Monte Carlo</strong>,
      <strong>RSE</strong>, ou coordenadas CSV importadas.</li>
  <li>Semeadura de malha com seleção embutida de tipo e formato de elemento
      (mecânico, térmico, termo-mecânico acoplado).</li>
  <li>Atribuição de materiais em lote entre modelos, usando a cópia via ODB
      do Abaqus.</li>
  <li>Inserção de microvazios na matriz com tamanho, distribuição e
      prioridade controláveis.</li>
  <li>Cinco análises de homogeneização baseadas em PBC (Elástica + CTE,
      Viscoelástica Tempo, Viscoelástica Frequência, Elasto-plástica,
      Condutividade Térmica).</li>
</ul>

<h2>Estrutura do plug-in</h2>
<p>O plug-in expõe <strong>seis abas</strong>, uma por etapa do fluxo:</p>

<div class="inline-tabs">
  <div class="tab-buttons">
    <button class="tab-btn">Create RVE</button>
    <button class="tab-btn">Mesh Control</button>
    <button class="tab-btn">Materials</button>
    <button class="tab-btn">Void Insertion</button>
    <button class="tab-btn">Interface</button>
    <button class="tab-btn">Analysis</button>
  </div>
  <div class="tab-panel">
    <p>Define geometria, gerador de coordenadas das fibras, fração
    volumétrica e quantos modelos gerar em lote.</p>
  </div>
  <div class="tab-panel">
    <p>Aplica sementes de malha, escolhe formato (HEX/WEDGE) e tipo de
    malha (mecânica / térmica / acoplada).</p>
  </div>
  <div class="tab-panel">
    <p>Atribui materiais à fibra e à matriz. Usa a cópia de materiais via
    ODB para propagar a atribuição a vários modelos.</p>
  </div>
  <div class="tab-panel">
    <p>Insere vazios com distribuição (aleatória ou ponderada para a
    vizinhança das fibras), método de tamanho e prioridade. Funciona após
    a malha.</p>
  </div>
  <div class="tab-panel">
    <p>Insere costuras coesivas (COH3D8) de espessura zero na interface
    fibra-matriz, opcionalmente com uma fração inicial já descolada.
    Trabalha em uma cópia do modelo, preservando a malha original.</p>
  </div>
  <div class="tab-panel">
    <p>Aplica condições de contorno periódicas e roda qualquer das seis
    análises de homogeneização. Sub-rotina UMAT opcional; elastoplástico
    e condutividade térmica trocam automaticamente para variantes
    cientes-de-interface quando o modelo já contém costuras coesivas.</p>
  </div>
</div>

<div class="callout callout-tip">
  <div class="callout-title">Fluxo recomendado</div>
  <p>As abas foram pensadas para serem usadas em ordem &mdash; Create RVE
  &rarr; Mesh Control &rarr; Materials &rarr; (opcional) Void Insertion
  &rarr; (opcional) Interface &rarr; Analysis. Cada
  aba tem um controle <em>Select Model Range</em> que permite operar no
  modelo atual, em todos os modelos com o mesmo nome principal, ou num
  subconjunto específico.</p>
</div>

`;
