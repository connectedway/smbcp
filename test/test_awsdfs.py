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
import time
import fcntl

import pytest

#
# Each test has a configuration.  From a test execution perspective
# we will run tests with both spiritdc and spiritdcb opertional
# just spiritdc, or just spiritdcb.
#
# Tests on the otherhand have requirements.  They may require either
# server be running, both servers be running, or a specific server be running.
# This is specified with the config column of the tests table.  Valid
# values are "any", "both", "spiritdc", or "spiritdcb".
#
# The test is parametrized and each test is run with three seperate
# firewall configurations perfomed inside of the setup_teardown logic.
# The setup_teardown will communicate to the test which firewall
# configuration is in place so the test can skip those tests not
# appropriate for a particular firewall configuration
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

#
# Test file size.  Keep transfers small on AWS.  We pay for it
#
# TEST_FILE_SIZE = "786438"
TEST_FILE_SIZE = "1024"

def run_command(command, fd):
    """
    Run a shell command and trace to log file

    Args:
        command (str): The shell command to run
        fd (io.TextIOWrapper): The file descriptor of the log file

    Returns:
        int: The return code

    Raises:
        Nothing
    """

    #
    # Run the shell command
    #
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    #
    # Trace the command
    #
    fd.write("command: \n")
    fd.write(f"{command}\n\n")
    #
    # Trace stdout
    #
    fd.write("stdout: \n")
    fd.write(result.stdout)
    fd.write("\n")
    #
    # Trace stderr
    #
    fd.write("stderr: \n")
    fd.write(result.stderr)
    fd.write("\n")
    #
    # Trace the result code
    #
    fd.write(f"result: {result.returncode}\n\n")
    fd.flush()
    #
    # Return the result
    #
    return result.returncode


#
# Names of firewall configurations
#
DENY_NONE = "none"
DENY_SPIRITDC = "spiritdc"
DENY_SPIRITDCB = "spiritdcb"


