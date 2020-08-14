# ZeroConfTransfer
COMP3010 Summer 2020 Term Project

## Overview 
A simple python program that transfer arbitrarily file from one computer to another on on the same local network.

Every other day on one of the Linux forum I usually visit, there will be a post asking for help on how to properly setup samba for transferring files between computer.

If samba works, it works perfectly. But in fact most of the time people are wasting their time on configuring and troubleshooting samba, while the old way of using a thumb drive to transfer files are way faster.

This is a CLI program with minimizing time wasted on configuration in mind. It's easy to use and runs anywhere python3 runs. 

## Usage

To transfer a file:

```
ZeroconfTransfer.py file_to_send 
```

Or just to transfer a string:

```
echo "string" | ZeroconfTransfer.py
```
--------------------------
A 4-digit random connection code will be provided like this:

```
Connection code: 5357
```


--------------------------

On the computer receiving the file, just run it without any parameter:

```
ZeroconfTransfer.py
```

The file will be saved to your current working directory, or the string will be displayed on the console:

```
string
Done.
```

## Current Limitation
1. Cannot transfer folder.
2. Cannot transfer large files (>10MB) will corrupt.
3. Cannot transfer video and audio files, file will corrupt.
4. zip, 7z, picture, binary files will have a high chance of corruption.
5. Non UTF-8 file will be unreadable.
6. It will crash if transferring string (pass from `stdin`) AND the program cannot figure out by itself which IP address to use.

Small files like DOCX, PDF and plain text files will work just fine.

## Implementation details
The program have 3 states, transmitting string, transmitting file, and receiving.

### Transmitting
The program will try to figure out which IP to use first.
1. Try what `socket.gethostbyname(socket.gethostname())` gives
    - If starts with `192.168`, use it.
    - Enumerate all the IP addresses, try to find the one start with `192.168`.
        - if nothing found, exit.
        - if there are multiple addresses starts with `192.168`, let the user choose one. Otherwise use it.
        - if there are multiple addresses that does not starts with `192.168`, let the user choose one.
2. Register zeroconf service, and generate the connection code.
    - zeroconf name will look like this:
        ```
        1234@._ishare._udp.local.
        ```
        Where `1234` is the connection code.
3. Wait for the `Hi` message from receiver.
4. Send the header and the file.
    - If transmitting file, the header will look like this:
        ```
        filename
        file size
        md5hash
        file_content
        ```
    - If transmitting string, the header will look like this:
        ```
        **stdin**
        string
        ```
5. Clean up.

### Receiving
1. Select node by connection code given from sender, by using zeroconf.
2. Send `Hi` message to sender.
3. Receive data
4. Check MD5, warn user if it doesn't match

## Library used
1. `zeroconf`
    
    Used to discover the sender and announce the IP address to the receiver. 

2. `hashlib`

    Used to calculate the MD5 checksum of the file. The checksum of received file will be compared with the original one, and warn the user if they differ.

3. `tqdm`

    Used to visualize the progress of transfer and elapsed time.

4.  `pstuil`

    Used to get the correct IP address from the host.
    
    Some hosts' network stack is really messed up, for example a computer with WSL2, Hyper-V, VMware and all kinds of VPN installed will have a bunch of network interfaces, thus more than a bunch of IP addresses, while usually 1 or 2 of them are the one to use.


# Reference
https://stackoverflow.com/questions/3431825/generating-an-md5-checksum-of-a-file

https://stackoverflow.com/questions/1118028/file-containing-its-own-checksum

https://stackoverflow.com/questions/13993514/sending-receiving-file-udp-in-python