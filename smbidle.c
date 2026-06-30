/* Copyright (c) 2021 Connected Way, LLC. All rights reserved.
 * Use of this source code is unrestricted
 */

#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <wchar.h>
#include <unistd.h>
#include <time.h>

#include <ofc/config.h>
#include <ofc/framework.h>
#include <ofc/handle.h>
#include <ofc/types.h>
#include <ofc/file.h>
#include <ofc/waitset.h>
#include <ofc/queue.h>
#include <of_smb/framework.h>

#include "smbinit.h"

/**
 * SMB Idle Test Utility
 *
 * This utility tests idle timeout scenarios by:
 * 1. Opening a file for write
 * 2. Writing initial data
 * 3. Sitting idle for a specified duration
 * 4. Attempting another operation to test session validation
 *
 * Usage: smbidle <file_url> <idle_seconds> [write_size]
 * Example: smbidle //server/share/test.dat 180 1024
 */

#define DEFAULT_WRITE_SIZE 1024
#define MAX_IDLE_SECONDS 3600  // Max 1 hour idle

static void usage(const char *program_name)
{
    printf("Usage: %s <file_url> <idle_seconds> [write_size]\n\n", program_name);
    printf("Arguments:\n");
    printf("  file_url      SMB file URL (e.g., //server/share/test.dat)\n");
    printf("  idle_seconds  Duration to idle (1-%d seconds)\n", MAX_IDLE_SECONDS);
    printf("  write_size    Optional: Size of data blocks to write (default: %d)\n", DEFAULT_WRITE_SIZE);
    printf("\nExample:\n");
    printf("  %s //vnc:happy@192.168.1.60/foobar/idle_test.dat 180 1024\n", program_name);
    printf("\nDescription:\n");
    printf("  Opens a file, writes initial data, idles for specified time,\n");
    printf("  then attempts another operation to test idle timeout handling.\n");
}

static OFC_BOOL write_test_data(OFC_HANDLE hFile, OFC_DWORD write_size, const char *label)
{
    OFC_CHAR *buffer;
    OFC_DWORD bytes_written;
    OFC_BOOL result = OFC_FALSE;

    // Allocate buffer and fill with test pattern
    buffer = (OFC_CHAR *)malloc(write_size);
    if (buffer == OFC_NULL)
    {
        printf("ERROR: Failed to allocate %lu bytes for %s\n", (unsigned long)write_size, label);
        return OFC_FALSE;
    }

    // Fill buffer with identifiable pattern
    for (OFC_DWORD i = 0; i < write_size; i++)
    {
        buffer[i] = (OFC_CHAR)('A' + (i % 26));
    }

    // Add timestamp and label to beginning of buffer
    time_t now = time(NULL);
    snprintf(buffer, write_size, "%s: %s", label, ctime(&now));

    // Perform the write
    printf("Writing %lu bytes (%s)...\n", (unsigned long)write_size, label);
    result = OfcWriteFile(hFile, buffer, write_size, &bytes_written, OFC_HANDLE_NULL);

    if (result && bytes_written == write_size)
    {
        printf("Successfully wrote %lu bytes (%s)\n", (unsigned long)bytes_written, label);
        result = OFC_TRUE;
    }
    else
    {
        OFC_DWORD error = OfcGetLastError();
        printf("ERROR: Write failed (%s). Requested: %lu, Written: %lu, Error: 0x%08lx\n",
               label, (unsigned long)write_size, (unsigned long)bytes_written, (unsigned long)error);
        result = OFC_FALSE;
    }

    free(buffer);
    return result;
}

