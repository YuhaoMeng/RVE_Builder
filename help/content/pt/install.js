// Auto-loaded via <script> tag from index.html
// Edit the HTML inside the template literal below; do NOT change the wrapper.
window.helpContent = window.helpContent || {};
window.helpContent['pt/install'] = `
<!-- ===== SECTION: install (PT-BR) ========================================= -->
<h1>2 · Instalação do plug-in</h1>

<p>
  Este plug-in foi desenvolvido para <strong>Abaqus/CAE 2024</strong> e
  utiliza o interpretador Python 3 embutido no Abaqus. Atualizações
  periódicas são publicadas no GitHub; para evitar incompatibilidades em
  tempo de execução, use a versão recomendada do Abaqus.
</p>

<h2>Local de instalação</h2>

<p>Copie a pasta inteira <code>RVE_Builder_plugin</code> para o diretório
de plug-ins do Abaqus. No Windows, normalmente:</p>

<pre><code>C:\\SIMULIA\\CAE\\plugins\\2024\\</code></pre>

<p>Após copiar, reinicie o Abaqus/CAE. O plug-in aparecerá no menu como
<strong>Plug-ins → RVE Builder (UDFRPs)</strong>.</p>

<h2>Arquivos do pacote</h2>

<table class="field-table">
  <thead>
    <tr><th>Arquivo</th><th>Tipo</th><th>Função</th></tr>
  </thead>
  <tbody>
    <tr><td><code>RVE_Builder_UDFRPs_plugin.py</code></td><td>Form GUI</td>
        <td>Registra a entrada de menu e define todos os bindings de keywords.</td></tr>
    <tr><td><code>RVE_Builder_UDFRPsDB.py</code></td><td>Diálogo GUI</td>
        <td>Constrói a janela de diálogo com abas e conecta os eventos da UI.</td></tr>
    <tr><td><code>RVE_Builder_UDFRPs.py</code></td><td>Kernel</td>
        <td>Implementa as operações disparadas por cada aba.</td></tr>
    <tr><td><code>Generate_UDFRPs_MonteCarlo.py</code></td><td>Gerador</td>
        <td>Gerador Monte-Carlo de coordenadas de fibras.</td></tr>
    <tr><td><code>Generate_UDFRPs_RSE.py</code></td><td>Gerador</td>
        <td>Gerador RSE (Random Sequential Expansion) de coordenadas de fibras.</td></tr>
    <tr><td><code>PBC_UDFRP_Elastic_CTE.py</code></td><td>Analisador</td>
        <td>Homogeneização elástica + CTE (analysis_type = 1).</td></tr>
    <tr><td><code>PBC_UDFRP_Viscoelastic_Time.py</code></td><td>Analisador</td>
        <td>Análise viscoelástica no domínio do tempo (analysis_type = 2).</td></tr>
    <tr><td><code>PBC_UDFRP_Viscoelastic_Frequency.py</code></td><td>Analisador</td>
        <td>Análise viscoelástica no domínio da frequência (analysis_type = 3).</td></tr>
    <tr><td><code>PBC_UDFRP_Elastoplastic.py</code></td><td>Analisador</td>
        <td>Análise elasto-plástica sob deformação macroscópica. Cobre
        Uniaxial (analysis_type = 4) e Biaxial (analysis_type = 6). Define
        Solution Controls como <em>Specify ON, Discontinuous, IC = 30</em>
        em cada execução e expõe os toggles <em>Nlgeom</em> e
        <em>Unsymmetric matrix storage</em> na GUI.</td></tr>
    <tr><td><code>PBC_UDFRP_thermal_conductivity.py</code></td><td>Analisador</td>
        <td>Tensor de condutividade térmica em regime estacionário (analysis_type = 5).</td></tr>
    <tr><td><code>PBC_UDFRP_Elastoplastic_interface.py</code></td><td>Analisador</td>
        <td>Variante "ciente de interface" do kernel elastoplástico;
        selecionada automaticamente pelo dispatcher quando o modelo
        escolhido já contém costuras coesivas COH3D8 (por exemplo um
        modelo <code>*_Interface</code> da aba Interface).</td></tr>
    <tr><td><code>PBC_UDFRP_thermal_conductivity_Interfaceh.py</code></td><td>Analisador</td>
        <td>Variante ciente de interface do kernel térmico, com o mesmo
        roteamento automático.</td></tr>
  </tbody>
</table>

<h2>Verificando a instalação</h2>
<ol>
  <li>Abra o Abaqus/CAE 2024.</li>
  <li>No menu superior, escolha <strong>Plug-ins</strong>.</li>
  <li>Você deve ver <strong>RVE Builder (UDFRPs)</strong>. Clique para
      abrir o diálogo.</li>
  <li>Devem aparecer seis abas: Create RVE, Mesh Control, Materials,
      Void Insertion, Interface, Analysis.</li>
</ol>

<details class="collapsible">
  <summary>Resolução de problemas</summary>
  <p><strong>O plug-in não aparece no menu.</strong> Confirme o caminho
  da pasta. No Windows, clique com o botão direito nos arquivos →
  Propriedades → Desbloquear.</p>
  <p><strong>Erro "Module not found".</strong> Algum arquivo renomeado
  está faltando. Confirme que todos os arquivos da tabela acima estão
  presentes na raiz da pasta do plug-in.</p>
  <p><strong>"AttributeError: object has no attribute …".</strong> Pode
  haver um <code>__pycache__</code> obsoleto sendo carregado. Apague a
  pasta <code>__pycache__</code> dentro do diretório do plug-in e
  reinicie o Abaqus.</p>
</details>
`;
