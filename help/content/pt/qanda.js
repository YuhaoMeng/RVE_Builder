// Auto-loaded via <script> tag from index.html
// Edit the HTML inside the template literal below; do NOT change the wrapper.
window.helpContent = window.helpContent || {};
window.helpContent['pt/qanda'] = `
<\!-- ===== SECTION: qanda (PT-BR) =========================================== -->
<h1>4 · Q&amp;A · Como funciona por dentro</h1>

<p>
  Esta seção apresenta os princípios de funcionamento de cada aba em
  formato de pergunta e resposta — útil para entender o que o plug-in está
  fazendo e diagnosticar comportamentos inesperados. As deduções
  matemáticas completas estão em <em>5 · Referências</em>.
</p>

<h2>Create RVE</h2>

<details class="collapsible" open>
  <summary>P. Como os círculos das fibras são realmente colocados na seção
  transversal?</summary>
  <p>Monte Carlo: a cada tentativa, sorteia-se um candidato a centro dentro
  do retângulo do RVE; aceita-se se todas as fibras já presentes estão a
  pelo menos a <em>safe distance</em> de distância — caso contrário,
  re-sorteia. RSE: parte de uma fibra semente e acrescenta fibras uma a
  uma — sorteia-se uma fibra existente e coloca-se a nova a uma distância
  superfície-a-superfície aleatória em <code>[Lmin, Lmax]</code> dela,
  aceita se não sobrepuser nenhuma outra fibra (ou se mantiver a folga
  opcional <code>MIN_GAP</code> de todas). O empacotamento segue até a
  célula travar e fibras são então removidas ao acaso até o Vf alvo. Ambos
  os métodos impõem periodicidade nas quatro faces do RVE — uma fibra que
  cruza uma face é duplicada na face oposta para que a seção possa ladrilhar.</p>
</details>

<details class="collapsible">
  <summary>P. Como (x, y) viram Parts e Sets no Abaqus?</summary>
  <p>Cada círculo de fibra e a fronteira do RVE são escritos no esboço
  Abaqus como equações de círculo e retas. O plug-in então intersecta
  <em>analiticamente</em> cada círculo com cada reta — essas interseções
  em forma fechada (e não picking numérico) determinam arestas, arcos e
  faces da seção. O esboço 2D é extrudado ao longo de X para formar a Part
  3D <code>UDComposite</code>. Por fim,
  <code>part.findAt(ponto)</code> com pontos de prova cuidadosamente
  escolhidos coleta edges e faces nos Sets listados em <em>3.1.8</em>.
  Os Sets de cells <code>Set-Fiber</code> e <code>Set-Matrix</code> são
  atribuídos geometricamente: um ponto interno de cada cell é testado
  contra os círculos das fibras (imagens periódicas incluídas), de modo
  que a atribuição não depende da ordem em que o Abaqus numera as cells
  após o merge booleano.</p>
</details>

<details class="collapsible">
  <summary>P. Por que o Vf efetivo às vezes difere do pedido?</summary>
  <p>O número inteiro de fibras <code>N</code> resulta do arredondamento de
  <code>(Vf · a · b) / (π · df² / 4)</code>. Ou o Vf ou as dimensões da
  seção precisam absorver esse arredondamento — o controle
  <em>Control Options</em> escolhe qual. Os valores efetivos ficam
  registrados no arquivo <code>parameters_output</code> TXT.</p>
</details>

<details class="collapsible">
  <summary>P. O que acontece quando uma fibra fica sobre um canto do RVE?</summary>
  <p>Uma fibra que cobre um canto é cortada em quatro lascas, uma em cada
  canto. Por isso os geradores Monte Carlo e RSE nunca produzem uma: um
  candidato cujo círculo cobre ou tangencia um canto, ou que cruza uma
  aresta do RVE (ou para antes dela) por menos de 10% do raio, é rejeitado
  (<code>BOUNDARY_CLEARANCE</code> nos arquivos geradores). Arquivos de
  coordenadas do usuário são usados como estão. Se uma de suas fibras
  cobrir um canto, <code>Set-Fiber</code> / <code>Set-Matrix</code> ainda
  são atribuídos por geometria, mas as lascas de canto são difíceis de
  malhar e as sementes de aresta podem sair desiguais. Desloque todo o
  padrão por um offset constante (com dobra periódica dos centros) para
  que nenhuma fibra cubra um canto e verifique os dois Sets de cells no
  Abaqus antes de malhar.</p>
</details>

<h2>Mesh Control</h2>

<details class="collapsible">
  <summary>P. A malha falha, ou alguns elementos são marcados como erro.
  Por quê?</summary>
  <p>A malha por varredura segue exatamente a partição da seção, portanto
  a malha é tão boa quanto a geometria. Duas fibras quase encostadas
  deixam um canal de matriz mais fino que um elemento, e uma fibra que
  cruza uma aresta por um fio produz uma calota minúscula; ambos fazem o
  malhador falhar ou deixam alguns elementos distorcidos. Remédios, em
  ordem: aumente a folga mínima entre fibras (<em>Safe distance</em> no
  Monte Carlo, a constante <code>MIN_GAP</code> em
  <code>Generate_UDFRPs_RSE.py</code> no RSE) para que o canal mais estreito tenha
  ao menos cerca de um elemento de largura; regenere as coordenadas, pois
  outro sorteio costuma malhar sem problemas; aumente o número de sementes
  na circunferência; ou mude <em>Element Shape</em> para WEDGE, que tolera
  melhor regiões estreitas. Alguns elementos distorcidos em canais
  estreitos têm volume desprezível e normalmente não alteram os módulos
  homogeneizados; para estudos de dano ou de interface, regenere.</p>
</details>

<details class="collapsible">
  <summary>P. Por que o plug-in restringe os tipos de elemento?</summary>
  <p>As PBC são aplicadas amarrando nós em faces opostas. Isso exige malha
  conformante nas faces pareadas, o que só é garantido com as famílias
  expostas em <em>Mesh Type</em> e <em>Element Shape</em>. Trocar
  manualmente por outros tipos (ex., tetraedros) pode quebrar o passo
  PBC.</p>
</details>

<details class="collapsible">
  <summary>P. De onde vem a fórmula de sementes em 3.2.3?</summary>
  <p>Cada círculo de diâmetro <code>df</code> é aproximado por um polígono
  de <code>NR</code> lados, cujo lado mede <code>π · df / NR</code>.
  Usando o mesmo tamanho característico nas demais arestas, chegamos a
  <code>NL = L · NR / (π · df)</code>. A calculadora interativa apenas
  embrulha essa fórmula numa UI.</p>
</details>

<h2>Materials</h2>

<details class="collapsible">
  <summary>P. Por que o modo lote escreve um ODB temporário?</summary>
  <p>O Abaqus não expõe uma API para copiar definições de material
  diretamente entre modelos. A solução é escrever os materiais do modelo
  fonte em um ODB (compatível com <code>materialsFromOdb</code>) e
  carregá-los em cada modelo alvo. O arquivo
  <code>UsetoCopyMaterial_&lt;modelo&gt;.odb</code> é exatamente isso, e o
  plug-in o apaga após as atribuições.</p>
</details>

<h2>Void Insertion</h2>

<details class="collapsible">
  <summary>P. Como o plug-in decide quais elementos da matriz viram
  vazios?</summary>
  <p>Logo após a malha, cada elemento da matriz recebe um rótulo:
  <em>fiber-adjacent</em> (compartilha nó ou face com uma cell de
  <code>Set-Fiber</code>) ou <em>inter-matrix</em> (os demais). O plug-in
  então percorre as listas rotuladas e seleciona elementos para deletar em
  proporções compatíveis com o peso <code>w</code> e a estratégia de
  tamanho (<code>theta</code> ou aleatório). A deleção para quando o
  volume removido acumulado atinge o Vf alvo.</p>
</details>

<details class="collapsible">
  <summary>P. Por que o <code>w</code> efetivo às vezes difere do
  alvo?</summary>
  <p>O conjunto de elementos fiber-adjacent é finito — em Vf alto ou
  <code>w</code> extremo, uma categoria pode esgotar antes da meta. O
  controle <em>Priority</em> decide o invariante: <code>w</code> estrito,
  tamanhos estritos, ou best-effort. O
  <code>void_summary_report.txt</code> sempre reporta os valores
  efetivos.</p>
</details>

<h2>Analysis</h2>

<details class="collapsible">
  <summary>P. Qual é o papel das "condições de contorno periódicas"?</summary>
  <p>O RVE é um pedaço finito de um compósito conceitualmente infinito.
  Para recuperar a resposta efetiva do material, os deslocamentos em faces
  opostas do RVE são restringidos a diferirem por uma deformação
  macroscópica constante — essas são as PBC. O EasyPBC implementa essas
  restrições como equações lineares entre nós pareados, daí a importância
  da tolerância de mapeamento e da escolha do tipo de elemento.</p>
</details>

<details class="collapsible">
  <summary>P. Como E11–G23 são calculados?</summary>
  <p>Para cada módulo pedido, o plug-in aplica uma deformação macroscópica
  unitária correspondente (ex.: ε11 = 1, demais = 0) e deixa o Abaqus
  resolver o RVE sob PBC. A tensão média em volume é lida do ODB e o
  módulo é a razão tensão / deformação. Seis casos independentes dão a
  rigidez ortotrópica completa (E11/E22/E33 + G12/G13/G23).</p>
</details>

<details class="collapsible">
  <summary>P. O que muda nas análises viscoelásticas?</summary>
  <p>A maquinaria PBC é a mesma, mas a lei constitutiva agora depende do
  tempo ou da frequência. <strong>Domínio do tempo</strong>: passo de
  relaxação sob deformação sustentada, amostrando E(t) ou G(t) nos pontos
  pedidos. <strong>Domínio da frequência</strong>: passo dinâmico
  estacionário do Abaqus varre a frequência e reporta módulos complexos
  E*(ω) ou G*(ω).</p>
</details>

<details class="collapsible">
  <summary>P. O que a análise elasto-plástica realmente resolve?</summary>
  <p>Aplica deformações macroscópicas prescritas (uniaxial ou biaxial,
  ao longo dos eixos do RVE) sob PBC e deixa o Abaqus integrar a lei constitutiva
  não linear de fibra + matriz passo a passo. Se um UMAT for fornecido,
  ele assume o comportamento constitutivo da matriz; caso contrário, o
  plug-in usa o que está definido na aba Materials. O histórico de
  tensão–deformação é exportado para CSV.</p>
</details>

<details class="collapsible">
  <summary>P. E a análise de condutividade térmica?</summary>
  <p>Condições de contorno periódicas em temperatura substituem as
  mecânicas: aplica-se um gradiente unitário em cada direção pedida,
  enquanto a face oposta fica na temperatura de referência. O solver
  estacionário de transferência de calor do Abaqus fornece o fluxo médio
  em volume, do qual K11–K33 são recuperados.</p>
</details>

<div class="callout callout-tip">
  <div class="callout-title">Quer mais profundidade?</div>
  <p>Para as deduções matemáticas por trás das PBC, da geração RSE /
  Monte-Carlo de fibras e do arcabouço micromecânico Bridging / Kerner
  do artigo de origem, veja <em>5 · Referências</em>.</p>
</div>
`;
