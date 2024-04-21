/* Copyright (c) 2021 Connected Way, LLC. All rights reserved.
 * Use of this source code is unrestricted
 */

#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <wchar.h>
#include <unistd.h>
#include <assert.h>

#include <ofc/config.h>
#include <ofc/handle.h>
#include <ofc/types.h>
#include <ofc/net.h>
#include <of_smb/framework.h>

int main (int argc, char **argp)
{
  OFC_DWORD ret;

#if defined(OF_SMB_SERVER)
  printf("Starting Server\n");

  OFC_HANDLE hScheduler = of_smb_startup_server();

  while (1)
    {
      sleep(10000);
    }
  of_smb_shutdown_server(hScheduler);
#else
  printf("Server Not Supported\n");
#endif

  exit(0);
  return (0);
}

