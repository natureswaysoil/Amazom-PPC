const fs = require('fs');
const path = require('path');

const distDir = process.env.DIST_DIR || '/app/dist';

const candidates = [
  'config-validator.js',
  'config-validator.cjs',
  'config-validator.mjs',
];

function patchFile(filePath) {
  const needle = 'Config not validated yet. Call validateConfig() first.';
  let content = fs.readFileSync(filePath, 'utf8');

  if (!content.includes(needle)) return false;

  const before = content;

  // Replace the hard-fail throw with a lazy validation call.
  // Handle common quote styles.
  content = content
    .replace(
      /throw\s+new\s+Error\(\"Config not validated yet\. Call validateConfig\(\) first\.\"\);/g,
      'validateConfig();'
    )
    .replace(
      /throw\s+new\s+Error\(\'Config not validated yet\. Call validateConfig\(\) first\.\'\);/g,
      'validateConfig();'
    )
    .replace(
      /throw\s+new\s+Error\(`Config not validated yet\. Call validateConfig\(\) first\.`\);/g,
      'validateConfig();'
    );

  if (content === before) {
    // Pattern drifted; don’t risk mangling the bundle.
    return false;
  }

  fs.writeFileSync(filePath, content, 'utf8');
  return true;
}

function main() {
  if (!fs.existsSync(distDir) || !fs.statSync(distDir).isDirectory()) {
    console.log(`No dist dir at ${distDir}; skipping config-validator patch.`);
    return;
  }

  let patched = 0;

  for (const fileName of candidates) {
    const filePath = path.join(distDir, fileName);
    if (!fs.existsSync(filePath)) continue;
    if (patchFile(filePath)) patched += 1;
  }

  if (patched > 0) {
    console.log(`Applied config-validator lazy validation patch to ${patched} file(s).`);
  } else {
    console.log('No config-validator patch applied (pattern not found or files missing).');
  }
}

main();
