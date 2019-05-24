from pyparsing import *

ParserElement.enablePackrat()

# Versions are considered over-layered enhancements
versions   = ("OPENQASM", "REQASM", "OMEQASM")
versioning = {None:0} # Default is always available
for i in versions: # None is always 0
    versioning[i] = versions.index(i)+1

def parseVersion(versionIn):
    if isinstance(versionIn, str):
        QASM, versionNo = versionIn.split()
        version = versioning.get(QASM,None), *map(int,versionNo.split("."))
    elif isinstance(versionIn, tuple):
        version = versionIn
    elif versionIn is None:
        return versioning[versionIn]
    else:
        raise IOError("Typo in version statement {}".format(versionIn))
    return version


cops = {}
qops = {}
blocks = {}
_reservedKeys = []
reserved = None

def _overrideKeyword(toks, name):
    toks["keyword"]=name
def _setVersion(toks, version):
    toks["reqVersion"] = version

def ungroup_non_groups(string,l,tokens):
    for i in range(len(tokens)):
        currToken = tokens[i]
        if len(currToken) == 1:
            tokens[i] = currToken[0]

def _setup_QASMParser():

    global reserved
    
    class _Op:

        def __init__(self, name, argParser, version = "OPENQASM 2.0", qop = False, keyOverride = None):
            global cops
            global qops
            global _reservedKeys
            if name in qops or name in cops: raise IOError(f'{name} already defined')
            self.operation = name
            if keyOverride is not None:
                self.parser = (keyOverride + argParser).addParseAction(lambda s,l,t: _overrideKeyword(t, name))
            else:
                self.parser = Keyword(name)("keyword") + argParser

            self.version = parseVersion(version)
            self.parser.addParseAction(lambda s,l,t: _setVersion(t, self.version))
            
            _reservedKeys.append(name)
            if qop:
                qops[name] = self
            else:
                cops[name] = self

    class _Routine(_Op):
        def __init__(self, name, pargs = False, spargs = False, gargs = False, qargs = False,
                     returnables = False, prefixes = None, version = "OPENQASM 2.0" ):
            global blocks
            global _reservedKeys
            if name in qops or name in cops: raise IOError(f'{name} already defined')
            self.operation = name

            self.parser = Keyword(name)("keyword") + validName("gateName")
            if prefixes: self.parser = Each(map(Optional, map(Keyword, prefixes)) )("attributes") + self.parser

            # Handle different args
            req = []
            if pargs: req.append(Optional(pargParser)("pargs"))
            if spargs: req.append(Optional(spargParser)("spargs"))
            if gargs: req.append(Optional(gargParser)("gargs"))
            self.parser = self.parser + Each(req)
            if qargs: self.parser = self.parser + qargParser("qargs")
            if returnables: self.parser = self.parser + returnParser

            self.version = parseVersion(version)
            self.parser.addParseAction(lambda s,l,t: _setVersion(t, self.version))

            _reservedKeys.append(name)
            blocks[name] = self

    class _Block(_Op):
        def __init__(self, name, detParser, version = "OPENQASM 2.0"):
            global blocks
            global _reservedKeys
            self.operation = name
            self.parser = Keyword(name)("keyword") + detParser

            self.version = parseVersion(version)
            self.parser.addParseAction(lambda s,l,t: _setVersion(t, self.version))

            _reservedKeys.append(name)
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

    _is_ = Keyword("to").suppress()
    _in_ = Keyword("in").suppress()
    _to_ = Literal("->").suppress()


    commentSyntax = "//"

    dirSyntax = "***"
    dirOpenStr = f"{dirSyntax} begin"
    dirCloseStr = f"{dirSyntax} end"
    dirSyntax = Keyword(dirSyntax)
    dirOpenSyntax  = Keyword(dirOpenStr)
    dirCloseSyntax = Keyword(dirCloseStr)

    intFunc = oneOf("abs rempow countof")
    realFunc = oneOf("abs rempow arcsin arccos arctan sin cos tan exp ln sqrt")
    boolFunc = oneOf("andof orof xorof")

    inL,inS,inR = map(Suppress, "[:]")
    brL,brR = map(Suppress, "()")

    intExp = Forward()
    realExp = Forward()

    index = intExp.setResultsName('index')
    interval = Optional(intExp.setResultsName('start'), default=None) + inS + Optional(intExp.setResultsName('end'), default=None)
    indexRef = Group(inL + index + inR)
    interRef = Group(inL + interval + inR)
    ref = inL + Group(delimitedList(index ^ interval))('ref') + inR
    regNoRef = validName("var")
    regRef   = Group(validName("var") + Optional(ref))
    regMustRef = Group(validName("var") + ref)
    regListNoRef = Group(delimitedList( regNoRef ))
    regListRef = Group(delimitedList( regRef ))
    regListMustRef = Group(delimitedList( regMustRef ))

    intVar = integer | regRef
    realVar = real | integer | pi | e | regRef
    boolVar = boolean | realExp | intExp
    intFuncVar =  intFunc  + brL + Group(Optional(delimitedList(intVar) ))("args") + brR
    realFuncVar = realFunc + brL + Group(Optional(delimitedList(realVar)))("args") + brR
    boolFuncVar = boolFunc + brL + Group(Optional(delimitedList(boolVar)))("args") + brR

    mathOp =  [
        (oneOf("-")  , 1, opAssoc.RIGHT),
        (oneOf("^")  , 2, opAssoc.LEFT),
        (oneOf("* / div"), 2, opAssoc.LEFT),
        (oneOf("+ -"), 2, opAssoc.LEFT)
    ]
    logOp = [
        (oneOf("! not"), 1, opAssoc.RIGHT),
        (oneOf("and or xor"), 2, opAssoc.LEFT),
        (oneOf("< <= == != >= >"), 2, opAssoc.LEFT)
    ]

    intOp =  [(Group(op[0]).setResultsName("op"), op[1], op[2]) for op in mathOp]
    realOp = [(Group(op[0]).setResultsName("op"), op[1], op[2]) for op in mathOp]
    boolOp = [(Group(op[0]).setResultsName("op"), op[1], op[2]) for op in logOp]

    intExp << infixNotation(intFuncVar | intVar, intOp)

    realExp << infixNotation(realFuncVar | realVar, realOp)

    boolExp = infixNotation(boolFuncVar | boolVar, boolOp)

    def setMathType(toks, type_):
        toks["type"] = type_

    mathExp = (intExp.setParseAction(lambda s,l,t: setMathType(t, "int")) ^
               realExp.setParseAction(lambda s,l,t: setMathType(t, "float")) ^
               boolExp.setParseAction(lambda s,l,t: setMathType(t, "bool"))
               )

    op  = []
    qop = []
    blockDelims = []

    procAttr = ["unitary","recursive"]
    callMods = ["CTRL-", "INV-"]

    pargParser = brL + delimitedList(validName)("pargs") + brR
    callPargParser = brL + delimitedList(realExp)("pargs") + brR
    spargParser = inL + delimitedList(validName) + inR
    gargParser = ungroup(nestedExpr("<",">", delimitedList(ungroup(validName)), None))
    qargParser = delimitedList(regRef)
    returnParser = _to_ + validName("byprod")

    modifiers = Group(ZeroOrMore(oneOf(callMods)))

    comment = Literal(commentSyntax).suppress() + restOfLine("comment")
    comment.addParseAction(lambda s,l,t : _setVersion(t, (0,0,0)))

    
    directiveName = Word(alphas)
    directiveArgs = CharsNotIn(";")

    _Op("directive", directiveName("directive") + Suppress(White()*(1,)) + directiveArgs("args"), version= "REQASM 1.0",
        keyOverride = (~dirOpenSyntax + ~dirCloseSyntax + dirSyntax))

    def splitArgs(toks):
        toks[0]["keyword"] = "directive"
        toks[0]["args"] = toks[0]["args"].strip().split(" ")

    directiveBlock = ungroup(nestedExpr(dirOpenSyntax,
                                dirCloseSyntax,
                                content = directiveName("directive") + restOfLine("args") +
                                Group(ZeroOrMore (Combine(Optional(White(" ")) + ~dirCloseSyntax + Word(printables+" "))))("block"),
                                ignoreExpr = comment | quotedString).setWhitespaceChars("\n").setParseAction(splitArgs))
    directiveBlock.addParseAction(lambda s,l,t: _setVersion(t, (2,1,0)))

    # Programming lines
    _Op("version", Empty(),version = None, keyOverride = Combine(oneOf(versions)("type") + White() + real("versionNumber"))("version") )
    _Op("include", quotedString("file").addParseAction(removeQuotes))


    # Gate-like structures
    _Op("opaque", validName("name") + qargParser("qargs"), keyOverride = Each(map(Optional, map(Keyword, procAttr)) )("attributes") + "opaque")
    _Routine("gate", pargs = True, qargs = True, prefixes = procAttr)
    _Routine("circuit", pargs = True, qargs = True, spargs = True, returnables = True, prefixes = procAttr, version = "REQASM 1.0")
    
    # Variable-like structures
    _Op("creg", regRef("arg"))
    _Op("qreg", regRef("arg"))
    _Op("defAlias", regMustRef("alias"), keyOverride = "alias", version = "REQASM 1.0" )
    _Op("alias", regRef("alias") + _is_ + regRef("target"), version = "REQASM 1.0")
    _Op("let", validName("var") + Literal("=").suppress() + Group(mathExp)("val"), version="REQASM 1.0")

    # Operations-like structures
    _Op("measure", regRef("qreg") + _to_ + regRef("creg"), qop = True)
    _Op("barrier", regListNoRef("args"))
    _Op("output", regRef("value"), version = "REQASM 1.0")
    _Op("reset", regRef("qreg"))
    _Op("exit", Empty(), version = "REQASM 1.0")

    _Op("next",   validName("loopVar"), qop = True, version = "REQASM 1.0")
    _Op("escape", validName("loopVar"), qop = True, version = "REQASM 1.0")
    _Op("end",    validName("process"), qop = True, version = "REQASM 1.0")
    
    # Special gate call handler
    callParser =  Optional(callPargParser("pargs")) & Optional(spargParser("spargs")) & Optional(gargParser("gargs"))
    callGate = (modifiers("mods") + validName("gate")) + callParser + regListRef("qargs").addParseAction(lambda s,l,t: _overrideKeyword(t, "call"))
    callGate.addParseAction(lambda s,l,t: _setVersion(t, (1,2,0)))


    # Block structures
    _Block("for", validName("var") + _in_ + interRef("range"), version = "REQASM 1.0")
    _Block("if", "(" + Group(boolExp)("cond") + ")", version = "REQASM 1.0")
    _Block("while", "(" + Group(boolExp)("cond") + ")", version = "OMEQASM 1.0")

    qopsParsers = list(map ( lambda qop: qop.parser, qops.values())) + [callGate]
    blocksParsers = list(map ( lambda block: block.parser, blocks.values()))

    _Op("if", blocks["if"].parser       + Group(Group(Group(Or(qopsParsers))))("block"), version="OPENQASM 2.0", keyOverride = Empty())
    _Op("for", blocks["for"].parser     + Group(Group(Group(Or(qopsParsers))))("block"), version="REQASM 1.0", keyOverride = Empty())
    _Op("while", blocks["while"].parser + Group(Group(Group(Or(qopsParsers))))("block"), version="OMEQASM 1.0", keyOverride = Empty())

    # Set-up line parsers    
    reserved = Or(_reservedKeys) ^ e ^ pi
    validName << (~reserved) + Word(alphas,alphanums+"_")

    copsParsers = list(map ( lambda cop: cop.parser, cops.values()))

    operations = ( (Or(copsParsers) ^ Or(qopsParsers)) | callGate ) + lineEnd.suppress()

    validLine = Forward()
    codeBlock = nestedExpr("{","}", Suppress(White()) ^ Group(validLine), (quotedString))

    validLine <<= (  (
        (operations + Optional(comment)) ^
        (Or(blocksParsers) + codeBlock("block")) ^
                comment))                              # Whole line comment

    testLine = Forward()
    dummyCodeBlock = nestedExpr("{","}", testLine, (quotedString | comment))
    
    testLine <<= directiveBlock | ((~dirOpenSyntax + ~dirCloseSyntax + CharsNotIn("{;")) + lineEnd) ^ (CharsNotIn("{") + dummyCodeBlock) ^ comment
    
    testKeyword = dirSyntax.setParseAction(lambda s,l,t: _overrideKeyword(t, "directive")) | Word(alphas)("keyword")

    code = (Group(directiveBlock)) | Group(validLine)

    return code, testLine, testKeyword

QASMcodeParser, lineParser, errorKeywordParser = _setup_QASMParser()
