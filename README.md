smbcp
=====

# Introduction

Open Files supports numerous deployment scenarios:
- statically linked RTOS deployments
- dynamically linked applications
- statically linked applications
- JNI based java applications
- FUSE handlers with external applications

The test_* applications are all statically linked applications.  The smbcp
executable is a dynamically linked application.  The application itself
is built seperately from the openfiles framework and is simply linked with
the framework on the target system.

The syntax of the smbcp utility is:

```
$ smbcp [-a | -dc <bootstrap-dc>] <source> <destination>
```

Where -a signifies that the copy operation should be done asynchronously
using multiple overlapped buffers.  The absense of -a specifies that the
copy is done synchronously.  Only one I/O is outstanding at a time in
syncronous mode.

If you are using a domain based DFS namespace in either the source or
destination filenames and the OpenFiles stack has not been configured
persistantly through the `/etc/openfiles.xml` file or the `bootstrap_dc`
entry in the configuration file has not been initialized, you should
specify the bootstrap dc in the `smbcp` command line.  This is primarily
here to support dynamic configuration testing of the bootstrap_dc.  We
highly recommend configuring the Open Files stack persistently.

smbcp can copy a file from local or remote locations to a file that resides
locally or remotely.  A file specification is of the form:

```
[//username:password:domain@server/share/]path.../file
```

Where the presence of a leading `//` signifies a remote location.  The
absence of a leading `//` signifies a local location.

With a remote URL, a username, password, server, and share are all required.
while the :domain is optional and used only for active directory managed
locations.  Path can be any depth as long as the total file path is less than
256 bytes.  For example:

```
$ smbcp //me:secret@remote/share/subdirectory/picture.jpg ./picture.jpg
```

This will access the server named 'remote' and log in using the username
'me' and the password 'secret'.  It will implicitly mount the remote share
named 'share' and will access the file 'subdirectory/picture.jpg' relative
to the share.  It will copy the file locally to the filename picture.jpg.

If you are using a domain based DFS namespace, and need to specify the
bootstrap dc, the command may be of the following form:

```
$ smbcp -dc dc1.spiritcloud.app \
  //me:secret@remote/share/subdirectory/picture.jpg ./picture.jpg
```

The source path and destination path can be either local or remote so
copies from a remote to a local, from a local to a remote, from a local to
a local, and from a remote to a remote are all possible.

The output of a smbcp session from a remote location to a remote location is
below:

```
root@qemuarm64:~# /usr/bin/openfiles/smbcp -a //*****:*******@192.168.1.206/spi
ritcloud/lizards.jpg //****:****@192.168.1.206/spiritcloud/lizard_copy.jpg
1435756250 OpenFiles (main) 5.0 1
1435756250 Loading /etc/openfiles.xml
1435756254 Device Name: localhost
1435756257 OpenFiles SMB (main) 5.0 1
Copying //******:*****@192.168.1.206/spiritcloud/lizards.jpg to //****:*****@192.168.1.206/spiritcloud/lizard_copy.jpg: [ok]
Total Allocated Memory 616, Max Allocated Memory 794571
```

The first line is the invocation of the command.  We wish to perform an
asynchronous copy from a remote file to a remote file.  The username and
password have been hidden for privacy.  
The server is specified with an IP address
(although a DNS name is acceptable).  The share is named spiritcloud.  The
file we are copying from is called lizards.jpg.  The destination is the same
user, password, remote, and share but with a target filename of
lizards_copy.jpg.  The following lines are information messages
which can be disabled.  At the completion is heap statistics.

# Building the smbcp application

If you are building a yocto based distribution using the of_manifests
repo configuration, the smbcp application will be built and included in
your distribution.

If you are deploying openfiles in a Linux environment, you will need to
clone, build, and install smbcp on your Linux machine.

## Cloning the smbcp repository

To clone the repo, simply issue:

```
$ git clone https://github.com/connectedway/smbcp.git
$ cd smbcp
```

## Building the smbcp Application

