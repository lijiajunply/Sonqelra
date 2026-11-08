'use strict';

const vscode = require('vscode');
const language = require('./language');

function activate(context) {
  const selector = { language: 'sonqelra' };
  context.subscriptions.push(vscode.languages.registerCompletionItemProvider(selector, {
    provideCompletionItems(document, position) {
      const text = document.getText();
      const offset = document.offsetAt(position);
      const line = document.lineAt(position).text.slice(0, position.character);
      const pipeline = /\|>\s*[A-Za-z_]*$/.test(line);
      const items = [];
      for (const [name, [signature, detail]] of Object.entries(language.builtins)) {
        if (pipeline && !['transpose', 'repeat'].includes(name)) continue;
        const item = new vscode.CompletionItem(name, vscode.CompletionItemKind.Function);
        item.detail = signature;
        item.documentation = detail;
        items.push(item);
      }
      if (pipeline) return items;
      for (const word of ['score', 'tempo', 'meter', 'key', 'major', 'minor', 'melody', 'let', 'fn', 'return', 'track', 'instrument', 'percussion', 'play', 'export', 'import', 'midi', 'musicxml', 'sonqelra', 'module', 'true', 'false', 'Pitch', 'Music', 'Int', 'Number', 'Interval', 'List']) {
        items.push(new vscode.CompletionItem(word, vscode.CompletionItemKind.Keyword));
      }
      for (const symbol of language.visibleSymbols(text, offset)) {
        const item = new vscode.CompletionItem(symbol.name, symbol.kind === 'fn' ? vscode.CompletionItemKind.Function : vscode.CompletionItemKind.Variable);
        item.detail = `Sonqelra ${symbol.kind}`;
        items.push(item);
      }
      return items;
    }
  }, '>'));
  context.subscriptions.push(vscode.languages.registerHoverProvider(selector, {
    provideHover(document, position) {
      const range = document.getWordRangeAtPosition(position);
      if (!range) return;
      const name = document.getText(range);
      const builtin = language.builtins[name];
      if (builtin) return new vscode.Hover(new vscode.MarkdownString(`\`\`\`sonqelra\n${builtin[0]}\n\`\`\`\n${builtin[1]}`), range);
      const symbol = language.visibleSymbols(document.getText(), document.offsetAt(position)).find(item => item.name === name);
      if (symbol) return new vscode.Hover(`Sonqelra ${symbol.kind}: ${symbol.name}`, range);
    }
  }));
  context.subscriptions.push(vscode.languages.registerDefinitionProvider(selector, {
    provideDefinition(document, position) {
      const range = document.getWordRangeAtPosition(position);
      if (!range) return;
      const symbol = language.visibleSymbols(document.getText(), document.offsetAt(position)).find(item => item.name === document.getText(range));
      if (symbol) return new vscode.Location(document.uri, document.positionAt(symbol.offset));
    }
  }));
  context.subscriptions.push(vscode.commands.registerCommand('sonqelra.compile', async () => {
    const editor = vscode.window.activeTextEditor;
    if (!editor || editor.document.languageId !== 'sonqelra') {
      vscode.window.showErrorMessage('Open a Sonqelra file before compiling.');
      return;
    }
    const document = editor.document;
    if (document.isUntitled || document.uri.scheme !== 'file') {
      vscode.window.showErrorMessage('Save the Sonqelra file to disk before compiling.');
      return;
    }
    if (document.isDirty && !(await document.save())) return;

    const folder = vscode.workspace.getWorkspaceFolder(document.uri);
    const python = vscode.workspace.getConfiguration('sonqelra', document.uri).get('pythonPath');
    const task = new vscode.Task(
      { type: 'sonqelra', file: document.uri.fsPath },
      folder || vscode.TaskScope.Global,
      `Compile ${document.fileName.split(/[\\/]/).pop()}`,
      'Sonqelra',
      new vscode.ProcessExecution(python, ['-m', 'sonqelra_lang', document.uri.fsPath]),
      ['$sonqelra']
    );
    task.presentationOptions = { reveal: vscode.TaskRevealKind.Always, panel: vscode.TaskPanelKind.Dedicated, clear: true };
    await vscode.tasks.executeTask(task);
  }));
}

module.exports = { activate };
