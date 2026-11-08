'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');

const root = path.join(__dirname, '..');
test('extension manifests and grammar are valid', () => {
  for (const file of ['package.json', 'language-configuration.json', 'syntaxes/sonqelra.tmLanguage.json']) {
    assert.doesNotThrow(() => JSON.parse(fs.readFileSync(path.join(root, file), 'utf8')));
  }
  const manifest = require('../package.json');
  assert.deepEqual(manifest.contributes.languages[0].extensions, ['.sonqelra']);
  const matcher = new RegExp(manifest.contributes.problemMatchers[0].pattern.regexp);
  assert.deepEqual(matcher.exec('/tmp/my score.sonqelra:12:3: bad note').slice(1), ['/tmp/my score.sonqelra', '12', '3', 'bad note']);
  assert.deepEqual(matcher.exec('C:\\music\\song.sonqelra:12:3: bad note').slice(1), ['C:\\music\\song.sonqelra', '12', '3', 'bad note']);
});

test('compile saves and passes the filename as a process argument', async () => {
  let command, task, saved = false;
  const document = { languageId: 'sonqelra', isUntitled: false, isDirty: true, uri: { scheme: 'file', fsPath: '/tmp/a score.sonqelra' }, fileName: '/tmp/a score.sonqelra', save: async () => { saved = true; return true; } };
  const vscode = {
    languages: { registerCompletionItemProvider: () => ({}), registerHoverProvider: () => ({}), registerDefinitionProvider: () => ({}) },
    commands: { registerCommand: (_, callback) => { command = callback; return {}; } },
    window: { activeTextEditor: { document }, showErrorMessage: assert.fail },
    workspace: { getWorkspaceFolder: () => undefined, getConfiguration: () => ({ get: () => '/tmp/my python' }) },
    TaskScope: { Global: 1 }, TaskRevealKind: { Always: 1 }, TaskPanelKind: { Dedicated: 1 },
    ProcessExecution: class { constructor(executable, args) { this.executable = executable; this.args = args; } },
    Task: class { constructor(...args) { this.args = args; } },
    tasks: { executeTask: async value => { task = value; } }
  };
  const original = Module._load;
  Module._load = function (request, ...args) { return request === 'vscode' ? vscode : original.call(this, request, ...args); };
  try { require('../extension').activate({ subscriptions: [] }); } finally { Module._load = original; }
  await command();
  assert.equal(saved, true);
  assert.equal(task.args[4].executable, '/tmp/my python');
  assert.deepEqual(task.args[4].args, ['-m', 'sonqelra_lang', '/tmp/a score.sonqelra']);
  assert.deepEqual(task.args[5], ['$sonqelra']);
});

const language = require('../language');
test('visible symbols respect declaration order and lexical scopes', () => {
  const text = `fn outer(p: Pitch) -> Music {
  let local = note(p, 1)
  return local
}
score "x" {
  melody tune { C4:1/4 }
  let part = tune
  track piano { play part }
}
score "y" {
  let last = outer(C4)
}`;
  const names = at => language.visibleSymbols(text, text.indexOf(at)).map(x => x.name);
  assert.deepEqual(names('return local'), ['p', 'local', 'outer']);
  assert.deepEqual(names('play part'), ['tune', 'part', 'outer']);
  assert.deepEqual(names('let last'), ['outer']);
  assert.deepEqual(names('let part'), ['tune', 'outer']);
});
test('comments and strings do not create symbols or scopes', () => {
  const text = 'score "let fake {" {\n // let ghost = 1 }\n let real = 1\n play real\n}';
  assert.deepEqual(language.visibleSymbols(text, text.indexOf('play')).map(x => x.name), ['real']);
});
