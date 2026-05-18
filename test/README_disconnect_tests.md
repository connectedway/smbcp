# Server Disconnect Race Condition Tests

This test suite validates the session validation and cleanup fixes implemented in commits **e7cc519** and **2a5f2df** for the OpenFiles SMB client stack.

## Overview

These tests are designed to reproduce and validate fixes for race conditions that occur when API operations access session structures after the real-time layer has cleaned them up due to server disconnects.

### Key Test Areas

1. **Basic Operations With Restart** - Validates graceful error handling
2. **Concurrent Operations** - Multi-threaded stress testing with periodic disconnects  
3. **Large File Transfers** - Tests session cleanup during active transfers
4. **Rapid Reconnects** - Session validation under rapid connect/disconnect cycles
5. **Memory Leak Detection** - Resource cleanup verification
6. **Idle Timeout Handling** - Session validation during idle timeout scenarios
7. **Idle + Server Restart** - Ultimate stress test combining idle timeout with disconnects
8. **Automated Memory Validation** - **NEW**: Automatic OpenFiles heap analysis and leak detection

## Prerequisites

- Samba server running locally (`systemctl start smb`)
- Test file: `~/Downloads/install.img` (~1GB file)
- sudo access for restarting samba service
- Python packages: `pytest`, `psutil`

## Quick Start

```bash
# Navigate to test directory
cd /home/vnc/git/openfiles-5.3/smbcp/test/

# Run basic connectivity test
./run_disconnect_tests.sh --quick

# Run full test suite (takes 10-15 minutes)
./run_disconnect_tests.sh
```

## Test Options

| Option | Description | Duration | Use Case |
|--------|-------------|----------|----------|
| `--quick` | Basic operations only | ~1 min | Quick validation after code changes |
| `--memory` | Memory leak detection | ~3 min | Resource cleanup verification |
| `--stress` | Concurrent operations | ~5 min | Multi-threaded stress testing |
| `--idle` | Idle timeout tests | ~5 min | Session validation during timeouts |
| (default) | Full test suite | ~20 min | Comprehensive validation |

## Test Configuration

- **Target Server**: `//vnc:happy@192.168.1.60/foobar`
- **Test File**: `~/Downloads/install.img`
- **Concurrent Threads**: 2 (copy operations + list operations)
- **Disconnect Intervals**: 1s, 3s, 5s (parameterized)

## Expected Results

### Success Criteria
- ✅ **Zero crashes** (no SIGSEGV/-11 return codes)
- ✅ **Proper error codes** for operations on dead sessions  
- ✅ **Resource cleanup** (no significant memory/FD leaks)
- ✅ **Session validation** prevents use-after-free scenarios

### Error Codes
- `0` - Success
- `>0` - Expected error (connection lost, file not found, etc.)
- `-11` - **CRASH (SIGSEGV)** - This indicates the race condition bug!
- `-1` - Timeout (may indicate hang due to improper cleanup)

## Log Analysis

Test logs are written to `./test_logs/disconnect_test_TIMESTAMP.log`

### Key Log Sections
```
=== RESOURCE MONITOR START ===
# Before/after resource usage tracking

Command: smbcp /home/vnc/Downloads/install.img //vnc:happy@...
Return code: 0
# Individual command results with timing

WARNING: Large memory change detected!
WARNING: Possible file descriptor leak!
# Resource leak detection

crashes detected: 0
# Summary of any crashes found
```

## Manual Validation

You can also run individual test scenarios manually:

```bash
# Terminal 1: Start a long file copy
smbcp ~/Downloads/install.img //vnc:happy@192.168.1.60/foobar/test.img

# Terminal 2: While copy is running, restart samba
sudo systemctl restart smb

# Check Terminal 1: Should show proper error, not crash
```

### SMB Idle Timeout Testing

The `smbidle` utility was created specifically for testing idle timeout scenarios:

```bash
# Test 3-minute idle timeout
smbidle //vnc:happy@192.168.1.60/foobar/idle_test.dat 180 1024

# Usage: smbidle <file_url> <idle_seconds> [write_size]
# - Opens file, writes initial data
# - Idles for specified duration  
# - Attempts post-idle operation
# - Tests session validation under timeout conditions
```

## Debugging Failed Tests

### If crashes are detected:
1. Check the exact command that crashed in the log
2. Try to reproduce manually with that command
3. Run under `gdb` or `valgrind` for more details
4. Check if the session validation code is being called

### If memory leaks are detected:
1. Look for "WARNING" messages in resource monitoring sections
2. Check if the leak is consistent across multiple test runs
3. Use `valgrind --leak-check=full` on the failing scenario

### If tests hang:
1. Check if samba service restarted properly (`systemctl status smb`)
2. Look for timeout messages in the log  
3. May indicate improper session cleanup or deadlocks

## Integration with CI/CD

To integrate these tests into automated testing:

```bash
# Exit code 0 = all tests passed
./run_disconnect_tests.sh --quick
if [ $? -eq 0 ]; then
    echo "Race condition tests PASSED"
else
    echo "Race condition tests FAILED - check logs"
    exit 1
fi
```

## Test Development

The test framework can be extended for additional scenarios:

- **Network simulation**: Use `iptables`/`tc` for packet loss simulation
- **Direct API testing**: Python C bindings for direct OpenFiles API calls
- **Different file sizes**: Vary transfer sizes to hit different timing windows
- **Multiple servers**: Test session isolation across different SMB servers

See `test_server_disconnect.py` for implementation details and `server-disconnect.tests` for the full testing strategy documentation.