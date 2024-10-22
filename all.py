all.py
-----------------

import paramiko
import pynetbox
import pandas as pd
import re
import os


file_path = '/home/tcs/router_details.xlsx'
data = pd.read_excel(file_path, engine='openpyxl')

router_ips = data['Router_Ips'].tolist()
router_names = data['Router_Names'].tolist()
usernames = data['Username'].tolist()
passwords = data['Password'].tolist()
NETBOX_URL = data['Netbox_url'].iloc[0]
NETBOX_TOKEN = data['Netbox_token'].iloc[0]

print("Router IPs:", router_ips)
print("Router Names:", router_names)


router_map = dict(zip(router_ips, router_names))
username = usernames[1]
password = passwords[1]
nb = pynetbox.api(NETBOX_URL, token=NETBOX_TOKEN)
aslis, asplis = [], []
al, tcl, ol = [], [], []
rack_name = "Rack1"

ssh_client = paramiko.SSHClient()
ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())


for router_ip, router_name in router_map.items():
    ssh_client.connect(router_ip, username=username, password=password)


    stdin, stdout, stderr = ssh_client.exec_command("show environment fan detail")
    output = stdout.read().decode()
    stdin.close()

    print(f"\n### {router_name} Fan Speed ###\n")
    print(output)
    fan_pattern = r"\s[0-9]{2}\s"
    fan_match = re.findall(fan_pattern, output)
    fan_list = [int(ele.strip()) for ele in fan_match]
    fan_sum = sum(fan_list)
    print(f"Average speed percentage is : {fan_sum / 6}")
    asplis.append(float(fan_sum / 6))

    rpm_pattern = r"\s[0-9]{4,5}\s"
    rpm_match = re.findall(rpm_pattern, output)
    rpm_list = [int(ele.strip()) for ele in rpm_match]
    rpm_sum = sum(rpm_list)
    print(f"Average Speed is : {rpm_sum / 6}")
    aslis.append(float(rpm_sum / 6))


    stdin, stdout, stderr = ssh_client.exec_command("show inventory chassis")
    output = stdout.read().decode()
    stdin.close()

    print(f"\n### {router_name} Serial Number ###\n")
    print(output)
    serial_pattern = r"SN: (\w+)"
    serial_match = re.search(serial_pattern, output)
    if serial_match:
        sn = serial_match.group(1)
        print(f"Serial Number: {sn}")
    else:
        sn = None


    stdin, stdout, stderr = ssh_client.exec_command("show environment power")
    output = stdout.read().decode()
    stdin.close()

    print(f"\n### {router_name} Power Utilization ###\n")
    print(output)

    power_details = {}
    lines = output.splitlines()
    for line in lines:
        if "Total Power Output (actual draw)" in line:
            value2 = ''.join(filter(lambda x: x.isdigit() or x == '.', line.split(":")[-1].strip()))
            power_details['output'] = float(value2)
        elif "Total Power Input (actual draw)" in line:
            value1 = ''.join(filter(lambda x: x.isdigit() or x == '.', line.split(":")[-1].strip()))
            power_details['input'] = float(value1)
        elif "Total Power Capacity" in line:
            value = ''.join(filter(lambda x: x.isdigit() or x == '.', line.split(":")[-1].strip()))
            power_details['capacity'] = float(value)

    al.append(power_details.get('output', 0))
    tcl.append(power_details.get('input', 0))
    ol.append(power_details.get('capacity', 0))


    stdin, stdout, stderr = ssh_client.exec_command("show interface mgmt0")
    output = stdout.read().decode()
    stdin.close()

    print(f"\n### {router_name} MAC and Active Status ###\n")
    print(output)

    mac_pattern = r"([0-9a-f]{4}\.[0-9a-f]{4}\.[0-9a-f]{4})"
    mac_match = re.search(mac_pattern, output)
    if mac_match:
        mac = mac_match.group(1)
        formatted_mac = mac.replace('.', '')
        truncated_mac = ':'.join(formatted_mac[i:i + 2] for i in range(0, len(formatted_mac), 2)).lower()[:10]


        arp_scan_output = os.popen('arp-scan --localnet').read()
        device_status = "active" if router_ip in arp_scan_output and truncated_mac in arp_scan_output else "offline"
    else:
        device_status = "offline"
        mac = None


    device = nb.dcim.devices.get(name=router_name)
    if device:
        device.update({
            "serial": sn,
            "custom_fields": {
                "MAC_Address": mac
            },
            "status": device_status
        })
        print(f"Updated {router_name} in NetBox with serial and MAC address.")
    else:
        print(f"Device {router_name} not found in NetBox.")


