import os.path
from .QASMTokens import coreTokens, openQASM
from .QASMErrors import *
import re

class QASMFile:

    _QASMFiles = []
    depth_limit = 10
    
    def __init__(self,filename, reqVersion=("2","0")):
        if filename in QASMFile._QASMFiles: raise IOError('Circular dependency in includes')
        if os.path.isfile(filename): self.File = open(filename,'r')
        else: raise FileNotFoundError()
        self.path = filename
        self.name = filename[filename.rfind('/')+1:] # Remove path
        if len(QASMFile._QASMFiles) > self.depth_limit: self._error(recursionError.format(self.depth_limit))
        QASMFile._QASMFiles.append(self.name)
        self.nLine = 0
        temp = ''
        self.header = []
        try:
            line=self.readline()
            while line is not None:
                if openQASM.wholeLineComment(line):
                    self.header += [line.lstrip('/')]
                elif openQASM.version(line):
                    self.version = openQASM.version(line).group('version','minorVer','majorVer')
                    self.QASMType, self.majorVer, self.minorVer = self.version
                    break
                else:
                    self._error('Header of file :\n'+temp+"\n does not contain version")
                line=self.readline()

            if reqVersion[0] > self.version[0] :
                self._error('Unsupported QASM version: {}.{}'.format(*self.version))
        
        except AttributeError:
            self._error("Header does not contain version")
        except RuntimeError:
            self._error(eofWarning.format('trying to determine QASM version'))

    def _error(self, message=""):
        raise IOError(fileWarning.format(message=message,
                                         file=self.name, line=self.nLine))

    def __del__(self):
        try:
            openFiles = QASMFile._QASMFiles
            del openFiles[openFiles.index(self.name)]
            self.File.close()
        except AttributeError:
            return

    def block_split(self, line):
        match = re.findall('(\{|\}|[^{}]+)', line)
        return [inst for inst in match if not re.match('^\s+$',inst)]

    def read_instruction(self):
        line = self.readline()
        lines = ""
        depth = 0
        instructions = []
        while line is not None:
            lines += line.rstrip('\n')
            if openQASM.wholeLineComment(lines):
                yield lines
                lines = ""

            *tmpInstructions, lines = lines.split(';')
            if len(tmpInstructions) > 0:
                instructions = []
                for instruction in tmpInstructions:
                    instructions += self.block_split(instruction)
                while instructions:
                    currInstruction = instructions.pop(0).strip()
                    yield currInstruction
            line = self.readline()
        # Catch remainder
        tmpInstructions = lines.split(';')
    
        for instruction in tmpInstructions:
            instructions += self.block_split(instruction)
        while instructions:
            currInstruction = instructions.pop(0).strip()
            yield currInstruction


    def readline(self):
        """ Reads a line from a file """
        for line in self.File:
            self.nLine += 1
            if coreTokens.blank(line): continue
            return line
        else:
            return None

    def _parent_file(self, parent):
        self.name = parent.name
        self.version = parent.version
        self.QASMType = parent.QASMType
        self.nLine = parent.nLine
        
        
class QASMBlock(QASMFile):
    def __init__(self, parent, block, startline = None):
        self._parent_file(parent)
        if startline: self.nLine = startline
        self.File = block.splitlines()
        self.orig = block

    def __len__(self):
        return len(self.File)
        
    def readline(self):
        """ Reads a line from a file """
        while len(self.File) > 0:
            line = self.File.pop(0)
            self.nLine += 1
            if coreTokens.blank(line): continue
            return line
        else:
            # Recallable
            self.File = self.orig.splitlines()
            return None

    def __del__(self):
        pass

class NullBlock(QASMFile):
    def __init__(self, parent):
        self._parent_file(parent)
        self.File = [';']
        self.read = False
        
    def __len__(self):
        return 0

    def readline(self):
        if not self.read:
            self.read = True
            return "// "
        return None

    def __del__(self):
        pass
