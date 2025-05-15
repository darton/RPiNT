#!/usr/bin/env bash


if [[ $(id -u) -ne 0 ]]; then
  echo "This script must be executed as root or using sudo"
  exit 99
fi

systemd="$(ps --no-headers -o comm 1)"
if [ ! "${systemd}" = "systemd" ]; then
  echo "This system is not running systemd.  Exiting..."
  exit 100
fi

if dpkg -l | grep -Eqw "gdm3|sddm|lxdm|xdm|lightdm|slim|wdm"; then
  echo "Please use a Lite version of the image"
  echo "Exiting..."
  exit 101
fi

repourl=https://github.com/darton/RPiNT/archive/refs/heads/master.zip
downloaddir=/tmp
unpackdir=/tmp/RPiNT-main
installdir=/home/pi/scripts/RPiNT

INSTALL_CMD="apt-get -y install"
PIP3_INSTALL_CMD="pip3 install --upgrade"

echo "Do you want to install the RPiNT software?"
read -r -p "$1 [y/N] " response < /dev/tty
if [[ $response =~ ^(yes|y|Y)$ ]]; then
    echo "Greats ! The installation has started."
else
    echo "OK. Exiting"
    exit
fi

raspi-config nonint do_i2c 0
raspi-config nonint do_spi 0

raspi-config nonint do_change_timezone Europe/Warsaw

[[ -d $installdir ]] || mkdir -p $installdir

curl -sS $repourl -L -o $downloaddir/RPiNT.zip
unzip  $downloaddir/RPiNT.zip -d $downloaddir
cp $unpackdir/* $installdir
chmod u+x $installdir/*.py
chown -R pi.pi $installdir

apt-get -y update
apt-get -y upgrade
apt-get -y autoremove

$INSTALL_CMD git
$INSTALL_CMD lldpd
$INSTALL_CMD libfreetype6-dev
$INSTALL_CMD libopenjp2-7
$INSTALL_CMD libtiff5
$INSTALL_CMD libjpeg-dev

$INSTALL_CMD build-essential
$INSTALL_CMD python3-dev
$INSTALL_CMD python3-pip
$INSTALL_CMD python3-setuptools
$INSTALL_CMD python3-wheel
$INSTALL_CMD python3-gpiozero
$INSTALL_CMD python3-systemd
$INSTALL_CMD python3-pil

$PIP3_INSTALL_CMD smbus2
$PIP3_INSTALL_CMD redis
$PIP3_INSTALL_CMD pid
$PIP3_INSTALL_CMD PyYAML
$PIP3_INSTALL_CMD luma.core luma.oled luma.lcd

$INSTALL_CMD redis-server
systemctl enable redis-server.service
sysctl -w vm.overcommit_memory=1
sysctl -w net.core.somaxconn=512
echo 'vm.overcommit_memory=1' | tee -a /etc/sysctl.conf
echo 'net.core.somaxconn=512' | tee -a /etc/sysctl.conf
echo 'maxmemory 100mb' | tee -a /etc/redis/redis.conf
systemctl start redis-server.service

mv $unpackdir/rpint.service /lib/systemd/system/rpint.service
systemctl daemon-reload
systemctl enable rpint.service

systemctl stop dphys-swapfile.service 2>/dev/null
systemctl disable dphys-swapfile.service 2>/dev/null
systemctl disable systemd-random-seed.service 2>/dev/null
systemctl disable hciuart.service 2>/dev/null
systemctl disable dhcpcd.service 2>/dev/null
systemctl disable --now systemd-timesyncd.service 2>/dev/null

echo "sudo ip link set dev eth0 up" | tee -a /etc/rc.local

rm $downloaddir/RPiNT.zip
rmdir --ignore-fail-on-non-empty $unpackdir
