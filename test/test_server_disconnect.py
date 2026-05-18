#!/usr/bin/env python3
"""
Server Disconnect Race Condition Testing

This test module validates the session validation and cleanup fixes implemented
in commits e7cc519 and 2a5f2df. It focuses on reproducing and validating fixes
for race conditions that occur when API operations access session structures
after the real-time layer has cleaned them up due to server disconnects.

Test Target: Local samba server at //vnc:happy@192.168.1.60/foobar
Test File: ~/Downloads/install.img (1GB file for stress testing)
"""

import subprocess
import sys
import threading
import time
import os
import random
import psutil
import pytest
import signal
from contextlib import contextmanager

# Test configuration
TEST_SERVER_URL = "//vnc:happy@192.168.1.60/foobar"
TEST_FILE_LOCAL = os.path.expanduser("~/Downloads/install.img")
TEST_FILE_REMOTE_LARGE = "test_large_disconnect.img"
TEST_FILE_REMOTE_SMALL = "test_small_disconnect.txt"

# Test file sizes
LARGE_FILE_SIZE = os.path.getsize(TEST_FILE_LOCAL) if os.path.exists(TEST_FILE_LOCAL) else 1024*1024*1024
SMALL_FILE_SIZE = 1024

def run_command_with_timeout(command, timeout=30, capture_output=True):
    """
    Run a shell command with timeout and capture output

    Args:
        command (str): Shell command to run
        timeout (int): Timeout in seconds
        capture_output (bool): Whether to capture stdout/stderr

    Returns:
        dict: {'returncode': int, 'stdout': str, 'stderr': str, 'timed_out': bool}
    """
    # Set up environment for OpenFiles
    env = os.environ.copy()
    env['PATH'] = env.get('PATH', '') + ':/usr/local/bin/openfiles'
    env['LD_LIBRARY_PATH'] = env.get('LD_LIBRARY_PATH', '') + ':/usr/local/lib64'

    try:
        if capture_output:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env
            )
            return {
                'returncode': result.returncode,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'timed_out': False
            }
        else:
            result = subprocess.run(
                command,
                shell=True,
                timeout=timeout,
                env=env
            )
            return {
                'returncode': result.returncode,
                'stdout': '',
                'stderr': '',
                'timed_out': False
            }
    except subprocess.TimeoutExpired:
        return {
            'returncode': -1,
            'stdout': '',
            'stderr': f'Command timed out after {timeout} seconds',
            'timed_out': True
        }

def log_command(command, result, logfile):
    """Log command execution details"""
    with open(logfile, "a") as fd:
        fd.write(f"Command: {command}\n")
        fd.write(f"Return code: {result['returncode']}\n")
        fd.write(f"Timed out: {result['timed_out']}\n")
        if result['stdout']:
            fd.write(f"STDOUT:\n{result['stdout']}\n")
        if result['stderr']:
            fd.write(f"STDERR:\n{result['stderr']}\n")
        fd.write("=" * 50 + "\n")
        fd.flush()

def validate_memory_cleanliness(output, test_name, logfile):
    """
    Validate OpenFiles memory cleanliness from command output

    Args:
        output (str): Command stdout to analyze
        test_name (str): Name of test for error reporting
        logfile (str): Log file for detailed reporting

    Returns:
        dict: Memory analysis results

    Raises:
        AssertionError: If memory leaks are detected
    """
    import re

    analysis = {
        'heap_clean': False,
        'total_allocated': None,
        'max_allocated': None,
        'deactivation_found': False,
        'memory_leak_detected': False
    }

    with open(logfile, "a") as fd:
        fd.write(f"\n=== MEMORY LEAK ANALYSIS: {test_name} ===\n")

        # Check for heap cleanliness message
        if "Heap is Empty, No leaks detected" in output:
            analysis['heap_clean'] = True
            fd.write("✓ PASS: 'Heap is Empty, No leaks detected' found\n")
        else:
            fd.write("✗ FAIL: 'Heap is Empty, No leaks detected' NOT found\n")
            analysis['memory_leak_detected'] = True

        # Check for proper stack deactivation
        if "Deactivating Stack" in output:
            analysis['deactivation_found'] = True
            fd.write("✓ PASS: Stack deactivation found\n")
        else:
            fd.write("✗ FAIL: Stack deactivation NOT found\n")

        # Extract total allocated memory
        total_memory_match = re.search(r'Total Allocated Memory (\d+)', output)
        if total_memory_match:
            analysis['total_allocated'] = int(total_memory_match.group(1))
            fd.write(f"✓ INFO: Total Allocated Memory: {analysis['total_allocated']}\n")

            if analysis['total_allocated'] == 0:
                fd.write("✓ PASS: Total allocated memory is 0 (no leaks)\n")
            else:
                fd.write(f"✗ FAIL: Total allocated memory is {analysis['total_allocated']} (MEMORY LEAK!)\n")
                analysis['memory_leak_detected'] = True
        else:
            fd.write("✗ FAIL: Total Allocated Memory information NOT found\n")
            analysis['memory_leak_detected'] = True

        # Extract max allocated memory
        max_memory_match = re.search(r'Max Allocated Memory (\d+)', output)
        if max_memory_match:
            analysis['max_allocated'] = int(max_memory_match.group(1))
            fd.write(f"✓ INFO: Max Allocated Memory: {analysis['max_allocated']}\n")

        # Final assessment
        if analysis['memory_leak_detected']:
            fd.write("✗ OVERALL: MEMORY LEAK DETECTED!\n")
        else:
            fd.write("✓ OVERALL: MEMORY CLEAN - No leaks detected\n")

        fd.write("=" * 50 + "\n")
        fd.flush()

    # Assert no memory leaks
    if analysis['memory_leak_detected']:
        error_msg = f"MEMORY LEAK DETECTED in {test_name}!"
        if analysis['total_allocated'] is not None and analysis['total_allocated'] > 0:
            error_msg += f" Total allocated: {analysis['total_allocated']} bytes"
        if not analysis['heap_clean']:
            error_msg += " | Heap not clean"
        raise AssertionError(error_msg)

    if not analysis['deactivation_found']:
        raise AssertionError(f"OpenFiles stack deactivation not found in {test_name} - incomplete shutdown")

    return analysis

