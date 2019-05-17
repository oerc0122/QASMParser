// Includes for using REQASM features in C codes

typedef struct bitstr
{
  char *str;
  int *val;
  int  nBits;
} bitstr;

bitstr toBitstr(int *bits, int nBits);
_Bool orOf(int *bits, int nBits);
_Bool xorOf(int *bits, int nBits);
_Bool andOf(int *bits, int nBits);

_Bool orOfBits (bitstr bits);
_Bool xorOfBits(bitstr bits);
_Bool andOfBits(bitstr bits);

int fllog(int c, int a);
int powrem(int a, int c);
