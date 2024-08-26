/* Copyright (c) 2021 Connected Way, LLC. All rights reserved.
 * Use of this source code is unrestricted
 */

#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <wchar.h>
#include <unistd.h>

#include <ofc/config.h>
#include <ofc/framework.h>
#include <ofc/handle.h>
#include <ofc/types.h>
#include <ofc/file.h>
#include <ofc/thread.h>

#include "smbinit.h"

/**
 * \{
 */

/*
 * Buffering definitions.  We test using overlapped asynchronous I/O.  
 */
#define BUFFER_SIZE OFC_MAX_IO

static OFC_DWORD ichatApp(OFC_HANDLE hThread, OFC_VOID *context)
{
  OFC_HANDLE hFile ;
  OFC_CHAR buffer[BUFFER_SIZE];

  ofc_printf("ichat Thread is Running\n");

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
      ofc_printf ("Couldn't create ichatsvc file\n") ;
    }
  else
    {
      while (!ofc_thread_is_deleting(hThread))
        {
          fgets(buffer, BUFFER_SIZE, stdin);
          if (OfcWriteFile(hFile, buffer, strlen(buffer),
                           OFC_NULL, OFC_HANDLE_NULL) == OFC_FALSE)
            ofc_printf("Couldn't write to ichatsvcfile\n");
        }
      OfcCloseHandle(hFile);
    }
    ofc_printf("Test Thread is Exiting\n");
    return (0);
}

static OFC_DWORD ochatApp(OFC_HANDLE hThread, OFC_VOID *context)
{
  OFC_HANDLE hFile ;
  OFC_CHAR buffer[BUFFER_SIZE];

  ofc_printf("ochat Thread is Running\n");

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
      ofc_printf ("Couldn't create ochatsvc file\n") ;
    }
  else
    {
      while (!ofc_thread_is_deleting(hThread))
        {
          OFC_DWORD bytes_read;
          if (OfcReadFile(hFile, buffer, BUFFER_SIZE, &bytes_read, OFC_HANDLE_NULL) == OFC_FALSE)
            ofc_printf("Couldn't read from ochatsvcfile\n");
          else
            ofc_printf("%.*s\n", bytes_read, buffer);
        }
      OfcCloseHandle(hFile);
    }
    ofc_printf("Test Thread is Exiting\n");
    return (0);
}

int main (int argc, char **argp)
{
  OFC_DWORD ret;
  OFC_HANDLE hiThread;
  OFC_HANDLE hoThread;

  smbcp_init();

  printf("Listening for chat...\n");
  fflush(stdout);

  hiThread = ofc_thread_create(&ichatApp
                               OFC_THREAD_THREAD_TEST, OFC_THREAD_SINGLETON,
                               OFC_NULL,
                               OFC_THREAD_JOIN, OFC_HANDLE_NULL);
  if (hiThread == OFC_HANDLE_NULL)
    printf("Could not create ichatApp\n");

  hoThread = ofc_thread_create(&ochatApp
                               OFC_THREAD_THREAD_TEST, OFC_THREAD_SINGLETON,
                               OFC_NULL,
                               OFC_THREAD_JOIN, OFC_HANDLE_NULL);
  if (hoThread == OFC_HANDLE_NULL)
    printf("Could not create ochatApp\n");

  ofc_thread_wait(hiThread);
  ofc_thread_wait(hoThread);

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

/**
 * \}
 */
