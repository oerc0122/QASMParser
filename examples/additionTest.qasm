REQASM 1.0;

unitary gate x a {
    U(pi,0,0) a;
}

unitary gate H a {
    U(pi/2,0,pi) a;
}    

unitary gate maj a,b,c
{
  CTRL-x c,b;
  CTRL-x c,a;
  CTRL-CTRL-x a,b,c;
}

unitary gate unmaj a,b,c
{
  CTRL-CTRL-x a,b,c;
  CTRL-x c,a;
  CTRL-x a,b;
}

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
TestAddTwice[n,k] a[n], b[n+2], cin -> out
{
    qbit d;
    creg out;
    Add[n] a[n], b[0:n+1], cin;
    Add[n+1] |d,a[n]|, b, cin;
    measure b[k] -> out;
    reset d;
}


qreg a[12];
qreg b[14];
qbit c;
cbit r;
 
H a;
TestAddTwice[12,0] a, b, c -> r;
TestAddTwice[12,1] a, b, c -> r;
