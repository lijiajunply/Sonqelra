'use strict';

// Ignore strings and comments while preserving offsets for editor locations.
function tokenize(text) {
  const tokens = [];
  const pattern = /\/\/[^\n]*|"(?:\\.|[^"\\\n])*"?|[A-Za-z_][A-Za-z_0-9#]*(?:-\d+)?|-?\d+(?:st)?|[^\s]/g;
  for (const match of text.matchAll(pattern)) {
    if (match[0].startsWith('//') || match[0].startsWith('"')) continue;
    tokens.push({ value: match[0], offset: match.index });
  }
  return tokens;
}

function symbols(text) {
  const tokens = tokenize(text);
  const root = { parent: null };
  const stack = [root];
  const found = [];
  const scopes = [{ offset: 0, scope: root }];
  const parameters = new Map();
  for (let i = 0; i < tokens.length; i++) {
    const token = tokens[i];
    const scope = stack[stack.length - 1];
    if (['let', 'melody', 'fn'].includes(token.value)) {
      const name = tokens[i + 1];
      if (name && /^[A-Za-z_][A-Za-z_0-9]*$/.test(name.value)) {
        found.push({ name: name.value, offset: name.offset, kind: token.value, scope });
      }
      if (token.value === 'fn' && tokens[i + 2]?.value === '(') {
        let j = i + 3;
        const args = [];
        while (j < tokens.length && tokens[j].value !== ')' && tokens[j].value !== '{') {
          if (/^[A-Za-z_][A-Za-z_0-9]*$/.test(tokens[j].value) && tokens[j + 1]?.value === ':') args.push(tokens[j]);
          j++;
        }
        while (j < tokens.length && !['{', '}'].includes(tokens[j].value)) j++;
        if (tokens[j]?.value === '{') parameters.set(tokens[j].offset, args);
      }
    }
    if (token.value === '{') {
      const child = { parent: scope };
      stack.push(child);
      scopes.push({ offset: token.offset + 1, scope: child });
      for (const param of parameters.get(token.offset) || []) found.push({ name: param.value, offset: param.offset, kind: 'parameter', scope: child });
    } else if (token.value === '}' && stack.length > 1) {
      stack.pop();
      scopes.push({ offset: token.offset + 1, scope: stack[stack.length - 1] });
    }
  }
  return { found, scopes };
}

function visibleSymbols(text, offset) {
  const { found, scopes } = symbols(text);
  let scope = scopes[0].scope;
  for (const entry of scopes) {
    if (entry.offset > offset) break;
    scope = entry.scope;
  }
  const visible = new Map();
  while (scope) {
    for (const item of found) {
      if (item.scope === scope && item.offset <= offset && !visible.has(item.name)) visible.set(item.name, item);
    }
    scope = scope.parent;
  }
  return [...visible.values()];
}

const builtins = {
  note: ['note(pitch: Pitch, beats: Number, velocity?: Int) -> Music', 'Create a note. Beats are measured in quarter notes; velocity defaults to 80.'],
  rest: ['rest(beats: Number) -> Music', 'Create a rest. Beats are measured in quarter notes.'],
  chord: ['chord(pitches: List<Pitch>, duration: Number, velocity?: Int) -> Music', 'Play pitches together. duration and velocity are named arguments; duration uses whole-note units.'],
  sequence: ['sequence(pitches: List<Pitch>, duration: Number, velocity?: Int) -> Music', 'Play pitches in order. duration and velocity are named arguments; duration uses whole-note units.'],
  transpose: ['transpose(music: Music, semitones: Int) -> Music', 'Transpose music by semitones. In a pipeline use music |> transpose(semitones).'],
  repeat: ['repeat(music: Music, count: Int) -> Music', 'Repeat music count times. In a pipeline use music |> repeat(count).']
};

module.exports = { tokenize, symbols, visibleSymbols, builtins };
