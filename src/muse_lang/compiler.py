"""Compile Muse syntax to core music objects and explicit export plans."""
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
import re
from muse.core import Pitch, Note, Rest, Sequence, Parallel
from muse.core.base import Music
from muse.core.work import Score, Track, TempoMap, MeterMap, TimeSignature
from muse.backends.mido import muse_to_midi
from .errors import SemanticError, ExportError
from .parser import parse

@dataclass(frozen=True)
class KeySignature:
    root: str
    mode: str

@dataclass(frozen=True)
class ScoreResult:
    score: Score
    key: KeySignature | None

@dataclass(frozen=True)
class ExportPlan:
    score: ScoreResult
    path: str
    span: object

@dataclass(frozen=True)
class CompilationResult:
    scores: tuple[ScoreResult, ...]
    exports: tuple[ExportPlan, ...]

@dataclass(frozen=True)
class Interval:
    semitones: int

@dataclass(frozen=True)
class Function:
    node: object
    closure: dict

BUILTINS = {'note','rest','transpose','repeat','chord','sequence'}

def fail(node, message): raise SemanticError(message, node.span)
def type_name(value):
    if isinstance(value, Music): return 'Music'
    if isinstance(value, Pitch): return 'Pitch'
    if isinstance(value, Interval): return 'Interval'
    if isinstance(value, tuple): return 'List<Pitch>'
    if type(value) is int: return 'Int'
    if isinstance(value, Fraction): return 'Number'
    return 'unknown'
def accepts(value, expected): return type_name(value)==expected or expected=='Number' and type_name(value)=='Int'
def require(node, value, expected):
    if not accepts(value,expected): fail(node, f'Expected {expected}, got {type_name(value)}')
    return value

def bind(env, name, value, node):
    if name in BUILTINS: fail(node, f'Cannot shadow builtin {name}')
    if name in env: fail(node, f'Duplicate declaration {name}')
    env[name] = value

def evaluate(n, env):
    try: return _evaluate(n,env)
    except SemanticError: raise
    except (ValueError, ZeroDivisionError, OverflowError) as exc: raise SemanticError(str(exc),n.span,cause=exc) from exc

def _evaluate(n, env):
    k=n.kind
    if k=='number':
        a,b=n.value
        if b <= 0: fail(n,'Number denominator must be positive')
        return a if b==1 else Fraction(a,b)
    if k=='pitch':
        p=Pitch.parse(n.value); p.midi; return p
    if k=='interval': return Interval(n.value)
    if k=='name':
        if n.value not in env: fail(n, f'Unknown name {n.value}')
        return env[n.value]
    if k=='list':
        if not n.children: fail(n,'Pitch list must not be empty')
        return tuple(require(c,evaluate(c,env),'Pitch') for c in n.children)
    if k in ('+','|'):
        a=evaluate(n.children[0],env); b=evaluate(n.children[1],env)
        if k=='+' and isinstance(a,Pitch) and isinstance(b,Interval): return a.transpose(b.semitones)
        require(n,a,'Music'); require(n,b,'Music'); return a+b if k=='+' else a|b
    if k in ('call','pipe'):
        if k=='pipe':
            if n.value not in ('transpose','repeat'): fail(n,'Pipeline only supports transpose and repeat')
            positional=[evaluate(n.children[0],env)]; args=n.children[1:]
        else: positional=[]; args=n.children
        named={}; seen_named=False
        for arg in args:
            v=evaluate(arg.children[0],env)
            if arg.value is None:
                if seen_named: fail(arg,'Positional argument follows named argument')
                positional.append(v)
            else:
                seen_named=True
                if arg.value in named: fail(arg,f'Duplicate argument {arg.value}')
                named[arg.value]=v
        return call(n,n.value,positional,named,env)
    fail(n,f'Unsupported expression {k}')

