"""
Module to supply functions to write C from given QASM types
"""
from QASMParser.QASMTypes import (TensorNetwork, ClassicalRegister, QuantumRegister, DeferredClassicalRegister,
                                  Let, Argument, CallGate, Comment, Measure, IfBlock, While, Gate, Circuit,
                                  Procedure, Opaque, CBlock, Loop, NestLoop, Reset, Output, InitEnv, Return,
                                  Include, Cycle, Escape, Alias, SetAlias, MathsBlock, Constant,
                                  MathOp, Register, Dealloc, DeferredAlias)
from QASMParser.QASMTokens import (Binary, Function)
from QASMParser.FileHandle import (NullBlock)

def set_lang():
    """
    Assign all methods for converting into C.

    :returns: None
    :rtype: None
    """
    TensorNetwork.to_lang = TensorNetwork_to_c
    ClassicalRegister.to_lang = ClassicalRegister_to_c
    QuantumRegister.to_lang = QuantumRegister_to_c
    DeferredClassicalRegister.to_lang = DeferredClassicalRegister_to_c
    Let.to_lang = Let_to_c
    Argument.to_lang = Argument_to_c
    CallGate.to_lang = CallGate_to_c
    Comment.to_lang = Comment_to_c
    Measure.to_lang = Measure_to_c
    IfBlock.to_lang = IfBlock_to_c
    While.to_lang = While_to_c
    Gate.to_lang = CreateGate_to_c
    Circuit.to_lang = CreateGate_to_c
    Procedure.to_lang = CreateGate_to_c
    Opaque.to_lang = CreateGate_to_c
    CBlock.to_lang = CBlock_to_c
    Loop.to_lang = Loop_to_c
    NestLoop.to_lang = NestLoop_to_c
    Reset.to_lang = Reset_to_c
    Output.to_lang = Output_to_c
    InitEnv.to_lang = init_env
    Return.to_lang = Return_to_c
    Include.to_lang = Include_to_c
    Cycle.to_lang = Cycle_to_c
    Escape.to_lang = Escape_to_c
    Alias.to_lang = Alias_to_c
    SetAlias.to_lang = SetAlias_to_c
    MathsBlock.to_lang = resolve_maths
    Dealloc.to_lang = Dealloc_to_c
    DeferredAlias.to_lang = DeferredAlias_to_c
    init_core_QASM_gates()

# Several details pertaining to the language in question
hoistFuncs = True    # Move functions to front of program
hoistIncludes = True # Move includes  to front of program
hoistVars = False    # Move variables to front of program
bareCode = False     # Can code be bare or does it need to be in function
blockOpen = "{"      # Block delimiters
blockClose = "}"     #  ""      ""
indent = "  "        # Standard indent depth

_typesTranslation = {
    "int":"int",
    "float":"qreal",
    "qreg":"Qureg",
    "complex":"Complex",
    "ComplexMatrix2":"ComplexMatrix2",
    "listint":"int *",
    "const listint":"const int",
    "listfloat":"float",
    "str":"char",
    "bool":"int",
    None:"void"
}

def init_core_QASM_gates():
    """ Set up the core gates in python """
    unitary = Gate.internalGates["U"]
    controlledNot = Gate.internalGates["CX"]
    unitaryInverse = Gate.internalGates["inv_U"]

    controlledNot.set_code([CBlock(
        None,
        """controlledNot(qreg, a_index, b_index);""".splitlines())])
    unitary.set_code([CBlock(
        None,
        """rotateZ(qreg,a_index,lambda);
rotateX(qreg,a_index,theta);
rotateZ(qreg,a_index,phi);""".splitlines())])

    unitaryInverse.set_code([CBlock(
        None,
        """rotateZ(qreg,a_index,-lambda);
rotateX(qreg,a_index,-theta);
rotateZ(qreg,a_index,-phi);""".splitlines())])


