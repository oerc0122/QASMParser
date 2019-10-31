"""
Module containing parsing tokens for reading QASM.
"""

from pyparsing import (ParserElement,
                       CaselessKeyword, Keyword, Literal, CaselessLiteral,
                       Empty, White, CharsNotIn, Word,
                       Group, Combine,
                       ungroup, removeQuotes, downcaseTokens,
                       Or, Each, oneOf, Optional, ZeroOrMore,
                       alphas, alphanums, nums, printables,
                       nestedExpr, delimitedList, restOfLine, quotedString, cStyleComment,
                       infixNotation, opAssoc, Forward,
                       Suppress)

from .QASMErrors import (QASMWarning, dupTokenWarning)

ParserElement.enablePackrat()

# Versions are considered over-layered enhancements
versions = ("OPENQASM", "REQASM", "OMEQASM")
versionDict = dict((index, version) for version, index in enumerate(versions, 1))
versionDict[None] = 0

def parse_version(versionIn):
    """Translate version string into tuple."""
    if isinstance(versionIn, str):
        QASM, versionNo = versionIn.split()
        version = versionDict.get(QASM, None), *map(int, versionNo.split("."))
    elif isinstance(versionIn, tuple):
        version = versionIn
    elif versionIn is None:
        return versionDict[versionIn]
    else:
        raise IOError(QASMWarning.format(versionIn))
    return version


cops = {}
qops = {}
blocks = {}
_reservedKeys = []

def _override_keyword(toks, name):
    """Set returned keyword to be name instead of the parser key."""
    toks["keyword"] = name
def _set_version(toks, version):
    """ Apply version to parsing tokens. """
    toks["reqVersion"] = version

def ungroup_non_groups(tokens):
    """ Ungroup groups which contain only one element."""
    for i, currToken in enumerate(tokens):
        if len(currToken) == 1:
            tokens[i] = currToken[0]

# Maths classes

class MathOp:
    """Abstract base class for subclassing maths operations"""

class Binary(MathOp):
    """
    Mathematical binary and unary operations (including nop).

    Parses tokens to be a list of elementary operations.
    """
    def __init__(self, tokens):
        tokens = tokens[0]
        if len(tokens)%2 == 1:
            self.args = [("nop", tokens.pop(0))]
        else: self.args = []
        while tokens:
            self.args.append(
                (tokens.pop(0), tokens.pop(0))
            )

class Function(MathOp):
    """ Mathematical functions token """
    def __init__(self, tokens):
        self.op = tokens[0]
        self.args = tokens["args"]


