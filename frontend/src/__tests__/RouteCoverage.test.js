import fs from 'fs';
import path from 'path';
const parser = require('@babel/parser');
const traverse = require('@babel/traverse').default;

const source = fs.readFileSync(path.join(__dirname, '../App.js'), 'utf8');
const ast = parser.parse(source, { sourceType: 'module', plugins: ['jsx'] });

const pages = new Map();
for (const node of ast.program.body) {
  if (node.type === 'ImportDeclaration' && node.source.value.startsWith('./pages/')) {
    for (const specifier of node.specifiers) {
      pages.set(specifier.local.name, node.source.value);
    }
  }
}

const paths = [];
const attribute = (node, name) => node.openingElement.attributes.find(a => a.name?.name === name)?.value;
traverse(ast, { JSXElement(p) {
  if (p.node.openingElement.name.name !== 'Route') return;
  const element = attribute(p.node, 'element')?.expression;
  const pageElement = element?.openingElement?.name?.name === 'ProtectedRoute'
    ? element.children.find(child => child.type === 'JSXElement') : element;
  const name = pageElement?.openingElement?.name?.name;
  if (!pages.has(name)) return;
  const routePath = attribute(p.node, 'path')?.value;
  const parent = p.findParent(q => q.isJSXElement() && q.node.openingElement.name.name === 'Route');
  const prefix = parent ? attribute(parent.node, 'path').value.replace(/\/\*$/, '/') : '';
  paths.push([prefix + routePath, name]);
} });

test('every page file has a concrete route element', () => {
  const root = path.join(__dirname, '../pages');
  const files = fs.readdirSync(root).flatMap(group =>
    fs.readdirSync(path.join(root, group))
      .filter(file => file.endsWith('.jsx'))
      .map(file => `./pages/${group}/${file.slice(0, -4)}`)
  );
  const routed = paths.map(([, name]) => pages.get(name));
  const nested = ['./pages/platform/PlatformMFA'];
  expect(fs.readFileSync(path.join(root, 'public/Login.jsx'), 'utf8')).toContain('PlatformMFA');
  expect(files.filter(file => !routed.includes(file) && !nested.includes(file))).toEqual([]);
});

test('every declared route points at an imported page', () => {
  expect(paths.length).toBeGreaterThan(20);
  expect(paths.filter(([, name]) => !pages.has(name))).toEqual([]);
});

test('every portal navigation link resolves to an explicit route', () => {
  const { ROLE_LINKS } = require('../components/common/PortalNavigation');
  const known = new Set([...paths.map(([url]) => url), '/superadmin/dashboard']);
  expect(Object.values(ROLE_LINKS).flat().map(([url]) => url).filter(url => !known.has(url))).toEqual([]);
});

test('superadmins have a dashboard route', () => {
  expect(paths).toContainEqual(['/superadmin/dashboard', 'PlatformDashboard']);
});
