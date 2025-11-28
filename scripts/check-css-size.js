#!/usr/bin/env node
/**
 * CSS Size Checker - Rider-PC Dashboard
 * Validates that page-specific CSS files stay under the 150 line limit.
 * ------------------------------------------------------------------
 */

const fs = require('fs');
const path = require('path');

const MAX_LINES = 150;
const CSS_DIR = path.join(__dirname, '..', 'web', 'assets');
const PAGES_DIR = path.join(CSS_DIR, 'pages');

function getPageCssFiles() {
  try {
    return fs.readdirSync(PAGES_DIR)
      .filter((file) => file.endsWith('.css'))
      .sort();
  } catch (err) {
    console.error('Nie udało się odczytać katalogu pages/:', err.message);
    return [];
  }
}

// Files that are shared components (allowed to be larger)
const SHARED_FILES = [
  'dashboard-common.css',
  'css/tokens.css',
  'css/base.css',
  'css/layout.css',
  'css/components.css',
  'css/utilities.css',
  'css/menu.css',
  'css/footer.css'
];

function countLines(filePath) {
  try {
    const content = fs.readFileSync(filePath, 'utf-8');
    // Count non-empty, non-comment lines
    const lines = content.split('\n');
    let count = 0;
    let inBlockComment = false;
    
    for (const line of lines) {
      const trimmed = line.trim();
      
      // Skip empty lines
      if (!trimmed) continue;
      
      // Handle block comments
      if (trimmed.startsWith('/*')) {
        inBlockComment = true;
        if (trimmed.includes('*/')) {
          inBlockComment = false;
        }
        continue;
      }
      
      if (inBlockComment) {
        if (trimmed.includes('*/')) {
          inBlockComment = false;
        }
        continue;
      }
      
      count++;
    }
    
    return { total: lines.length, code: count };
  } catch (err) {
    return null;
  }
}

function logPageFile(file, result) {
  const status = result.code <= MAX_LINES ? '✓' : '✗';
  const color = result.code <= MAX_LINES ? '\x1b[32m' : '\x1b[31m';
  const reset = '\x1b[0m';
  console.log(`  ${color}${status}${reset} ${file}: ${result.code} lines (${result.total} total)`);
}

function main() {
  console.log('CSS Size Report - Rider-PC Dashboard');
  console.log('=====================================\n');

  let hasErrors = false;

  console.log('Page-specific CSS files (max ' + MAX_LINES + ' lines):');
  console.log('-'.repeat(50));

  const pageFiles = getPageCssFiles();
  if (!pageFiles.length) {
    console.log('  (brak plików w web/assets/pages)');
  }

  for (const file of pageFiles) {
    const filePath = path.join(PAGES_DIR, file);
    const result = countLines(filePath);

    if (!result) {
      console.log(`  ${file}: NOT FOUND`);
      continue;
    }

    logPageFile(file, result);

    if (result.code > MAX_LINES) {
      hasErrors = true;
    }
  }
  
  console.log('\nShared CSS files:');
  console.log('-'.repeat(50));
  
  for (const file of SHARED_FILES) {
    const filePath = path.join(CSS_DIR, file);
    const result = countLines(filePath);
    
    if (!result) {
      console.log(`  ${file}: NOT FOUND`);
      continue;
    }
    
    console.log(`  ○ ${file}: ${result.code} lines (${result.total} total)`);
  }
  
  console.log('\n');
  
  if (hasErrors) {
    console.log('\x1b[31mERROR: Some page-specific CSS files exceed ' + MAX_LINES + ' lines!\x1b[0m');
    console.log('Please refactor to use shared components from dashboard-common.css');
    process.exit(1);
  } else {
    console.log('\x1b[32mAll page-specific CSS files are within limits.\x1b[0m');
    process.exit(0);
  }
}

main();
