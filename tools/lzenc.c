#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "LzmaEnc.h"
#include "Alloc.h"
/* usage: lzenc in out ; raw LZMA stream, no end mark, lc3 lp0 pb2 dict 2^23 fb 273 (pylzma defaults used by kid23) */
int main(int c,char**v){FILE*f=fopen(v[1],"rb");fseek(f,0,2);long n=ftell(f);fseek(f,0,0);
 unsigned char*in=malloc(n);fread(in,1,n,f);fclose(f);
 SizeT dl=n+n/2+1024;unsigned char*out=malloc(dl);
 CLzmaEncProps p;LzmaEncProps_Init(&p);p.level=5;p.dictSize=1<<14;p.lc=3;p.lp=0;p.pb=2;p.fb=273;p.numThreads=1;p.algo=1;
 unsigned char pr[5];SizeT ps=5;
 int r=LzmaEncode(out,&dl,in,n,&p,pr,&ps,0,NULL,&g_Alloc,&g_Alloc);
 if(r){fprintf(stderr,"err %d\n",r);return 1;}
 f=fopen(v[2],"wb");fwrite(out,1,dl,f);fclose(f);return 0;}
