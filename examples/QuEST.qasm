// QASM include file for QuEST functions

REQASM 1.0;

// Direct insertions
unitary opaque PhaseShift(angle) targetQubit;
*** begin opaque PhaseShift
phaseShift(qreg, targetQubit, angle);
*** end

unitary opaque ControlledPhaseShift(angle) controlQubit, targetQubit;
*** begin opaque ControlledPhaseShift
controlledPhaseShift(qreg, controlQubit, targetQubit, angle);
*** end

unitary opaque ControlledPhaseFlip controlQubit, targetQubit;
*** begin opaque ControlledPhaseFlip
controlledPhaseFlip(qreg, controlQubit, targetQubit);
*** end

unitary opaque SGate targetQubit;
*** begin opaque SGate
sGate(qreg, targetQubit);
*** end

unitary opaque TGate targetQubit;
*** begin opaque TGate
tGate(qreg, targetQubit);
*** end

unitary opaque RotateX(angle) targetQubit;
*** begin opaque RotateX
rotateX(qreg, targetQubit, angle);
*** end

unitary opaque RotateY(angle) targetQubit;
*** begin opaque RotateY
rotateY(qreg, targetQubit, angle);
*** end

unitary opaque RotateZ(angle) targetQubit;
*** begin opaque RotateZ
rotateZ(qreg, targetQubit, angle);
*** end

unitary opaque ControlledRotateX(angle) controlQubit, targetQubit;
*** begin opaque ControlledRotateX
controlledRotateX(qreg, controlQubit, targetQubit, angle)
*** end

unitary opaque ControlledRotateY(angle) controlQubit, targetQubit;
*** begin opaque ControlledRotateY
controlledRotateY(qreg, controlQubit, targetQubit, angle)
*** end

unitary opaque ControlledRotateZ(angle) controlQubit, targetQubit;
*** begin opaque ControlledRotateZ
controlledRotateZ(qreg, controlQubit, targetQubit, angle)
*** end

unitary opaque PauliX targetQubit;
*** begin opaque PauliX
pauliX(qreg, targetQubit)
*** end

unitary opaque ControlledPauliX controlQubit, targetQubit;
*** begin opaque ControlledPauliX
controlledNot(qreg, controlQubit, targetQubit);
*** end

unitary opaque PauliY targetQubit;
*** begin opaque PauliY
pauliY(qreg, targetQubit)
*** end

unitary opaque ControlledPauliY controlQubit, targetQubit;
*** begin opaque ControlledPauliY
controlledPauliY(qreg, controlQubit, targetQubit);
*** end

unitary opaque PauliZ targetQubit;
*** begin opaque PauliZ
pauliZ(qreg, targetQubit)
*** end

unitary opaque Hadamard targetQubit;
*** begin opaque Hadamard
hadamard(qreg, targetQubit)
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
    unitary(qreg, targetQubit, u);
*** end

unitary opaque ControlledUnitary(r0c0Real, r0c0Imag, r0c1Real, r0c1Imag, r1c0Real, r1c0Imag, r1c1Real, r1c1Imag)  controlQubit, targetQubit;
*** begin opaque ControlledUnitary
    ComplexMatrix2 u = {
        .r0c0 = (Complex) {r0c0Real, r0c0Imag},
        .r0c1 = (Complex) {r0c1Real, r0c1Imag},
        .r1c0 = (Complex) {r1c0Real, r1c0Imag},
        .r1c1 = (Complex) {r1c1Real, r1c1Imag}
    };
    unitary(qreg, controlQubit, targetQubit, u);
*** end

unitary opaque CompactUnitary(alphaReal, alphaImag, betaReal, betaImag) targetQubit;
*** begin opaque CompactUnitary
    Complex alpha = {alphaReal, alphaImag};
    Complex beta  = {betaReal,  betaImag};
    compactUnitary(qreg, targetQubit, alpha, beta);
*** end

unitary opaque ControlledCompactUnitary(alphaReal, alphaImag, betaReal, betaImag) controlQubit, targetQubit;
*** begin opaque ControlledCompactUnitary
    Complex alpha = {alphaReal, alphaImag};
    Complex beta  = {betaReal,  betaImag};
    controlledCompactUnitary(qreg, controlQubit, targetQubit, alpha, beta);
*** end

unitary opaque RotateAroundAxis(angle, xDir, yDir, zDir) targetQubit;
*** begin opaque RotateAroundAxis
    Vector axis = {xDir, yDir, zDir};
    rotateAroundAxis(qreg, targetQubit, angle, axis)
*** end

unitary opaque ControlledRotateAroundAxis(angle, xDir, yDir, zDir) controlQubit, targetQubit;
*** begin opaque ControlledRotateAroundAxis
    Vector axis = {xDir, yDir, zDir};
    controlledRotateAroundAxis(qreg, controlQubit, targetQubit, angle, axis)
*** end

unitary opaque MultiControlledUnitary(r0c0Real, r0c0Imag,
				      r0c1Real, r0c1Imag,
				      r1c0Real, r1c0Imag,
				      r1c1Real, r1c1Imag) [nCtrls] ctrls[nCtrls], targ;

*** begin opaque MultiControlledUnitary
not = (ComplexMatrix2) { .r0c0 = (Complex) {r0c0Real, r0c0Imag},
			 .r0c1 = (Complex) {r0c1Real, r0c1Imag},
			 .r1c0 = (Complex) {r1c0Real, r1c0Imag},
			 .r1c1 = (Complex) {r1c1Real, r1c1Imag} };
  multiControlledUnitary(qreg, ctrls, nCtrls, targ, not);
*** end

unitary opaque MultiCtrlNot[nCtrls] ctrls[nCtrls], targ;
*** begin opaque MultiCtrlNot
  not = (ComplexMatrix2) { .r0c0 = (Complex) {0.,0.},
			   .r0c1 = (Complex) {1.,0.},
			   .r1c0 = (Complex) {1.,0.},
			   .r1c1 = (Complex) {0.,0.} };
  multiControlledUnitary(qreg, ctrls, nCtrls, targ, not);
*** end