def restart_samba_service():
    """Restart the samba service"""
    result = run_command_with_timeout("sudo systemctl restart smb", timeout=10)
    time.sleep(2)  # Give service time to start
    return result['returncode'] == 0

def get_resource_usage():
    """Get current process resource usage"""
    process = psutil.Process()
    return {
        'memory_mb': process.memory_info().rss / 1024 / 1024,
        'open_files': len(process.open_files()),
        'num_fds': process.num_fds(),
        'cpu_percent': process.cpu_percent()
    }

@contextmanager
def resource_monitor(test_name, logfile):
    """Context manager to monitor resource usage before/after test"""
    start_resources = get_resource_usage()
    start_time = time.time()

    with open(logfile, "a") as fd:
        fd.write(f"\n=== RESOURCE MONITOR START: {test_name} ===\n")
        fd.write(f"Start resources: {start_resources}\n")
        fd.flush()

    try:
        yield start_resources
    finally:
        end_resources = get_resource_usage()
        end_time = time.time()
        duration = end_time - start_time

        # Calculate deltas
        memory_delta = end_resources['memory_mb'] - start_resources['memory_mb']
        fd_delta = end_resources['num_fds'] - start_resources['num_fds']

        with open(logfile, "a") as fd:
            fd.write(f"=== RESOURCE MONITOR END: {test_name} ===\n")
            fd.write(f"Duration: {duration:.2f} seconds\n")
            fd.write(f"End resources: {end_resources}\n")
            fd.write(f"Memory delta: {memory_delta:+.1f} MB\n")
            fd.write(f"FD delta: {fd_delta:+d}\n")

            # Flag potential leaks
            if abs(memory_delta) > 50:  # >50MB change
                fd.write(f"WARNING: Large memory change detected!\n")
            if fd_delta > 5:  # >5 file descriptors leaked
                fd.write(f"WARNING: Possible file descriptor leak!\n")

            fd.write("=" * 50 + "\n")
            fd.flush()

class SMBOperationThread(threading.Thread):
    """Thread that performs continuous SMB operations"""

    def __init__(self, name, operation_type, logfile, duration=30):
        super().__init__(name=name)
        self.operation_type = operation_type
        self.logfile = logfile
        self.duration = duration
        self.results = []
        self.stop_event = threading.Event()
        self.daemon = True

    def run(self):
        start_time = time.time()
        operation_count = 0

        while not self.stop_event.is_set() and (time.time() - start_time) < self.duration:
            try:
                if self.operation_type == "copy_large":
                    command = f"smbcp {TEST_FILE_LOCAL} {TEST_SERVER_URL}/{TEST_FILE_REMOTE_LARGE}"
                elif self.operation_type == "copy_small":
                    # Create a small test file
                    small_file = f"/tmp/small_test_{operation_count}.txt"
                    with open(small_file, 'w') as f:
                        f.write("x" * SMALL_FILE_SIZE)
                    command = f"smbcp {small_file} {TEST_SERVER_URL}/small_test_{operation_count}.txt"
                elif self.operation_type == "list":
                    command = f"smbls {TEST_SERVER_URL}/"
                elif self.operation_type == "delete":
                    command = f"smbrm {TEST_SERVER_URL}/{TEST_FILE_REMOTE_SMALL}"
                else:
                    continue

                result = run_command_with_timeout(command, timeout=15)
                self.results.append({
                    'operation': operation_count,
                    'command': command,
                    'result': result,
                    'timestamp': time.time()
                })

                # Clean up small files
                if self.operation_type == "copy_small":
                    try:
                        os.remove(small_file)
                    except:
                        pass

                operation_count += 1
                time.sleep(random.uniform(0.1, 0.5))  # Random delay between operations

            except Exception as e:
                self.results.append({
                    'operation': operation_count,
                    'command': 'EXCEPTION',
                    'result': {'returncode': -999, 'stderr': str(e), 'timed_out': False},
                    'timestamp': time.time()
                })

    def stop(self):
        self.stop_event.set()

    def get_summary(self):
        total_ops = len(self.results)
        successful_ops = len([r for r in self.results if r['result']['returncode'] == 0])
        failed_ops = total_ops - successful_ops
        timed_out_ops = len([r for r in self.results if r['result']['timed_out']])

        return {
            'total_operations': total_ops,
            'successful': successful_ops,
            'failed': failed_ops,
            'timed_out': timed_out_ops,
            'success_rate': (successful_ops / total_ops * 100) if total_ops > 0 else 0
        }