def Maths_to_c(parent, maths: MathsBlock):
    """Resolve mathematical operations into C.

    :param parent: Parent containing resolvable variables
    :param maths: Mathsblock to convert to C

    """
    # Ops which should be unchanged
    identOp = ["-", "+", "*", "/", "%", "<", "<=", "==", "!=", ">=", ">", "!", "sin", "cos", "tan", "sqrt", "abs"]
    # Ops which require simple substitution
    subOp = {"and":"&&", "or":"||", "xor":"!=", "mod":"%",
             "arccos":"acos", "arcsin":"asin", "arctan":"atan"}
    outStr = ""

    for element in maths.maths:
        if isinstance(element, Binary):
            for operator, operand in element.args:
                if operator == "in":
                    if len(operand) == 2:
                        outStr = f"({outStr} > {operand[0]} && {outStr} < {operand[1]})"
                    else:
                        raise OSError
                    continue
                operand = resolve_maths(parent, operand)
                if operator == "nop":
                    outStr += f"{operand}"
                elif operator == "^":
                    outStr = f"pow({outStr}, {operand})"
                elif operator == "div":
                    outStr = f"floor({outStr} / {operand})"
                elif operator in identOp:
                    outStr += f" {operator} {operand}"
                elif operator in subOp:
                    outStr += f" {subOp[operator]} {operand}"
                else:
                    raise NotImplementedError(operator)
        elif isinstance(element, Function):
            elem = element.op
            args = []
            for arg in element.args:
                args.append(resolve_maths(parent, arg))
            outStr += f"{elem}({', '.join(args)})"
        elif isinstance(element, str):
            outStr += element
        else: raise NotImplementedError("Maths cannot parse type {} {}".format(type(element).__name__, element))

    return outStr

def resolve_maths(self, elem):
    """Resolve mathematical element into C.

    :param elem: Mathematical element to transpile
    :returns: Parsed maths in C
    :rtype: str
    """


    if isinstance(elem, MathsBlock):
        value = Maths_to_c(self, elem)
    elif isinstance(elem, list) and isinstance(elem[0], ClassicalRegister):
        if isinstance(elem[1], tuple):
            start, end = elem[1]
            if start == end:
                value = f"{elem[0].name}[{start}]"
            else:
                size = end - start + 1
                if start:
                    value = f"decOf({elem[0].name}[{start}], {size})"
                else:
                    value = f"decOf({elem[0].name}, {size})"
        elif elem[1] is None:
            value = f"decOf({elem[0].name}, {elem[0].size})"
    elif isinstance(elem, (int, float, str)):
        value = str(elem)
    elif isinstance(elem, Constant):
        value = elem.name
    elif issubclass(type(elem), MathOp):
        value = Maths_to_c(self.parent, elem)
    else:
        raise NotImplementedError(elem)

    return value

def resolve_arg(arg):
    """Resolve quantum arguments into their appropriate references or indices.

    :param arg: List consisting of [register, index] to resolve
    :returns: C-resolved array reference in register
    :rtype: str
    """

    obj, index = arg

    if isinstance(index, (list, tuple)):
        ref = "&"
        index = index[0]
    else:
        ref = ""

    if isinstance(index, Constant):
        index = index.name
    elif isinstance(index, MathsBlock):

        index = resolve_maths(None, index)

    if isinstance(obj, Argument):
        if obj.size == 1:
            out = obj.start
        else:
            out = f"{ref}{obj.start}[{index}]"

    elif issubclass(type(obj), Register):
        out = f"{ref}{obj.name}[{index}]"
    else:
        raise NotImplementedError("Resolution of {}".format(type(obj).__name__))

    return out


def Include_to_c(self):
    """Syntax conversion for C imports."""
    return f'#include "{self.filename}"'

def inc(filename):
    """Shorthand for C imports.

    :param filename: File to include
    :returns: Include line
    :rtype: str

    """
    return f'#include "{filename}"'

header = [inc("QuEST.h"), inc("stdio.h"), inc("reqasm.h")]
includeTN = inc("QuEST_tn.h") + "\n#define CX tn_controlledNot\n#define U tn_unitary"

def init_env(self):
    """ Syntax conversion for initialising QuEST environment """
    return f'QuESTEnv Env = createQuESTEnv();'

def Output_to_c(self):
    """Syntax conversion for initialising the QuEST environment."""
    parg, bindex = self.pargs
    return f'printf("%d ", {parg.name}[{bindex}]);'

def Return_to_c(self):
    """Syntax conversion for breaking out of a function."""
    return f'return {self.pargs.name};'

def Cycle_to_c(self):
    """Syntax conversion for cycling a loop."""
    return "continue;"

def Escape_to_c(self):
    """Syntax conversion for breaking a loop."""
    return "break;"

