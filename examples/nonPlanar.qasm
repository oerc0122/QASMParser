REQASM 1.0;

qreg a[4];
creg b[4];
CX a[0], a[1];
CX a[1], a[2];
CX a[2], a[3];
CX a[0], a[2];
CX a[0], a[1];
CX a[1], a[2];
CX a[2], a[3];
