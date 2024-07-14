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
#include <ofc/perist.h>
#include <ofc/queue.h>
#include <of_smb/framework.h>

/**
 * \{
 */

/*
 * Buffering definitions.  We test using overlapped asynchronous I/O.  
 */
#define BUFFER_SIZE OFC_MAX_IO
#define NUM_FILE_BUFFERS 10
/*
 * Buffer states.
 */
typedef enum {
  BUFFER_STATE_IDLE,        /* There is no I/O active */
  BUFFER_STATE_READ,        /* Data is being read into the buffer */
  BUFFER_STATE_WRITE        /* Data is being written from the buffer */
} BUFFER_STATE;
/*
 * The buffer context
 */
typedef struct {
  OFC_HANDLE readOverlapped;  /* The handle to the buffer when reading */
  OFC_HANDLE writeOverlapped; /* The handle to the buffer when writing */
  OFC_CHAR *data;             /* Pointer to the buffer */
  BUFFER_STATE state;         /* Buffer state */
  OFC_OFFT offset;            /* Offset in file for I/O */
} OFC_FILE_BUFFER;
/**
 * Async I/O Result
 */
typedef enum {
  ASYNC_RESULT_DONE,            /* I/O is successful */
  ASYNC_RESULT_ERROR,           /* I/O was in error */
  ASYNC_RESULT_EOF,             /* I/O hit EOF */
  ASYNC_RESULT_PENDING          /* I/O is still pending */
} ASYNC_RESULT;

/**
 * Copy State
 *
 * Main state for the copy
 */
struct copy_state {
  OFC_HANDLE read_file;         /* Handle of Read File */
  OFC_HANDLE write_file;        /* Handle of Write File */
  OFC_HANDLE wait_set;          /* Wait Set of all pending bufers */
  OFC_HANDLE buffer_list;       /* List of Buffers */
  OFC_OFFT offset;              /* Running Offset for next read */
  OFC_INT pending;              /* Number of pending I/Os */
  OFC_BOOL eof;                 /* EOF state of copy */
};

/*
 * Perform an I/O Read
 *
 * This routine initiates a read on an async buffer and adds it to the
 * waitset if the I/O is pending
 *
 * \param wait_set
 * The wait set that this I/O and it's overlapped handles will be part of
 *
 * \param read_file
 * Handle of read file
 *
 * \param buffer
 * Pointer to buffer to read into
 *
 * \param dwLen
 * Length of buffer to read
 *
 * \param dwLastError
 * Error code if result is error
 *
 * \returns
 * ASYNC_RESULT of I/O
 */
static ASYNC_RESULT AsyncRead(OFC_HANDLE wait_set,
                              OFC_HANDLE read_file,
                              OFC_FILE_BUFFER *buffer,
                              OFC_DWORD dwLen,
                              OFC_DWORD *dwLastError)
{
  ASYNC_RESULT result;
  OFC_BOOL status;

  /*
   * initialize the read buffer using the read file, the read overlapped
   * handle and the current read offset
   */
  OfcSetOverlappedOffset(read_file, buffer->readOverlapped, buffer->offset);
  buffer->state = BUFFER_STATE_READ;
  /*
   * Issue the non blocking read
   */
  status = OfcReadFile(read_file, buffer->data, dwLen,
                       OFC_NULL, buffer->readOverlapped);

  if (status == OFC_TRUE)
    {
      result = ASYNC_RESULT_DONE;
    }
  else
    {
      /*
       * Check if it's pending (expected)
       */
      *dwLastError = OfcGetLastError();
      if (*dwLastError == OFC_ERROR_IO_PENDING)
        {
          /*
           * Add it to the waitset
           */
          ofc_waitset_add(wait_set, (OFC_HANDLE) buffer,
                          buffer->readOverlapped);
          result = ASYNC_RESULT_PENDING;
	  *dwLastError = OFC_ERROR_SUCCESS;
        }
      else
        {
          if (*dwLastError == OFC_ERROR_HANDLE_EOF) 
            {
              result = ASYNC_RESULT_EOF;
            }
          else
            {
              result = ASYNC_RESULT_ERROR;
            }
          /*
           * Either eof or error, buffer is complete
           */
          buffer->state = BUFFER_STATE_IDLE;
          ofc_waitset_remove(wait_set, buffer->readOverlapped);
        }
    }
  return (result);
}