def End_to_c(self):
    """Syntax conversion for early return from function."""
    return "return;"

def Reset_to_c(self):
    """Syntax conversion for resetting quantum state to zero."""
    qarg = self.qargs
    qargRef = resolve_arg(qarg)
    return f'collapseToOutcome(qreg, {qargRef}, 0);'

def ClassicalRegister_to_c(self):
    """Syntax conversion for creating a classical register."""
    return f'int {self.name}[{self.size}];'+"\n"+f'for (int i = 0; i < {self.size}; i++) {self.name}[i] = 0;'

def DeferredClassicalRegister_to_c(self):
    """Syntax conversion for creating a deferred classical register."""
    if isinstance(self.size, MathsBlock):
        size = Maths_to_c(self, self.size)
    elif isinstance(self.size, list):
        size = f'{{{",".join(self.size)}}}'
    else:
        size = f'{self.size}'

    return (f'int* {self.name} = malloc(sizeof(int)*({size}));''\n'
            f'for (int i = 0; i < {size}; i++) {self.name}[i] = 0;')

def Dealloc_to_c(self):
    return f'free {self.pargs};'

def QuantumRegister_to_c(self):
    """Syntax conversion for creating a quantum register."""
    return f"Qureg {self.name} = createQureg({self.size}, Env);"

def TensorNetwork_to_c(self):
    """Syntax conversion for creating a TensorNetwork """
    numTensors = len(self.physicalQubits)
    numPqPerTensor = Let(self, ("numPqPerTensor", "const listint"), (self.physicalQubits, None)).to_lang()
    numVqPerTensor = Let(self, ("numVqPerTensor", "const listint"), (self.virtualQubits, None)).to_lang()

    return f"""{numPqPerTensor}
{numVqPerTensor}
TensorNetwork {self.name} = createTensorNetwork({numTensors}, numPqPerTensor, numVqPerTensor, Env)"""

def Argument_to_c(self):
    """Syntax conversion for creating a function argument."""
    if self.classical:
        return f'qreal {self.name}'
    return f'Qureg {self.name}, int {self.name}_index'

def Alias_to_c(self):
    """Syntax conversion for creating an alias."""
    return f"int {self.name}[{self.size}];"

def DeferredAlias_to_c(self):
    """Syntax conversion for creating a deferred Alias."""
    if isinstance(self.size, MathsBlock):
        size = Maths_to_c(self, self.size)
    elif isinstance(self.size, list):
        size = f'{{{",".join(self.size)}}}'
    else:
        size = f'{self.size}'

    return (f'int* {self.name} = malloc(sizeof(int)*{size});''\n'
            f'for (int i = 0; i < {size}; i++) {self.name}[i] = 0;')

def SetAlias_to_c(self):
    """Syntax conversion for setting an alias."""
    outStr = ""

    if self.parent.resolve_maths(self.pargs[1][1] - self.pargs[1][0] + 1) > 1:
        aliasIndex, targetIndex = (self.alias.name+"_index", self.qargs[0].name+"_index")
        outStr += Loop(self.parent, NullBlock(self.parent.currentFile),
                       (aliasIndex, targetIndex),
                       (self.pargs[1][0], self.qargs[1][0]),
                       (self.pargs[1][1], self.qargs[1][1]), step=None).to_lang()
        if self.qargs[0].start > 0:
            outStr += f"\n  {self.alias.name}[{aliasIndex}] = {targetIndex} + {self.qargs[0].start};"
        else:
            outStr += f"\n  {self.alias.name}[{aliasIndex}] = {targetIndex};"
    else:
        qargs = (self.qargs[0], self.qargs[1][0])
        outStr = f"{self.alias.name}[{self.pargs[1][0]}] = {resolve_arg(qargs)};"
    return outStr

def Let_to_c(self):
    """Syntax conversion for creating a variable."""
    var = self.const
    assignee = var.name

    if var.varType:
        assignee = f"{_typesTranslation[var.varType]} {assignee}"
        if var.varType in ["const listint", "listint", "listfloat"]:
            assignee += f"[{len(var.val)}]"

    # Simple declaration
    if var.val is None:
        return f"{assignee};"

    if isinstance(var.val, (list, tuple)):
        if var.varType.startswith("const"):
            val = map(str, var.val)
            value = f"{assignee} = {{ {','.join(val)} }};"
        else:
            if var.varType:
                value = f"{assignee};\n"
            else:
                value = ""
            for index, val in enumerate(var.val):
                if val is not None:
                    value += f"{var.name}[{index}] = {val};\n"
        out = value
    else:
        value = resolve_maths(self, var.val)
        if var.cast:
            value = f"({var.cast}) {value}"
        out = f"{assignee} = {value};"

    return out