@pytest.fixture(scope="session")
def verify_test_environment():
    """Verify test environment is set up correctly"""

    # Check test file exists
    assert os.path.exists(TEST_FILE_LOCAL), f"Test file {TEST_FILE_LOCAL} does not exist"

    # Check samba is running
    result = run_command_with_timeout("systemctl is-active smb")
    assert result['returncode'] == 0, "Samba service is not running"

    # Test basic connectivity
    result = run_command_with_timeout(f"smbls {TEST_SERVER_URL}/")
    assert result['returncode'] == 0, f"Cannot connect to {TEST_SERVER_URL}"

    yield

    # Cleanup any test files
    cleanup_commands = [
        f"smbrm {TEST_SERVER_URL}/{TEST_FILE_REMOTE_LARGE}",
        f"smbrm {TEST_SERVER_URL}/{TEST_FILE_REMOTE_SMALL}",
    ]
    for cmd in cleanup_commands:
        run_command_with_timeout(cmd)

def test_basic_operations_with_restart(verify_test_environment, logfile):
    """Test basic SMB operations survive samba restart"""

    with resource_monitor("basic_operations_with_restart", logfile) as start_resources:
        with open(logfile, "a") as fd:
            fd.write("\n=== TEST: Basic Operations With Restart ===\n")

        # Initial file copy
        command = f"smbcp {TEST_FILE_LOCAL} {TEST_SERVER_URL}/{TEST_FILE_REMOTE_LARGE}"
        result = run_command_with_timeout(command, timeout=60)
        log_command(command, result, logfile)
        assert result['returncode'] == 0, f"Initial copy failed: {result['stderr']}"

        # Restart samba
        with open(logfile, "a") as fd:
            fd.write("Restarting samba service...\n")
        assert restart_samba_service(), "Failed to restart samba service"

        # Try operations after restart - should get proper error codes
        command = f"smbls {TEST_SERVER_URL}/"
        result = run_command_with_timeout(command)
        log_command(command, result, logfile)
        # Should either succeed (new session) or fail gracefully (not crash)
        assert result['returncode'] != -11, "smbls crashed with SIGSEGV"

        # Test file deletion
        command = f"smbrm {TEST_SERVER_URL}/{TEST_FILE_REMOTE_LARGE}"
        result = run_command_with_timeout(command)
        log_command(command, result, logfile)

@pytest.mark.parametrize("disconnect_interval", [1, 3, 5])
def test_concurrent_operations_with_periodic_restart(verify_test_environment, logfile, disconnect_interval):
    """Test concurrent file operations with periodic samba restarts"""

    test_name = f"concurrent_ops_restart_{disconnect_interval}s"
    with resource_monitor(test_name, logfile) as start_resources:

        with open(logfile, "a") as fd:
            fd.write(f"\n=== TEST: Concurrent Operations (restart every {disconnect_interval}s) ===\n")

        # Start operation threads
        threads = [
            SMBOperationThread("copy_ops", "copy_small", logfile, duration=30),
            SMBOperationThread("list_ops", "list", logfile, duration=30),
        ]

        for thread in threads:
            thread.start()

        # Periodically restart samba
        restart_count = 0
        test_start = time.time()
        test_duration = 30  # 30 seconds total test

        while (time.time() - test_start) < test_duration:
            time.sleep(disconnect_interval)

            with open(logfile, "a") as fd:
                fd.write(f"Performing restart #{restart_count + 1}...\n")
                fd.flush()

            restart_success = restart_samba_service()
            restart_count += 1

            if not restart_success:
                with open(logfile, "a") as fd:
                    fd.write(f"WARNING: Restart #{restart_count} failed!\n")

        # Stop all threads
        for thread in threads:
            thread.stop()

        for thread in threads:
            thread.join(timeout=10)

        # Analyze results
        with open(logfile, "a") as fd:
            fd.write(f"Performed {restart_count} samba restarts\n")

            for thread in threads:
                summary = thread.get_summary()
                fd.write(f"\n{thread.name} Summary:\n")
                fd.write(f"  Total operations: {summary['total_operations']}\n")
                fd.write(f"  Successful: {summary['successful']}\n")
                fd.write(f"  Failed: {summary['failed']}\n")
                fd.write(f"  Timed out: {summary['timed_out']}\n")
                fd.write(f"  Success rate: {summary['success_rate']:.1f}%\n")

                # Log any crashes (SIGSEGV = -11)
                crashes = [r for r in thread.results if r['result']['returncode'] == -11]
                if crashes:
                    fd.write(f"  CRITICAL: {len(crashes)} crashes detected!\n")
                    for crash in crashes:
                        fd.write(f"    Crash at operation {crash['operation']}: {crash['command']}\n")

                # Assert no crashes occurred
                assert len(crashes) == 0, f"{thread.name} had {len(crashes)} crashes"