/*
 * Return the state of an async read
 *
 * \param wait_set
 * Wait set that the I/O should be part of
 *
 * \param read_file
 * Handle to the read file
 *
 * \param buffer
 * Pointer to the buffer
 *
 * \param dwLen
 * Number of bytes to read / number of bytes read
 *
 * \param dwLastError
 * Error code if status is ASYNC_RESULT_ERROR
 *
 * \returns
 * status of the read
 */
static ASYNC_RESULT AsyncReadResult(OFC_HANDLE wait_set,
                                    OFC_HANDLE read_file,
                                    OFC_FILE_BUFFER *buffer,
                                    OFC_DWORD *dwLen,
                                    OFC_DWORD *dwLastError)
{
  ASYNC_RESULT result;
  OFC_BOOL status;
  /*
   * Get the overlapped result
   */
  status = OfcGetOverlappedResult(read_file, buffer->readOverlapped,
                                  dwLen, OFC_FALSE);
  /*
   * If the I/O is complete, status will be true and length will be non zero
   */
  if (status == OFC_TRUE)
    {
      if (*dwLen == 0)
        {
          result = ASYNC_RESULT_EOF;
        }
      else
        {
          result = ASYNC_RESULT_DONE;
        }
    }
  else
    {
      /*
       * I/O may still be pending
       */
      *dwLastError = OfcGetLastError();
      if (*dwLastError == OFC_ERROR_IO_PENDING)
        result = ASYNC_RESULT_PENDING;
      else
        {
          /*
           * I/O may also be EOF
           */
          if (*dwLastError != OFC_ERROR_HANDLE_EOF)
            {
              result = ASYNC_RESULT_ERROR;
            }
          else
            result = ASYNC_RESULT_EOF;
        }
    }

  if (result != ASYNC_RESULT_PENDING)
    {
      /*
       * Finish up the buffer if the I/O is no longer pending
       */
      buffer->state = BUFFER_STATE_IDLE;
      ofc_waitset_remove(wait_set, buffer->readOverlapped);
    }

  return (result);
}

/*
 * Perform an I/O Write
 *
 * This routine initiates a write on an async buffer and adds it to the
 * waitset if the I/O is pending
 *
 * \param wait_set
 * The wait set that this I/O and it's overlapped handles will be part of
 *
 * \param write_file
 * Handle of write file
 *
 * \param buffer
 * Pointer to buffer to read into
 *
 * \param dwLen
 * Length of buffer to read
 *
 * \param dwLastError
 * Error code if result is error
 *
 * \returns
 * Async Result
 */
static ASYNC_RESULT AsyncWrite(OFC_HANDLE wait_set, OFC_HANDLE write_file,
                               OFC_FILE_BUFFER *buffer, OFC_DWORD dwLen,
                               OFC_DWORD *dwLastError)
{
  OFC_BOOL status;
  ASYNC_RESULT result;

  OfcSetOverlappedOffset(write_file, buffer->writeOverlapped,
                         buffer->offset);

  buffer->state = BUFFER_STATE_WRITE;

  status = OfcWriteFile(write_file, buffer->data, dwLen, OFC_NULL,
                        buffer->writeOverlapped);

  result = ASYNC_RESULT_DONE;
  if (status != OFC_TRUE)
    {
      *dwLastError = OfcGetLastError();
      if (*dwLastError == OFC_ERROR_IO_PENDING)
        {
	  *dwLastError = OFC_ERROR_SUCCESS;
          result = ASYNC_RESULT_PENDING;
          ofc_waitset_add(wait_set,
                          (OFC_HANDLE) buffer, buffer->writeOverlapped);
        }
      else
        {
          result = ASYNC_RESULT_ERROR;
          buffer->state = BUFFER_STATE_IDLE;
        }
    }
  return (result);
}

