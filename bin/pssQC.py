#
#  ppssQC.py
###########################################################################
#
#  Purpose:
#
#	This script will generate a set of QC reports for a problem
#	sequence setload file. 
#
#  Usage:
#
#      pssQC.py  filename
#
#      where:
#          filename = path to the input file
#
#  Env Vars:
#
#      The following environment variables are set by the configuration
#      files that are sourced by the wrapper script:
#
#          INVALID_SEQUENCE_RPT
#          SEC_SEQUENCE_RPT
#
#      The following environment variable is set by the wrapper script:
#
#          LIVE_RUN
#
#  Inputs:
# 	See: mcvQC.sh	
#
#  Outputs:
#
#      - QC report (${INVALID_SEQUENCE_RPT})
#
#      - QC report (${SEC_SEQUENCE_RPT})
#
#  Exit Codes:
#
#      0:  Successful completion
#      1:  An exception occurred
#      2:  Non-fatal discrepancy errors detected in the input files
#      3:  Fatal discrepancy errors detected in the input files
#
#  Assumes:
#
#  Implementation:
#
#      This script will perform following steps:
#
#      1) Validate the arguments to the script.
#      2) Perform initialization steps.
#      3) Open the input/output files.
#      4) Generate the QC reports.
#
#  Notes:  None
#
###########################################################################

import sys
import os
import string
import re
import mgi_utils
import db

#
#  CONSTANTS
#
TAB = '\t'
CRT = '\n'

USAGE = 'Usage: pssQC.py  inputFile'

liveRun = os.environ['LIVE_RUN']

tempTable = os.environ['TEMP_TABLE']

# temp table bcp file name
bcpFile = os.environ['INPUT_FILE_BCP']

# Report file names
invSeqRptFile = os.environ['INVALID_SEQUENCE_RPT']
secSeqRptFile = os.environ['SEC_SEQUENCE_RPT']

BCP_COMMAND = os.environ['PG_DBUTILS'] + '/bin/bcpin.csh'

timestamp = mgi_utils.date()

# current number of fatal errors
fatalCount = 0

# current number of nonfatal errors
nonfatalCount = 0

#
# Purpose: Validate the arguments to the script.
# Returns: Nothing
# Assumes: Nothing
# Effects: sets global variable
# Throws: Nothing
#
def checkArgs ():
    global inputFile

    if len(sys.argv) != 2:
        print(USAGE)
        sys.exit(1)

    inputFile = sys.argv[1]


#
# Purpose: Perform initialization steps.
# Returns: Nothing
# Assumes: Nothing
# Effects: Sets global variables.
# Throws: Nothing
#
def init ():

    print('DB Server:' + db.get_sqlServer())
    print('DB Name:  ' + db.get_sqlDatabase())
    sys.stdout.flush()

    db.useOneConnection(1)

    openFiles()
    loadTempTable()

    # query for invalid seqIds
#
# Purpose: Open the files.
# Returns: Nothing
# Assumes: Nothing
# Effects: Sets global variables.
# Throws: Nothing
#
def openFiles ():
    global fpInput, fpBCP
    global fpInvSeqRpt, fpSecSeqRpt

    #
    # Open the input file.
    #
    try:
        fpInput = open(inputFile, 'r')
    except:
        print('Cannot open input file: ' + inputFile)
        sys.exit(1)

    #
    # Open the output file.
    #
    try:
        fpBCP = open(bcpFile, 'w')
    except:
        print('Cannot open output file: ' + bcpFile)
        sys.exit(1)

    #
    # Open the report files.
    #
    try:
        fpInvSeqRpt = open(invSeqRptFile, 'a')
    except:
        print('Cannot open report file: ' + invSeqRptFile)
        sys.exit(1)
    try:
        fpSecSeqRpt = open(secSeqRptFile, 'a')
    except:
        print('Cannot open report file: ' + secMrkRptFile)
        sys.exit(1)


#
# Purpose: Close the files.
# Returns: Nothing
# Assumes: Nothing
# Effects: Nothing
# Throws: Nothing
#
def closeFiles ():
    fpInput.close()
    fpInvSeqRpt.close()
    fpSecSeqRpt.close()