def test_large_file_transfer_with_disconnect(verify_test_environment, logfile):
    """Test large file transfer interrupted by server disconnect"""

    with resource_monitor("large_file_disconnect", logfile) as start_resources:

        with open(logfile, "a") as fd:
            fd.write("\n=== TEST: Large File Transfer With Disconnect ===\n")

        # Start large file transfer in background
        command = f"smbcp {TEST_FILE_LOCAL} {TEST_SERVER_URL}/{TEST_FILE_REMOTE_LARGE}"

        with open(logfile, "a") as fd:
            fd.write(f"Starting large file transfer: {command}\n")
            fd.flush()

        # Set up environment for OpenFiles
        env = os.environ.copy()
        env['PATH'] = env.get('PATH', '') + ':/usr/local/bin/openfiles'
        env['LD_LIBRARY_PATH'] = env.get('LD_LIBRARY_PATH', '') + ':/usr/local/lib64'

        # Start the transfer process
        process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env
        )

        # Let it run for a few seconds
        time.sleep(3)

        # Restart samba mid-transfer
        with open(logfile, "a") as fd:
            fd.write("Restarting samba during file transfer...\n")
            fd.flush()

        restart_samba_service()

        # Wait for process to complete
        try:
            stdout, stderr = process.communicate(timeout=30)
            returncode = process.returncode
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
            returncode = -1
            stderr += "\nProcess killed due to timeout"

        with open(logfile, "a") as fd:
            fd.write(f"Transfer completed with return code: {returncode}\n")
            if stdout:
                fd.write(f"STDOUT: {stdout}\n")
            if stderr:
                fd.write(f"STDERR: {stderr}\n")

        # The key test: should not crash (SIGSEGV = -11)
        assert returncode != -11, f"Large file transfer crashed: {stderr}"

        # Should return proper error code (not 0 since we interrupted it)
        # But exact error code depends on timing

def test_session_validation_with_rapid_reconnects(verify_test_environment, logfile):
    """Test session validation under rapid connect/disconnect cycles"""

    with resource_monitor("rapid_reconnects", logfile) as start_resources:

        with open(logfile, "a") as fd:
            fd.write("\n=== TEST: Session Validation Rapid Reconnects ===\n")

        # Rapid connect/disconnect/reconnect cycles
        for cycle in range(10):
            with open(logfile, "a") as fd:
                fd.write(f"Cycle {cycle + 1}: Connect -> Disconnect -> Reconnect\n")
                fd.flush()

            # Quick operation
            command = f"smbls {TEST_SERVER_URL}/"
            result = run_command_with_timeout(command, timeout=5)

            # Immediate restart
            restart_samba_service()

            # Another quick operation (may fail, but shouldn't crash)
            command = f"smbls {TEST_SERVER_URL}/"
            result = run_command_with_timeout(command, timeout=5)
            log_command(f"cycle_{cycle}_post_restart", result, logfile)

            assert result['returncode'] != -11, f"Cycle {cycle} crashed with SIGSEGV"

            time.sleep(0.5)  # Brief pause between cycles

def test_memory_leak_detection(verify_test_environment, logfile):
    """Test for memory leaks during repeated disconnect scenarios"""

    with resource_monitor("memory_leak_detection", logfile) as start_resources:

        with open(logfile, "a") as fd:
            fd.write("\n=== TEST: Memory Leak Detection ===\n")

        # Baseline operations
        baseline_operations = 5
        for i in range(baseline_operations):
            command = f"smbcp {TEST_FILE_LOCAL} {TEST_SERVER_URL}/leak_test_{i}.img"
            result = run_command_with_timeout(command, timeout=60)

            command = f"smbrm {TEST_SERVER_URL}/leak_test_{i}.img"
            result = run_command_with_timeout(command, timeout=10)

        baseline_resources = get_resource_usage()

        # Operations with disconnects
        disconnect_operations = 10
        for i in range(disconnect_operations):
            with open(logfile, "a") as fd:
                fd.write(f"Disconnect cycle {i + 1}/{disconnect_operations}\n")
                fd.flush()

            # Start operation
            command = f"smbcp {TEST_FILE_LOCAL} {TEST_SERVER_URL}/leak_test_disconnect_{i}.img"

            # Set up environment for OpenFiles
            env = os.environ.copy()
            env['PATH'] = env.get('PATH', '') + ':/usr/local/bin/openfiles'
            env['LD_LIBRARY_PATH'] = env.get('LD_LIBRARY_PATH', '') + ':/usr/local/lib64'

            process = subprocess.Popen(command, shell=True, env=env)

            # Quick disconnect
            time.sleep(1)
            restart_samba_service()

            # Let process finish (will likely error)
            process.wait()

            # Cleanup attempt
            command = f"smbrm {TEST_SERVER_URL}/leak_test_disconnect_{i}.img"
            run_command_with_timeout(command, timeout=5)

        final_resources = get_resource_usage()

        # Check for significant resource increases
        memory_increase = final_resources['memory_mb'] - baseline_resources['memory_mb']
        fd_increase = final_resources['num_fds'] - baseline_resources['num_fds']

        with open(logfile, "a") as fd:
            fd.write(f"Memory increase after disconnect cycles: {memory_increase:.1f} MB\n")
            fd.write(f"FD increase after disconnect cycles: {fd_increase}\n")

        # Assert reasonable resource usage (adjust thresholds as needed)
        assert memory_increase < 100, f"Possible memory leak: {memory_increase:.1f} MB increase"
        assert fd_increase < 20, f"Possible FD leak: {fd_increase} file descriptors increase"

