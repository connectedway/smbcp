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

import pytest

#
# Each test has a configuration.  From a test execution perspective
# we will run tests with both spiritdc and spiritdcb opertional
# just spiritdc, or just spiritdcb.  This is communicated to this test
# module using the --online keyword:  i.e --online=both|spiritdc|spiritdcb
#
# Tests on the otherhand have requirements.  They may require either
# server be running, both servers be running, or a specific server be running.
# This is specified with the config column of the tests table.  Valid
# values are "any", "both", "spiritdc", or "spiritdcb".
#
# When running, the following scenarios are possible:
#   online is both, any, both, spiritdc and spiritdcb all work.
#   online is spiritdc, then any, and spiritdc work
#   online is spiritdcb, then any and spiritdcb work
#

#
# Tuples of the form:
# ("comment", "remote directory", "scenario")
#
tests = [
    ("DFS Domain", "//DOUBLEDOUBLEU/Spirit/air", "any"),
    ("DFS Domain Alternate", "//DOUBLEDOUBLEU.COM/Spirit/air", "any"),
    ("DFS Domain (LC)", "//doubledoubleu/Spirit/air", "any"),
    ("DFS Domain Alternate (LC)", "//doubledoubleu.com/Spirit/air", "any"),
    ("DFS DC", "//SPIRITDC/Spirit/air", "spiritdc"),
    ("DFS DC Alternate", "//SPIRITDC.DOUBLEDOUBLEU.COM/Spirit/air", "spiritdc"),
    ("DFS DCB", "//SPIRITDCB/Spirit/air", "spiritdcb"),
    ("DFS DCB Alternate", "//SPIRITDCB.DOUBLEDOUBLEU.COM/Spirit/air", "spiritdcb"),
    ("DFS DC (LC)", "//spiritdc/Spirit/air", "spiritdc"),
    ("DFS DC Alternate (LC)", "//spiritdc.doubledoubleu.com/Spirit/air", "spiritdc"),
    ("DFS DCB (LC)", "//spiritdcb/Spirit/air", "spiritdcb"),
    ("DFS DCB Alternate (LC)", "//spiritdcb.doubledoubleu.com/Spirit/air", "spiritdcb"),
    ("SMB Domain", "//DOUBLEDOUBLEU/air", "any"),
    ("SMB Domain Alternate", "//DOUBLEDOUBLEU.COM/air", "any"),
    ("SMB Domain (LC)", "//doubledoubleu/air", "any"),
    ("SMB Domin Alternate (LC)", "//doubledoubleu.com/air", "any"),
    ("SMB DC", "//SPIRITDC/air", "spiritdc"),
    ("SMB DC Alternate", "//SPIRITDC.DOUBLEDOUBLEU.COM/air", "spiritdc"),
    ("SMB DCB", "//SPIRITDCB/air", "spiritdcb"),
    ("SMB DCB Alternate", "//SPIRITDCB.DOUBLEDOUBLEU.COM/air", "spiritdcb"),
    ("SMB DC (LC)", "//spiritdc/air", "spiritdc"),
    ("SMB DC Alternate (LC)", "//spiritdc.doubledoubleu.com/air", "spiritdc"),
    ("SMB DCB (LC)", "//spiritdcb/air", "spiritdcb"),
    ("SMB DCB Alternate (LC)", "//spiritdcb.doubledoubleu.com/air", "spiritdcb"),
    ("Non Replicated Domain Cross DCB", "//DOUBLEDOUBLEU/Root/water", "spiritdcb"),
    ("Non Replicated Domain Cross DCA", "//DOUBLEDOUBLEU/Root/wine", "spiritdc"),
    ("Non Replicated DC Cross DCB", "//spiritdc/Root/water", "both"),
    ("Non Replicated DC DCB", "//spiritdcb/Root/water", "spiritdcb"),
    ("Non Replicated DC Cross DCA", "//spiritdc/Root/wine", "spiritdc"),
    ("Non Replicated DC DC", "//spiritdcb/Root/wine", "both"),
    ("Non Replicated SMB DCA", "//spiritdc/wine", "spiritdc"),
    ("Non Replicated SMB DCB", "//spiritdcb/water", "spiritdcb"),
]

TEST_INPUT_FILENAME = "test_input_file.txt"
TEST_INPUT_FILE = f"/tmp/{TEST_INPUT_FILENAME}"
TEST_OUTPUT_FILENAME = "test_output_file.txt"
TEST_OUTPUT_FILE = f"/tmp/{TEST_OUTPUT_FILENAME}"
DFS_CACHE_FILE = "/tmp/dfs_cache.xml"


