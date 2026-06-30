#!/usr/bin/env python3
"""
Simple validation test to verify test framework and SMB connectivity
Run this first to make sure basic setup is working before running disconnect tests
"""

import subprocess
import os
import pytest

# Test configuration
TEST_SERVER_URL = "//vnc:happy@192.168.1.60/foobar"
TEST_FILE_LOCAL = os.path.expanduser("~/Downloads/install.img")

def run_command(command, timeout=30):
    """Simple command runner with proper OpenFiles environment"""
    # Set up environment for OpenFiles
    env = os.environ.copy()
    env['PATH'] = env.get('PATH', '') + ':/usr/local/bin/openfiles'
    env['LD_LIBRARY_PATH'] = env.get('LD_LIBRARY_PATH', '') + ':/usr/local/lib64'

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env
        )
        return result
    except subprocess.TimeoutExpired:
        return type('obj', (object,), {'returncode': -1, 'stderr': 'Timeout', 'stdout': ''})

def test_environment_setup(logfile):
    """Verify test environment is properly configured"""

    with open(logfile, "w") as fd:
        fd.write("=== Simple Validation Test ===\n")

        # Test 1: Check if test file exists
        if os.path.exists(TEST_FILE_LOCAL):
            file_size = os.path.getsize(TEST_FILE_LOCAL)
            fd.write(f"✓ Test file exists: {TEST_FILE_LOCAL} ({file_size} bytes)\n")
        else:
            fd.write(f"✗ Test file missing: {TEST_FILE_LOCAL}\n")
            assert False, f"Test file {TEST_FILE_LOCAL} not found"

        # Test 2: Check samba service
        result = run_command("systemctl is-active smb")
        if result.returncode == 0:
            fd.write("✓ Samba service is running\n")
        else:
            fd.write(f"✗ Samba service not running: {result.stderr}\n")
            assert False, "Samba service not running"

        # Test 3: Basic SMB connectivity
        result = run_command(f"smbls {TEST_SERVER_URL}/")
        if result.returncode == 0:
            fd.write("✓ SMB connectivity working\n")
            fd.write(f"Directory listing:\n{result.stdout}\n")
        else:
            fd.write(f"✗ SMB connection failed: {result.stderr}\n")
            assert False, f"Cannot connect to {TEST_SERVER_URL}"

        # Test 4: Test small file copy
        small_test_file = "/tmp/simple_test.txt"
        with open(small_test_file, 'w') as f:
            f.write("Hello, OpenFiles test!")

        result = run_command(f"smbcp {small_test_file} {TEST_SERVER_URL}/simple_test.txt")
        if result.returncode == 0:
            fd.write("✓ Small file copy working\n")
        else:
            fd.write(f"✗ Small file copy failed: {result.stderr}\n")
            assert False, f"Small file copy failed: {result.stderr}"

        # Clean up
        run_command(f"smbrm {TEST_SERVER_URL}/simple_test.txt")
        os.remove(small_test_file)

        fd.write("\n=== All validation tests passed! ===\n")
        fd.write("Environment is ready for disconnect race condition testing.\n")

if __name__ == "__main__":
    print("Running simple validation...")
    import sys
    sys.exit(pytest.main([__file__, "-v", "--logfile=simple_validation.log"]))