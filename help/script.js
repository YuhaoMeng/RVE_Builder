/* =========================================================================
   RVE Builder Help Manual — main script
   - Section content lives in content/<lang>/<id>.js files. Each file
     registers a string into window.helpContent['<lang>/<id>'].
   - We load sections by appending a <script> tag at runtime. This works
     directly from file:// (no fetch / CORS issues), so users can simply
     double-click index.html.
   - To add a new page: drop content/<lang>/<id>.js with the standard
     wrapper, and add an <a class="toc-link" data-section="<id>"> entry
     to index.html.
   - Languages cycle: en -> zh -> pt -> en
   ========================================================================= */

(function () {
  // Make sure the registry exists before any content file is loaded.
  window.helpContent = window.helpContent || {};
  // Track which keys are currently being fetched, to avoid double-loads.
  const inFlight = {};

  // Available languages.
  const LANG_ORDER = ['en', 'zh', 'pt'];
  const LANG_LABEL = { en: 'EN', zh: '中文', pt: 'PT' };

  const tocLinks   = document.querySelectorAll('.toc-link');
  const contentEl  = document.getElementById('content');
  const langSwitch = document.getElementById('lang-switch');
  const langBtns   = langSwitch ? langSwitch.querySelectorAll('.seg-btn') : [];
  const themeBtn   = document.getElementById('theme-toggle');
  const tocSearch  = document.getElementById('toc-search');
  const backToTop  = document.getElementById('back-to-top');

  // --- Language state ---------------------------------------------------
  let lang = localStorage.getItem('rveHelpLang') || 'en';
  if (!LANG_ORDER.includes(lang)) lang = 'en';
  applyLangSwitch();

  // --- Theme state ------------------------------------------------------
  let theme = localStorage.getItem('rveHelpTheme') || 'light';
  document.documentElement.setAttribute('data-theme', theme);
  themeBtn.textContent = theme === 'dark' ? 'Light' : 'Dark';

  themeBtn.addEventListener('click', () => {
    theme = theme === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('rveHelpTheme', theme);
    themeBtn.textContent = theme === 'dark' ? 'Light' : 'Dark';
  });

  // Segmented control: each button picks a specific language.
  langBtns.forEach((btn) => {
    btn.addEventListener('click', () => {
      const next = btn.getAttribute('data-lang');
      if (!LANG_ORDER.includes(next) || next === lang) return;
      lang = next;
      localStorage.setItem('rveHelpLang', lang);
      applyLangSwitch();
      loadCurrentSection();
    });
  });

  function applyLangSwitch() {
    langBtns.forEach((btn) => {
      const isActive = btn.getAttribute('data-lang') === lang;
      btn.classList.toggle('active', isActive);
      btn.setAttribute('aria-checked', isActive ? 'true' : 'false');
      btn.setAttribute('title', 'Switch to ' + LANG_LABEL[btn.getAttribute('data-lang')]);
    });
  }

  // --- Section loader ---------------------------------------------------
  // Loads via dynamic <script> tag (works from file:// — no CORS).
  function loadSection(id) {
    setActiveLink(id);
    const key = `${lang}/${id}`;

    if (window.helpContent[key]) {
      showContent(window.helpContent[key]);
      return;
    }
    if (inFlight[key]) return;       // already loading
    inFlight[key] = true;

    contentEl.innerHTML = '<div class="loading">Loading…</div>';

    const script = document.createElement('script');
    // Path is RELATIVE to index.html — works at any install location.
    script.src = `content/${key}.js`;
    script.onload = () => {
      delete inFlight[key];
      showContent(window.helpContent[key] || '');
    };
    script.onerror = () => {
      delete inFlight[key];
      // Fallback to English if the requested language file is missing.
      if (lang !== 'en') {
        const enKey = `en/${id}`;
        if (window.helpContent[enKey]) {
          showContent(window.helpContent[enKey] +
            `<div class="callout callout-note"><div class="callout-title">Translation pending</div>
             <p>This section has not been translated to ${LANG_LABEL[lang]} yet — showing English version.</p></div>`);
          return;
        }
        // Try to load EN
        const fb = document.createElement('script');
        fb.src = `content/en/${id}.js`;
        fb.onload = () => {
          showContent((window.helpContent[enKey] || '') +
            `<div class="callout callout-note"><div class="callout-title">Translation pending</div>
             <p>This section has not been translated to ${LANG_LABEL[lang]} yet — showing English version.</p></div>`);
        };
        fb.onerror = () => showLoadError(script.src);
        document.head.appendChild(fb);
        return;
      }
      showLoadError(script.src);
    };
    document.head.appendChild(script);
  }

  function showLoadError(src) {
    contentEl.innerHTML = `<div class="callout callout-warn">
      <div class="callout-title">Could not load this section</div>
      <p>Tried to load <code>${src}</code>.<br>
      Make sure the file exists.</p>
    </div>`;
  }

  function showContent(html) {
    contentEl.innerHTML = html;
    hookInlineTabs();
    hookSeedCalculator();
    if (window.MathJax && MathJax.typesetPromise) MathJax.typesetPromise([contentEl]);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  function setActiveLink(id) {
    tocLinks.forEach(a => a.classList.toggle('active', a.dataset.section === id));
  }

  function loadCurrentSection() {
    const hash = (location.hash || '#intro').slice(1);
    loadSection(hash);
  }

  // --- TOC click & hash change -----------------------------------------
  tocLinks.forEach(link => {
    link.addEventListener('click', e => {
      e.preventDefault();
      const id = link.dataset.section;
      history.replaceState(null, '', '#' + id);
      loadSection(id);
    });
  });
  window.addEventListener('hashchange', loadCurrentSection);

  // --- TOC search (filters sidebar links) -------------------------------
  tocSearch.addEventListener('input', () => {
    const q = tocSearch.value.toLowerCase().trim();
    tocLinks.forEach(a => {
      a.style.display = !q || a.textContent.toLowerCase().includes(q) ? '' : 'none';
    });
  });

  // --- Inline tabs inside content (interactive) -------------------------
  function hookInlineTabs() {
    contentEl.querySelectorAll('.inline-tabs').forEach(group => {
      const buttons = group.querySelectorAll('.tab-btn');
      const panels  = group.querySelectorAll('.tab-panel');
      buttons.forEach((btn, i) => {
        btn.addEventListener('click', () => {
          buttons.forEach(b => b.classList.remove('active'));
          panels.forEach(p => p.classList.remove('active'));
          btn.classList.add('active');
          panels[i].classList.add('active');
        });
      });
      if (buttons.length && !group.querySelector('.tab-btn.active')) {
        buttons[0].classList.add('active');
        panels[0].classList.add('active');
      }
    });
  }

  // --- Mesh seed calculator (interactive widget) ------------------------
  // Looks for any element with id="seed-calc" inside loaded content.
  // Inputs: df (fiber diameter), NR (seeds around fiber), L (edge length).
  // Outputs: approximate element size = pi * df / NR
  //          recommended NL = L / approx_size = L * NR / (pi * df)
  function hookSeedCalculator() {
    const root = contentEl.querySelector('#seed-calc');
    if (!root) return;
    const dfIn = root.querySelector('[data-calc=df]');
    const nrIn = root.querySelector('[data-calc=nr]');
    const lIn  = root.querySelector('[data-calc=l]');
    const sOut = root.querySelector('[data-calc=size]');
    const nOut = root.querySelector('[data-calc=nl]');

    function update() {
      const df = parseFloat(dfIn.value);
      const nr = parseFloat(nrIn.value);
      const L  = parseFloat(lIn.value);
      if (!isFinite(df) || !isFinite(nr) || !isFinite(L) || nr <= 0 || df <= 0) {
        sOut.textContent = '—';
        nOut.textContent = '—';
        return;
      }
      const size = Math.PI * df / nr;
      const nl   = L / size;
      sOut.textContent = size.toFixed(4);
      nOut.textContent = nl.toFixed(2) + '  →  use ' + Math.round(nl);
    }
    [dfIn, nrIn, lIn].forEach(el => el && el.addEventListener('input', update));
    update();
  }

  // --- Back-to-top button -----------------------------------------------
  window.addEventListener('scroll', () => {
    backToTop.classList.toggle('visible', window.scrollY > 400);
  });
  backToTop.addEventListener('click', () => {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  });

  // --- Initial load -----------------------------------------------------
  loadCurrentSection();
})();
