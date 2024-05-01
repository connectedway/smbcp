#
# This python script performs simple tests against all known DFS locations in
# the Connected Way Vapornet openfiles qualification network
#
# Domain: DOUBLEDOUBLEU.COM
#  DCs: intuition.doubledoubleu.com
#       creativity.iritdcb.doubledoubleu.com
#
#  Shares:
#       \\creativity.doubledoubleu.com\air : C:\Shares\air
#       \\creativity.doubledoubleu.com\earth : C:\Shares\earth
#       \\creativity.doubledoubleu.com\Shared : C:\Shares\Shared
#       \\creativity.doubledoubleu.com\Spirit : C:\DFSRoots\Spirit
#
#       \\creativity.doubledoubleu.com\Root : c:\DFSRoots\Root
#
#       \\creativity.doubledoubleu.com\wine : C:\Shares\wine
#
#       \\intuition.doubledoubleu.com\air : C:\Shares\air
#       \\intuition.doubledoubleu.com\earth : C:\Shares\earth
#       \\intuition.doubledoubleu.com\Shared : C:\Shares\Shared
#       \\intuition.doubledoubleu.com\Spirit : C:\DFSRoots\Spirit
#
#       \\intuition.doubledoubleu.com\Root : c:\DFSRoots\Root
#
#       \\intuition.doubledoubleu.com\water : c:\Shares\water
#
#  DFS Roots:
#       \\creativity.doubledoubleu.com\Spirit
#       \\intuition.doubledoubleu.com\Spirit
#
#       \\creativity.doubledoubleu.com\Root
#       \\intuition.doubledoubleu.com\Root

#  DFS Links:
#       \\creativity.doubledoubleu.com\Spirit\air -> \\creativity.doubledoubleu.com\air
#       \\creativity.doubledoubleu.com\Spirit\earth -> \\creativity.doubledoubleu.com\earth
#       \\intuition.doubledoubleu.com\Spirit\air -> \\intuition.doubledoubleu.com\air
#       \\intuition.doubledoubleu.com\Spirit\earth -> \\intuition.doubledoubleu.com\earth
#
#       \\creativity.doubledoubleu.com\Root\wine -> \\intuition.doubledoubleu.com\water
#       \\intuition.doubledoubleu.com\Root\water -> \\creativity.doubledoubleu.com\wine
#
#
#  Replicated Storage:
#       \\creativity.doubledoubleu.com\Spirit
#       \\intuition.doubledoubleu.com\Spirit


import subprocess
import sys
import argparse
import os
import time
import fcntl

import pytest

