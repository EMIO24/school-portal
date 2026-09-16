// Resolve frontend request paths statically, including conditional endpoint names.
const fs = require('fs');
const path = require('path');
const parser = require('@babel/parser');
const traverse = require('@babel/traverse').default;
const root = path.resolve(__dirname, '../src');
const candidates = [];
const unknown = [];
function values(node, scope, depth = 0) {
  if (!node || depth > 12) return null;
  if (node.type === 'StringLiteral' || node.type === 'NumericLiteral') return [String(node.value)];
  if (node.type === 'ConditionalExpression') {
    const a = values(node.consequent, scope, depth + 1), b = values(node.alternate, scope, depth + 1);
    return a && b ? [...a, ...b] : null;
  }
  if (node.type === 'BinaryExpression' && node.operator === '+') {
    const left = values(node.left, scope, depth + 1), right = values(node.right, scope, depth + 1);
    return left && right ? left.flatMap(a => right.map(b => a + b)) : null;
  }
  if (node.type === 'NewExpression' && node.callee?.name === 'URLSearchParams') return [''];
  if (node.type === 'CallExpression' && node.callee?.type === 'MemberExpression') {
    const prop = node.callee.property;
    if (['toString', 'trim'].includes(prop?.name)) return values(node.callee.object, scope, depth + 1);
    if (prop?.name === 'get') return ['1'];
  }
  if (node.type === 'MemberExpression') {
    const property = node.property;
    if (!node.computed && ['id', 'pk', 'reference'].includes(property?.name)) return ['1'];
    return values(node.object, scope, depth + 1) || ['1'];
  }
  if (node.type === 'Identifier') {
    const binding = scope.getBinding(node.name);
    if (binding?.path.node.type === 'VariableDeclarator') {
      const resolved = values(binding.path.node.init, binding.path.scope, depth + 1);
      if (resolved) return resolved;
      if (/^(term|schoolId|page|search|status|plan|params|reference|id)$/.test(node.name)) return ['1'];
      return null;
    }
    if (binding?.kind === 'param') {
      const fn = binding.path.getFunctionParent();
      const parent = fn?.parentPath;
      const paramIndex = fn?.node.params.findIndex(param => param === binding.path.node);
      const callee = parent?.node?.callee;
      if (paramIndex === 0 && parent?.node?.type === 'CallExpression' && callee?.type === 'MemberExpression' && callee.property?.name === 'map') {
        const mapped = values(callee.object, parent.scope, depth + 1);
        if (mapped) return mapped;
      }
    }
    if (/^(term|schoolId|page|search|status|plan|params|reference|id)$/.test(node.name)) return ['1'];
    return null;
  }
  if (node.type === 'ArrayExpression') {
    const out = [];
    for (const element of node.elements) {
      const elementValues = values(element, scope, depth + 1);
      if (!elementValues) return null;
      out.push(...elementValues);
    }
    return out;
  }
  if (node.type === 'TemplateLiteral') {
    let result = [node.quasis[0].value.cooked];
    node.expressions.forEach((expr, i) => {
      // Origin environment variables do not form part of the backend path.
      const origin = i === 0 && !node.quasis[0].value.cooked && node.quasis[1].value.cooked.startsWith('/api/');
      const substitutions = origin ? [''] : values(expr, scope, depth + 1) || ['1'];
      result = result.flatMap(prefix => substitutions.map(v => prefix + v + node.quasis[i + 1].value.cooked));
    });
    return result;
  }
  return null;
}
function scan(dir) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (['__tests__', 'testSupport'].includes(entry.name)) continue;
    const file = path.join(dir, entry.name);
    if (entry.isDirectory()) { scan(file); continue; }
    if (!/\.jsx?$/.test(file) || /(?:setupTests|jest.setup|serviceWorker)\.js$/.test(file)) continue;
    const relative = path.relative(root, file).replaceAll('\\', '/');
    const ast = parser.parse(fs.readFileSync(file, 'utf8'), { sourceType: 'module', plugins: ['jsx'] });
    traverse(ast, {
      CallExpression(p) {
        const { callee, arguments: args } = p.node;
        let method;
        if (callee.type === 'MemberExpression' && ['api', 'axios'].includes(callee.object.name)
            && ['get', 'post', 'patch', 'put', 'delete'].includes(callee.property.name)) method = callee.property.name.toUpperCase();
        if (callee.type === 'Identifier' && callee.name === 'fetch') {
          method = args[1]?.properties?.find(prop => prop.key?.name === 'method')?.value?.value || 'GET';
        }
        if (callee.type === 'Identifier' && callee.name === 'downloadFile') method = 'GET';
        if (!method) return;
        if (relative === 'services/download.js' && args[0]?.name === 'url') return; // Enumerated at downloadFile call sites.
        let urls = values(args[0], p.scope);
        // The importer is configured by these two explicit endpoints in BulkImportPage.
        if (!urls && relative === 'components/admin/BulkImport.jsx' && args[0]?.name === 'endpoint') {
          const config = parser.parse(fs.readFileSync(path.join(root, 'pages/admin/BulkImportPage.jsx'), 'utf8'), { sourceType: 'module', plugins: ['jsx'] });
          urls = [];
          traverse(config, { ObjectProperty(q) { if (q.node.key.name === 'endpoint') urls.push(q.node.value.value); } });
        }
        if (!urls && relative === 'pages/payments/Payments.jsx' && args[0]?.name === 'url') {
          urls = ['/api/platform/payments/', '/api/platform/schools/1/payments/'];
        }
        if (!urls) { unknown.push(`${relative}:${p.node.loc.start.line}`); return; }
        for (const url of [...new Set(urls)]) {
          if (/^https?:/.test(url)) continue; // External Cloudinary upload.
          candidates.push({ file: relative, line: p.node.loc.start.line, method, path: url.split('?')[0] });
        }
      },
    });
  }
}
scan(root);
if (unknown.length) { console.error('Unresolved API expressions: ' + unknown.join(', ')); process.exitCode = 1; }
process.stdout.write(JSON.stringify(candidates));
