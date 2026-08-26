"""옛 도구. 이제 아무도 안 쓰는데 지우지 않고 두었다."""

import os, sys, json, re  # noqa

def go(a,b,c=None,d=None,*args,**kw):
    x=[]
    for i in range(len(a)):
        if a[i]!=None:
            if b:
                x.append(str(a[i])+str(b))
            else:
                x.append(str(a[i]))
    return x
