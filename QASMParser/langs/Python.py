"""
Module to supply functions to write Python from given QASM types
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
    Assign all methods for converting into Python

    :returns: None
    :rtype: None
    """
    TensorNetwork.to_lang = TensorNetwork_to_Python
    ClassicalRegister.to_lang = ClassicalRegister_to_Python
    DeferredClassicalRegister.to_lang = ClassicalRegister_to_Python
    QuantumRegister.to_lang = QuantumRegister_to_Python
    Let.to_lang = Let_to_Python
    Argument.to_lang = Argument_to_Python
    CallGate.to_lang = CallGate_to_Python
    Comment.to_lang = Comment_to_Python
    Measure.to_lang = Measure_to_Python
    IfBlock.to_lang = IfBlock_to_Python
    While.to_lang = While_to_Python
    Gate.to_lang = CreateGate_to_Python
    Circuit.to_lang = CreateGate_to_Python
    Procedure.to_lang = CreateGate_to_Python
    Opaque.to_lang = CreateGate_to_Python
    CBlock.to_lang = CBlock_to_Python
    Loop.to_lang = Loop_to_Python
    NestLoop.to_lang = NestLoop_to_Python
    Reset.to_lang = Reset_to_Python
    Output.to_lang = Output_to_Python
    InitEnv.to_lang = init_env
    Return.to_lang = Return_to_Python
    Include.to_lang = Include_to_Python
    Cycle.to_lang = Cycle_to_Python
    Escape.to_lang = Escape_to_Python
    Alias.to_lang = Alias_to_Python
    DeferredAlias.to_lang = Alias_to_Python
    Dealloc.to_lang = lambda: ""
    SetAlias.to_lang = SetAlias_to_Python
    MathsBlock.to_lang = resolve_maths
    init_core_QASM_gates()

# Several details pertaining to the language in question
hoistFuncs = False    # Move functions to front of program
hoistIncludes = False # Move includes  to front of program
hoistVars = False     # Move variables to front of program
bareCode = False      # Can code be bare or does it need to be in function
blockOpen = ":"       # Block delimiters
blockClose = "\n"       #  ""      ""
indent = "    "       # Standard indent depth

def init_core_QASM_gates():
    """ Set up the core gates in python """
    unitary = Gate.internalGates["U"]
    controlledNot = Gate.internalGates["CX"]
    unitaryInverse = Gate.internalGates["inv_U"]

    controlledNot.set_code([CBlock(
        None,
        """controlledNot(qreg, a_index, b_index)""".splitlines())])
    unitary.set_code([CBlock(
        None,
        """rotateZ(qreg,a_index,lambda)
rotateX(qreg,a_index,theta)
rotateZ(qreg,a_index,phi)""".splitlines())])

    unitaryInverse.set_code([CBlock(
        None,
        """rotateZ(qreg,a_index,-lambda)
rotateX(qreg,a_index,-theta)
rotateZ(qreg,a_index,-phi)""".splitlines())])



def Maths_to_Python(parent, maths: MathsBlock):
    """Resolve mathematical operations into C.

    :param parent: Parent containing resolvable variables
    :param maths: Mathsblock to convert to C

    """
    # Ops which should be unchanged
    identOp = ["-", "+", "*", "/", "%", "<", "<=", "==", "!=", ">=", ">", "!", "sin", "cos", "tan", "sqrt", "abs",
               "and", "or"]
    # Ops which require simple substitution
    subOp = {"xor":"!=", "mod":"%", "arccos":"acos", "arcsin":"asin", "arctan":"atan", "^":"**", "div":"//"}
    outStr = ""

    for element in maths.maths:
        if isinstance(element, Binary):
            for operator, operand in element.args:
                if operator == "in":
                    if len(operand) == 2:
                        outStr = f"{operand[0]} < {outStr} < {operand[1]}"
                    else:
                        raise OSError
                    continue
                operand = resolve_maths(parent, operand)
                if operator == "nop":
                    outStr += f"{operand}"
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
        value = Maths_to_Python(self, elem)
    elif isinstance(elem, list) and isinstance(elem[0], ClassicalRegister):
        if isinstance(elem[1], tuple):
            start, end = elem[1]
            if start == end:
                value = f"{elem[0].name}[{start}]"
            else:
                value = f"int(''.join({elem[0].name}[{start}:{end}]), 2)"
        elif elem[1] is None:
            value = f"int(''.join({elem[0].name}), 2)"
    elif isinstance(elem, (int, float, str)):
        value = str(elem)
    elif isinstance(elem, Constant):
        value = elem.name
    elif issubclass(type(elem), MathOp):
        value = Maths_to_Python(self.parent, elem)
    else:
        raise NotImplementedError(elem)

    return value

