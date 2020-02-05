// Program containing functions relating to the OME/REQASM specification
// Written by J. Wilkins May 2019
# include "reqasm.h"
# include <math.h>
# include <stdio.h>
# include <stdlib.h>
# include <string.h>

void U(Qureg qreg, int a, float theta, float phi, float lambda) {

  rotateZ(qreg,a,lambda);
  rotateX(qreg,a,theta);
  rotateZ(qreg,a,phi);

}
void CX(Qureg qreg, int a, int b) {
  controlledNot(qreg, a, b);
}

bitstr toBitstr(int *bits, int nBits) {
  bitstr outBits;
  outBits.str = (char*) malloc(sizeof(outBits.str) * nBits);
  outBits.val = (int*) malloc(sizeof(outBits.val) * nBits);
  outBits.nBits = nBits;
  for (int i = 0; i < nBits; i++) {
    sprintf(&outBits.str[i], "%1d", bits[i]);
    outBits.val[i] = bits[i];
  }
  return outBits;
}

void printBitstr(bitstr bits) {
  printf("%s", bits.str);
  printf("\n");
}

int countOfBits(bitstr bits) {
  int sum = 0;
  for (int j = 0; j < bits.nBits; j++) {
    sum += bits.val[j];
  }
  return sum;
}

int decOfBits(bitstr bits) {
  int sum = 0;
  int i = 1;
  for (int j = 0; j < bits.nBits; j++) {
    sum += bits.val[j] * i;
    i *= 2;
  }
  return sum;


}

_Bool orOfBits (bitstr bits) {
  _Bool test = 0;
  for (int j = 0; j < bits.nBits; j++) {
    if (bits.val[j]) {
      test = 1;
      goto endOR;
    }
  }
 endOR:
  return test;
}

_Bool xorOfBits(bitstr bits) {
  _Bool test = countOfBits(bits)%2;
  return test;
}

_Bool andOfBits(bitstr bits) {
  _Bool test = 1;
  for (int j = 0; j < bits.nBits; j++) {
    if (bits.val[j]) {
      test = 0;
      goto endAND;
    }
  }
 endAND:
  return test;
}

_Bool orOf(int* a, int nBits) {
  bitstr temp = toBitstr(a, nBits);
  return orOfBits(temp);
}

_Bool xorOf(int* a, int nBits) {
  bitstr temp = toBitstr(a, nBits);
  return xorOfBits(temp);
}

_Bool andOf(int* a, int nBits) {
  bitstr temp = toBitstr(a, nBits);
  return andOfBits(temp);
}

int decOf(int* a, int nBits) {
  bitstr temp = toBitstr(a, nBits);
  return decOfBits(temp);
}

int fllog(int a, int c) {
  if (a < 1 || c < 2) {
    perror("Bad values passed to fllog");
    exit(-1);
  }
  return floor(log((double) a)/log((double) c));
}

int powrem(int a, int c) {
  if (a < 1 || c < 2) {
    perror("Bad values passed to fllog");
    exit(-1);
  }
  return a - pow(c, fllog(a,c));
}

void setArr(int n, int* inArr, int* outArr) {
    for (int i=0; i < n; i++) {
        outArr[i] = inArr[i];
    }
}
