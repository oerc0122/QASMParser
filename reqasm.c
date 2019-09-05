// Program containing functions relating to the OME/REQASM specification
// Written by J. Wilkins May 2019
# include "reqasm.h"
# include <math.h>
# include <stdio.h>
# include <stdlib.h>
# include <string.h>

void U(Qureg qreg, int a, float theta, float phi, float lambda) {
  
  rotateZ(qreg,a_index,lambda);
  rotateX(qreg,a_index,theta);
  rotateZ(qreg,a_index,phi);
          
}
void CX(Qureg qreg, int a, int b) {
  controlledNot(qreg, a_index, b_index);
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

int main() {
  int nBits = 10;
  int bits[10] = {1,0,0,1,1,0,0,1,1};
  bitstr rand = toBitstr(bits, nBits);
  for (int i = 0; i < nBits; i++) bits[i] = 0;
  bitstr zero = toBitstr(bits, nBits);
  for (int i = 0; i < nBits; i++) bits[i] = 1;
  bitstr ones = toBitstr(bits, nBits);
  printBitstr(rand);
  printBitstr(zero);
  printBitstr(ones);
  _Bool a,b,c = 0;

  a = andOfBits(rand);
  b = orOfBits(rand);
  c = xorOfBits(rand);
  printf("%d %d %d\n",a, b, c);

  a = andOfBits(zero);
  b = orOfBits(zero);
  c = xorOfBits(zero);
  printf("%d %d %d\n",a, b, c);

  a = andOfBits(ones);
  b = orOfBits(ones);
  c = xorOfBits(ones);
  printf("%d %d %d\n",a, b, c);

  a = andOfBits(ones) && andOfBits(zero);
  b = orOfBits(ones)  && orOfBits(zero);
  c = xorOfBits(ones) && xorOfBits(zero);
  printf("%d %d %d\n",a, b, c);

  printf("%d %d\n", decOfBits(rand), countOfBits(rand));

  printf("%d %d\n", fllog(154, 2), powrem(154, 2));
  
  int bits2[10] = {1,0,0,1,1,0,0,1,1};
  a = andOf(bits2, nBits);
  b = orOf(bits2, nBits);
  c = xorOf(bits2, nBits);
  printf("%d %d %d\n",a, b, c);

  return 0;
}