average_speed = int(sum(aslis) / len(aslis)) if aslis else 0
average_percentage = int(sum(asplis) / len(asplis)) if asplis else 0
input_sum = str(sum(tcl))
output_sum =int(sum(ol))

rack = nb.dcim.racks.get(name=rack_name)
if rack:
    rack.update({
        "custom_fields": {
            "Average_Speed": average_speed,
            "Average_Fan_Speed_Percentage": average_percentage,
            "Power_Input": input_sum,
            "Power_Output": output_sum,
            "Power_Utilization1": int((sum(al) / 10000) * 100)
        }
    })
    print(f"Updated rack {rack_name} in NetBox.")
else:
    print(f"Rack {rack_name} not found in NetBox.")

ssh_client.close()


output:
--------

Router IPs: ['10.133.35.148', '10.133.35.150', '10.133.35.152', '10.133.35.143']
Router Names: ['n9k1', 'n9k2', 'n9k3', 'n9k4']

### n9k1 Fan Speed ###

Fan:
---------------------------------------------------------------------------
Fan             Model                Hw     Direction       Status
---------------------------------------------------------------------------
Fan1(sys_fan1)  N9K-C9300-FAN2       --     front-to-back   Ok
Fan2(sys_fan2)  N9K-C9300-FAN2       --     front-to-back   Ok
Fan3(sys_fan3)  N9K-C9300-FAN2       --     front-to-back   Ok
Fan_in_PS1      --                   --     front-to-back   Ok
Fan_in_PS2      --                   --     front-to-back   Shutdown
Fan Zone Speed: Zone 1: 0x80
Fan Air Filter : NotSupported
Fan:
------------------------------------------------------------------
 Fan Name          Fan Num   Fan Direction   Speed(%)  Speed(RPM)
------------------------------------------------------------------
Fan1(sys_fan1)      fan1    front-to-back    64        10693
Fan1(sys_fan1)      fan2    front-to-back    59        7747
Fan2(sys_fan2)      fan1    front-to-back    63        10465
Fan2(sys_fan2)      fan2    front-to-back    60        7860
Fan3(sys_fan3)      fan1    front-to-back    63        10526
Fan3(sys_fan3)      fan2    front-to-back    60        7826

Average speed percentage is : 61.5
Average Speed is : 9186.166666666666

### n9k1 Serial Number ###

NAME: "Chassis",  DESCR: "Nexus9000 C9396PX Chassis"
PID: N9K-C9396PX         ,  VID: V02 ,  SN: SAL1927J6P3


Serial Number: SAL1927J6P3

### n9k1 Power Utilization ###

Power Supply:
Voltage: 12 Volts
Power                      Actual             Actual        Total
Supply    Model            Output             Input        Capacity     Status
                           (Watts )           (Watts )     (Watts )
-------  ----------  ---------------  ------  ----------  --------------------
1        N9K-PAC-650W          160 W              174 W       650 W      Ok
2        N9K-PAC-650W            0 W                0 W         0 W   Shutdown


Power Usage Summary:
--------------------
Power Supply redundancy mode (configured)                PS-Redundant
Power Supply redundancy mode (operational)               Non-Redundant

Total Power Capacity (based on configured mode)             650.00 W
Total Grid-A (first half of PS slots) Power Capacity        650.00 W
Total Grid-B (second half of PS slots) Power Capacity         0.00 W
Total Power of all Inputs (cumulative)                      650.00 W
Total Power Output (actual draw)                            160.00 W
Total Power Input (actual draw)                             174.00 W
Total Power Allocated (budget)                                N/A
Total Power Available for additional modules                  N/A