def _setup_QASMParser():
    """
    Routine to initialise and return parsing blocks
    """

    class _Op:
        """ Class to set up quantum operations """
        def __init__(self, name, argParser, version="OPENQASM 2.0", qop=False, keyOverride=None):
            global cops
            global qops
            global _reservedKeys
            if name in qops or name in cops:
                raise IOError(dupTokenWarning.format("Operation", name))
            self.operation = name
            if keyOverride is not None:
                self.parser = (keyOverride + argParser).addParseAction(lambda s, l, t: _override_keyword(t, name))
            else:
                self.parser = CaselessKeyword(name)("keyword") + argParser

            self.version = parse_version(version)
            self.parser.addParseAction(lambda s, l, t: _set_version(t, self.version))

            _reservedKeys.append(name)
            if qop:
                qops[name] = self
            else:
                cops[name] = self

    class _Routine():
        """ Class to set up quantum gates, circuits, etc. """
        def __init__(self, name, pargs=False, spargs=False, gargs=False, qargs=False,
                     returnables=False, prefixes=None, version="OPENQASM 2.0"):
            global blocks
            global _reservedKeys
            if name in qops or name in cops:
                raise IOError(dupTokenWarning.format("Routine", name))
            self.operation = name

            self.parser = Keyword(name)("keyword") + validName("gateName")


            if prefixes:
                localPrefixParser = Each(map(Optional, map(Keyword, prefixes))).addParseAction(prefix_setter)
            else:
                localPrefixParser = prefixParser
            self.parser = localPrefixParser + self.parser

            # Handle different args
            req = []
            if pargs:
                req.append(Optional(pargParser)("pargs"))
            if spargs:
                req.append(Optional(spargParser)("spargs"))
            if gargs:
                req.append(Optional(gargParser)("gargs"))
            self.parser = self.parser + Each(req)
            if qargs:
                self.parser = self.parser + qargParser("qargs")
            if returnables:
                self.parser = self.parser + Optional(returnParser)

            self.version = parse_version(version)
            self.parser.addParseAction(lambda s, l, t: _set_version(t, self.version))

            _reservedKeys.append(name)
            blocks[name] = self

    class _Block():
        """ Class to set up blocks such as if, for, etc. """
        def __init__(self, name, detParser, version="OPENQASM 2.0"):
            global blocks
            global _reservedKeys
            self.operation = name
            self.parser = Keyword(name)("keyword") + detParser

            self.version = parse_version(version)
            self.parser.addParseAction(lambda s, l, t: _set_version(t, self.version))

            _reservedKeys.append(name)
            blocks[name] = self

    sign = Word("+-", exact=1)
    number = Word(nums)
    expo = Combine(CaselessLiteral("e") + Optional(sign) + number).setResultsName("exponent")

    e = CaselessKeyword("e")
    pi = CaselessKeyword("pi")

    integer = Combine(number + Optional(expo))
    real = Combine(Optional(sign) + (("." + number) ^ (number + "." + Optional(number))) + Optional(expo))
    boolean = Word("TF", exact=1)
    validName = Forward()
    lineEnd = Literal(";")

    _is_ = Keyword("to").suppress()
    _in_ = Keyword("in")
    _to_ = Literal("->").suppress()


    commentSyntax = "//"
    commentOpenStr = "/*"
    commentCloseStr = "*/"
    commentOpenSyntax = Literal(commentOpenStr)
    commentCloseSyntax = Literal(commentCloseStr)

    dirSyntax = "***"
    dirOpenStr = f"{dirSyntax} begin"
    dirCloseStr = f"{dirSyntax} end"

    dirSyntax = Keyword(dirSyntax)
    dirOpenSyntax = CaselessLiteral(dirOpenStr)
    dirCloseSyntax = CaselessLiteral(dirCloseStr)

    intFunc = oneOf("abs rempow countof fllog")
    realFunc = oneOf("abs rempow arcsin arccos arctan sin cos tan exp ln sqrt")
    boolFunc = oneOf("andof orof xorof")

    inL, inS, inR = map(Suppress, "[:]")
    brL, brR = map(Suppress, "()")

    intExp = Forward()
    realExp = Forward()
    boolExp = Forward()

    index = intExp.setResultsName("index")
    interval = Optional(intExp.setResultsName("start"), default=None) + inS \
        + Optional(intExp.setResultsName("end"), default=None)
    interRef = Group(inL + interval + inR)
    ref = inL + Group(delimitedList(index ^ interval))("ref") + inR
    regNoRef = validName("var")
    regRef = Group(validName("var") + Optional(ref))
    regMustRef = Group(validName("var") + ref)
    regListNoRef = Group(delimitedList(regNoRef))
    regListRef = Group(delimitedList(regRef))

    def set_maths_type(toks, mathsType):
        """ Set logical or integer or floating point """
        toks["type"] = mathsType

    intVar = integer | regRef
    realVar = real | integer | pi | e | regRef
    boolVar = boolean | interRef | regRef | realExp | intExp
    intFuncVar = (intFunc  + brL + Group(Optional(delimitedList(intVar)))("args") + brR).setParseAction(Function)
    realFuncVar = ((realFunc ^ intFunc)
                   + brL + Group(Optional(delimitedList(realVar)))("args") + brR).setParseAction(Function)
    boolFuncVar = (boolFunc + brL + Group(Optional(delimitedList(boolVar)))("args") + brR).setParseAction(Function)

    mathOp = [
        (oneOf("- +"), 1, opAssoc.RIGHT, Binary),
        (oneOf("^"), 2, opAssoc.LEFT, Binary),
        (oneOf("* / div"), 2, opAssoc.LEFT, Binary),
        (oneOf("+ -"), 2, opAssoc.LEFT, Binary)
    ]
    logOp = [
        (oneOf("! not"), 1, opAssoc.RIGHT, Binary),
        (oneOf("and or xor"), 2, opAssoc.LEFT, Binary),
        (oneOf("< <= == != >= >"), 2, opAssoc.LEFT, Binary),
        (oneOf("in"), 2, opAssoc.LEFT, Binary)
    ]

    intExp <<= infixNotation(intFuncVar | intVar, mathOp).setParseAction(lambda s, l, t: set_maths_type(t, "int"))

    realExp <<= infixNotation(realFuncVar | realVar, mathOp).setParseAction(lambda s, l, t: set_maths_type(t, "float"))

    boolExp <<= infixNotation(boolFuncVar | boolVar, logOp).setParseAction(lambda s, l, t: set_maths_type(t, "bool"))

    mathExp = intExp ^ realExp ^ boolExp

    prefixes = ["unitary", "recursive"]
    callMods = ["CTRL", "INV"]

    def prefix_setter(toks):
        """ Pull out prefixes of gate calls and add them into list """
        for prefix in prefixes:
            toks[prefix] = prefix in toks.asList()
    prefixParser = Each(map(Optional, map(Keyword, prefixes))).addParseAction(prefix_setter)


    pargParser = brL + delimitedList(validName)("pargs") + brR
    spargParser = inL + delimitedList(validName)("spargs") + inR
    gargParser = ungroup(nestedExpr("<", ">", delimitedList(ungroup(validName)), None))
    qargParser = delimitedList(regRef)

    callPargParser = brL + delimitedList(realExp) + brR
    callSpargParser = inL + delimitedList(intExp) + inR

    fullArgParser = Each((Optional(pargParser("pargs")),
                          Optional(spargParser("spargs")),
                          Optional(gargParser("gargs"))))

    callArgParser = Each((Optional(callPargParser("pargs")),
                          Optional(callSpargParser("spargs")),
                          Optional(gargParser("gargs"))))

    returnParser = Optional(_to_ + validName("byprod"))

    modifiers = ZeroOrMore(Combine(oneOf(callMods) + Suppress("-")))

    commentLine = Literal(commentSyntax).suppress() + restOfLine("comment")
    commentBlock = cStyleComment("comment").addParseAction(removeQuotes).addParseAction(removeQuotes)
    comment = commentLine | commentBlock
    comment.addParseAction(lambda s, l, t: _set_version(t, (0, 0, 0)))

    directiveName = Word(alphas).setParseAction(downcaseTokens)
    directiveArgs = CharsNotIn(";")

    _Op("directive",
        directiveName("directive") + Suppress(White()*(1,)) + directiveArgs("args"),
        version="REQASM 1.0",
        keyOverride=(~dirOpenSyntax + ~dirCloseSyntax + dirSyntax))

    def split_args(toks):
        """ Split directive arguments out """
        toks[0]["keyword"] = "directive"
        toks[0]["args"] = toks[0]["args"].strip().split(" ")

    directiveStatement = directiveName("directive") + restOfLine("args") + \
        Group(ZeroOrMore(Combine(Optional(White(" ")) + ~dirCloseSyntax + Word(printables+" "))))("block")

    directiveBlock = ungroup(nestedExpr(dirOpenSyntax,
                                        dirCloseSyntax,
                                        content=directiveStatement,
                                        ignoreExpr=(comment | quotedString))
                             .setWhitespaceChars("\n").setParseAction(split_args))
    directiveBlock.addParseAction(lambda s, l, t: _set_version(t, (2, 1, 0)))

    # Programming lines
    _Op("version", Empty(),
        version=(0, 0, 0),
        keyOverride=Combine(oneOf(versions)("type") + White() + real("versionNumber"))("version"))
    _Op("include", quotedString("file").addParseAction(removeQuotes))

    # Gate-like structures
    _Op("opaque", validName("name") + fullArgParser + Optional(qargParser("qargs")) + returnParser,
        keyOverride=prefixParser + "opaque")
    _Routine("gate", pargs=True, qargs=True)
    _Routine("circuit", pargs=True, qargs=True, spargs=True, returnables=True, version="REQASM 1.0")

    # Variable-like structures
    _Op("creg", regRef("arg"))
    _Op("qreg", regRef("arg"))
    _Op("cbit", regNoRef("arg"), version="REQASM 1.0")
    _Op("qbit", regNoRef("arg"), version="REQASM 1.0")
    _Op("defAlias", regMustRef("alias"), keyOverride="alias", version="REQASM 1.0")
    _Op("alias", regRef("alias") + _is_ + regRef("target"), version="REQASM 1.0")
    _Op("val", validName("var") + Literal("=").suppress() + mathExp("val"), version="REQASM 1.0")

    # Operations-like structures
    _Op("measure", regRef("qreg") + _to_ + regRef("creg"), qop=True)
    _Op("barrier", regListNoRef("args"))
    _Op("output", regRef("value"), qop=True, version="REQASM 1.0")
    _Op("reset", regRef("qreg"))
    _Op("exit", Empty(), version="REQASM 1.0")

    _Op("free", validName("target"), version="REQASM 1.0")
    _Op("next", validName("loopVar"), qop=True, version="REQASM 1.0")
    _Op("escape", validName("loopVar"), qop=True, version="REQASM 1.0")
    _Op("end", validName("process"), qop=True, version="REQASM 1.0")

    # Special gate call handler
    callGate = Combine(Group(modifiers)("mods") + \
                       validName("gate")) + \
                       callArgParser + \
                       regListRef("qargs").addParseAction(lambda s, l, t: _override_keyword(t, "call")) + \
                       returnParser
    callGate.addParseAction(lambda s, l, t: _set_version(t, (1, 2, 0)))

    # Block structures
    _Block("for", validName("var") + _in_ + interRef("range"), version="REQASM 1.0")
    _Block("if", "(" + boolExp("cond") + ")", version="REQASM 1.0")
    _Block("while", "(" + boolExp("cond") + ")", version="OMEQASM 1.0")

    qopsParsers = list(map(lambda qop: qop.parser, qops.values())) + [callGate, directiveBlock]
    blocksParsers = list(map(lambda block: block.parser, blocks.values()))

    _Op("if", blocks["if"].parser + Group(Group(Group(Or(qopsParsers))))("block"),
        version="OPENQASM 2.0",
        keyOverride=Empty())
    _Op("for", blocks["for"].parser + Group(Group(Group(Or(qopsParsers))))("block"),
        version="REQASM 1.0",
        keyOverride=Empty())
    _Op("while", blocks["while"].parser + Group(Group(Group(Or(qopsParsers))))("block"),
        version="OMEQASM 1.0",
        keyOverride=Empty())

    # Set-up line parsers
    reservedNames = Or(_reservedKeys) ^ e ^ pi
    validName <<= (~reservedNames) + Word(alphas, alphanums+"_")

    copsParsers = list(map(lambda cop: cop.parser, cops.values()))

    operations = (((Or(copsParsers) ^ Or(qopsParsers)) |    # Classical/Quantum Operations
                   callGate |                               # Gate parsers
                   White()                                  # Blank Line
                   ) + lineEnd.suppress()) ^ directiveBlock # ; or Directives

    validLine = Forward()
    codeBlock = nestedExpr("{", "}", Suppress(White()) ^ Group(validLine), (quotedString))

    validLine <<= ((
        (operations + Optional(comment)) ^
        (Or(blocksParsers) + codeBlock("block") + Optional(lineEnd)) ^
                comment))                              # Whole line comment

    testLine = Forward()
    dummyCodeBlock = nestedExpr("{", "}", testLine, (directiveBlock | quotedString | comment)) + Optional(lineEnd)

    ignoreSpecialBlocks = (~commentOpenSyntax + ~commentCloseSyntax + ~dirOpenSyntax + ~dirCloseSyntax)

    testLine <<= (comment |                                                                 # Comments
                  directiveBlock |                                                          # Directives
                  (ignoreSpecialBlocks + ZeroOrMore(CharsNotIn("{}")) + dummyCodeBlock) |   # Block operations
                  (ignoreSpecialBlocks + ZeroOrMore(CharsNotIn("{};")) + lineEnd))          # QASM Instructions
    
    testKeyword = (dirSyntax.setParseAction(lambda s, l, t: _override_keyword(t, "directive")) |
                   Word(alphas)("keyword"))

    code = (Group(directiveBlock)) | Group(validLine)

    return code, testLine, testKeyword, reservedNames


QASMcodeParser, lineParser, errorKeywordParser, reserved = _setup_QASMParser()
