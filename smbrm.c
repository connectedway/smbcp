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

static OFC_DWORD rm(OFC_CTCHAR *wfilename)
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
			     OFC_GENERIC_WRITE | OFC_FILE_DELETE,
			     0,
			     OFC_NULL,
			     OFC_OPEN_EXISTING,
			     OFC_FILE_ATTRIBUTE_NORMAL | OFC_FILE_FLAG_DELETE_ON_CLOSE,
			     OFC_HANDLE_NULL);

  if (write_file == OFC_INVALID_HANDLE_VALUE)
    {
      dwLastError = OfcGetLastError();
    }
  else
    {
      OfcCloseHandle(write_file);
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
      printf ("Usage: smbrm <destination>\n");
      exit (1);
    }

  memset(&ps, 0, sizeof(ps));
  len = strlen(argp[1]) + 1;
  wfilename = malloc(sizeof(wchar_t) * len);
  cursor = argp[1];
  mbsrtowcs(wfilename, &cursor, len, &ps);

  printf("Removing %s: ", argp[1]);
  fflush(stdout);

  ret = rm(wfilename);
  
  free(wfilename);

  if (ret == OFC_ERROR_SUCCESS)
    {
      printf("[ok]\n");
      exit(0);
    }
  else
    {
      printf("[failed]\n");
      printf("%s\n", ofc_get_error_string(ret));
      exit(1);
    }
  return (0);
}