### n9k1 MAC and Active Status ###

mgmt0 is up
admin state is up,
  Hardware: GigabitEthernet, address: 5897.bd00.9cd2 (bia 5897.bd00.9cd2)
  Internet Address is 10.133.35.148/27
  MTU 1500 bytes, BW 1000000 Kbit , DLY 10 usec
  reliability 255/255, txload 1/255, rxload 1/255
  Encapsulation ARPA, medium is broadcast
  full-duplex, 1000 Mb/s
  Auto-Negotiation is turned on
  Auto-mdix is turned off
  EtherType is 0x0000
  1 minute input rate 1904 bits/sec, 0 packets/sec
  1 minute output rate 24 bits/sec, 0 packets/sec
  Rx
    12934826 input packets 841688 unicast packets 10528764 multicast packets
    1564374 broadcast packets 1860852756 bytes
  Tx
    794386 output packets 572881 unicast packets 221436 multicast packets
    69 broadcast packets 277185117 bytes
  Active connector: RJ45



Updated n9k1 in NetBox with serial and MAC address.

### n9k2 Fan Speed ###

Fan:
---------------------------------------------------------------------------
Fan             Model                Hw     Direction       Status
---------------------------------------------------------------------------
Fan1(sys_fan1)  N9K-C9300-FAN2-B     --     back-to-front   Ok
Fan2(sys_fan2)  N9K-C9300-FAN2-B     --     back-to-front   Ok
Fan3(sys_fan3)  N9K-C9300-FAN2-B     --     back-to-front   Ok
Fan_in_PS1      --                   --     back-to-front   Ok
Fan_in_PS2      --                   --     back-to-front   Shutdown
Fan Zone Speed: Zone 1: 0x80
Fan Air Filter : NotSupported
Fan:
------------------------------------------------------------------
 Fan Name          Fan Num   Fan Direction   Speed(%)  Speed(RPM)
------------------------------------------------------------------
Fan1(sys_fan1)      fan1    back-to-front    60        10000
Fan1(sys_fan1)      fan2    back-to-front    59        7747
Fan2(sys_fan2)      fan1    back-to-front    61        10131
Fan2(sys_fan2)      fan2    back-to-front    60        7860
Fan3(sys_fan3)      fan1    back-to-front    59        9890
Fan3(sys_fan3)      fan2    back-to-front    59        7769

Average speed percentage is : 59.666666666666664
Average Speed is : 8899.5

### n9k2 Serial Number ###

NAME: "Chassis",  DESCR: "Nexus9000 C9396PX Chassis"
PID: N9K-C9396PX         ,  VID: V02 ,  SN: SAL18401MPT


Serial Number: SAL18401MPT

### n9k2 Power Utilization ###

Power Supply:
Voltage: 12 Volts
Power                      Actual             Actual        Total
Supply    Model            Output             Input        Capacity     Status
                           (Watts )           (Watts )     (Watts )
-------  ----------  ---------------  ------  ----------  --------------------
1        N9K-PAC-650W-B        155 W              176 W       650 W      Ok
2        N9K-PAC-650W-B          0 W                0 W         0 W   Shutdown


Power Usage Summary:
--------------------
Power Supply redundancy mode (configured)                PS-Redundant
Power Supply redundancy mode (operational)               Non-Redundant

Total Power Capacity (based on configured mode)             650.00 W
Total Grid-A (first half of PS slots) Power Capacity        650.00 W
Total Grid-B (second half of PS slots) Power Capacity         0.00 W
Total Power of all Inputs (cumulative)                      650.00 W
Total Power Output (actual draw)                            155.00 W
Total Power Input (actual draw)                             176.00 W
Total Power Allocated (budget)                                N/A
Total Power Available for additional modules                  N/A



### n9k2 MAC and Active Status ###

