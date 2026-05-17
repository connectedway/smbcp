#!/bin/bash

# Server Disconnect Test Runner
# This script runs the server disconnect race condition tests

set -e

echo "OpenFiles Server Disconnect Race Condition Tests"
echo "================================================="

# Set up OpenFiles environment
export PATH="$PATH:/usr/local/bin/openfiles"
export LD_LIBRARY_PATH="$LD_LIBRARY_PATH:/usr/local/lib64"

# Check prerequisites
echo "Checking prerequisites..."

# Check if samba is running
if ! systemctl is-active --quiet smb; then
    echo "ERROR: Samba service is not running. Start it with: sudo systemctl start smb"
    exit 1
fi

# Check if test file exists
TEST_FILE="$HOME/Downloads/install.img"
if [ ! -f "$TEST_FILE" ]; then
    echo "ERROR: Test file $TEST_FILE not found"
    echo "Please ensure the test file exists or modify TEST_FILE_LOCAL in the test"
    exit 1
fi

# Check if we can run sudo (needed for systemctl restart smb)
if ! sudo -n true 2>/dev/null; then
    echo "WARNING: sudo access required for restarting samba service"
    echo "You may be prompted for your password during tests"
fi

# Create log directory
LOG_DIR="./test_logs"
mkdir -p "$LOG_DIR"

# Set log file with timestamp
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="$LOG_DIR/disconnect_test_$TIMESTAMP.log"

echo "Prerequisites check complete."
echo "Log file: $LOG_FILE"
echo ""

# Test execution options
if [ "$1" = "--quick" ]; then
    echo "Running quick test suite..."
    pytest test_server_disconnect.py::test_basic_operations_with_restart \
           --logfile="$LOG_FILE" \
           -v -s
elif [ "$1" = "--memory" ]; then
    echo "Running memory leak tests..."
    pytest test_server_disconnect.py::test_memory_leak_detection \
           --logfile="$LOG_FILE" \
           -v -s
elif [ "$1" = "--stress" ]; then
    echo "Running stress tests (this may take several minutes)..."
    pytest test_server_disconnect.py::test_concurrent_operations_with_periodic_restart \
           --logfile="$LOG_FILE" \
           -v -s
elif [ "$1" = "--idle" ]; then
    echo "Running idle timeout tests (this may take 5+ minutes)..."
    pytest test_server_disconnect.py::test_idle_timeout_handling \
           test_server_disconnect.py::test_idle_timeout_with_server_restart \
           --logfile="$LOG_FILE" \
           -v -s
else
    echo "Running full test suite..."
    echo "This will take 10-15 minutes and will restart samba multiple times"
    echo "Press Ctrl+C within 5 seconds to cancel..."
    sleep 5

    pytest test_server_disconnect.py \
           --logfile="$LOG_FILE" \
           -v -s
fi

echo ""
echo "Test execution complete!"
echo "Check log file for detailed results: $LOG_FILE"

# Quick summary from log
if [ -f "$LOG_FILE" ]; then
    echo ""
    echo "=== Quick Summary ==="
    echo "Crashes detected:"
    grep -c "crashes detected" "$LOG_FILE" 2>/dev/null || echo "0"

    echo "Memory warnings:"
    grep -c "WARNING.*memory" "$LOG_FILE" 2>/dev/null || echo "0"

    echo "Resource warnings:"
    grep -c "WARNING.*leak" "$LOG_FILE" 2>/dev/null || echo "0"
fi

echo ""
echo "Available test options:"
echo "  $0 --quick    # Run basic connectivity tests only"
echo "  $0 --memory   # Run memory leak detection only"
echo "  $0 --stress   # Run concurrent operation stress tests only"
echo "  $0 --idle     # Run idle timeout tests only (5+ minutes)"
echo "  $0            # Run full test suite (default)"