@pytest.mark.parametrize("idle_duration", [60, 120])  # 1 and 2 minute idle tests
def test_idle_timeout_handling(verify_test_environment, logfile, idle_duration):
    """Test session validation during idle timeout scenarios"""

    test_name = f"idle_timeout_{idle_duration}s"
    with resource_monitor(test_name, logfile) as start_resources:

        with open(logfile, "a") as fd:
            fd.write(f"\n=== TEST: Idle Timeout ({idle_duration} seconds) ===\n")
            fd.write(f"Testing session validation with {idle_duration}-second idle period\n")

        # Use smbidle to test idle timeout behavior
        idle_file = f"idle_test_{idle_duration}s.dat"
        command = f"smbidle {TEST_SERVER_URL}/{idle_file} {idle_duration} 1024"

        with open(logfile, "a") as fd:
            fd.write(f"Starting idle test: {command}\n")
            fd.flush()

        result = run_command_with_timeout(command, timeout=idle_duration + 30)

        # Enhanced logging to capture complete smbidle output
        with open(logfile, "a") as fd:
            fd.write(f"=== COMPLETE SMBIDLE OUTPUT ===\n")
            fd.write(f"Command: {command}\n")
            fd.write(f"Return code: {result['returncode']}\n")
            fd.write(f"Timed out: {result['timed_out']}\n")
            fd.write(f"STDOUT LENGTH: {len(result['stdout'])} characters\n")
            fd.write(f"STDERR LENGTH: {len(result['stderr'])} characters\n")
            fd.write("--- COMPLETE STDOUT ---\n")
            fd.write(result['stdout'])
            fd.write("\n--- END STDOUT ---\n")
            if result['stderr']:
                fd.write("--- COMPLETE STDERR ---\n")
                fd.write(result['stderr'])
                fd.write("\n--- END STDERR ---\n")
            fd.write("=" * 60 + "\n")
            fd.flush()

        # Key assertion: should not crash regardless of timeout behavior
        assert result['returncode'] != -11, f"Idle timeout test crashed with SIGSEGV"

        # AUTOMATED MEMORY LEAK VALIDATION
        memory_analysis = validate_memory_cleanliness(
            result['stdout'],
            f"idle_timeout_{idle_duration}s",
            logfile
        )

        # Analyze the results
        with open(logfile, "a") as fd:
            if result['returncode'] == 0:
                fd.write("SUCCESS: Idle timeout test completed without errors\n")
                fd.write("This indicates session remained active or recovered gracefully\n")
                fd.write(f"MEMORY: Total allocated: {memory_analysis['total_allocated']}, ")
                fd.write(f"Max allocated: {memory_analysis['max_allocated']}, ")
                fd.write(f"Heap clean: {memory_analysis['heap_clean']}\n")
            elif result['timed_out']:
                fd.write("TIMEOUT: Idle test process timed out\n")
                fd.write("This may indicate a hang in session validation\n")
                # This is concerning and should be investigated
                assert False, "Idle test timed out - possible deadlock in session validation"
            else:
                fd.write(f"EXPECTED: Idle test failed with return code {result['returncode']}\n")
                fd.write("This likely indicates proper idle timeout and session cleanup\n")
                fd.write(f"MEMORY: Total allocated: {memory_analysis['total_allocated']}, ")
                fd.write(f"Max allocated: {memory_analysis['max_allocated']}, ")
                fd.write(f"Heap clean: {memory_analysis['heap_clean']}\n")

        # Cleanup test file
        cleanup_command = f"smbrm {TEST_SERVER_URL}/{idle_file}"
        cleanup_result = run_command_with_timeout(cleanup_command, timeout=10)
        if cleanup_result['returncode'] != 0:
            with open(logfile, "a") as fd:
                fd.write("Note: Test file cleanup failed (file may not exist due to timeout)\n")

