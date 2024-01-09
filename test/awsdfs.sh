#!/bin/bash

#
# This shell script performs simple tests against all known DFS locations in the
# AWS openfiles qualification network
#
# Domain: DOUBLEDOUBLEU.COM
#  DCs: spiritdc.doubledoubleu.com
#       spiritdcb.doubledoubleu.com
#
#  Shares:
#       \\spiritdc.doubledoubleu.com\air : C:\Shares\air
#       \\spiritdc.doubledoubleu.com\earth : C:\Shares\earth
#       \\spiritdc.doubledoubleu.com\Shared : C:\Shares\Shared
#       \\spiritdc.doubledoubleu.com\Spirit : C:\DFSRoots\Spirit
#
#       \\spiritdc.doubledoubleu.com\Root : c:\DFSRoots\Root
#
#       \\spiritdc.doubledoubleu.com\wine : C:\Shares\wine
#
#       \\spiritdcb.doubledoubleu.com\air : C:\Shares\air
#       \\spiritdcb.doubledoubleu.com\earth : C:\Shares\earth
#       \\spiritdcb.doubledoubleu.com\Shared : C:\Shares\Shared
#       \\spiritdcb.doubledoubleu.com\Spirit : C:\DFSRoots\Spirit
#
#       \\spiritdcb.doubledoubleu.com\Root : c:\DFSRoots\Root
#
#       \\spiritdcb.doubledoubleu.com\water : c:\Shares\water
#
#  DFS Roots:
#       \\spiritdc.doubledoubleu.com\Spirit
#       \\spiritdcb.doubledoubleu.com\Spirit
#
#       \\spiritdc.doubledoubleu.com\Root
#       \\spiritdcb.doubledoubleu.com\Root

#  DFS Links:
#       \\spiritdc.doubledoubleu.com\Spirit\air -> \\spiritdc.doubledoubleu.com\air
#       \\spiritdc.doubledoubleu.com\Spirit\earth -> \\spiritdc.doubledoubleu.com\earth
#       \\spiritdcb.doubledoubleu.com\Spirit\air -> \\spiritdcb.doubledoubleu.com\air
#       \\spiritdcb.doubledoubleu.com\Spirit\earth -> \\spiritdcb.doubledoubleu.com\earth
#
#       \\spiritdc.doubledoubleu.com\Root\wine -> \\spiritdcb.doubledoubleu.com\water
#       \\spiritdcb.doubledoubleu.com\Root\water -> \\spiritdc.doubledoubleu.com\wine
#
#
#  Replicated Storage:
#       \\spiritdc.doubledoubleu.com\Spirit
#       \\spiritdcb.doubledoubleu.com\Spirit

declare -a dirs=(
    # DFS Domain
    "//DOUBLEDOUBLEU/Spirit/air"
    # DFS Domain Alternate
    "//DOUBLEDOUBLEU.COM/Spirit/air"
    # DFS Domain (LC)
    "//doubledoubleu/Spirit/air"
    # DFS Domain Alternate (LC)
    "//doubledoubleu.com/Spirit/air"
    # DFS DC
    "//SPIRITDC/Spirit/air"
    # DFS DC Alternate
    "//SPIRITDC.DOUBLEDOUBLEU.COM/Spirit/air"
    # DFS DC (LC)
    "//spiritdc/Spirit/air"
    # DFS DC Alternate (LC)
    "//spiritdc.doubledoubleu.com/Spirit/air"
    # SMB Domain
    "//DOUBLEDOUBLEU/air"
    # SMB Domain Alternate
    "//DOUBLEDOUBLEU.COM/air"
    # SMB Domain (LC)
    "//doubledoubleu/air"
    # SMB Domin Alternate (LC)
    "//doubledoubleu.com/air"
    # SMB DC
    "//SPIRITDC/air"
    # SMB DC Alternate
    "//SPIRITDC.DOUBLEDOUBLEU.COM/air"
    # SMB DC (LC)
    "//spiritdc/air"
    # SMB DC Alternate (LC)
    "//spiritdc.doubledoubleu.com/air"
    # Non Replicated Domain Cross Server
    "//DOUBLEDOUBLEU/Root/water"
    "//DOUBLEDOUBLEU/Root/wine"
    # Non Replicated DC Cross Server
    "//spiritdc/Root/water"
    "//spiritdcb/Root/water"
    "//spiritdc/Root/wine"
    "//spiritdcb/Root/wine"
    # Non Replicated SMB Cros Server
    # Note, //spiritdc/water and //spiritdcb/wine would fail
    "//spiritdc/wine"
    "//spiritdcb/water"
)

TEST_INPUT_FILENAME="test_input_file.txt"
TEST_INPUT_FILE="/tmp/$TEST_INPUT_FILENAME"
TEST_OUTPUT_FILENAME="test_output_file.txt"
TEST_OUTPUT_FILE="/tmp/$TEST_OUTPUT_FILENAME"
SLEEP=0
#
# Show authentication
#
klist
#
# Create test file
#
dd if=/dev/urandom bs=786438 count=1 | base64 > $TEST_INPUT_FILE
#
# Loop through list of shares to test access to
#
for dir in "${dirs[@]}";
do
    smbcp $TEST_INPUT_FILE $dir/$TEST_INPUT_FILENAME
    if [ $? -ne 0 ];
    then
	echo "Could not copy $TEST_INPUT_FILE to $dir"
	exit 1
    fi
       
    sleep $SLEEP

    smbcp $dir/$TEST_INPUT_FILENAME $TEST_OUTPUT_FILE
    if [ $? -ne 0 ];
    then
	echo "Could not copy $TEST_OUTPUT_FILE from $dir"
	exit 1
    fi

    smbrm $dir/$TEST_INPUT_FILENAME
    if [ $? -ne 0 ];
    then
	echo "Could not delete $TEST_INPUT_FILE from $dir"
	exit 1
    fi

    sleep $SLEEP

    smbls $dir
done    
rm $TEST_INPUT_FILE $TEST_OUTPUT_FILE
echo "Success"
