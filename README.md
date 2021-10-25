# FATMAX PHOTOBOOTH

NOTE: This is designed and tested to work with a Nikon D700 (changing this camera shouldn't affect application),
and the Canon Selphy ES30 (install and code changes are needed to handle alternate printers) 

## Test
Unit Tests and code coverage
```shell
coverage run -m unittest main_test.py
coverage report
coverage html
````
## Install
This is designed to run on a raspberry pi. On a basic pi OS, you'll need to do the following:
1. Update the software repos
```shell
sudo apt update 
sudo apt upgrade
```
2. Install python3.8
```shell
sudo apt install software-properties-common
sudo apt-get install -y build-essential tk-dev libncurses5-dev libncursesw5-dev libreadline6-dev libdb5.3-dev libgdbm-dev libsqlite3-dev libssl-dev libbz2-dev libexpat1-dev liblzma-dev zlib1g-dev libffi-dev
wget https://www.python.org/ftp/python/3.8.0/Python-3.8.0.tar.xz
tar xf Python-3.8.0.tar.xz
cd Python-3.8.0
./configure --prefix=/usr/local/opt/python-3.8.0
make -j 4
sudo make altinstall
cd ..
sudo rm -r Python-3.8.0
rm Python-3.8.0.tar.xz
echo "alias python=/usr/local/opt/python-3.8.0/bin/python3.8" >> ~/.bashrc
sudo echo "alias python=/usr/local/opt/python-3.8.0/bin/python3.8" >> /root/.bashrc
. ~/.bashrc
python --version
sudo chown -R max.max /usr/local/opt/python-3.8.0/
```
3. Install gphoto2
```shell
sudo apt install gphoto2
sudo apt install libgphoto2-dev
sudo apt install libgphoto2-6
```
4. Install cups and gutenprint
```shell
sudo apt install cups
sudo apt install libcups2-dev
sudo apt install printer-driver-gutenprint=5.3.1-7
```
5. Install imagemagick
```shell
sudo apt-get install imagemagick
```
6. Install printer
```shell
lpinfo -v
lpadmin -p "Selphy" -v [device-uri] -E -m gutenprint.5.3://canon-es30/expert
```
7. Copy over script
```shell
scp main.py [raspberry-ip]:~/
scp logo.jpg [raspberry-ip]:~/
scp requirements.txt [raspberry-ip]:~/
```
8. Setup modules
```shell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```
9. Setup to run on start
- Edit the `/etc/rc.local` file
```shell
sudo vim /etc/rc.local
```
- Before the `exit 0` line add the below
```shell
# Runs our photobooth program
sudo /usr/local/opt/python-3.8.0/bin/python3.8 /home/max/main.py &
```
## Execute Manually
```shell
python main.py
```
## Usage
Note that these steps need to be run in order, or 
the application won't find the camera or printer
Also note that all the steps in [Install](#install) 
need to have been run
1. Plug the printer into the raspberry pi using the 
   mini usb square cable
2. Plug the printer in the power outlet
3. Turn on the printer
4. Plug the camera into the raspberry pi using the 
   mini usb otg cable
5. Turn on the camera
6. Plug the raspberry pi into a power outlet using 
   the micro usb cable and power adapter
7. Wait until the printer indicates it is connected
8. Take photos
9. Based on the default config, every three photos 
   will be printed out with a logo
> Note that it might take up to a minute between the 
> third photo being taken and the printer starts printing

## Notes
- This project is using python 3.8

