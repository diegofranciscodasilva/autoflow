/*
 * AutoFlow: lógica do front-end
 * Planilhas: envia o arquivo + regras ao back-end, mostra prévia e permite baixar.
 * Arquivos: envia vários arquivos e baixa um ZIP organizado.
 */
document.addEventListener('DOMContentLoaded', () => {
    const API = 'http://localhost:5000/api';
    const $ = (id) => document.getElementById(id);
    const esc = (s = '') => String(s).replace(/[&<>"']/g, c => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;',
    }[c]));
    const MAX_SHEET = 10 * 1024 * 1024; // 10 MB (igual ao back-end)
    const MAX_FILES = 15 * 1024 * 1024; // 15 MB no total

    $('current-year').textContent = new Date().getFullYear();

    // ========== MENU MOBILE ==========
    $('nav-toggle').addEventListener('click', () => {
        const open = $('nav-menu').classList.toggle('show');
        $('nav-toggle').setAttribute('aria-expanded', open);
        $('nav-toggle').querySelector('i').className = open ? 'ri-close-line' : 'ri-menu-line';
    });
    document.querySelectorAll('.header__link').forEach(l => l.addEventListener('click', () => {
        $('nav-menu').classList.remove('show');
        $('nav-toggle').querySelector('i').className = 'ri-menu-line';
        $('nav-toggle').setAttribute('aria-expanded', 'false');
    }));

    // ========== LINK ATIVO AO ROLAR + SCROLL UP ==========
    const sections = document.querySelectorAll('main section[id]');
    const navLinks = document.querySelectorAll('.header__link');
    window.addEventListener('scroll', () => {
        let currentId = sections[0].id;
        sections.forEach(s => { if (window.scrollY >= s.offsetTop - 120) currentId = s.id; });
        navLinks.forEach(l => l.classList.toggle('active', l.getAttribute('href') === `#${currentId}`));
        $('scroll-up').classList.toggle('show', window.scrollY > 400);
    });
    $('scroll-up').addEventListener('click', () => window.scrollTo({ top: 0, behavior: 'smooth' }));

    // ========== UTILIDADES ==========
    const formatSize = (b) => b < 1024 ? `${b} B` : b < 1048576 ? `${(b / 1024).toFixed(1)} KB` : `${(b / 1048576).toFixed(1)} MB`;

    function setStatus(el, msg, isError = false) {
        el.textContent = msg;
        el.classList.toggle('error', isError);
    }

    /** Habilita arrastar e soltar em uma dropzone. */
    function enableDrop(zone, input) {
        ['dragenter', 'dragover'].forEach(ev => zone.addEventListener(ev, (e) => { e.preventDefault(); zone.classList.add('over'); }));
        ['dragleave', 'drop'].forEach(ev => zone.addEventListener(ev, (e) => { e.preventDefault(); zone.classList.remove('over'); }));
        zone.addEventListener('drop', (e) => { input.files = e.dataTransfer.files; input.dispatchEvent(new Event('change')); });
    }

    /** Baixa um Blob como arquivo. */
    function download(blob, name) {
        const a = document.createElement('a');
        const url = URL.createObjectURL(blob);
        a.href = url;
        a.download = name;
        document.body.appendChild(a);
        a.click();
        a.remove();
        setTimeout(() => URL.revokeObjectURL(url), 0);
    }

    /** Lê a mensagem de erro do back-end ou devolve uma padrão (back-end offline). */
    async function errorMessage(res) {
        try { return (await res.json()).error; } catch { return 'Não foi possível processar. Tente novamente.'; }
    }
    const OFFLINE = 'Não foi possível conectar ao servidor. Verifique se o back-end está rodando.';

    // ========== PLANILHAS ==========
    let sheetFile = null;
    const ruleBoxes = () => document.querySelectorAll('.rules input[type="checkbox"]');
    const selectedRules = () => [...ruleBoxes()].filter(c => c.checked).map(c => c.value);

    enableDrop($('sheet-drop'), $('sheet-input'));
    $('sheet-input').addEventListener('change', () => {
        const f = $('sheet-input').files[0];
        $('sheet-result').hidden = true;
        sheetFile = null;
        $('btn-process').disabled = true;
        if (!f) {
            $('sheet-name').textContent = 'Clique ou arraste uma planilha';
            return setStatus($('sheet-status'), '');
        }
        if (!/\.(csv|xlsx)$/i.test(f.name)) return setStatus($('sheet-status'), 'Formato inválido. Use .csv ou .xlsx.', true);
        if (f.size > MAX_SHEET) return setStatus($('sheet-status'), 'Arquivo acima de 10 MB.', true);
        sheetFile = f;
        $('sheet-name').textContent = `${f.name} (${formatSize(f.size)})`;
        $('btn-process').disabled = false;
        setStatus($('sheet-status'), '');
    });

    // Interpreta o comando em texto e marca as regras correspondentes
    $('btn-interpret').addEventListener('click', async () => {
        const text = $('command-input').value.trim();
        if (!text) return setStatus($('sheet-status'), 'Escreva um comando para interpretar.', true);
        try {
            const res = await fetch(`${API}/sheet/interpret`, {
                method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text }),
            });
            if (!res.ok) throw new Error(await errorMessage(res));
            const { rules } = await res.json();
            ruleBoxes().forEach(c => { c.checked = rules.includes(c.value); });
            setStatus($('sheet-status'), rules.length ? `${rules.length} regra(s) marcada(s). Revise antes de gerar a prévia.` : 'Não entendi o comando. Marque as regras manualmente.', !rules.length);
        } catch (err) {
            setStatus($('sheet-status'), err.message === 'Failed to fetch' ? OFFLINE : err.message, true);
        }
    });

    /** Monta o FormData comum à prévia e ao download. */
    function sheetFormData(extra = {}) {
        const fd = new FormData();
        fd.append('file', sheetFile);
        fd.append('rules', JSON.stringify(selectedRules()));
        Object.entries(extra).forEach(([k, v]) => fd.append(k, v));
        return fd;
    }

    $('btn-process').addEventListener('click', async () => {
        if (!sheetFile) return;
        $('btn-process').disabled = true;
        setStatus($('sheet-status'), 'Processando...');
        try {
            const res = await fetch(`${API}/sheet/process`, { method: 'POST', body: sheetFormData() });
            if (!res.ok) throw new Error(await errorMessage(res));
            renderSheetResult(await res.json());
            setStatus($('sheet-status'), '');
        } catch (err) {
            setStatus($('sheet-status'), err.message === 'Failed to fetch' ? OFFLINE : err.message, true);
        } finally {
            $('btn-process').disabled = false;
        }
    });

    function renderSheetResult(r) {
        $('sheet-stats').innerHTML = `
      <div class="stat"><b>${r.rows_before}</b><span>linhas antes</span></div>
      <div class="stat"><b>${r.rows_after}</b><span>linhas depois</span></div>
      <div class="stat"><b>${r.rows_before - r.rows_after}</b><span>removidas</span></div>`;
        $('sheet-log').innerHTML = r.log.length
            ? r.log.map(l => `<li>${esc(l)}</li>`).join('')
            : '<li>Nenhuma regra selecionada: o arquivo não foi alterado.</li>';
        $('sheet-table').innerHTML =
            `<thead><tr>${r.columns.map(c => `<th>${esc(c)}</th>`).join('')}</tr></thead>` +
            `<tbody>${r.preview.map(row => `<tr>${row.map(v => `<td>${esc(v)}</td>`).join('')}</tr>`).join('')}</tbody>`;
        $('sheet-result').hidden = false;
    }

    // Download do arquivo tratado (CSV ou XLSX)
    document.querySelectorAll('[data-format]').forEach(btn => btn.addEventListener('click', async () => {
        const format = btn.dataset.format;
        setStatus($('sheet-status'), 'Gerando arquivo...');
        try {
            const res = await fetch(`${API}/sheet/download`, { method: 'POST', body: sheetFormData({ format }) });
            if (!res.ok) throw new Error(await errorMessage(res));
            const base = sheetFile.name.replace(/\.[^.]+$/, '');
            download(await res.blob(), `${base}_tratado.${format}`);
            setStatus($('sheet-status'), 'Download iniciado.');
        } catch (err) {
            setStatus($('sheet-status'), err.message === 'Failed to fetch' ? OFFLINE : err.message, true);
        }
    }));

    // ========== ARQUIVOS ==========
    let chosenFiles = [];
    enableDrop($('files-drop'), $('files-input'));
    $('files-input').addEventListener('change', () => {
        chosenFiles = [...$('files-input').files];
        const total = chosenFiles.reduce((s, f) => s + f.size, 0);
        $('file-list').innerHTML = chosenFiles.map(f => `<li><span>${esc(f.name)}</span><small>${formatSize(f.size)}</small></li>`).join('');
        if (total > MAX_FILES) {
            chosenFiles = [];
            $('file-list').innerHTML = '';
            $('btn-organize').disabled = true;
            return setStatus($('files-status'), 'O total passa de 15 MB. Envie menos arquivos.', true);
        }
        $('btn-organize').disabled = chosenFiles.length === 0;
        setStatus($('files-status'), chosenFiles.length ? `${chosenFiles.length} arquivo(s) selecionado(s).` : '');
    });

    $('btn-organize').addEventListener('click', async () => {
        const fd = new FormData();
        chosenFiles.forEach(f => fd.append('files', f));
        fd.append('prefix_date', $('opt-date').checked);
        fd.append('slugify', $('opt-slug').checked);

        $('btn-organize').disabled = true;
        setStatus($('files-status'), 'Organizando...');
        try {
            const res = await fetch(`${API}/files/organize`, { method: 'POST', body: fd });
            if (!res.ok) throw new Error(await errorMessage(res));
            download(await res.blob(), 'arquivos_organizados.zip');
            setStatus($('files-status'), 'ZIP gerado. O relatório está dentro dele (RELATORIO.txt).');
        } catch (err) {
            setStatus($('files-status'), err.message === 'Failed to fetch' ? OFFLINE : err.message, true);
        } finally {
            $('btn-organize').disabled = false;
        }
    });

    window.dispatchEvent(new Event('scroll')); // define o link ativo inicial
});
