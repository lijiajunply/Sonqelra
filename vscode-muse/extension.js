'use strict';

const vscode = require('vscode');

function activate(context) {
  context.subscriptions.push(vscode.commands.registerCommand('muse.compile', async () => {
    const editor = vscode.window.activeTextEditor;
    if (!editor || editor.document.languageId !== 'muse') {
      vscode.window.showErrorMessage('Open a Muse file before compiling.');
      return;
    }
    const document = editor.document;
    if (document.isUntitled || document.uri.scheme !== 'file') {
      vscode.window.showErrorMessage('Save the Muse file to disk before compiling.');
      return;
    }
    if (document.isDirty && !(await document.save())) return;

    const folder = vscode.workspace.getWorkspaceFolder(document.uri);
    const python = vscode.workspace.getConfiguration('muse', document.uri).get('pythonPath');
    const task = new vscode.Task(
      { type: 'muse', file: document.uri.fsPath },
      folder || vscode.TaskScope.Global,
      `Compile ${document.fileName.split(/[\\/]/).pop()}`,
      'Muse',
      new vscode.ProcessExecution(python, ['-m', 'muse_lang', document.uri.fsPath]),
      ['$muse']
    );
    task.presentationOptions = { reveal: vscode.TaskRevealKind.Always, panel: vscode.TaskPanelKind.Dedicated, clear: true };
    await vscode.tasks.executeTask(task);
  }));
}

module.exports = { activate };
