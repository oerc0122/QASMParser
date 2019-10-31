// Includes for using REQASM features in C codes

#ifndef REQASM_H
#define REQASM_H

#include "QuEST.h"

typedef struct bitstr
{
  char *str;
  int *val;
  int  nBits;
} bitstr;

const qreal pi = 3.141592653589;
const qreal e  = 2.718281828459;
const _Bool T  = 1;
const _Bool F  = 0;

// Basic gates
void U(Qureg qreg, int a, float theta, float phi, float lambda);
void CX(Qureg qreg, int a, int b);
void inv_U(Qureg qreg, int a, float theta, float phi, float lambda);


bitstr toBitstr(int *bits, int nBits);
_Bool orOf(int *bits, int nBits);
_Bool xorOf(int *bits, int nBits);
_Bool andOf(int *bits, int nBits);

_Bool orOfBits (bitstr bits);
_Bool xorOfBits(bitstr bits);
_Bool andOfBits(bitstr bits);

int fllog(int c, int a);
int powrem(int a, int c);

ComplexMatrix2 uPauliX = {
			  .r0c0 = {0.,0.},
			  .r1c0 = {1.,0.},
			  .r0c1 = {1.,0.},
			  .r1c1 = {0.,0.}
};
ComplexMatrix2 uHadamard = {
			    .r0c0 = {.real=1/sqrt(2), .imag=0},
			    .r0c1 = {.real=1/sqrt(2), .imag=0},
			    .r1c0 = {.real=1/sqrt(2), .imag=0},
			    .r1c1 = {.real=-1/sqrt(2), .imag=0}
};
#endif
