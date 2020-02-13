# QASMParser
A Utility for transpiling an extended QASM variant into QuEST or Pyquest inputs, with the capability to be extended to any other imperative quantum-simulator input.

# Requirements

## Core
 - Python 3.6+
 - [PyParsing][PyParsing]
## Tensor network functionality
 - [METIS][METIS]
 - [NumPy][Numpy]
 - [NetworkX][NetworkX] 
## TN Drawing
 - [PyGraphViz][PyGraphViz]

# Usage

Basic help can be found by running `QASMToQuEST.py -h`

```
usage: QASMToQuEST.py [-h] [-o OUTPUT] [-l LANGUAGE] [-d] [-c]
                      [-I QASMFILE=CFILE,QASMFILE2=CFILE2,...] [-a]
                      [-p [PRINT]] [-e [ENTANGLEMENT]] [-t]
                      [--max-depth MAX_DEPTH] [--include-internals]
                      [-P PARTITION]
                      sources [sources ...]

QASM parser to translate from QASM to QuEST input

positional arguments:
  sources               List of sources to compile

optional arguments:
  -h, --help            show this help message and exit
  -o OUTPUT, --output OUTPUT
                        File to compile to
  -l LANGUAGE, --language LANGUAGE
                        Output file language
  -d, --debug           Output original QASM in translation
  -c, --to-module       Compile as module for inclusion into larger project
  -I QASMFILE=CFILE,QASMFILE2=CFILE2,..., --include QASMFILE=CFILE,QASMFILE2=CFILE2,...
                        Include a pre-transpiled source
  -a, --analyse         Print adjacency matrix info
  -p [PRINT], --print [PRINT]
                        Print graphical summary of circuit to file
  -e [ENTANGLEMENT], --entanglement [ENTANGLEMENT]
                        Print graphical summary of entanglements to file
  -t, --dummy-partition
                        Calculate effects of partition without compilation
  --max-depth MAX_DEPTH
                        Max depth for analysis and printing
  --include-internals   Include internal gates explicitly
  -P PARTITION, --partition PARTITION
                        Set partitioning optimisation type:
                            0 = None  -- Do not attempt to partition,
                            1 = Registers -- Partition based on specification of qregs in QASM,
                            2 = Space-like -- Slice only in qreg space based on adjacent slice-cost analysis,
                            3 = Space-time-like -- Perform full graph analysis and attempt to partition
```

### Basic usage

In general, a QASM file can be compiled with the following:

```QASMToQuEST.py -o test.c test.qasm```

Provided that all requirements including QASM includes are in the directory from which QASMToQuEST was run. 

### Explicit language

If the output language can be determined through the file extension of the output file, it will be. Otherwise, it will be necessary to define the language using the `-l` flag. 

```QASMToQuEST.py -o temp -l C test.qasm```

### Modules

In order to avoid having to recompile an included file, or to avoid it cluttering the final output, it is possible to part compile to something resembling a module. Essentially, this does not include the main or other includes of the module, allowing it to be imported in the output, rather than being included verbatim. 

```QASMToQuEST.py -c -o module.c module.qasm```

This can then replace a QASM include by using the `-I` flag.

```QASMToQuEST.py -I module.qasm=module.c -o test.c test.qasm```

### Include internals

Includes source for the core OpenQASM/REQASM gates into the output file, for ease of compilation if not included by other means. Will clutter output source, though.

### Debug

Prints the original QASM line before each translation to ensure the translation is correct.

## Tensor Network & Analysis Options

It is possible to turn on Tensor Network partitioning by setting the `-P` flag to a vlue greater than 0. Enabling tensor partitioning will also enable options to do with analysing the circuit. In future, it will be possible to perform these analyses without enabling partitioning, but for now, it is too heavily entangled (ho ho). 

### Partitioning options

Partitioning has 4 different levels which can be selected. 

Level 0 (`-P 0`) disables partitioning and is the default option.

Level 1 (`-P 1`) enables purely space-like partitioning (separation of qubits globally) based on the declaration of qregs in the QASM.

Level 2 (`-P 2`) enables purely space-like partitioning based on rudimentary analysis of the entanglements between qubits.

Level 3 (`-P 3`) enables full space-time-like partitioning based on recursive network analysis methods.

### Adjacency Matrix

The `-a` option prints the circuit's qubit adjacency matrix which is a count of the number of entangling operations between qubits. 

### Circuit diagram and entanglements

The `-p` option causes Network X to print out a grpahical representation of the circuit diagram in a standard format. The file is output to the argument and the format is detected based on the file extension.

The `-e` option works similarly, but prints the entanglement diagram between qubits.
  
### Max depth

Max depth (`--max-depth`) determines the depth of gates (maximum stack depth) to which the code will go to find analyse the circuit (including drawing functions). By default it will follow all gates until it hits core QASM or Opaque gates.

### Dummy partition

Dummy partition (`-t`) will perform the analyses related to partitioning but will not output a source file, instead it will draw the partitioned graphs to a file coloured by the partition they represent.

[METIS]:https://pypi.org/project/metis/
[PyGraphViz]:https://pypi.org/project/pygraphviz/
[PyParsing]:https://pypi.org/project/pyparsing/
[Numpy]:https://pypi.org/project/numpy/
[NetworkX]:https://pypi.org/project/networkx/
