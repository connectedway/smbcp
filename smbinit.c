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
#include <ofc/waitset.h>
#include <ofc/queue.h>
#include <of_smb/framework.h>

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
void smbcp_init(void)
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
  of_smb_startup(OFC_HANDLE_NULL);
#endif
}

#if !defined(INIT_ON_LOAD)
void smbcp_configure(void)
{
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
   * though this should be a unique number.  We are passing in a 
   * string.  Make sure it is null terminated.
   */
  static const OFC_CHAR uuid[] = 
  {
    0x04, 0x5d, 0x88, 0x8a, 0xeb, 0x1c, 0xc9, 0x11,
    0x9f, 0xe8, 0x08, 0x00, 0x2b, 0x10, 0x48, 0x60,
    0x00
  };
  ofc_framework_set_uuid(uuid);
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

/**
 * Routine to deactivate the openfiles stack.
 *
 * This can be called implicitly on exit by setting the build
 * configuration variable INIT_ON_LOAD.  When performing manual
 * initialization, this should be called when shutting down the stack
 */
void smbcp_deactivate(void)
{
  /*
   * Shutdown and deactivate SMB
   */
  of_smb_shutdown();
  of_smb_destroy();
  /*
   * Shutdown and deactivate the core framework
   */
  ofc_framework_shutdown();
  ofc_framework_destroy();
}
#endif

