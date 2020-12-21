import string
import os

TAB = '\t'
CRT = '\n'

fpIn = open(os.getenv('INPUT_FILE_DEFAULT'), 'r')
fpOut = open(os.getenv('INPUT_FILE_SET'), 'w')

for line in fpIn:
    seqID = str.strip(line)
    if seqID == '':
        continue
    fpOut.write('%s%s%s%s' % (seqID, TAB, seqID, CRT))
fpIn.close()
fpOut.close()