#
# Each test has a configuration.  From a test execution perspective
# we will run tests with both creativity and intuition opertional
# just creativity, or just intuition.
#
# Tests on the otherhand have requirements.  They may require either
# server be running, both servers be running, or a specific server be running.
# This is specified with the config column of the tests table.  Valid
# values are "any", "both", "creativity", or "intuition".
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
    ("DFS DC", "//CREATIVITY/Spirit/air", "creativity"),
    ("DFS DC Alternate", "//CREATIVITY.DOUBLEDOUBLEU.COM/Spirit/air", "creativity"),
    ("DFS DCB", "//INTUITION/Spirit/air", "intuition"),
    ("DFS DCB Alternate", "//INTUITION.DOUBLEDOUBLEU.COM/Spirit/air", "intuition"),
    ("DFS DC (LC)", "//creativity/Spirit/air", "creativity"),
    ("DFS DC Alternate (LC)", "//creativity.doubledoubleu.com/Spirit/air", "creativity"),
    ("DFS DCB (LC)", "//intuition/Spirit/air", "intuition"),
    ("DFS DCB Alternate (LC)", "//intuition.doubledoubleu.com/Spirit/air", "intuition"),
    ("SMB Domain", "//DOUBLEDOUBLEU/air", "any"),
    ("SMB Domain Alternate", "//DOUBLEDOUBLEU.COM/air", "any"),
    ("SMB Domain (LC)", "//doubledoubleu/air", "any"),
    ("SMB Domin Alternate (LC)", "//doubledoubleu.com/air", "any"),
    ("SMB DC", "//CREATIVITY/air", "creativity"),
    ("SMB DC Alternate", "//CREATIVITY.DOUBLEDOUBLEU.COM/air", "creativity"),
    ("SMB DCB", "//INTUITION/air", "intuition"),
    ("SMB DCB Alternate", "//INTUITION.DOUBLEDOUBLEU.COM/air", "intuition"),
    ("SMB DC (LC)", "//creativity/air", "creativity"),
    ("SMB DC Alternate (LC)", "//creativity.doubledoubleu.com/air", "creativity"),
    ("SMB DCB (LC)", "//intuition/air", "intuition"),
    ("SMB DCB Alternate (LC)", "//intuition.doubledoubleu.com/air", "intuition"),
    ("Non Replicated Domain Cross DCB", "//DOUBLEDOUBLEU/Root/water", "intuition"),
    ("Non Replicated Domain Cross DCA", "//DOUBLEDOUBLEU/Root/wine", "creativity"),
    ("Non Replicated DC Cross DCB", "//creativity/Root/water", "both"),
    ("Non Replicated DC DCB", "//intuition/Root/water", "intuition"),
    ("Non Replicated DC Cross DCA", "//creativity/Root/wine", "creativity"),
    ("Non Replicated DC DC", "//intuition/Root/wine", "both"),
    ("Non Replicated SMB DCA", "//creativity/wine", "creativity"),
    ("Non Replicated SMB DCB", "//intuition/water", "intuition"),
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
DENY_CREATIVITY = "creativity"
DENY_INTUITION = "intuition"


@pytest.fixture(params=[DENY_NONE, DENY_CREATIVITY, DENY_INTUITION])
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
    dfs_iptables_path = os.path.dirname(
        os.path.abspath(__file__)
    ) + "/dfs_iptables.py"

    #
    # Spawn off the firewall utility
    #
    dfs_iptables = subprocess.Popen(
        ["python3", dfs_iptables_path],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    #
    # Set stdout as non blocking so we can read output asynchronously
    #
    fcntl.fcntl(dfs_iptables.stdout.fileno(), fcntl.F_SETFL, os.O_NONBLOCK)
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
        dfs_iptables.stdin.write("reset\n")
        dfs_iptables.stdin.flush()
        #
        # Check if we want to set up deny rules
        #
        if request.param != DENY_NONE:
            #
            # Deny traffic to the specified host
            #
            dfs_iptables.stdin.write(f"deny {request.param}\n")
            dfs_iptables.stdin.flush()
            #
            # And get the firewall status for our log
            #
            dfs_iptables.stdin.write(f"status\n")
            dfs_iptables.stdin.flush()

        #
        # Scrape output from the firewall and log.
        # It may be that the firewall hasn't completed the command
        # We had a delay here so we could capture the output but
        # opted to run without the delay.  This may result in the
        # status of the firewall configuration after setting the
        # deny rule may not appear in the log file until later in
        # test output
        #
        for line in dfs_iptables.stdout:
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
            dfs_iptables.stdin.write(f"reset\n")
            dfs_iptables.stdin.flush()
            #
            # Capture firewall status after the reset
            #
            dfs_iptables.stdin.write(f"status\n")
            dfs_iptables.stdin.flush()
        #
        # Quite the firewall app
        #
        dfs_iptables.stdin.write(f"quit\n")
        dfs_iptables.stdin.flush()
        #
        # Wait for the firewall app to complete
        #
        dfs_iptables.wait()
        #
        # Now flush the output of the firewall app to our logfile
        #
        for line in dfs_iptables.stdout:
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
    elif setup_teardown == DENY_INTUITION and (config == "any" or config == "creativity"):
        #
        # Firewall is denying intuition.  We only want to run the
        # iteration if the iteration can run under any firewall config (any)
        # or the test only needs creativity.
        #
        pass
    elif setup_teardown == DENY_CREATIVITY and (config == "any" or config == "intuition"):
        #
        # Firewall is denying creativity.  We only want to run the
        # iteration if the iteration can run under any firewall config (any)
        # or the test only needs intuition.
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