static ASYNC_RESULT AsyncWriteResult(OFC_HANDLE wait_set,
                                     OFC_HANDLE write_file,
                                     OFC_FILE_BUFFER *buffer,
                                     OFC_DWORD *dwLen,
                                     OFC_DWORD *dwLastError)
{
  ASYNC_RESULT result;
  OFC_BOOL status;

  status = OfcGetOverlappedResult(write_file, buffer->writeOverlapped,
                                  dwLen, OFC_FALSE);
  if (status == OFC_TRUE)
    result = ASYNC_RESULT_DONE;
  else
    {
      *dwLastError = OfcGetLastError();
      if (*dwLastError == OFC_ERROR_IO_PENDING)
        result = ASYNC_RESULT_PENDING;
      else
        {
          result = ASYNC_RESULT_ERROR;
        }
    }

  if (result != ASYNC_RESULT_PENDING)
    {
      buffer->state = BUFFER_STATE_IDLE;
      ofc_waitset_remove(wait_set, buffer->writeOverlapped);
    }

  return (result);
}

static OFC_VOID destroy_buffer(struct copy_state *copy_state,
			       OFC_FILE_BUFFER *buffer)
{
  if (buffer->writeOverlapped != OFC_HANDLE_NULL)
    {
      /*
       * Destroy the overlapped I/O handle for each buffer
       */
      OfcDestroyOverlapped(copy_state->write_file, buffer->writeOverlapped);
      buffer->writeOverlapped = OFC_HANDLE_NULL;
    }

  if (buffer->readOverlapped != OFC_HANDLE_NULL)
    {
      OfcDestroyOverlapped(copy_state->read_file, buffer->readOverlapped);
      buffer->readOverlapped = OFC_HANDLE_NULL;
    }

  if (buffer->data != OFC_NULL)
    {
      free(buffer->data);
      buffer->data = OFC_NULL;
    }

  free(buffer);
}

static OFC_VOID destroy_buffer_list (struct copy_state *copy_state,
				     OFC_HANDLE buffer_list)
{
  OFC_FILE_BUFFER *buffer;

  for (buffer = ofc_dequeue(buffer_list);
       buffer != OFC_NULL;
       buffer = ofc_dequeue(buffer_list))
    {
      destroy_buffer(copy_state, buffer);
    }
}

static OFC_HANDLE alloc_buffer_list(struct copy_state *copy_state,
				    OFC_HANDLE read_file,
                                    OFC_HANDLE write_file)
{
  OFC_HANDLE buffer_list;
  OFC_BOOL status = OFC_TRUE;
  OFC_FILE_BUFFER *buffer;
  
  buffer_list = ofc_queue_create();
  if (buffer_list == OFC_HANDLE_NULL)
    status = OFC_FALSE;
  
  for (int i = 0; i < NUM_FILE_BUFFERS && status; i++)
    {
      /*
       * Get the buffer descriptor and the data buffer
       */
      buffer = malloc(sizeof(OFC_FILE_BUFFER));
      if (buffer == OFC_NULL)
        {
          status = OFC_FALSE;
        }
      else
        {
          buffer->data = OFC_NULL;
          buffer->readOverlapped = OFC_HANDLE_NULL;
          buffer->writeOverlapped = OFC_HANDLE_NULL;
          
          buffer->data = malloc(BUFFER_SIZE);
          if (buffer->data == OFC_NULL)
            {
              status = OFC_FALSE;
            }
          else
            {
              /*
               * And initialize the overlapped handles
               */
              buffer->readOverlapped = OfcCreateOverlapped(read_file);
              buffer->writeOverlapped = OfcCreateOverlapped(write_file);
              if (buffer->readOverlapped == OFC_HANDLE_NULL ||
                  buffer->writeOverlapped == OFC_HANDLE_NULL)
                {
                  status = OFC_FALSE;
                }
            }

          if (status == OFC_TRUE)
            {
              /*
               * Add it to our buffer list
               */
              ofc_enqueue(buffer_list, buffer);
            }
          else
            {
              destroy_buffer(copy_state, buffer);
              buffer = OFC_NULL;
            }
        }
    }

  if (status == OFC_FALSE && buffer_list != OFC_HANDLE_NULL)
    {
      destroy_buffer_list(copy_state, buffer_list);
      buffer_list = OFC_HANDLE_NULL;
    }

  return (buffer_list);
}

