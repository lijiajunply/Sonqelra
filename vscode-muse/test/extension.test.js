'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');

const root = path.join(__dirname, '..');
test('extension manifests and grammar are valid', () => {
  for (const file of ['package.json', 'language-configuration.json', 'syntaxes/muse.tmLanguage.json']) {
    assert.doesNotThrow(() => JSON.parse(fs.readFileSync(path.join(root, file), 'utf8')));
  }
  const manifest = require('../package.json');
  assert.deepEqual(manifest.contributes.languages[0].extensions, ['.muse']);
  const matcher = new RegExp(manifest.contributes.problemMatchers[0].pattern.regexp);
  assert.deepEqual(matcher.exec('/tmp/my score.muse:12:3: bad note').slice(1), ['/tmp/my score.muse', '12', '3', 'bad note']);
  assert.deepEqual(matcher.exec('C:\\music\\song.muse:12:3: bad note').slice(1), ['C:\\music\\song.muse', '12', '3', 'bad note']);
});

test('compile saves and passes the filename as a process argument', async () => {
  let command, task, saved = false;
  const document = { languageId: 'muse', isUntitled: false, isDirty: true, uri: { scheme: 'file', fsPath: '/tmp/a score.muse' }, fileName: '/tmp/a score.muse', save: async () => { saved = true; return true; } };
  const vscode = {
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
  assert.deepEqual(task.args[4].args, ['-m', 'muse_lang', '/tmp/a score.muse']);
  assert.deepEqual(task.args[5], ['$muse']);
});
