#!/usr/bin/python3

#
# This python script performs simple tests against all known DFS locations in
# the AWS openfiles qualification network
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


import subprocess
import sys
import argparse
import os

#
# Tuples of the form:
# ("comment", "remote directory", "scenario")
#
tests = [
    ("DFS Domain", "//DOUBLEDOUBLEU/Spirit/air", "any"),
    ("DFS Domain Alternate", "//DOUBLEDOUBLEU.COM/Spirit/air", "any"),
    ("DFS Domain (LC)", "//doubledoubleu/Spirit/air", "any"),
    ("DFS Domain Alternate (LC)", "//doubledoubleu.com/Spirit/air", "any"),
    ("DFS DC", "//SPIRITDC/Spirit/air", "any"),
    ("DFS DC Alternate", "//SPIRITDC.DOUBLEDOUBLEU.COM/Spirit/air", "any"),
    ("DFS DC (LC)", "//spiritdc/Spirit/air", "any"),
    ("DFS DC Alternate (LC)", "//spiritdc.doubledoubleu.com/Spirit/air", "any"),
    ("SMB Domain", "//DOUBLEDOUBLEU/air", "any"),
    ("SMB Domain Alternate", "//DOUBLEDOUBLEU.COM/air", "any"),
    ("SMB Domain (LC)", "//doubledoubleu/air", "any"),
    ("SMB Domin Alternate (LC)", "//doubledoubleu.com/air", "any"),
    ("SMB DC", "//SPIRITDC/air", "any"),
    ("SMB DC Alternate", "//SPIRITDC.DOUBLEDOUBLEU.COM/air", "any"),
    ("SMB DC (LC)", "//spiritdc/air", "any"),
    ("SMB DC Alternate (LC)", "//spiritdc.doubledoubleu.com/air", "any"),
    ("Non Replicated Domain Cross DCB", "//DOUBLEDOUBLEU/Root/water", "spiritdcb"),
    ("Non Replicated Domain Cross DCA", "//DOUBLEDOUBLEU/Root/wine", "spiritdc"),
    ("Non Replicated DC Cross DCB", "//spiritdc/Root/water", "both"),
    ("Non Replicated DC DCB", "//spiritdcb/Root/water", "spiritdcb"),
    ("Non Replicated DC Cross DCA", "//spiritdc/Root/wine", "spiritdc"),
    ("Non Replicated DC DC", "//spiritdcb/Root/wine", "both"),
    ("Non Replicated SMB DCA", "//spiritdc/wine", "spiritdc"),
    ("Non Replicated SMB DCB", "//spiritdcb/water", "spiritdcb"),
]

TEST_INPUT_FILENAME="test_input_file.txt"
TEST_INPUT_FILE=f"/tmp/{TEST_INPUT_FILENAME}"
TEST_OUTPUT_FILENAME="test_output_file.txt"
TEST_OUTPUT_FILE=f"/tmp/{TEST_OUTPUT_FILENAME}"

def run_command(command, fd):

    result = subprocess.run(command, shell=True,
                            capture_output=True, text=True)
    fd.write("command: \n")
    fd.write(f"{command}\n\n")
    fd.write("stdout: \n")
    fd.write(result.stdout)
    fd.write("\n")
    fd.write("stderr: \n")
    fd.write(result.stderr)
    fd.write("\n")
    fd.write(f"result: {result.returncode}\n\n")
    return result.returncode


def run_test(descr, dir, logfile):

    return_code = 1
    
    with open(logfile, "a") as fd:
        fd.write(f"Running {descr}\n\n")

        command = f"smbcp {TEST_INPUT_FILE} {dir}/{TEST_INPUT_FILENAME}"
        return_code = run_command(command, fd)
        if return_code != 0:
            print(f"Could not copy {TEST_INPUT_FILE} to {dir}")
            return return_code

        command = f"smbcp {dir}/{TEST_INPUT_FILENAME} {TEST_OUTPUT_FILE}"
        return_code = run_command(command, fd)
        if return_code != 0:
            print(f"Could not copy {TEST_OUTPUT_FILE} from {dir}")
            return return_code

        command = f"smbrm {dir}/{TEST_INPUT_FILENAME}"
        return_code = run_command(command, fd)
        if return_code != 0:
            print(f"Could not delete {TEST_INPUT_FILE} from {dir}")
            return return_code

        command = f"smbls {dir}"
        run_command(command, fd)

    return return_code


def run_regressions(online, logfile):

    return_code = 0

    #
    # Create test file
    #
    with open(TEST_INPUT_FILE, "w") as output_file:
        command = f"dd if=/dev/urandom bs=786438 count=1 | base64"
        result = subprocess.run(command, shell=True, stdout=output_file,
                                text=True)

    for descr, dir, config in tests:
        if online == "any" or config == online:
            print(f"Running {descr}")
            return_code = run_test(descr, dir, logfile)
        else:
            print(f"Skipping {descr}, not part of {online}")

    try:
        os.remove(TEST_INPUT_FILE)
    except FileNotFoundError:
        pass

    try:
        os.remove(TEST_OUTPUT_FILE)
    except FileNotFoundError:
        pass

    return return_code


if __name__ == "__main__":
    #
    # Parse arguments
    #
    #   --online any | both | spiritdc | spiritdcb
    #   --log <logfile>
    #
    # where:
    #    any implies that either spiritdc and spiritdcb are only
    #    both implies that both spiritdc and spiritdcb are online
    #    spiritdc implies that only spiritdc is online
    #    spiritdcb implies that only spiritdcb is online
    #
    parser = argparse.ArgumentParser(
        description="Openfiles DFS Regression Test"
    )

    allowed_online = ["any", "both", "spiritdc", "spiritdcb"]
    parser.add_argument("online", choices=allowed_online,
                        help="Choose a configuration")
    parser.add_argument("-l", "--log", default="of_regression.log",
                        help="Log filename")

    args = parser.parse_args()

    with open(args.log, "w") as fd:
        fd.write(f"Openfiles Regression Results with {args.online}\n")

    #
    # Show authentication
    #
    result = subprocess.run("klist", shell=True,
                            capture_output=True, text=True)

    print(f"{result.stdout}")
    if result.returncode != 0:
        print(f"{result.stderr}")
        print("Not currently logged into a domain")
        return_code = 1
    else:
        return_code = run_regressions(args.online, args.log)

    sys.exit(return_code)
