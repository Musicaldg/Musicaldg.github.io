const fs = require('fs');
const katex = require('../assets/vendor/katex/katex.min.js');
const equations = JSON.parse(fs.readFileSync(0, 'utf8'));
for (const equation of equations) {
  katex.renderToString(equation.tex, {
    displayMode: equation.displayMode,
    throwOnError: true,
    strict: 'error',
    trust: false
  });
}
console.log(`${equations.length} 个公式渲染通过。`);
