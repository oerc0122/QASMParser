OMEQASM 2.0;

creg a[2];
creg b[2];
set \a[0], b, a[1]\ = \b[0], a, b[0]\;

circuit test[nBits] a[nBits] {
  for i in [1:nBits-1] {

      for j in [1:nBits-1] {
	  CX a[i], a[i+1];
	  if (j == 7) {
	    next i;
	    finish i;
	    finish test;
	  }
	}
    }
}
finish quantum process;
