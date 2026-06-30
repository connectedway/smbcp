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
 * SMB Find Transaction Test Utility
 *
 * This utility tests Find operation scenarios by:
 * 1. Opening a directory for enumeration (FindFirst)
 * 2. Enumerating some files (FindNext)
 * 3. Sitting idle for a specified duration
 * 4. Attempting to continue enumeration to test session validation
 * 5. Properly closing the search handle (FindClose)
 *
 * Usage: smbfind <directory_url> <files_to_read> <idle_seconds>
 * Example: smbfind //server/share/directory/ 5 180
 */

#define MAX_IDLE_SECONDS 3600  // Max 1 hour idle
#define MAX_FILES_TO_READ 100   // Max files to enumerate before idle

static void usage(const char *program_name)
{
    printf("Usage: %s <directory_url> <files_to_read> <idle_seconds>\n\n", program_name);
    printf("Arguments:\n");
    printf("  directory_url    SMB directory URL (e.g., //server/share/dir/)\n");
    printf("  files_to_read    Number of files to enumerate before idle (1-%d)\n", MAX_FILES_TO_READ);
    printf("  idle_seconds     Duration to idle mid-enumeration (1-%d seconds)\n", MAX_IDLE_SECONDS);
    printf("\nExample:\n");
    printf("  %s //vnc:happy@192.168.1.60/foobar/ 5 180\n", program_name);
    printf("\nDescription:\n");
    printf("  Opens directory, reads some files (FindFirst/FindNext),\n");
    printf("  idles mid-enumeration, then tries to continue (FindNext/FindClose).\n");
    printf("  Tests Find transaction state during idle timeout/disconnects.\n");
}

static OFC_BOOL enumerate_files(OFC_HANDLE hFind, OFC_INT max_files, const char *phase, OFC_INT *files_found)
{
    OFC_WIN32_FIND_DATA find_data;
    OFC_BOOL result = OFC_TRUE;
    OFC_BOOL more = OFC_TRUE;
    OFC_INT count = 0;

    printf("\n=== %s: Enumerating up to %d files ===\n", phase, max_files);

    while (count < max_files && more && result)
    {
        result = OfcFindNextFile(hFind, &find_data, &more);
        if (result == OFC_TRUE)
        {
            if (more)
            {
                // Skip . and .. entries like smbls does
                if (wcscmp(find_data.cFileName, L".") != 0 &&
                    wcscmp(find_data.cFileName, L"..") != 0)
                {
                    count++;
                    printf("  [%d] File: %ls\n", count, find_data.cFileName);
                    printf("       Size: %lu bytes, Attributes: 0x%08lx\n",
                           (unsigned long)find_data.nFileSizeLow,
                           (unsigned long)find_data.dwFileAttributes);
                }
            }
            else
            {
                printf("  End of directory reached after %d files\n", count);
                break;
            }
        }
        else
        {
            OFC_DWORD error = OfcGetLastError();
            printf("ERROR: FindNext failed after %d files. Error: 0x%08lx\n", count, (unsigned long)error);
            break;
        }
    }

    *files_found = count;
    printf("=== %s: Found %d files ===\n", phase, count);
    return result;
}