#
# Purpose: Load the data from the input file into the temp table.
# Returns: Nothing
# Assumes: Nothing
# Effects: Nothing
# Throws: Nothing
#
def loadTempTable ():

    print('Create a bcp file from the input file')
    sys.stdout.flush()

    #
    # Read each record from the input file, perform validation checks and
    # write them to a bcp file.
    #
    line  = fpInput.readline()
    while line:
    #for line in fpInput.readlines():
        seqID  = str.strip(line)

        # write out to the bcp file:
        fpBCP.write('%s%s' % (seqID, CRT))
        line  = fpInput.readline()


    #
    # Close the bcp file.
    #
    fpBCP.close()

    #
    # Load the input data into the temp table.
    #
    print('Load the input data into the temp table: ' + tempTable)
    sys.stdout.flush()

    bcpCmd = '%s %s %s %s "/" %s "\\t" "\\n" mgd' % \
        (BCP_COMMAND, db.get_sqlServer(), db.get_sqlDatabase(),tempTable,
        bcpFile)
    rc = os.system(bcpCmd)
    if rc != 0:
        closeFiles()
        sys.exit(1)



#
# Purpose: Create the secondary sequence report.
# Returns: Nothing
# Assumes: Nothing
# Effects: Nothing
# Throws: Nothing
#
def createSecSeqReport ():
    global nonfatalCount
    print('Create the secondary sequence report')
    sys.stdout.flush()
    fpSecSeqRpt.write(str.center('Secondary Sequence Report',80) + CRT)
    fpSecSeqRpt.write(str.center('(' + timestamp + ')',80) + 2*CRT)
    fpSecSeqRpt.write('%-20s %s' % ('Sequence ID', CRT))
    fpSecSeqRpt.write(20*'-' + CRT)

    cmds = []

    #
    # Find any sequences from the input data that are secondary IDs
    #
    cmds.append('''
        select tmp.seqID
        from %s tmp, 
                     ACC_Accession a1
        where tmp.seqID is not null and 
                      lower(tmp.seqID) = lower(a1.accID) and 
                      a1._MGIType_key = 19 and 
                      a1._LogicalDB_key in (9, 27) and 
                      a1.preferred = 0 
        order by lower(tmp.seqID)
        ''' % (tempTable))

    results = db.sql(cmds,'auto')

    #
    # Write the records to the report.
    #
    for r in results[0]:
        seqID = r['seqID']

        fpSecSeqRpt.write('%-20s %s' %
            (seqID, CRT))

    numErrors = len(results[0])
    fpSecSeqRpt.write(CRT + 'Number of Rows: ' + str(numErrors) + CRT)
    nonfatalCount += numErrors


#
# Purpose: Create the invalid seqID report.
# Returns: Nothing
# Assumes: Nothing
# Effects: Nothing
# Throws: Nothing
#
def createInvSeqIdReport ():
    global fatalCount

    print('Create the invalid Sequence ID report')
    sys.stdout.flush()
    fpInvSeqRpt.write(str.center('Invalid Sequence ID Report',80) + CRT)
    fpInvSeqRpt.write(str.center('(' + timestamp + ')',80) + 2*CRT)
    fpInvSeqRpt.write('%-20s%s' % ('Sequence ID',CRT))
    fpInvSeqRpt.write(20*'-' + CRT)
    cmds = []

    #
    # Find any seq IDs from the input data that are not in the database.
    #
    cmds.append('''
        select tmp.seqID
        from %s tmp 
        where tmp.seqID is not null and 
                      not exists (select 1 
                                  from ACC_Accession a 
                                  where lower(a.accID) = lower(tmp.seqID) and 
                                        a._MGIType_key = 19 and 
                                        a._LogicalDB_key in (9,27)) 
        order by lower(tmp.seqID)
        ''' % (tempTable))

    results = db.sql(cmds,'auto')

    #
    # Write a record to the report for each sequence ID that is not in the
    # database..
    #
    for r in results[0]:
        seqID = r['seqID']
        fpInvSeqRpt.write('%-20s%s' % (seqID, CRT))

    numErrors = len(results[0])
    fpInvSeqRpt.write(CRT + 'Number of Rows: ' + str(numErrors) + CRT)
    fatalCount += numErrors

def createSetFile():
    print('creating set file')
    fpIn = open(os.getenv('INPUT_FILE_DEFAULT'), 'r')
    fpOut = open(os.getenv('INPUT_FILE_SET'), 'w')

    for line in fpIn:
        seqID = str.strip(line)
        fpOut.write('%s%s%s%s' % (seqID, TAB, seqID, CRT))
    fpIn.close()
    fpOut.close()

#	
# Main
#
checkArgs()
init()

createSecSeqReport()
createInvSeqIdReport()

closeFiles()

if liveRun == "1":
    createSetFile()

db.useOneConnection(0)
# START HERE - report whether fatal or non-fatal to command line.
if fatalCount > 0: # fatal errors
    sys.exit(3)
elif nonfatalCount > 0:
    sys.exit(2)
else:
    sys.exit(0)