Note that if you wish to build the smbcp application, you will have had to
successfully build and installed the Open Files Framework.  You can find
more [Here](https://github.com/connectedway/openfiles/blob/main/README.md)
and [Here](https://github.com/connectedway/openfiles/blob/main/LINUX.md).

Then simply issue:

```
$ make
```

## Installing the smbcp Application

You can install the application into your system directories by issuing:

```
$ sudo make install
```

The application will be install, by default, in /usr/local/bin/openfiles.  You
may wish to add this to your path variable:

```
$ export PATH=$PATH:/usr/local/bin/openfiles
```

And update your shell startup scripts accordingly

## Uninstalling the smbcp Application

You can uninstall the application from your system directories by issuing:

```
$ sudo make uninstall
```

## Cleaning your build directory

You can clean up build artifacts from your build directory by issuing:

```
$ make clean
```

## Running the smbcp application

You can run the application by following the description in this README
files [Introduction](#introduction)

# smbcp Implementation

The implementatoin of the smbcp application is relevant for
integrating customer applications with the Linux based openfiles framework.

## smbcp Makefile

The makefile is a basic make.  The smbcp application consists of one object
file, smbcp.o.  The object file is compiled using bitbakes default CFLAGS
which includes a specification of the sysroot which will contain the necessary
openfiles header files.  The executable is linked with five shared libraries:
- libof_smb_shared
- libof_core_shared
- libmbedtls
- libkrb5
- libgssapi_krb5

We specify the linker option `--no-as-needed` which directs the linker to
include the libraries whether they are explicity referenced in the object
files or not.  This is needed if we wish to utilize implicit library
constructors.  As a conveniece to openfile application developers, we will
initialize the stack implicitly upon library load rather than requiring the
developer to initialize the stack within the application itself.

## smbcp Source Code

This readme will not go through line by line within the smbcp.c source file.
Rather, we'll call out relevant sections.

An openfiles application can use standard C libraries and with respect to
smbcp, we use four.  The wchar.h file is included so we can convert ASCII
characters to wide characters used as part of the openfiles API.  NOTE that
openfiles exposes an ascii API as well but wide characters is recommended.

There are six openfiles header files used by this application.  Openfiles
provides a robust set of APIs for many services.  We recommend viewing
the [openfiles api documentation](http://www.connectedway.com/openfiles) for
a detail.  The Openfiles recipe installs a subset of the available APIs into
the yocto sysroot.  If you find that particular headers are not available in
your sysroot, Connected Way support will be glad to export them for you.

A brief description of the headers used:

- ofc/config.h - This provides constants that the openfiles framework was
built with.  This will have defines for the maximum buffer size, whether
smb I/O is supported and more.
- ofc/handle.h - This defines a generic handle type used to refer to
openfile objects.  Handles are used throughout openfiles and can refer to
files, queues, events, sockets and more.
- ofc/types.h - This defines the basic types used by openfiles.
- ofc/file.h - The API used by the openfiles file system.
- ofc/waitset.h - This allows aggregation of waitable objects.  This is used
by the asynchronous file copy to manage asynchronous completion of multiple
buffers.
- ofc/queue.h - This is a robust abstraction of a doubly linked list.  It
is purely a convenience facility but is heavily used throughout the openfiles
framework and within the smbcp application to maintain lists of buffers.

In the simple case, this is the full set of APIs needed to interact with
the openfiles framework.  The main set of APIs is contained in the header
`file.h`.  For the most part, the file API of Open Files is based on the
Windows File APIs.  

The smbcp.c source file contains code for both the asynchronous file copy
and synchronous file copy modes.

The synchronous file copy is simple.  It simply opens up the source
and destination files and then enters a loop where a buffer is read from the
read file, and written to the write file.  The loop continues till an
eof on the read file or an error on either.  The entry point of the synchronous
copy is:

```
static OFC_DWORD copy_sync(OFC_CTCHAR *rfilename, OFC_CTCHAR *wfilename)
```

Pseudo code for the simple file copy follows.  

```
Begin

    Open the Read File as read_file

    Open the Write File as write_fil

    while Read from read_file into buffer and length is True

        Write to write_file from buffer and length

    Close write_file

    Close read_file

Done
```

The asynchronous code supports arbitrary
queue depth of arbitrary buffer size (up to a max of OFC_MAX_IO).  If you
have questions on the operation of the asynchrous copy, please contact
Connected Way support.  The entry point to the asynchronous file copy is

```
static OFC_DWORD copy_async(OFC_CTCHAR *rfilename, OFC_CTCHAR *wfilename)
```

The main entry point parses the arguments, converts the ascii file names
into wide character file names and calls the respective asynchronous or
synchronous entry points.

The APIs used by smbcp are:

APIs for Synchronous File Copy:

- OfcCreateFile - Create or Open a Local or Remote file.
- OfcReadFile - Read from a Local or Remote File
- OfcWriteFile - Write to a Local or Remote File
- OfcGetLasstError - Get the last error code encountered
- OfcCloseHandle - Close a Local or Remote File
- ofc_get_error_string - Convert a last error into a string

APIs for Asynchronous File Copy:

- OfcSetOverlappedOffset - Set the offset for an overlapped buffer
- OfcGetOverlappedResult - Get the result of an overlapped i/o
- OfcDestroyOverlapped - Destroy an overlapped buffer
- OfcCreateOverlapped - Create an overlapped buffer
- OfcReadFile - Read from a local or remote file
- OfcWriteFile - Write to a local or remote file
- OfcCreateFile - Create or Open a local or remote file
- OfcCloseHandle - Close a local or remote file
- OfcGetLastError - Get the last error code encountered
- ofc_waitset_add - Add an object to a list of waitable objects
- ofc_waitset_remove - Remove an object from a list of waitable objects
- ofc_waitset_destroy - Destroy the list of waitable objects
- ofc_waitset_create - Create a list of waitable objects
- ofc_waitset_wait - Wait for a buffer completion
- ofc_handle_get_app - Get a buffer association
- ofc_dequeue - Dequeue a buffer from a buffer list
- ofc_queue_create - Create a buffer list
- ofc_enqueue - Queue a buffer to a buffer list
- ofc_queue_first - Get the first item on the buffer list
- ofc_queue_next - Get the subsequent item on a buffer list
- ofc_get_error_string - Convert a last error into a string

It is clear from the list of APIs used between synchronous and asynchronous
file copy that the asynchronous mode is more complex but it can offer
considerable performance improvements

This is the full list of APIs required for either mode.  This should help in
understanding the level of effort in integrating openfiles with a customer
application.

There are a few features of Open Files which allow this simple set of APIs:

- Implicit Framework Initialization and Destruction.  No explicit
initialization required although explicit and static initialization is
supported.
- Implicit Remote Connections.  Connections to remotes do not need to be
explicitly established.  Remote URLs are examined and if the URL is to a
remote that does not have a connection, a connection will be established
and authenticated.  Connections are closed when idle.
- Implicit Share Mounting.  Mounting of a share is performed implicity when
accessing a file through the URL.  No explicit mounting or unmounting of
a share is required.  Shares are dismounted when idle.
- Integrated local and remote file APIs.  No need to be aware of whether a
file is local or remote.  The framework handles the difference internally.

