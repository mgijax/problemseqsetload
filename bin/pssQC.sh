#!/bin/sh 
#
#  pssQC.sh
###########################################################################
#
#  Purpose:
#
#      This script is a wrapper around the process that creates sanity/QC
#      reports for the problem alignment sequences file
#
#  Usage:
#
#      pssQC.sh  filename  [ "live" ]
#
#      where
#          filename = path to the input file
#          live = option to let the script know that this is a "live" run
#                 so the output files are created under the /data/loads
#                 directory instead of the current directory
#
#  Env Vars:
#
#      See the configuration file
#
#  Inputs:
#
#      - setlod input file with the following tab-delimited fields:
#
#	1. Sequence ID (object ID)
# 	2. Sequence ID (label)
#
#       There can be additional fields, but they are not used.
#
#  Outputs:
#
#      - Sanity report for the input file.
#
#      - Log file (${PSSLOADQC_LOGFILE})
#
#  Exit Codes:
#
#      0:  Successful completion
#      1:  Fatal error occurred
#
#  Assumes:  Nothing
#
#  Implementation:
#
#      This script will perform following steps:
#
#      1) Validate the arguments to the script.
#      2) Source the common configuration file to establish the environment.
#      3) Verify that the input files exist.
#      4) If this is not a "live" run, override the path to the output, log
#         and report files, so they reside in the current directory.
#      5) Initialize the log and report files.
#      6) Clean up the input files by removing blank lines, Ctrl-M, etc.
#      7) Generate the sanity report.
#      8) Create a temp table for the input data.
#      9) Call pssQC.py to generate the QC reports and the
#          setload file.
#      10) Drop the temp table.
#
#  Notes:  None
#
###########################################################################

CURRENTDIR=`pwd`
BINDIR=`dirname $0`

CONFIG=`cd ${BINDIR}/..; pwd`/problemseqsetload.config

USAGE='Usage: pssQC.sh  filename  [ "live" ]'

LIVE_RUN=0; export LIVE_RUN

