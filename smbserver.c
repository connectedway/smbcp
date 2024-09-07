/* Copyright (c) 2021 Connected Way, LLC. All rights reserved.
 * Use of this source code is unrestricted
 */

#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <wchar.h>
#include <unistd.h>
#include <assert.h>
#include <errno.h>

#include <ofc/config.h>
#include <ofc/handle.h>
#include <ofc/types.h>
#include <ofc/net.h>
#include <ofc/process.h>
#include <of_smb/framework.h>

#include <ofc/file.h>
#define NO_RETURN
#include <ofc/thread.h>

#include "smbinit.h"

#define BUFFER_SIZE 80
OFC_HANDLE hiThread = OFC_HANDLE_NULL;
OFC_HANDLE hoThread = OFC_HANDLE_NULL;

static OFC_VOID term_handler(OFC_INT signal)
{
  printf("Terminating SMB Server\n");
  ofc_thread_delete(hiThread);
  ofc_thread_delete(hoThread);
}

static OFC_DWORD ichatApp(OFC_HANDLE hThread, OFC_VOID *context)
{
  OFC_HANDLE hFile ;
  OFC_CHAR buffer[BUFFER_SIZE];

  hFile = OfcCreateFileW (TSTR("IPC:/ichatsvc"),
                          OFC_GENERIC_READ | OFC_GENERIC_WRITE,
                          OFC_FILE_SHARE_READ,
                          OFC_NULL,
                          OFC_CREATE_ALWAYS,
                          OFC_FILE_ATTRIBUTE_NORMAL,
                          OFC_HANDLE_NULL) ;

  if ((hFile == OFC_HANDLE_NULL) ||
      (hFile == OFC_INVALID_HANDLE_VALUE))
    {
      printf ("Couldn't create ichatsvc file\n") ;
    }
  else
    {
      while (!ofc_thread_is_deleting(hThread))
        {
	  char *p;
          p = fgets(buffer, BUFFER_SIZE, stdin);
	  if (p == NULL)
	    {
	      ofc_thread_delete(hThread);
	    }
	  else if (strlen(buffer)==0)
	    {
	      ofc_thread_delete(hThread);
	    }
	  else if (OfcWriteFile(hFile, buffer, strlen(buffer),
				OFC_NULL, OFC_HANDLE_NULL) == OFC_FALSE)
	    {
	      printf("Couldn't write to ichatsvcfile %d\n", OfcGetLastError());
	      ofc_thread_delete(hThread);
	    }
	  else if (strncmp(buffer, "quit", 4) == 0)
	    {
	      printf("Exiting\n");
	      ofc_thread_delete(hiThread);
	      ofc_thread_delete(hoThread);
	    }
        }
      OfcCloseHandle(hFile);
    }
  return (0);
}
static OFC_DWORD ochatApp(OFC_HANDLE hThread, OFC_VOID *context)
{
  OFC_HANDLE hFile ;
  OFC_CHAR buffer[BUFFER_SIZE];

  hFile = OfcCreateFileW (TSTR("IPC:/ochatsvc"),
                          OFC_GENERIC_READ | OFC_GENERIC_WRITE,
                          OFC_FILE_SHARE_READ,
                          OFC_NULL,
                          OFC_CREATE_ALWAYS,
                          OFC_FILE_ATTRIBUTE_NORMAL,
                          OFC_HANDLE_NULL) ;

  if ((hFile == OFC_HANDLE_NULL) ||
      (hFile == OFC_INVALID_HANDLE_VALUE))
    {
      printf ("Couldn't create ochatsvc file\n") ;
    }
  else
    {
      while (!ofc_thread_is_deleting(hThread))
        {
          OFC_DWORD bytes_read;
          if (OfcReadFile(hFile, buffer, BUFFER_SIZE, &bytes_read, OFC_HANDLE_NULL) == OFC_FALSE)
	    {
	      printf("Couldn't read from ochatsvcfile %d\n", OfcGetLastError());
	      ofc_thread_delete(hThread);
	    }
          else
            printf("%.*s\n", bytes_read, buffer);
        }
      OfcCloseHandle(hFile);
    }
    return (0);
}

int main (int argc, char **argp)
{
  OFC_DWORD ret;

  smbcp_init();

#if defined(OF_SMB_SERVER)
  printf("Starting Server\n");

  OFC_HANDLE hApp = of_smb_startup_server(OFC_HANDLE_NULL);

  hiThread = ofc_thread_create(&ichatApp,
			       OFC_THREAD_THREAD_TEST, OFC_THREAD_SINGLETON,
			       OFC_NULL,
			       OFC_THREAD_JOIN, OFC_HANDLE_NULL);
  if (hiThread == OFC_HANDLE_NULL)
    printf("Could not create ichatApp\n");

  hoThread = ofc_thread_create(&ochatApp,
                               OFC_THREAD_THREAD_TEST, OFC_THREAD_SINGLETON,
                               OFC_NULL,
                               OFC_THREAD_JOIN, OFC_HANDLE_NULL);
  if (hoThread == OFC_HANDLE_NULL)
    printf("Could not create ochatApp\n");

  ofc_process_term_trap(term_handler);

  ofc_thread_wait(hiThread);
  ofc_thread_wait(hoThread);

  of_smb_shutdown_server(hApp);

#else
  printf("Server Not Supported\n");
#endif

  /*
   * Deactivate the openfiles stack
   */
  printf("Deactivating Stack\n");
  smbcp_deactivate();

  exit(0);
  return (0);
}

