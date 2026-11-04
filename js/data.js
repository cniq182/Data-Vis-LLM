/* data.js — CSV parsing and schema extraction (mirrors data/loader.py) */

function cleanColumnName(name, seen) {
  let cleaned = String(name).replace(/[.\[\]\\]/g, '_').trim();
  if (!cleaned) cleaned = 'column';
  if (seen.has(cleaned)) {
    let i = 1;
    while (seen.has(`${cleaned}_${i}`)) i++;
    cleaned = `${cleaned}_${i}`;
  }
  seen.add(cleaned);
  return cleaned;
}

function inferVLType(values) {
  const nonNull = values.filter(v => v !== null && v !== undefined && v !== '');
  if (nonNull.length === 0) return 'nominal';
  const threshold = 0.9;

  const numCount = nonNull.filter(v => v !== '' && !isNaN(+v) && isFinite(+v)).length;
  if (numCount / nonNull.length >= threshold) return 'quantitative';

  // require at least 6 chars to avoid false positives on short strings like "10" or "yes"
  const dateCount = nonNull.filter(v => {
    if (String(v).length < 6) return false;
    const d = new Date(v);
    return !isNaN(d.getTime());
  }).length;
  if (dateCount / nonNull.length >= threshold) return 'temporal';

  return 'nominal';
}

function loadCSV(text) {
  const result = Papa.parse(text.trim(), {
    header: true,
    skipEmptyLines: true,
    dynamicTyping: false,
  });

  if (result.data.length === 0) throw new Error('The CSV has no rows.');
  if (!result.meta.fields || result.meta.fields.length === 0) throw new Error('The CSV has no columns.');

  const seen = new Set();
  const origFields = result.meta.fields;
  const fieldMap = {};
  const cleanFields = origFields.map(f => {
    const c = cleanColumnName(f, seen);
    fieldMap[f] = c;
    return c;
  });

  const data = result.data.map(row => {
    const out = {};
    for (const orig of origFields) out[fieldMap[orig]] = row[orig] ?? '';
    return out;
  });

  return { data, fields: cleanFields };
}

function extractSchema(data, fields) {
  const columns = fields.map(field => {
    const values = data.map(r => r[field]);
    const nonNull = values.filter(v => v !== null && v !== undefined && v !== '');
    return {
      name: field,
      vl_type: inferVLType(nonNull),
      n_unique: new Set(nonNull).size,
      n_missing: values.length - nonNull.length,
    };
  });

  const sample = data.slice(0, 3).map(row => {
    const r = {};
    for (const f of fields) {
      const v = row[f];
      r[f] = typeof v === 'string' && v.length > 40 ? v.slice(0, 40) + '...' : v;
    }
    return r;
  });

  return {
    n_rows: data.length,
    columns,
    column_names: new Set(fields),
    sample,
  };
}
