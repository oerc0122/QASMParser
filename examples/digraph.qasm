REQASM 1.0;

qreg a[8];

for i in [1:30]
{
    for A in [0:3]
          {
              for B in [0:3]
                    {
                        CX a[A], a[B];
                        CX a[A+4], a[B+4];
                    }
          }
}


CX a[3], a[4];
