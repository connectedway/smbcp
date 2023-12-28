CC = gcc
DESTDIR ?= /usr/local
BINDIR ?= bin/openfiles

all: smbcp smbrm smbfree smbls

smbcp: smbcp.o
	$(CC) $(LDFLAGS) -o $@ $< -Wl,--no-as-needed -lof_smb_shared -lof_core_shared -lssl -lkrb5 -lgssapi_krb5 

smbrm: smbrm.o
	$(CC) $(LDFLAGS) -o $@ $< -Wl,--no-as-needed -lof_smb_shared -lof_core_shared -lssl -lkrb5 -lgssapi_krb5 

smbfree: smbfree.o
	$(CC) $(LDFLAGS) -o $@ $< -Wl,--no-as-needed -lof_smb_shared -lof_core_shared -lssl -lkrb5 -lgssapi_krb5 

smbls: smbls.o
	$(CC) $(LDFLAGS) -o $@ $< -Wl,--no-as-needed -lof_smb_shared -lof_core_shared -lssl -lkrb5 -lgssapi_krb5 

%.o: %.c
	$(CC) -g -c $(CFLAGS) -o $@ $< 

clean:
	rm -f smbcp.o smbcp
	rm -f smbrm.o smbrm
	rm -f smbfree.o smbfree
	rm -f smbls.o smbls

install:
	install -d $(DESTDIR)/$(BINDIR)
	install -m 755 smbcp $(DESTDIR)/$(BINDIR)
	install -m 755 smbrm $(DESTDIR)/$(BINDIR)
	install -m 755 smbfree $(DESTDIR)/$(BINDIR)
	install -m 755 smbls $(DESTDIR)/$(BINDIR)
	ldconfig

uninstall:
	@-rm $(DESTDIR)/$(BINDIR)/smbcp 2> /dev/null || true
	@-rm $(DESTDIR)/$(BINDIR)/smbrm 2> /dev/null || true
	@-rm $(DESTDIR)/$(BINDIR)/smbfree 2> /dev/null || true
	@-rm $(DESTDIR)/$(BINDIR)/smbls 2> /dev/null || true
	@-rmdir $(DESTDIR)/$(BINDIR) 2> /dev/null || true
