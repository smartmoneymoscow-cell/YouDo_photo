// YouDo Photo v2 — Frontend с AI-отбором по эмбеддингам
// ========================================================

(function () {
  'use strict';

  // ═══ Конфигу═══
  // Если сайт на Render — API_BASE будет текущий origin.
  // Для локальной разработки — пустая строка (same origin).
  const API_BASE = window.YOUDO_API_BASE || '';

  // ═══ Состояние ═══
  const state = {
    sessionId: null,
    rawFiles: [],
    refFiles: [],
    videoFiles: [],
    currentStep: 1,
    results: [],       // [{path, score, rank, accepted, status}]
    params: {
      model: null,  // auto-select based on available RAM
      threshold: 0.75,
      topK: 0,
      refMethod: 'max',
      maxSide: 1024,
    },
  };

  // ═══ DOM ═══
  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => document.querySelectorAll(sel);

  // ═══ Навигация по шагам ═══
  function goToStep(step) {
    state.currentStep = step;
    $$('.step-panel').forEach(p => p.classList.remove('active'));
    $(`#step${step}`).classList.add('active');
    $$('.step-btn').forEach((btn, i) => {
      btn.classList.remove('active');
      if (i + 1 === step) btn.classList.add('active');
      if (i + 1 < step) btn.classList.add('completed');
    });
    window.scrollTo({ top: 0, behavior: 'smooth' });

    if (step === 3) renderGallery();
    if (step === 4) { buildExportPreview(); updateExportSummary(); }
  }

  $$('.step-btn').forEach(btn => {
    btn.addEventListener('click', () => goToStep(parseInt(btn.dataset.step)));
  });

  $('#btnToStep2').addEventListener('click', () => goToStep(2));
  $('#btnBackTo1').addEventListener('click', () => goToStep(1));
  $('#btnBackTo2').addEventListener('click', () => goToStep(2));
  $('#btnBackTo3').addEventListener('click', () => goToStep(3));
  $('#btnToStep4').addEventListener('click', () => goToStep(4));

  // ═══ Dropzones ═══
  function initDropzone(dropzoneEl, inputEl, onFiles) {
    dropzoneEl.addEventListener('click', () => inputEl.click());
    dropzoneEl.addEventListener('dragover', (e) => { e.preventDefault(); dropzoneEl.classList.add('dragover'); });
    dropzoneEl.addEventListener('dragleave', () => dropzoneEl.classList.remove('dragover'));
    dropzoneEl.addEventListener('drop', (e) => { e.preventDefault(); dropzoneEl.classList.remove('dragover'); onFiles(e.dataTransfer.files); });
    inputEl.addEventListener('change', () => { onFiles(inputEl.files); inputEl.value = ''; });
  }

  // RAW файлы
  initDropzone($('#dropzoneRaw'), $('#dropzoneRaw input[type="file"]'), (files) => {
    for (const f of files) state.rawFiles.push(f);
    updateRawInfo();
    updateNextButton();
  });

  function updateRawInfo() {
    const count = state.rawFiles.length;
    const size = state.rawFiles.reduce((s, f) => s + f.size, 0);
    $('#rawInfo .file-count').textContent = `${count} файлов`;
    $('#rawInfo .file-size').textContent = formatSize(size);
    const list = $('#rawList');
    list.innerHTML = '';
    state.rawFiles.forEach(f => {
      const item = document.createElement('div');
      item.className = 'file-list-item';
      item.innerHTML = `<span class="fname">${f.name}</span><span class="fsize">${formatSize(f.size)}</span>`;
      list.appendChild(item);
    });
  }

  // Видео файлы
  initDropzone($('#dropzoneVideo'), $('#dropzoneVideo input[type="file"]'), (files) => {
    for (const f of files) state.videoFiles.push(f);
    updateVideoInfo();
    updateNextButton();
  });

  function updateVideoInfo() {
    const count = state.videoFiles.length;
    const size = state.videoFiles.reduce((s, f) => s + f.size, 0);
    $('#videoInfo .file-count').textContent = `${count} файлов`;
    $('#videoInfo .file-size').textContent = formatSize(size);
    const list = $('#videoList');
    list.innerHTML = '';
    state.videoFiles.forEach(f => {
      const item = document.createElement('div');
      item.className = 'file-list-item';
      item.innerHTML = `<span class="fname">${f.name}</span><span class="fsize">${formatSize(f.size)}</span>`;
      list.appendChild(item);
    });
  }

  // JPG эталоны
  initDropzone($('#dropzoneRef'), $('#dropzoneRef input[type="file"]'), (files) => {
    for (const f of files) state.refFiles.push(f);
    updateRefPreview();
    updateNextButton();
  });

  function updateRefPreview() {
    const grid = $('#refPreview');
    grid.innerHTML = '';
    $('#refInfo .file-count').textContent = `${state.refFiles.length} файлов`;
    state.refFiles.forEach((f, i) => {
      const img = document.createElement('img');
      img.src = URL.createObjectURL(f);
      img.title = f.name;
      if (i === 0) img.classList.add('starred');
      img.addEventListener('click', () => { grid.querySelectorAll('img').forEach(el => el.classList.remove('starred')); img.classList.add('starred'); });
      grid.appendChild(img);
    });
  }

  function updateNextButton() {
    $('#btnToStep2').disabled = state.rawFiles.length === 0 && state.videoFiles.length === 0 || state.refFiles.length === 0;
  }

  // ═══ Range sliders ═══
  $$('input[type="range"]').forEach(range => {
    const display = $(`.range-val[data-for="${range.id}"]`);
    if (display) {
      const suffix = display.textContent.includes('%') ? '%' : '';
      range.addEventListener('input', () => { display.textContent = range.value + suffix; });
    }
  });

  // ═══ Анализ ═══
  $('#btnAnalyze').addEventListener('click', async () => {
    // Собираем параметры
    state.params.threshold = parseInt($('#paramThreshold').value) / 100;
    state.params.topK = parseInt($('#paramTopK').value) || 0;
    state.params.refMethod = $('#paramRefMethod').value;
    state.params.model = $('#paramModel').value || null;
    state.params.maxSide = parseInt($('#paramMaxSide').value);

    const progressEl = $('#analysisProgress');
    const progressText = $('#progressText');
    const progressFill = $('#progressFill');

    progressEl.hidden = false;
    $('#btnAnalyze').disabled = true;
    progressText.textContent = 'Создание сессии...';
    progressFill.style.width = '5%';

    try {
      // 1. Создать сессию
      const sessRes = await apiFetch('/api/session/create', { method: 'POST' });
      state.sessionId = sessRes.session_id;

      // 2. Загрузить эталоны
      progressText.textContent = `Загрузка эталонов (${state.refFiles.length})...`;
      progressFill.style.width = '15%';
      await uploadFiles(`/api/upload/references/${state.sessionId}`, state.refFiles);

      // 3. Загрузить RAW фото
      if (state.rawFiles.length > 0) {
        progressText.textContent = `Загрузка RAW файлов (${state.rawFiles.length})...`;
        progressFill.style.width = '30%';
        await uploadFiles(`/api/upload/photos/${state.sessionId}`, state.rawFiles);
      }

      // 3b. Загрузить видео (если есть)
      if (state.videoFiles.length > 0) {
        const fps = parseFloat($('#videoFps').value) || 1;
        const maxFrames = parseInt($('#videoMaxFrames').value) || 30;
        progressText.textContent = `Загрузка видео (${state.videoFiles.length}) + извлечение кадров...`;
        progressFill.style.width = '35%';
        await uploadVideo(`/api/upload/video/${state.sessionId}`, state.videoFiles, fps, maxFrames);
      }

      // 4. Запустить анализ
      progressText.textContent = 'AI-анализ: извлечение эмбеддингов...';
      progressFill.style.width = '50%';

      // Анимация прогресса пока ждём
      let pct = 50;
      const progressInterval = setInterval(() => {
        pct = Math.min(pct + 1, 90);
        progressFill.style.width = pct + '%';
        if (pct < 60) progressText.textContent = 'AI-анализ: извлечение эмбеддингов...';
        else if (pct < 75) progressText.textContent = 'AI-анализ: сравнение с эталоном...';
        else progressText.textContent = 'AI-анализ: ранжирование кадров...';
      }, 500);

      const analyzeRes = await apiFetch(`/api/analyze/${state.sessionId}`, {
        method: 'POST',
        timeoutMs: 300000,
        body: JSON.stringify({
          model: state.params.model || null,
          threshold: state.params.threshold,
          top_k: state.params.topK || null,
          ref_method: state.params.refMethod,
          max_side: state.params.maxSide,
        }),
      });

      clearInterval(progressInterval);
      progressFill.style.width = '100%';
      progressText.textContent = `Готово! ${analyzeRes.accepted_count} из ${analyzeRes.total} принято`;

      // Сохраняем результаты
      state.results = analyzeRes.results.map(r => ({
        ...r,
        status: r.accepted ? 'accepted' : 'rejected',
      }));

      // Показываем сводку
      showAnalysisSummary(analyzeRes);

      // Переход на шаг 3 через 1.5 сек
      setTimeout(() => {
        progressEl.hidden = true;
        goToStep(3);
      }, 1500);

    } catch (err) {
      clearInterval(progressInterval);
      const msg = err.name === 'AbortError' ? 'Превышен таймаут (5 мин). Уменьшите количество файлов.' : err.message;
      progressText.textContent = `Ошибка: ${msg}`;
      progressFill.style.width = '0%';
      $('#btnAnalyze').disabled = false;
      console.error(err);
    }
  });

  function showAnalysisSummary(data) {
    const el = $('#analysisSummary');
    el.innerHTML = `
      <div class="summary-card">
        <div class="summary-stat"><span class="stat-num">${data.total}</span><span class="stat-label">всего</span></div>
        <div class="summary-stat accepted"><span class="stat-num">${data.accepted_count}</span><span class="stat-label">принято</span></div>
        <div class="summary-stat rejected"><span class="stat-num">${data.rejected_count}</span><span class="stat-label">отклонено</span></div>
        <div class="summary-stat"><span class="stat-num">${(data.best_score * 100).toFixed(1)}%</span><span class="stat-label">лучший</span></div>
        <div class="summary-stat"><span class="stat-num">${data.elapsed_sec}с</span><span class="stat-label">время</span></div>
        <div class="summary-stat"><span class="stat-num">${data.model}</span><span class="stat-label">модель</span></div>
      </div>
    `;
  }

  // ═══ Галерея ═══
  function renderGallery(filter = 'all') {
    const gallery = $('#gallery');
    gallery.innerHTML = '';

    const filtered = filter === 'all'
      ? state.results
      : state.results.filter(r => r.status === filter);

    if (filtered.length === 0) {
      gallery.innerHTML = '<div class="gallery-empty"><p>Нет фото по этому фильтру</p></div>';
      return;
    }

    filtered.forEach((item, idx) => {
      const card = document.createElement('div');
      card.className = `gallery-card ${item.status}`;
      card.dataset.index = state.results.indexOf(item);

      const scorePct = (item.score * 100).toFixed(1);
      const scoreClass = item.score >= 0.85 ? 'high' : item.score >= 0.65 ? 'mid' : 'low';
      const statusIcon = item.status === 'accepted' ? '✅' : '❌';
      const fileName = item.path.split('/').pop().split('\\').pop();

      card.innerHTML = `
        <div class="card-score-bar ${scoreClass}">${scorePct}%</div>
        <div class="card-placeholder">
          <span class="card-rank">#${item.rank}</span>
          <span class="card-fname">${fileName}</span>
        </div>
        <button class="card-toggle" data-idx="${state.results.indexOf(item)}" title="Принять/Отклонить">${statusIcon}</button>
      `;

      card.addEventListener('click', (e) => {
        if (e.target.closest('.card-toggle')) {
          const i = parseInt(e.target.closest('.card-toggle').dataset.idx);
          state.results[i].status = state.results[i].status === 'accepted' ? 'rejected' : 'accepted';
          renderGallery(getCurrentFilter());
          return;
        }
        openViewer(parseInt(card.dataset.index));
      });

      gallery.appendChild(card);
    });

    updateStats();
  }

  function updateStats() {
    const total = state.results.length;
    const accepted = state.results.filter(r => r.status === 'accepted').length;
    const rejected = state.results.filter(r => r.status === 'rejected').length;
    const pending = state.results.filter(r => r.status === 'pending').length;
    $('#statTotal').textContent = total;
    $('#statAccepted').textContent = accepted;
    $('#statRejected').textContent = rejected;
    $('#statPending').textContent = pending;
  }

  // ═══ Фильтры ═══
  $$('.filter-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      $$('.filter-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      renderGallery(btn.dataset.filter);
    });
  });

  function getCurrentFilter() {
    const active = $('.filter-btn.active');
    return active ? active.dataset.filter : 'all';
  }

  // ═══ Порог ═══
  $('#btnApplyThreshold').addEventListener('click', () => {
    const newThreshold = parseInt($('#galleryThreshold').value) / 100;
    state.results.forEach(r => {
      r.status = r.score >= newThreshold ? 'accepted' : 'rejected';
    });
    renderGallery(getCurrentFilter());
  });

  // ═══ Полноэкранный просмотр ═══
  let viewerIndex = 0;

  function openViewer(index) {
    viewerIndex = index;
    const item = state.results[index];
    const fileName = item.path.split('/').pop().split('\\').pop();

    $('#viewerImage').innerHTML = `<div class="viewer-placeholder"><span class="viewer-rank">#${item.rank}</span><span>${fileName}</span></div>`;

    const scoreColor = item.score >= 0.85 ? 'var(--success)' : item.score >= 0.65 ? 'var(--warning)' : 'var(--danger)';
    $('#viewerScore').innerHTML = `
      <div style="font-size:48px;font-weight:700;color:${scoreColor}">${(item.score * 100).toFixed(1)}%</div>
      <div style="font-size:14px;color:var(--text-muted);margin-top:4px">сходство с эталоном</div>
    `;

    $('#viewerInfo').innerHTML = `
      <div style="font-size:13px;line-height:1.6">
        <div><b>Файл:</b> ${fileName}</div>
        <div><b>Ранг:</b> #${item.rank} из ${state.results.length}</div>
        <div><b>Статус:</b> ${item.status === 'accepted' ? '✅ Принят' : '❌ Отклонён'}</div>
      </div>
    `;

    $('#fullscreenViewer').hidden = false;
    document.body.style.overflow = 'hidden';
  }

  function closeViewer() {
    $('#fullscreenViewer').hidden = true;
    document.body.style.overflow = '';
    renderGallery(getCurrentFilter());
  }

  $('#viewerClose').addEventListener('click', closeViewer);
  $('#viewerPrev').addEventListener('click', () => { viewerIndex = Math.max(0, viewerIndex - 1); openViewer(viewerIndex); });
  $('#viewerNext').addEventListener('click', () => { viewerIndex = Math.min(state.results.length - 1, viewerIndex + 1); openViewer(viewerIndex); });
  $('#viewerAccept').addEventListener('click', () => { state.results[viewerIndex].status = 'accepted'; viewerIndex < state.results.length - 1 ? openViewer(++viewerIndex) : closeViewer(); });
  $('#viewerReject').addEventListener('click', () => { state.results[viewerIndex].status = 'rejected'; viewerIndex < state.results.length - 1 ? openViewer(++viewerIndex) : closeViewer(); });

  document.addEventListener('keydown', (e) => {
    if ($('#fullscreenViewer').hidden) return;
    if (e.key === 'Escape') closeViewer();
    if (e.key === 'ArrowLeft') { viewerIndex = Math.max(0, viewerIndex - 1); openViewer(viewerIndex); }
    if (e.key === 'ArrowRight') { viewerIndex = Math.min(state.results.length - 1, viewerIndex + 1); openViewer(viewerIndex); }
    if (e.key === 'a' || e.key === 'ф') { state.results[viewerIndex].status = 'accepted'; viewerIndex < state.results.length - 1 ? openViewer(++viewerIndex) : closeViewer(); }
    if (e.key === 'r' || e.key === 'к') { state.results[viewerIndex].status = 'rejected'; viewerIndex < state.results.length - 1 ? openViewer(++viewerIndex) : closeViewer(); }
  });

  // ═══ Экспорт ═══
  function buildExportPreview() {
    const grid = $('#exportPreviewGrid');
    grid.innerHTML = '';
    const accepted = state.results.filter(r => r.status === 'accepted');
    $('#exportPreviewCount').textContent = accepted.length;

    accepted.forEach(item => {
      const fileName = item.path.split('/').pop().split('\\').pop();
      const card = document.createElement('div');
      card.className = 'export-preview-card';
      card.innerHTML = `
        <div class="export-card-score">${(item.score * 100).toFixed(1)}%</div>
        <div class="export-card-name">${fileName}</div>
        <div class="export-card-rank">#${item.rank}</div>
      `;
      grid.appendChild(card);
    });
  }

  function updateExportSummary() {
    const accepted = state.results.filter(r => r.status === 'accepted');
    $('#summaryAccepted').textContent = accepted.length;
    $('#summaryTotal').textContent = state.results.length;
    $('#summaryBest').textContent = accepted.length > 0 ? (accepted[0].score * 100).toFixed(1) + '%' : '—';
  }

  // ZIP экспорт
  $('#btnExportZip').addEventListener('click', async () => {
    if (!state.sessionId) return alert('Сначала выполните анализ');
    try {
      const format = $('#exportFormat').value;
      const quality = parseInt($('#exportQuality').value);
      const includeRejected = $('#exportIncludeRejected').checked;

      const resp = await fetch(`${API_BASE}/api/export/${state.sessionId}/zip`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ format, quality, include_rejected: includeRejected }),
      });

      if (!resp.ok) throw new Error(await resp.text());

      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `youdo_photo_${state.sessionId}.zip`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      alert('Ошибка экспорта: ' + err.message);
    }
  });

  // JSON экспорт
  $('#btnExportJson').addEventListener('click', async () => {
    if (!state.sessionId) return alert('Сначала выполните анализ');
    try {
      const resp = await fetch(`${API_BASE}/api/export/${state.sessionId}/json`);
      if (!resp.ok) throw new Error(await resp.text());
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `results_${state.sessionId}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      alert('Ошибка: ' + err.message);
    }
  });

  // ═══ Утилиты ═══
  function formatSize(bytes) {
    if (bytes < 1024) return bytes + ' Б';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' КБ';
    return (bytes / (1024 * 1024)).toFixed(1) + ' МБ';
  }

  async function apiFetch(path, options = {}) {
    const url = API_BASE + path;
    const controller = new AbortController();
    const timeoutMs = options.timeoutMs || 120000;
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const res = await fetch(url, {
        headers: { 'Content-Type': 'application/json', ...options.headers },
        signal: controller.signal,
        ...options,
      });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `HTTP ${res.status}`);
      }
      return res.json();
    } finally {
      clearTimeout(timer);
    }
  }

  async function uploadFiles(path, files) {
    const formData = new FormData();
    for (const f of files) formData.append('files', f);
    const res = await fetch(API_BASE + path, { method: 'POST', body: formData });
    if (!res.ok) throw new Error(`Upload failed: ${res.status}`);
    return res.json();
  }

  async function uploadVideo(path, files, fps, maxFrames) {
    const formData = new FormData();
    for (const f of files) formData.append('files', f);
    const url = `${API_BASE + path}?fps=${fps}&max_frames=${maxFrames}`;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 300000);
    try {
      const res = await fetch(url, { method: 'POST', body: formData, signal: controller.signal });
      if (!res.ok) throw new Error(`Video upload failed: ${res.status}`);
      return res.json();
    } finally {
      clearTimeout(timer);
    }
  }

})();