mgmt0 is up
admin state is up,
  Hardware: GigabitEthernet, address: fc5b.39f7.7d6c (bia fc5b.39f7.7d6c)
  Internet Address is 10.133.35.150/27
  MTU 1500 bytes, BW 1000000 Kbit , DLY 10 usec
  reliability 255/255, txload 1/255, rxload 1/255
  Encapsulation ARPA, medium is broadcast
  full-duplex, 1000 Mb/s
  Auto-Negotiation is turned on
  Auto-mdix is turned off
  EtherType is 0x0000
  1 minute input rate 1872 bits/sec, 0 packets/sec
  1 minute output rate 24 bits/sec, 0 packets/sec
  Rx
    12433312 input packets 361644 unicast packets 10528728 multicast packets
    1542940 broadcast packets 1738640100 bytes
  Tx
    526128 output packets 304680 unicast packets 221436 multicast packets
    12 broadcast packets 189782334 bytes
  Active connector: RJ45



Updated n9k2 in NetBox with serial and MAC address.

### n9k3 Fan Speed ###

Fan:
---------------------------------------------------------------------------
Fan             Model                Hw     Direction       Status
---------------------------------------------------------------------------
Fan1(sys_fan1)  N9K-C9300-FAN2-B     --     back-to-front   Ok
Fan2(sys_fan2)  N9K-C9300-FAN2-B     --     back-to-front   Ok
Fan3(sys_fan3)  N9K-C9300-FAN2-B     --     back-to-front   Ok
Fan_in_PS1      --                   --     back-to-front   Shutdown
Fan_in_PS2      --                   --     back-to-front   Ok
Fan Zone Speed: Zone 1: 0x80
Fan Air Filter : NotSupported
Fan:
------------------------------------------------------------------
 Fan Name          Fan Num   Fan Direction   Speed(%)  Speed(RPM)
------------------------------------------------------------------
Fan1(sys_fan1)      fan1    back-to-front    60        9926
Fan1(sys_fan1)      fan2    back-to-front    61        7941
Fan2(sys_fan2)      fan1    back-to-front    58        9729
Fan2(sys_fan2)      fan2    back-to-front    61        8011
Fan3(sys_fan3)      fan1    back-to-front    60        9908
Fan3(sys_fan3)      fan2    back-to-front    61        8059

Average speed percentage is : 60.166666666666664
Average Speed is : 8929.0

### n9k3 Serial Number ###

NAME: "Chassis",  DESCR: "Nexus9000 C9396PX Chassis"
PID: N9K-C9396PX         ,  VID: V02 ,  SN: SAL1911B602


Serial Number: SAL1911B602

### n9k3 Power Utilization ###

Power Supply:
Voltage: 12 Volts
Power                      Actual             Actual        Total
Supply    Model            Output             Input        Capacity     Status
                           (Watts )           (Watts )     (Watts )
-------  ----------  ---------------  ------  ----------  --------------------
1        N9K-PAC-650W-B          0 W                0 W         0 W   Shutdown
2        N9K-PAC-650W-B        158 W              175 W       650 W      Ok


Power Usage Summary:
--------------------
Power Supply redundancy mode (configured)                PS-Redundant
Power Supply redundancy mode (operational)               Non-Redundant

Total Power Capacity (based on configured mode)             650.00 W
Total Grid-A (first half of PS slots) Power Capacity          0.00 W
Total Grid-B (second half of PS slots) Power Capacity       650.00 W
Total Power of all Inputs (cumulative)                      650.00 W
Total Power Output (actual draw)                            158.00 W
Total Power Input (actual draw)                             175.00 W
Total Power Allocated (budget)                                N/A
Total Power Available for additional modules                  N/A



### n9k3 MAC and Active Status ###

mgmt0 is up
admin state is up,
  Hardware: GigabitEthernet, address: 74a2.e6e8.6358 (bia 74a2.e6e8.6358)
  Internet Address is 10.133.35.152/27
  MTU 1500 bytes, BW 1000000 Kbit , DLY 10 usec
  reliability 255/255, txload 1/255, rxload 1/255
  Encapsulation ARPA, medium is broadcast
  full-duplex, 1000 Mb/s
  Auto-Negotiation is turned on
  Auto-mdix is turned off
  EtherType is 0x0000
  1 minute input rate 1976 bits/sec, 0 packets/sec
  1 minute output rate 24 bits/sec, 0 packets/sec
  Rx
    12443895 input packets 346007 unicast packets 10531307 multicast packets
    1566581 broadcast packets 1747327924 bytes
  Tx
    494433 output packets 272935 unicast packets 221488 multicast packets
    10 broadcast packets 150329802 bytes
  Active connector: RJ45



