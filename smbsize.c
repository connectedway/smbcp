/* Copyright (c) 2021 Connected Way, LLC. All rights reserved.
 * Use of this source code is unrestricted
 */

#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <wchar.h>
#include <unistd.h>

#include <ofc/config.h>
#include <ofc/handle.h>
#include <ofc/types.h>
#include <ofc/file.h>

#include "smbinit.h"
/**
 * \{
 */

static OFC_DWORD getsizebyhandle(OFC_CTCHAR *wfilename)
{
  OFC_DWORD dwLastError;
  OFC_HANDLE write_file;
  OFC_BOOL ret;

  dwLastError = OFC_ERROR_SUCCESS;

  write_file = OFC_HANDLE_NULL;
  /*
   * Open up our write file.  If it exists, it will be deleted
   */
  write_file = OfcCreateFile(wfilename,
			     OFC_GENERIC_READ,
			     0,
			     OFC_NULL,
			     OFC_OPEN_EXISTING,
			     OFC_FILE_ATTRIBUTE_NORMAL,
			     OFC_HANDLE_NULL);

  if (write_file == OFC_INVALID_HANDLE_VALUE)
    {
      dwLastError = OfcGetLastError();
    }
  else
    {
      OFC_FILE_STANDARD_INFO info;
      ret = OfcGetFileInformationByHandleEx(write_file,
					    OfcFileStandardInfo,
					    &info,
					    sizeof(OFC_FILE_STANDARD_INFO));
      if (ret != OFC_TRUE)
	{
	  dwLastError = OfcGetLastError();
	}
      else
	{
	  printf("Size Info of %S by Handle:\n", wfilename);
	  printf("  Allocation Size: %lld bytes\n", info.AllocationSize);
	  printf("  End of File: %lld\n", info.EndOfFile);
	}
      OfcCloseHandle(write_file);
    }

  return (dwLastError);
}

static OFC_DWORD getsize(OFC_CTCHAR *wfilename)
{
  OFC_DWORD dwLastError;
  OFC_BOOL ret;

  dwLastError = OFC_ERROR_SUCCESS;

  OFC_WIN32_FILE_ATTRIBUTE_DATA info;
  ret = OfcGetFileAttributesEx(wfilename,
			       OfcGetFileExInfoStandard,
			       &info);
  if (ret != OFC_TRUE)
    {
      dwLastError = OfcGetLastError();
    }
  else
    {
      OFC_UINT64 file_size;
      OFC_LARGE_INTEGER_SET(file_size, info.nFileSizeLow, info.nFileSizeHigh);
      printf("Size Info of %S by Name:\n", wfilename);
      printf("  File Size %llu\n", file_size);
    }

  return (dwLastError);
}

int main (int argc, char **argp)
{
  OFC_TCHAR *wfilename;
  OFC_DWORD ret;
  size_t len;
  mbstate_t ps;
  const char *cursor;

  smbcp_init();
  
  if (argc < 2)
    {
      printf ("Usage: smbsize <destination>\n");
      exit (1);
    }

  memset(&ps, 0, sizeof(ps));
  len = strlen(argp[1]) + 1;
  wfilename = malloc(sizeof(wchar_t) * len);
  cursor = argp[1];
  mbsrtowcs(wfilename, &cursor, len, &ps);

  printf("Size of %s: ", argp[1]);
  fflush(stdout);

  ret = getsizebyhandle(wfilename);
  if (ret == OFC_ERROR_SUCCESS)
    {
      ret = getsize(wfilename);
    }
  
  free(wfilename);

  int status;
  if (ret == OFC_ERROR_SUCCESS)
    {
      printf("[ok]\n");
      status = 0;
    }
  else
    {
      printf("[failed]\n");
      printf("%s\n", ofc_get_error_string(ret));
      status = 1;
    }

  /*
   * Deactivate the openfiles stack
   */
  printf("Deactivating Stack\n");
  smbcp_deactivate();

  exit(status);
}

