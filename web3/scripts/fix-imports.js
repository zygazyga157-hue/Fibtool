const fs = require('fs');
const path = require('path');

const contractsDir = path.join(__dirname, '../contracts');
const files = fs.readdirSync(contractsDir).filter(f => f.endsWith('.sol'));

console.log('Fixing OpenZeppelin v5 import paths...\n');

files.forEach(file => {
  const filePath = path.join(contractsDir, file);
  let content = fs.readFileSync(filePath, 'utf8');
  let changed = false;

  // Fix security/ imports (moved to utils/ in v5)
  if (content.includes('@openzeppelin/contracts-upgradeable/security/')) {
    content = content.replace(
      /@openzeppelin\/contracts-upgradeable\/security\//g,
      '@openzeppelin/contracts-upgradeable/utils/'
    );
    changed = true;
  }

  if (changed) {
    fs.writeFileSync(filePath, content);
    console.log(`✅ Fixed: ${file}`);
  }
});

console.log('\n✨ Import paths updated for OpenZeppelin v5!');
