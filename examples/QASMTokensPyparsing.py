from pyparsing import *

ParserElement.enablePackrat()

cops = {}
qops = {}
blocks = {}
reservedKeys = []

class _Op:

    def __init__(self, name, argParser, version = "OPENQASM", qop = False, keyOverride = None):
        global cops
        global qops
        global reservedKeys
        if name in qops or name in cops: raise IOError(f'{name} already defined')
        self.operation = name
        if keyOverride is not None:
            def overrideKeyword(toks):
                toks["keyword"]=name
            self.parser = (keyOverride + argParser).addParseAction(overrideKeyword)
        else:
            self.parser = Keyword(name)("keyword") + argParser

        self.version = version

        reservedKeys.append(name)
        if qop:
            qops[name] = self
        else:
            cops[name] = self
            
class _Routine(_Op):
    def __init__(self, name, pargs = False, spargs = False, gargs = False, qargs = False,
                 returnable = False, prefixes = None, version = "OPENQASM"):
        global cops
        global qops
        global reservedKeys
        if name in qops or name in cops: raise IOError(f'{name} already defined')
        self.operation = name

        self.parser = Keyword(name)("keyword") + validName("gateName")
        
        if prefixes: self.parser = Each( map(Optional,prefixes) ) + self.parser
        
        # Handle different args
        req = []
        if pargs: req.append(Optional(pargParser))
        if spargs: req.append(Optional(spargParser))
        if gargs: req.append(Optional(gargParser))
        self.parser = self.parser + Each(req)
        if qargs: self.parser = self.parser + qargParser
        if returnable: self.parser = self.parser + returnParser
        
        blocks[name] = self

class _Block(_Op):


    def __init__(self, name, detParser, version = "OPENQASM"):
        global blocks
        global reservedKeys
        self.operation = name
        self.parser = Keyword(name)("keyword") + detParser
        reservedKeys.append(name)
        blocks[name] = self

        
    
sign = Word("+-", exact=1)
number = Word(nums)
expo = Combine(CaselessLiteral("e") + Optional(sign) + number).setResultsName("exponent")

e = CaselessKeyword("e")
pi = CaselessKeyword("pi")

integer  = Combine( number + Optional(expo))
real = Combine( Optional(sign) + ( ("." + number) ^ ( number + "." + Optional(number) ) ) + Optional(expo))
boolean = Word("TF", exact=1)
validName = Forward()
lineEnd = Literal(";")

_is_ = Keyword("is").suppress()
_in_ = Keyword("in").suppress()
toClass = Literal("->").suppress()

intFunc = oneOf("abs rempow")
realFunc = Or(intFunc, oneOf("arcsin arccos arctan sin cos tan exp ln sqrt"))

inL,inS,inR = map(Suppress, "[:]")

intExp = Forward()
realExp = Forward()

index = intExp.setResultsName('index')
interval = Optional(intExp.setResultsName('start'), default=None) + inS + Optional(intExp.setResultsName('end'), default=None)
ref = inL + delimitedList(index ^ interval) + inR
regNoRef = validName("var")
regRef   = Group(validName("var") + Optional(ref))
regMustRef = Group(validName("var") + ref)
regListNoRef = Group(delimitedList( regNoRef ))
regListRef = Group(delimitedList( regRef ))
regListMustRef = Group(delimitedList( regMustRef ))


intExp << infixNotation(
    integer ^ regRef,
    [
        (intFunc, 1, opAssoc.RIGHT),
        (oneOf("-")  , 1, opAssoc.RIGHT),
        (oneOf("^")  , 2, opAssoc.LEFT),
        (oneOf("* / //"), 2, opAssoc.LEFT),
        (oneOf("+ -"), 2, opAssoc.LEFT)
    ]
)


realExp << infixNotation(
    real ^ integer ^ pi ^ e ^ regRef,
    [
        (realFunc, 1, opAssoc.RIGHT),
        (oneOf("-")  , 1, opAssoc.RIGHT),
        (oneOf("^")  , 2, opAssoc.LEFT),
        (oneOf("* / //"), 2, opAssoc.LEFT),
        (oneOf("+ -"), 2, opAssoc.LEFT)
    ]
)

boolExp = infixNotation(
    boolean ^ realExp ^ intExp,
    [
        (oneOf("! not"), 1, opAssoc.RIGHT),
        (oneOf("and or xor"), 2, opAssoc.LEFT),
        (oneOf("orof xorof andof"), 1, opAssoc.RIGHT),
        (oneOf("< <= == != => >"), 2, opAssoc.LEFT)
    ]
)

mathExp = realExp ^ intExp ^ boolExp


op  = []
qop = []
blockDelims = []

procAttr = ["unitary recursive"]
callMods = ["CTRL-", "INV-"] 

