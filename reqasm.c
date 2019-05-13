// Program containing functions relating to the OME/REQASM specification
// Written by J. Wilkins May 2019
# include "reqasm.h"
# include <math.h>
# include <stdio.h>
# include <stdlib.h>
# include <string.h>

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

int countOf(bitstr bits) {
  int sum = 0;
  for (int j = 0; j < bits.nBits; j++) {
    sum += bits.val[j];
  }
  return sum;
}

int decOf(bitstr bits) {
  int sum = 0;
  int i = 1;
  for (int j = 0; j < bits.nBits; j++) {
    sum += bits.val[j] * i;
    i *= 2;
  }
  return sum;


}

_Bool orOf (bitstr bits) {
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

_Bool xorOf(bitstr bits) {
  _Bool test = countOf(bits)%2;
  return test;
}

_Bool andOf(bitstr bits) {
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

  a = andOf(rand);
  b = orOf(rand);
  c = xorOf(rand);
  printf("%d %d %d\n",a, b, c);

  a = andOf(zero);
  b = orOf(zero);
  c = xorOf(zero);
  printf("%d %d %d\n",a, b, c);

  a = andOf(ones);
  b = orOf(ones);
  c = xorOf(ones);
  printf("%d %d %d\n",a, b, c);

  a = andOf(ones) && andOf(zero);
  b = orOf(ones)  && orOf(zero);
  c = xorOf(ones) && xorOf(zero);
  printf("%d %d %d\n",a, b, c);

  printf("%d %d\n", decOf(rand), countOf(rand));

  printf("%d %d\n", fllog(154, 2), powrem(154, 2));
  
  return 1;
}
