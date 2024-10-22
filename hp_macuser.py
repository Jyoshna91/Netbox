import paramiko
import pynetbox
import re
import time

import os
NETBOX_URL = 'http://10.133.35.137:8000'
NETBOX_TOKEN = 'b10f953429d54bcbe45a24445161f863b202089b'

server_ip = '10.133.35.138'
server_username = 'tcs'
server_password = 'tcs123'

hp_device_ip = '10.133.35.134'
hp_username = 'tcs'
device_name = 'HP-2920-24G'
nb = pynetbox.api(NETBOX_URL, token=NETBOX_TOKEN)
ssh_client = paramiko.SSHClient()
ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    ssh_client.connect(server_ip, username=server_username, password=server_password)
    channel = ssh_client.invoke_shell()
    time.sleep(1)
    channel.recv(1000)
    channel.send(f'ssh {hp_username}@{hp_device_ip}\n')
    time.sleep(2)

    output = channel.recv(1000).decode()
    if "yes/no" in output:
        channel.send("yes\n")
        time.sleep(2)
        output = channel.recv(1000).decode()

    channel.send("\n")
    time.sleep(2)

    if channel.recv_ready():
        output = channel.recv(65535).decode()
        #print("Output after pressing Enter:", output)

    channel.send("show system information\n")
    time.sleep(2)

    output = ""
    while channel.recv_ready():
        output += channel.recv(65535).decode()
        output = re.sub(r';\d{1,9}R', '', output)
    #print("\n### HP Device Command Output ###\n")
    #print(output)

    mac_pattern = r"Base MAC Addr\s+:\s+([0-9a-fA-F]{6}-[0-9a-fA-F]{6})"
    serial_pattern = r"Serial Number\s+:\s+(\S+)"


    mac_match = re.search(mac_pattern, output)
    serial_match = re.search(serial_pattern, output)

    if mac_match and serial_match:

        mac_address = mac_match.group(1).replace("-", "")
        formatted_mac = ':'.join(mac_address[i:i+2] for i in range(0, len(mac_address), 2)).lower()


        serial_number = serial_match.group(1).replace("-", "")

        print(f"Extracted MAC Address: {formatted_mac}")
        print(f"Extracted Serial Number: {serial_number}")

        arp_scan = os.popen('sudo arp-scan --localnet').read()
        print(arp_scan)
        arp_match = re.search(r'10\.133\.35\.134\s+([0-9a-fA-F:]{17})',arp_scan)
        print(f"Extracted MAC Address from HP Device : {formatted_mac}")
        if arp_match:
            arp_mac_address = arp_match.group(1)
            print(f"MAC Address from 'arp-scan' for IP 10.133.35.134 : {arp_mac_address}")
        else:
            print("No match Address found for IP 10.133.35.134 in arp-scan output")

        status = "active" if formatted_mac in arp_scan else "offline"

        device = nb.dcim.devices.get(name=device_name)

        if device:
            device.update({
                "serial": serial_number,
                "status": status,
                "custom_fields": {
                    "MAC_Address": formatted_mac
                }
            })
            print(f"\nDevice '{device_name}' updated in NetBox with MAC Address: {formatted_mac} and Serial Number: {serial_number}\n")
        else:
            print(f"Device '{device_name}' not found in NetBox.")
    else:
        print("Could not find Base MAC Addr or Serial Number in the output.")

except Exception as e:
    print(f"An error occurred: {e}")
finally:
    ssh_client.close()
