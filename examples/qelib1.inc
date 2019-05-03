OPENQASM 2.0;

// I'm another file
gate U(theta, phi, lambda) a,b {
     rotateZ(lambda) a;
     rotateY(theta) a;
     rotateZ(phi) a;
}
