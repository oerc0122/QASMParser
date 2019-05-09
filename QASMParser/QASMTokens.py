from pyparsing import *

ParserElement.enablePackrat()

cops = {}
qops = {}
_blocks = {}
_reservedKeys = []

def _overrideKeyword(toks, name):
    toks["keyword"]=name

def ungroup_non_groups(string,l,tokens):
    for i in range(len(tokens)):
        currToken = tokens[i]
        if len(currToken) == 1:
            tokens[i] = currToken[0]
    
        
def _setup_QASMParser():    

    class _Op:
    
        def __init__(self, name, argParser, version = "OPENQASM", qop = False, keyOverride = None):
            global cops
            global qops
            global _reservedKeys
            if name in qops or name in cops: raise IOError(f'{name} already defined')
            self.operation = name
            if keyOverride is not None:
                self.parser = (keyOverride + argParser).addParseAction(lambda s,l,t: _overrideKeyword(t, name))
            else:
                self.parser = Keyword(name)("keyword") + argParser
    
            self.version = version
    
            _reservedKeys.append(name)
            if qop:
                qops[name] = self
            else:
                cops[name] = self
                
    class _Routine(_Op):
        def __init__(self, name, pargs = False, spargs = False, gargs = False, qargs = False,
                     returnable = False, prefixes = None, version = "OPENQASM"):
            global cops
            global qops
            global _reservedKeys
            if name in qops or name in cops: raise IOError(f'{name} already defined')
            self.operation = name
    
            self.parser = Keyword(name)("keyword") + validName("gateName")
            
            if prefixes: self.parser = Each( map(Optional,prefixes) ) + self.parser
            
            # Handle different args
            req = []
            if pargs: req.append(Optional(pargParser)("pargs"))
            if spargs: req.append(Optional(spargParser)("spargs"))
            if gargs: req.append(Optional(gargParser)("gargs"))
            self.parser = self.parser + Each(req)
            if qargs: self.parser = self.parser + qargParser("qargs")
            if returnable: self.parser = self.parser + returnParser
            
            _blocks[name] = self
    
    class _Block(_Op):
        def __init__(self, name, detParser, version = "OPENQASM"):
            global _blocks
            global _reservedKeys
            self.operation = name
            self.parser = Keyword(name)("keyword") + detParser
            _reservedKeys.append(name)
            _blocks[name] = self
    
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
    
    
    commentSyntax = "//"
    
    dirSyntax = "***"
    dirOpenStr = f"{dirSyntax} begin"
    dirCloseStr = f"{dirSyntax} end"
    dirSyntax = Keyword(dirSyntax)
    dirOpenSyntax  = Keyword(dirOpenStr)
    dirCloseSyntax = Keyword(dirCloseStr)
    
    intFunc = oneOf("abs rempow")
    realFunc = Or(intFunc, oneOf("arcsin arccos arctan sin cos tan exp ln sqrt"))
    
    inL,inS,inR = map(Suppress, "[:]")
    
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

    intVar = integer ^ regRef
    realVar = real ^ integer ^ pi ^ e ^ regRef
    boolVar = boolean ^ realExp ^ intExp
    mathOp =  [
        (oneOf("-")  , 1, opAssoc.RIGHT),
        (oneOf("^")  , 2, opAssoc.LEFT),
        (oneOf("* / div"), 2, opAssoc.LEFT),
        (oneOf("+ -"), 2, opAssoc.LEFT)
    ]
    logOp = [
        (oneOf("! not"), 1, opAssoc.RIGHT),
        (oneOf("and or xor"), 2, opAssoc.LEFT),
        (oneOf("orof xorof andof"), 1, opAssoc.RIGHT),
        (oneOf("< <= == != >= >"), 2, opAssoc.LEFT)
    ]

   
    intOp = [(Group(op[0]).setResultsName("op"), op[1], op[2]) for op in [(intFunc, 1, opAssoc.RIGHT)] + mathOp]
    realOp = [(Group(op[0]).setResultsName("op"), op[1], op[2]) for op in [(realFunc, 1, opAssoc.RIGHT)] + mathOp]
    boolOp = [(Group(op[0]).setResultsName("op"), op[1], op[2]) for op in logOp]

    intOp = [(intFunc, 1, opAssoc.RIGHT)] + mathOp
    realOp = [(realFunc, 1, opAssoc.RIGHT)] + mathOp
    boolOp = logOp
    
    intExp << infixNotation(intVar, intOp)
   
    realExp << infixNotation(realVar, realOp)
    
    boolExp = infixNotation(boolVar, boolOp)
    
    mathExp = (intExp | realExp) ^ boolExp
    
    
    op  = []
    qop = []
    blockDelims = []
    
    procAttr = ["unitary recursive"]
    callMods = ["CTRL-", "INV-"] 

    pargParser = nestedExpr("(",")", delimitedList(realExp.addParseAction(ungroup_non_groups)), None)
    spargParser = ungroup(nestedExpr("[","]", delimitedList(realExp.addParseAction(ungroup_non_groups)), None))
    gargParser = ungroup(nestedExpr("<",">", delimitedList(ungroup(validName)), None))
    qargParser = Group(delimitedList( regNoRef ))

    
    modifiers = Group(ZeroOrMore(oneOf(callMods)))
    attributes  = Each( map(Optional, map(Keyword, procAttr)) )("attributes")
    
    comment = Literal(commentSyntax).suppress() + restOfLine("comment")
    
    directiveName = Word(alphas)
    directiveArgs = CharsNotIn(";") #Group(ZeroOrMore((Word( alphas ) | quotedString | mathExp))) 
    
    _Op("directive", directiveName("directive") + Suppress(White()*(1,)) + directiveArgs("args"), version="REQASM",
        keyOverride = (~dirOpenSyntax + ~dirCloseSyntax + dirSyntax))
    
    def splitArgs(toks):
        toks[0]["keyword"] = "directive"
        toks[0]["args"] = toks[0]["args"].strip().split(" ")
    
    directiveBlock = ungroup(nestedExpr(dirOpenSyntax,
                                dirCloseSyntax,
                                content = directiveName("directive") + restOfLine("args") +
                                Group(ZeroOrMore (Combine(Optional(White(" ")) + ~dirCloseSyntax + Word(printables+" "))))("block"), 
                                ignoreExpr = comment | quotedString).setWhitespaceChars("\n").setParseAction(splitArgs))
    
    
    _Op("let", validName("var") + Literal("=").suppress() + mathExp("val"), version="REQASM")
    _Op("version", real("versionNumber"), version = None, keyOverride = (Keyword("REQASM")^Keyword("OPENQASM"))("type") )
    _Op("include", quotedString("file").addParseAction(removeQuotes))
    _Op("opaque", validName("name") + regListNoRef("qargs"), keyOverride = attributes + "opaque")
    _Routine("gate", pargs = True, qargs = True, prefixes = attributes)
    _Op("creg", regRef("arg"))
    _Op("qreg", regRef("arg"))
    
    
    _Op("measure", regRef("qreg") + toClass + regRef("creg"), qop = True)
    _Op("barrier", regListNoRef("args"))
    _Op("alias", regRef("alias") + _is_ + regRef("target"), version = "REQASM")
    _Op("output", regRef("value"), version = "REQASM")
    _Op("reset", regRef("qreg"))
    
    _Block("for", validName("var") + _in_ + interRef("range"), version = "REQASM")
    _Block("if", "(" + boolExp("cond") + ")", version = "REQASM")
    _Block("while", "(" + boolExp("cond") + ")", version = "REQASM")
    
    callParser =  Optional(pargParser("pargs")) & Optional(spargParser("spargs")) & Optional(gargParser("gargs"))
    callGate = (modifiers("mods") + validName("gate")) + callParser + regListRef("qargs").addParseAction(lambda s,l,t: _overrideKeyword(t, "call"))
    
    
    qopsParsers = list(map ( lambda qop: qop.parser, qops.values())) + [callGate]
    blocksParsers = list(map ( lambda block: block.parser, _blocks.values()))
    
    _Op("if", _blocks["if"].parser       + Group(Group(Group(Or(qopsParsers))))("block"), keyOverride = Empty())
    _Op("for", _blocks["for"].parser     + Group(Group(Group(Or(qopsParsers))))("block"), version="REQASM", keyOverride = Empty())
    _Op("while", _blocks["while"].parser + Group(Group(Group(Or(qopsParsers))))("block"), version="REQASM", keyOverride = Empty())
    
    reserved = Or(_reservedKeys) ^ e ^ pi
    validName << (~reserved) + Word(alphas,alphanums+"_")
    
    copsParsers = list(map ( lambda cop: cop.parser, cops.values()))
    
    operations = ( (Or(copsParsers) ^ Or(qopsParsers)) | callGate ) + lineEnd.suppress()
    
    validLine = Forward()
    codeBlock = nestedExpr("{","}", Group(validLine), (quotedString | comment))
    
    validLine << (    (
        (operations + Optional(comment)) ^
        (Or(blocksParsers) + Optional(comment) + codeBlock("block")) ^
                comment))                              # Whole line comment
    
    testLine = directiveBlock | ((~dirOpenSyntax + ~dirCloseSyntax + CharsNotIn("{;")) + lineEnd) ^ (CharsNotIn("{") + codeBlock) ^ comment
    testKeyword = dirSyntax.setParseAction(lambda s,l,t: _overrideKeyword(t, "directive")) | Word(alphas)("keyword")
    
    code = (Group(directiveBlock)) | Group(validLine)

    return code, testLine, testKeyword
        
QASMcodeParser, lineParser, errorKeywordParser = _setup_QASMParser()
