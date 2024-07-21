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

#include "smbinit.h"

int main (int argc, char **argp)
{
  OFC_DWORD ret;

  smbcp_init();

#if defined(OF_SMB_SERVER)
  printf("Starting Server\n");

  OFC_HANDLE hApp = of_smb_startup_server(OFC_HANDLE_NULL);

  while (1)
    {
      sleep(10000);
    }
#if 0
  of_smb_server_shutdown(hScheduler);
#endif
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