static OFC_DWORD prime_buffers (struct copy_state *copy_state)
{
  OFC_FILE_BUFFER *buffer;
  OFC_DWORD dwLen;
  ASYNC_RESULT result;
  OFC_DWORD dwLastError;

  for (buffer = ofc_queue_first(copy_state->buffer_list);
       buffer != OFC_NULL && !copy_state->eof;
       buffer = ofc_queue_next(copy_state->buffer_list, buffer))
    {
      dwLen = BUFFER_SIZE;
      /*
       * Issue the read (pre increment the pending to
       * avoid races
       */
      copy_state->pending++;
      buffer->offset = copy_state->offset;
      result = AsyncRead(copy_state->wait_set, copy_state->read_file,
                         buffer, dwLen, &dwLastError);

      if (result != ASYNC_RESULT_PENDING)
        {
          /*
           * discount pending and set eof
           */
          copy_state->pending--;
          /*
           * Set eof either because it really is eof, or we
           * want to clean up.
           */
          copy_state->eof = OFC_TRUE;
        }
      /*
       * Prepare for the next buffer
       */
      copy_state->offset += BUFFER_SIZE;
    }
  return (dwLastError);
}

static OFC_VOID destroy_copy_state(struct copy_state *copy_state)
{
  if (copy_state->buffer_list != OFC_HANDLE_NULL)
    {
      destroy_buffer_list (copy_state, copy_state->buffer_list);
      copy_state->buffer_list = OFC_HANDLE_NULL;
    }
  
  if (copy_state->wait_set != OFC_HANDLE_NULL)
    {
      ofc_waitset_destroy(copy_state->wait_set);
      copy_state->wait_set = OFC_HANDLE_NULL;
    }

  if (copy_state->write_file != OFC_HANDLE_NULL)
    {
      OfcCloseHandle(copy_state->write_file);
      copy_state->write_file = OFC_HANDLE_NULL;
    }

  if (copy_state->read_file != OFC_HANDLE_NULL)
    {
      OfcCloseHandle(copy_state->read_file);
      copy_state->read_file = OFC_HANDLE_NULL;
    }

  free(copy_state);
}

static struct copy_state *init_copy_state(OFC_CTCHAR *rfilename,
                                          OFC_CTCHAR *wfilename,
                                          OFC_DWORD *dwLastError)
{
  struct copy_state *copy_state;

  *dwLastError = OFC_ERROR_SUCCESS;
  
  copy_state = malloc(sizeof(struct copy_state));
  if (copy_state == OFC_NULL)
    *dwLastError = OFC_ERROR_NOT_ENOUGH_MEMORY;
  else
    {
      copy_state->read_file = OFC_HANDLE_NULL;
      copy_state->write_file = OFC_HANDLE_NULL;
      copy_state->wait_set = OFC_HANDLE_NULL;
      copy_state->buffer_list = OFC_HANDLE_NULL;
      copy_state->offset = 0;
      copy_state->pending = 0;
      copy_state->eof = OFC_FALSE;
      /*
       * Open up our read file.  This file should
       * exist
       */
      copy_state->read_file = OfcCreateFile(rfilename,
                                            OFC_GENERIC_READ,
                                            OFC_FILE_SHARE_READ,
                                            OFC_NULL,
                                            OFC_OPEN_EXISTING,
                                            OFC_FILE_ATTRIBUTE_NORMAL |
                                            OFC_FILE_FLAG_OVERLAPPED,
                                            OFC_HANDLE_NULL);

      if (copy_state->read_file == OFC_INVALID_HANDLE_VALUE)
        {
          *dwLastError = OfcGetLastError();
        }
      else
        {
          /*
           * Open up our write file.  If it exists, it will be deleted
           */
          copy_state->write_file = OfcCreateFile(wfilename,
                                                 OFC_GENERIC_WRITE,
                                                 0,
                                                 OFC_NULL,
                                                 OFC_CREATE_ALWAYS,
                                                 OFC_FILE_ATTRIBUTE_NORMAL |
                                                 OFC_FILE_FLAG_OVERLAPPED,
                                                 OFC_HANDLE_NULL);

          if (copy_state->write_file == OFC_INVALID_HANDLE_VALUE)
            {
              *dwLastError = OfcGetLastError();
            }
        }

      if (*dwLastError == OFC_ERROR_SUCCESS)
        {
          /*
           * Now, create a wait set that we will wait for
           */
          copy_state->wait_set = ofc_waitset_create();
          if (copy_state->wait_set == OFC_HANDLE_NULL)
            {
              *dwLastError = OFC_ERROR_NOT_ENOUGH_MEMORY;
            }
        }

      if (*dwLastError == OFC_ERROR_SUCCESS)
        {
          /*
           * And create our own buffer list that we will manage
           */
          copy_state->buffer_list = alloc_buffer_list(copy_state,
						      copy_state->read_file,
                                                      copy_state->write_file);

          if (copy_state->buffer_list == OFC_HANDLE_NULL)
            *dwLastError = OFC_ERROR_NOT_ENOUGH_MEMORY;
        }

      if (*dwLastError != OFC_ERROR_SUCCESS)
        {
          destroy_copy_state (copy_state);
          copy_state = OFC_NULL;
        }
    }
  return (copy_state);
}

