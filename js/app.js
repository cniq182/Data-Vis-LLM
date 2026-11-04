/* app.js — UI interactions and state */

const appState = { data: null, fields: [], schema: null };

function goTab(name, el) {
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('on'));
  document.querySelectorAll('.nb').forEach(b => b.classList.remove('on'));
  document.getElementById('tab-' + name).classList.add('on');
  if (el) el.classList.add('on');
}

function showMsg(id, msg, type) {
  const el = document.getElementById(id);
  if (!el) return;
  el.textContent = msg;
  el.className = 'ib' + (type === 'success' ? ' success' : ' warn');
  el.style.display = 'block';
}

function hideMsg(id) {
  const el = document.getElementById(id);
  if (el) el.style.display = 'none';
}

function renderSchemaCard(schema) {
  const typeColor = { quantitative: 'var(--prot)', temporal: 'var(--carb)', nominal: 'var(--text-c)' };
  const typeLabel = { quantitative: 'QT', temporal: 'TM', nominal: 'NM' };

  let html = '<div class="sch-grid">';
  for (const col of schema.columns) {
    const extra = col.n_missing > 0 ? ` · ${col.n_missing} missing` : '';
    html += `<div class="sch-col">
      <span class="sch-type" style="color:${typeColor[col.vl_type]}">${typeLabel[col.vl_type]}</span>
      <span class="sch-name">${col.name}</span>
      <span class="sch-stat">${col.n_unique.toLocaleString()} unique${extra}</span>
    </div>`;
  }
  html += '</div>';
  html += `<div class="ib" style="margin-top:.6rem;font-size:10.5px">
    <span style="color:var(--prot)">QT</span> quantitative &nbsp;·&nbsp;
    <span style="color:var(--carb)">TM</span> temporal &nbsp;·&nbsp;
    <span style="color:var(--text-c)">NM</span> nominal
  </div>`;

  document.getElementById('schema-content').innerHTML = html;
  document.getElementById('schema-card').style.display = 'block';
}

function processFile(file) {
  if (!file.name.toLowerCase().endsWith('.csv')) {
    showMsg('upload-error', 'Please select a CSV file.');
    return;
  }
  const reader = new FileReader();
  reader.onload = e => {
    hideMsg('upload-error');
    try {
      const { data, fields } = loadCSV(e.target.result);
      appState.data = data;
      appState.fields = fields;
      appState.schema = extractSchema(data, fields);

      const box = document.getElementById('upload-box');
      box.classList.add('loaded');
      document.getElementById('upload-ok').textContent =
        `✓ ${file.name} — ${appState.schema.n_rows.toLocaleString()} rows, ${fields.length} columns`;

      const badge = document.getElementById('data-badge');
      badge.textContent = `${appState.schema.n_rows.toLocaleString()} rows · ${fields.length} cols`;
      badge.classList.add('loaded');

      renderSchemaCard(appState.schema);
      document.getElementById('render-btn').disabled = false;
    } catch (err) {
      showMsg('upload-error', err.message);
    }
  };
  reader.onerror = () => showMsg('upload-error', 'Could not read the file.');
  reader.readAsText(file);
}

// File input change
document.getElementById('csv-file').addEventListener('change', e => {
  const file = e.target.files[0];
  if (file) processFile(file);
});

// Drag and drop
const uploadBox = document.getElementById('upload-box');
uploadBox.addEventListener('dragover',  e => { e.preventDefault(); uploadBox.classList.add('drag'); });
uploadBox.addEventListener('dragleave', ()  => uploadBox.classList.remove('drag'));
uploadBox.addEventListener('drop', e => {
  e.preventDefault();
  uploadBox.classList.remove('drag');
  const file = e.dataTransfer.files[0];
  if (file) processFile(file);
});

// Render button
document.getElementById('render-btn').addEventListener('click', async () => {
  hideMsg('chart-error');
  document.getElementById('chart-summary').textContent = '';

  if (!appState.data) {
    showMsg('chart-error', 'No data loaded. Upload a CSV first.');
    return;
  }

  try {
    const parsed = parseSpec(document.getElementById('spec-editor').value);
    const clean  = sanitizeSpec(parsed);
    checkFields(clean, appState.schema.column_names);
    document.getElementById('chart-summary').textContent = summarize(clean);
    await renderChart(appState.data, clean);
  } catch (err) {
    showMsg('chart-error', err.message);
    document.getElementById('chart-card').style.display = 'none';
  }
});
