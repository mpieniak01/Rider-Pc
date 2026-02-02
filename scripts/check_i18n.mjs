import fs from 'fs';
import path from 'path';

const filePath = path.join(process.cwd(), 'web/assets/i18n.js');
const source = fs.readFileSync(filePath, 'utf8');
const marker = 'export const I18N =';
const startIdx = source.indexOf(marker);
if (startIdx === -1) {
  throw new Error('Could not find I18N definition');
}
const braceStart = source.indexOf('{', startIdx);
if (braceStart === -1) throw new Error('Malformed I18N object');

let depth = 0;
let inSingle = false;
let inDouble = false;
let inTemplate = false;
let escape = false;
let endIdx = -1;
for (let i = braceStart; i < source.length; i += 1) {
  const ch = source[i];
  if (escape) {
    escape = false;
    continue;
  }
  if (ch === '\\') {
    escape = true;
    continue;
  }
  if (inSingle) {
    if (ch === "'") inSingle = false;
    continue;
  }
  if (inDouble) {
    if (ch === '"') inDouble = false;
    continue;
  }
  if (inTemplate) {
    if (ch === '`') inTemplate = false;
    continue;
  }
  if (ch === "'") {
    inSingle = true;
    continue;
  }
  if (ch === '"') {
    inDouble = true;
    continue;
  }
  if (ch === '`') {
    inTemplate = true;
    continue;
  }
  if (ch === '{') depth += 1;
  if (ch === '}') {
    depth -= 1;
    if (depth === 0) {
      endIdx = i;
      break;
    }
  }
}

if (endIdx < 0) throw new Error('Could not determine end of I18N object');
const objectLiteral = source.slice(braceStart, endIdx + 1);

const I18N = (new Function(`return (${objectLiteral});`))();
const missing = [];

function checkNode(node, path = []) {
  if (typeof node !== 'object' || node === null) return;
  const hasLang = 'pl' in node || 'en' in node;
  if (hasLang) {
    if (typeof node.en !== 'string' || !node.en.trim()) {
      missing.push(`${path.join('.') || 'root'} (missing en)`);
    }
    return;
  }
  for (const [key, value] of Object.entries(node)) {
    checkNode(value, [...path, key]);
  }
}

checkNode(I18N);

if (missing.length) {
  console.error('Missing English translations for keys:');
  missing.forEach((key) => console.error(`  • ${key}`));
  process.exitCode = 1;
} else {
  console.log('check_i18n: all keys have English translations.');
}
