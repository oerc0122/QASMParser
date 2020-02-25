// General purpose adder circuit

REQASM 1.0;
include "qelib1.inc";

unitary gate maj a,b,c
{
    cx c,b;
    cx c,a;
    ccx a,b,c;
}

unitary gate unmaj a,b,c
{
    ccx a,b,c;
    cx c,a;
    cx a,b;
}

circuit add[nBits] a[nBits],b[nBits],in,out -> ans {
    maj in, b[0], a[0];
    for bit in [1:nBits-1] {
	maj a[bit-1], b[bit], a[bit];
      }
    cx a[nBits-1], out;

    for bit in [nBits-1:1:-1] {
	unmaj a[bit-1], b[bit], a[bit];
        }
    
    /* for bit in [1:nBits-1] { */
    /*     unmaj a[nBits-1-bit], b[nBits-bit], a[nBits-bit]; */
    /*   } */
    unmaj in, b[0], a[0];
    creg ans[nBits + 1];
    for bit in [0:nBits-1] {
	measure b[bit] -> ans[bit];
      }
    measure out -> ans[nBits];
}

circuit printNum[nBits] a[nBits] {
    creg tmp[nBits];
    measure a -> tmp;
    output tmp;
    *** begin classical
    printf("= %d\n", decOf(tmp, nBits));
    *** end
}

val bitNum = 5;

qreg cin;
qreg a[bitNum];
qreg b[bitNum];
qreg cout;
creg ans[bitNum+1];

x a[1:2]; // Set a to 6
x b[4];   // set b to 8

printNum[bitNum] a;
printNum[bitNum] b;
add[bitNum] a,b,cin,cout -> ans;
output ans;
*** begin classical
printf("= %d\n", decOf(ans, bitNum+1));
*** end
