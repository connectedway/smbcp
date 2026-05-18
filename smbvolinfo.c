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
 * SMB Volume Info Test Utility
 *
 * This utility tests volume info operations by:
 * 1. Calling OfcGetVolumeInformation successfully to establish connection
 * 2. Looping additional volume info calls for specified duration
 * 3. Testing session validation during volume info operations
 *
 * Usage: smbvolinfo <directory_url> <loop_seconds>
 * Example: smbvolinfo //server/share/directory/ 60
 */

#define MAX_LOOP_SECONDS 600  // Max 10 minutes

static void usage(const char *program_name)
{
    printf("Usage: %s <directory_url> <loop_seconds>\n\n", program_name);
    printf("Arguments:\n");
    printf("  directory_url    SMB directory URL (e.g., //server/share/dir/)\n");
    printf("  loop_seconds     Duration to loop volume info calls (1-%d seconds)\n", MAX_LOOP_SECONDS);
    printf("\nExample:\n");
    printf("  %s //vnc:happy@192.168.1.60/foobar/ 60\n", program_name);
    printf("\nDescription:\n");
    printf("  Calls OfcGetVolumeInformation once successfully, then loops additional\n");
    printf("  calls for specified time. Useful for testing session validation during\n");
    printf("  volume info operations with server disconnects.\n");
}

static OFC_BOOL get_volume_info(OFC_CTCHAR *directory_url, const char *phase, OFC_INT call_number)
{
    OFC_BOOL result;
    OFC_DWORD last_error;
    OFC_TCHAR volume_name[256];
    OFC_DWORD serial_number;
    OFC_DWORD max_component_length;
    OFC_DWORD file_system_flags;
    OFC_TCHAR file_system_name[256];

    printf("  [%s #%d] Calling OfcGetVolumeInformation...\n", phase, call_number);
    printf("Calling GetVolumeInfo with %ls\n", directory_url);

#if 1
    result = OfcGetVolumeInformation(directory_url,
                                     volume_name, sizeof(volume_name)/sizeof(OFC_TCHAR),
                                     &serial_number,
                                     &max_component_length,
                                     &file_system_flags,
                                     file_system_name, sizeof(file_system_name)/sizeof(OFC_TCHAR));
#else
    result = OfcGetVolumeInformation(directory_url,
				     OFC_NULL, 0,
				     OFC_NULL,
				     OFC_NULL,
				     OFC_NULL,
				     OFC_NULL, 0);
#endif
    if (result)
    {
        printf("  [%s #%d] SUCCESS: Volume info retrieved\n", phase, call_number);
#if 1
        printf("       Volume: %ls, Serial: 0x%08lx, FileSystem: %ls\n",
               volume_name, (unsigned long)serial_number, file_system_name);
#endif
        return OFC_TRUE;
    }
    else
    {
        last_error = OfcGetLastError();
        printf("  [%s #%d] FAILED: OfcGetVolumeInformation failed. Error: 0x%08lx\n",
               phase, call_number, (unsigned long)last_error);

        if (last_error == 995)  // OFC_ERROR_OPERATION_ABORTED
        {
            printf("  🎯 FOUND IT: OFC_ERROR_OPERATION_ABORTED (995)!\n");
        }

        return OFC_FALSE;
    }
}

int main(int argc, char *argv[])
{
    OFC_TCHAR *directory_url = OFC_NULL;
    OFC_INT loop_seconds;
    OFC_INT call_count = 0;
    OFC_INT success_count = 0;
    OFC_INT error_count = 0;
    OFC_INT operation_aborted_count = 0;
    OFC_BOOL success = OFC_FALSE;

    printf("OpenFiles SMB Volume Info Test Utility\n");
    printf("=======================================\n");

    // Parse command line arguments
    if (argc != 3)
    {
        usage(argv[0]);
        return 1;
    }

    // Parse loop duration
    loop_seconds = atoi(argv[2]);
    if (loop_seconds < 1 || loop_seconds > MAX_LOOP_SECONDS)
    {
        printf("ERROR: loop_seconds must be between 1 and %d\n", MAX_LOOP_SECONDS);
        return 1;
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
    directory_url = malloc(sizeof(wchar_t) * len);
    if (directory_url == OFC_NULL)
    {
        printf("ERROR: Failed to allocate memory for URL conversion\n");
        goto cleanup;
    }
    cursor = argv[1];
    mbsrtowcs(directory_url, &cursor, len, &ps);

    printf("Target directory: %s\n", argv[1]);
    printf("Loop duration: %d seconds (%d minutes)\n", loop_seconds, loop_seconds / 60);
    printf("\n");

    // Loop volume info calls for specified duration
    printf("=== Looping Volume Info Calls for %d seconds ===\n", loop_seconds);
    printf("External server restarts should begin after ~60 seconds\n");

    time_t start_time = time(NULL);
    time_t last_progress = start_time;

    while ((time(NULL) - start_time) < loop_seconds)
    {
        call_count++;

        if (get_volume_info(directory_url, "CALL", call_count))
        {
            success_count++;
        }
        else
        {
            error_count++;

            // Check for operation aborted specifically
            OFC_DWORD last_error = OfcGetLastError();
            if (last_error == 995)  // OFC_ERROR_OPERATION_ABORTED
            {
                operation_aborted_count++;
                printf("🎯 OPERATION ABORTED CAUGHT! Error 995 during volume info call #%d\n", call_count);
            }
        }

        // Progress update every 30 seconds
        time_t current_time = time(NULL);
        if ((current_time - last_progress) >= 30)
        {
            time_t elapsed = current_time - start_time;
            printf("\n--- Progress Update ---\n");
            printf("Elapsed: %ld/%d seconds (%d%% complete)\n",
                   elapsed, loop_seconds, (int)((elapsed * 100) / loop_seconds));
            printf("Calls: %d total, %d success, %d errors\n",
                   call_count, success_count, error_count);
            if (operation_aborted_count > 0)
            {
                printf("🎯 OPERATION_ABORTED caught: %d times!\n", operation_aborted_count);
            }
            printf("--- End Progress ---\n\n");
            last_progress = current_time;
        }

        // Brief pause between calls
        sleep(1);
    }

    time_t end_time = time(NULL);
    time_t elapsed_time = end_time - start_time;

    printf("\n=== Volume Info Loop Complete ===\n");
    printf("Total runtime: %ld seconds\n", elapsed_time);

    success = OFC_TRUE;

cleanup:

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
    printf("Total calls: %d\n", call_count);
    printf("Successful calls: %d\n", success_count);
    printf("Failed calls: %d\n", error_count);
    if (operation_aborted_count > 0)
    {
        printf("🎯 OPERATION_ABORTED caught: %d times\n", operation_aborted_count);
        printf("SUCCESS: Found OFC_ERROR_OPERATION_ABORTED during volume info operations!\n");
    }
    else
    {
        printf("No operation aborted errors caught (may need server restart during loop)\n");
    }

    if (success)
    {
        printf("PASS: Volume info test completed successfully\n");
        return 0;
    }
    else
    {
        printf("FAIL: Volume info test encountered errors\n");
        return 1;
    }
}
