#!/bin/bash

#
# This shell script performs simple tests against all known DFS locations in the
# AWS openfiles qualification network
#
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
)

TEST_INPUT_FILENAME="test_input_file.txt"
TEST_INPUT_FILE="/tmp/$TEST_INPUT_FILENAME"
TEST_OUTPUT_FILENAME="test_output_file.txt"
TEST_OUTPUT_FILE="/tmp/$TEST_OUTPUT_FILENAME"
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
    smbls $dir
done    
rm $TEST_INPUT_FILE $TEST_OUTPUT_FILE
echo "Success"