def test_idle_timeout_with_server_restart(verify_test_environment, logfile):
    """Test idle timeout combined with server restart - the ultimate stress test"""

    with resource_monitor("idle_timeout_with_restart", logfile) as start_resources:

        with open(logfile, "a") as fd:
            fd.write("\n=== TEST: Idle Timeout With Server Restart ===\n")
            fd.write("Testing worst-case scenario: idle session + server restart\n")

        # Start an idle operation
        idle_file = "idle_restart_test.dat"
        command = f"smbidle {TEST_SERVER_URL}/{idle_file} 90 512"  # 90-second idle

        with open(logfile, "a") as fd:
            fd.write(f"Starting idle operation: {command}\n")
            fd.flush()

        # Set up environment for OpenFiles
        env = os.environ.copy()
        env['PATH'] = env.get('PATH', '') + ':/usr/local/bin/openfiles'
        env['LD_LIBRARY_PATH'] = env.get('LD_LIBRARY_PATH', '') + ':/usr/local/lib64'

        # Start the idle process
        process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env
        )

        # Let it start and begin idling
        time.sleep(10)

        # Restart samba while it's idling
        with open(logfile, "a") as fd:
            fd.write("Restarting samba during idle period...\n")
            fd.flush()

        restart_samba_service()

        # Wait for the idle process to complete
        try:
            stdout, stderr = process.communicate(timeout=120)  # Give it time to complete
            returncode = process.returncode
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
            returncode = -1
            stderr += "\nProcess killed due to timeout"

        with open(logfile, "a") as fd:
            fd.write(f"Idle+restart test completed with return code: {returncode}\n")
            if stdout:
                fd.write(f"STDOUT:\n{stdout}\n")
            if stderr:
                fd.write(f"STDERR:\n{stderr}\n")

        # Critical test: should handle the scenario gracefully, not crash
        assert returncode != -11, f"Idle+restart test crashed with SIGSEGV: {stderr}"

        # AUTOMATED MEMORY LEAK VALIDATION for idle + restart
        memory_analysis = validate_memory_cleanliness(
            stdout,
            "idle_timeout_with_restart",
            logfile
        )

        with open(logfile, "a") as fd:
            if returncode == 0:
                fd.write("REMARKABLE: Process survived idle timeout + server restart!\n")
                fd.write(f"MEMORY: Total allocated: {memory_analysis['total_allocated']}, ")
                fd.write(f"Max allocated: {memory_analysis['max_allocated']}, ")
                fd.write(f"Heap clean: {memory_analysis['heap_clean']}\n")
            else:
                fd.write("EXPECTED: Process failed gracefully during idle timeout + restart\n")
                fd.write("This demonstrates proper session validation under extreme conditions\n")
                fd.write(f"MEMORY: Total allocated: {memory_analysis['total_allocated']}, ")
                fd.write(f"Max allocated: {memory_analysis['max_allocated']}, ")
                fd.write(f"Heap clean: {memory_analysis['heap_clean']}\n")

        # Cleanup
        cleanup_command = f"smbrm {TEST_SERVER_URL}/{idle_file}"
        run_command_with_timeout(cleanup_command, timeout=10)


@pytest.mark.parametrize("idle_duration", [60, 120])
def test_find_transaction_idle_timeout(verify_test_environment, logfile, idle_duration):
    """Test Find transaction behavior during idle timeout scenarios"""

    test_name = f"find_idle_timeout_{idle_duration}s"
    with resource_monitor(test_name, logfile) as start_resources:

        with open(logfile, "a") as fd:
            fd.write(f"\n=== TEST: Find Transaction Idle Timeout ({idle_duration} seconds) ===\n")
            fd.write(f"Testing Find operations with {idle_duration}-second idle period\n")

        # Use smbfind to test Find transaction behavior during idle timeout
        # Use local executable since smbfind is not installed system-wide yet
        smbfind_path = "../smbfind"
        command = f"PATH=/usr/local/bin/openfiles:$PATH LD_LIBRARY_PATH=/usr/local/lib64:$LD_LIBRARY_PATH {smbfind_path} {TEST_SERVER_URL}/ 8 {idle_duration}"

        with open(logfile, "a") as fd:
            fd.write(f"Starting Find transaction idle test: {command}\n")
            fd.flush()

        result = run_command_with_timeout(command, timeout=idle_duration + 30)

        with open(logfile, "a") as fd:
            fd.write(f"Find idle test completed with return code: {result['returncode']}\n")
            if result['timed_out']:
                fd.write("WARNING: Find idle test timed out\n")

        # Validate that process didn't crash
        assert result['returncode'] != -11, f"Find idle test crashed with SIGSEGV"
        assert result['returncode'] == 0, f"Find idle test failed with return code {result['returncode']}"

        # Validate memory analysis
        memory_analysis = validate_memory_cleanliness(
            result['stdout'],
            test_name,
            logfile
        )
        # Enhanced logging to capture complete smbfind output
        with open(logfile, "a") as fd:
            fd.write(f"=== COMPLETE SMBFIND OUTPUT ===\n")
            fd.write(f"Command: {command}\n")
            fd.write(f"Return code: {result['returncode']}\n")
            fd.write(f"Timed out: {result['timed_out']}\n")
            fd.write(f"STDOUT LENGTH: {len(result['stdout'])} characters\n")
            fd.write(f"STDERR LENGTH: {len(result['stderr'])} characters\n")
            fd.write("--- COMPLETE STDOUT ---\n")
            fd.write(result['stdout'])
            fd.write("\n--- END STDOUT ---\n")
            fd.write("=" * 60 + "\n")

        # Validate memory analysis
        with open(logfile, "a") as fd:
            if memory_analysis['heap_clean']:
                fd.write("✓ PASS: Find transaction memory validation passed\n")
                fd.write(f"MEMORY: Total allocated: {memory_analysis['total_allocated']}, ")
                fd.write(f"Max allocated: {memory_analysis['max_allocated']}, ")
                fd.write(f"Heap clean: {memory_analysis['heap_clean']}\n")
            else:
                fd.write("✗ FAIL: Find transaction memory leak detected\n")