def call(n,name,args,kwargs,env):
    if name in ('chord','sequence'):
        if len(args)!=1 or set(kwargs)-{'duration','velocity'} or 'duration' not in kwargs: fail(n,f'{name} expects a pitch list and named duration, with optional velocity')
        pitches=require(n,args[0],'List<Pitch>'); duration=require(n,kwargs['duration'],'Number'); velocity=kwargs.get('velocity',80)
        require(n,velocity,'Int')
        if duration<=0 or not 0<=velocity<=127: fail(n,'Invalid duration or velocity')
        notes=tuple(Note(p,Fraction(duration)*4,velocity) for p in pitches)
        return Parallel(notes) if name=='chord' else Sequence(notes)
    if kwargs: fail(n,'Named arguments are not supported here')
    if name in BUILTINS:
        counts={'note':(2,3),'rest':(1,),'transpose':(2,),'repeat':(2,)}
        if len(args) not in counts[name]: fail(n,f'Wrong number of arguments for {name}')
        if name=='note':
            p=require(n,args[0],'Pitch'); duration=require(n,args[1],'Number'); velocity=args[2] if len(args)==3 else 80
            require(n,velocity,'Int')
            if duration<=0 or not 0<=velocity<=127: fail(n,'Invalid duration or velocity')
            return Note(p,Fraction(duration),velocity)
        if name=='rest':
            duration=require(n,args[0],'Number')
            if duration<0: fail(n,'Rest duration must be non-negative')
            return Rest(Fraction(duration))
        music=require(n,args[0],'Music'); count=require(n,args[1],'Int')
        if name=='repeat' and count<0: fail(n,'Repeat count must be non-negative')
        return music.repeat(count) if name=='repeat' else music.transpose(count)
    fn=env.get(name)
    if not isinstance(fn,Function): fail(n,f'Unknown function {name}')
    params=[x for x in fn.node.children if x.kind=='param']
    if len(args)!=len(params): fail(n,f'Wrong number of arguments for {name}')
    local={}
    for p,v in zip(params,args): require(p,v,p.value[1]); bind(local,p.value[0],v,p)
    for stmt in fn.node.children[len(params):-1]:
        value=evaluate(stmt.children[0],fn.closure|local); bind(local,stmt.value,value,stmt)
    result=evaluate(fn.node.children[-1],fn.closure|local)
    return require(fn.node,result,fn.node.value[1])

def infer(n, env):
    k = n.kind
    if k == 'number':
        if n.value[1] <= 0: fail(n, 'Number denominator must be positive')
        return 'Int' if n.value[1] == 1 else 'Number'
    if k == 'pitch':
        try: Pitch.parse(n.value).midi
        except ValueError as exc: raise SemanticError(str(exc), n.span, cause=exc) from exc
        return 'Pitch'
    if k == 'interval': return 'Interval'
    if k == 'name':
        if n.value not in env: fail(n, f'Unknown name {n.value}')
        value = env[n.value]
        return value if isinstance(value, str) else type_name(value)
    if k == 'list':
        if not n.children: fail(n, 'Pitch list must not be empty')
        for child in n.children:
            if infer(child, env) != 'Pitch': fail(child, 'Expected Pitch')
        return 'List<Pitch>'
    if k in ('+', '|'):
        a, b = (infer(c, env) for c in n.children)
        if k == '+' and (a,b) == ('Pitch','Interval'): return 'Pitch'
        if (a,b) != ('Music','Music'): fail(n, 'Expected Music operands')
        return 'Music'
    if k in ('call','pipe'):
        name=n.value; args=[]; named={}; seen=False
        if k=='pipe':
            if name not in ('transpose','repeat'): fail(n, 'Pipeline only supports transpose and repeat')
            args.append(infer(n.children[0],env)); children=n.children[1:]
        else: children=n.children
        for arg in children:
            ty=infer(arg.children[0],env)
            if arg.value is None:
                if seen: fail(arg,'Positional argument follows named argument')
                args.append(ty)
            else:
                seen=True
                if arg.value in named: fail(arg,'Duplicate named argument')
                named[arg.value]=ty
        def check(actual, expected):
            if actual != expected and not (expected=='Number' and actual=='Int'): fail(n,f'Expected {expected}, got {actual}')
        if name in ('chord','sequence'):
            if len(args)!=1 or set(named)-{'duration','velocity'} or 'duration' not in named: fail(n,'Invalid named arguments')
            check(args[0],'List<Pitch>'); check(named['duration'],'Number')
            if 'velocity' in named: check(named['velocity'],'Int')
            return 'Music'
        if named: fail(n,'Named arguments are not supported here')
        signatures={'note':(['Pitch','Number','Int'],(2,3)), 'rest':(['Number'],(1,)), 'repeat':(['Music','Int'],(2,)), 'transpose':(['Music','Int'],(2,))}
        if name in signatures: expected,counts=signatures[name]; result='Music'
        else:
            f=env.get(name)
            if not isinstance(f,Function): fail(n,f'Unknown function {name}')
            expected=[p.value[1] for p in f.node.children if p.kind=='param']; counts=(len(expected),); result=f.node.value[1]
        if len(args) not in counts: fail(n,f'Wrong number of arguments for {name}')
        for actual, want in zip(args,expected): check(actual,want)
        return result
    fail(n,'Invalid expression')

