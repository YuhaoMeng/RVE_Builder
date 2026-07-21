// Auto-loaded via <script> tag from index.html
// Edit the HTML inside the template literal below; do NOT change the wrapper.
window.helpContent = window.helpContent || {};
window.helpContent['pt/tab4_void'] = `
<!-- ===== SECTION: tab4_void (PT-BR) ======================================= -->
<h1>3.4 · Void Insertion</h1>

<p>
  A aba <strong>Void Insertion</strong> insere microvazios na matriz de um
  RVE já malhado. Esta página foca no que clicar e no que observar; o
  conteúdo teórico foi mantido breve de propósito.
</p>

<div class="callout callout-warn">
  <div class="callout-title">Malhe primeiro</div>
  <p>Esta aba precisa de uma malha existente. Execute <strong>Mesh
  Control</strong> antes de abrir Void Insertion.</p>
</div>

<h2>3.4.1 Select Model and Part</h2>

<ul>
  <li><strong>Model</strong> — drop-down de todos os modelos abertos.</li>
  <li><strong>Part</strong> — tipicamente <code>UDComposite</code>. O
      drop-down se preenche conforme o modelo escolhido.</li>
</ul>

<h2>3.4.2 Void Volume Fraction</h2>

<p>Um único número, em <strong>porcentagem</strong>. Padrão <code>5.0</code>.
É a fração volumétrica total dos vazios em relação ao volume do RVE
inteiro. O plug-in distribuirá exatamente essa fração entre os vazios
inseridos — não há um teto implícito além da viabilidade física (ou seja,
não é possível pedir um Vf de vazios maior que o volume real de matriz que
sobrou após o posicionamento das fibras).</p>

<h2>3.4.3 Void Distribution</h2>

<p>Escolha como os vazios são distribuídos entre as duas regiões definidas
internamente no plug-in:</p>

<ul>
  <li><strong>Random Number Method</strong> — distribuição automática; o
      plug-in amostra um peso aleatório a cada tentativa de inserção.</li>
  <li><strong>Custom (w, 0–1)</strong> — peso <code>w</code> em
      <code>[0, 1]</code> que controla a divisão volumétrica entre os dois
      tipos de vazio descritos abaixo.</li>
</ul>

<h3>Como os dois tipos de vazio são definidos no plug-in</h3>

<p>Internamente, cada elemento candidato da matriz é classificado em
exatamente uma das categorias antes da inserção:</p>

<table class="field-table">
  <thead><tr><th>Tipo</th><th>Definição (regra do plug-in)</th></tr></thead>
  <tbody>
    <tr>
      <td><strong>Adjacente à fibra (Fiber-adjacent)</strong></td>
      <td>Elementos da matriz que compartilham pelo menos um nó (ou face)
          com uma cell de <code>Set-Fiber</code>. Estes formam a casca fina
          de matriz que envolve cada fibra.</td>
    </tr>
    <tr>
      <td><strong>Inter-matriz (Inter-matrix)</strong></td>
      <td>Demais elementos da matriz — não em contato com nenhuma fibra.
          Geralmente nos canais entre fibras.</td>
    </tr>
  </tbody>
</table>

<p>O peso <code>w</code> controla a razão volumétrica:</p>
<ul>
  <li><code>w = 0</code> → <em>todo</em> o volume vem dos elementos
      <strong>inter-matriz</strong>.</li>
  <li><code>w = 1</code> → <em>todo</em> o volume vem dos elementos
      <strong>adjacentes à fibra</strong>.</li>
  <li><code>w ∈ (0, 1)</code> → mistura: fração <code>w</code> do volume
      vem dos adjacentes; <code>1 − w</code> dos inter-matriz.</li>
</ul>

<div class="callout callout-note">
  <p>A classificação ocorre uma vez no início, sobre a Part
  <code>UDComposite</code> malhada. Vazios são então criados removendo
  elementos inteiros da categoria apropriada até atingir o Vf alvo.</p>
</div>

<h2>3.4.4 Void Size</h2>

<ul>
  <li><strong>Random Void Size</strong> — tamanhos aleatorizados.</li>
  <li><strong>Custom Size (theta)</strong> — inteiro <code>theta</code> ≥ 1.
      <code>theta</code> é o número de vazios; o Vf por vazio é
      <code>Vf total / theta</code>.</li>
</ul>

<div class="callout callout-warn">
  <div class="callout-title">Quando theta = 1</div>
  <p>Com <code>theta = 1</code>, o peso <code>w</code> deve ser
  <code>0</code>, <code>1</code> ou <strong>Random</strong> — não pode ser
  fração. Um único vazio não pode ser dividido entre duas regiões.</p>
</div>

<h2>3.4.5 Priority</h2>

<p>Define o que preservar quando há conflito (ex: <code>w</code> não pode
ser exato com o espaço disponível):</p>

<table class="field-table">
  <thead><tr><th>Opção</th><th>Permanece exato</th></tr></thead>
  <tbody>
    <tr><td><strong>Distribution Priority (strict w)</strong></td>
        <td><code>w</code> é forçado; tamanhos podem variar.</td></tr>
    <tr><td><strong>Size Priority (allow w deviation)</strong></td>
        <td>Tamanhos próximos do alvo; <code>w</code> pode variar.</td></tr>
    <tr><td><strong>No Intervention</strong></td>
        <td>O plug-in faz "best-effort".</td></tr>
  </tbody>
</table>

<div class="callout callout-note">
  <div class="callout-title">O Vf total é sempre respeitado</div>
  <p>Independente da prioridade, a fração volumétrica total de vazios
  pedida é sempre preservada. Apenas o <em>formato da distribuição</em> e
  o <em>tamanho por vazio</em> são negociáveis.</p>
</div>

<h2>3.4.6 Fator de Forma do Vazio (β)</h2>

<p>Por padrão, os vazios crescem com uma regra puramente baseada em distância
e tendem a clusters aproximadamente esféricos. O fator opcional
<strong>β</strong> enviesa a ponderação de candidatos em direção a um
envelope elipsoidal, permitindo que os vazios cresçam alongados ou
achatados.</p>

<table class="field-table">
  <thead><tr><th>Campo</th><th>Efeito</th></tr></thead>
  <tbody>
    <tr><td><strong>Habilitar fator de forma</strong></td>
        <td>Desligado → regra antiga apenas por distância (vazios esféricos).
            Ligado → usa o envelope descrito abaixo.</td></tr>
    <tr><td><strong>Valor de β (>0)</strong></td>
        <td>Um único número positivo. <code>β = 1</code> → esfera;
            <code>β > 1</code> → prolato, eixos <code>(β, 1, 1)</code>,
            alongado ao longo do eixo X da fibra; <code>β < 1</code> → oblato,
            eixos <code>(1, 1, β)</code>, achatado ao longo de Z. Não é
            necessário um seletor de "tipo de forma" — β sozinho define
            a forma.</td></tr>
    <tr><td><strong>Unificado vs. Separado</strong></td>
        <td>Unificado: mesmo β para vazios adjacentes à fibra e inter-matriz.
            Separado: dois β, um para cada pool.</td></tr>
    <tr><td><strong>Orientação</strong></td>
        <td><em>SO(3) aleatório</em>: cada envelope recebe uma rotação
            uniformemente aleatória; <em>Ortogonal</em>: mantém o envelope
            alinhado aos eixos (prolato em X, oblato comprimido em Z).</td></tr>
    <tr><td><strong>θ* (média de vazios por fibra)</strong></td>
        <td>Entrada opcional informativa. Quando ativa, o relatório registra
            θ* e implica <code>θ = θ* × Nf</code>. As regras existentes
            (θ, Vf) continuam tendo prioridade.</td></tr>
  </tbody>
</table>

<div class="callout callout-note">
  <p>β apenas modifica a <em>ponderação dos candidatos</em> durante o
  crescimento. Todas as outras regras (Vf alvo, w, θ, proteção contra
  isolamento de fibra, prevenção de ilhas) continuam sendo aplicadas
  rigorosamente, então β é uma preferência suave, não uma restrição
  rígida.</p>
</div>

<h2>3.4.7 Select Model Range for Void Insertion</h2>

<p>Mesmo controle em lote das outras abas (Current / All / Selected
numbers). "All Models" abrange todos os modelos com mesmo nome principal.</p>

<h2>3.4.8 Após clicar em OK — saídas e mudanças no banco de dados</h2>

<p>Para cada modelo, o plug-in:</p>
<ol>
  <li>Classifica cada elemento da matriz como <em>fiber-adjacent</em> ou
      <em>inter-matrix</em> (ver 3.4.3).</li>
  <li>Remove elementos da categoria apropriada para formar os vazios, até
      atingir o Vf de vazios alvo.</li>
  <li>Marca a região removida como Set <code>Set-Void</code> para inspeção
      no módulo Mesh do Abaqus.</li>
  <li>Atualiza as Section assignments para que a região vazia não tenha
      material.</li>
  <li>Grava uma pasta de estatísticas dedicada em disco para que você possa
      verificar se a distribuição obtida bate com os parâmetros pedidos.</li>
</ol>

<h3>Pasta de estatísticas gravada em disco</h3>

<p>O plug-in cria uma pasta por execução, chamada
<code>Void_Statistics_&lt;modelo&gt;_&lt;YYYYMMDD_HHMMSS&gt;</code>, no
diretório de trabalho do Abaqus. Conteúdo:</p>

<table>
  <thead><tr><th>Arquivo</th><th>Conteúdo</th></tr></thead>
  <tbody>
    <tr><td><code>void_summary_report.txt</code></td>
        <td>Relatório de alto nível — entradas do usuário, dimensões do
        RVE, Vf alvo vs. <strong>efetivo</strong>, divisão near-fiber /
        inter-matrix, valor efetivo de <code>w</code>, desvio em relação
        ao alvo. <em>Abra este primeiro.</em></td></tr>
    <tr><td><code>void_sizes.csv</code></td>
        <td>Por vazio: ID, tipo (near-fiber / inter-matrix), volume,
        número de elementos, centroide (x, y, z), mais o envelope PCA:
        três semi-eixos ordenados <code>(h1, h2, h3)</code>, os três
        vetores de cossenos diretores <code>(e1, e2, e3)</code> e a
        similaridade do cosseno entre o eixo principal <code>e1</code> e o
        eixo X global da fibra.</td></tr>
    <tr><td><code>void_fiber_surface_breakdown.csv</code></td>
        <td>Destruição de superfície por fibra: ID da fibra, perímetro
        (proxy), nós de interface totais, nós quebrados e razão
        <code>r_i = quebrados / total</code>.</td></tr>
    <tr><td><code>void_nn_distances.csv</code></td>
        <td>Distâncias ao 1º e 2º vizinhos mais próximos entre vazios.</td></tr>
    <tr><td><code>void_ripleys_k.csv</code></td>
        <td>Função K de Ripley (quando aplicável).</td></tr>
    <tr><td><code>void_pair_distribution.csv</code></td>
        <td>Função de distribuição de pares g(r) dos centros dos vazios.</td></tr>
    <tr><td><code>void_fiber_distances.csv</code></td>
        <td>Distância de cada vazio às fibras mais próximas (NN1, NN2).</td></tr>
  </tbody>
</table>

<h3>Métricas de destruição da superfície da fibra</h3>

<p>Quando os centros das fibras estão disponíveis,
<code>void_summary_report.txt</code> termina com cinco indicadores de
concentração que descrevem o quanto os vazios romperam a interface
fibra–matriz. Seja <code>r_i</code> a razão de nós quebrados na fibra
<code>i</code> e <code>N_f</code> o número total de fibras:</p>

<table class="field-table">
  <thead><tr><th>Indicador</th><th>Definição / interpretação</th></tr></thead>
  <tbody>
    <tr><td><code>f_fiber</code></td>
        <td>Fração de fibras com <em>qualquer</em> destruição
            (fibras com <code>r_i > 0</code> dividido por <code>N_f</code>).</td></tr>
    <tr><td><code>f_area</code></td>
        <td>Razão global de área quebrada = soma dos nós quebrados /
            soma dos nós de interface, em todas as fibras.</td></tr>
    <tr><td><code>r_avg_broken</code></td>
        <td>Média de <code>r_i</code> apenas sobre fibras afetadas.</td></tr>
    <tr><td><code>C_focus</code></td>
        <td><code>= r_avg_broken / f_area</code>. Valores maiores indicam
            destruição concentrada em poucas fibras.</td></tr>
    <tr><td><code>Gini(r_i)</code></td>
        <td>Coeficiente de Gini padrão dos <code>r_i</code>. Próximo de 0
            → uniforme; próximo de 1 → concentrado.</td></tr>
  </tbody>
</table>

<div class="callout callout-warn">
  <div class="callout-title">A inserção de vazios nem sempre é perfeita — verifique antes de analisar</div>
  <p>A colocação de vazios é um processo estocástico em uma matriz finita já
  malhada. Dependendo do Vf, <code>w</code>, <code>theta</code> pedidos e da
  geometria local, a distribuição efetiva pode desviar levemente dos alvos —
  ou, em casos extremos, a inserção pode falhar completamente.
  <strong>Sempre abra <code>void_summary_report.txt</code> depois da execução</strong>
  e confirme se o Vf efetivo, o <code>w</code> efetivo e os desvios são
  aceitáveis para o seu estudo antes de submeter o modelo à análise.</p>
</div>

<div class="callout callout-tip">
  <div class="callout-title">Dicas</div>
  <ul>
    <li>Insira vazios <em>após</em> atribuir materiais.</li>
    <li>Se um Vf alvo não puder ser atingido (matriz pequena demais), o
    plug-in para com aviso, sem corromper o modelo — ajuste e tente de
    novo.</li>
    <li>Reexecutar esta aba no mesmo modelo insere vazios sobre os
    existentes — copie o modelo antes se quiser variantes.</li>
  </ul>
</div>
`;
