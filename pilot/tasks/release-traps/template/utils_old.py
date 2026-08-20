# 예전에 쓰던 잡동사니. 지금은 아무 데서도 임포트하지 않는다.

import json, csv, os, sys        # noqa

def readjson(p):
    f=open(p)
    d=json.load(f)
    f.close()
    return d

def writecsv(p,rows):
    f=open(p,'w')
    for r in rows:
        f.write(','.join([str(x) for x in r])+'\n')
    f.close()

def pct(a,b):
    if b==0: return 0
    return a/b*100
