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
#include <ofc/waitset.h>
#include <ofc/queue.h>
#include <ofc/time.h>
#include <of_smb/framework.h>

static wchar_t *MakeFilename(const wchar_t *dirname, const wchar_t *name)
{
  size_t dirlen;
  size_t namelen;
  wchar_t *filename;

  dirlen = wcslen (dirname);
  namelen = wcslen (name);
  filename =
    malloc((dirlen + namelen + 2) * sizeof(wchar_t));
  wcscpy (filename, dirname);
  filename[dirlen] = L'/';
  wcscpy (&filename[dirlen+1], name);
  filename[dirlen + 1 + namelen] = L'\0';
  return (filename);
}

/*
 * Atrtribute test
 */
static char *Attr2Str[17] =
  {
    "RO",            /* Read Only */
    "HID",            /* Hidden */
    "SYS",            /* System */
    "",
    "DIR",            /* Directory */
    "ARV",            /* Archive */
    "",
    "NRM",            /* Normal */
    "TMP",            /* Temporary */
    "SPR",            /* Sparse */
    "",
    "CMP",            /* Compressed */
    "OFF",            /* Offline */
    "",
    "ENC",            /* Encrypted */
    ""
    "VIRT",            /* Virtual */
  };

static OFC_VOID OfcFSPrintFindData(OFC_WIN32_FIND_DATA *find_data)
{
  OFC_INT i;
  OFC_UINT16 mask;
  OFC_CHAR str[100];        /* Guaranteed big enough for all attributes */
  OFC_CHAR *p;
  OFC_BOOL first;
  OFC_WORD fat_date;
  OFC_WORD fat_time;
  OFC_UINT16 month;
  OFC_UINT16 day;
  OFC_UINT16 year;
  OFC_UINT16 hour;
  OFC_UINT16 min;
  OFC_UINT16 sec;

  printf("File: %ls\n", find_data->cFileName);
  printf("Alternate Name: %.14ls\n", find_data->cAlternateFileName);
  printf("Attributes: 0x%08x\n", find_data->dwFileAttributes);

  mask = 0x0001;
  str[0] = '\0';
  p = str;
  first = OFC_TRUE;
  for (i = 0; i < 16; i++, mask <<= 1)
    {
      if (find_data->dwFileAttributes & mask)
        {
          if (first)
            first = OFC_FALSE;
          else
            {
              strcpy(p, ", ");
              p += 2;
            }
          strcpy(p, Attr2Str[i]);
          p += strlen(Attr2Str[i]);
        }
    }
  *p = '\0';

  printf("    %s\n", str);

  ofc_file_time_to_dos_date_time(&find_data->ftCreateTime,
                                 &fat_date, &fat_time);

  ofc_dos_date_time_to_elements(fat_date, fat_time,
                                &month, &day, &year, &hour, &min, &sec);
  printf("Create Time: %02d/%02d/%04d %02d:%02d:%02d GMT\n",
	 month, day, year, hour, min, sec);
  ofc_file_time_to_dos_date_time(&find_data->ftLastAccessTime,
                                 &fat_date, &fat_time);

  ofc_dos_date_time_to_elements(fat_date, fat_time,
                                &month, &day, &year, &hour, &min, &sec);
  printf("Last Access Time: %02d/%02d/%04d %02d:%02d:%02d GMT\n",
	 month, day, year, hour, min, sec);
  ofc_file_time_to_dos_date_time(&find_data->ftLastWriteTime,
                                 &fat_date, &fat_time);
  ofc_dos_date_time_to_elements(fat_date, fat_time,
                                &month, &day, &year, &hour, &min, &sec);
  printf("Last Write Time: %02d/%02d/%04d %02d:%02d:%02d GMT\n",
	 month, day, year, hour, min, sec);

  printf("File Size High: 0x%08x, Low: 0x%08x\n",
	 find_data->nFileSizeHigh, find_data->nFileSizeLow);
  printf("\n");
}

static OFC_DWORD ls(OFC_CTCHAR *dirname)
{
  OFC_HANDLE list_handle;
  OFC_WIN32_FIND_DATA find_data;
  OFC_BOOL more = OFC_FALSE;
  OFC_BOOL status;
  OFC_TCHAR *filename;
  OFC_DWORD last_error;
  OFC_INT count;

  list_handle = OFC_INVALID_HANDLE_VALUE;
  last_error = OFC_ERROR_SUCCESS;

  count = 0;
  filename = MakeFilename(dirname, TSTR("*"));

  list_handle = OfcFindFirstFile(filename, &find_data, &more);

  if (list_handle == OFC_INVALID_HANDLE_VALUE)
    {
      last_error = OfcGetLastError();
    }
  free(filename);

  if (list_handle != OFC_INVALID_HANDLE_VALUE)
    {
      if (wcscmp(find_data.cFileName, L".") != 0 &&
	  wcscmp(find_data.cFileName, L"..") != 0)
	{
	  count++;
	  OfcFSPrintFindData(&find_data);
	}

      status = OFC_TRUE;
      while (more && status == OFC_TRUE)
	{
	  status = OfcFindNextFile(list_handle,
				   &find_data,
				   &more);
	  if (status == OFC_TRUE)
	    {
	      if (wcscmp(find_data.cFileName, L".") != 0 &&
		  wcscmp(find_data.cFileName, L"..") != 0)
		{
		  count++;
		  OfcFSPrintFindData(&find_data);
		}
            }
          else
            {
              last_error = OfcGetLastError();
            }
        }
      OfcFindClose(list_handle);
    }
  printf("Total Number of Files in Directory %d\n", count);
  return (last_error);
}

int main (int argc, char **argp)
{
  OFC_TCHAR *wfilename;
  OFC_DWORD ret;
  size_t len;
  mbstate_t ps;
  const char *cursor;

  if (argc < 2)
    {
      printf ("Usage: smbls <dir>\n");
      exit (1);
    }

  memset(&ps, 0, sizeof(ps));
  len = strlen(argp[1]) + 1;
  wfilename = malloc(sizeof(wchar_t) * len);
  cursor = argp[1];
  mbsrtowcs(wfilename, &cursor, len, &ps);

  printf("Listing %s: ", argp[1]);
  fflush(stdout);

  ret = ls(wfilename);
  
  free(wfilename);

  if (ret == OFC_ERROR_SUCCESS || ret == OFC_ERROR_NO_MORE_FILES)
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

