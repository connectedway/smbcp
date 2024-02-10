import asyncio
import subprocess

SPIRITDC = 0
SPIRITDCB = 1

#
# Hosts Configuration.
#
# This table holds the currently active firewall configuration.
# The initial state is not used.  It will be updated when we
# reset the firewall.
#
hosts = [
    {"ip": "172.31.17.154", "state": "enabled", "toggle": False},
    {"ip": "172.31.30.112", "state": "disabled", "toggle": False},
]


def allow(ip_address):
    """
    Add an allow input and output rules to the Ubuntu firewall

    Args:
        ip_address (str): The IP address to allow
    """

    #
    # Run the firewall command
    #
    try:
        subprocess.run(["sudo", "ufw", "allow", "from", ip_address], check=True)
        subprocess.run(["sudo", "ufw", "allow", "out", "to", ip_address], check=True)
    except subprocess.CalledProcessError as error:
        print(f"Error adding UFW rules for IP {ip_address}: {error}")


def deny(ip_address):
    """
    Add a deny input and output rules to the Ubuntu firewall

    Args:
        ip_address (str): The IP address to deny
    """

    #
    # Run the firewall command
    #
    try:
        subprocess.run(["sudo", "ufw", "deny", "from", ip_address], check=True)
        subprocess.run(["sudo", "ufw", "deny", "out", "to", ip_address], check=True)
    except subprocess.CalledProcessError as error:
        print(f"Error adding UFW rules for IP {ip_address}: {error}")


def enable():
    """
    Enable the firewall

    Args:
        None
    """
    #
    # Run the firewall command
    #
    try:
        subprocess.run(["sudo", "ufw", "enable"], check=True)
    except subprocess.CalledProcessError as error:
        print(f"Error enabling UFW: {error}")


def disable():
    """
    Disable the firewall

    Args:
        None
    """
    #
    # Run the firewall command
    #
    try:
        subprocess.run(["sudo", "ufw", "disable"], check=True)
    except subprocess.CalledProcessError as error:
        print(f"Error enabling UFW: {error}")


