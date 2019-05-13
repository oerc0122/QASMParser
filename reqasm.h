// Includes for using REQASM features in C codes

typedef struct bitstr
{
  char *str;
  int *val;
  int  nBits;
} bitstr;

bitstr toBitstr(int *bits, int nBits);
_Bool orOf (bitstr bits);
_Bool xorOf(bitstr bits);
_Bool andOf(bitstr bits);

int fllog(int c, int a);
int powrem(int a, int c);