static OFC_DWORD feed_buffers(struct copy_state *copy_state)
{
  OFC_HANDLE hEvent;
  OFC_FILE_BUFFER *buffer;
  OFC_DWORD dwLen;
  OFC_DWORD dwLastError;
  OFC_DWORD dwFirstError;
  ASYNC_RESULT result;
  /*
   * Now all our buffers should be busy doing reads.  Keep pumping
   * more data to read and service writes
   */
  dwLastError = OFC_ERROR_SUCCESS;
  dwFirstError = OFC_ERROR_SUCCESS;

  while (copy_state->pending > 0)
    {
      /*
       * Wait for some buffer to finish (may be a read if we've
       * just finished priming, but it may be a write also if
       * we've been in this loop a bit
       */
      hEvent = ofc_waitset_wait(copy_state->wait_set);
      if (hEvent != OFC_HANDLE_NULL)
        {
          /*
           * We use the app of the event as a pointer to the
           * buffer descriptor.  Yeah, this isn't really nice but
           * the alternative is to add a context to each handle.
           * That may be cleaner, but basically unnecessary.  If
           * we did this kind of thing a lot, I'm all for a
           * new property of a handle
           */
          buffer = (OFC_FILE_BUFFER *) ofc_handle_get_app(hEvent);
          /*
           * Now we have both read and write overlapped descriptors
           * See what state we're in
           */
          if (buffer->state == BUFFER_STATE_READ)
            {
              /*
               * Read, so let's see the result of the read
               */
              result = AsyncReadResult(copy_state->wait_set,
                                       copy_state->read_file,
                                       buffer, &dwLen,
                                       &dwLastError);
              if (result == ASYNC_RESULT_ERROR)
                dwFirstError = dwLastError;
              else if (result == ASYNC_RESULT_DONE)
                {
                  /*
                   * When the read is done, let's start up the write
                   */
                  result = AsyncWrite(copy_state->wait_set,
                                      copy_state->write_file,
                                      buffer, dwLen,
                                      &dwLastError);
                  if (result == ASYNC_RESULT_ERROR)
                    dwFirstError = dwLastError;
                }
              /*
               * If the write failed, or we had a read result error
               */
              if (result == ASYNC_RESULT_ERROR ||
                  result == ASYNC_RESULT_EOF ||
                  (result == ASYNC_RESULT_DONE &&
                   dwLastError != OFC_ERROR_SUCCESS))
                {
                  /*
                   * The I/O is no longer pending.
                   */
                  copy_state->pending--;
                  copy_state->eof = OFC_TRUE;
                }
            }
          else
            {
              /*
               * The buffer state was write.  Let's look at our
               * status
               */
              result = AsyncWriteResult(copy_state->wait_set,
                                        copy_state->write_file,
                                        buffer, &dwLen,
                                        &dwLastError);
              if (result == ASYNC_RESULT_ERROR)
                dwFirstError = dwLastError;
              else if (result == ASYNC_RESULT_DONE)
                {
                  /*
                   * The write is finished.
                   * Let's step the buffer
                   */
                  buffer->offset = copy_state->offset;
                  copy_state->offset += BUFFER_SIZE;
                  /*
                   * And start a read on the next chunk
                   */
                  result = AsyncRead(copy_state->wait_set,
                                     copy_state->read_file,
                                     buffer, BUFFER_SIZE,
                                     &dwLastError);
                  if (result == ASYNC_RESULT_ERROR)
                    dwFirstError = dwLastError;
                }

              if (result != ASYNC_RESULT_PENDING)
                {
                  copy_state->eof = OFC_TRUE;
                  copy_state->pending--;
                }
            }
        }
    }
  return (dwFirstError);
}