@pytest.fixture(params=[DENY_NONE, DENY_SPIRITDC, DENY_SPIRITDCB])
def setup_teardown(request, logfile):
    """
    pytest setup/teardown logic for transaction test

    Args:
        request (obj): The pytest request object
        logfile (str): The name of the logfile

    Returns:
        Nothing

    Raiess:
        Nothing
    """

    #
    # Find the path of the firewall Utility
    #
    awsdfs_ufw_path = os.path.dirname(os.path.abspath(__file__)) + "/awsdfs_ufw.py"

    #
    # Spawn off the firewall utility
    #
    awsdfs_ufw = subprocess.Popen(
        ["python3", awsdfs_ufw_path],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    #
    # Set stdout as non blocking so we can read output asynchronously
    #
    fcntl.fcntl(awsdfs_ufw.stdout.fileno(), fcntl.F_SETFL, os.O_NONBLOCK)
    #
    # Open our Logfile
    #
    with open(logfile, "a") as fd:
        fd.write(f"\nRemoving dfs_cache\n")
        #
        # Remove the dfs cache
        # Technically not necessary but we want the starting cache
        # state for each iteration to be the same
        #
        try:
            os.remove(DFS_CACHE_FILE)
        except FileNotFoundError:
            pass

        fd.write(f"\n\nSetup Firewall for Denying {request.param}\n\n")
        #
        # Reset the firewall.  This will enable the firewall and
        # allow input from and output to all hosts
        #
        awsdfs_ufw.stdin.write("reset\n")
        awsdfs_ufw.stdin.flush()
        #
        # Check if we want to set up deny rules
        #
        if request.param != DENY_NONE:
            #
            # Deny traffic to the specified host
            #
            awsdfs_ufw.stdin.write(f"deny {request.param}\n")
            awsdfs_ufw.stdin.flush()
            #
            # And get the firewall status for our log
            #
            awsdfs_ufw.stdin.write(f"status\n")
            awsdfs_ufw.stdin.flush()

        #
        # Scrape output from the firewall and log.
        # It may be that the firewall hasn't completed the command
        # We had a delay here so we could capture the output but
        # opted to run without the delay.  This may result in the
        # status of the firewall configuration after setting the
        # deny rule may not appear in the log file until later in
        # test output
        #
        for line in awsdfs_ufw.stdout:
            fd.write(line)
        fd.flush()
    #
    # Run the test transaction
    #
    yield request.param
    #
    # Reopen the log file
    #
    with open(logfile, "a") as fd:
        fd.write(f"\n\nTeardown Firewall for Denying {request.param}\n\n")

        if request.param != DENY_NONE:
            #
            # Reset the firewall
            #
            awsdfs_ufw.stdin.write(f"reset\n")
            awsdfs_ufw.stdin.flush()
            #
            # Capture firewall status after the reset
            #
            awsdfs_ufw.stdin.write(f"status\n")
            awsdfs_ufw.stdin.flush()
        #
        # Quite the firewall app
        #
        awsdfs_ufw.stdin.write(f"quit\n")
        awsdfs_ufw.stdin.flush()
        #
        # Wait for the firewall app to complete
        #
        awsdfs_ufw.wait()
        #
        # Now flush the output of the firewall app to our logfile
        #
        for line in awsdfs_ufw.stdout:
            fd.write(line)


def test_authenticated(logfile):
    """
    Test that the user has authenticated with Kerberos

    Args:
        logfile (str): A string obtained from the logfile fixture.
    """
    #
    # Show authentication
    #
    result = subprocess.run("klist", shell=True, capture_output=True, text=True)
    #
    # Trace the output of klist
    #
    with open(logfile, "w") as fd:
        fd.write("Authentication:\n")
        fd.write("stdout:\n")
        fd.write(result.stdout)
        fd.write("\n")
        fd.write("stderr:\n")
        fd.write(result.stderr)
        fd.flush()
    #
    # If klist returne a non 0 return code, then we are not logged in.
    #
    assert result.returncode == 0, "Not currently logged into a domain"


@pytest.mark.usefixtures("setup_teardown")
@pytest.mark.parametrize("descr, dir, config", tests)
def test_transaction(descr, dir, config, logfile, setup_teardown):
    """
    Test an SMB Transaction

    An SMB transaction is the copy of a file to a remote location,
    the copy of that file from the remote location to a local location,
    the deletion of the remote file, and a list of the remote directory.

    At the end of a successful test, we will output the overall elapsed
    time of the transaction, and the elapsed time for each step.

    Args:
        descr (str) : The test description
        dir (str) : The remote path to use
        config (str) : The config that this test is valid for
        logfile (str) : The output log file fixture
        setup_teardown (str) : The firewall configuration
    """

    return_code = 1
    #
    # Check the firewwall configuration against the iterations valid
    # configuration.  If the iteraation is not valid for a particular
    # firewall configuration, we will skip the iteration.
    #
    if setup_teardown == DENY_NONE:
        #
        # Firewwall not enying anyone.  We can run this itertion
        #
        pass
    elif setup_teardown == DENY_SPIRITDCB and (config == "any" or config == "spiritdc"):
        #
        # Firewall is denying spiritdcb.  We only want to run the
        # iteration if the iteration can run under any firewall config (any)
        # or the test only needs spiritdc.
        #
        pass
    elif setup_teardown == DENY_SPIRITDC and (config == "any" or config == "spiritdcb"):
        #
        # Firewall is denying spiritdc.  We only want to run the
        # iteration if the iteration can run under any firewall config (any)
        # or the test only needs spiritdcb.
        #
        pass
    else:
        #
        # An test not compatible with our current firewall configuration
        #
        pytest.skip("Test not part of config")

    #
    # Now Open our output log file
    #
    with open(logfile, "a") as fd:
        fd.write(f"Running {descr}\n\n")
        fd.flush()

        start = time.time()

        #
        # Perform the copy to step
        #
        start_copy_to = start
        command = f"smbcp {TEST_INPUT_FILE} {dir}/{TEST_INPUT_FILENAME}"
        return_code = run_command(command, fd)
        assert return_code == 0, f"Could not copy {TEST_INPUT_FILE} to {dir}"
        end_copy_to = time.time()

        #
        # Perform the copy from step
        #
        start_copy_from = end_copy_to
        command = f"smbcp {dir}/{TEST_INPUT_FILENAME} {TEST_OUTPUT_FILE}"
        return_code = run_command(command, fd)
        assert return_code == 0, f"Could not copy {TEST_INPUT_FILENAME} from {dir}"
        end_copy_from = time.time()

        #
        # Perform the rm step
        #
        start_rm = end_copy_from
        command = f"smbrm {dir}/{TEST_INPUT_FILENAME}"
        return_code = run_command(command, fd)
        assert return_code == 0, f"Could not delete {TEST_INPUT_FILENAME} from {dir}"
        end_rm = time.time()

        #
        # Perform the ls step
        #
        start_ls = end_rm
        command = f"smbls {dir}"
        run_command(command, fd)
        end_ls = time.time()
        #
        # End of transaction
        #
        end = end_ls
        #
        # Output timing info to the log
        #
        fd.write(f"Test {descr} Completed in {end - start:.2f} seconds\n")
        fd.write(f"  Copy to {end_copy_to- start_copy_to:.2f} seconds\n")
        fd.write(f"  Copy from {end_copy_from - start_copy_from:.2f} seconds\n")
        fd.write(f"  Remove {end_rm - start_rm:.2f} seconds\n")
        fd.write(f"  List {end_ls - start_ls:.2f} seconds\n")


@pytest.fixture(scope="module", autouse=True)
def setup_module():
    """
    Setup for this test module
    """
    #
    # Create test file
    #
    with open(TEST_INPUT_FILE, "w") as output_file:
        command = f"dd if=/dev/urandom bs={TEST_FILE_SIZE} count=1 | base64"
        result = subprocess.run(command, shell=True, stdout=output_file, text=True)
    #
    # Run the tests
    #
    yield
    #
    # Remove the test file
    #
    try:
        os.remove(TEST_INPUT_FILE)
    except FileNotFoundError:
        pass
    #
    # And the test output file
    #
    try:
        os.remove(TEST_OUTPUT_FILE)
    except FileNotFoundError:
        pass