Updated n9k3 in NetBox with serial and MAC address.

### n9k4 Fan Speed ###

Fan:
---------------------------------------------------------------------------
Fan             Model                Hw     Direction       Status
---------------------------------------------------------------------------
Fan1(sys_fan1)  N9K-C9300-FAN2-B     --     back-to-front   Ok
Fan2(sys_fan2)  N9K-C9300-FAN2-B     --     back-to-front   Ok
Fan3(sys_fan3)  N9K-C9300-FAN2-B     --     back-to-front   Ok
Fan_in_PS1      --                   --     back-to-front   Shutdown
Fan_in_PS2      --                   --     back-to-front   Ok
Fan Zone Speed: Zone 1: 0x80
Fan Air Filter : NotSupported
Fan:
------------------------------------------------------------------
 Fan Name          Fan Num   Fan Direction   Speed(%)  Speed(RPM)
------------------------------------------------------------------
Fan1(sys_fan1)      fan1    back-to-front    61        10169
Fan1(sys_fan1)      fan2    back-to-front    61        8023
Fan2(sys_fan2)      fan1    back-to-front    61        10150
Fan2(sys_fan2)      fan2    back-to-front    61        8011
Fan3(sys_fan3)      fan1    back-to-front    61        10150
Fan3(sys_fan3)      fan2    back-to-front    60        7837

Average speed percentage is : 60.833333333333336
Average Speed is : 9056.666666666666

### n9k4 Serial Number ###

NAME: "Chassis",  DESCR: "Nexus9000 C9396PX Chassis"
PID: N9K-C9396PX         ,  VID: V02 ,  SN: SAL18411YGQ


Serial Number: SAL18411YGQ

### n9k4 Power Utilization ###

Power Supply:
Voltage: 12 Volts
Power                      Actual             Actual        Total
Supply    Model            Output             Input        Capacity     Status
                           (Watts )           (Watts )     (Watts )
-------  ----------  ---------------  ------  ----------  --------------------
1        N9K-PAC-650W-B          0 W                0 W         0 W   Shutdown
2        N9K-PAC-650W-B        158 W              178 W       650 W      Ok


Power Usage Summary:
--------------------
Power Supply redundancy mode (configured)                PS-Redundant
Power Supply redundancy mode (operational)               Non-Redundant

Total Power Capacity (based on configured mode)             650.00 W
Total Grid-A (first half of PS slots) Power Capacity          0.00 W
Total Grid-B (second half of PS slots) Power Capacity       650.00 W
Total Power of all Inputs (cumulative)                      650.00 W
Total Power Output (actual draw)                            158.00 W
Total Power Input (actual draw)                             178.00 W
Total Power Allocated (budget)                                N/A
Total Power Available for additional modules                  N/A



### n9k4 MAC and Active Status ###

mgmt0 is up
admin state is up,
  Hardware: GigabitEthernet, address: f40f.1bc2.bf3e (bia f40f.1bc2.bf3e)
  Internet Address is 10.133.35.143/27
  MTU 1500 bytes, BW 1000000 Kbit , DLY 10 usec
  reliability 255/255, txload 1/255, rxload 1/255
  Encapsulation ARPA, medium is broadcast
  full-duplex, 1000 Mb/s
  Auto-Negotiation is turned on
  Auto-mdix is turned off
  EtherType is 0x0000
  1 minute input rate 1976 bits/sec, 0 packets/sec
  1 minute output rate 32 bits/sec, 0 packets/sec
  Rx
    19834184 input packets 4342471 unicast packets 12475623 multicast packets
    3016090 broadcast packets 4424942315 bytes
  Tx
    961577 output packets 699529 unicast packets 262037 multicast packets
    11 broadcast packets 263578116 bytes
  Active connector: RJ45



Updated n9k4 in NetBox with serial and MAC address.
Updated rack Rack1 in NetBox.