static OFC_DWORD copy_async(OFC_CTCHAR *rfilename, OFC_CTCHAR *wfilename)
{
  struct copy_state *copy_state;
  OFC_DWORD dwLastError;

  dwLastError = OFC_ERROR_SUCCESS;

  copy_state = init_copy_state(rfilename, wfilename, &dwLastError);
  if (copy_state != OFC_NULL)
    {
      /*
       * Prime the engine.  Priming involves obtaining a buffer
       * for each overlapped I/O and initilizing them
       */
      dwLastError = prime_buffers(copy_state);
      if (dwLastError == OFC_ERROR_SUCCESS)
        {
          dwLastError = feed_buffers(copy_state);
        }

      destroy_copy_state(copy_state);
      copy_state = OFC_NULL;
    }

  return (dwLastError);
}

static OFC_DWORD copy_sync(OFC_CTCHAR *rfilename, OFC_CTCHAR *wfilename)
{
  struct copy_state *copy_state;
  OFC_DWORD dwLastError;
  OFC_HANDLE read_file;
  OFC_HANDLE write_file;
  OFC_CHAR buffer[BUFFER_SIZE];
  OFC_DWORD dwLen;
  OFC_BOOL ret;

  dwLastError = OFC_ERROR_SUCCESS;

  read_file = OFC_HANDLE_NULL;
  write_file = OFC_HANDLE_NULL;
  /*
   * Open up our read file.  This file should
   * exist
   */
  read_file = OfcCreateFile(rfilename,
			    OFC_GENERIC_READ,
			    OFC_FILE_SHARE_READ,
			    OFC_NULL,
			    OFC_OPEN_EXISTING,
			    OFC_FILE_ATTRIBUTE_NORMAL,
			    OFC_HANDLE_NULL);

  if (read_file == OFC_INVALID_HANDLE_VALUE)
    {
      dwLastError = OfcGetLastError();
    }
  else
    {
      /*
       * Open up our write file.  If it exists, it will be deleted
       */
      write_file = OfcCreateFile(wfilename,
				 OFC_GENERIC_WRITE,
				 0,
				 OFC_NULL,
				 OFC_CREATE_ALWAYS,
				 OFC_FILE_ATTRIBUTE_NORMAL,
				 OFC_HANDLE_NULL);

      if (write_file == OFC_INVALID_HANDLE_VALUE)
	{
	  dwLastError = OfcGetLastError();
	}
      else
	{
	  while ((ret = OfcReadFile(read_file, buffer, BUFFER_SIZE,
				    &dwLen, OFC_HANDLE_NULL)) == OFC_TRUE)
	    {
	      ret = OfcWriteFile(write_file, buffer, dwLen,
				 &dwLen, OFC_HANDLE_NULL);
	    }
	  if (ret == OFC_FALSE)
	    {
	      if (OfcGetLastError() != OFC_ERROR_HANDLE_EOF)
		dwLastError = OfcGetLastError();
	    }
	    
	  OfcCloseHandle(write_file);
	}
      OfcCloseHandle(read_file);
    }

  return (dwLastError);
}

#if !defined(INIT_ON_LOAD)
/*
 * Forward Declaration of explicit configuration routine
 */
void smbcp_configure(void);
#endif

