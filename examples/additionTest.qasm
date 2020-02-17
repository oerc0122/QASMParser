unitary circuit
  Add[n] a[n], b[n+1], cin
  {
    maj cin, b[0], a[0];
    for j in [1:n-1] {
	maj a[j-1], b[j], a[j];
      }
    CX a[n-1], b[n];

    for j in [n-1:1:-1] {
	unmaj a[j-1], b[j], a[j];
    }
    
    unmaj cin, b[0], a[0];
  }

circuit
  TestAddTwice[n](k) a[n], b[n+2], cin -> out
  {
    qbit d;
    Add[n] a[n], b[0:n+1], cin;
    Add[n+1] |d,a[n]|, b, cin;
    meas b[k] -> out;
    reset d;
  }


qreg a[12];
qreg b[14];
qbit c;
cbit r;
 
H a;
TestAddTwice[12](0) a, b, c -> r;
TestAddTwice[12](1) a, b, c -> r;
