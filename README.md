# RPiNT

Link Layer Discovery Tool based on RPi Zero

![RPiNT](https://github.com/darton/RPiNT/blob/main/RPiNT.jpg)

![RPiNT](https://github.com/darton/RPiNT/blob/main/IMG_1695.jpeg)

![RPiNT](https://github.com/darton/RPiNT/blob/main/IMG_1696.jpeg)

![RPiNT](https://github.com/darton/RPiNT/blob/main/IMG_1697.jpeg)

![RPiNT](https://github.com/darton/RPiNT/blob/main/IMG_1698.jpeg)

## Installation

### Installing operating system images 

Download the image [Raspberry Pi OS Lite](https://downloads.raspberrypi.org/raspios_lite_armhf_latest)

To writing an image to the SD card, use [Imager](https://www.raspberrypi.org/downloads/) 

### Run installation script

Running the following command will download and run the script.

```
curl -sS https://raw.githubusercontent.com/darton/RPiNT/main/install.sh |sudo bash
```

Start/Stop RPiNT
```
sudo systemctl start rpint.service
sudo systemclt stop rpint.service
```

## Usage

### rpint.toml config file

auto_lldp_read = true

Reading lldp data is done automatically after connecting UTP cable to the device. The process of reading lldp data takes a few seconds.


auto_lldp_read = false

To read lldp data, connect the UTP cable to the device, wait a few seconds, press "key 1" a few seconds. If there is no reading, try again.


To shut down the system, press "KEY1" for more than 5 seconds.

## B.o.M - Bill of Materials

* [1.44inch-lcd-hat](https://www.waveshare.com/product/raspberry-pi/displays/lcd-oled/1.44inch-lcd-hat.htm)
* [eth-usb-hub-hat](https://www.waveshare.com/product/raspberry-pi/hats/interface-power/eth-usb-hub-hat.htm)
* [ups-hat-c](https://www.waveshare.com/product/raspberry-pi/hats/interface-power/ups-hat-c.htm)
* [raspberry-pi-zero](https://www.waveshare.com/product/raspberry-pi/boards-kits/raspberry-pi-zero/raspberry-pi-zero.htm)

## Wiki

* [UPS_HAT_(C)](https://www.waveshare.com/wiki/UPS_HAT_(C))
* [USB_HUB_HAT](https://www.waveshare.com/wiki/ETH/USB_HUB_HAT)
* [1.44inch_LCD_HAT](https://www.waveshare.com/wiki/1.44inch_LCD_HAT)
* [raspberry-pi-zero](https://www.raspberrypi.com/documentation/computers/raspberry-pi.html#raspberry-pi-zero)
