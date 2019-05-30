// QASM include file for QuEST functions

REQASM 1.0;

// Direct insertions
unitary opaque PhaseShift(angle) targetQubit;
*** begin opaque PhaseShift
phaseShift(qreg, targetQubit_index, angle);
*** end

unitary opaque ControlledPhaseShift(angle) controlQubit, targetQubit;
*** begin opaque ControlledPhaseShift
controlledPhaseShift(qreg, controlQubit_index, targetQubit_index, angle);
*** end

unitary opaque ControlledPhaseFlip controlQubit, targetQubit;
*** begin opaque ControlledPhaseFlip
controlledPhaseFlip(qreg, controlQubit_index, targetQubit_index);
*** end

unitary opaque SGate targetQubit;
*** begin opaque SGate
sGate(qreg, targetQubit_index);
*** end

unitary opaque TGate targetQubit;
*** begin opaque TGate
tGate(qreg, targetQubit_index);
*** end

unitary opaque RotateX(angle) targetQubit;
*** begin opaque RotateX
rotateX(qreg, targetQubit_index, angle);
*** end

unitary opaque RotateY(angle) targetQubit;
*** begin opaque RotateY
rotateY(qreg, targetQubit_index, angle);
*** end

unitary opaque RotateZ(angle) targetQubit;
*** begin opaque RotateZ
rotateZ(qreg, targetQubit_index, angle);
*** end

unitary opaque ControlledRotateX(angle) controlQubit, targetQubit;
*** begin opaque ControlledRotateX
controlledRotateX(qreg, controlQubit_index, targetQubit_index, angle)
*** end

unitary opaque ControlledRotateY(angle) controlQubit, targetQubit;
*** begin opaque ControlledRotateY
controlledRotateY(qreg, controlQubit_index, targetQubit_index, angle)
*** end

unitary opaque ControlledRotateZ(angle) controlQubit, targetQubit;
*** begin opaque ControlledRotateZ
controlledRotateZ(qreg, controlQubit_index, targetQubit_index, angle)
*** end

unitary opaque PauliX targetQubit;
*** begin opaque PauliX
pauliX(qreg, targetQubit_index)
*** end

unitary opaque ControlledPauliX controlQubit, targetQubit;
*** begin opaque ControlledPauliX
controlledNot(qreg, controlQubit_index, targetQubit_index);
*** end

unitary opaque PauliY targetQubit;
*** begin opaque PauliY
pauliY(qreg, targetQubit_index)
*** end

unitary opaque ControlledPauliY controlQubit, targetQubit;
*** begin opaque ControlledPauliY
controlledPauliY(qreg, controlQubit_index, targetQubit_index);
*** end

unitary opaque PauliZ targetQubit;
*** begin opaque PauliZ
pauliZ(qreg, targetQubit_index)
*** end

unitary opaque Hadamard targetQubit;
*** begin opaque Hadamard
hadamard(qreg, targetQubit_index)
*** end

// Complex insertions

unitary opaque Unitary(r0c0Real, r0c0Imag, r0c1Real, r0c1Imag, r1c0Real, r1c0Imag, r1c1Real, r1c1Imag)  targetQubit;
*** begin opaque Unitary
    ComplexMatrix2 u = {
        .r0c0 = (Complex) {r0c0Real, r0c0Imag},
        .r0c1 = (Complex) {r0c1Real, r0c1Imag},
        .r1c0 = (Complex) {r1c0Real, r1c0Imag},
        .r1c1 = (Complex) {r1c1Real, r1c1Imag}
    };
    unitary(qreg, targetQubit_index, u);
*** end

unitary opaque ControlledUnitary(r0c0Real, r0c0Imag, r0c1Real, r0c1Imag, r1c0Real, r1c0Imag, r1c1Real, r1c1Imag)  controlQubit, targetQubit;
*** begin opaque ControlledUnitary
    ComplexMatrix2 u = {
        .r0c0 = (Complex) {r0c0Real, r0c0Imag},
        .r0c1 = (Complex) {r0c1Real, r0c1Imag},
        .r1c0 = (Complex) {r1c0Real, r1c0Imag},
        .r1c1 = (Complex) {r1c1Real, r1c1Imag}
    };
    unitary(qreg, controlQubit_index, targetQubit_index, u);
*** end

unitary opaque CompactUnitary(alphaReal, alphaImag, betaReal, betaImag) targetQubit;
*** begin opaque CompactUnitary
    Complex alpha = {alphaReal, alphaImag};
    Complex beta  = {betaReal,  betaImag};
    compactUnitary(qreg, targetQubit_index, alpha, beta);
*** end

unitary opaque ControlledCompactUnitary(alphaReal, alphaImag, betaReal, betaImag) controlQubit, targetQubit;
*** begin opaque ControlledCompactUnitary
    Complex alpha = {alphaReal, alphaImag};
    Complex beta  = {betaReal,  betaImag};
    controlledCompactUnitary(qreg, controlQubit_index, targetQubit_index, alpha, beta);
*** end

unitary opaque RotateAroundAxis(angle, xDir, yDir, zDir) targetQubit;
*** begin opaque RotateAroundAxis
    Vector axis = {xDir, yDir, zDir};
    rotateAroundAxis(qreg, targetQubit_index, angle, axis)
*** end

unitary opaque ControlledRotateAroundAxis(angle, xDir, yDir, zDir) controlQubit, targetQubit;
*** begin opaque ControlledRotateAroundAxis
    Vector axis = {xDir, yDir, zDir};
    controlledRotateAroundAxis(qreg, controlQubit_index, targetQubit_index, angle, axis)
*** end

