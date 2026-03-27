const fs = require('fs');
const path = require('path');

// Ensure dist directory exists
if (!fs.existsSync('dist')) {
  fs.mkdirSync('dist');
}

// Copy index.html to dist
const html = `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Amazon PPC Optimizer</title>
</head>
<body>
    <h1>Amazon PPC Optimizer - Active</h1>
    <p>Status: Operational</p>
</body>
</html>`;

fs.writeFileSync(path.join('dist', 'index.html'), html);
console.log('Build complete - dist/index.html created');