pargParser = nestedExpr("(",")", delimitedList(realExp), None)
spargParser = nestedExpr("[","]", delimitedList(realExp), None)
gargParser = nestedExpr("<",">", delimitedList(validName), None)
qargParser = regListRef("qargs")

modifiers = Group(ZeroOrMore(oneOf(callMods)))
attributes  = Each( map(Optional, map(Keyword, procAttr)) )("attributes")

comment = Literal("//").suppress() + restOfLine("comment")

_Op("directive", Word(alphanums)("directive") + CharsNotIn(";")("args"), version="REQASM", keyOverride = Keyword("**"))

directiveBlock = originalTextFor(nestedExpr("**begin", "**end"))

_Op("let", validName("var") + Literal("=").suppress() + mathExp("val"), version="REQASM")
_Op("version", real("versionNumber"), version = None, keyOverride = Keyword("REQASM")^Keyword("OPENQASM") )
_Op("include", quotedString("file").addParseAction(removeQuotes))
_Op("opaque", validName("name") + regListNoRef("qargs"), keyOverride = attributes + "opaque")
_Routine("gate", pargs = True, qargs = True, prefixes = attributes)
_Op("creg", validName("name") + Optional(index))
_Op("qreg", validName("name") + Optional(index))


_Op("measure", regRef("qreg") + toClass + regRef("creg"), qop = True)
_Op("barrier", regListNoRef("args"))
_Op("alias", regRef("alias") + _is_ + regRef("target"), version = "REQASM")
_Op("output", regRef("value"), version = "REQASM")

_Block("for", validName("var") + _in_ + interval, version = "REQASM")
_Block("if", "(" + boolExp("cond") + ")", version = "REQASM")
_Block("while", "(" + boolExp("cond") + ")", version = "REQASM")

callParser =  Optional(pargParser("pargs")) & Optional(spargParser("spargs")) & Optional(gargParser("gargs"))
callGate = (modifiers("mods") + validName("gate")) + callParser + regListRef("qargs")


qopsParsers = list(map ( lambda qop: qop.parser, qops.values())) + [callGate]
blocksParsers = list(map ( lambda block: block.parser, blocks.values()))

_Op("if", blocks["if"].parser + Group(Or(qopsParsers))("Block"), keyOverride = Empty())
_Op("for", blocks["for"].parser + Group(Or(qopsParsers))("Block"), version="REQASM", keyOverride = Empty())
_Op("while", blocks["while"].parser + Group(Or(qopsParsers))("Block"), version="REQASM", keyOverride = Empty())

reserved = Or(reservedKeys) ^ e ^ pi
validName << (~reserved) + Word(alphas,alphanums+"_")

print(validName)

copsParsers = list(map ( lambda cop: cop.parser, cops.values()))

operations = ( (Or(copsParsers) ^ Or(qopsParsers)) | callGate ) + lineEnd.suppress()

validLine = Forward()
codeBlock =  nestedExpr("{","}", Group(validLine), (quotedString | comment))

validLine << (    (
    (operations + Optional(comment)) ^
    (Or(blocksParsers) + Optional(comment) + codeBlock("Block")) ^
            comment))                              # Whole line comment

testLine = (CharsNotIn("{;") + lineEnd) ^ (CharsNotIn("{") + codeBlock) ^ directiveBlock
testKeyword = Word(alphas)("keyword")

code = (Group(directiveBlock)) | Group(validLine)

currentLine = ""
with open("test.qasm","r") as current:
    for line in current:
        if not line.strip(): continue
        currentLine += line
        *test, = testLine.scanString(currentLine)
        if not test or test[0][1] != 0: continue
        try:
            print(f"'{currentLine}'")
            print(code.parseString(currentLine).dump())
            currentLine = ""
        except ParseException as err:
            print(err.line)
            print(" "*(err.column-1) + "^")
            problem = testKeyword.parseString(err.line)
            try:
                if problem["keyword"] in qops.keys():
                    qops[problem["keyword"]].parser.parseString(err.line)
                elif problem["keyword"] in cops.keys():
                    cops[problem["keyword"]].parser.parseString(err.line)
                else:
                    print("Unrecognised instruction: {} not found in {} format".format(problem["keyword"], "QASM"))
            except ParseException as subErr:
                print(subErr)
            quit()
    if currentLine:
        try:
            print(code.parseString(line).dump())
        except ParseException as err:
            print("Error : ")
            print(err.line)
            print(" "*(err.column-1) + "^")
            #print(err)
            quit()
        
    # for lines in code.searchString(current.read()):
    #     print(lines.dump())
    # try:
    #     print(code.parseString(current.read(),parseAll=True).dump())
    # except ParseException as err:
    #     print(err.line)
    #     print(" "*(err.column-1) + "^")
    #     print(err)
        