def declare_function(n, outer, local):
    names=set()
    for p in n.children:
        if p.kind!='param': break
        if p.value[0] in names or p.value[0] in BUILTINS: fail(p,'Duplicate or reserved parameter')
        names.add(p.value[0])
    closure=dict(outer)|dict(local)
    scope=dict(closure)
    for p in n.children:
        if p.kind!='param': break
        scope[p.value[0]]=p.value[1]
    declared=set(names)
    params_count=len(names)
    for stmt in n.children[params_count:-1]:
        if stmt.value in declared or stmt.value in BUILTINS: fail(stmt, 'Duplicate or reserved local name')
        scope[stmt.value]=infer(stmt.children[0],scope); declared.add(stmt.value)
    actual=infer(n.children[-1],scope); expected=n.value[1]
    if actual != expected and not (expected=='Number' and actual=='Int'): fail(n.children[-1],f'Expected {expected}, got {actual}')
    bind(local,n.value[0],Function(n,closure),n)

def compile_source(source, *, filename='<string>'):
    program=parse(source,filename=filename); globals_={}; results=[]; exports=[]
    for item in program:
        if item.kind=='fn': declare_function(item,{},globals_); continue
        if not item.value: fail(item,'Score title must not be empty')
        local={}; tracks=[]; plans=[]; fields={}; key=None; tempo=120; meter=TimeSignature(4,4)
        for n in item.children:
            env=globals_|local
            try:
                if n.kind in ('tempo','meter','key'):
                    if n.kind in fields: fail(n,f'Duplicate {n.kind}')
                    fields[n.kind]=True
                    if n.kind=='tempo':
                        tempo=require(n,evaluate(n.children[0],env),'Number')
                        if tempo<=0: fail(n,'Tempo must be positive')
                    elif n.kind=='meter': meter=TimeSignature(*n.value)
                    else:
                        if not re.fullmatch(r'[A-G](?:#+|b+)?',n.value[0]): fail(n,'Invalid key root')
                        key=KeySignature(*n.value)
                elif n.kind=='let': bind(local,n.value,evaluate(n.children[0],env),n)
                elif n.kind=='fn': declare_function(n,globals_,local)
                elif n.kind=='melody':
                    if not n.children: fail(n,'Melody must not be empty')
                    notes=[]
                    for note in n.children:
                        pitch,a,b,velocity=note.value
                        if a<=0 or b<=0: fail(note,'Duration must be positive')
                        if pitch=='rest':
                            if velocity is not None: fail(note,'Rest cannot have velocity')
                            notes.append(Rest(Fraction(a,b)*4))
                        else:
                            velocity=80 if velocity is None else velocity
                            if not 0<=velocity<=127: fail(note,'Velocity must be 0–127')
                            
                            try: p=Pitch.parse(pitch); p.midi
                            except ValueError as exc: raise SemanticError(str(exc),note.span,cause=exc) from exc
                            notes.append(Note(p,Fraction(a,b)*4,velocity))
                    bind(local,n.value,Sequence(tuple(notes)),n)
                elif n.kind=='track':
                    if not n.value: fail(n,'Track name must not be empty')
                    parts={}
                    for part in n.children:
                        if part.kind in parts: fail(part,f'Duplicate {part.kind}')
                        parts[part.kind]=part
                    if 'instrument' not in parts or 'play' not in parts: fail(n,'Track requires instrument and play')
                    music=require(parts['play'],evaluate(parts['play'].children[0],env),'Music')
                    track=Track(music,parts['instrument'].value,n.value,parts['percussion'].value if 'percussion' in parts else False)
                    try: track.instrument_to_midi_program()
                    except ValueError as exc: raise SemanticError(str(exc),parts['instrument'].span,cause=exc) from exc
                    tracks.append(track)
                elif n.kind=='export': plans.append(n)
            except SemanticError: raise
            except (ValueError, ZeroDivisionError, OverflowError) as exc: raise SemanticError(str(exc),n.span,cause=exc) from exc
        if not tracks: fail(item,'Score must have at least one track')
        result=ScoreResult(Score(tuple(tracks),item.value,TempoMap(((Fraction(0),tempo),)),MeterMap(((Fraction(0),meter),))),key)
        results.append(result); exports.extend(ExportPlan(result,p.value,p.span) for p in plans)
    return CompilationResult(tuple(results),tuple(exports))

def execute_exports(result, *, base_dir):
    targets=[]; seen=set()
    for plan in result.exports:
        target=Path(plan.path)
        if not target.is_absolute(): target=Path(base_dir)/target
        target=target.resolve()
        if target in seen: raise ExportError(f'Duplicate export target: {target}',plan.span)
        seen.add(target); targets.append((plan,target))
    for plan,target in targets:
        try: muse_to_midi(plan.score.score,str(target))
        except Exception as exc: raise ExportError(f'MIDI export failed: {exc}',plan.span,cause=exc) from exc
