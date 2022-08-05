# RPiNT

Link Layer Discovery Tool based on RPi Zero

## Installation

### Installing operating system images 

Download the image [Raspberry Pi OS Lite](https://downloads.raspberrypi.org/raspios_lite_armhf_latest)

To writing an image to the SD card, use [Etcher](https://etcher.io/) an image writing tool or use [Imager](https://www.raspberrypi.org/downloads/)

If you're not using Etcher, you'll need to unzip .zip downloads to get the image file (.img) to write to your SD card.

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

Reading lldp data is done automatically after connecting UTP cable to the device. The process of reading lldp data takes a few seconds.

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
