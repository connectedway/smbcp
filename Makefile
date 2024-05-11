CC = gcc
DESTDIR ?= /usr/local
BINDIR ?= bin/openfiles
ROOT ?= /root

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

.PHONY: test_awsdfs
test_awsdfs:
	pytest test/test_awsdfs.py

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
	install -d $(DESTDIR)/$(ROOT)/test
	install -m 755 test/conftest.py $(DESTDIR)/$(ROOT)/test
	install -m 755 test/test_dfs.py $(DESTDIR)/$(ROOT)/test
	install -m 755 test/dfs_iptables.py $(DESTDIR)/$(ROOT)/test

uninstall:
	@-rm $(DESTDIR)/$(BINDIR)/smbcp 2> /dev/null || true
	@-rm $(DESTDIR)/$(BINDIR)/smbrm 2> /dev/null || true
	@-rm $(DESTDIR)/$(BINDIR)/smbfree 2> /dev/null || true
	@-rm $(DESTDIR)/$(BINDIR)/smbls 2> /dev/null || true
	@-rmdir $(DESTDIR)/$(BINDIR) 2> /dev/null || true