def resolve_index(index):
    if isinstance(index, Constant):
        index = index.name
    elif isinstance(index, MathsBlock):
        index = resolve_maths(None, index)
    return index

def resolve_arg(arg):
    """Resolve quantum arguments into their appropriate references or indices.

    :param arg: List consisting of [register, index] to resolve
    :returns: Python-resolved array reference in register
    :rtype: str
    """

    obj, index = arg

    if isinstance(index, (list, tuple)):
        index = "{}:{}".format(*map(resolve_index, index))
    else:
        index = resolve_index(index)

    if isinstance(obj, Argument):
        if obj.size == 1:
            out = obj.start
        else:
            out = f"{obj.start}[{index}]"

    elif issubclass(type(obj), Register):
        out = f"{obj.name}[{index}]"
    else:
        raise NotImplementedError("Resolution of {}".format(type(obj).__name__))

    return out


def python_include(filename: str):
    """Syntax conversion for python imports.

    :param filename: filename to import

    """
    return f'from {filename} import *'
header = [python_include("QuESTLibs"), python_include("math")]
includeTN = python_include("TNPy")

def Include_to_Python(self):
    """Syntax conversion for Python imports."""
    return python_include(self.filename)

def init_env(self):
    """Syntax conversion for initialising the QuEST environment."""
    return f'Env = createQuESTEnv()'

def Output_to_Python(self):
    """Syntax conversion for printing a parg."""
    parg, bindex = self.pargs
    return f'print({parg.name}[{bindex}], end=" ")'

def Return_to_Python(self):
    """Syntax conversion for breaking out of a function."""
    return f'return {self.pargs[0]}'

def Cycle_to_Python(self):
    """Syntax conversion for cycling a loop."""
    return "continue"

def Escape_to_Python(self):
    """Syntax conversion for breaking a loop."""
    return "break"

def End_to_Python(self):
    """Syntax conversion for early return from function."""
    return "return"

def Reset_to_Python(self):
    """Syntax conversion for resetting quantum state to zero."""
    qarg = self.qargs
    qargRef = self.resolve_arg(qarg)
    return f'collapseToOutcome(qreg, {qargRef}, 0)'

def ClassicalRegister_to_Python(self):
    """Syntax conversion for creating a classical register."""
    if isinstance(self.size, MathsBlock):
        size = Maths_to_Python(self, self.size)
    elif isinstance(self.size, list):
        size = f'{{{",".join(self.size)}}}'
    else:
        size = f'{self.size}'

    return f'{self.name} = [0]*{size}'


def QuantumRegister_to_Python(self):
    """Syntax conversion for creating a quantum register."""
    return f"{self.name} = createQureg({self.size}, Env)"

def Argument_to_Python(self):
    """Syntax conversion for creating a function argument."""
    if self.classical:
        return f'{self.name}'
    return f'{self.name}, {self.name}_index'

def Alias_to_Python(self):
    """Syntax conversion for creating an alias."""
    return f"{self.name} = [None]*{self.size}"

def SetAlias_to_Python(self):
    """Syntax conversion for setting an alias."""
    outStr = ""

    if self.parent.resolve_maths(self.pargs[1][1] - self.pargs[1][0] + 1) > 1:
        aliasIndex, targetIndex = (self.alias.name+"_index", self.qargs[0].name+"_index")
        outStr += Loop(self.parent, NullBlock(self.parent.currentFile),
                       (aliasIndex, targetIndex),
                       (self.pargs[1][0], self.qargs[1][0]),
                       (self.pargs[1][1], self.qargs[1][1]), step=None).to_lang()
        if self.qargs[0].start > 0:
            outStr += f"\n  {self.alias.name}[{aliasIndex}] = {targetIndex} + {self.qargs[0].start}"
        else:
            outStr += f"\n  {self.alias.name}[{aliasIndex}] = {targetIndex}"
    else:
        qargs = (self.qargs[0], self.qargs[1][0])
        outStr = f"{self.alias.name}[{self.pargs[1][0]}] = {resolve_arg(qargs)}"
    return outStr

