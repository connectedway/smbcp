CC ?= gcc
DESTDIR ?= /usr/local
BINDIR ?= bin/openfiles

all: smbcp

smbcp: smbcp.o
	$(CC) $(LDFLAGS) -o $@ $< -Wl,--no-as-needed -lof_smb_shared -lof_core_shared -lmbedtls -lkrb5 -lgssapi_krb5 

%.o: %.c
	$(CC) -g -c $(CFLAGS) -o $@ $< 

clean:
	rm -f smbcp.o smbcp

install:
	install -d $(DESTDIR)/$(BINDIR)
	install -m 755 smbcp $(DESTDIR)/$(BINDIR)

uninstall:
	@-rm $(DESTDIR)/$(BINDIR)/smbcp 2> /dev/null || true
	@-rmdir $(DESTDIR)/$(BINDIR) 2> /dev/null || true