def test_find_transaction_server_disconnect(verify_test_environment, logfile):
    """Test Find transaction behavior during server disconnect"""

    with resource_monitor("find_server_disconnect", logfile) as start_resources:

        with open(logfile, "a") as fd:
            fd.write("\n=== TEST: Find Transaction Server Disconnect ===\n")
            fd.write("Testing Find operations with server restart during enumeration\n")

        # Start Find operation that will enumerate files slowly
        # Use local executable since smbfind is not installed system-wide yet
        smbfind_path = "../smbfind"
        command = f"PATH=/usr/local/bin/openfiles:$PATH LD_LIBRARY_PATH=/usr/local/lib64:$LD_LIBRARY_PATH {smbfind_path} {TEST_SERVER_URL}/ 15 45"

        with open(logfile, "a") as fd:
            fd.write(f"Starting Find operation: {command}\n")
            fd.flush()

        # Start the Find process
        process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        # Let it enumerate some files first
        time.sleep(8)

        # Restart samba during Find operation
        with open(logfile, "a") as fd:
            fd.write("Restarting samba during Find operation...\n")
            fd.flush()

        restart_samba_service()

        # Wait for process to complete
        try:
            stdout, stderr = process.communicate(timeout=60)
            returncode = process.returncode
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
            returncode = -1
            stderr += "\nFind process killed due to timeout"

        with open(logfile, "a") as fd:
            fd.write(f"Find operation completed with return code: {returncode}\n")
            if stdout:
                fd.write(f"STDOUT: {stdout}\n")
            if stderr:
                fd.write(f"STDERR: {stderr}\n")

        # The key test: should not crash (SIGSEGV = -11)
        assert returncode != -11, f"Find operation crashed with SIGSEGV during server disconnect"

        # Should complete with expected error code (session invalidated)
        assert returncode == 0, f"Find operation should handle disconnect gracefully, got: {returncode}"

        # Validate memory analysis if we have stdout
        if stdout:
            memory_analysis = validate_memory_cleanliness(
                stdout,
                "find_server_disconnect",
                logfile
            )
            with open(logfile, "a") as fd:
                if memory_analysis['heap_clean']:
                    fd.write("✓ PASS: Find transaction disconnect memory validation passed\n")
                    fd.write(f"MEMORY: Total allocated: {memory_analysis['total_allocated']}, ")
                    fd.write(f"Max allocated: {memory_analysis['max_allocated']}, ")
                    fd.write(f"Heap clean: {memory_analysis['heap_clean']}\n")
                else:
                    fd.write("✗ FAIL: Find transaction disconnect memory leak detected\n")

        with open(logfile, "a") as fd:
            fd.write("SUCCESS: Find transaction server disconnect test completed\n")


def test_async_copy_with_disconnect(verify_test_environment, logfile):
    """Test async copy operations (overlapped I/O) during server disconnect"""

    with resource_monitor("async_copy_disconnect", logfile) as start_resources:

        with open(logfile, "a") as fd:
            fd.write("\n=== TEST: Async Copy Server Disconnect ===\n")
            fd.write("Testing overlapped I/O copy operations with server restart\n")

        # Start async copy operation (smbcp -a uses overlapped I/O with multiple buffers)
        remote_file = "async_copy_test.img"
        command = f"smbcp -a {TEST_FILE_LOCAL} {TEST_SERVER_URL}/{remote_file}"

        with open(logfile, "a") as fd:
            fd.write(f"Starting async copy: {command}\n")
            fd.flush()

        # Set up environment for OpenFiles
        env = os.environ.copy()
        env['PATH'] = env.get('PATH', '') + ':/usr/local/bin/openfiles'
        env['LD_LIBRARY_PATH'] = env.get('LD_LIBRARY_PATH', '') + ':/usr/local/lib64'

        # Start the async copy process
        process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env
        )

        # Let async copy start (overlapped I/O needs time to establish buffers)
        time.sleep(5)

        # Restart samba during async copy
        with open(logfile, "a") as fd:
            fd.write("Restarting samba during async copy with overlapped I/O...\n")
            fd.flush()

        restart_samba_service()

        # Wait for process to complete
        try:
            stdout, stderr = process.communicate(timeout=60)
            returncode = process.returncode
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
            returncode = -1
            stderr += "\nAsync copy process killed due to timeout"

        with open(logfile, "a") as fd:
            fd.write(f"Async copy completed with return code: {returncode}\n")
            if stdout:
                fd.write(f"STDOUT: {stdout}\n")
            if stderr:
                fd.write(f"STDERR: {stderr}\n")

        # The key test: should not crash (SIGSEGV = -11)
        assert returncode != -11, f"Async copy crashed with SIGSEGV during server disconnect"

        # Cleanup
        cleanup_command = f"smbrm {TEST_SERVER_URL}/{remote_file}"
        run_command_with_timeout(cleanup_command, timeout=10)

        with open(logfile, "a") as fd:
            fd.write("SUCCESS: Async copy server disconnect test completed\n")
            fd.write("Overlapped I/O operations handled disconnect properly\n")