/**
 * Routine to initialize the openfiles (ConnectSMB) stack
 *
 * There are three operations involved in starting up an Open Files
 * stack:
 *   - Initialize the Open Files state
 *   - Configure the Open Files Stack
 *   - Start up the stack
 *
 * Open Files (ConnectSMB) can implicitly initialize, configure and startup
 * the stack, or the steps can be executed explicitly.
 *
 * The behavior is governed by two config variables.
 * The config file used in the build (<platform>-behavior.cfg) contains two
 * variables:
 *
 * INIT_ON_LOAD - Initialize libraries on load
 * OFC_PERSIST - Build in persistent configuration support.
 *
 * If INIT_ON_LOAD is ON, OpenFiles will be initialized upon
 * library load, the stack will be configured through the default configuration
 * file, and the stack will be subsequently be sstarted.
 *
 * If INIT_ON_LOAD is OFF, an application will need to explicitly initialize
 * both the core framework and the smb framework, configure the stack
 * either through the persistent framework or explicitly through API calls, and
 * then must manually startup the stack.
 *
 * A runtime application can examine the state of these configuration variabues which
 * will be defined within the include file "ofc/config.h".
 *
 * If INIT_ON_LOAD is defined, then the stack will be implicitly initialized
 * upon library load.  If INIT_ON_LOAD is undefined, the application must perform
 * the initialization, configuration, and startup itself.
 *
 * If the application is performing explicit initialization, it needs to configure
 * the stack.  It can check whether OFC_PERSIST is defined or not.  If it is defined,
 * then the ability to configure the stack through a configuration file is supported.
 * Whether or not the configuration file has been set up or not is a deployment
 * consideration.  If the platform supports OFC_PERSIST and the deployment has
 * provided a configuration file, then the configuration can be loaded and stack
 * subsequently configured from the loaded config, or the application can explicity
 * configure the stack through APIs.  If OFC_PERSIST is not defined, the only way
 * to configure the stack will be through the APIs.
 *
 * Lastly, if the application is performing it's own explicit initialization, it must
 * start the stack after it has been configured.
 *
 * This routine is an example startup routine that will show how to explicitly
 * initialize, configure, and startup an Open Files (ConnectSMB) stack.
 */

void smsbcp_init(void)
{
#if defined(INIT_ON_LOAD)
  /*
   * Force an SMB library load, which will force initialization
   */
  volatile OFC_VOID *init = of_smb_init;
#else
  /*
   * Explicit Open Files Initialization
   */
  ofc_framework_init();
  of_smb_init();
  /*
   * Configure the stack either through persistent configuration or
   * explicitly through APIs
   */
  smbcp_configure();
  /*
   * Startup SMB.  The argument is a handle to a scheduler (i.e. a
   * run loop thread.  If Null, one will be created for it 
   */
  of_smb_startup(OFC_NULL);
#endif
  return (0);
}

