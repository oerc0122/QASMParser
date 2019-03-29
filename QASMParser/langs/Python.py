from QASMParser.QASMTypes import *

def set_lang():
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
    PyBlock.to_lang = PyBlock_to_Python
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
    return f'from {filename} import *'
header = [Python_include("QuESTLibs")]

def init_env(self):
    return f'Env = createQuESTEnv()'

def Output_to_Python(self):
    carg, bindex = self._cargs
    return f'print({carg.name}[{bindex}])'

def Reset_to_Python(self):
    qarg = self._qargs
    qargRef = self.resolve_arg(qarg)
    return f'collapseToOutcome(qreg, {qargRef}, 0)'
    
def ClassicalRegister_to_Python(self):
    return f'{self.name} = [0]*{self.size}'

def QuantumRegister_to_Python(self):
    return f"{self.name} = createQureg({self.size}, Env)"

def Argument_to_Python(self):
    if self.classical: return f'{self.name}'
    else: return f'{self.name}, {self.name}_index'

def Let_to_Python(self):
    var = self.const
    assignee = var.name

    # Simple declaration
    if var.val is None and var.var_type is None: return f"{assignee} = None"
    elif var.val is None and var.var_type: return f'{assignee} = {var.var_type}()' 

    if type(var.val) is list: value = ",".join(var.val)
    else:  value =  f'{var.val}'
    if var.cast: value = f"{var.cast}({value})"

    return f"{assignee} = {value}"
    
def PyBlock_to_Python(self):
    return ""
    
def CallGate_to_Python(self):
    printArgs = ""
    if self._qargs:
        printArgs += "qreg, "
        printArgs += ", ".join([self.resolve_arg(qarg) for qarg in self._qargs])
    for carg in self._cargs:
        if printArgs:
            printArgs += ", "+carg
        else:
            printArgs = carg
    printGate = self.name
    preString = []
    outString = ""    
    for line in preString:
        outString += line + ";\n"
    outString += f"{printGate}({printArgs})"
    return outString

def Comment_to_Python(self):
    return "#" + self.comment

def Measure_to_Python(self):
    carg, bindex = self._cargs
    qarg = self._qargs
    qargRef = self.resolve_arg(qarg)
    return f"{carg.name}[{bindex}] = measure(qreg, {qargRef})"

def IfBlock_to_Python(self):
    return f"if ({self._cond})"

def CreateGate_to_Python(self):
    if type(self._code[0]) is Verbatim and self._code[0].line == ";": self._code = [Verbatim("pass")]
    printArgs = ""
    if self._qargs:
        printArgs += "qreg"
        printArgs += ", " + ", ".join([f"{qarg}_index" for qarg in self._qargs])
    for carg in self._cargs:
        if printArgs: printArgs += ", "+carg
        else: printArgs += carg
    outStr = f"def {self.name}({printArgs})"
    return outStr

def Loop_to_Python(self):
    return  f"for {self.var} in range({self.start}, {self.end}, {self.step})"


