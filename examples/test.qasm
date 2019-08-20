REQASM 1.0;

gate H x {
  U(0.,0.,pi) x;
}

qreg a[4];
creg Q[4];
H a[0];
H a[1];
H a[3];
CX a[0], a[2];

measure a -> Q;