class StateMachine:
    """
    UFW Asynchronous State Machine

    We manage the state asynchronously so we can have an asyncrhonous
    state transitions intermixed with user input
    """

    def __init__(self):
        self.loop = asyncio.get_running_loop()
        self.interval = 0
        self.timer_task = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        pass

    async def read_input(self):
        """
        Asyncrounously Read Input from Console
        """
        command = await self.loop.run_in_executor(None, input, "awsdfs_ufw: ")
        return command

    def status(self):
        """
        Perform a status of the firewall
        """
        try:
            subprocess.run(["sudo", "ufw", "status", "numbered"], check=True)

        except subprocess.CalledProcessError as error:
            print(f"Error getting UFW status: {error}")

    def reset(self):
        """
        Reset the firewall
        """
        try:
            subprocess.run(["sudo", "ufw", "--force", "reset"], check=True)

        except subprocess.CalledProcessError as error:
            print(f"Error resetting UFW rules: {error}")
        #
        # Reset our state.
        #
        for i in range(2):
            allow(hosts[i]["ip"])
            hosts[i]["state"] = "enabled"
            hosts[i]["toggle"] = False

        #
        # Add the catch all rules to allow traffic from all and to all
        #
        # We add this, although we'd rather not.  The problem is, if the
        # system crashes while the firewall is active, you will not be able
        # to get to the system over the network.  We could be more specific
        # and say, we allow ssh or rdp traffic throught the VPN.  But this
        # is easier.
        #
        try:
            subprocess.run(
                ["sudo", "ufw", "allow", "from", "any", "to", "any"], check=True
            )
        except subprocess.CalledProcessError as error:
            print(f"Error adding default UFW rules: {error}")
        #
        # Now enable the firewall
        #
        enable()

    def allow(self, ip):
        """
        Add an allow rule for the ip

        NOTE: This is here for future only.  It is not currently called

        Args:
            ip (str): IP address to allow traffic to and from
        """
        allow(ip)

    def deny(self, host):
        """
        Add an deny rule for the ip

        Args:
            host (str): host name to deny traffic to and from
        """
        #
        # Convert the host name to an IP
        #
        if host == "spiritdc":
            ip = hosts[SPIRITDC]["ip"]
        elif host == "spiritdcb":
            ip = hosts[SPIRITDCB]["ip"]
        else:
            print(f"Bad host name")
            return
        #
        # Deny traffic to and from the ip
        #
        deny(ip)

    def toggle(self, host):
        """
        Toggle the enable/disable status of the host
        """
        if host == "spiritdc":
            hosts[SPIRITDC]["toggle"] = True
        elif host == "spiritdcb":
            hosts[SPIRITDCB]["toggle"] = True
        else:
            print(f"Bad host name")
            return

    async def run_timer(self):
        """
        The toggle timer
        """
        while True:
            try:
                #
                # Sleep for the requisite time
                #
                await asyncio.sleep(self.interval)
                #
                # Now for both hosts, if toggling, change state
                #
                for i in [SPIRITDC, SPIRITDCB]:
                    if hosts[i]["toggle"]:
                        if hosts[i]["state"] == "enabled":
                            #
                            # Currently enabled, deny
                            #
                            deny(hosts[i]["ip"])
                            hosts[i]["state"] = "disabled"
                        else:
                            #
                            # Currently denied, enable
                            #
                            allow(hosts[i]["ip"])
                            hosts[i]["state"] = "enabled"
            except asyncio.CancelledError:
                self.timer_task = None
                break

    async def run(self):
        """
        The asynchronou run routine for the State Machine
        """
        try:
            while True:
                #
                # Commands:
                #
                # Firewall state:
                #     both up
                #     spiritdc up
                #     piritdc up
                #     toggleing
                #
                # disable spiritdc [-toggle]
                # disable piritdcb [-toggle]
                # reset
                # reset enables the firewall and
                #    allows input and output on all
                #    sets up two state spiritdc and spiritdcb
                #    the state for each is [up, down]
                #    a toggle [on off]
                # host[spiritdc].state = up | down
                # host[spiritdc].toggle = on | off
                #
                # a reset sets state to up for both hosts
                # and sets toggle to off
                #
                # when a timer fires, we go through hosts
                # if a host has toggle on, wwe'll toggle the state
                #
                # commands
                #  reset
                #  quit
                #  deny spiritdc -toggle
                #  deny spiritdcb -toggle
                #
                # initial state is same as reset
                #
                command = await self.read_input()
                parts = command.split()
                if len(parts) > 0:
                    if parts[0] == "quit":
                        disable()
                        break
                    elif parts[0] == "reset":
                        self.reset()
                    elif parts[0] == "status":
                        self.status()
                    elif parts[0] == "help":
                        print(f"Valid Commands:")
                        print(f"   quit: reset firewall and quit")
                        print(f"   reset: reset firewall")
                        print(f"   help: print this text")
                        print(f"   deny spiritdc | spiritdcb [-toggle]:")
                        print(f"       disable spiritdc or spiritdcb")
                        print(f"       -toggle: periodically reenable")
                    elif parts[0] == "deny":
                        if len(parts) > 1:
                            host = parts[1]
                            self.deny(host)
                            if len(parts) > 2:
                                if parts[2] == "-toggle":
                                    self.toggle(host)
                                else:
                                    print(f"unrecognized option")
                        else:
                            print(f"requires host spiritdc or spiritdcb")
                    else:
                        print(f"Valid commands: quit, reset, deny")

        except asyncio.CancelledError:
            pass
        finally:
            if self.timer_task:
                self.timer_task.cancel()

    async def start_timer(self, interval):
        """
        Start the timer at specified interval
        """
        self.interval = interval
        self.timer_task = asyncio.create_task(self.run_timer())

    def stop_timer(self):
        """
        Stop the timer
        """
        if self.timer_task is not None:
            self.timer_task.cancel()


async def main():
    """
    Main asynchronous Routine
    """
    #
    # Intantitae the state machine
    #
    state_machine = StateMachine()

    # Schedule timers as needed within the state machine
    await state_machine.start_timer(5)

    # Run both coroutines concurrently
    await state_machine.run()


#
# If run from the command line, run the main routine
#
if __name__ == "__main__":
    asyncio.run(main())
