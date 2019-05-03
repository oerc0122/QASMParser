from QASMParser.QASMTypes import *

def set_lang():
    ClassicalRegister.to_lang = ClassicalRegister_to_c
    QuantumRegister.to_lang = QuantumRegister_to_c
    Let.to_lang = Let_to_c
    Argument.to_lang = Argument_to_c
    CallGate.to_lang = CallGate_to_c
    Comment.to_lang = Comment_to_c
    Measure.to_lang = Measure_to_c
    IfBlock.to_lang = IfBlock_to_c
    Gate.to_lang = CreateGate_to_c
    Opaque.to_lang = CreateGate_to_c
    CBlock.to_lang = CBlock_to_c
    Loop.to_lang = Loop_to_c
    NestLoop.to_lang = Loop_to_c
    Reset.to_lang = Reset_to_c
    Output.to_lang = Output_to_c
    InitEnv.to_lang = init_env

# Several details pertaining to the language in question
hoistFuncs = True   # Move functions to front of program
hoistVars  = False  # Move variables to front of program
bareCode   = False  # Can code be bare or does it need to be in function
blockOpen = "{"     # Block delimiters
blockClose = "}"    #  ""      ""
indent = "  "       # Standard indent depth

typesTranslation = {
    "int":"int",
    "float":"qreal",
    "qreg":"Qureg",
    "complex":"Complex",
    "ComplexMatrix2":"ComplexMatrix2",
    "pointint":"int *",
    "pointfloat":"float *",
    "str":"char",
    None:"void"
    }


def c_include(filename):
    return f'#include "{filename}"'
header = [c_include("QuEST.h"), c_include("stdio.h")]

def init_env(self):
    return f'QuESTEnv Env = createQuESTEnv();'

def Output_to_c(self):
    carg, bindex = self._cargs
    return f'printf("%d ", {carg.name}[{bindex}]);'
    
def Reset_to_c(self):
    qarg = self._qargs
    qargRef = self.resolve_arg(qarg)
    return f'collapseToOutcome(qreg, {qargRef}, 0);'
    
def ClassicalRegister_to_c(self):
    return f'int {self.name}[{self.size}];'+"\n"+f'for (int i = 0; i < {self.size}; i++) {self.name}[i] = 0;'

def QuantumRegister_to_c(self):
    return f"Qureg {self.name} = createQureg({self.size}, Env);"

def Argument_to_c(self):
    if self.classical: return f'qreal {self.name}'
    else: return f'Qureg {self.name}, int {self.name}_index'

def Let_to_c(self):
    var = self.const

    assignee = var.name
    if var.var_type: assignee = f"{var.var_type} {assignee}"

    # Simple declaration
    if var.val is None: return f"{assignee};"

    if type(var.val) is list: value =  f'{{{",".join(var.val)}}}'
    else:  value =  f'{var.val}'
    if var.cast: value = f"({var.cast}) {value}"

    return f"{assignee} = {value};"

def CBlock_to_c(self):
    return "\n".join(self.block)
    
def CallGate_to_c(self):
    printArgs = ""
    if self._qargs:
        printArgs += "qreg, "
        printArgs += ", ".join([self.resolve_arg(qarg) for qarg in self._qargs])
    for carg in self._cargs:
        if carg is None: continue
        if printArgs:
            printArgs += ", "+str(carg)
        else:
            printArgs = str(carg)
    printGate = self.name
    preString = []
    outString = ""    
    for line in preString:
        outString += line + ";\n"
    outString += f"{printGate}({printArgs});"
    return outString

def Comment_to_c(self):
    return "//" + self.comment

def Measure_to_c(self):
    carg = self._cargs
    qarg = self._qargs
    qargRef = self.resolve_arg(qarg)
    cargRef = self.resolve_arg(carg)
    return f"{carg[0].name}[{cargRef}] = measure(qreg, {qargRef});"

def IfBlock_to_c(self):
    return f"if ({self._cond})"

def CreateGate_to_c(self):
    printQargs = ""
    printPargs = ""
    if self._qargs: printQargs = "Qureg qreg, " + ", ".join((f"int {qarg.name}_index" for qarg in self._qargs))
    if self._cargs: printPargs = ", ".join((f"{carg.var_type} {carg.name}" for carg in self._cargs))
        
    printArgs = ", ".join((printQargs, printPargs)).rstrip(", ")
    returnType = typesTranslation[self.returnType]
    outStr = f"{returnType} {self.name}({printArgs}) "
    return outStr

def Loop_to_c(self):
    return  f"for (int {self.var} = {self.start}; {self.var} < {self.end}; {self.var} += {self.step})"