def run_command(command, fd):
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    fd.write("command: \n")
    fd.write(f"{command}\n\n")
    fd.write("stdout: \n")
    fd.write(result.stdout)
    fd.write("\n")
    fd.write("stderr: \n")
    fd.write(result.stderr)
    fd.write("\n")
    fd.write(f"result: {result.returncode}\n\n")
    fd.flush()
    return result.returncode


SPIRITDC = "172.31.17.154"
SPIRITDCB = "172.31.30.112"
BOTH = "0.0.0.0"

@pytest.fixture(params=[BOTH, SPIRITDC, SPIRITDCB])
def setup_teardown(request, logfile):

    with open(logfile, "a") as fd:
        fd.write ("Begin test\n")
        fd.flush()

    awsdfs_ufw_path = os.path.dirname(os.path.abspath(__file__)) + "/awsdfs_ufw.py"

    awsdfs_ufw = subprocess.Popen(
        ["python3", awsdfs_ufw_path],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )

    awsdfs_ufw.stdin.write("reset\n")
    awsdfs_ufw.stdin.flush()

    ip = request.param
    if ip == SPIRITDC or ip == SPIRITDCB:
        #
        # Start up the firewall
        #
        if ip == SPIRITDC:
            deny = "spiritdcb"
        else:
            deny = "spiritdc"

        awsdfs_ufw.stdin.write(f"deny {deny}\n")
        awsdfs_ufw.stdin.flush()

        flush_stdout(awsdfs_ufw.stdout, fd)

    yield

    if ip != BOTH:
        #
        # teardown firewall
        #
        awsdfs_ufw.stdin.write(f"reset\n")
        awsdfs_ufw.stdin.flush()

    awsdfs_ufw.stdin.write(f"quit\n")
    awsdfs_ufw.stdin.flush()

    awsdfs_ufw.wait()

    with open(logfile, "a") as fd:
        for line in awsdfs_ufw.stdout:
            fd.write(line)


def test_authenticated(logfile):
    #
    # Show authentication
    #
    result = subprocess.run("klist", shell=True, capture_output=True, text=True)
    with open(logfile, "w") as fd:
        fd.write("Authentication:\n")
        fd.write("stdout:\n")
        fd.write(result.stdout)
        fd.write("\n")
        fd.write("stderr:\n")
        fd.write(result.stderr)
        fd.flush()

    assert result.returncode == 0, "Not currently logged into a domain"


@pytest.mark.usefixtures("setup_teardown")
@pytest.mark.parametrize("descr, dir, config", tests)
def test_transaction(descr, dir, config, online, logfile):
    return_code = 1
    #
    # When running, the following scenarios are possible:
    #   online is both, any, both, spiritdc and spiritdcb all work.
    #   online is spiritdc, then any, and spiritdc work
    #   online is spiritdcb, then any and spiritdcb work
    #
    if online == "both":
        pass
    elif online == "spiritdc" and (config == "any" or config == "spiritdc"):
        pass
    elif online == "spiritdcb" and (config == "any" or config == "spiritdcb"):
        pass
    else:
        pytest.skip("Test not part of config")

    with open(logfile, "a") as fd:
        fd.write(f"Running {descr}\n\n")
        fd.flush()

        command = f"smbcp {TEST_INPUT_FILE} {dir}/{TEST_INPUT_FILENAME}"
        return_code = run_command(command, fd)
        assert return_code == 0, f"Could not copy {TEST_INPUT_FILE} to {dir}"

        command = f"smbcp {dir}/{TEST_INPUT_FILENAME} {TEST_OUTPUT_FILE}"
        return_code = run_command(command, fd)
        assert return_code == 0, f"Could not copy {TEST_INPUT_FILENAME} from {dir}"

        command = f"smbrm {dir}/{TEST_INPUT_FILENAME}"
        return_code = run_command(command, fd)
        assert return_code == 0, f"Could not delete {TEST_INPUT_FILENAME} from {dir}"

        command = f"smbls {dir}"
        run_command(command, fd)

        fd.write(f"*** {descr} Should Have Succeeded *** \n")


@pytest.fixture(scope="module", autouse=True)
def setup_module():
    #
    # Create test file
    #
    with open(TEST_INPUT_FILE, "w") as output_file:
        command = f"dd if=/dev/urandom bs=786438 count=1 | base64"
        result = subprocess.run(command, shell=True, stdout=output_file, text=True)

    try:
        os.remove(DFS_CACHE_FILE)
    except FileNotFoundError:
        pass

    yield

    try:
        os.remove(TEST_INPUT_FILE)
    except FileNotFoundError:
        pass

    try:
        os.remove(TEST_OUTPUT_FILE)
    except FileNotFoundError:
        pass
