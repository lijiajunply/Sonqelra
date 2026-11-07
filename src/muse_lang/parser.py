"""Recursive-descent parser; parsing never evaluates source."""
from .ast import Node, Span, MeterLiteral, NoteLiteral
from .errors import ParseError
from .lexer import lex

class Parser:
    def __init__(self, tokens): self.tokens, self.i = tokens, 0
    @property
    def t(self): return self.tokens[self.i]
    def take(self, value=None):
        t = self.t
        if value is not None and t.kind != value and t.value != value:
            raise ParseError(f'Expected {value}, got {t.value or t.kind}', t.span)
        self.i += 1
        return t
    def is_(self, value): return self.t.kind == value or self.t.value == value
    def node(self, kind, start, value=None, children=(), cls=Node):
        return cls(kind, Span(start.span.filename, start.span.start, self.tokens[self.i-1].span.end), value, tuple(children))
    def nl(self):
        while self.is_('NL'): self.take()
    def end(self):
        if self.is_('NL'): self.nl()
        elif not self.is_('}') and not self.is_('EOF'): raise ParseError('Expected end of statement', self.t.span)
    def ident(self):
        t = self.take('IDENT')
        if t.value in {'score','tempo','meter','key','melody','let','fn','return','track','instrument','percussion','play','export','midi','true','false','major','minor','rest'}: raise ParseError('Expected identifier', t.span)
        return t.value
    def program(self):
        items = []; self.nl()
        while not self.is_('EOF'):
            if self.is_('score'): items.append(self.score())
            elif self.is_('fn'): items.append(self.fn())
            else: raise ParseError('Expected score or fn', self.t.span)
            self.end()
        return tuple(items)
    def score(self):
        s=self.take('score'); title=self.take('STRING').value; self.take('{'); self.nl(); items=[]
        while not self.is_('}'):
            if self.is_('EOF'): raise ParseError('Expected }', self.t.span)
            items.append(self.statement('score')); self.end()
        self.take('}'); return self.node('score',s,title,items)
    def statement(self, context):
        s=self.t; k=s.value
        if k == 'fn' and context == 'score': return self.fn()
        if k == 'let':
            self.take(); name=self.ident(); self.take('='); return self.node('let',s,name,(self.expr(),))
        if k == 'tempo' and context == 'score': self.take(); return self.node(k,s,None,(self.expr(),))
        if k == 'meter' and context == 'score':
            self.take(); a=self.take('INT'); self.take('/'); b=self.take('INT'); return self.node(k,s,(int(a.value),int(b.value)),cls=MeterLiteral)
        if k == 'key' and context == 'score':
            self.take(); root=self.take('IDENT'); mode=self.take('IDENT')
            if mode.value not in ('major','minor'): raise ParseError('Expected major or minor', mode.span)
            return self.node(k,s,(root.value,mode.value))
        if k == 'melody' and context == 'score':
            self.take(); name=self.ident(); self.take('{'); self.nl(); items=[]
            while not self.is_('}'):
                t=self.t
                if not (self.is_('PITCH') or self.is_('rest')): raise ParseError('Expected note or rest',t.span)
                self.take(); self.take(':'); a=self.take('INT'); self.take('/'); b=self.take('INT'); velocity=None
                if self.is_('@'): self.take(); velocity=int(self.take('INT').value)
                items.append(self.node('note',t,(t.value,int(a.value),int(b.value),velocity),cls=NoteLiteral)); self.end()
            self.take('}'); return self.node(k,s,name,items)
        if k == 'track' and context == 'score':
            self.take(); name=self.take('STRING').value if self.is_('STRING') else self.ident(); self.take('{'); self.nl(); items=[]
            while not self.is_('}'):
                items.append(self.statement('track')); self.end()
            self.take('}'); return self.node(k,s,name,items)
        if k == 'export' and context == 'score': self.take(); self.take('midi'); return self.node(k,s,self.take('STRING').value)
        if k == 'instrument' and context == 'track': self.take(); return self.node(k,s,self.take('STRING').value)
        if k == 'percussion' and context == 'track':
            self.take(); t=self.take('IDENT')
            if t.value not in ('true','false'): raise ParseError('Expected true or false', t.span)
            return self.node(k,s,t.value == 'true')
        if k == 'play' and context == 'track': self.take(); return self.node(k,s,None,(self.expr(),))
        raise ParseError(f'Unexpected statement {k!r}',s.span)
    def type_(self):
        t=self.take('IDENT'); name=t.value
        if name == 'List': self.take('<'); self.take('Pitch'); self.take('>'); return 'List<Pitch>'
        if name not in ('Pitch','Music','Int','Number','Interval'): raise ParseError('Unknown type',t.span)
        return name
    def fn(self):
        s=self.take('fn'); name=self.ident(); self.take('('); params=[]
        if not self.is_(')'):
            while True:
                p=self.t; n=self.ident(); self.take(':'); ty=self.type_(); params.append(self.node('param',p,(n,ty)))
                if not self.is_(','): break
                self.take(',')
        self.take(')'); self.take('->'); result=self.type_(); self.take('{'); self.nl(); body=[]
        while self.is_('let'): body.append(self.statement('fn')); self.end()
        self.take('return'); body.append(self.expr()); self.end(); self.take('}')
        return self.node('fn',s,(name,result),(*params,*body))
    def expr(self):
        left=self.binary(0)
        while True:
            save=self.i
            if self.is_('NL'):
                self.nl()
                if not self.is_('|>'): self.i=save; break
            if not self.is_('|>'): break
            self.take(); t=self.t; name=self.ident(); args=self.args(); left=Node('pipe',Span(left.span.filename,left.span.start,self.tokens[self.i-1].span.end),name,(left,*args))
        return left
    def binary(self, level):
        if level == 2: return self.primary()
        left=self.binary(level+1); op='|' if level==0 else '+'
        while self.is_(op):
            self.take(); right=self.binary(level+1); left=Node(op,Span(left.span.filename,left.span.start,right.span.end),None,(left,right))
        return left
    def args(self):
        self.take('('); args=[]
        if not self.is_(')'):
            while True:
                s=self.t; name=None
                if self.t.kind=='IDENT' and self.tokens[self.i+1].kind==':': name=self.take().value; self.take(':')
                arg=self.expr(); args.append(self.node('arg',s,name,(arg,)))
                if not self.is_(','): break
                self.take(',')
        self.take(')'); return args
    def primary(self):
        s=self.t
        if self.is_('PITCH'): self.take(); return self.node('pitch',s,s.value)
        if self.is_('INTERVAL'): self.take(); return self.node('interval',s,int(s.value[:-2]))
        if self.is_('INT'):
            self.take(); n=int(s.value); d=1
            if self.is_('/'): self.take(); d=int(self.take('INT').value)
            return self.node('number',s,(n,d))
        if self.is_('IDENT'):
            name=self.take().value
            if self.is_('('): return self.node('call',s,name,self.args())
            return self.node('name',s,name)
        if self.is_('['):
            self.take(); items=[]
            if not self.is_(']'):
                while True:
                    items.append(self.expr())
                    if not self.is_(','): break
                    self.take(',')
                    if self.is_(']'): break
            self.take(']'); return self.node('list',s,None,items)
        if self.is_('('): self.take(); result=self.expr(); self.take(')'); return result
        raise ParseError('Expected expression',s.span)

def parse(source, *, filename='<string>'):
    return Parser(lex(source, filename)).program()