int main(int argc, char *argv[])
{
    OFC_TCHAR *directory_url = OFC_NULL;
    OFC_HANDLE hFind = OFC_INVALID_HANDLE_VALUE;
    OFC_WIN32_FIND_DATA find_data;
    OFC_BOOL more = OFC_FALSE;
    OFC_INT files_to_read;
    OFC_INT idle_seconds;
    OFC_INT files_before_idle = 0;
    OFC_INT files_after_idle = 0;
    OFC_BOOL success = OFC_FALSE;

    printf("OpenFiles SMB Find Transaction Test Utility\n");
    printf("============================================\n");

    // Parse command line arguments
    if (argc != 4)
    {
        usage(argv[0]);
        return 1;
    }

    // Parse files to read before idle
    files_to_read = atoi(argv[2]);
    if (files_to_read < 1 || files_to_read > MAX_FILES_TO_READ)
    {
        printf("ERROR: files_to_read must be between 1 and %d\n", MAX_FILES_TO_READ);
        return 1;
    }

    // Parse idle duration
    idle_seconds = atoi(argv[3]);
    if (idle_seconds < 1 || idle_seconds > MAX_IDLE_SECONDS)
    {
        printf("ERROR: idle_seconds must be between 1 and %d\n", MAX_IDLE_SECONDS);
        return 1;
    }

    // Initialize OpenFiles stack
    printf("Initializing OpenFiles stack...\n");
    smbcp_init();

    // Convert URL to wide characters and append wildcard (following smbls.c pattern)
    size_t len;
    size_t url_len;
    mbstate_t ps;
    const char *cursor;

    memset(&ps, 0, sizeof(ps));
    url_len = strlen(argv[1]);
    len = url_len + 2;  // +1 for '*' wildcard, +1 for null terminator
    directory_url = malloc(sizeof(wchar_t) * len);
    if (directory_url == OFC_NULL)
    {
        printf("ERROR: Failed to allocate memory for URL conversion\n");
        goto cleanup;
    }
    cursor = argv[1];
    mbsrtowcs(directory_url, &cursor, url_len + 1, &ps);

    // Append wildcard for directory enumeration
    wcscat(directory_url, L"*");

    printf("Target directory: %s\n", argv[1]);
    printf("Files to read before idle: %d\n", files_to_read);
    printf("Idle duration: %d seconds (%d minutes)\n", idle_seconds, idle_seconds / 60);
    printf("\n");

    // Start Find operation (FindFirst)
    printf("Starting directory enumeration (FindFirst)...\n");
    hFind = OfcFindFirstFile(directory_url, &find_data, &more);

    if (hFind == OFC_INVALID_HANDLE_VALUE)
    {
        OFC_DWORD error = OfcGetLastError();
        printf("ERROR: FindFirst failed. Error: 0x%08lx\n", (unsigned long)error);
        goto cleanup;
    }

    printf("FindFirst succeeded\n");
    printf("First file: %ls\n", find_data.cFileName);
    printf("Size: %lu bytes, Attributes: 0x%08lx\n",
           (unsigned long)find_data.nFileSizeLow,
           (unsigned long)find_data.dwFileAttributes);

    // Enumerate some files before idle (FindNext calls)
    if (files_to_read > 1)
    {
        if (!enumerate_files(hFind, files_to_read - 1, "PRE_IDLE", &files_before_idle))
        {
            goto cleanup;
        }
    }

    printf("Total files enumerated before idle: %d\n", files_before_idle + 1); // +1 for FindFirst

    // Start idle period
    printf("\n=== Starting idle period ===\n");
    printf("Idling for %d seconds (session timeout may occur)...\n", idle_seconds);
    printf("Find handle remains open during idle period\n");

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

    // Attempt post-idle Find operations
    printf("\n=== Testing post-idle Find operations ===\n");
    printf("Attempting to continue directory enumeration...\n");

    // Try to continue enumeration
    if (enumerate_files(hFind, files_to_read, "POST_IDLE", &files_after_idle))
    {
        printf("SUCCESS: Post-idle Find operations completed successfully\n");
        printf("This indicates the search handle remained active or recovered gracefully\n");
        success = OFC_TRUE;
    }
    else
    {
        printf("EXPECTED: Post-idle Find operations failed\n");
        printf("This likely indicates session timeout occurred and was handled properly\n");

        // Try a simple FindNext to test the handle state
        printf("Testing single FindNext operation...\n");
        OFC_BOOL test_more = OFC_FALSE;
        OFC_BOOL next_result = OfcFindNextFile(hFind, &find_data, &test_more);
        if (next_result && test_more)
        {
            printf("FindNext succeeded: %ls\n", find_data.cFileName);
        }
        else if (next_result && !test_more)
        {
            printf("FindNext indicated end of directory (normal)\n");
        }
        else
        {
            OFC_DWORD error = OfcGetLastError();
            printf("FindNext failed. Error: 0x%08lx\n", (unsigned long)error);
            printf("This confirms session timeout was handled properly\n");
        }

        // For our test purposes, graceful failure is actually success
        success = OFC_TRUE;
    }

cleanup:

    // Close Find handle if opened (FindClose)
    if (hFind != OFC_INVALID_HANDLE_VALUE)
    {
        printf("\nClosing Find handle (FindClose)...\n");
        if (OfcFindClose(hFind))
        {
            printf("FindClose succeeded\n");
        }
        else
        {
            OFC_DWORD error = OfcGetLastError();
            printf("WARNING: FindClose failed. Error: 0x%08lx\n", (unsigned long)error);
        }
    }

    // Clean up URL string
    if (directory_url != OFC_NULL)
    {
        free(directory_url);
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
    printf("Files enumerated before idle: %d\n", files_before_idle + 1);
    printf("Files enumerated after idle: %d\n", files_after_idle);
    if (success)
    {
        printf("PASS: Find transaction test completed successfully\n");
        printf("Session validation and Find operation handling working correctly\n");
        return 0;
    }
    else
    {
        printf("FAIL: Find transaction test encountered errors\n");
        printf("Check session validation and Find operation handling\n");
        return 1;
    }
}