#if !defined(OFC_PERSIST)
void smbcp_configure(void)
{
  OFC_INT ret;
#if defined(OFC_PERSIST)
  /*
   * Our build supports loading configuration from a file.
   * We can either specify the file to load, or we can
   * specify NULL which will implicity specify a default
   * location for the platform.  NOTE: not all platforms
   * have a default os to be safe, you probably should
   * explicitly specify the location.
   */
  ofc_framework_load(TSTR("/etc/openfiles.xml"));
#else
  /*
   * We will explicity configure the stack.
   *
   * Set up the network.  Openfiles supports network
   * autoconfiguration which is useful if the objective
   * is to bring up all interfaces available on the platform
   * and to have it adapt to interfaces dynamically coming
   * on and offline.  Manual network configuration is useful
   * if you wish to use a WINS server (which cannot be
   * autoconfigured).  NOTE: If autoconfiguration is off
   * there is no reason to have Network Monitoring On.
   * Network Monitoring will monitor for interface interruption.
   */
#if defined(SMBCP_NETWORK_AUTOCONFIG)
  ofc_persist_set_interface_type(OFC_CONFIG_ICONFIG_AUTO);
#else
  /*
   * Turn off interface discovery
   */
  ofc_framework_set_interface_discovery(OFC_FALSE);
  /*
   * Add an interface.  This is done by filling in an
   * framework interface structure add calling
   * ofc_framework_add_interface
   */
  OFC_FRAMEWORK_INTERFACE iface ;
  /*
   * Configure WINS (PMODE) mode.
   * Other mode are Broadcast (BMODE), Mixed (MMODE), and
   * Hybrid (HMODE).  Mixed is broadcast first, if that
   * fails, then WINS.  Hybrid is WINS first, then broadcast.
   */
  iface.netBiosMode = OFC_CONFIG_PMODE;
  /*
   * Configure the IP address.  The IP address is an
   * OFC_IPADDR which can initialized by a call to
   * ofc_pton.  NOTE: Be sure to retrieve and specify
   * the actual IP you wish to use.
   */
  ofc_pton("192.168.1.60", &iface.ip);
  ofc_pton("192.168.1.255", &iface.bcast);
  ofc_pton("255.255.255.0", &iface.mask);
  /*
   * Local Master Browser is not supported in SMBv2.  Deprecated
   * but specify as NULL.
   */
  iface.lmb = OFC_NULL;
  /*
   * Build a WINS list
   * A wins list consists of a count of wins servers followed
   * by a pointer to an array of WINS ip addresses
   * The wins list can be statically or dynamically allocated.
   * If you are dynamically allocating it, make sure you
   * free it after the ofc_framework_add_interface call.
   */
  OFC_IPADDR winsaddr[2];
  ofc_pton("192.168.1.61", &winsaddr[0]);
  ofc_pton("192.168.1.62", &winsaddr[1]);
  iface.wins.num_wins = 2;
  iface.wins.winsaddr = winsaddr;
  /*
   * Now add the interface
   */
  ofc_framework_add_interface(&iface) ;
#endif
  /*
   * Set up logging.  We want to log INFO messages and
   * higher. Don't log to the console.  On Linux,
   * This will log to syslog
   */
  ofc_framework_set_logging(OFC_LOG_INFO, OFC_FALSE);
  /*
   * Set the host name
   * This is not required for a client.  It is never used.
   * The fields are the hostname, the workgroup/domain name,
   * and a description
   */
  ofc_framework_set_host_name(TSTR("example"), TSTR("example.com"),
                              TSTR("Example Host"));
  /*
   * It is also possible to configure drives which is similar to
   * aliases.  In other words, you can set a tag for a particular
   * destination.  This would be done by calls to ofc_framework_add_map
   * Typically this is only done by the Android app so won't
   * be documented here.
   */

  /*
   * Enable Netbios
   */
  ofc_framework_set_netbios(OFC_TRUE);
  /*
   * Set the UUID.  This is required in an SMB negotiate request
   * but it doesn't appear to be checked by servers.  Ideally
   * though this should be a unique number.
   */
  static OFC_UUID uuid =
  {
    0x04, 0x5d, 0x88, 0x8a, 0xeb, 0x1c, 0xc9, 0x11,
    0x9f, 0xe8, 0x08, 0x00, 0x2b, 0x10, 0x48, 0x60
  };
  ofc_framework_set_uid(&uuid);
  /*
   * bootstrap_dcs can be explicity specified, but if
   * not set, DFS will query DNS.  So no need to configure
   */

  /*
   * There is configuration for supported ciphers, but by
   * default we specify both AES-128-GCM and AES-128-CCM.
   * There should never be a reason to change this
   */

  /*
   * There is also a configuration for max smb version but
   * by default we specify SMB 3.11.  There should never be
   * a reason to change this.
   */
#endif
}

int main (int argc, char **argp)
{
  OFC_TCHAR *rfilename;
  OFC_TCHAR *wfilename;
  size_t len;
  mbstate_t ps;
  OFC_DWORD ret;
  const char *cursor;
  int async = 0;
  int argidx;

  smbcp_init();

  if (argc < 3)
    {
      printf ("Usage: smbcp [-a | -dc <bootstrap-dc>] <source> <destination>\n");
      exit (1);
    }

  argidx = 1;
  while (1)
    {
      if (strcmp(argp[argidx], "-a") == 0)
	{
	  async = 1;
	  argidx++;
	}
      else if (strcmp(argp[argidx], "-dc") == 0)
	{
	  argidx++;
	  memset(&ps, 0, sizeof(ps));
	  len = strlen(argp[argidx]) + 1;
	  argidx++;
	  of_smb_set_bootstrap_dcs(1, &argp[argidx]);
	}
      else
	break;
    }

  memset(&ps, 0, sizeof(ps));
  len = strlen(argp[argidx]) + 1;
  rfilename = malloc(sizeof(wchar_t) * len);
  cursor = argp[argidx];
  mbsrtowcs(rfilename, &cursor, len, &ps);

  memset(&ps, 0, sizeof(ps));
  len = strlen(argp[argidx+1]) + 1;
  wfilename = malloc(sizeof(wchar_t) * len);
  cursor = argp[argidx+1];
  mbsrtowcs(wfilename, &cursor, len, &ps);

  printf("Copying %s to %s: ", argp[argidx], argp[argidx+1]);
  fflush(stdout);

  if (async)
    ret = copy_async(rfilename, wfilename);
  else
    ret = copy_sync(rfilename, wfilename);
  
  free(rfilename);
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

/**
 * \}
 */
