# FATMAX PHOTOBOOTH

NOTE: This is designed and tested to work with a Nikon D700 (changing this camera shouldn't effect application),
and the Canon Selphy ES30 (install and code changes are needed to handle alternate printers) 

## Test
Unit Tests and code coverage
> python -m unittest main_test.py
> 
> coverage report
> 
> coverage html

## Install
This is designed to run on a raspberry pi. On a basic pi OS, you'll need to do the following:
1. Update the software repos
> sudo apt update 
>
> sudo apt upgrade
2. Install python3.8
> sudo apt install software-properties-common
> 
> sudo add-apt-repository ppa:deadsnakes/ppa
> 
> sudo apt update
> 
> sudo apt upgrade
> 
> sudo apt install python3.8
3. Install gphoto2
> sudo apt install gphoto2
> 
> sudo apt install libgphoto2-dev
>
> sudo apt install libgphoto2-6
4. Install cups and gutenprint
> sudo apt install printer-driver-gutenprint=5.3.3-4
> 
> sudo apt install cups
> 
> sudo apt install libcups2-dev
5. Install printer
> lpinfo -v
> 
> lpadmin -p "Selphy" -v {device-uri} -E -m gutenprint.5.3://canon-es30/expert
6. Copy over script
> TBD
7. Setup to run on start
> TBD

## Execute Manually
> python3.8 main.py

## Usage
Note that these steps need to be run in order, or the application won't find the camera or printer
Also note that all the steps in [Setup](#setup) need to have been run

## Notes
- This project is using python 3.8

