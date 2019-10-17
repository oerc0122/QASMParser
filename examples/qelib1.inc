// Quantum Experience (QE) Standard Header
// file: qelib1.inc

OPENQASM 2.0;

// --- QE Hardware primitives ---

// 3-parameter 2-pulse single qubit unitary gate
unitary gate u3(theta,phi,lambda) q { U(theta,phi,lambda) q; }
// 2-parameter 1-pulse single qubit unitary gate
unitary gate u2(phi,lambda) q { U(pi/2,phi,lambda) q; }
// 1-parameter 0-pulse single qubit unitary gate
unitary gate u1(lambda) q { U(0,0,lambda) q; }
// controlled-NOT
unitary gate cx c,t { CX c,t; }
// idle unitary gate (identity)
unitary gate id a { U(0,0,0) a; }

// --- QE Standard Unitary Gates ---

// Pauli unitary gate: bit-flip
unitary gate x a { u3(pi,0,pi) a; }
// Pauli unitary gate: bit and phase flip
unitary gate y a { u3(pi,pi/2,pi/2) a; }
// Pauli unitary gate: phase flip
unitary gate z a { u1(pi) a; }
// Clifford unitary gate: Hadamard
unitary gate h a { u2(0,pi) a; }
// Clifford unitary gate: sqrt(Z) phase unitary gate
unitary gate s a { u1(pi/2) a; }
// Clifford unitary gate: conjuunitary gate of sqrt(Z)
unitary gate sdg a { u1(-pi/2) a; }
// C3 unitary gate: sqrt(S) phase unitary gate
unitary gate t a { u1(pi/4) a; }
// C3 unitary gate: conjuunitary gate of sqrt(S)
unitary gate tdg a { u1(-pi/4) a; }

// --- Standard rotations ---
// Rotation around X-axis
unitary gate rx(theta) a { u3(theta,-pi/2,pi/2) a; }
// rotation around Y-axis
unitary gate ry(theta) a { u3(theta,0,0) a; }
// rotation around Z axis
unitary gate rz(phi) a { u1(phi) a; }

// --- QE Standard User-Defined Unitary Gates  ---

// controlled-Phase
unitary gate cz a,b { h b; cx a,b; h b; }
// controlled-Y
unitary gate cy a,b { sdg b; cx a,b; s b; }
// controlled-H
unitary gate ch a,b {
h b; sdg b;
cx a,b;
h b; t b;
cx a,b;
t b; h b; s b; x b; s a;
}
// C3 unitary gate: Toffoli
unitary gate ccx a,b,c
{
  h c;
  cx b,c; tdg c;
  cx a,c; t c;
  cx b,c; tdg c;
  cx a,c; t b; t c; h c;
  cx a,b; t a; tdg b;
  cx a,b;
}
// controlled rz rotation
unitary gate crz(lambda) a,b
{
  u1(lambda/2) b;
  cx a,b;
  u1(-lambda/2) b;
  cx a,b;
}
// controlled phase rotation
unitary gate cu1(lambda) a,b
{
  u1(lambda/2) a;
  cx a,b;
  u1(-lambda/2) b;
  cx a,b;
  u1(lambda/2) b;
}
// controlled-U
unitary gate cu3(theta,phi,lambda) c, t
{
  // implements controlled-U(theta,phi,lambda) with  target t and control c
  u1((lambda-phi)/2) t;
  cx c,t;
  u3(-theta/2,0,-(phi+lambda)/2) t;
  cx c,t;
  u3(theta/2,phi,0) t;
}

