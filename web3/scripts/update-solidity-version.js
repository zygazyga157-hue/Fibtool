const fs = require('fs');
const path = require('path');

const contractsDir = path.join(__dirname, '../contracts');
const files = fs.readdirSync(contractsDir).filter(f => f.endsWith('.sol'));

console.log('Updating Solidity version to 0.8.24...\n');

files.forEach(file => {
  const filePath = path.join(contractsDir, file);
  let content = fs.readFileSync(filePath, 'utf8');
  
  if (content.includes('pragma solidity ^0.8.20')) {
    content = content.replace(/pragma solidity \^0\.8\.20/g, 'pragma solidity ^0.8.24');
    fs.writeFileSync(filePath, content);
    console.log(`✅ Updated: ${file}`);
  }
});

console.log('\n✨ All contracts updated to Solidity 0.8.24!');
