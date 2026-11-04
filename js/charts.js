/* charts.js — spec parsing, validation, and Vega-Lite rendering (mirrors render/spec.py) */

function parseSpec(text) {
  // tolerate ``` fences from LLM output
  const cleaned = text.trim()
    .replace(/^```(?:json)?\s*/m, '')
    .replace(/\s*```\s*$/m, '');
  let spec;
  try { spec = JSON.parse(cleaned); }
  catch (e) { throw new Error('Not valid JSON: ' + e.message); }
  if (typeof spec !== 'object' || Array.isArray(spec) || spec === null)
    throw new Error('The top-level JSON value must be an object.');
  return spec;
}

function sanitizeSpec(node) {
  if (Array.isArray(node)) return node.map(sanitizeSpec);
  if (node && typeof node === 'object') {
    const out = {};
    for (const [k, v] of Object.entries(node))
      if (k !== 'data' && k !== 'datasets') out[k] = sanitizeSpec(v);
    return out;
  }
  return node;
}

function _collectFields(node, used, derived) {
  if (Array.isArray(node)) { node.forEach(n => _collectFields(n, used, derived)); return; }
  if (node && typeof node === 'object') {
    for (const [k, v] of Object.entries(node)) {
      if (k === 'field' && typeof v === 'string') used.add(v);
      else if ((k === 'groupby' || k === 'fold') && Array.isArray(v))
        v.forEach(x => typeof x === 'string' && used.add(x));
      else if (k === 'as')
        (Array.isArray(v) ? v : [v]).forEach(x => typeof x === 'string' && derived.add(x));
      _collectFields(v, used, derived);
    }
  }
}

function checkFields(spec, columnNames) {
  const used = new Set(), derived = new Set();
  _collectFields(spec, used, derived);
  const unknown = [...used].filter(f => !columnNames.has(f) && !derived.has(f)).sort();
  if (unknown.length > 0)
    throw new Error(
      `Unknown field(s): [${unknown.join(', ')}]. ` +
      `Available columns: [${[...columnNames].sort().join(', ')}].`
    );
}

function summarize(spec) {
  const mark = spec.mark;
  const markName = typeof mark === 'object' ? mark.type : mark;
  const parts = [];
  for (const [ch, enc] of Object.entries(spec.encoding || {})) {
    if (typeof enc !== 'object' || enc === null) continue;
    let field = enc.field || '';
    if (enc.aggregate) field = `${enc.aggregate}(${field})`;
    if (enc.timeUnit)  field = `${enc.timeUnit}(${field})`;
    if (enc.bin)       field = `bin(${field})`;
    if (field) parts.push(`${ch} = ${field}`);
  }
  let text = `${markName || 'layered'} chart`;
  if (parts.length) text += ': ' + parts.join(', ');
  return text;
}

const DARK_CONFIG = {
  background: 'transparent',
  axis: {
    domainColor: '#2a2a40', gridColor: '#1a1a28',
    labelColor: '#b0b0cc', titleColor: '#b0b0cc', tickColor: '#2a2a40',
  },
  legend: { labelColor: '#b0b0cc', titleColor: '#b0b0cc' },
  title:  { color: '#e2e2f0', subtitleColor: '#b0b0cc' },
  view:   { stroke: 'transparent' },
  style:  { 'guide-label': { fill: '#b0b0cc' }, 'guide-title': { fill: '#b0b0cc' } },
};

let _embedView = null;

async function renderChart(data, spec) {
  const container = document.getElementById('chart-container');
  container.innerHTML = '';
  document.getElementById('chart-card').style.display = 'block';

  const { config: userConfig, ...rest } = spec;
  const fullSpec = {
    ...rest,
    data: { values: data },
    config: { ...DARK_CONFIG, ...(userConfig || {}) },
  };

  try {
    if (_embedView) { _embedView.finalize(); _embedView = null; }
    const result = await vegaEmbed(container, fullSpec, {
      actions: { export: true, source: false, compiled: false, editor: false },
      renderer: 'canvas',
    });
    _embedView = result.view;
  } catch (e) {
    throw new Error('Render error: ' + (e.message || String(e)));
  }
}
