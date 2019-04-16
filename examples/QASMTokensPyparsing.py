from pyparsing import *

cops = {}
qops = {}
blocks = {}

class _Op:

    def __init__(self, name, argParser, version = "OPENQASM", qop = False, keyOverride = None):
        global cops
        global qops
        
        if name in qops or name in cops: raise IOError(f'{name} already defined')
        self.operation = name
        if keyOverride is not None:
            def overrideKeyword(toks):
                toks["keyword"]=name
            self.parser = (keyOverride + argParser).addParseAction(overrideKeyword)
        else:
            self.parser = Keyword(name)("keyword") + argParser

        self.version = version

        if qop:
            qops[name] = self
        else:
            cops[name] = self
            
class _Routine(_Op):
    def __init__(self, name, pargs = False, spargs = False, gargs = False, qargs = False,
                 returnable = False, prefixes = None, version = "OPENQASM"):
        global cops
        global qops
        if name in qops or name in cops: raise IOError(f'{name} already defined')
        self.operation = name

        self.parser = Keyword(name)("keyword")
        
        if prefixes: self.parser = Each( map(Optional,prefixes) ) + self.parser
        
        # Handle different args
        req = []
        if pargs: req.append(pargParser)
        if spargs: req.append(spargParser)
        if gargs: req.append(gargParser)
        self.parser = self.parser + Each(req)
        if qargs: self.parser = self.parser + qargParser
        if returnable: self.parser = self.parser + returnParser
        
        blocks[name] = self

class _Block(_Op):


    def __init__(self, name, detParser, version = "OPENQASM"):
        global blocks
        self.operation = name
        self.parser = Keyword(name)("keyword") + detParser
        blocks[name] = self

        
class _BlockMark():

    delims = []
    
    def __init__(self, name, startDelim, endDelim, contents):

        _Block.delims.append( (startDelim, endDelim) )
        self.name = name
        self.parser = nestedExpr(startDelim, endDelim, contents, (quotedString | comment))

    
sign = Word("+-", exact=1)
number = Word(nums)
expo = Combine(CaselessLiteral("e") + Optional(sign) + number).setResultsName("exponent")

e = CaselessKeyword("e")
pi = CaselessKeyword("pi")

integer  = Combine( number + Optional(expo))
real = Combine( Optional(sign) + ( Combine("." + number) | Combine( number + "." + Optional(number) ) ) + Optional(expo))
boolean = Word("TF", exact=1)
validName = Combine( ~e + ~pi + Word(alphas,alphanums+"_") )
lineEnd = Literal(";")

_in_ = Keyword("in").suppress()
toClass = Literal("->").suppress()

intFunc = oneOf("abs rempow")
realFunc = Or(intFunc, oneOf("arcsin arccos arctan sin cos tan exp ln sqrt"))

inL,inS,inR = map(Suppress, "[:]")

intExp  = infixNotation(
    integer | validName,
    [
        (intFunc, 1, opAssoc.RIGHT),
        (oneOf("-")  , 1, opAssoc.RIGHT),
        (oneOf("^")  , 2, opAssoc.LEFT),
        (oneOf("* / //"), 2, opAssoc.LEFT),
        (oneOf("+ -"), 2, opAssoc.LEFT)
    ]
)


realExp = infixNotation(
    integer | real | validName | pi | e,
    [
        (realFunc, 1, opAssoc.RIGHT),
        (oneOf("-")  , 1, opAssoc.RIGHT),
        (oneOf("^")  , 2, opAssoc.LEFT),
        (oneOf("* / //"), 2, opAssoc.LEFT),
        (oneOf("+ -"), 2, opAssoc.LEFT)
    ]
)

boolExp = infixNotation(
    boolean | realExp | intExp,
    [
        (oneOf("! not"), 1, opAssoc.RIGHT),
        (oneOf("and or xor"), 2, opAssoc.LEFT),
        (oneOf("orof xorof andof"), 1, opAssoc.RIGHT),
        (oneOf("< <= == != => >"), 2, opAssoc.LEFT)
    ]
)

mathExp = realExp ^ intExp ^ boolExp

index = inL + intExp.setResultsName('index') + inR
interval = inL + Optional(intExp.setResultsName('start'), default=None) + inS + Optional(intExp.setResultsName('end'), default=None) + inR
ref = index ^ interval

op  = []
qop = []
blockDelims = []

procAttr = ["unitary"]
callMods = ["CTRL-", "INV-"] 


regListNoRef = Group(delimitedList(validName))
regListRef = Group(delimitedList( Group(validName + Optional(ref)) ))
regListMustRef = Group(delimitedList( Group(validName + ref) ))

pargParser = nestedExpr("(",")", delimitedList(realExp), None)("pargs")
spargParser = nestedExpr("[","]", delimitedList(realExp), None)("spargs")
gargParser = nestedExpr("<",">", delimitedList(validName), None)("gargs")
qargParser = regListRef("qargs")

modifiers = Group(ZeroOrMore(oneOf(callMods)))
attributes  = Each( map(Optional, map(Keyword, procAttr)) )("attributes")

comment = Keyword("//").suppress() + restOfLine("comment")

_Op("directive", Word(alphanums)("directive") + CharsNotIn(";")("args"), version="REQASM", keyOverride = Keyword("**"))

directiveBlock = originalTextFor(nestedExpr("** begin", "** end"))

_Op("let", validName("var") + Literal("=").suppress() + mathExp("val"), version="REQASM")
_Op("version", real("versionNumber"), version = None, keyOverride = Keyword("REQASM")^Keyword("OPENQASM") )
_Op("include", quotedString("file").addParseAction(removeQuotes))
_Op("opaque", validName("name") + regListNoRef("args"), keyOverride = attributes + "opaque")
_Routine("gate", pargs = True, qargs = True, prefixes = attributes)
_Op("creg", validName("name") + Optional(index))
_Op("qreg", validName("name") + Optional(index))
_Op("call", Group(Each( map(Optional,[pargParser,spargParser,gargParser]) )) + regListRef,
                        qop = True, keyOverride = (modifiers("mods") + validName("gate")) )
_Op("measure", validName("qreg") + toClass + validName("creg"), qop = True)
_Op("barrier", regListNoRef("args"))
_Block("for", validName("var") + _in_ + interval, version = "REQASM")
_Block("if", "(" + boolExp("cond") + ")", version = "REQASM")
_Block("while", "(" + boolExp("cond") + ")", version = "REQASM")


qopsParsers = list(map ( lambda qop: qop.parser, qops.values()))
blocksParsers = list(map ( lambda block: block.parser, blocks.values()))

_Op("ifLine", blocks["for"].parser + Or(qopsParsers) , keyOverride = Keyword("if"))
_Op("forLine", blocks["for"].parser + Or(qopsParsers), version="REQASM", keyOverride = Keyword("for"))
_Op("whileLine", blocks["while"].parser + Or(qopsParsers), version="REQASM", keyOverride = Keyword("while"))

copsParsers = list(map ( lambda cop: cop.parser, cops.values()))

operations = ( Or(copsParsers) ^ Or(qopsParsers) ) + lineEnd.suppress()

validLine = Forward()
codeBlock =  ungroup(nestedExpr("{","}", Group(validLine), (quotedString | comment)))
validLine << (    (
    (operations + Optional(comment)) ^
    (Or(blocksParsers) + Optional(comment) + codeBlock("Block")) ^
            comment))                              # Whole line comment
       



code = (directiveBlock) | validLine # ^ codeBlock

with open("test.qasm","r") as current:
    for lines in code.searchString(current.read()):
        print(lines.dump())