def Let_to_Python(self):
    """Syntax conversion for creating a variable."""
    var = self.const
    assignee = var.name

    # Simple declaration
    if var.val is None and var.var_type is None:
        return f"{assignee} = None"

    if var.val is None and var.var_type:
        return f'{assignee} = {var.var_type}()'

    if isinstance(var.val, MathsBlock):
        value = resolve_maths(None, var.val)
    else:
        value = str(var.val)

    if var.cast:
        value = f"{var.cast}({value})"

    return f"{assignee} = {value}"

def CBlock_to_Python(self):
    """Syntax conversion for classical block."""
    return "\n".join(self.block)

def CallGate_to_Python(self):
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
    outString = f"{printGate}({printArgs})"
    return outString

def Comment_to_Python(self):
    """Syntax conversion for a comment."""
    return "#" + self.comment.replace("\n", "\n#").replace("/*", "#").replace("*/", "")

def Measure_to_Python(self):
    """Syntax conversion for a measurement."""
    parg = self.pargs
    qarg = self.qargs
    qargRef = resolve_arg(qarg)
    pargRef = resolve_arg(parg)
    return f"{pargRef} = measure(qreg, {qargRef})"

def IfBlock_to_Python(self):
    """Syntax conversion for an if statement."""
    outStr = Maths_to_Python(self, self.cond)
    return f"if {outStr}"

def While_to_Python(self):
    """Syntax conversion for an if statement."""
    outStr = Maths_to_Python(self, self.cond)
    return f"while {outStr}"

def CreateGate_to_Python(self):
    """Syntax conversion for declaring a gate."""
    printQargs = ""
    printPargs = ""
    printSpargs = ""
    if self.qargs:
        printQargs = "qreg, " + ", ".join(f"{qarg.name}" for qarg in self.qargs)
    if self.pargs:
        printPargs = ", ".join(f"{parg.name}" for parg in self.pargs)
    if self.spargs:
        printSpargs = ", ".join(f"{sparg.name}" for sparg in self.spargs)

    printArgs = ", ".join(args for args in (printQargs, printPargs, printSpargs) if args).rstrip(", ")
    outStr = f"def {self.name}({printArgs})"
    return outStr


def Loop_to_Python(self):
    """Syntax conversion for declaring a loop (inclusive)."""
    resolve = lambda b: resolve_maths(self, b)
    start = map(resolve, self.start)
    end = map(resolve, self.end)
    step = map(resolve, self.step)

    if len(self.var) == 1:
        return f"for {''.join(self.var)} in range({''.join(start)}, {''.join(end)}+1, {''.join(step)})"

    ranges = [f"range({init}, {term}+1, {incr})" for init, term, incr in zip(start, end, step)]
    return f"for {', '.join(self.var)} in zip({', '.join(ranges)})"

def NestLoop_to_Python(self):
    """Syntax conversion for declaring a loop (exclusive)."""
    resolve = lambda b: resolve_maths(self, b)
    start = map(resolve, self.start)
    end = map(resolve, self.end)
    step = map(resolve, self.step)

    if len(self.var) == 1:
        return f"for {''.join(self.var)} in range({''.join(start)}, {''.join(end)}, {''.join(step)})"

    ranges = [f"range({init}, {term}, {incr})" for init, term, incr in zip(start, end, step)]
    return f"for {', '.join(self.var)} in zip({', '.join(ranges)})"

def TensorNetwork_to_Python(self):
    """Syntax conversion for creating a TensorNetwork """
    return "{} = createTensorNetwork({}, {}, {}, Env)".format(self.name,
                                                              len(self.physicalQubits),
                                                              self.physicalQubits,
                                                              self.virtualQubits)
