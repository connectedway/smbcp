import asyncio
import subprocess

SPIRITDC = 0
SPIRITDCB = 1


hosts = [
    {"ip": "172.31.17.154", "state": "enabled", "toggle": False},
    {"ip": "172.31.30.112", "state": "disabled", "toggle": False},
]


def manage_ip_rulesx(ip_address, state):
    pass


def allow(ip_address):
    try:
        subprocess.run(["sudo", "ufw", "allow", "from", ip_address], check=True)
        subprocess.run(["sudo", "ufw", "allow", "out", "to", ip_address], check=True)
    except subprocess.CalledProcessError as error:
        print(f"Error adding UFW rules for IP {ip_address}: {error}")


def deny(ip_address):
    try:
        subprocess.run(["sudo", "ufw", "deny", "from", ip_address], check=True)
        subprocess.run(["sudo", "ufw", "deny", "out", "to", ip_address], check=True)
    except subprocess.CalledProcessError as error:
        print(f"Error adding UFW rules for IP {ip_address}: {error}")


def enable():
    try:
        subprocess.run(["sudo", "ufw", "enable"], check=True)
    except subprocess.CalledProcessError as error:
        print(f"Error enabling UFW: {error}")


def disable():
    try:
        subprocess.run(["sudo", "ufw", "disable"], check=True)
    except subprocess.CalledProcessError as error:
        print(f"Error enabling UFW: {error}")


def manage_ip_rules(ip_address, state):
    """
    Manages UFW firewall rules for a given IP address and state.

    Args:
        ip_address (str): The IP address to manage.
        state (str): The desired state ("enabled" or "disabled").
    """

    # Get existing rules with numbers
    rules_output = subprocess.check_output(["sudo", "ufw", "status", "numbered"])
    rules = rules_output.decode().splitlines()

    # Find and delete existing rules for the IP, handling rule numbering
    rule_numbers_to_delete = []
    for i, rule in enumerate(rules):
        if "from" in rule and ip_address in rule:
            rule_numbers_to_delete.append(i + 1)
        if "to" in rule and ip_address in rule:
            rule_numbers_to_delete.append(i + 1)

    # Delete rules in reverse order to avoid numbering issues
    for rule_number in sorted(rule_numbers_to_delete, reverse=True):
        try:
            subprocess.run(["sudo", "ufw", "delete", str(rule_number)], check=True)
        except subprocess.CalledProcessError as error:
            print(f"Error deleting UFW rule {rule_number}: {error}")

    # Add rules based on the state
    if state == "enabled":
        allow(ip_address)
    elif state == "disabled":
        deny(ip_address)
    else:
        print("Invalid state. Please use 'enabled' or 'disabled'.")


class StateMachine:
    def __init__(self):
        self.loop = asyncio.get_running_loop()
        self.interval = 0
        self.timer_task = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        pass

    async def read_input(self):
        command = await self.loop.run_in_executor(None, input, "awsdfs_ufw: ")
        return command

    def reset(self):
        try:
            subprocess.run(["sudo", "ufw", "--force", "reset"], check=True)

            subprocess.run(["sudo", "ufw", "allow", "from", "any", "to", "any"], check=True)

        except subprocess.CalledProcessError as error:
            print(f"Error resetting UFW rules: {error}")

        for i in range(2):
            manage_ip_rules(hosts[i]["ip"], "enabled")
            hosts[i]["state"] = "enabled"
            hosts[i]["toggle"] = False
        enable()

    def allow(self, ip):
        manage_ip_rules(ip, "enabled")

    def deny(self, host):
        if host == "spiritdc":
            ip = hosts[0]["ip"]
        elif host == "spiritdcb":
            ip = hosts[1]["ip"]
        else:
            print(f"Bad host name")
            return

        manage_ip_rules(ip, "disabled")

    def toggle(self, host):
        if host == "spiritdc":
            hosts[0]["toggle"] = True
        elif host == "spiritdcb":
            hosts[1]["toggle"] = True
        else:
            print(f"Bad host name")
            return

    async def run_timer(self):
        while True:
            try:
                await asyncio.sleep(self.interval)
                for i in [0, 1]:
                    if hosts[i]["toggle"]:
                        if hosts[i]["state"] == "enabled":
                            manage_ip_rules(hosts[i]["ip"], "disabled")
                            hosts[i]["state"] = "disabled"
                        else:
                            manage_ip_rules(hosts[i]["ip"], "enabled")
                            hosts[i]["state"] = "enabled"
            except asyncio.CancelledError:
                self.timer_task = None
                break

    async def run(self):
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
                # reest enables the firewall and
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
        self.interval = interval
        self.timer_task = asyncio.create_task(self.run_timer())

    def stop_timer(self):
        if self.timer_task is not None:
            self.timer_task.cancel()


async def main():
    state_machine = StateMachine()

    # Schedule timers as needed within the state machine
    # Example:
    await state_machine.start_timer(5)

    # Run both coroutines concurrently
    await state_machine.run()


if __name__ == "__main__":
    asyncio.run(main())
