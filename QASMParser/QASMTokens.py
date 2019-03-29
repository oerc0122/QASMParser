import copy
import re

class Token:

    def __init__(self, name: str, pattern: str):
        self.name = name
        self.re = re.compile(pattern.replace(' ','\s*'), re.I + re.X)
        self.string = pattern
        
    def __str__(self):
        return self.string

    def __call__(self, string):
        return self.re.match(string)
    

class TokenSet(dict):
    def add(self, token: Token):
        if token not in self.__dict__: self.__dict__[token.name] = token
        else: raise IOError(f'Token {token.name} already in tokenSet')

    def __add__(self, other):
        out = copy.copy(self.__dict__)
        for token in other.__dict__.values():
            if token not in out: out[token.name] = token
        new = TokenSet()
        new.__dict__ = out
        return new

    def tokens(self):
        return self.__dict__.values()
    
coreTokens = TokenSet()
openQASM = TokenSet()

# Base Types
coreTokens.add(Token('blank', '^\s*$'))
coreTokens.add(Token('int', '\d+(?:[eE]+?\d+)?'))
coreTokens.add(Token('float', '[+-]?(?:\d*\.)?\d+(?:[eE][+-]?\d+)?'))
coreTokens.add(Token('compOp', '(?:<|>|==|!=)'))
coreTokens.add(Token('compJoin', '(?:&&|\|\|)'))
coreTokens.add(Token('mathOp', '[-+*/^]'))
coreTokens.add(Token('funcOp', '(?:sin|cos|tan|exp|ln|sqrt)'))
coreTokens.add(Token('validName', '[a-z]\w*'))
coreTokens.add(Token('openBlock', '\{'))
coreTokens.add(Token('closeBlock', '\}'))

coreTokens.add(Token('validSingRef', f'(?:(?:{coreTokens.int})|(?:{coreTokens.validName}))'))
coreTokens.add(Token('validRef', r'(?:{}(?:\:{})?)'.format(coreTokens.validSingRef, coreTokens.validSingRef)))

coreTokens.add(Token('qubitRef', '(?:\[{}\])'.format(coreTokens.validRef)))
coreTokens.add(Token('namedQubitRef', '(?:\[(?P<qubitIndex>{})\])'.format(coreTokens.validRef)))
coreTokens.add(Token('namedBitRef', '(?:\[(?P<bitIndex> {})\])'.format(coreTokens.validRef)))
coreTokens.add(Token('namedQarg', '(?P<qargName>{})'.format(coreTokens.validName)))
coreTokens.add(Token('namedCarg', '(?P<cargName>{})'.format(coreTokens.validName)))

coreTokens.add(Token('qarg', '{} {}?'.format(coreTokens.validName,coreTokens.qubitRef)))
coreTokens.add(Token('singCarg', '(?:{}|{}|{}{}?)'.format(coreTokens.float,coreTokens.int,coreTokens.validName,coreTokens.qubitRef)))
coreTokens.add(Token('cargOp', '{}(?: {} {})*'.format(coreTokens.singCarg,coreTokens.mathOp,coreTokens.singCarg)))
coreTokens.add(Token('funcCarg', '(?:(?:{}\({}\))|(?:{}))'.format(coreTokens.funcOp,coreTokens.cargOp, coreTokens.cargOp)))
coreTokens.add(Token('carg', '{}(?: {} {})*'.format(coreTokens.funcCarg, coreTokens.mathOp, coreTokens.funcCarg)))

coreTokens.add(Token('funcName', '(?P<funcName>{})'.format(coreTokens.validName)))
coreTokens.add(Token('namedQubit', '{} {}?'.format(coreTokens.namedQarg,coreTokens.namedQubitRef)))
coreTokens.add(Token('namedParam', '{} {}?'.format(coreTokens.namedCarg,coreTokens.namedBitRef)))

coreTokens.add(Token('singCond','{} {} {}'.format(coreTokens.carg,coreTokens.compOp,coreTokens.carg)))
coreTokens.add(Token('conditional','{}(?: {} {})*'.format(coreTokens.singCond,coreTokens.compJoin,coreTokens.singCond)))

coreTokens.add(Token('qargList', '(?P<qargs>{} (?:, {})*)'.format(coreTokens.qarg,coreTokens.qarg)))
coreTokens.add(Token('cargList', '(?:\((?P<cargs>{} (?:, {})*)\))'.format(coreTokens.carg,coreTokens.carg)))
coreTokens.add(Token('comment', '//(?P<comment>.*)$'))
coreTokens.add(Token('gate', '{} {}?\s+{} $'.format(coreTokens.funcName,coreTokens.cargList,coreTokens.qargList)))

openQASM.add(Token('createReg', '(?P<regType>[qc])reg\s+{}'.format(coreTokens.namedQubit)))
openQASM.add(Token('measure', 'measure\s+{}? -> {}'.format(coreTokens.namedQubit,coreTokens.namedParam)))
openQASM.add(Token('wholeLineComment','^ //(?P<comment>.*)'))
openQASM.add(Token('version', '(?P<version>[a-zA-Z]+QASM)\s+(?P<majorVer>\d+)\.(?P<minorVer>\d+)'))
openQASM.add(Token('include', 'include\s+[\'"](?P<filename>(?:\w|[./])+)[\'"]'))
openQASM.add(Token('reset', 'reset\s+{}'.format(coreTokens.namedQubit)))
openQASM.add(Token('barrier', 'barrier\s+{}'.format(coreTokens.qargList)))
openQASM.add(Token('opaque', 'opaque\s+{}'.format(coreTokens.gate)))
openQASM.add(Token('createGate', 'gate\s+{}'.format(coreTokens.gate)))
openQASM.add(Token('callGate', coreTokens.gate.string))
openQASM.add(Token('qop', re.sub(r'\(\?P\<[a-zA-Z]+\>','(','(?:{})'.format('|'.join(
    map(str,[openQASM.callGate,openQASM.createReg,openQASM.include,openQASM.measure, openQASM.reset]))
))))
openQASM.add(Token('ifLine','if \((?P<cond>{cond})\)(?P<op> {op})?'.format(cond=coreTokens.conditional,op=openQASM.qop)))

OAQEQASM = TokenSet()

OAQEQASM.add(Token('forLoop', 'for\s+(?P<var>{})\s+in\s+\[(?P<range>{})\]\s+do'.format(coreTokens.validName, coreTokens.validRef)))
OAQEQASM.add(Token('CBlock', 'CBLOCK'))
OAQEQASM.add(Token('PyBlock', 'PYBLOCK'))
OAQEQASM.add(Token('createRGate', 'rgate\s+{}'.format(coreTokens.gate)))
OAQEQASM.add(Token('exit', 'exit'))
OAQEQASM.add(Token('let', 'let\s+(?P<var>{}) = (?P<val>{})'.format(coreTokens.validName, coreTokens.carg)))
OAQEQASM.add(Token('output', 'output\s+{}'.format(coreTokens.namedParam)))
OAQEQASM.add(Token('alias','alias\s+(?P<alias>{}) -> {}'.format(coreTokens.validName, coreTokens.namedQubit)))

OAQEQASM = OAQEQASM + openQASM