def CBlock_to_c(self):
    """Syntax conversion for classical block."""
    return "\n".join(self.block)

def CallGate_to_c(self):
    """Syntax conversion for calling a gate."""
    printQargs = ""
    printPargs = ""
    printSpargs = ""

    if self.qargs:
        printQargs = "qreg, " + ", ".join(f"{resolve_arg(qarg)}" for qarg in self.qargs)
    if self.pargs:
        printPargs = ", ".join(f"{resolve_maths(self.parent,parg)}" for parg in self.pargs)
    if self.spargs:
        printSpargs = ", ".join(f"{resolve_maths(self.parent, sparg)}" for sparg in self.spargs)

    printArgs = ", ".join(args for args in (printQargs, printPargs, printSpargs) if args).rstrip(", ")
    printGate = self.name
    if self.byprod:
        outString = f"{self.byprod} = {printGate}({printArgs});"
    else:
        outString = f"{printGate}({printArgs});"
    return outString

def Comment_to_c(self):
    """Syntax conversion for a comment."""
    if len(self.comment.splitlines()) > 1:
        return "/*" + self.comment.replace("*/", "**") + "*/"
    return "//" + self.comment.replace("/*", "**").replace("*/", "**")

def Measure_to_c(self):
    """Syntax conversion for a measurement."""
    parg = self.pargs
    qarg = self.qargs
    qargRef = resolve_arg(qarg)
    pargRef = resolve_arg(parg)
    return f"{pargRef} = measure(qreg, {qargRef});"

def IfBlock_to_c(self):
    """Syntax conversion for an if statement."""
    outStr = Maths_to_c(self, self.cond)
    return f"if ({outStr}) "

def While_to_c(self):
    """Syntax conversion for a while loop."""
    outStr = Maths_to_c(self, self.cond)
    return f"while ({outStr}) "


def CreateGate_to_c(self):
    """Syntax conversion for declaring a gate."""
    printQargs = ""
    printPargs = ""
    printSpargs = ""
    if self.qargs:
        printQargs = "Qureg qreg, " + ", ".join(f"int {qarg.name}" if qarg.size == 1
                                                else f"int* {qarg.name}" for qarg in self.qargs)
    if self.pargs:
        printPargs = ", ".join(f"{parg.varType} {parg.name}" for parg in self.pargs)
    if self.spargs:
        printSpargs = ", ".join(f"int {sparg.name}" for sparg in self.spargs)

    printArgs = ", ".join(args for args in (printQargs, printPargs, printSpargs) if args).rstrip(", ")
    returnType = _typesTranslation[self.returnType]
    outStr = f"{returnType} {self.name}({printArgs}) "
    return outStr

def Loop_to_c(self):
    """Syntax conversion for declaring a loop (inclusive)."""
    resolve = lambda b: resolve_maths(self, b)
    start = map(resolve, self.start)
    end = map(resolve, self.end)
    step = map(resolve, self.step)

    var = (f"int {var} = {init}" for var, init in zip(self.var, start))
    term = (f"{var} <= {term}"    for var, term in zip(self.var, end))
    incr = (f"{var} += {incr}"     for var, incr  in zip(self.var, step))
    return f"for ( {', '.join(var)}; {' && '.join(term)}; {', '.join(incr)} )"

def NestLoop_to_c(self):
    """Syntax conversion for implicit loop (exclusive)."""
    resolve = lambda b: resolve_maths(self, b)
    start = map(resolve, self.start)
    end = map(resolve, self.end)
    step = map(resolve, self.step)

    var = (f"int {var} = {init}" for var, init in zip(self.var, start))
    term = (f"{var} < {term}"    for var, term in zip(self.var, end))
    incr = (f"{var} += {incr}"     for var, incr  in zip(self.var, step))
    return f"for ( {', '.join(var)}; {' && '.join(term)}; {', '.join(incr)} )"
