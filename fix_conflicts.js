const fs = require('fs');
const path = require('path');

function walk(dir) {
    let results = [];
    const list = fs.readdirSync(dir);
    list.forEach(function(file) {
        file = path.resolve(dir, file);
        const stat = fs.statSync(file);
        if (stat && stat.isDirectory()) {
            if (!file.includes('.git') && !file.includes('node_modules')) {
                results = results.concat(walk(file));
            }
        } else {
            results.push(file);
        }
    });
    return results;
}

const files = walk('.');
let fixedCount = 0;

for (const file of files) {
    try {
        const content = fs.readFileSync(file, 'utf8');
        if (content.includes('<<<<<<< HEAD')) {
            const lines = content.split(/\r?\n/);
            const newLines = [];
            let inHead = false;
            let inOther = false;
            
            for (let i = 0; i < lines.length; i++) {
                const line = lines[i];
                if (line.startsWith('<<<<<<< HEAD')) {
                    inHead = true;
                    continue;
                }
                if (line.startsWith('=======')) {
                    inHead = false;
                    inOther = true;
                    continue;
                }
                if (line.startsWith('>>>>>>> ')) {
                    inOther = false;
                    continue;
                }
                
                if (!inOther) {
                    newLines.push(line);
                }
            }
            
            const newContent = newLines.join('\n');
            fs.writeFileSync(file, newContent, 'utf8');
            console.log('Fixed ' + file);
            fixedCount++;
        }
    } catch (e) {
    }
}
console.log('Total fixed: ' + fixedCount);
