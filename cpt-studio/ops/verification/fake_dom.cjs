'use strict';
// A small DOM for the walk's in-page readers (ops/verify_browser.cjs readCustomerDom), so the unit suite runs the same
// functions the walk runs in Chromium over markup written to the DOM contract (CORE-UX-DESIGN 8). It parses the HTML the
// samples and the tests write (no scripts, no entities beyond the five HTML escapes and numeric ones) and answers
// querySelector(All) and closest for the selectors the readers use: tag, #id, .class, [attr], [attr="value"],
// descendant and child (>) combinators, and comma lists. Anything else throws, so a reader can never silently match
// nothing because this DOM did not understand it.

const VOID = new Set(['area', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'source', 'track', 'wbr']);

function decode(text) {
  return text.replace(/&#x([0-9a-f]+);/gi, (_, hex) => String.fromCodePoint(parseInt(hex, 16)))
    .replace(/&#(\d+);/g, (_, dec) => String.fromCodePoint(Number(dec)))
    .replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&#x27;/g, "'").replace(/&amp;/g, '&');
}

class Node {
  constructor(tag, attrs, parent) {
    this.tag = tag;
    this.attrs = attrs;
    this.parentNode = parent;
    this.childNodes = [];
  }

  get tagName() { return this.tag.toUpperCase(); }

  get id() { return this.attrs.id || ''; }

  get className() { return this.attrs.class || ''; }

  get parentElement() { return this.parentNode && this.parentNode.tag !== '#root' ? this.parentNode : null; }

  get children() { return this.childNodes.filter(child => child instanceof Node); }

  get textContent() {
    return this.childNodes.map(child => (child instanceof Node ? child.textContent : child.text)).join('');
  }

  get value() {
    if (this.tag === 'textarea') return this.attrs.value ?? this.textContent;
    if (this.tag === 'select') {
      const options = this.querySelectorAll('option');
      const chosen = options.find(option => option.hasAttribute('selected')) || options[0];
      return chosen ? chosen.getAttribute('value') ?? chosen.textContent : '';
    }
    return this.attrs.value ?? '';
  }

  get checked() { return this.hasAttribute('checked'); }

  get disabled() { return this.hasAttribute('disabled'); }

  get open() { return this.hasAttribute('open'); }

  getAttribute(name) { return Object.prototype.hasOwnProperty.call(this.attrs, name) ? this.attrs[name] : null; }

  hasAttribute(name) { return Object.prototype.hasOwnProperty.call(this.attrs, name); }

  * descendants() {
    for (const child of this.children) {
      yield child;
      yield* child.descendants();
    }
  }

  querySelectorAll(selector) {
    const groups = parseSelector(selector);
    return [...this.descendants()].filter(node => groups.some(group => matchesGroup(node, group)));
  }

  querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }

  matches(selector) { return parseSelector(selector).some(group => matchesGroup(this, group)); }

  closest(selector) {
    for (let node = this; node && node.tag !== '#root'; node = node.parentNode) if (node.matches(selector)) return node;
    return null;
  }

  contains(other) {
    for (let node = other; node; node = node.parentNode) if (node === this) return true;
    return false;
  }
}

// One compound selector: {tag, id, classes, attrs: [[name, value|undefined]]}.
function parseCompound(text) {
  const compound = { tag: null, id: null, classes: [], attrs: [] };
  let rest = text;
  const tag = /^[a-z][a-z0-9-]*/i.exec(rest);
  if (tag) {
    compound.tag = tag[0].toLowerCase();
    rest = rest.slice(tag[0].length);
  }
  while (rest) {
    let m;
    if ((m = /^#([\w-]+)/.exec(rest))) compound.id = m[1];
    else if ((m = /^\.([\w-]+)/.exec(rest))) compound.classes.push(m[1]);
    else if ((m = /^\[([\w-]+)(?:="((?:[^"\\]|\\.)*)")?\]/.exec(rest))) compound.attrs.push([m[1], m[2] === undefined ? undefined : m[2].replace(/\\(.)/g, '$1')]);
    else throw new Error(`fake_dom does not understand the selector part ${JSON.stringify(rest)} in ${JSON.stringify(text)}`);
    rest = rest.slice(m[0].length);
  }
  return compound;
}

// A selector list: each group a list of [combinator, compound] read right to left.
function parseSelector(selector) {
  return selector.split(',').map(group => {
    const tokens = group.trim().replace(/\s*>\s*/g, ' > ').split(/\s+/).filter(Boolean);
    const steps = [];
    let combinator = ' ';
    for (const token of tokens) {
      if (token === '>') {
        combinator = '>';
        continue;
      }
      steps.push([combinator, parseCompound(token)]);
      combinator = ' ';
    }
    if (!steps.length) throw new Error(`fake_dom: empty selector ${JSON.stringify(selector)}`);
    return steps;
  });
}

function matchesCompound(node, compound) {
  if (!(node instanceof Node) || node.tag === '#root') return false;
  if (compound.tag && node.tag !== compound.tag) return false;
  if (compound.id && node.attrs.id !== compound.id) return false;
  const classes = (node.attrs.class || '').split(/\s+/);
  if (compound.classes.some(name => !classes.includes(name))) return false;
  return compound.attrs.every(([name, value]) => node.hasAttribute(name) && (value === undefined || node.attrs[name] === value));
}

function matchesGroup(node, steps, index = steps.length - 1) {
  const [combinator, compound] = steps[index];
  if (!matchesCompound(node, compound)) return false;
  if (index === 0) return true;
  if (combinator === '>') return Boolean(node.parentNode) && matchesGroup(node.parentNode, steps, index - 1);
  for (let up = node.parentNode; up; up = up.parentNode) if (matchesGroup(up, steps, index - 1)) return true;
  return false;
}

function parseHtml(html) {
  const root = new Node('#root', {}, null);
  let node = root;
  const token = /<!--[\s\S]*?-->|<!doctype[^>]*>|<(\/?)([a-zA-Z][a-zA-Z0-9-]*)((?:\s+[^\s=>/]+(?:\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]+))?)*)\s*(\/?)>|([^<]+)/gi;
  for (const m of html.matchAll(token)) {
    if (m[5] !== undefined) {
      node.childNodes.push({ text: decode(m[5]) });
      continue;
    }
    if (!m[2]) continue;
    const tag = m[2].toLowerCase();
    if (m[1]) {
      let open = node;
      while (open && open.tag !== tag) open = open.parentNode;
      if (open && open.parentNode) node = open.parentNode;
      continue;
    }
    const attrs = {};
    for (const a of m[3].matchAll(/([^\s=]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+)))?/g)) attrs[a[1].toLowerCase()] = decode(a[2] ?? a[3] ?? a[4] ?? '');
    const element = new Node(tag, attrs, node);
    node.childNodes.push(element);
    if (!VOID.has(tag) && !m[4]) node = element;
  }
  return root;
}

// A document over the markup: querySelector(All) from the root, title, documentElement and body.
function fakeDocument(html) {
  const root = parseHtml(html);
  const doc = {
    root, querySelector: selector => root.querySelector(selector), querySelectorAll: selector => root.querySelectorAll(selector),
    get documentElement() { return root.children[0] || root; },
    get body() { return root.querySelector('body'); },
    get title() { return root.querySelector('title')?.textContent || ''; },
  };
  return doc;
}

module.exports = { fakeDocument, parseHtml, parseSelector, Node };