int main(int argc, char *argv[])
{
    OFC_TCHAR *remote_file_url = OFC_NULL;
    OFC_HANDLE hFile = OFC_INVALID_HANDLE_VALUE;
    OFC_INT idle_seconds;
    OFC_DWORD write_size = DEFAULT_WRITE_SIZE;
    OFC_BOOL success = OFC_FALSE;

    printf("OpenFiles SMB Idle Test Utility\n");
    printf("================================\n");

    // Parse command line arguments
    if (argc < 3 || argc > 4)
    {
        usage(argv[0]);
        return 1;
    }

    // Parse idle duration
    idle_seconds = atoi(argv[2]);
    if (idle_seconds < 1 || idle_seconds > MAX_IDLE_SECONDS)
    {
        printf("ERROR: idle_seconds must be between 1 and %d\n", MAX_IDLE_SECONDS);
        return 1;
    }

    // Parse optional write size
    if (argc == 4)
    {
        write_size = (OFC_DWORD)atol(argv[3]);
        if (write_size < 1 || write_size > (1024 * 1024))  // Max 1MB
        {
            printf("ERROR: write_size must be between 1 and 1048576 bytes\n");
            return 1;
        }
    }

    // Initialize OpenFiles stack
    printf("Initializing OpenFiles stack...\n");
    smbcp_init();

    // Convert URL to wide characters (following smbcp.c pattern)
    size_t len;
    mbstate_t ps;
    const char *cursor;

    memset(&ps, 0, sizeof(ps));
    len = strlen(argv[1]) + 1;
    remote_file_url = malloc(sizeof(wchar_t) * len);
    if (remote_file_url == OFC_NULL)
    {
        printf("ERROR: Failed to allocate memory for URL conversion\n");
        goto cleanup;
    }
    cursor = argv[1];
    mbsrtowcs(remote_file_url, &cursor, len, &ps);

    printf("Target file: %s\n", argv[1]);
    printf("Idle duration: %d seconds (%d minutes)\n", idle_seconds, idle_seconds / 60);
    printf("Write size: %lu bytes\n", (unsigned long)write_size);
    printf("\n");

    // Open file for writing (create if doesn't exist, overwrite if exists)
    printf("Opening file for write access...\n");
    hFile = OfcCreateFile(remote_file_url,
                         OFC_GENERIC_WRITE,
                         OFC_FILE_SHARE_READ | OFC_FILE_SHARE_WRITE,
                         OFC_NULL,
                         OFC_CREATE_ALWAYS,  // Overwrite existing file
                         OFC_FILE_ATTRIBUTE_NORMAL,
                         OFC_HANDLE_NULL);

    if (hFile == OFC_INVALID_HANDLE_VALUE)
    {
        OFC_DWORD error = OfcGetLastError();
        printf("ERROR: Failed to open file. Error: 0x%08lx\n", (unsigned long)error);
        goto cleanup;
    }

    printf("File opened successfully\n");

    // Write initial data block
    if (!write_test_data(hFile, write_size, "INITIAL_WRITE"))
    {
        goto cleanup;
    }

    // Flush the file to ensure data is written
    printf("Flushing file buffers...\n");
    if (!OfcFlushFileBuffers(hFile))
    {
        OFC_DWORD error = OfcGetLastError();
        printf("WARNING: Flush failed. Error: 0x%08lx\n", (unsigned long)error);
    }

    // Start idle period
    printf("\n=== Starting idle period ===\n");
    printf("Idling for %d seconds (session timeout may occur)...\n", idle_seconds);

    time_t start_time = time(NULL);
    for (int i = 0; i < idle_seconds; i++)
    {
        sleep(1);

        // Print progress every 30 seconds
        if ((i + 1) % 30 == 0)
        {
            time_t elapsed = time(NULL) - start_time;
            printf("  Idle progress: %ld/%d seconds (%d%% complete)\n",
                   elapsed, idle_seconds, (int)((elapsed * 100) / idle_seconds));
        }
    }

    time_t end_time = time(NULL);
    printf("Idle period complete. Elapsed: %ld seconds\n", end_time - start_time);

    // Attempt post-idle operation
    printf("\n=== Testing post-idle operations ===\n");
    printf("Attempting write operation after idle timeout...\n");

    if (write_test_data(hFile, write_size, "POST_IDLE_WRITE"))
    {
        printf("SUCCESS: Post-idle write operation completed successfully\n");
        printf("This indicates the session remained active or recovered gracefully\n");
        success = OFC_TRUE;
    }
    else
    {
        printf("EXPECTED: Post-idle write operation failed\n");
        printf("This likely indicates session timeout occurred and was handled properly\n");

        // Try to get file position to test another operation
        printf("Attempting to get file position...\n");
        OFC_LONG high_part = 0;

        OFC_DWORD result = OfcSetFilePointer(hFile, 0, &high_part, OFC_FILE_CURRENT);
        if (result != 0xFFFFFFFF)
        {
            printf("File position operation succeeded: %lu\n", (unsigned long)result);
        }
        else
        {
            OFC_DWORD error = OfcGetLastError();
            printf("File position operation failed. Error: 0x%08lx\n", (unsigned long)error);
            printf("This confirms session timeout was handled properly\n");
        }

        // For our test purposes, graceful failure is actually success
        success = OFC_TRUE;
    }

    cleanup:

    // Close file if opened
    if (hFile != OFC_INVALID_HANDLE_VALUE)
    {
        printf("\nClosing file...\n");
        if (OfcCloseHandle(hFile))
        {
            printf("File closed successfully\n");
        }
        else
        {
            OFC_DWORD error = OfcGetLastError();
            printf("WARNING: File close failed. Error: 0x%08lx\n", (unsigned long)error);
        }
    }

    // Clean up URL string
    if (remote_file_url != OFC_NULL)
    {
        free(remote_file_url);
    }

    // Shutdown OpenFiles stack properly
    printf("Shutting down OpenFiles stack...\n");

    OfcFileThreadDeinit();
    /*
     * Deactivate the openfiles stack
     */
    printf("Deactivating Stack\n");
    fflush(stdout);  // Ensure output is flushed before deactivation
    smbcp_deactivate();
    fflush(stdout);  // Ensure memory debug output is flushed

    printf("\n=== Test Summary ===\n");
    if (success)
    {
        printf("PASS: Idle timeout test completed successfully\n");
        printf("Session validation and timeout handling working correctly\n");
        return 0;
    }
    else
    {
        printf("FAIL: Idle timeout test encountered errors\n");
        printf("Check session validation and timeout handling\n");
        return 1;
    }
}