OMEQASM 2.0;

circuit test[nBits] a[nBits] {
  for i in [1:nBits-1] {

      for j in [1:nBits-1] {
	  CX a[i], a[i+1];
	  if (j == 7) {
	    finish i;
	  }
	}
    }
}
