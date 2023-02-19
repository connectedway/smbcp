/* Copyright (c) 2021 Connected Way, LLC. All rights reserved.
 * Use of this source code is unrestricted
 */
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <wchar.h>

#include <ofc/file.h>

int main (int argc, char **argv)
{
  OFC_TCHAR *sharename;
  size_t len;
  mbstate_t ps;
  int ret;
  const char *cursor;
  OFC_BOOL result;

  OFC_DWORD SectorsPerCluster;
  OFC_DWORD BytesPerSector;
  OFC_DWORD NumberOfFreeClusters;
  OFC_DWORD TotalNumberOfClusters;

  long int used;
  long int avail;
  long int total;

  if (argc < 2)
    {
      printf ("Usage: smbfree <destination>\n");
      exit (1);
    }

  memset(&ps, 0, sizeof(ps));
  len = strlen(argv[1]) + 1;
  sharename = malloc(sizeof(wchar_t) * len);
  cursor = argv[1];
  mbsrtowcs(sharename, &cursor, len, &ps);

  printf("Finding Free Space on %s: ", argv[1]);
  fflush(stdout);

  result = OfcGetDiskFreeSpace(sharename,
			       &SectorsPerCluster,
                               &BytesPerSector,
			       &NumberOfFreeClusters,
                               &TotalNumberOfClusters);
  if (result == OFC_FALSE)
    {
      printf("[failed]\n");
      printf("%s\n", ofc_get_error_string(OfcGetLastError()));
      ret = 1;
    }
  else
    {
      printf("[ok]\n");
      printf("Free Space On %ls\n", sharename);
      printf("  Sectors Per Cluster: %d\n", SectorsPerCluster);
      printf("  Bytes Per Sector: %d\n", BytesPerSector);
      printf("  Number of Free Clusters: %d\n", NumberOfFreeClusters);
      printf("  Total Number of Clusters: %d\n", TotalNumberOfClusters);
      total = ((long int) TotalNumberOfClusters *
	       (long int) SectorsPerCluster *
	       (long int) BytesPerSector) / 512; 
      avail = ((long int) NumberOfFreeClusters *
	       (long int) SectorsPerCluster *
	       (long int) BytesPerSector) / 512; 
      used = total - avail;
      printf("  Capacity (512 byte blocks): %ld\n", total);
      printf("  Number of Free blocks: %ld\n", avail);
      printf("  Number of Used blocks: %ld\n", used);

#if 0
      printf("Sleeping for 11 seconds...\n");
      sleep(11);
      printf("Woke.  Bye\n");
#endif
      ret = 0;
    }

  free(sharename);

  return (ret);
}
  