#
# Make sure an input file was passed to the script. If the optional "live"
# argument is given, that means that the output files are located in the
# /data/loads/... directory, not in the current directory.
#
if [ $# -eq 1 ]
then
    INPUT_FILE=$1
elif [ $# -eq 2 -a "$2" = "live" ]
then
    INPUT_FILE=$1
    LIVE_RUN=1
else
    echo ${USAGE}; exit 1
fi
#
# Create a temporary file and make sure that it is removed when this script
# terminates.
#
echo 'creating temp file'
TMP_FILE=/tmp/`basename $0`.$$
touch ${TMP_FILE}
trap "rm -f ${TMP_FILE}" 0 1 2 15

#
# Make sure the configuration file exists and source it.
#
if [ -f ${CONFIG} ]
then
    . ${CONFIG}
else
    echo "Missing configuration file: ${CONFIG}"
    exit 1
fi

#
# If the QC check is being run by a curator, the mgd_dbo password needs to
# be in a password file in their HOME directory because they won't have
# permission to read the password file in the pgdbutilities product.
#
if [ "${USER}" != "mgiadmin" ]
then
    PGPASSFILE=$HOME/.pgpass
fi

#
# Make sure the input file exists (regular file or symbolic link).
#
if [ "`ls -L ${INPUT_FILE} 2>/dev/null`" = "" ]
then
    echo "Missing input file: ${INPUT_FILE}"
    exit 1
fi

#
# If this is not a "live" run, the output, log and report files should reside
# in the current directory, so override the default settings.
#
if [ ${LIVE_RUN} -eq 0 ]
then
    INPUT_FILE_QC=${CURRENTDIR}/`basename ${INPUT_FILE_QC}`
    INPUT_FILE_BCP=${CURRENTDIR}/`basename ${INPUT_FILE_BCP}`
    LOADQC_LOGFILE=${CURRENTDIR}/`basename ${LOADQC_LOGFILE}`
    SANITY_RPT=${CURRENTDIR}/`basename ${SANITY_RPT}`
    INVALID_SEQUENCE_RPT=${CURRENTDIR}/`basename ${INVALID_SEQUENCE_RPT}`
    SEC_SEQUENCE_RPT=${CURRENTDIR}/`basename ${SEC_SEQUENCE_RPT}`
fi

#
# Initialize the log file.
#
LOG=${LOADQC_LOGFILE}
rm -rf ${LOG}
touch ${LOG}

#
# Initialize the report files to make sure the current user can write to them.
#
RPT_LIST="${SANITY_RPT} ${INVALID_SEQUENCE_RPT} ${SEC_SEQUENCE_RPT}" 

for i in ${RPT_LIST}
do
    rm -f $i; >$i
done

#
# Convert the input file into a QC-ready version that can be used to run
# the sanity/QC reports against. This involves doing the following:
# 1) Extract column 1 
# 2) Remove any spaces
# 3) Extract only lines that have alphanumerics (excludes blank lines)
# 4) Remove any Ctrl-M characters (dos2unix)
#
cat ${INPUT_FILE} | tail -n +1 | cut -d'	' -f1 | sed 's/ //g' | grep '[0-9A-Za-z]' > ${INPUT_FILE_QC}
dos2unix ${INPUT_FILE_QC} ${INPUT_FILE_QC} 2>/dev/null

#
# FUNCTION: Check for lines with missing columns in an input file and write
#           the line numbers to the sanity report.
#
checkColumns ()
{
    FILE=$1         # The input file to check
    REPORT=$2       # The sanity report to write to
    NUM_COLUMNS=$3  # The number of columns expected in each input record
    ${PYTHON} ${PROBLEMSEQSETLOAD}/bin/checkColumns.py ${FILE} ${NUM_COLUMNS} >> ${REPORT}
}


#
# Run sanity checks on the input file.
#
echo "" >> ${LOG}
date >> ${LOG}
echo "Run sanity checks on the input file" >> ${LOG}
FILE_ERROR=0

checkColumns ${INPUT_FILE_QC} ${SANITY_RPT} ${FILE_COLUMNS}
if [ $? -ne 0 ]
then
    FILE_ERROR=1
fi

#
# If the input file had sanity error, remove the QC-ready input file and
# skip the QC reports.
#
if [ ${FILE_ERROR} -ne 0 ]
then
    echo "Sanity errors detected in input file" | tee -a ${LOG}
    rm -f ${INPUT_FILE_QC}
    exit 1
fi

#
# Append the current user ID to the name of the temp table that needs to be
# created. This allows multiple people to run the QC checks at the same time
# without sharing the same table.
#
TEMP_TABLE=${TEMP_TABLE}_${USER}

#
# Create a temp table for the input data.
#
echo "" >> ${LOG}
date >> ${LOG}
echo "Create a temp table for the input data" >> ${LOG}
cat - <<EOSQL | psql -h${PG_DBSERVER} -d${PG_DBNAME} -U${PG_DBUSER} -e  >> ${LOG}

create table ${TEMP_TABLE} (
    seqID text null
)
;

create  index idx_seqID on ${TEMP_TABLE} (lower(seqID)) ;

grant all on ${TEMP_TABLE} to public ;

EOSQL

#
# Generate the QC reports.
#
echo "" >> ${LOG}
date >> ${LOG}
echo "" | tee -a ${LOG}
echo "Generate the QC reports" | tee -a ${LOG}
echo "" | tee -a ${LOG}
{ ${PYTHON} ${LOAD_QC} ${INPUT_FILE_QC} 2>&1; echo $? > ${TMP_FILE}; } >> ${LOG}
if [ `cat ${TMP_FILE}` -eq 1 ]
then
    echo "A fatal error occurred while generating the QC reports"
    echo "See log file (${LOG})"
    RC=1
elif [ `cat ${TMP_FILE}` -eq 2 ]
then
    echo "Fatal errors Secondary Sequence ID(s) see ${SEC_SEQUENCE_RPT}" | tee -a ${LOG}
    RC=1
elif [ `cat ${TMP_FILE}` -eq 3 ]
then
    echo "Fatal errors Invalid Sequence ID(s) see ${INVALID_SEQUENCE_RPT}" | tee -a ${LOG}
    RC=1
else
    echo "QC reports successful, no errors" | tee -a ${LOG}
    RC=0
fi

#
# Drop the temp table.
#
echo "" >> ${LOG}
date >> ${LOG}
echo "Drop the temp table" >> ${LOG}
cat - <<EOSQL | psql -h${PG_DBSERVER} -d${PG_DBNAME} -U${PG_DBUSER} -e  >> ${LOG}

drop table ${TEMP_TABLE};

EOSQL

date >> ${LOG}

#
# Remove the QC-ready input file and the bcp file.
#
rm -f ${INPUT_FILE_QC}
rm -f ${INPUT_FILE_BCP}

exit ${RC}
