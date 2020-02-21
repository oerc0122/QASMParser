"""
Extend the ProgFile to transpile code
"""

from importlib import import_module
import sys
import os.path

from QASMParser.parser.types import (Comment, Include, Gate, Opaque, Verbatim, InitEnv, QuantumRegister, Let, CBlock)

from .errors import(langNotDefWarning, langMismatchWarning)


def to_lang(codeObj, filename=None, langOut="C", **options):
    """
    Translate file into provided language.
    If filename is provided write translation to file.
    Replace included files with their in language equivalents for module support.

    :param filename: output file to write
    :param module: whether to compile
    :param includes: dictionary of substitutions for included files
    :param langOut: output language
    :param verbose: whether to provide original QASM alongside
    :returns: None
    :rtype: None
    """
    includes = options.get("includes", {})

    try:
        lang = import_module(f"QASMToQuEST.langs.{langOut}")
        lang.set_lang()
    except ImportError:
        raise NotImplementedError(langNotDefWarning.format(langOut))

    indent = lang.INDENT
    if codeObj.classLang is not None and codeObj.classLang != langOut:
        raise NotImplementedError(langMismatchWarning.format(codeObj.classLang, langOut))

    def print_code(codeObj, code, outputFile):
        nonlocal depth
        depth += 1
        for line in code:
            # Verbose -- Print original
            if options["verbose"] and hasattr(line, 'original') and not isinstance(line, Comment):
                writeln(Comment(codeObj, line.original).to_lang() + "\n")

            if hasattr(line, "inlineComment"): # Inline comments
                writeln(line.inlineComment.to_lang())

            if hasattr(line, "loops") and line.loops: # Handle loops
                writeln(line.loops.to_lang() + lang.BLOCKOPEN)
                print_code(codeObj, line.loops.code, outputFile)
                writeln(lang.BLOCKCLOSE)

            elif isinstance(line, CBlock): # Handle verbatim language blocks
                writeln(line.to_lang())

            elif hasattr(line, "code"): # Print children
                writeln(line.to_lang() + lang.BLOCKOPEN)
                print_code(codeObj, line.code, outputFile)
                writeln(lang.BLOCKCLOSE)

            elif issubclass(type(line), Verbatim):
                if lang.BLOCKCLOSE and lang.BLOCKCLOSE in line.line:
                    depth -= 1
                writeln(line.to_lang())
                if lang.BLOCKOPEN and lang.BLOCKOPEN in line.line:
                    depth += 1

            else: # Print codeObj
                writeln(line.to_lang())

        depth -= 1

    if filename:
        outputFile = open(filename, 'w')
    else:
        outputFile = sys.stdout

    # Create copy to work with
    codeToWrite = codeObj.code[:]
    depth = -1

    writeln = lambda writeIn: [outputFile.write(depth*indent + toWrite + "\n")
                               for toWrite in writeIn.splitlines()]

    for line in codeObj.currentFile.header:
        writeln(Comment(codeObj, line).to_lang())

    # If our language needs to add things to the header
    if options["module"]:
        if filename:
            funcName = os.path.splitext(os.path.basename(filename))[0]
        else:
            funcName = "module"
    else:
        funcName = "main"
        if hasattr(lang, 'HEADER'):
            if isinstance(lang.HEADER, (list, tuple)):
                for line in lang.HEADER:
                    writeln(line)
            elif isinstance(lang.HEADER, str):
                writeln(lang.HEADER)

    incs = (x for x in codeToWrite if isinstance(x, Include))
    for include in incs:
        target = codeToWrite.index(include)
        if include.filename in includes:
            codeToWrite[target].set_import(includes[include.filename])
        else:
            codeToWrite[target:target+1] = include.raw_code

    if lang.HOIST_INCLUDES:
        codeToWrite = sorted(codeToWrite, key=lambda x: isinstance(x, Include))
        while isinstance(codeToWrite[-1], Include):
            print_code(codeObj, [codeToWrite.pop()], outputFile)

    if codeObj.useTN:
        lang.UseTN()
        writeln(lang.INCLUDE_TN)

    if options["include_internals"]:
        codeToWrite = list(Gate.internalGates.values()) + codeToWrite

    if lang.HOIST_FUNCS:
        codeToWrite = sorted(codeToWrite, key=lambda x: issubclass(type(x), Gate))
        gate = []
        while codeToWrite and issubclass(type(codeToWrite[-1]), Gate):
            gate.append(codeToWrite.pop())
        print_code(codeObj, reversed(gate), outputFile)

    # Hoist qregs
    codeToWrite = [line for line in codeToWrite if line not in codeObj.quantumRegisters]
    codeToWrite = fix_qureg(codeObj) + codeToWrite

    if any([not isinstance(line, Comment) for line in codeToWrite]):
        mainProg = Opaque(codeObj, funcName, returnType="int")
        mainProg.set_code(codeToWrite)

    print_code(codeObj, [mainProg], outputFile)

    if filename:
        outputFile.close()

def fix_qureg(codeObj):
    """ Fix quantum registers to align with QuEST style """
    code = [InitEnv(codeObj)]
    for reg in codeObj.quantumRegisters:
        code += [Comment(codeObj, f'{reg.name}[{reg.start}:{reg.end-1}] => {", ".join(map(str, reg.mapping))}')]
        code += [Let(codeObj, (reg.name, "const listint"), (reg.mapping, None))]

    if not codeObj.useTN:
        code += [QuantumRegister(codeObj, "qreg", QuantumRegister.numQubits + QuantumRegister.numGateQubits)]
    else:
        for reg in codeObj.quantumRegisters:
            code += [Comment(codeObj, f'{reg.name}[{reg.start}:{reg.end-1}] => {", ".join(map(str, reg.TNMapping))}')]
            code += [Let(codeObj, (reg.name+"_TN", "listint"), (reg.TNMapping, None))]
        code += [codeObj.partition]
    return code

def run(codeObj):
    """ Run constructed code in Python """
    try:
        lang = import_module(f"QASMToQuEST.langs.Python")
        lang.set_lang()
    except ImportError:
        raise NotImplementedError(langNotDefWarning.format(lang))

    for line in codeObj.code:
        exec(line.to_lang())
