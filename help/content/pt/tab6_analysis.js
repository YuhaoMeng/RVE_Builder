// Auto-loaded via <script> tag from index.html
// Edit the HTML inside the template literal below; do NOT change the wrapper.
window.helpContent = window.helpContent || {};
window.helpContent['pt/tab6_analysis'] = `
<!-- ===== SECTION: tab6_analysis (PT-BR) =================================== -->
<h1>3.6 · Analysis</h1>

<p>
  A aba <strong>Analysis</strong> aplica condições de contorno periódicas e
  roda uma das <strong>seis</strong> análises de homogeneização nos modelos
  selecionados. A implementação das PBC é baseada no plug-in open-source
  EasyPBC [3], estendida com fluxos viscoelásticos, elasto-plásticos e de
  condutividade térmica.
</p>

<div class="callout callout-warn">
  <div class="callout-title">Mensagens de erro e aviso do EasyPBC são preservadas</div>
  <p>Esta aba mantém intactos os textos originais de erro e aviso do
  EasyPBC. Se uma execução falhar ou imprimir um aviso mencionando PBC,
  tolerância de mapeamento de malha, nós dependentes / independentes ou
  similares, consulte o
  <a href="https://doi.org/10.1007/s00366-018-0616-4" target="_blank" rel="noopener">artigo do EasyPBC (Omairey et al., 2019)</a>
  para diagnóstico. Questões fora deste escopo (parâmetros específicos do
  tipo de análise, carregamento de UMAT etc.) estão documentadas abaixo.</p>
</div>

<div class="callout callout-warn" style="border-left-color:#cc0000;">
  <div class="callout-title" style="color:#cc0000;">Aviso de unidades · Entrada em °C, interno em K</div>
  <p style="color:#cc0000;">
    <strong>Para todas as análises com temperatura, as entradas do plug-in usam
    Celsius (°C).</strong> As definições de material no Abaqus permanecem em
    Kelvin (K); o plug-in converte automaticamente as entradas °C para K e
    todas as temperaturas reportadas nos arquivos de saída estão em °C.
    As duas linhas em negrito vermelho no topo da aba Analysis na GUI
    repetem o mesmo contrato.
  </p>
</div>

<h2>3.6.1 Basic Information</h2>

<table class="field-table">
  <thead><tr><th>Campo</th><th>Padrão</th><th>Significado</th></tr></thead>
  <tbody>
    <tr><td>Model</td><td>(atual)</td><td>Modelo a ser analisado.</td></tr>
    <tr><td>Part</td><td>UDComposite</td><td>Auto-preenchido conforme o modelo escolhido.</td></tr>
    <tr><td>Mapping accuracy *</td><td>1E-04</td>
        <td>Tolerância para casar nós de faces opostas do RVE. Deve ser
        menor que a menor aresta da malha.</td></tr>
    <tr><td>Number of CPUs **</td><td>1</td>
        <td>CPUs para o job Abaqus. Se exceder o disponível, todos os
        disponíveis são usados.</td></tr>
    <tr><td>UMAT Subroutine</td><td>(vazio)</td>
        <td>Opcional e disponível para <strong>todos os tipos de análise</strong>.
        Selecione um arquivo Fortran <code>.for</code> se quiser que o Abaqus
        chame sua sub-rotina personalizada durante a execução; deixar vazio
        roda com os materiais definidos na aba Materials e o solver embutido
        do Abaqus. O backend de Thermal Conductivity atualmente não consome
        UMAT, portanto qualquer caminho indicado lá é silenciosamente
        ignorado; os demais tipos de análise honram o UMAT.</td></tr>
  </tbody>
</table>

<h2>3.6.2 Analysis Type</h2>

<p>Escolha exatamente uma. O painel de parâmetros muda conforme a escolha.</p>

<table class="narrow-index-table">
  <thead><tr><th>#</th><th>Tipo</th><th>Módulo de back-end</th></tr></thead>
  <tbody>
    <tr><td>1</td><td>Elastic + CTE</td>
        <td><code>PBC_UDFRP_Elastic_CTE</code></td></tr>
    <tr><td>5</td><td>Thermal Conductivity</td>
        <td><code>PBC_UDFRP_thermal_conductivity</code>
        (troca automática para <code>_Interfaceh</code> com modelos de
        interface)</td></tr>
    <tr><td>4</td><td>Elastoplastic (Uniaxial)</td>
        <td><code>PBC_UDFRP_Elastoplastic</code>
        (troca automática para <code>_interface</code> com modelos de
        interface)</td></tr>
    <tr><td>6</td><td>Elastoplastic (Biaxial)</td>
        <td><code>PBC_UDFRP_Elastoplastic</code>
        (troca automática para <code>_interface</code> com modelos de
        interface)</td></tr>
    <tr><td>2</td><td>Viscoelastic (Time domain)</td>
        <td><code>PBC_UDFRP_Viscoelastic_Time</code></td></tr>
    <tr><td>3</td><td>Viscoelastic (Frequency domain)</td>
        <td><code>PBC_UDFRP_Viscoelastic_Frequency</code></td></tr>
  </tbody>
</table>

<h2>3.6.3 Analysis Parameters (por tipo)</h2>

<div class="inline-tabs">
  <div class="tab-buttons">
    <button class="tab-btn">Elastic + CTE</button>
    <button class="tab-btn">Visc. Time</button>
    <button class="tab-btn">Visc. Freq.</button>
    <button class="tab-btn">EP Uniaxial</button>
    <button class="tab-btn">EP Biaxial</button>
    <button class="tab-btn">Thermal</button>
  </div>

  <div class="tab-panel">
    <p>Selecione os módulos a calcular (qualquer combinação):</p>
    <ul>
      <li><strong>E11(X), E22(Y), E33(Z)</strong> — módulos de Young.</li>
      <li><strong>G12(XY), G13(XZ), G23(YZ)</strong> — módulos de cisalhamento.</li>
      <li><strong>Only Corresponding PBC</strong> — só aplica as PBC dos
          módulos selecionados, sem resolver (útil para inspeção).</li>
      <li><strong>Coefficient of Thermal Expansion (CTE)</strong> — adiciona
          step térmico. Habilita as entradas de temperatura abaixo.</li>
    </ul>
    <p>Se <strong>CTE</strong> estiver marcado:</p>
    <ul>
      <li><strong>Initial / Final Temperature (°C)</strong>,
          <strong>Segment</strong> — rampa de temperatura. Valores em °C
          são convertidos para Kelvin internamente.</li>
    </ul>
    <p><strong>Temperature Points (°C)</strong> — lista opcional de Celsius
    separada por vírgulas (por ex. <code>-40, 25, 80, 120</code>). Quando
    fornecida, o despachador roda o analisador elástico <em>uma vez por
    temperatura</em> e grava CSVs por ponto + um agregado
    <code>&lt;modelo&gt;_elastic_temperature_sweep_&lt;timestamp&gt;.csv</code>.
    Cada valor é validado contra o zero absoluto (−273.15 °C) antes de
    submeter qualquer job Abaqus.</p>
  </div>

  <div class="tab-panel">
    <ul>
      <li><strong>E11/E22/E33/G12/G13/G23</strong> — componentes a relaxar.</li>
      <li><strong>Temperature (°C)</strong> — temperatura fixa
          (−273 a 5000).</li>
      <li><strong>Relaxation Total Time (s)</strong> — duração da relaxação.</li>
      <li><strong>Number of Time Points</strong> — pontos de amostragem.</li>
    </ul>
    <p>Saída: módulo de relaxação E(t) (ou G(t)) nos tempos amostrados.</p>
  </div>

  <div class="tab-panel">
    <ul>
      <li><strong>E11*/E22*/E33*/G12*/G13*/G23*</strong> — módulos complexos.</li>
      <li><strong>Temperature (°C)</strong> — temperatura fixa.</li>
      <li><strong>Lower / Upper Frequency (Hz)</strong> — limites do sweep.</li>
      <li><strong>Number of Points</strong> — pontos totais.</li>
      <li><strong>Bias</strong> — &gt; 3 concentra amostras no limite
          inferior; ≤ 3 amostragem uniforme.</li>
    </ul>
  </div>

  <div class="tab-panel">
    <p>Aplica deformações macroscópicas prescritas sob PBC.
    <strong>Layout Uniaxial</strong> (Analysis Type = 4) permite marcar
    qualquer combinação entre seis componentes independentes e roda
    um caso por componente marcado num único clique.</p>

    <h4>Entradas uniaxiais</h4>
    <p>Seis check-boxes independentes &mdash; <strong>Strain11, Strain22,
    Strain33, Shear12, Shear13, Shear23</strong> &mdash; cada um com seu
    campo de texto. Marque os componentes desejados e preencha os valores;
    o dispatcher roda um caso por componente marcado, pulando os não
    marcados.</p>
    <ul>
      <li><strong>Strain11 / Strain22 / Strain33</strong> aceitam um único
          valor ou um <em>par separado por vírgula</em>. Ex.
          <code>0.012,-0.016</code> roda a linha duas vezes &mdash; uma em
          tração (+0.012) e outra em compressão (-0.016).</li>
      <li><strong>Shear12 / Shear13 / Shear23</strong> aceitam exatamente
          um valor (engineering shear strain).</li>
    </ul>

    <h4>Entradas compartilhadas (ambos os layouts)</h4>
    <ul>
      <li><strong>Temperature Points (&deg;C)</strong> &mdash; lista
          opcional de temperaturas separadas por vírgula. Cada caso
          uniaxial / biaxial é repetido em cada temperatura listada; todos os
          pontos de um caso ficam na mesma sub-pasta e os nomes de job / CSV
          levam a etiqueta de temperatura (ex.: <code>Temp_025</code>).</li>
      <li><strong>Nlgeom</strong> (large deformation) &mdash; checkbox.
          Padrão <em>ligado</em>. Desligue apenas quando tiver certeza de
          que análise de pequenas deformações é suficiente.</li>
      <li><strong>Unsymmetric matrix storage (UMAT)</strong> &mdash;
          checkbox. Desligado por padrão. Ligue quando a UMAT ativa tem
          tangente assimétrica (fluxo não-associado, Chaboche cinemático,
          etc.). O solver assimétrico aproximadamente dobra memória e
          tempo, então mantenha desligado quando não for necessário.</li>
    </ul>

    <div class="callout callout-tip">
      <p>Valores negativos representam compressão. Cisalhamento usa a
      convenção engineering shear strain.</p>
    </div>

    <div class="callout callout-note">
      <div class="callout-title">UMAT é opcional</div>
      <p>UMAT <strong>não é obrigatório</strong>. Se você tem uma sub-rotina
      Fortran <code>.for</code> customizada, selecione-a no painel Basic
      Information. Deixar em branco roda a análise com os materiais
      definidos na aba Materials e com o solver elastoplástico nativo do
      Abaqus.</p>
    </div>

    <div class="callout callout-warn">
      <div class="callout-title">Solution Controls aplicados automaticamente</div>
      <p>Toda execução elastoplástica define <em>General Solution Controls</em>
      com <strong>Specify ON</strong>, <strong>Discontinuous analysis</strong>
      (I0=8, IR=10) e <strong>IC=30</strong> (padrão 16). Uma linha de log
      <code>[StaticStep] Solution controls: ...</code> confirma os valores
      em cada job.</p>
    </div>

    <div class="callout callout-warn">
      <div class="callout-title">Limpeza defensiva entre casos</div>
      <p>Antes de cada novo caso o analisador apaga steps, loads, BCs,
      constraints, campos de temperatura predefinidos, analysis sets e
      reference points residuais. Os nomes de Job são <em>estáveis</em>
      &mdash; padrão
      <code>Job_&lt;model&gt;_&lt;load&gt;_&lt;Temp&gt;.odb</code> (sem
      timestamp) &mdash; então o ODB abre direto pela visão Jobs do Abaqus.
      Se um Job de mesmo nome já existir, o analisador apaga antes; se a
      sub-pasta de carga já existir, o dispatcher adiciona sufixo
      <code>(1)</code>, <code>(2)</code>, ... para nunca sobrescrever
      execuções anteriores.</p>
    </div>

    <div class="callout callout-note">
      <div class="callout-title">Roteamento ciente da interface</div>
      <p>Se o modelo escolhido for um modelo <code>*_Interface</code>
      produzido pela aba Interface (ou qualquer modelo já contendo
      costuras COH3D8), o dispatcher troca o kernel para
      <code>PBC_UDFRP_Elastoplastic_interface</code> automaticamente. A
      GUI se comporta identicamente; você confirma o roteamento pelo log.</p>
    </div>
  </div>

  <div class="tab-panel">
    <p>Aplica deformações macroscópicas prescritas sob PBC.
    <strong>Layout Biaxial</strong> (Analysis Type = 6) escolhe um par de
    componentes do catálogo fixo e roda um único caso combinado.</p>

    <h4>Entradas biaxiais</h4>
    <p>Um drop-down lista os 15 pares suportados: Strain11-Strain22,
    Strain11-Strain33, Strain11-Shear12, Strain11-Shear13, Strain11-Shear23,
    Strain22-Strain33, Strain22-Shear12, Strain22-Shear13, Strain22-Shear23,
    Strain33-Shear12, Strain33-Shear13, Strain33-Shear23, Shear12-Shear13,
    Shear12-Shear23, Shear13-Shear23. Escolha um par e defina
    <strong>Load 1 Max Strain</strong> e <strong>Load 2 Max Strain</strong>;
    componentes Strain seguem convenção tensorial (negativo = compressão)
    e Shear seguem engineering shear strain.</p>

    <h4>Entradas compartilhadas (ambos os layouts)</h4>
    <ul>
      <li><strong>Temperature Points (&deg;C)</strong> &mdash; lista
          opcional de temperaturas separadas por vírgula. Cada caso
          uniaxial / biaxial é repetido em cada temperatura listada; todos os
          pontos de um caso ficam na mesma sub-pasta e os nomes de job / CSV
          levam a etiqueta de temperatura (ex.: <code>Temp_025</code>).</li>
      <li><strong>Nlgeom</strong> (large deformation) &mdash; checkbox.
          Padrão <em>ligado</em>. Desligue apenas quando tiver certeza de
          que análise de pequenas deformações é suficiente.</li>
      <li><strong>Unsymmetric matrix storage (UMAT)</strong> &mdash;
          checkbox. Desligado por padrão. Ligue quando a UMAT ativa tem
          tangente assimétrica (fluxo não-associado, Chaboche cinemático,
          etc.). O solver assimétrico aproximadamente dobra memória e
          tempo, então mantenha desligado quando não for necessário.</li>
    </ul>

    <div class="callout callout-tip">
      <p>Valores negativos representam compressão. Cisalhamento usa a
      convenção engineering shear strain.</p>
    </div>

    <div class="callout callout-note">
      <div class="callout-title">UMAT é opcional</div>
      <p>UMAT <strong>não é obrigatório</strong>. Se você tem uma sub-rotina
      Fortran <code>.for</code> customizada, selecione-a no painel Basic
      Information. Deixar em branco roda a análise com os materiais
      definidos na aba Materials e com o solver elastoplástico nativo do
      Abaqus.</p>
    </div>

    <div class="callout callout-warn">
      <div class="callout-title">Solution Controls aplicados automaticamente</div>
      <p>Toda execução elastoplástica define <em>General Solution Controls</em>
      com <strong>Specify ON</strong>, <strong>Discontinuous analysis</strong>
      (I0=8, IR=10) e <strong>IC=30</strong> (padrão 16). Uma linha de log
      <code>[StaticStep] Solution controls: ...</code> confirma os valores
      em cada job.</p>
    </div>

    <div class="callout callout-warn">
      <div class="callout-title">Limpeza defensiva entre casos</div>
      <p>Antes de cada novo caso o analisador apaga steps, loads, BCs,
      constraints, campos de temperatura predefinidos, analysis sets e
      reference points residuais. Os nomes de Job são <em>estáveis</em>
      &mdash; padrão
      <code>Job_&lt;model&gt;_&lt;load&gt;_&lt;Temp&gt;.odb</code> (sem
      timestamp) &mdash; então o ODB abre direto pela visão Jobs do Abaqus.
      Se um Job de mesmo nome já existir, o analisador apaga antes; se a
      sub-pasta de carga já existir, o dispatcher adiciona sufixo
      <code>(1)</code>, <code>(2)</code>, ... para nunca sobrescrever
      execuções anteriores.</p>
    </div>

    <div class="callout callout-note">
      <div class="callout-title">Roteamento ciente da interface</div>
      <p>Se o modelo escolhido for um modelo <code>*_Interface</code>
      produzido pela aba Interface (ou qualquer modelo já contendo
      costuras COH3D8), o dispatcher troca o kernel para
      <code>PBC_UDFRP_Elastoplastic_interface</code> automaticamente. A
      GUI se comporta identicamente; você confirma o roteamento pelo log.</p>
    </div>
  </div>

  <div class="tab-panel">
    <p>Componentes de condutividade a calcular:</p>
    <ul>
      <li><strong>K11, K12, K13 (X)</strong> / <strong>K21, K22, K23 (Y)</strong>
          / <strong>K31, K32, K33 (Z)</strong></li>
      <li><strong>Only Corresponding PBC</strong> — igual ao painel Elastic.</li>
      <li><strong>Initial / Final Temperature (°C)</strong>,
          <strong>Segment</strong> — varredura opcional de temperatura,
          mesma conversão °C → K.</li>
    </ul>
    <div class="callout callout-warn">
      <p>A malha precisa ser do tipo <strong>thermal</strong> (família
      DC3D8). Se você malhou para análise mecânica, refaça a malha com o
      tipo correto (aba Mesh Control).</p>
    </div>
  </div>
</div>

<h2>3.6.4 Selecionar intervalo de modelos para análise</h2>

<p>Mesmo controle Current / All / Selected numbers. Para múltiplos
modelos, o plug-in submete um job Abaqus por modelo e agrega os
resultados.</p>

<ul>
  <li><strong>Current</strong> — analisa apenas o modelo selecionado.</li>
  <li><strong>All Models</strong> — analisa todos os modelos que compartilham
      o nome-base e o padrão de índice do modelo selecionado.</li>
  <li><strong>Selected numbers</strong> — uma lista de vírgulas / intervalos
      (ex.: <code>1,3,5-8</code>) escolhendo os índices a analisar.</li>
</ul>

<div class="callout callout-note">
  <div class="callout-title">A análise em lote agora funciona em modelos de interface</div>
  <p>Modelos comuns são nomeados <code>&lt;base&gt;_&lt;N&gt;</code>, onde
  <code>N</code> é o índice do modelo. <strong>Modelos de interface</strong>
  produzidos pela aba Interface inserem esse índice <em>antes</em> de um rótulo
  de interface final &mdash; por exemplo <code>&lt;base&gt;_cohesive_3_D000</code>
  (descolamento coesivo) ou <code>&lt;base&gt;_thermal_3_&hellip;</code>
  (costura térmica de Kapitza). Versões anteriores resolviam o índice com um
  simples <code>rsplit('_')</code>, que confundia o rótulo final
  (<code>D000</code>) com o índice, fazendo <em>All Models</em> e
  <em>Selected numbers</em> falharem em modelos de interface. O dispatcher
  agora detecta o índice em ambos os esquemas de nomenclatura, então a análise
  em lote (All / Selected numbers) funciona corretamente em modelos comuns
  <strong>e</strong> de interface, incluindo condutividade térmica de interface.</p>
</div>

<h2>3.6.5 Notas de comportamento</h2>

<ul>
  <li>O campo <strong>UMAT</strong> é desabilitado automaticamente quando o
      tipo de análise não o suporta, e habilitado para Elastoplastic. Mesmo
      habilitado é <em>opcional</em> — deixe em branco se não precisar.</li>
  <li>As <strong>entradas de temperatura do CTE</strong> ficam desabilitadas
      até o checkbox CTE ser marcado.</li>
  <li>Trocar o tipo de análise dispara um re-layout da diálogo, mostrando
      apenas os campos relevantes.</li>
</ul>

<h2>3.6.6 Após clicar em OK — saídas e mudanças no banco de dados</h2>

<p>Para cada modelo selecionado, o plug-in:</p>
<ol>
  <li>Gera as condições de contorno periódicas na instância malhada de
      <code>UDComposite</code>.</li>
  <li>Cria os steps de análise exigidos pelo Analysis Type escolhido (um
      por módulo, mais um step térmico para CTE).</li>
  <li>Submete um job Abaqus, espera o término, e grava o
      <code>.odb</code> resultante no diretório de trabalho.</li>
  <li>Pós-processa o ODB e grava um resumo CSV / TXT com as propriedades
      homogeneizadas, ao lado do ODB.</li>
</ol>

<p>Em execução em lote (All / Selected numbers), um ODB e um arquivo
resumo são produzidos por modelo, nomeados conforme o modelo. Resultados
agregados aparecem na área de mensagens do Abaqus.</p>
<h3>Saída de Elastic + CTE</h3>

<table class="field-table">
  <thead><tr><th>Arquivo</th><th>Conteúdo</th></tr></thead>
  <tbody>
    <tr>
      <td><code>&lt;part&gt;_elastic_properties.txt</code></td>
      <td>Relatório texto com os módulos efetivos
      (E11/E22/E33 e G12/G13/G23 conforme marcado), mais CTE quando a
      caixa CTE está ativa. Também grava
      <code>&lt;part&gt;_elastic_properties(easycopy).txt</code> em layout
      compatível com easyPBC para copy-paste.</td>
    </tr>
    <tr>
      <td><code>&lt;model&gt;_CTE_results.csv</code></td>
      <td>Uma linha por segmento da rampa de temperatura:
      start/end/average e CTE_X/CTE_Y/CTE_Z. O dispatcher renomeia em
      execuções em lote para incluir a faixa de temperatura.</td>
    </tr>
    <tr>
      <td><code>&lt;model&gt;_elastic_temperature_sweep_&lt;timestamp&gt;.csv</code></td>
      <td>Só quando <em>Temperature Points (&deg;C)</em> não está vazio.
      Cada linha agrega os módulos calculados em cada temperatura.</td>
    </tr>
  </tbody>
</table>

<h3>Saída de Thermal Conductivity</h3>

<table class="field-table">
  <thead><tr><th>Arquivo</th><th>Conteúdo</th></tr></thead>
  <tbody>
    <tr>
      <td><code>&lt;part&gt;_thermal_properties.txt</code></td>
      <td>Relatório texto com o tensor de condutividade efetivo
      (K11/K12/K13/K21/K22/K23/K31/K32/K33 conforme marcado). Também
      grava o <code>(easycopy).txt</code> para copiar / colar.</td>
    </tr>
  </tbody>
</table>

<h3>Saída Viscoelástica (tempo / frequência)</h3>

<table class="field-table">
  <thead><tr><th>Padrão de arquivo</th><th>Conteúdo</th></tr></thead>
  <tbody>
    <tr>
      <td><code>&lt;model&gt;_E11_v12_v13_viscoelastic_time_Temp&lt;TTT&gt;.csv</code><br>
          <code>&lt;model&gt;_E33_v31_v32_viscoelastic_time_Temp&lt;TTT&gt;.csv</code><br>
          <code>&lt;model&gt;_G12_viscoelastic_time_Temp&lt;TTT&gt;.csv</code><br>
          <code>&lt;model&gt;_G13_viscoelastic_time_Temp&lt;TTT&gt;.csv</code><br>
          <code>&lt;model&gt;_G23_viscoelastic_time_Temp&lt;TTT&gt;.csv</code></td>
      <td>Módulo de relaxação no domínio do tempo amostrado nos pontos
      escolhidos. Um arquivo por componente ativo, por temperatura.
      Domínio da frequência usa <code>_viscoelastic_freq_</code> no lugar
      de <code>_viscoelastic_time_</code>; as colunas então carregam o
      módulo complexo (storage / loss) por frequência.</td>
    </tr>
  </tbody>
</table>

<h3>Saída CSV elastoplástica</h3>

<p>Para cada (modelo, caso de carga, temperatura) o analisador escreve
estes arquivos na sub-pasta do caso:</p>

<table class="field-table">
  <thead><tr><th>Arquivo</th><th>Conteúdo</th></tr></thead>
  <tbody>
    <tr>
      <td><code>&lt;model&gt;_all_RP_history_&lt;case&gt;.csv</code></td>
      <td>Histórico por frame e por reference point (U1/U2/U3, RF1/RF2/RF3,
      e os 6 componentes de tensão / deformação por RP).</td>
    </tr>
    <tr>
      <td><code>&lt;model&gt;_macroscopic_stress_strain_&lt;case&gt;.csv</code></td>
      <td>Tensor macroscópico 6+6 por frame, mais von Mises, pressão
      hidrostática, triaxialidade, deformação volumétrica e taxa de
      deformação equivalente. Cisalhamentos como
      <code>2*Gamma_ij</code> (engineering).</td>
    </tr>
    <tr>
      <td><code>&lt;model&gt;_true_stress_strain_&lt;case&gt;.csv</code></td>
      <td>Tensão Cauchy / deformação logarítmica na direção de carga ativa.
      Layout depende do tipo de carga:
        <ul>
          <li><em>Normal</em> (E11/E22/E33): 4 colunas de dados &mdash;
          <code>True_Strain</code>, <code>True_Stress</code>,
          <code>True_Strain_Abs</code>, <code>True_Stress_Abs</code>.</li>
          <li><em>Shear</em> (G12/G13/G23): 2 colunas de dados &mdash;
          <code>True_Shear_Strain</code> (tensor shear verdadeiro,
          <code>= ln(1 + eps_ij) * sign</code>; multiplique por 2 para
          recuperar o gamma de engenharia) e <code>True_Shear_Stress</code>
          (Cauchy shear stress).</li>
        </ul>
      </td>
    </tr>
    <tr>
      <td><code>&lt;model&gt;_volume_averages_&lt;case&gt;.csv</code></td>
      <td>Médias volumétricas de tensão / deformação / Mises sobre o RVE
      (uma linha).</td>
    </tr>
    <tr>
      <td><code>&lt;model&gt;_analysis_summary_&lt;case&gt;.csv</code></td>
      <td>Resumo de uma linha: nome do modelo, instância, rótulo de carga,
      propriedades efetivas, rigidez aparente.</td>
    </tr>
  </tbody>
</table>
`;
