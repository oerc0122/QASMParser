// quantum ripple-carry adder from Cuccaro et al, quant-ph/0410184
OMEQASM 2.0;
include "qelib1.inc";
include "QuEST.qasm";

*** ClassLang "C";

gate majority a,b,c
{ 
  cx c,b; 
  cx c,a; 
  ccx a,b,c; 
}

opaque magic a;

opaque rotateytate a;
*** begin opaque rotateytate
rotateX(qreg, a_index, 13.);
rotateZ(qreg, a_index, 15.1);
rotateY(qreg, a_index, 91.);
*** end 

gate unmaj a,b,c 
{
  ccx a,b,c; 
  cx c,a; 
  cx a,b;
}

*** begin classical
printf("%s \n", "Hello!");
int A = 3;
float C = 0.6;
for (int i = 1; i < 3; i++) {
   printf("%s %d","hi",i);
}
*** end

qreg cin[1];
qreg a[4];
qreg b[4];
qreg cout[1];
creg ans[5];

// set input states
x a[0]; // a = 0001
x b;    // b = 1111

let QWE = sqrt(8.);
let Barf = a[0] and T;
let Twip = fllog(2,51);
barrier a, b;

// add a to b, storing result in b
majority cin[0],b[0],a[0];
majority a[0],b[1],a[1];
majority a[1],b[2],a[2];
majority a[2],b[3],a[3];

cx a[3],cout[0];

unmaj a[2],b[3],a[3];
unmaj a[1],b[2],a[2];
unmaj a[0],b[1],a[1];
unmaj cin[0],b[0],a[0];

measure b[0] -> ans[0];
measure b[1] -> ans[1];
measure b[2] -> ans[2];
measure b[3] -> ans[3];

measure cout[0] -> ans[4];

creg loop_de[4];
measure b -> loop_de;

if ((ans[1] == 1) and (ans[0] == 2))
{
  *** classical printf("%i", 128);
}

let lambda = sqrt(1);
U(0,0,lambda) a;
if (ans[0] == 1) U a;

alias geoff to a;
reset a;
reset b[2];

alias q to a[1:2];

x q;

for Q in [1:3] {
    U(1,1,1) a[Q];
}

output ans;

let Q = 3;
while ( Q < 3 )
{
 output ans[2:3];
 let Q = Q + 1;
}

Hadamard q;
ControlledRotateAroundAxis(90., 0., 1., 1.) a,b;