"""
Module to supply functions to write Python from given QASM types
"""



from QASMParser.QASMTypes import (ClassicalRegister, QuantumRegister, Let, CBlock,
                                  Argument, CallGate, Comment, Measure, IfBlock, Verbatim,
                                  Gate, Opaque, Loop, NestLoop, Reset, Output, InitEnv)

def set_lang():
    """
    Assign all methods for converting into python.
    """
    ClassicalRegister.to_lang = ClassicalRegister_to_Python
    QuantumRegister.to_lang = QuantumRegister_to_Python
    Let.to_lang = Let_to_Python
    Argument.to_lang = Argument_to_Python
    CallGate.to_lang = CallGate_to_Python
    Comment.to_lang = Comment_to_Python
    Measure.to_lang = Measure_to_Python
    IfBlock.to_lang = IfBlock_to_Python
    Gate.to_lang = CreateGate_to_Python
    Opaque.to_lang = CreateGate_to_Python
    CBlock.to_lang = PyBlock_to_Python
    Loop.to_lang = Loop_to_Python
    NestLoop.to_lang = Loop_to_Python
    Reset.to_lang = Reset_to_Python
    Output.to_lang = Output_to_Python
    InitEnv.to_lang = init_env


# Several details pertaining to the language in question
hoistFuncs = False   # Move functions to front of program
hoistVars  = False  # Move variables to front of program
bareCode   = False  # Can code be bare or does it need to be in function
blockOpen = ":"     # Block delimiters
blockClose = ""    #  ""      ""
indent = "    "       # Standard indent depth

def Python_include(filename):
    """Syntax conversion for python imports."""
    return f'from {filename} import *'
header = [Python_include("QuESTLibs")]

def init_env(self):
    """Syntax conversion for initialising the QuEST environment."""
    return f'Env = createQuESTEnv()'

def Output_to_Python(self):
    """Syntax conversion for printing a parg."""
    parg, bindex = self.pargs
    return f'print({parg.name}[{bindex}])'

def Reset_to_Python(self):
    """Syntax conversion for resetting quantum state to zero."""
    qarg = self.qargs
    qargRef = self.resolve_arg(qarg)
    return f'collapseToOutcome(qreg, {qargRef}, 0)'

def ClassicalRegister_to_Python(self):
    """Syntax conversion for creating a classical register."""
    return f'{self.name} = [0]*{self.size}'

def QuantumRegister_to_Python(self):
    """Syntax conversion for creating a quantum register."""
    return f"{self.name} = createQureg({self.size}, Env)"

def Argument_to_Python(self):
    """Syntax conversion for creating a function argument."""
    if self.classical:
        return f'{self.name}'
    return f'{self.name}, {self.name}_index'

def Let_to_Python(self):
    """Syntax conversion for creating a variable."""
    var = self.const
    assignee = var.name

    # Simple declaration
    if var.val is None and var.var_type is None:
        return f"{assignee} = None"
    elif var.val is None and var.var_type:
        return f'{assignee} = {var.var_type}()'

    if isinstance(var.val, (tuple, list)):
        value = ",".join(var.val)
    else:
        value =  f'{var.val}'
    if var.cast:
        value = f"{var.cast}({value})"

    return f"{assignee} = {value}"

def PyBlock_to_Python(self):
    """Syntax conversion for classical block."""
    return "\n".join(self.block)

def CallGate_to_Python(self):
    """Syntax conversion for calling a gate."""
    printArgs = ""
    if self.qargs:
        printArgs += "qreg, "
        printArgs += ", ".join([self.resolve_arg(qarg) for qarg in self.qargs])
    for parg in self.pargs:
        if printArgs:
            printArgs += ", "+parg
        else:
            printArgs = parg
    printGate = self.name
    preString = []
    outString = ""
    for line in preString:
        outString += line + ";\n"
    outString += f"{printGate}({printArgs})"
    return outString

def Comment_to_Python(self):
    """Syntax conversion for a comment."""
    return "#" + self.comment

def Measure_to_Python(self):
    """Syntax conversion for a measurement."""
    parg, bindex = self.pargs
    qarg = self.qargs
    qargRef = self.resolve_arg(qarg)
    return f"{parg.name}[{bindex}] = measure(qreg, {qargRef})"

def IfBlock_to_Python(self):
    """Syntax conversion for an if statement."""
    return f"if ({self.cond})"

def CreateGate_to_Python(self):
    """Syntax conversion for declaring a gate."""
    if isinstance(self.code[0], Verbatim) and self.code[0].line == ";":
        self.code = [Verbatim("pass")]
    printArgs = ""
    if self.qargs:
        printArgs += "qreg"
        printArgs += ", " + ", ".join([f"{qarg}_index" for qarg in self.qargs])
    for parg in self.pargs:
        if printArgs:
            printArgs += ", "+parg
        else:
            printArgs += parg
    outStr = f"def {self.name}({printArgs})"
    return outStr

def Loop_to_Python(self):
    """Syntax conversion for declaring a loop."""
    return  f"for {self.var} in range({self.start}, {self.end}, {self.step})"