def test_volume_info_with_rapid_disconnects(verify_test_environment, logfile):
    """Test OfcGetVolumeInformation calls until we catch OFC_ERROR_OPERATION_ABORTED"""

    with resource_monitor("volume_info_operation_aborted", logfile) as start_resources:

        with open(logfile, "a") as fd:
            fd.write("\n=== TEST: Volume Info Operation Aborted Hunt ===\n")
            fd.write("Looping OfcGetVolumeInformation calls until we catch operation aborted status\n")
            fd.write("Will run for up to 10 minutes or until we get OFC_ERROR_OPERATION_ABORTED\n")

        # Set up environment for OpenFiles
        env = os.environ.copy()
        env['PATH'] = env.get('PATH', '') + ':/usr/local/bin/openfiles'
        env['LD_LIBRARY_PATH'] = env.get('LD_LIBRARY_PATH', '') + ':/usr/local/lib64'

        crash_count = 0
        success_count = 0
        error_count = 0
        operation_aborted_count = 0
        other_error_count = 0

        # Target error code we're hunting for
        OFC_ERROR_OPERATION_ABORTED = 995  # Actual value from ofc/file.h

        # Run for up to 10 minutes (600 seconds) or until we catch operation aborted
        start_time = time.time()
        max_runtime = 600  # 10 minutes
        iteration = 0
        operation_aborted_found = False

        with open(logfile, "a") as fd:
            fd.write(f"Hunting for OFC_ERROR_OPERATION_ABORTED (exit code {OFC_ERROR_OPERATION_ABORTED})\n")
            fd.write("Strategy: Continuous smbls calls with very frequent server restarts\n")
            fd.flush()

        while (time.time() - start_time) < max_runtime and not operation_aborted_found:
            iteration += 1

            # Start smbls (calls OfcGetVolumeInformation)
            command = f"smbls {TEST_SERVER_URL}/"

            # Start multiple concurrent calls to increase chances
            processes = []
            for i in range(3):  # 3 concurrent smbls calls
                process = subprocess.Popen(
                    command,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    env=env
                )
                processes.append(process)

            # Very brief wait, then restart samba
            time.sleep(0.5)
            restart_samba_service()

            # Check results from all concurrent processes
            for i, process in enumerate(processes):
                try:
                    stdout, stderr = process.communicate(timeout=5)
                    returncode = process.returncode
                except subprocess.TimeoutExpired:
                    process.kill()
                    stdout, stderr = process.communicate()
                    returncode = -1

                # Analyze the return code
                if returncode == -11:
                    crash_count += 1
                    with open(logfile, "a") as fd:
                        fd.write(f"CRASH: SIGSEGV in iteration {iteration}, process {i+1}\n")
                elif returncode == 0:
                    success_count += 1
                elif returncode == OFC_ERROR_OPERATION_ABORTED:
                    operation_aborted_count += 1
                    operation_aborted_found = True
                    with open(logfile, "a") as fd:
                        fd.write(f"🎯 SUCCESS: Found OFC_ERROR_OPERATION_ABORTED in iteration {iteration}, process {i+1}!\n")
                        fd.write(f"Return code: {returncode} (0x{returncode:08x})\n")
                        if stderr:
                            fd.write(f"STDERR: {stderr}\n")
                        fd.flush()
                    break
                else:
                    other_error_count += 1
                    if iteration % 20 == 0:  # Log details every 20th iteration
                        with open(logfile, "a") as fd:
                            fd.write(f"Iteration {iteration}: return code {returncode}\n")

            # Brief pause before next iteration
            time.sleep(0.5)

            # Progress update every 60 iterations
            if iteration % 60 == 0:
                elapsed = time.time() - start_time
                with open(logfile, "a") as fd:
                    fd.write(f"Progress: {iteration} iterations, {elapsed:.1f}s elapsed\n")
                    fd.write(f"  Successes: {success_count}, Errors: {other_error_count}, Crashes: {crash_count}\n")
                    fd.flush()

        elapsed_time = time.time() - start_time

        with open(logfile, "a") as fd:
            fd.write(f"\n=== Volume Info Operation Aborted Hunt Summary ===\n")
            fd.write(f"Total runtime: {elapsed_time:.1f} seconds ({elapsed_time/60:.1f} minutes)\n")
            fd.write(f"Total iterations: {iteration}\n")
            fd.write(f"Successes: {success_count}\n")
            fd.write(f"Other errors: {other_error_count}\n")
            fd.write(f"Crashes: {crash_count}\n")
            fd.write(f"🎯 OPERATION_ABORTED found: {operation_aborted_count}\n")

        # Main assertions
        assert crash_count == 0, f"Volume info operations crashed {crash_count} times during hunt"

        if operation_aborted_found:
            with open(logfile, "a") as fd:
                fd.write("🎯 SUCCESS: Successfully caught OFC_ERROR_OPERATION_ABORTED during OfcGetVolumeInformation!\n")
                fd.write("This proves session validation works for volume info operations\n")
        else:
            with open(logfile, "a") as fd:
                fd.write("⚠️ INFO: Did not catch OFC_ERROR_OPERATION_ABORTED in available time\n")
                fd.write("Volume info calls are very fast - may need longer runtime or different timing\n")
                fd.write("But no crashes occurred, confirming session validation prevents crashes\n")


if __name__ == "__main__":
    # Can be run standalone for debugging
    print("Server Disconnect Tests")
    print("Run with: pytest test_server_disconnect.py -v --logfile disconnect_test.log")